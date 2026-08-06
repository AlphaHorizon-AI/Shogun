"""Model-specific tool-calling profile discovery and normalization.

Providers disagree about how tools are advertised and how a model emits a
call.  Shogun stores a small, versioned profile on every registry entry and
normalizes all supported formats into one canonical call before ToolGate or
Torii sees it.  Governance remains downstream and authoritative.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

import httpx

PROFILE_KEY = "tool_calling_profile"
PROFILE_VERSION = 1

CANONICAL_CALL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["tool", "arguments"],
    "properties": {
        "id": {"type": "string"},
        "tool": {"type": "string", "minLength": 1},
        "arguments": {"type": "object"},
    },
    "additionalProperties": False,
}

PROFILE_CATALOG: dict[str, dict[str, Any]] = {
    "openai_native_v1": {
        "mode": "native",
        "request_schema": "openai.tools.v1",
        "response_schema": "openai.tool_calls.v1",
        "result_schema": "openai.tool_message.v1",
        "description": "Native tools parameter and structured tool_calls response.",
    },
    "shogun_text_v1": {
        "mode": "text",
        "request_schema": "shogun.prompt_tools.v1",
        "response_schema": "shogun.tool_call_text.v1",
        "result_schema": "shogun.tool_result_text.v1",
        "description": "Shogun prompt-injected JSON/XML call format and parser.",
    },
    "unsupported_v1": {
        "mode": "unsupported",
        "request_schema": "none",
        "response_schema": "none",
        "result_schema": "none",
        "description": "No safe tool-calling transport is available.",
    },
}

OPENAI_COMPATIBLE_PROVIDERS = {
    "openai",
    "openrouter",
    "google",
    "ollama",
    "lmstudio",
    "local",
    "custom",
}

# These families can still use Shogun's text protocol, but their commonly
# distributed Ollama templates do not reliably expose native tools.
OLLAMA_TEXT_FALLBACK_FAMILIES = (
    "deepseek-r1",
    "deepseek-r2",
    "gemma3",
    "gemma 3",
    "phi-2",
    "phi-3",
    "phi-4",
    "tinyllama",
    "stablelm",
    "codellama",
    "starcoder",
)

OLLAMA_NATIVE_FAMILIES = (
    "gemma4",
    "gemma 4",
    "llama3.1",
    "llama3.2",
    "llama3.3",
    "qwen2",
    "qwen2.5",
    "qwen3",
    "mistral",
    "mixtral",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fingerprint(provider: str, model_id: str, metadata: dict[str, Any] | None = None) -> str:
    metadata = metadata or {}
    material = json.dumps(
        {
            "provider": provider,
            "model_id": model_id,
            "capabilities": metadata.get("capabilities") or [],
            "template": str(metadata.get("template") or "")[:4096],
            "details": metadata.get("details") or {},
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]


def make_profile(
    adapter_id: str,
    *,
    status: str,
    source: str,
    confidence: float,
    provider: str,
    model_id: str,
    metadata: dict[str, Any] | None = None,
    last_error: str | None = None,
    tested: bool = False,
) -> dict[str, Any]:
    adapter = PROFILE_CATALOG[adapter_id]
    return {
        "version": PROFILE_VERSION,
        "adapter_id": adapter_id,
        "mode": adapter["mode"],
        "request_schema": adapter["request_schema"],
        "response_schema": adapter["response_schema"],
        "result_schema": adapter["result_schema"],
        "canonical_schema": "shogun.tool_call.v1",
        "fallback_adapter_id": "shogun_text_v1" if adapter_id != "unsupported_v1" else None,
        "fallback_enabled": adapter_id != "unsupported_v1",
        "status": status,
        "source": source,
        "confidence": round(max(0.0, min(1.0, float(confidence))), 2),
        "provider": provider,
        "model_id": model_id,
        "metadata_fingerprint": _fingerprint(provider, model_id, metadata),
        "last_tested_at": _utc_now() if tested else None,
        "last_error": str(last_error)[:500] if last_error else None,
    }


def infer_tool_calling_profile(
    model_id: str,
    provider: str,
    *,
    metadata: dict[str, Any] | None = None,
    tool_capability: bool | None = None,
) -> dict[str, Any]:
    """Infer the safest adapter without loading or invoking the model."""
    provider_key = str(provider or "").strip().lower()
    model_key = str(model_id or "").strip().lower().replace("_", "-")
    metadata = metadata or {}
    advertised = {str(item).lower() for item in (metadata.get("capabilities") or [])}

    if provider_key == "ollama" and advertised:
        if "tools" in advertised or "tool_use" in advertised:
            return make_profile(
                "openai_native_v1",
                status="detected",
                source="ollama_metadata",
                confidence=0.98,
                provider=provider_key,
                model_id=model_id,
                metadata=metadata,
            )
        return make_profile(
            "shogun_text_v1",
            status="fallback",
            source="ollama_metadata",
            confidence=0.96,
            provider=provider_key,
            model_id=model_id,
            metadata=metadata,
        )

    if provider_key == "ollama":
        if any(name in model_key for name in OLLAMA_TEXT_FALLBACK_FAMILIES):
            adapter, confidence = "shogun_text_v1", 0.9
        elif any(name in model_key for name in OLLAMA_NATIVE_FAMILIES):
            adapter, confidence = "openai_native_v1", 0.78
        else:
            adapter, confidence = "shogun_text_v1", 0.62
        return make_profile(
            adapter,
            status="inferred" if adapter == "openai_native_v1" else "fallback",
            source="model_family",
            confidence=confidence,
            provider=provider_key,
            model_id=model_id,
            metadata=metadata,
        )

    if provider_key in OPENAI_COMPATIBLE_PROVIDERS and tool_capability is not False:
        return make_profile(
            "openai_native_v1",
            status="inferred",
            source="provider_adapter",
            confidence=0.82,
            provider=provider_key,
            model_id=model_id,
            metadata=metadata,
        )

    # Anthropic is currently reached through provider-specific deployments in
    # Shogun. Until a native content-block adapter is selected and verified,
    # the canonical text protocol is safer than guessing its wire format.
    if provider_key == "anthropic" or tool_capability is not False:
        return make_profile(
            "shogun_text_v1",
            status="fallback",
            source="shogun_default",
            confidence=0.7,
            provider=provider_key,
            model_id=model_id,
            metadata=metadata,
        )

    return make_profile(
        "unsupported_v1",
        status="unsupported",
        source="capability_metadata",
        confidence=0.9,
        provider=provider_key,
        model_id=model_id,
        metadata=metadata,
    )


def stored_or_inferred_profile(item: Any) -> dict[str, Any]:
    state = dict(getattr(item, "config_json", None) or {})
    stored = state.get(PROFILE_KEY)
    if isinstance(stored, dict) and stored.get("version") == PROFILE_VERSION and stored.get("adapter_id"):
        return dict(stored)
    capabilities = dict(getattr(item, "capabilities", None) or {})
    return infer_tool_calling_profile(
        str(getattr(item, "model_id", "")),
        str(getattr(item, "provider", "")),
        tool_capability=capabilities.get("tool_use"),
    )


def persist_profile(item: Any, profile: dict[str, Any]) -> None:
    state = dict(getattr(item, "config_json", None) or {})
    state[PROFILE_KEY] = dict(profile)
    item.config_json = state
    capabilities = dict(getattr(item, "capabilities", None) or {})
    capabilities["tool_use"] = profile.get("mode") != "unsupported"
    item.capabilities = capabilities


def profile_catalog_payload() -> dict[str, Any]:
    return {
        "version": PROFILE_VERSION,
        "canonical_schema_id": "shogun.tool_call.v1",
        "canonical_schema": CANONICAL_CALL_SCHEMA,
        "adapters": PROFILE_CATALOG,
    }


def normalize_native_tool_calls(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize OpenAI, Ollama, or Anthropic response objects."""
    message: dict[str, Any] = {}
    choices = payload.get("choices") or []
    if choices and isinstance(choices[0], dict):
        message = choices[0].get("message") or choices[0].get("delta") or {}
    elif isinstance(payload.get("message"), dict):
        message = payload["message"]

    raw_calls = message.get("tool_calls") or payload.get("tool_calls") or []
    normalized: list[dict[str, Any]] = []
    for index, call in enumerate(raw_calls):
        if not isinstance(call, dict):
            continue
        function = call.get("function") or {}
        name = str(function.get("name") or call.get("name") or "").strip()
        arguments = function.get("arguments", call.get("arguments", {}))
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments or "{}")
            except json.JSONDecodeError:
                arguments = {}
        if name and isinstance(arguments, dict):
            normalized.append({
                "id": str(call.get("id") or f"call-{index}-{uuid.uuid4().hex[:8]}"),
                "tool": name,
                "arguments": arguments,
            })

    # Anthropic native content blocks.
    content = payload.get("content") or message.get("content") or []
    if isinstance(content, list):
        for index, block in enumerate(content):
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            name = str(block.get("name") or "").strip()
            arguments = block.get("input") or {}
            if name and isinstance(arguments, dict):
                normalized.append({
                    "id": str(block.get("id") or f"call-{index}-{uuid.uuid4().hex[:8]}"),
                    "tool": name,
                    "arguments": arguments,
                })
    return normalized


