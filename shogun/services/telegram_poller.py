"""Background Telegram Listener — Polls Telegram API and routes to Shogun AI engine."""

import asyncio
import json
import logging
import traceback
import httpx
from datetime import datetime, timezone

from shogun.db.engine import async_session_factory
from shogun.db.models.agent import Agent
from shogun.services.agent_service import AgentService
from shogun.api.agents import _shogun_chat_internal
from shogun.services.channel_service import _TELEGRAM_KEY, _get_agent_bushido

logger = logging.getLogger("shogun.telegram_poller")

async def send_telegram_message(bot_token: str, chat_id: str, text: str) -> int | None:
    """Push a textual response back to the Telegram client. Returns message_id if successful."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            if resp.is_success:
                return resp.json().get("result", {}).get("message_id")
            logger.error(f"Failed to send Telegram message: {resp.text}")
    except Exception as e:
        logger.error(f"Network error sending to Telegram: {e}")
    return None

async def edit_telegram_message(bot_token: str, chat_id: str, message_id: int, text: str):
    """Update an existing Telegram message with new content."""
    url = f"https://api.telegram.org/bot{bot_token}/editMessageText"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
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
    
    try:
        # Fire up a scoped AgentService session
        async with async_session_factory() as session:
            svc = AgentService(session)
            
            # 1. Send initial thinking message
            msg_id = await send_telegram_message(bot_token, chat_id, "_Shogun is thinking..._")
            
            # Invoke the core engine internal router
            logger.info(f"[Telegram] Routing to Shogun engine...")
            response_stream = await _shogun_chat_internal(user_msg=user_msg, history=[], svc=svc)
            
            # 2. Aggregate the SSE chunks and update Telegram periodically
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
                    
                    # High-frequency update every 0.8 seconds for smooth UI
                    now = datetime.now(timezone.utc)
                    if (now - last_update_time).total_seconds() > 0.8 or current_action:
                        display_text = full_reply.strip()
                        if current_action:
                            if display_text:
                                display_text += f"\n\n⚙️ _{current_action}_"
                            else:
                                display_text = f"⚙️ _{current_action}_"
                                
                        if display_text and display_text != last_update_text:
                            # Note: We use NO parse_mode for intermediate edits
                            # This prevents Telegram from rejecting messages with unclosed markdown
                            await edit_telegram_message(bot_token, chat_id, msg_id, display_text + (" ▮" if not current_action else ""))
                            last_update_text = display_text
                            last_update_time = now
                
                logger.info(f"[Telegram] AI response complete ({len(full_reply)} chars)")
            except Exception as e:
                logger.error(f"[Telegram] Error reading SSE response stream: {e}\n{traceback.format_exc()}")
                full_reply = "⚠️ Sorry, I encountered an internal error while processing your request."
                
            if not full_reply.strip():
                logger.warning("[Telegram] AI Engine returned empty response.")
                full_reply = "I apologize, but I couldn't generate a response to that message."
                
            # 3. Final update to the same message — HERE we enable Markdown for the finished text
            await edit_telegram_message(bot_token, chat_id, msg_id, full_reply)
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
            # 1. Check if telegram is connected and what the config is
            bushido = await _get_agent_bushido()
            if not bushido:
                logger.debug("[Telegram] No bushido settings found, sleeping...")
                await asyncio.sleep(10)
                continue
                
            cfg = bushido.get(_TELEGRAM_KEY, {})
            bot_token = cfg.get("bot_token")
            is_connected = cfg.get("connected", False)
            allowed_ids = cfg.get("allowed_chat_ids", [])
            
            if not bot_token or not is_connected:
                # If disconnected, just sleep for a while and check again later
                await asyncio.sleep(10)
                continue
                
            # 2. Hit the Telegram Long-Polling endpoint.
            url = f"https://api.telegram.org/bot{bot_token}/getUpdates?timeout=30&offset={offset}"
            
            async with httpx.AsyncClient(timeout=40) as client:
                try:
                    resp = await client.get(url)
                except httpx.ReadTimeout:
                    continue
                except Exception as e:
                    logger.warning(f"[Telegram] Polling network exception: {e}")
                    await asyncio.sleep(5)
                    continue

            if not resp.is_success:
                logger.warning(f"[Telegram] Polling failed: HTTP {resp.status_code} - {resp.text}")
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
                    
                if text:
                    asyncio.create_task(process_telegram_message(bot_token, chat_id_str, text))

        except asyncio.CancelledError:
            logger.info("[Telegram] Listener task cancelled.")
            break
        except Exception as e:
            logger.error(f"[Telegram] Unexpected exception in poller: {e}\n{traceback.format_exc()}")
            await asyncio.sleep(5)
            
    logger.info("[Telegram] Background listener loop exited.")
