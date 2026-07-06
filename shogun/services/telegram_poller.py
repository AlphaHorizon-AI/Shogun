"""Background Telegram Listener — Polls Telegram API and routes to Shogun AI engine."""

import asyncio
import json
import logging
import time
import traceback
from datetime import datetime, timezone

import httpx

from shogun.api.agents import _classify_chat_mode, _shogun_chat_internal
from shogun.db.engine import async_session_factory
from shogun.db.models.agent import Agent
from shogun.services.agent_service import AgentService
from shogun.services.channel_service import _TELEGRAM_KEY, _get_agent_bushido

logger = logging.getLogger("shogun.telegram_poller")

# ── Persistent httpx client (connection pooling, avoids TLS handshake per call) ──
_tg_client: httpx.AsyncClient | None = None


def _get_tg_client() -> httpx.AsyncClient:
    """Return (and lazily create) a long-lived httpx client for Telegram API calls."""
    global _tg_client
    if _tg_client is None or _tg_client.is_closed:
        _tg_client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5, read=40, write=10, pool=5),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=5),
            http2=False,
        )
    return _tg_client


# ── Telegram config cache (avoid DB hit every poll cycle) ──────────────────
_tg_config_cache: dict = {"data": None, "ts": 0.0}
_TG_CONFIG_TTL = 60  # seconds


def _select_telegram_chat_mode(user_msg: str, history: list) -> tuple[str, str, dict]:
    """Choose a lane for Telegram, which has no graphical mode selector.

    Telegram defaults to Mission so requests can use the tools permitted by
    the active Torii posture. Operators can opt into a narrower lane per
    message.
    """
    text = user_msg.strip()
    lowered = text.lower()
    overrides = {
        "/fast": "fast",
        "/governed": "governed",
        "/mission": "mission",
        "/auto": "auto",
    }
    for command, requested_mode in overrides.items():
        if lowered == command or lowered.startswith(command + " "):
            clean_message = text[len(command):].lstrip() or "Hello"
            classification = _classify_chat_mode(clean_message, history)
            mode = classification["mode"] if requested_mode == "auto" else requested_mode
            classification = {
                **classification,
                "mode": mode,
                "reason": f"telegram_{requested_mode}_override",
            }
            return clean_message, mode, classification

    classification = _classify_chat_mode(text, history)
    return text, "mission", {
        **classification,
        "mode": "mission",
        "reason": "telegram_mission_default",
    }


async def _get_cached_telegram_config() -> tuple[dict, dict]:
    """Return (bushido_settings, telegram_config) with 60s caching.

    Returns ({}, {}) when no config is available.
    """
    now = time.monotonic()
    if now - _tg_config_cache["ts"] < _TG_CONFIG_TTL and _tg_config_cache["data"] is not None:
        bushido = _tg_config_cache["data"]
        return bushido, bushido.get(_TELEGRAM_KEY, {})

    bushido = await _get_agent_bushido()
    _tg_config_cache["data"] = bushido or {}
    _tg_config_cache["ts"] = now
    cfg = (bushido or {}).get(_TELEGRAM_KEY, {})
    return bushido or {}, cfg


def invalidate_telegram_config_cache():
    """Force a config refresh on the next poll cycle (e.g. after connect/disconnect)."""
    _tg_config_cache["ts"] = 0.0


# ── Telegram API helpers (use persistent client) ──────────────────────────


async def send_chat_action(bot_token: str, chat_id: str, action: str = "typing"):
    """Send a chat action indicator (e.g. 'typing...') — instant user feedback."""
    url = f"https://api.telegram.org/bot{bot_token}/sendChatAction"
    try:
        client = _get_tg_client()
        await client.post(url, json={"chat_id": chat_id, "action": action})
    except Exception:
        pass  # Non-critical — best effort


