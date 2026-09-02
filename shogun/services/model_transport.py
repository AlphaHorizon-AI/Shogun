"""Shared HTTP/Codex transport for model chat-completion requests."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import httpx

from shogun.services.codex_app_server import CodexAppServerError, get_codex_app_server


def is_chatgpt_subscription(auth_type: Any) -> bool:
    return str(getattr(auth_type, "value", auth_type) or "").casefold() == "chatgpt"


@dataclass(slots=True)
class ModelTransportResponse:
    status_code: int
    text: str

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300

    @property
    def content(self) -> bytes:
        return self.text.encode()

    def json(self) -> Any:
        return json.loads(self.text)


async def model_chat_completion(
    *,
    auth_type: Any,
    base_url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: float,
) -> httpx.Response | ModelTransportResponse:
    """Return one OpenAI-compatible response from HTTP or Codex app-server."""

    if not is_chatgpt_subscription(auth_type):
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{base_url.rstrip('/')}/chat/completions",
                headers=headers,
                json=payload,
            )
        return response

    content = ""
    tool_calls: list[dict[str, Any]] = []
    try:
        async for event in get_codex_app_server().run_completion(payload, timeout=timeout, stream=False):
            if event.get("type") == "content":
                content += str(event.get("content") or "")
            elif event.get("type") == "tool_result":
                content = str(event.get("content") or "")
                tool_calls = list(event.get("tool_calls") or [])
    except CodexAppServerError as exc:
        return ModelTransportResponse(exc.status_code, json.dumps({"error": {"message": str(exc)}}))

    message: dict[str, Any] = {"role": "assistant", "content": content or None}
    if tool_calls:
        message["tool_calls"] = tool_calls
    response_payload = {
        "id": f"chatcmpl-codex-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "model": payload.get("model"),
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": "tool_calls" if tool_calls else "stop",
            }
        ],
    }
    return ModelTransportResponse(200, json.dumps(response_payload, ensure_ascii=False))


class _CodexStreamResponse:
    status_code = 200

    def __init__(self, payload: dict[str, Any], timeout: float):
        self.payload = payload
        self.timeout = timeout

    async def aread(self) -> bytes:
        return b""

    async def aiter_lines(self) -> AsyncIterator[str]:
        model = self.payload.get("model")
        async for event in get_codex_app_server().run_completion(
            self.payload,
            timeout=self.timeout,
            stream=True,
        ):
            delta: dict[str, Any] = {}
            if event.get("type") == "content":
                delta["content"] = str(event.get("content") or "")
            elif event.get("type") == "tool_result":
                content = str(event.get("content") or "")
                if content:
                    delta["content"] = content
                calls = list(event.get("tool_calls") or [])
                if calls:
                    delta["tool_calls"] = [
                        {
                            "index": index,
                            "id": call.get("id"),
                            "type": "function",
                            "function": call.get("function") or {},
                        }
                        for index, call in enumerate(calls)
                    ]
            if delta:
                chunk = {
                    "id": f"chatcmpl-codex-{uuid.uuid4().hex}",
                    "object": "chat.completion.chunk",
                    "model": model,
                    "choices": [{"index": 0, "delta": delta, "finish_reason": None}],
                }
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}"
        yield "data: [DONE]"


class _ErrorStreamResponse:
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self._content = json.dumps({"error": {"message": message}}).encode()

    async def aread(self) -> bytes:
        return self._content

    async def aiter_lines(self) -> AsyncIterator[str]:
        if False:  # pragma: no cover - keeps this an async generator
            yield ""


@asynccontextmanager
async def model_chat_stream(
    *,
    auth_type: Any,
    base_url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: float,
) -> AsyncIterator[Any]:
    """Yield an httpx-like SSE response for either supported transport."""

    if not is_chatgpt_subscription(auth_type):
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                f"{base_url.rstrip('/')}/chat/completions",
                headers=headers,
                json=payload,
            ) as response:
                yield response
        return

    try:
        state = await get_codex_app_server().account(refresh=False)
        account = state.get("account") or {}
        if account.get("type") != "chatgpt":
            yield _ErrorStreamResponse(
                401,
                "ChatGPT/Codex is not connected. Open this provider in Katana and sign in first.",
            )
            return
    except CodexAppServerError as exc:
        yield _ErrorStreamResponse(exc.status_code, str(exc))
        return
    yield _CodexStreamResponse(payload, timeout)
