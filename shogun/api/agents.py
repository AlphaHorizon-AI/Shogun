"""Agent routes — CRUD for Shogun and Samurai agents."""

from __future__ import annotations

import json
import time
import uuid
import shutil
import os
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse

from shogun.api.deps import get_agent_service
from shogun.schemas.agents import (
    AgentCreate,
    AgentResponse,
    AgentUpdate,
    SamuraiProfileCreate,
    SamuraiProfileResponse,
)
from shogun.schemas.common import ApiResponse
from shogun.services.agent_service import AgentService

router = APIRouter(prefix="/agents", tags=["Agents"])

# ── System-context cache (90 s TTL) to avoid DB hits on every chat turn ──
_CTX_CACHE: dict = {"data": None, "ts": 0.0}
_CTX_TTL = 90  # seconds

async def _get_system_context() -> dict:
    """Return cached samurai/provider/tool counts, refreshed every 90 s."""
    if time.monotonic() - _CTX_CACHE["ts"] < _CTX_TTL and _CTX_CACHE["data"]:
        return _CTX_CACHE["data"]

    from shogun.db.engine import async_session_factory
    from shogun.db.models.model_provider import ModelProvider
    from shogun.db.models.agent import Agent as AgentModel
    from shogun.db.models.tool_connector import ToolConnector
    from sqlalchemy import select, func

    async with async_session_factory() as db:
        samurai_result = await db.execute(
            select(func.count()).select_from(AgentModel)
            .where(AgentModel.agent_type == "samurai", AgentModel.is_deleted == False)
        )
        samurai_count = samurai_result.scalar() or 0

        provider_result = await db.execute(
            select(ModelProvider).where(ModelProvider.status == "connected")
        )
        active_providers = provider_result.scalars().all()

        tool_result = await db.execute(
            select(func.count()).select_from(ToolConnector)
            .where(ToolConnector.is_deleted == False)
        )
        tool_count = tool_result.scalar() or 0

    ctx = {
        "samurai_count": samurai_count,
        "tool_count": tool_count,
        "provider_summary": ", ".join(
            f"{p.name} ({p.provider_type})" for p in active_providers
        ) or "none configured",
    }
    _CTX_CACHE["data"] = ctx
    _CTX_CACHE["ts"] = time.monotonic()
    return ctx


@router.get("/shogun", response_model=ApiResponse)
async def get_primary_shogun(svc: AgentService = Depends(get_agent_service)):
    from shogun.db.models.agent import Agent
    filters = [Agent.agent_type == "shogun", Agent.is_primary == True, Agent.is_deleted == False]
    records, _ = await svc.get_all(filters=filters)
    if not records:
        raise HTTPException(status_code=404, detail="Primary Shogun not found")
    return ApiResponse(data=AgentResponse.model_validate(records[0]))


@router.get("", response_model=ApiResponse)
async def list_agents(
    agent_type: str | None = None,
    status: str | None = None,
    svc: AgentService = Depends(get_agent_service),
):
    filters = []
    from shogun.db.models.agent import Agent

    filters.append(Agent.is_deleted == False)
    if agent_type:
        filters.append(Agent.agent_type == agent_type)
    if status:
        filters.append(Agent.status == status)

    records, total = await svc.get_all(filters=filters)
    return ApiResponse(
        data=[AgentResponse.model_validate(r) for r in records],
        meta={"total": total},
    )


@router.get("/{agent_id}", response_model=ApiResponse)
async def get_agent(
    agent_id: uuid.UUID,
    svc: AgentService = Depends(get_agent_service),
):
    record = await svc.get_by_id(agent_id)
    if not record or record.is_deleted:
        raise HTTPException(status_code=404, detail="Agent not found")
    return ApiResponse(data=AgentResponse.model_validate(record))