async def send_telegram_message(bot_token: str, chat_id: str, text: str) -> int | None:
    """Push a textual response back to the Telegram client. Returns message_id if successful."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        client = _get_tg_client()
        resp = await client.post(url, json=payload)
        if resp.is_success:
            return resp.json().get("result", {}).get("message_id")
        logger.error(f"Failed to send Telegram message: {resp.text}")
    except Exception as e:
        logger.error(f"Network error sending to Telegram: {e}")
    return None


async def edit_telegram_message(
    bot_token: str,
    chat_id: str,
    message_id: int,
    text: str,
    *,
    use_markdown: bool = True,
):
    """Update an existing Telegram message with new content.

    Set ``use_markdown=False`` for intermediate streaming edits where the
    markdown may be incomplete (unclosed ``*``, ``_``, etc.), which would
    cause Telegram to reject the edit.
    """
    url = f"https://api.telegram.org/bot{bot_token}/editMessageText"
    payload: dict = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
    }
    if use_markdown:
        payload["parse_mode"] = "Markdown"
    try:
        client = _get_tg_client()
        resp = await client.post(url, json=payload)
        if not resp.is_success:
            # Often occurs if content is identical, skip error logging for that
            if "message is not modified" not in resp.text:
                logger.debug(f"Note: Failed to edit Telegram message: {resp.text}")
    except Exception as e:
        logger.error(f"Network error editing Telegram message: {e}")


async def process_telegram_message(bot_token: str, chat_id: str, user_msg: str):
    """Pipe an incoming message into the Shogun AI engine, capturing its SSE streaming output."""
    logger.info(f"[Telegram] Received: '{user_msg[:50]}...' from {chat_id}")

    # ── 0. Immediate typing indicator — user sees feedback in <100ms ──
    await send_chat_action(bot_token, chat_id, "typing")

    # Emergency controls must be handled before the kill-switch gate so the
    # same authorized Telegram user can also reset an active Harakiri.
    from shogun.services.harakiri_control import (
        execute_harakiri_control,
        parse_harakiri_control,
    )
    harakiri_action = parse_harakiri_control(user_msg)
    if harakiri_action:
        await execute_harakiri_control(
            harakiri_action,
            source="telegram",
            actor=chat_id,
        )
        if harakiri_action == "activate":
            await send_telegram_message(
                bot_token,
                chat_id,
                "⛩️ *HARAKIRI ACTIVATED*\n\nAll agent activity is suspended. Posture is now SHRINE.",
            )
        else:
            await send_telegram_message(
                bot_token,
                chat_id,
                "✅ *HARAKIRI RESET*\n\nThe kill switch is inactive. Posture is now TACTICAL.",
            )
        return
    
    # ── Posture enforcement: kill switch gate ──────────────────
    try:
        from shogun.api.security import _get_agent_posture
        posture = await _get_agent_posture()
        if posture.get("kill_switch_active", False):
            logger.warning("[Telegram] Kill switch active — blocking message from %s", chat_id)
            await send_telegram_message(bot_token, chat_id,
                "⛩️ Shogun is in emergency lockdown mode (HARAKIRI). "
                "All AI operations are suspended. Deactivate the kill switch "
                "in the Torii to resume.")
            return
    except Exception as e:
        logger.debug("[Telegram] Posture check failed: %s", e)

    try:
        # Fire up a scoped AgentService session
        async with async_session_factory() as session:
            svc = AgentService(session)
            from shogun.services.chat_sync_service import (
                append_chat_message,
                get_chat_context,
            )
            history = await get_chat_context(session, limit=20)
            await append_chat_message(
                session,
                channel="telegram",
                role="user",
                content=user_msg,
                external_chat_id=chat_id,
            )
            await session.commit()
            
            # ── 1. Select the Telegram execution lane ──────────────
            # Telegram has no graphical mode selector, so default to the
            # tool-capable Mission lane. Torii still gates every tool call.
            user_msg, mode, classification = _select_telegram_chat_mode(user_msg, history)
            logger.info(
                "[Telegram] Mode classified: %s (reason=%s, matched=%s)",
                mode,
                classification.get("reason", ""),
                classification.get("matched", [])[:3],
            )

            # 2. Send initial thinking message
            msg_id = await send_telegram_message(bot_token, chat_id, "_Shogun is thinking..._")
            
            # 3. Invoke the appropriate engine lane
            if mode == "fast":
                from shogun.api.agents import _shogun_fast_chat
                logger.info("[Telegram] Routing to Fast Chat lane...")
                response_stream = await _shogun_fast_chat(
                    user_msg=user_msg, history=history, svc=svc,
                    classification=classification,
                )
            elif mode == "governed":
                from shogun.api.governed_chat import _shogun_governed_chat
                logger.info("[Telegram] Routing to Governed Chat lane...")
                response_stream = await _shogun_governed_chat(
                    user_msg=user_msg, history=history, svc=svc,
                    classification=classification,
                )
            else:
                logger.info("[Telegram] Routing to Mission lane...")
                response_stream = await _shogun_chat_internal(
                    user_msg=user_msg, history=history, svc=svc,
                    classification=classification,
                )
            
            # 4. Aggregate the SSE chunks and update Telegram periodically
            full_reply = ""
            current_action = ""
            last_update_text = ""
            last_update_time = datetime.now(timezone.utc)
            buffer = ""
            
            try:
                generator = getattr(response_stream, "body_iterator", response_stream)
                
                async for chunk in generator:
                    chunk_str = chunk.decode("utf-8") if isinstance(chunk, bytes) else str(chunk)
                    buffer += chunk_str
                    
                    while "\n\n" in buffer:
                        event_block, buffer = buffer.split("\n\n", 1)
                        for line in event_block.split("\n"):
                            if line.startswith("data: "):
                                payload = line[6:].strip()
                                if payload == "[DONE]":
                                    break
                                try:
                                    data = json.loads(payload)
                                    if data.get("type") == "token":
                                        full_reply += data.get("content", "")
                                        current_action = "" # Clear action when text resumes
                                    elif data.get("type") == "action":
                                        current_action = data.get("content", "")
                                    elif data.get("type") == "error":
                                        logger.error(f"[Telegram] AI Engine Error: {data.get('content')}")
                                        full_reply += f"\n⚠️ {data.get('content')}"
                                        current_action = ""
                                except json.JSONDecodeError:
                                    pass
                    
                    # Throttled update every 1.5 seconds (Telegram rate limit is ~1 msg/sec per chat)
                    now = datetime.now(timezone.utc)
                    if (now - last_update_time).total_seconds() > 1.5 or current_action:
                        display_text = full_reply.strip()
                        if current_action:
                            if display_text:
                                display_text += f"\n\n⚙️ _{current_action}_"
                            else:
                                display_text = f"⚙️ _{current_action}_"
                                
                        if display_text and display_text != last_update_text:
                            # use_markdown=False for intermediate edits to avoid
                            # Telegram rejecting partial/unclosed markdown syntax
                            await edit_telegram_message(
                                bot_token, chat_id, msg_id,
                                display_text + (" ▮" if not current_action else ""),
                                use_markdown=False,
                            )
                            last_update_text = display_text
                            last_update_time = now
                
                logger.info(f"[Telegram] AI response complete ({len(full_reply)} chars)")
            except Exception as e:
                logger.error(f"[Telegram] Error reading SSE response stream: {e}\n{traceback.format_exc()}")
                full_reply = "⚠️ Sorry, I encountered an internal error while processing your request."
                
            if not full_reply.strip():
                logger.warning("[Telegram] AI Engine returned empty response.")
                full_reply = "I apologize, but I couldn't generate a response to that message."
                
            # 5. Final update to the same message — HERE we enable Markdown for the finished text
            await edit_telegram_message(bot_token, chat_id, msg_id, full_reply, use_markdown=True)
            await append_chat_message(
                session,
                channel="telegram",
                role="assistant",
                content=full_reply,
                external_chat_id=chat_id,
            )
            await session.commit()
            logger.info(f"[Telegram] Response finalized for {chat_id}")

    except Exception as e:
        logger.error(f"[Telegram] Critical failure in process_telegram_message: {e}\n{traceback.format_exc()}")
        await send_telegram_message(bot_token, chat_id, "⚠️ I encountered a critical system error.")

async def telegram_poller_task():
    """Continuous background loop for polling Long-Polling getUpdates API."""
    logger.info("[Telegram] Background listener task starting...")
    offset = 0

    while True:
        try:
            # 1. Check if telegram is connected and what the config is (cached)
            bushido, cfg = await _get_cached_telegram_config()
            if not bushido:
                logger.debug("[Telegram] No bushido settings found, sleeping...")
                await asyncio.sleep(10)
                continue
                
            bot_token = cfg.get("bot_token")
            is_connected = cfg.get("connected", False)
            allowed_ids = cfg.get("allowed_chat_ids", [])
            
            if not bot_token or not is_connected:
                # If disconnected, just sleep for a while and check again later
                await asyncio.sleep(10)
                continue
                
            # 2. Hit the Telegram Long-Polling endpoint (uses persistent client).
            url = f"https://api.telegram.org/bot{bot_token}/getUpdates?timeout=30&offset={offset}"
            
            client = _get_tg_client()
            try:
                resp = await client.get(url)
            except httpx.ReadTimeout:
                continue
            except Exception as e:
                logger.warning(f"[Telegram] Polling network exception: {e}")
                await asyncio.sleep(5)
                continue

            if not resp.is_success:
                if resp.status_code == 401:
                    # Invalid or revoked bot token — auto-disconnect to stop polling
                    logger.warning("[Telegram] Bot token is invalid (HTTP 401). Auto-disconnecting to stop polling. Reconfigure in the Katana to reconnect.")
                    try:
                        async with async_session_factory() as session:
                            from sqlalchemy import select
                            agent = (await session.execute(
                                select(Agent).where(Agent.agent_type == "shogun", Agent.is_primary == True, Agent.is_deleted == False)
                            )).scalar_one_or_none()
                            if agent and agent.bushido_settings:
                                tg_cfg = agent.bushido_settings.get(_TELEGRAM_KEY, {})
                                tg_cfg["connected"] = False
                                agent.bushido_settings = {**agent.bushido_settings, _TELEGRAM_KEY: tg_cfg}
                                await session.commit()
                                logger.info("[Telegram] Auto-disconnected due to invalid token.")
                    except Exception as disc_err:
                        logger.debug(f"[Telegram] Failed to auto-disconnect: {disc_err}")
                    invalidate_telegram_config_cache()
                    await asyncio.sleep(60)  # Long sleep after auto-disconnect
                else:
                    logger.warning(f"[Telegram] Polling failed: HTTP {resp.status_code} - {resp.text[:200]}")
                    await asyncio.sleep(10)
                continue
                
            data = resp.json()
            results = data.get("result", [])
            
            if results:
                logger.debug(f"[Telegram] Received {len(results)} updates")

            for update in results:
                update_id = update.get("update_id")
                if update_id and update_id >= offset:
                    offset = update_id + 1
                    
                msg = update.get("message")
                if not msg:
                    continue
                    
                chat = msg.get("chat", {})
                chat_id_str = str(chat.get("id"))
                text = msg.get("text", "").strip()
                
                # Check whitelist (allowing ID capture if empty)
                if allowed_ids and chat_id_str not in allowed_ids:
                    logger.warning(f"[Telegram] Blocked unauthorized message from {chat_id_str}")
                    # Optionally notify unauthorized users? Usually better to stay silent.
                    continue

                # Remote emergency controls require an explicit Telegram
                # allowlist; an empty list is acceptable for chat discovery,
                # but never for kill-switch activation or reset.
                from shogun.services.harakiri_control import parse_harakiri_control
                if parse_harakiri_control(text) and not allowed_ids:
                    logger.warning(
                        "[Telegram] Blocked Harakiri control from %s because no chat allowlist is configured",
                        chat_id_str,
                    )
                    await send_telegram_message(
                        bot_token,
                        chat_id_str,
                        "⚠️ Harakiri control is disabled until this chat ID is added to Telegram's allowed chat IDs.",
                    )
                    continue
                    
                if text:
                    asyncio.create_task(process_telegram_message(bot_token, chat_id_str, text))

        except asyncio.CancelledError:
            logger.info("[Telegram] Listener task cancelled.")
            break
        except Exception as e:
            logger.error(f"[Telegram] Unexpected exception in poller: {e}\n{traceback.format_exc()}")
            await asyncio.sleep(5)
            
    # Clean up the persistent client on exit
    if _tg_client and not _tg_client.is_closed:
        await _tg_client.aclose()

    logger.info("[Telegram] Background listener loop exited.")
