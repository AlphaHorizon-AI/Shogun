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
    logger.info(f"[Telegram] Processing message from {chat_id}: {user_msg[:30]}...")
    
    # Fire up a scoped AgentService session
    async with async_session_factory() as session:
        svc = AgentService(session)
        
        # Invoke the core engine internal router
        response_stream = await _shogun_chat_internal(user_msg=user_msg, history=[], svc=svc)
        
        # Aggregate the SSE chunks into a single response
        full_reply = ""
        try:
            # We must iterate the stream.  Depending on FastAPI return type, we either iterate an AsyncGenerator or StreamingResponse.body_iterator
            generator = getattr(response_stream, "body_iterator", response_stream)
            
            async for chunk in generator:
                # `chunk` is a string like: `data: {"type": "content", "content": "..."}\n\n`
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
                            if data.get("type") == "content":
                                full_reply += data.get("content", "")
                            elif data.get("type") == "error":
                                full_reply += f"⚠️ {data.get('content')}"
                        except json.JSONDecodeError:
                            pass
        except Exception as e:
            logger.error(f"Error reading SSE response stream: {e}")
            full_reply = "⚠️ Sorry, I encountered an internal error while processing your request."
            
        if not full_reply.strip():
            full_reply = "..."
            
        # Send the joined string response back to Telegram
        await send_telegram_message(bot_token, chat_id, full_reply)

async def telegram_poller_task():
    """Continuous background loop for polling Long-Polling getUpdates API."""
    logger.info("[Telegram] Background listener task starting...")
    offset = 0

    while True:
        try:
            # 1. Check if telegram is connected and what the config is
            bushido = await _get_agent_bushido()
            cfg = bushido.get(_TELEGRAM_KEY, {})
            
            bot_token = cfg.get("bot_token")
            is_connected = cfg.get("connected", False)
            allowed_ids = cfg.get("allowed_chat_ids", [])
            
            if not bot_token or not is_connected:
                # If disconnected, just sleep for a while and check again later
                await asyncio.sleep(10)
                continue
                
            # 2. Hit the Telegram Long-Polling endpoint. This will block for up to 30 seconds server-side if no messages.
            url = f"https://api.telegram.org/bot{bot_token}/getUpdates?timeout=30&offset={offset}"
            
            async with httpx.AsyncClient(timeout=40) as client:
                try:
                    resp = await client.get(url)
                except httpx.ReadTimeout:
                    # Expected if 30s passes with no traffic
                    continue
                except Exception as e:
                    logger.warning(f"[Telegram] Polling network exception: {e}")
                    await asyncio.sleep(5)
                    continue

            if not resp.is_success:
                logger.warning(f"[Telegram] Polling failed: HTTP {resp.status_code}")
                await asyncio.sleep(10)
                continue
                
            data = resp.json()
            results = data.get("result", [])
            
            for update in results:
                update_id = update.get("update_id")
                # Advance the offset so Telegram removes it from the queue
                if update_id and update_id >= offset:
                    offset = update_id + 1
                    
                msg = update.get("message")
                if not msg:
                    continue
                    
                chat = msg.get("chat", {})
                chat_id_str = str(chat.get("id"))
                text = msg.get("text", "").strip()
                
                # Check whitelist
                if allowed_ids and chat_id_str not in allowed_ids:
                    logger.warning(f"[Telegram] Blocked unauthorized message from {chat_id_str}")
                    continue
                    
                if text:
                    # Offload the processing task so we don't block the polling loop
                    asyncio.create_task(process_telegram_message(bot_token, chat_id_str, text))

        except asyncio.CancelledError:
            logger.info("[Telegram] Listener task cancelled.")
            break
        except Exception as e:
            logger.error(f"[Telegram] Unexpected exception in poller: {e}\n{traceback.format_exc()}")
            await asyncio.sleep(5)
            
    logger.info("[Telegram] Background listener loop exited.")