def _json_candidates(text: str) -> Iterable[Any]:
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    for block in re.findall(r"```(?:json|tool_call)?\s*(.*?)```", cleaned, flags=re.DOTALL | re.IGNORECASE):
        try:
            yield json.loads(block.strip())
        except json.JSONDecodeError:
            pass
    for match in re.findall(r"<tool_call>\s*(.*?)\s*</tool_call>", cleaned, flags=re.DOTALL | re.IGNORECASE):
        candidate = match.strip()
        try:
            yield json.loads(candidate)
            continue
        except json.JSONDecodeError:
            pass
        function = re.match(r"([A-Za-z_][\w.-]*)\s*\((.*)\)\s*$", candidate, flags=re.DOTALL)
        if function:
            raw = function.group(2).strip() or "{}"
            try:
                args = json.loads(raw)
            except json.JSONDecodeError:
                args = {}
            yield {"tool": function.group(1), "arguments": args}
    try:
        yield json.loads(cleaned)
    except json.JSONDecodeError:
        pass


def normalize_text_tool_calls(text: str, allowed_names: Iterable[str]) -> list[dict[str, Any]]:
    allowed = {str(name) for name in allowed_names}
    normalized: list[dict[str, Any]] = []
    for candidate in _json_candidates(text):
        values = candidate if isinstance(candidate, list) else [candidate]
        for value in values:
            if not isinstance(value, dict):
                continue
            function = value.get("function") if isinstance(value.get("function"), dict) else {}
            name = str(value.get("tool") or value.get("name") or function.get("name") or "").strip()
            arguments = value.get("arguments", function.get("arguments", {}))
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments or "{}")
                except json.JSONDecodeError:
                    arguments = {}
            if name in allowed and isinstance(arguments, dict):
                normalized.append({
                    "id": str(value.get("id") or f"text-{uuid.uuid4().hex[:10]}"),
                    "tool": name,
                    "arguments": arguments,
                })
    return normalized