@router.post("", response_model=ApiResponse, status_code=201)
async def create_agent(
    body: AgentCreate,
    svc: AgentService = Depends(get_agent_service),
):
    data = body.model_dump()
    data["memory_scope"] = data["memory_scope"] if isinstance(data["memory_scope"], dict) else data["memory_scope"].model_dump()
    record = await svc.create(**data)
    return ApiResponse(data=AgentResponse.model_validate(record))


@router.patch("/{agent_id}", response_model=ApiResponse)
async def update_agent(
    agent_id: uuid.UUID,
    body: AgentUpdate,
    svc: AgentService = Depends(get_agent_service),
):
    update_data = body.model_dump(exclude_unset=True)
    if "memory_scope" in update_data and update_data["memory_scope"] is not None:
        update_data["memory_scope"] = update_data["memory_scope"].model_dump() if hasattr(update_data["memory_scope"], "model_dump") else update_data["memory_scope"]
    record = await svc.update(agent_id, **update_data)
    if not record:
        raise HTTPException(status_code=404, detail="Agent not found")
    return ApiResponse(data=AgentResponse.model_validate(record))


@router.post("/{agent_id}/suspend", response_model=ApiResponse)
async def suspend_agent(
    agent_id: uuid.UUID,
    svc: AgentService = Depends(get_agent_service),
):
    record = await svc.suspend(agent_id)
    if not record:
        raise HTTPException(status_code=404, detail="Agent not found")
    return ApiResponse(data=AgentResponse.model_validate(record))


@router.post("/{agent_id}/resume", response_model=ApiResponse)
async def resume_agent(
    agent_id: uuid.UUID,
    svc: AgentService = Depends(get_agent_service),
):
    record = await svc.resume(agent_id)
    if not record:
        raise HTTPException(status_code=404, detail="Agent not found")
    return ApiResponse(data=AgentResponse.model_validate(record))


