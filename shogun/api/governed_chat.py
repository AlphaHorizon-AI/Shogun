"""Governed Chat Lane — context-aware chat with memory retrieval, no tools.

This module is imported into shogun.api.agents and provides the governed
chat execution lane. It sits between Fast Chat (no context) and Mission
Mode (full orchestration with tools).
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from datetime import datetime

import httpx
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from shogun.services.provider_credentials import provider_api_key
from shogun.services.model_reasoning import apply_chat_reasoning
from shogun.services.model_transport import model_chat_stream
from shogun.services.provider_oauth import ensure_provider_access_token

logger = logging.getLogger(__name__)


async def _shogun_governed_chat(
    user_msg: str,
    history: list,
    svc,
    *,
    classification: dict | None = None,
):
    """Governed Chat execution lane — memory-enriched conversation, no side effects.

    Capability profile:
    - YES: Memory retrieval (Qdrant semantic search)
    - YES: Pinned memory injection
    - YES: Kaizen constitution context
    - YES: Auto-store episodic memory after exchange
    - NO:  Tool execution, filesystem, shell, network
    - NO:  Mission planner, subagent orchestration
    - NO:  External side effects (email, browser, etc.)
    """
    from shogun.db.models.agent import Agent
    from shogun.db.models.model_provider import ModelProvider
    from shogun.db.models.operator import Operator
    from shogun.api.deps import get_db
    from shogun.services.posture_guard import check_kill_switch
    from shogun.services.event_logger import EventLogger
    import uuid as _uuid

    EL = EventLogger
    _t_start = time.monotonic()
    _trace_id = f"trc_{uuid.uuid4().hex[:16]}"
    classification = classification or {"mode": "governed", "reason": "manual_selection", "matched": []}

    # ── 0. Kill switch gate ──
    try:
        await check_kill_switch()
    except HTTPException:
        async def _blocked():
            yield f"data: {json.dumps({'type': 'error', 'content': 'HARAKIRI is active — all AI operations are suspended.'})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(_blocked(), media_type="text/event-stream")

    # ── 1. Load primary Shogun agent ──
    filters = [Agent.agent_type == "shogun", Agent.is_primary == True, Agent.is_deleted == False]
    records, _ = await svc.get_all(filters=filters)
    if not records:
        raise HTTPException(status_code=404, detail="Primary Shogun agent not found")
    agent = records[0]
    _agent_id_str = str(agent.id)

    try:
        from shogun.services.self_learning import capture_operator_correction

        await capture_operator_correction(
            agent_id=agent.id,
            user_message=user_msg,
            history=history,
            source_type="governed_chat",
        )
    except Exception as exc:
        logger.warning("Governed Chat: operator correction capture failed: %s", exc)

    # ── 2. Resolve model ──
    bushido = agent.bushido_settings or {}
    _exploration_variance = bushido.get("exploration_variance", 24)
    _temperature = round(0.3 + (_exploration_variance / 100) * 0.9, 2)

    saved_primary: str = bushido.get("primary_model", "")
    saved_provider_id: str = saved_primary.split("::")[0] if "::" in saved_primary else ""
    saved_model_name: str = saved_primary.split("::")[1] if "::" in saved_primary else ""

    provider = None
    async for db in get_db():
        if saved_provider_id:
            try:
                res = await db.execute(
                    select(ModelProvider).where(ModelProvider.id == _uuid.UUID(saved_provider_id))
                )
                provider = res.scalar_one_or_none()
            except Exception:
                provider = None

        if not provider and saved_model_name:
            res = await db.execute(
                select(ModelProvider).where(ModelProvider.status == "connected")
            )
            for p in res.scalars().all():
                p_models = p.config.get("models") or []
                if saved_model_name in p_models or saved_model_name == p.name:
                    provider = p
                    break

        if not provider:
            res = await db.execute(
                select(ModelProvider)
                .where(ModelProvider.status == "connected")
                .order_by(ModelProvider.created_at)
                .limit(1)
            )
            provider = res.scalar_one_or_none()
        if provider and provider.auth_type == "oauth":
            await ensure_provider_access_token(db, provider)
            await db.commit()
        break

    if not provider:
        async def _no_provider():
            yield f"data: {json.dumps({'type': 'error', 'content': 'No active model provider found. Go to The Katana and add one.'})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(_no_provider(), media_type="text/event-stream")

    # ── Endpoint resolve ──
    PROVIDER_URLS: dict[str, str] = {
        "ollama":     "http://127.0.0.1:11434",
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

    from shogun.api.agents import _resolve_provider_model_id

    model_name = _resolve_provider_model_id(
        provider,
        saved_model_name=saved_model_name,
        saved_provider_id=saved_provider_id,
    )
    provider_name = provider.name

    if not model_name:
        async def _no_model():
            yield f"data: {json.dumps({'type': 'error', 'content': 'The selected model provider has no valid model ID configured. Update it in The Katana.'})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(_no_model(), media_type="text/event-stream")

    api_key = provider_api_key(provider.config)
    req_headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        req_headers["Authorization"] = f"Bearer {api_key}"
    if provider.provider_type == "openrouter":
        req_headers["HTTP-Referer"] = "https://shogun.ai"
        req_headers["X-Title"] = "Shogun"
    if provider.provider_type == "google" and provider.config.get("oauth_project_id"):
        req_headers["x-goog-user-project"] = str(provider.config["oauth_project_id"])

    # ── 3. Load cached operator name ──
    operator_name = "Daimyo"
    async for db in get_db():
        op_res = await db.execute(select(Operator).where(Operator.username == "admin"))
        op = op_res.scalar_one_or_none()
        if op and op.display_name:
            operator_name = op.display_name
        break
    speaker_role = "Primary Admin"
    if classification.get("_speaker_name"):
        operator_name = str(classification["_speaker_name"])
        speaker_role = str(classification.get("_speaker_role") or "Team Member")

    # ── 4. Get posture tier ──
    try:
        from shogun.services.posture_guard import get_posture_tool_filter
        _posture = await get_posture_tool_filter()
        _active_tier = _posture.get("active_tier", "tactical").upper()
    except Exception:
        _active_tier = "TACTICAL"

    # ── 5. Retrieve memories (semantic search + pinned) ──
    memory_context_block = ""
    kiroku_context_block = ""
    memory_count = 0
    recalled_memory_ids: list[uuid.UUID] = []
    try:
        from shogun.services.memory_service import MemoryService
        from shogun.services.cascade_retrieval import CascadeRetrievalService
        from shogun.services.memory_scope import resolve_active_memory_scope
        from shogun.config import settings
        from shogun.db.engine import async_session_factory

        async with async_session_factory() as mem_db:
            mem_svc = MemoryService(mem_db)

            # Semantic search: find top-5 relevant memories
            active_scope = resolve_active_memory_scope()
            search_results, _retrieval_diagnostic = await CascadeRetrievalService(mem_db).run(
                query=user_msg,
                agent_id=agent.id,
                scope=active_scope,
                limit=5,
            )
            if (
                _retrieval_diagnostic
                and settings.memory_graph_retrieval_mode == "active"
                and _retrieval_diagnostic.plan_json.get("context_pack_id")
            ):
                from shogun.services.memory_context_pack_service import MemoryContextPackService

                pack = await MemoryContextPackService(mem_db).get(
                    uuid.UUID(_retrieval_diagnostic.plan_json["context_pack_id"])
                )
                if pack:
                    kiroku_context_block = MemoryContextPackService.render_prompt_block(pack)

            # Pinned memories (always included)
            pinned = await mem_svc.get_pinned(
                agent_id=agent.id,
                scope=active_scope,
            )

            # Combine and deduplicate
            seen_ids = set()
            memory_entries = []

            for mem in (pinned or []):
                if hasattr(mem, "id") and mem.id not in seen_ids:
                    seen_ids.add(mem.id)
                    recalled_memory_ids.append(mem.id)
                    memory_entries.append(f"[PINNED] {mem.content}")

            for mem in (search_results or []):
                if isinstance(mem, dict):
                    memory_id = uuid.UUID(str(mem["memory_id"]))
                    if memory_id not in seen_ids:
                        seen_ids.add(memory_id)
                        recalled_memory_ids.append(memory_id)
                        score = (mem.get("scores") or {}).get("final")
                        score_str = f" (salience: {score:.2f})" if score is not None else ""
                        memory_entries.append(
                            f"[RECALLED{score_str}] {mem.get('title', '')}\n{mem.get('content', '')}"
                        )

            memory_count = len(memory_entries)
            for memory_id in recalled_memory_ids:
                await mem_svc.record_access(memory_id)
            if recalled_memory_ids:
                await mem_db.commit()
            if memory_entries:
                if kiroku_context_block:
                    pinned_entries = [entry for entry in memory_entries if entry.startswith("[PINNED]")]
                    memory_context_block = "\n\n" + "\n".join([*pinned_entries, kiroku_context_block])
                else:
                    memory_context_block = "\n\n[MEMORY CONTEXT — recalled from Archives]\n" + "\n".join(memory_entries)

    except Exception as exc:
        logger.warning("Governed Chat: memory retrieval failed: %s", exc)
        memory_context_block = "\n\n[MEMORY CONTEXT — retrieval failed, proceeding without memory]"

    # ── 6. Load Kaizen constitution (if available) ──
    kaizen_block = ""
    try:
        from shogun.api.kaizen import build_governance_prompt_block
        governance = build_governance_prompt_block()
        if governance:
            kaizen_block = f"\n\n[GOVERNANCE — Kaizen Constitution]\n{governance}"
    except Exception:
        pass

    # ── 7. Build system prompt with memory and governance ──
    persona_name = agent.name or "Shogun"
    system_prompt = f"""You are {persona_name}, the primary AI of the Shogun platform.