async def probe_tool_calling_profile(
    *,
    provider: str,
    base_url: str,
    model_id: str,
    api_key: str | None = None,
    timeout_seconds: float = 30.0,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Ask a model to format a harmless echo call without executing it."""
    provider_key = provider.lower()
    root = base_url.rstrip("/")
    if provider_key == "ollama" and not root.endswith("/v1"):
        root += "/v1"
    url = f"{root}/chat/completions"
    marker = f"KATANA-{uuid.uuid4().hex[:10]}"
    tool = {
        "type": "function",
        "function": {
            "name": "echo_tool",
            "description": "Return the supplied text unchanged.",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
                "additionalProperties": False,
            },
        },
    }
    request = {
        "model": model_id,
        "messages": [{"role": "user", "content": f"Call echo_tool with text {marker}. Do not answer normally."}],
        "stream": False,
        "temperature": 0,
        "max_tokens": 160,
        "tools": [tool],
        "tool_choice": {"type": "function", "function": {"name": "echo_tool"}},
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(url, headers=headers, json=request)
            if response.status_code >= 400:
                # Native tools and forced tool choice are separate provider
                # features. Retry without forcing before selecting fallback.
                request.pop("tool_choice", None)
                response = await client.post(url, headers=headers, json=request)
        body_text = response.text[:2000]
        if response.is_success:
            payload = response.json()
            calls = normalize_native_tool_calls(payload)
            native = next((call for call in calls if call["tool"] == "echo_tool"), None)
            if native:
                profile = make_profile(
                    "openai_native_v1",
                    status="verified",
                    source="katana_probe",
                    confidence=1.0,
                    provider=provider_key,
                    model_id=model_id,
                    tested=True,
                )
                return profile, {"success": True, "mode": "native", "call": native}

            choices = payload.get("choices") or []
            message = choices[0].get("message", {}) if choices else payload.get("message", {})
            content = message.get("content") if isinstance(message, dict) else ""
            if isinstance(content, list):
                content = "\n".join(str(part.get("text") or "") for part in content if isinstance(part, dict))
            text_calls = normalize_text_tool_calls(str(content or ""), {"echo_tool"})
            if text_calls:
                profile = make_profile(
                    "shogun_text_v1",
                    status="verified",
                    source="katana_probe",
                    confidence=0.95,
                    provider=provider_key,
                    model_id=model_id,
                    tested=True,
                )
                return profile, {"success": True, "mode": "text", "call": text_calls[0]}

            profile = make_profile(
                "shogun_text_v1",
                status="fallback",
                source="katana_probe",
                confidence=0.6,
                provider=provider_key,
                model_id=model_id,
                tested=True,
                last_error="The model responded but emitted no recognized tool call.",
            )
            return profile, {"success": False, "mode": "text", "error": profile["last_error"]}

        profile = make_profile(
            "shogun_text_v1",
            status="fallback",
            source="katana_probe",
            confidence=0.85 if response.status_code == 400 else 0.55,
            provider=provider_key,
            model_id=model_id,
            tested=True,
            last_error=f"HTTP {response.status_code}: {body_text}",
        )
        return profile, {
            "success": False,
            "mode": "text",
            "status_code": response.status_code,
            "error": profile["last_error"],
        }
    except Exception as exc:
        profile = infer_tool_calling_profile(model_id, provider_key)
        profile["last_tested_at"] = _utc_now()
        profile["last_error"] = f"Probe unavailable: {str(exc)[:400]}"
        return profile, {"success": False, "mode": profile["mode"], "error": profile["last_error"]}