@router.delete("/{agent_id}", response_model=ApiResponse)
async def delete_agent(
    agent_id: uuid.UUID,
    svc: AgentService = Depends(get_agent_service),
):
    deleted = await svc.delete(agent_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Agent not found")
    return ApiResponse(data={"deleted": True})


@router.post("/{agent_id}/avatar", response_model=ApiResponse)
async def upload_agent_avatar(
    agent_id: uuid.UUID,
    file: UploadFile = File(...),
    svc: AgentService = Depends(get_agent_service),
):
    """Upload a profile picture for an agent."""
    from shogun.config import settings
    
    # Verify agent exists
    agent = await svc.get_by_id(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Determine file extension and create unique filename
    ext = Path(file.filename).suffix or ".png"
    filename = f"avatar_{agent_id.hex}_{int(datetime.now().timestamp())}{ext}"
    
    # Ensure directory exists (redundant since settings.ensure_directories() is called on startup)
    upload_dir = Path(settings.uploads_path)
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    dest_path = upload_dir / filename
    
    try:
        with open(dest_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Update agent record with the new avatar URL
        avatar_url = f"/uploads/{filename}"
        await svc.update(agent_id, avatar_url=avatar_url)
        
        return ApiResponse(data={"avatar_url": avatar_url})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload avatar: {str(e)}")


@router.put("/{agent_id}/samurai-profile", response_model=ApiResponse)
async def update_samurai_profile(
    agent_id: uuid.UUID,
    body: SamuraiProfileCreate,
    svc: AgentService = Depends(get_agent_service),
):
    profile = await svc.update_samurai_profile(agent_id, **body.model_dump())
    return ApiResponse(data=SamuraiProfileResponse.model_validate(profile))


@router.post("/shogun/chat")
async def shogun_chat(
    body: dict,
    svc: AgentService = Depends(get_agent_service),
):
    """Stream chat tokens from the primary Shogun agent via SSE."""
    import httpx
    from shogun.db.models.agent import Agent
    user_msg: str = body.get("message", "").strip()
    history: list = body.get("history", [])

    if not user_msg:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    return await _shogun_chat_internal(user_msg, history, svc)


def _detect_task_type(message: str) -> str:
    """Simple heuristic to detect task intent. Future: use an LLM classifier."""
    triggers = (
        "search", "find", "look up", "lookup", "google",
        "latest", "current", "today", "right now", "news",
        "what happened", "who is", "what is", "where is",
        "when did", "when is", "how much", "price of",
        "weather", "score", "stock", "release", "announced",
        "recently", "2024", "2025", "live",
    )
    msg_lower = message.lower()
    if any(t in msg_lower for t in triggers):
        return "research"
    return "*"


async def _shogun_chat_internal(user_msg: str, history: list, svc: AgentService):
    import httpx
    from shogun.db.models.agent import Agent
    from shogun.db.models.model_provider import ModelProvider
    from shogun.db.models.model_definition import ModelDefinition
    from shogun.db.models.model_routing import ModelRoutingProfile
    from shogun.db.models.operator import Operator
    from shogun.api.deps import get_db
    from sqlalchemy import select
    import uuid as _uuid

    # ── 1. Load primary Shogun agent ──────────────────────────────
    filters = [Agent.agent_type == "shogun", Agent.is_primary == True, Agent.is_deleted == False]
    records, _ = await svc.get_all(filters=filters)
    if not records:
        raise HTTPException(status_code=404, detail="Primary Shogun agent not found")
    agent = records[0]

    # ── 2. Resolve primary model from settings ────────────────────
    bushido = agent.bushido_settings or {}
    saved_primary: str = bushido.get("primary_model", "")
    saved_provider_id: str = saved_primary.split("::")[0] if "::" in saved_primary else ""
    saved_model_name: str = saved_primary.split("::")[1] if "::" in saved_primary else ""

    provider = None

    # ── 3. Resolve routing profiles and provider ──────────────────
    task_type = _detect_task_type(user_msg)
    _search_model: str | None = None
    provider_name: str | None = None
    res_reason = "primary_agent_model"

    async for db in get_db():
        # ── Step 0: Build Authorized Inventory ──
        authorized_keys = set()
        prov_res = await db.execute(select(ModelProvider).where(ModelProvider.status == "connected"))
        for p in prov_res.scalars().all():
            authorized_keys.add(p.name)
            m_id = p.config.get("model_id") or p.config.get("model")
            if m_id:
                authorized_keys.add(m_id)

        # Get active (default) routing profile
        res = await db.execute(
            select(ModelRoutingProfile).where(ModelRoutingProfile.is_default == True).limit(1)
        )
        profile = res.scalar_one_or_none()
        
        # If we have a special task (like research), check if there's a specific rule
        if profile and task_type != "*":
            rule = next((r for r in profile.rules if r.get("task_type") == task_type), None)
            if rule and rule.get("primary_model_id"):
                try:
                    # Look up the model definition
                    mid = _uuid.UUID(rule["primary_model_id"])
                    res = await db.execute(
                        select(ModelDefinition).where(ModelDefinition.id == mid)
                    )
                    mdef = res.scalar_one_or_none()
                    if mdef and mdef.provider and mdef.provider.status == "connected":
                        # Check if this specific model is authorized in Katana
                        if mdef.model_key in authorized_keys or mdef.display_name in authorized_keys:
                            # Success! Override provider and model
                            provider = mdef.provider
                            model_name = mdef.model_key
                            provider_name = mdef.display_name
                            _search_model = model_name
                            res_reason = f"logic_routing_authorized ({task_type})"
                        else:
                            logger.warning(f"[Routing] Unauthorized model '{mdef.model_key}' blocked. Fallback to primary.")
                            res_reason = f"routing_blocked_unauthorized ({task_type})"
                    else:
                        logger.debug(f"Routing rule skipped: Provider {mdef.provider.name if mdef and mdef.provider else 'unknown'} is NOT connected.")
                except Exception:
                    pass # Fallback to default if anything goes wrong

        # If no routing override, use the saved primary or first connected
        if not provider:
            if saved_provider_id:
                try:
                    res = await db.execute(
                        select(ModelProvider).where(ModelProvider.id == _uuid.UUID(saved_provider_id))
                    )
                    provider = res.scalar_one_or_none()
                except Exception:
                    provider = None

            if not provider:
                res = await db.execute(
                    select(ModelProvider)
                    .where(ModelProvider.status == "connected")
                    .order_by(ModelProvider.created_at)
                    .limit(1)
                )
                provider = res.scalar_one_or_none()
                if provider:
                    res_reason = "auto_fallback_to_connected"
        break

    if not provider:
        async def _no_provider():
            yield f"data: {json.dumps({'type': 'error', 'content': '⚠️ No active model provider found. Go to The Katana → Model Providers and add one.'})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(_no_provider(), media_type="text/event-stream")

    # Endpoint resolve
    PROVIDER_URLS: dict[str, str] = {
        "ollama":     "http://localhost:11434",
        "lmstudio":   "http://localhost:1234/v1",
        "local":      "http://localhost:1234/v1",
        "openai":     "https://api.openai.com/v1",
        "openrouter": "https://openrouter.ai/api/v1",
        "anthropic":  "https://api.anthropic.com/v1",
        "google":     "https://generativelanguage.googleapis.com/v1beta/openai",
        "custom":     "https://api.openai.com/v1",
    }
    base_url: str = provider.base_url or PROVIDER_URLS.get(provider.provider_type, "https://api.openai.com/v1")
    if provider.provider_type == "ollama" and not base_url.rstrip("/").endswith("/v1"):
        base_url = base_url.rstrip("/") + "/v1"

    if not _search_model:
        model_name = (
            saved_model_name
            or provider.config.get("model_id")
            or (provider.config.get("models") or [None])[0]
            or provider.name
        )
        provider_name = provider.name

    api_key = provider.config.get("api_key") or provider.config.get("api-key")
    req_headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        req_headers["Authorization"] = f"Bearer {api_key}"
    if provider.provider_type == "openrouter":
        req_headers["HTTP-Referer"] = "https://shogun.ai"
        req_headers["X-Title"] = "Shogun"

    # ── 4. System context (90 s cache) ────────────────────────────
    ctx = await _get_system_context()

    # ── 4b. Governance context (constitution + mandate) ───────────
    try:
        from shogun.api.kaizen import get_governance_context
        gov = get_governance_context()
    except Exception:
        gov = {"rules_text": "  (not loaded)", "mandate_summary": ""}

    # ── 4c. Fetch Operator Identity ───────────────────────────────
    operator_name = "Daimyo"
    async for db in get_db():
        op_res = await db.execute(select(Operator).limit(1))
        op = op_res.scalar_one_or_none()
        if op and op.display_name:
            operator_name = op.display_name
        break

    # ── 5. Build system prompt ────────────────────────────────────
    persona_name = agent.name or "Shogun"
    system_prompt = f"""You are {persona_name}, the primary AI orchestrator of the Shogun platform.

YOUR OPERATOR:
You report exclusively to your Operator, whose preferred name is '{operator_name}'.
Address them respectfully by this name in your responses.

ABOUT THE SHOGUN PLATFORM:
Shogun is an AI agent orchestration framework. You are the master agent that coordinates everything.
The platform uses Japanese-themed naming:
- **Shogun** (you): The primary orchestrating AI. You reason, plan, and delegate.
- **Samurai**: Sub-agents you can spawn to handle specific tasks (research, coding, analysis, etc.).
- **Dojo**: The UI section where Samurai agents are created, configured, and managed.
- **Katana**: The configuration hub for model providers (Ollama, OpenAI, etc.) and API tools.
- **Comms**: This chat interface where the user talks directly to you.
- **Bushido**: The behavioral rules/directives that govern agent decisions.
- **Kaizen**: The continuous improvement and optimization system.
- **Torii**: The mission and task management system.

CONSTITUTIONAL DIRECTIVES (from Kaizen — you must follow these):
{gov['rules_text']}

YOUR MANDATE:
{gov['mandate_summary']}

CURRENT SYSTEM STATE:
- Active model providers: {ctx['provider_summary']}
- Your current model: {model_name} (Selection logic: {res_reason})
- Samurai agents deployed: {ctx['samurai_count']}
- Registered tools/API connectors: {ctx['tool_count']}

YOUR CAPABILITIES:
- Answer questions and have natural conversations on any topic
- Help the user understand and configure their Shogun system
- When asked to "spawn a samurai", explain that this is done via the Dojo section of the UI, and ask what kind of specialist they need
- Reason about tasks, suggest which Samurai agents would be best for a given workflow
- Help with code, analysis, writing, and general knowledge

BEHAVIOUR:
- Be conversational, warm, and genuinely helpful
- Use platform terminology naturally since the user knows the system
- When you don't know something about live system state, say so honestly
- Do NOT pretend you can directly execute actions
- Format responses with markdown when it improves readability
"""

    # ── 6. Build messages ─────────────────────────────────────────
    messages = [{"role": "system", "content": system_prompt}]
    for h in history[-10:]:
        if h.get("role") in ("user", "assistant") and h.get("content"):
            messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": user_msg})

    provider_name = provider_name or provider.name

    # ── 7. Stream SSE ─────────────────────────────────────────────
    # Log user message for drift monitor
    _append_chat_log("user", user_msg)
    timestamp = datetime.now().isoformat()

    async def generate():
        # Metadata event: lets frontend show model badge immediately
        yield f"data: {json.dumps({'type': 'meta', 'model': model_name, 'provider': provider_name, 'timestamp': timestamp, 'reason': res_reason, 'search': bool(_search_model)})}\n\n"

        assistant_tokens: list[str] = []

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST",
                    f"{base_url.rstrip('/')}/chat/completions",
                    headers=req_headers,
                    json={
                        "model": model_name,
                        "messages": messages,
                        "stream": True,
                        "temperature": 0.7,
                    },
                ) as resp:
                    if resp.status_code >= 400:
                        body_bytes = await resp.aread()
                        err = body_bytes.decode(errors="replace")[:300]
                        yield f"data: {json.dumps({'type': 'error', 'content': f'⚠️ LLM error ({resp.status_code}): {err}'})}\n\n"
                        yield "data: [DONE]\n\n"
                        return

                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            # Log assistant response for drift monitor
                            if assistant_tokens:
                                _append_chat_log("assistant", "".join(assistant_tokens))
                            yield "data: [DONE]\n\n"
                            return
                        try:
                            chunk = json.loads(data_str)
                            content = chunk["choices"][0]["delta"].get("content") or ""
                            if content:
                                assistant_tokens.append(content)
                                yield f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"
                        except Exception:
                            pass  # skip malformed chunks

        except httpx.ConnectError:
            yield f"data: {json.dumps({'type': 'error', 'content': f'⚠️ Cannot connect to {base_url}. Is {provider.provider_type} running?'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': f'⚠️ Unexpected error: {str(e)[:200]}'})}\n\n"

        # Final log if stream ended without [DONE]
        if assistant_tokens:
            _append_chat_log("assistant", "".join(assistant_tokens))

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def _append_chat_log(role: str, content: str) -> None:
    """Append a message to the chat log JSONL for drift monitoring.
    
    The file at logs/chat_log.jsonl stores the last N interactions
    for the Persona Drift Monitor to analyze.
    """
    import json as _json
    from datetime import datetime as _dt, timezone as _tz
    from pathlib import Path as _P
    from shogun.config import settings as _settings

    log_path = _P(_settings.log_path) / "chat_log.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = _json.dumps({
        "role": role,
        "content": content[:2000],  # cap to prevent huge entries
        "timestamp": _dt.now(_tz.utc).isoformat(),
    })
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(entry + "\n")
    except Exception:
        pass  # non-critical — don't break chat

