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

async def send_telegram_message(bot_token: str, chat_id: str, text: str):
    """Push a textual response back to the Telegram client."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            if not resp.is_success:
                logger.error(f"Failed to send Telegram message: {resp.text}")
    except Exception as e:
        logger.error(f"Network error sending to Telegram: {e}")

async def process_telegram_message(bot_token: str, chat_id: str, user_msg: str):
    """Pipe an incoming message into the Shogun AI engine, capturing its SSE streaming output."""
    logger.info(f"[Telegram] Received: '{user_msg[:50]}...' from {chat_id}")
    
    try:
        # Fire up a scoped AgentService session
        async with async_session_factory() as session:
            svc = AgentService(session)
            
            logger.info(f"[Telegram] Routing to Shogun engine...")
            # Invoke the core engine internal router
            response_stream = await _shogun_chat_internal(user_msg=user_msg, history=[], svc=svc)
            
            # Aggregate the SSE chunks into a single response
            full_reply = ""
            try:
                # We must iterate the stream. Depending on FastAPI return type, we either iterate an AsyncGenerator or StreamingResponse.body_iterator
                generator = getattr(response_stream, "body_iterator", response_stream)
                
                async for chunk in generator:
                    if type(chunk) == bytes:
                        chunk_str = chunk.decode("utf-8")
                    else:
                        chunk_str = str(chunk)
                        
                    lines = chunk_str.strip().split("\n")
                    for line in lines:
                        if line.startswith("data: "):
                            payload = line[6:].strip()
                            if payload == "[DONE]":
                                break
                            try:
                                data = json.loads(payload)
                                if data.get("type") == "token":
                                    full_reply += data.get("content", "")
                                elif data.get("type") == "error":
                                    logger.error(f"[Telegram] AI Engine Error: {data.get('content')}")
                                    full_reply += f"⚠️ {data.get('content')}"
                            except json.JSONDecodeError:
                                pass
                
                logger.info(f"[Telegram] AI response generated ({len(full_reply)} chars)")
            except Exception as e:
                logger.error(f"[Telegram] Error reading SSE response stream: {e}\n{traceback.format_exc()}")
                full_reply = "⚠️ Sorry, I encountered an internal error while processing your request."
                
            if not full_reply.strip():
                logger.warning("[Telegram] AI Engine returned empty response.")
                full_reply = "I apologize, but I couldn't generate a response to that message."
                
            # Send the joined string response back to Telegram
            await send_telegram_message(bot_token, chat_id, full_reply)
            logger.info(f"[Telegram] Response sent to {chat_id}")

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