The verified current speaker is '{operator_name}' ({speaker_role}).
Current mode: Governed Chat (context-aware).
Current posture: {_active_tier}.
Current model: {model_name}.

Governed Chat has access to your long-term memory (Archives) and the Kaizen constitution.
You do NOT have access to tools, files, shell, network, agents, or external systems in this mode.
You cannot perform actions, browse the web, send emails, or make persistent changes.
You CAN reference and discuss recalled memories, answer questions about past interactions,
and provide context-aware responses based on what you remember.

If the user's request requires actions (browsing, email, file operations, agent spawning),
explain that it requires Mission Mode and they can switch using the mode selector.

Be conversational, direct, and helpful. Use markdown when it improves readability.
When referencing recalled memories, acknowledge them naturally.
Explicit operator corrections are durable learning signals. Acknowledge them and apply them in future answers.
{memory_context_block}{kaizen_block}"""

    # ── 8. Build messages ──
    messages = [{"role": "system", "content": system_prompt}]
    for h in history[-10:]:
        if h.get("role") in ("user", "assistant") and h.get("content"):
            messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": user_msg})

    timestamp = datetime.now().isoformat()

    # ── 9. Stream response ──
    async def generate():
        _t_first_token = None
        _failed = False

        # Meta event
        yield f"data: {json.dumps({'type': 'meta', 'model': model_name, 'provider': provider_name, 'timestamp': timestamp, 'mode': 'governed', 'memories_recalled': memory_count})}\n\n"

        if memory_count > 0:
            yield f"data: {json.dumps({'type': 'status', 'content': f'Retrieved {memory_count} memories from Archives...'})}\n\n"
        yield f"data: {json.dumps({'type': 'status', 'content': 'Calling model with context...'})}\n\n"

        req_json = {
            "model": model_name,
            "messages": messages,
            "stream": True,
            "temperature": _temperature,
        }
        apply_chat_reasoning(
            req_json,
            provider_type=provider.provider_type,
            model_id=model_name,
            provider_config=provider.config,
        )

        assistant_tokens: list[str] = []

        try:
            async with model_chat_stream(
                auth_type=provider.auth_type,
                base_url=base_url,
                headers=req_headers,
                payload=req_json,
                timeout=120.0,
            ) as resp:
                    if resp.status_code != 200:
                        _failed = True
                        body_text = await resp.aread()
                        yield f"data: {json.dumps({'type': 'error', 'content': f'Model error {resp.status_code}: {body_text.decode()[:300]}'})}\n\n"
                        yield "data: [DONE]\n\n"
                        return

                    async for raw_line in resp.aiter_lines():
                        if not raw_line.startswith("data: "):
                            continue
                        payload = raw_line[6:].strip()
                        if payload == "[DONE]":
                            break
                        try:
                            chunk = json.loads(payload)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                if _t_first_token is None:
                                    _t_first_token = time.monotonic()
                                assistant_tokens.append(content)
                                yield f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"
                        except Exception:
                            continue
        except httpx.ConnectError:
            _failed = True
            yield f"data: {json.dumps({'type': 'error', 'content': f'Cannot connect to {provider.provider_type} at {base_url}. Is the server running?'})}\n\n"
        except Exception:
            _failed = True
            logger.exception("Governed chat streaming failed")
            yield f"data: {json.dumps({'type': 'error', 'content': 'Streaming failed. Check the Shogun logs.'})}\n\n"

        # ── Post-stream: store episodic memory ──
        _t_end = time.monotonic()
        full_response = "".join(assistant_tokens)

        if full_response and not _failed:
            try:
                from shogun.services.memory_service import MemoryService
                from shogun.db.engine import async_session_factory

                async with async_session_factory() as mem_db:
                    mem_svc = MemoryService(mem_db)
                    for memory_id in recalled_memory_ids:
                        await mem_svc.reinforce(memory_id, "retrieved_and_used")
                    await mem_svc.create_memory(
                        agent_id=agent.id,
                        title=f"Governed chat with {operator_name}: {user_msg[:90]}",
                        content=(
                            f"[Governed Chat Exchange]\nSpeaker: {operator_name} ({speaker_role})\n"
                            f"{user_msg}\nShogun: {full_response[:1000]}"
                        ),
                        memory_type="episodic",
                        source_type="governed_chat",
                        decay_class="medium",
                        tags=[
                            "governed-chat",
                            *(
                                [f"member:{classification['_speaker_member_id']}"]
                                if classification.get("_speaker_member_id")
                                else []
                            ),
                        ],
                    )
                    await mem_db.commit()
            except Exception as exc:
                logger.warning("Governed Chat: failed to store episodic memory: %s", exc)

        # ── Audit completion ──
        try:
            _latency_ms = round((_t_end - _t_start) * 1000)
            _ttft_ms = round((_t_first_token - _t_start) * 1000) if _t_first_token else None

            _event_type = "chat.governed.failed" if _failed else "chat.governed.completed"
            _summary = f"Governed Chat {'failed' if _failed else 'completed'} ({model_name}) — {_latency_ms}ms, {memory_count} memories"

            await EL.emit_model_event(
                _event_type, _summary,
                model_used=model_name, provider_used=provider_name,
                trace_id=_trace_id, agent_id=_agent_id_str, user_id=operator_name,
                detail={
                    "mode": "governed",
                    "latency_ms": _latency_ms,
                    "time_to_first_token_ms": _ttft_ms,
                    "memories_recalled": memory_count,
                    "posture_tier": _active_tier,
                },
            )
        except Exception:
            pass

        logger.info(
            "[Shogun] Governed Chat %s: model=%s latency=%dms memories=%d",
            "FAILED" if _failed else "completed",
            model_name,
            round((_t_end - _t_start) * 1000),
            memory_count,
        )

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
