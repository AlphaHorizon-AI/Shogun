"""Background Telegram Listener — Polls Telegram API and routes to Shogun AI engine."""

import asyncio
import json
import logging
import mimetypes
import re
import time
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx

from shogun.api.agents import _classify_chat_mode, _shogun_chat_internal
from shogun.config import settings
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
_topic_registry_cache: dict | None = None

_TOPIC_TAG_NAMES = {
    "general": "General",
    "strategy": "Alpha Horizon Strategy",
    "shogun": "Shogun AFM",
    "research": "Research",
    "personal": "Personal",
    "education": "Education and Skills",
    "news": "News & current events",
}


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
            clean_message = text[len(command) :].lstrip() or "Hello"
            classification = _classify_chat_mode(clean_message, history)
            mode = classification["mode"] if requested_mode == "auto" else requested_mode
            classification = {
                **classification,
                "mode": mode,
                "reason": f"telegram_{requested_mode}_override",
            }
            return clean_message, mode, classification

    classification = _classify_chat_mode(text, history)
    return (
        text,
        "mission",
        {
            **classification,
            "mode": "mission",
            "reason": "telegram_mission_default",
        },
    )


async def _prepare_telegram_visual_context(session, prompt: str, attachments: list[dict]) -> tuple[str, list[dict]]:
    """Analyze Telegram images with the governed vision router before chat.

    The regular chat model may be text-only. Passing raw image bytes to it
    caused OpenRouter's "No endpoints found that support image input" error.
    """
    import uuid

    from shogun.services.visual_intake import VisualIntakeError, VisualIntakeService

    visual = VisualIntakeService(session)
    safe_attachments: list[dict] = []
    visual_context: list[str] = []
    for attachment in attachments:
        is_image = bool(attachment.get("is_image")) or str(attachment.get("mime_type", "")).startswith("image/")
        if not is_image:
            safe_attachments.append(attachment)
            continue

        artifact_id = attachment.get("artifact_id")
        filename = attachment.get("filename") or "Telegram image"
        if not artifact_id:
            visual_context.append(f"[Visual analysis unavailable for {filename}: image artifact was not created.]")
            continue
        try:
            artifact = await visual.get(uuid.UUID(str(artifact_id)))
            if not artifact:
                raise VisualIntakeError("image artifact was not found")
            analysis = await visual.analyze(
                artifact,
                (
                    "Analyze this Telegram image accurately so another assistant can answer the user's request. "
                    "Describe visible people, objects, text, layout, and other relevant details. "
                    f"User request and chat context: {prompt}"
                ),
                analysis_type="telegram_vision",
                allow_cloud=True,
            )
            visual_context.append(f"[Governed visual analysis for {filename}]\n{analysis.result_text}")
        except Exception as exc:
            logger.warning("[Telegram] Vision analysis unavailable for %s: %s", filename, exc)
            visual_context.append(f"[Visual analysis unavailable for {filename}: {exc}]")

    if visual_context:
        prompt = f"{prompt}\n\n" + "\n\n".join(visual_context)
    return prompt, safe_attachments


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


def _topic_registry_path() -> Path:
    return settings.workspace_path.resolve() / "Telegram" / "topic_registry.json"


def _load_topic_registry() -> dict:
    """Load remembered Telegram forum topic names from disk."""
    global _topic_registry_cache
    if _topic_registry_cache is not None:
        return _topic_registry_cache

    path = _topic_registry_path()
    try:
        _topic_registry_cache = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except Exception as exc:
        logger.warning("[Telegram] Could not load topic registry: %s", exc)
        _topic_registry_cache = {}
    return _topic_registry_cache


def _save_topic_registry(registry: dict) -> None:
    """Persist remembered Telegram forum topic names."""
    try:
        path = _topic_registry_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(registry, indent=2, sort_keys=True), encoding="utf-8")
    except Exception as exc:
        logger.warning("[Telegram] Could not save topic registry: %s", exc)


def _topic_name_hint(msg: dict) -> tuple[str, str] | None:
    """Extract an explicit topic name from Telegram service data or operator tags."""
    created = msg.get("forum_topic_created")
    edited = msg.get("forum_topic_edited")
    if isinstance(created, dict) and created.get("name"):
        return str(created["name"]).strip(), "telegram_topic_created"
    if isinstance(edited, dict) and edited.get("name"):
        return str(edited["name"]).strip(), "telegram_topic_edited"

    text = str(msg.get("text") or msg.get("caption") or "").strip()
    command = re.match(r"^/topic(?:@\w+)?\s+(.+)$", text, re.IGNORECASE)
    if command:
        return command.group(1).strip()[:200], "topic_command"
    tag = re.match(r"^\*(general|strategy|shogun|research|personal|education|news)\b", text, re.IGNORECASE)
    if tag:
        key = tag.group(1).lower()
        return _TOPIC_TAG_NAMES[key], f"tag:{key}"
    return None


def set_telegram_topic_mapping(chat_id: str, thread_id: int, name: str, *, source: str = "manual") -> dict:
    """Persist an operator-confirmed mapping from Telegram thread ID to topic name."""
    clean_name = str(name or "").strip()
    if not clean_name:
        raise ValueError("Topic name cannot be empty.")
    registry = _load_topic_registry()
    chat_key = str(chat_id)
    chat_entry = registry.setdefault(
        chat_key,
        {
            "chat_id": chat_key,
            "chat_title": "",
            "chat_type": "supergroup",
            "topics": {},
        },
    )
    topic = chat_entry.setdefault("topics", {}).setdefault(str(int(thread_id)), {})
    topic.update(
        {
            "message_thread_id": int(thread_id),
            "name": clean_name[:200],
            "name_source": source,
            "status": topic.get("status") or "open",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    _save_topic_registry(registry)
    return topic


def list_telegram_topic_mappings() -> list[dict]:
    """Return every discovered Telegram chat and its durable topic mappings."""
    registry = _load_topic_registry()
    return [
        {
            **chat,
            "chat_id": chat.get("chat_id") or chat_id,
            "topics": sorted(
                (chat.get("topics") or {}).values(),
                key=lambda item: int(item.get("message_thread_id") or 0),
            ),
        }
        for chat_id, chat in registry.items()
    ]


def _update_topic_registry_from_message(msg: dict) -> None:
    """Remember group/forum topic names Telegram reveals in service messages."""
    chat = msg.get("chat") or {}
    chat_id = str(chat.get("id") or "")
    if not chat_id:
        return

    registry = _load_topic_registry()
    chat_entry = registry.setdefault(
        chat_id,
        {
            "chat_id": chat_id,
            "chat_title": chat.get("title") or "",
            "chat_type": chat.get("type") or "",
            "topics": {},
        },
    )
    chat_entry["chat_title"] = chat.get("title") or chat_entry.get("chat_title") or ""
    chat_entry["chat_type"] = chat.get("type") or chat_entry.get("chat_type") or ""

    thread_id = msg.get("message_thread_id")
    if thread_id is None:
        _save_topic_registry(registry)
        return

    topic_entry = chat_entry.setdefault("topics", {}).setdefault(str(thread_id), {"message_thread_id": thread_id})
    topic_entry["message_thread_id"] = thread_id
    topic_entry["last_seen_at"] = datetime.now(timezone.utc).isoformat()
    topic_entry["status"] = topic_entry.get("status") or "open"

    created = msg.get("forum_topic_created")
    edited = msg.get("forum_topic_edited")
    if isinstance(created, dict) and created.get("name"):
        topic_entry["name"] = created["name"]
        topic_entry["icon_color"] = created.get("icon_color")
    if isinstance(edited, dict) and edited.get("name"):
        topic_entry["name"] = edited["name"]
    hint = _topic_name_hint(msg)
    if hint:
        topic_entry["name"], topic_entry["name_source"] = hint
    if msg.get("forum_topic_closed") is not None:
        topic_entry["status"] = "closed"
    if msg.get("forum_topic_reopened") is not None:
        topic_entry["status"] = "open"

    _save_topic_registry(registry)


def _register_group_from_member_update(update: dict) -> None:
    """Learn about groups from my_chat_member / chat_member updates.

    When the bot is added to a group, promoted, demoted, or removed,
    Telegram sends a ``my_chat_member`` update.  We use it to populate
    the topic registry so the bot knows which groups it belongs to.
    """
    chat = update.get("chat") or {}
    chat_id = str(chat.get("id") or "")
    chat_type = chat.get("type") or ""
    if not chat_id or chat_type not in ("group", "supergroup"):
        return

    new_member = update.get("new_chat_member") or {}
    status = new_member.get("status") or ""  # member, administrator, left, kicked, etc.

    registry = _load_topic_registry()
    chat_entry = registry.setdefault(
        chat_id,
        {
            "chat_id": chat_id,
            "chat_title": "",
            "chat_type": "",
            "topics": {},
        },
    )
    chat_entry["chat_title"] = chat.get("title") or chat_entry.get("chat_title") or ""
    chat_entry["chat_type"] = chat_type
    chat_entry["bot_status"] = status

    if status in ("left", "kicked"):
        # Bot was removed from the group — keep the entry but mark it
        chat_entry["bot_status"] = status
        logger.info("[Telegram] Bot removed from group %s (%s)", chat_id, chat_entry.get("chat_title"))
    else:
        logger.info(
            "[Telegram] Bot status in group %s (%s): %s",
            chat_id,
            chat_entry.get("chat_title"),
            status,
        )

    _save_topic_registry(registry)


def _telegram_context_from_message(msg: dict) -> dict:
    """Extract group and forum-topic context from a Telegram message."""
    chat = msg.get("chat") or {}
    chat_id = str(chat.get("id") or "")
    thread_id = msg.get("message_thread_id")
    registry = _load_topic_registry()
    chat_entry = registry.get(chat_id, {})
    topic_entry = (chat_entry.get("topics") or {}).get(str(thread_id), {}) if thread_id is not None else {}

    return {
        "chat_id": chat_id,
        "chat_type": chat.get("type") or chat_entry.get("chat_type") or "",
        "chat_title": chat.get("title") or chat_entry.get("chat_title") or "",
        "message_thread_id": thread_id,
        "is_topic_message": bool(msg.get("is_topic_message")),
        "topic_name": topic_entry.get("name") or "",
        "topic_name_source": topic_entry.get("name_source") or "",
        "known_topics": [
            {
                "message_thread_id": value.get("message_thread_id") or key,
                "name": value.get("name") or "",
                "status": value.get("status") or "open",
            }
            for key, value in sorted((chat_entry.get("topics") or {}).items())
        ],
    }


def _telegram_message_from_update(update: dict) -> dict | None:
    """Extract every Telegram update shape that carries message/thread metadata."""
    return (
        update.get("message")
        or update.get("edited_message")
        or update.get("channel_post")
        or update.get("edited_channel_post")
    )


def _telegram_context_from_update(update: dict) -> tuple[dict | None, dict | None]:
    """Extract and register inbound topic context before agent processing."""
    message = _telegram_message_from_update(update)
    if not message:
        return None, None
    _update_topic_registry_from_message(message)
    return message, _telegram_context_from_message(message)


def _telegram_context_text(user_msg: str, telegram_context: dict | None) -> str:
    """Add group/topic context to the prompt."""
    if not telegram_context:
        return user_msg

    chat_title = telegram_context.get("chat_title") or "unknown"
    chat_type = telegram_context.get("chat_type") or "unknown"
    thread_id = telegram_context.get("message_thread_id")
    topic_name = telegram_context.get("topic_name") or "unknown"
    known_topics = telegram_context.get("known_topics") or []

    lines = ["", "", "Telegram context:", f"- Chat: {chat_title} ({chat_type})"]
    if thread_id is not None:
        lines.append(f"- message_thread_id: {thread_id}")
        lines.append(f"- Topic name: {topic_name}")
    if known_topics:
        topic_text = ", ".join(
            f"{topic.get('name') or 'unknown'} [{topic.get('message_thread_id')}]" for topic in known_topics[:20]
        )
        lines.append(f"- Known topics in this chat: {topic_text}")
    else:
        lines.append("- Known topics in this chat: none learned yet")
    lines.append(
        "You can see the current group/topic metadata above, but Telegram Bot API does not provide a full topic list unless topic events or messages have been observed."
    )
    return user_msg.strip() + "\n".join(lines)


_IMAGE_MIME_PREFIX = "image/"
_FILENAME_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_upload_filename(name: str, fallback: str) -> str:
    """Return a local filename safe for the workspace."""
    clean = Path(name or "").name.strip() or fallback
    clean = _FILENAME_SAFE.sub("_", clean).strip("._")
    return (clean or fallback)[:120]


def _attachment_context_text(user_msg: str, attachments: list[dict]) -> str:
    """Add saved Telegram uploads to the prompt as workspace references."""
    text = user_msg.strip()
    if not attachments:
        return text

    if not text:
        text = "Please review the uploaded attachment(s)."

    lines = ["", "", "Uploaded attachment(s) saved in the Shogun workspace:"]
    for index, att in enumerate(attachments, start=1):
        label = att.get("filename") or att.get("kind") or f"attachment-{index}"
        rel_path = att.get("workspace_path") or att.get("path") or ""
        mime_type = att.get("mime_type") or "unknown type"
        size = att.get("size")
        size_text = f", {size} bytes" if isinstance(size, int) else ""
        lines.append(f"{index}. {label} ({mime_type}{size_text}) at {rel_path}")
    lines.append(
        "Use workspace tools to read files. For images use workspace_read_image, for PDFs use workspace_read_pdf."
    )
    return text + "\n".join(lines)


async def _download_telegram_file(
    bot_token: str,
    *,
    file_id: str,
    chat_id: str,
    kind: str,
    filename: str,
    mime_type: str | None = None,
    source_message_id: str | None = None,
    sender_id: str | None = None,
    caption: str | None = None,
) -> dict | None:
    """Download a Telegram file into the persistent agent workspace."""
    client = _get_tg_client()
    info_resp = await client.get(f"https://api.telegram.org/bot{bot_token}/getFile", params={"file_id": file_id})
    if not info_resp.is_success:
        logger.warning("[Telegram] getFile failed for %s: %s", file_id, info_resp.text[:200])
        return None

    file_path = info_resp.json().get("result", {}).get("file_path")
    if not file_path:
        logger.warning("[Telegram] getFile response had no file_path for %s", file_id)
        return None

    data_resp = await client.get(f"https://api.telegram.org/file/bot{bot_token}/{file_path}")
    if not data_resp.is_success:
        logger.warning("[Telegram] file download failed for %s: %s", file_id, data_resp.text[:200])
        return None

    suffix = Path(filename).suffix
    guessed_mime, guessed_encoding = mimetypes.guess_type(filename)
    effective_mime = mime_type or guessed_mime or data_resp.headers.get("content-type") or "application/octet-stream"
    if not suffix:
        suffix = mimetypes.guess_extension(effective_mime) or ".bin"
        filename = f"{filename}{suffix}"

    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    workspace_root = settings.workspace_path.resolve()
    target_dir = workspace_root / "Telegram" / day / _safe_upload_filename(chat_id, "chat")
    target_dir.mkdir(parents=True, exist_ok=True)
    safe_name = _safe_upload_filename(filename, f"{kind}-{file_id}{suffix}")
    target = target_dir / safe_name

    if target.exists():
        target = target.with_name(f"{target.stem}-{int(time.time())}{target.suffix}")

    content = data_resp.content
    if effective_mime.startswith(_IMAGE_MIME_PREFIX):
        try:
            from shogun.db.engine import async_session_factory
            from shogun.services.visual_intake import VisualIntakeService

            async with async_session_factory() as db:
                visual = VisualIntakeService(db)
                artifact = await visual.ingest(
                    content,
                    filename=filename,
                    declared_mime=effective_mime,
                    source="telegram",
                    source_chat_id=chat_id,
                    source_message_id=source_message_id,
                    sender_id=sender_id,
                    caption=caption,
                    chat_session_id=chat_id,
                )
                await db.commit()
                return visual._public(artifact) | {
                    "kind": kind,
                    "file_id": file_id,
                    "path": artifact.normalized_path,
                    "workspace_path": artifact.normalized_path,
                    "is_image": True,
                }
        except Exception as exc:
            logger.warning("[Telegram] governed image intake failed for %s: %s", file_id, exc)
            return None

    target.write_bytes(content)
    rel_path = target.relative_to(workspace_root).as_posix()
    return {
        "source": "telegram",
        "kind": kind,
        "file_id": file_id,
        "filename": target.name,
        "mime_type": effective_mime,
        "encoding": guessed_encoding,
        "size": len(content),
        "workspace_path": rel_path,
        "path": str(target),
        "is_image": effective_mime.startswith(_IMAGE_MIME_PREFIX),
    }


async def _extract_telegram_attachments(bot_token: str, chat_id: str, msg: dict) -> list[dict]:
    """Collect supported Telegram message uploads and save them locally."""
    attachments: list[dict] = []

    photos = msg.get("photo") or []
    if photos:
        photo = max(photos, key=lambda item: item.get("file_size", 0))
        file_unique_id = photo.get("file_unique_id") or photo.get("file_id") or "photo"
        attachment = await _download_telegram_file(
            bot_token,
            file_id=photo["file_id"],
            chat_id=chat_id,
            kind="photo",
            filename=_safe_upload_filename(f"{file_unique_id}.jpg", "telegram-photo.jpg"),
            mime_type="image/jpeg",
            source_message_id=str(msg.get("message_id") or ""),
            sender_id=str((msg.get("from") or {}).get("id") or ""),
            caption=msg.get("caption"),
        )
        if attachment:
            attachments.append(attachment)

    document = msg.get("document")
    if document and document.get("file_id"):
        attachment = await _download_telegram_file(
            bot_token,
            file_id=document["file_id"],
            chat_id=chat_id,
            kind="document",
            filename=_safe_upload_filename(document.get("file_name", ""), f"telegram-document-{document['file_id']}"),
            mime_type=document.get("mime_type"),
            source_message_id=str(msg.get("message_id") or ""),
            sender_id=str((msg.get("from") or {}).get("id") or ""),
            caption=msg.get("caption"),
        )
        if attachment:
            attachments.append(attachment)

    return attachments


async def send_chat_action(
    bot_token: str,
    chat_id: str,
    action: str = "typing",
    *,
    message_thread_id: int | None = None,
):
    """Send a chat action indicator (e.g. 'typing...') — instant user feedback."""
    url = f"https://api.telegram.org/bot{bot_token}/sendChatAction"
    try:
        client = _get_tg_client()
        payload = {"chat_id": chat_id, "action": action}
        if message_thread_id is not None:
            payload["message_thread_id"] = int(message_thread_id)
        await client.post(url, json=payload)
    except Exception:
        pass  # Non-critical — best effort


async def send_telegram_message(
    bot_token: str,
    chat_id: str,
    text: str,
    *,
    message_thread_id: int | None = None,
    use_markdown: bool = True,
) -> int | None:
    """Push a textual response back to the Telegram client. Returns message_id if successful."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    if use_markdown:
        payload["parse_mode"] = "Markdown"
    if message_thread_id is not None:
        payload["message_thread_id"] = message_thread_id
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
) -> bool:
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
        if resp.is_success:
            return True
        if not resp.is_success:
            # Often occurs if content is identical, skip error logging for that
            if "message is not modified" not in resp.text:
                logger.debug(f"Note: Failed to edit Telegram message: {resp.text}")
            else:
                return True
    except Exception as e:
        logger.error(f"Network error editing Telegram message: {e}")
    return False


async def process_telegram_message(
    bot_token: str,
    chat_id: str,
    user_msg: str,
    attachments: list[dict] | None = None,
    telegram_context: dict | None = None,
):
    """Process one inbound message inside its isolated Telegram topic scope."""
    from shogun.services.telegram_routing_context import telegram_routing_scope

    with telegram_routing_scope(telegram_context):
        return await _process_telegram_message(bot_token, chat_id, user_msg, attachments, telegram_context)


async def _process_telegram_message(
    bot_token: str,
    chat_id: str,
    user_msg: str,
    attachments: list[dict] | None = None,
    telegram_context: dict | None = None,
):
    """Pipe an incoming message into the Shogun AI engine, capturing its SSE streaming output."""
    attachments = attachments or []
    message_thread_id = telegram_context.get("message_thread_id") if telegram_context else None
    prompt_msg = _telegram_context_text(_attachment_context_text(user_msg, attachments), telegram_context)
    logger.info(f"[Telegram] Received: '{user_msg[:50]}...' from {chat_id}")

    # ── 0. Immediate typing indicator — user sees feedback in <100ms ──
    await send_chat_action(
        bot_token,
        chat_id,
        "typing",
        message_thread_id=message_thread_id,
    )

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
                message_thread_id=message_thread_id,
            )
        else:
            await send_telegram_message(
                bot_token,
                chat_id,
                "✅ *HARAKIRI RESET*\n\nThe kill switch is inactive. Posture is now TACTICAL.",
                message_thread_id=message_thread_id,
            )
        return

    # ── Posture enforcement: kill switch gate ──────────────────
    posture = {"active_tier": "guarded", "ide_enabled": False}
    try:
        from shogun.api.security import _get_agent_posture

        posture = await _get_agent_posture()
        if posture.get("kill_switch_active", False):
            logger.warning("[Telegram] Kill switch active — blocking message from %s", chat_id)
            await send_telegram_message(
                bot_token,
                chat_id,
                "⛩️ Shogun is in emergency lockdown mode (HARAKIRI). "
                "All AI operations are suspended. Deactivate the kill switch "
                "in the Torii to resume.",
                message_thread_id=message_thread_id,
            )
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

            prompt_msg, chat_attachments = await _prepare_telegram_visual_context(session, prompt_msg, attachments)
            history = await get_chat_context(session, limit=20)
            await append_chat_message(
                session,
                channel="telegram",
                role="user",
                content=prompt_msg,
                external_chat_id=chat_id,
                message_data={
                    **(
                        {
                            "attachments": [
                                {
                                    key: value
                                    for key, value in attachment.items()
                                    if key not in {"path", "workspace_path"}
                                }
                                for attachment in attachments
                            ]
                        }
                        if attachments
                        else {}
                    ),
                    **({"telegram_context": telegram_context} if telegram_context else {}),
                },
            )
            await session.commit()

            # ── 1. Select the Telegram execution lane ──────────────
            # Telegram has no graphical mode selector, so default to the
            # tool-capable Mission lane. Torii still gates every tool call.
            prompt_msg, mode, classification = _select_telegram_chat_mode(prompt_msg, history)
            try:
                from shogun.schemas.skills import SkillActivationRequest
                from shogun.services.active_skill_service import SkillActivationService
                from shogun.services.native_skills import NATIVE_TOOLS

                skill_result = await SkillActivationService(session).activate(
                    SkillActivationRequest(
                        run_id=f"telegram:{chat_id}:{uuid.uuid4()}",
                        objective=prompt_msg,
                        context=" ".join(
                            str(item.get("content", "")) for item in history[-4:] if isinstance(item, dict)
                        ),
                        posture=posture.get("active_tier", "guarded"),
                        available_tools=[item["function"]["name"] for item in NATIVE_TOOLS],
                        usage_location="telegram",
                        agent_id="shogun",
                        ide_enabled=bool(posture.get("ide_enabled", False)),
                    )
                )
                classification["_skill_context"] = skill_result["context_block"]
                classification["_active_skill_run_ids"] = [
                    str(item["active_skill_run_id"]) for item in skill_result["active_skills"]
                ]
                classification["active_skills"] = [item["name"] for item in skill_result["active_skills"]]
                await session.commit()
            except Exception as exc:
                logger.warning("[Telegram] Active skill trajectory capture skipped: %s", exc)
            logger.info(
                "[Telegram] Mode classified: %s (reason=%s, matched=%s)",
                mode,
                classification.get("reason", ""),
                classification.get("matched", [])[:3],
            )

            # 2. Send initial thinking message
            msg_id = await send_telegram_message(
                bot_token,
                chat_id,
                "_Shogun is thinking..._",
                message_thread_id=message_thread_id,
            )

            # 3. Invoke the appropriate engine lane
            if mode == "fast":
                from shogun.api.agents import _shogun_fast_chat

                logger.info("[Telegram] Routing to Fast Chat lane...")
                response_stream = await _shogun_fast_chat(
                    user_msg=prompt_msg,
                    history=history,
                    svc=svc,
                    classification=classification,
                )
            elif mode == "governed":
                from shogun.api.governed_chat import _shogun_governed_chat

                logger.info("[Telegram] Routing to Governed Chat lane...")
                response_stream = await _shogun_governed_chat(
                    user_msg=prompt_msg,
                    history=history,
                    svc=svc,
                    classification=classification,
                )
            else:
                logger.info("[Telegram] Routing to Mission lane...")
                response_stream = await _shogun_chat_internal(
                    user_msg=prompt_msg,
                    history=history,
                    svc=svc,
                    classification=classification,
                    attachments=chat_attachments,
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
                                        current_action = ""  # Clear action when text resumes
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

                        if msg_id is not None and display_text and display_text != last_update_text:
                            # use_markdown=False for intermediate edits to avoid
                            # Telegram rejecting partial/unclosed markdown syntax
                            await edit_telegram_message(
                                bot_token,
                                chat_id,
                                msg_id,
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
            edited = False
            if msg_id is not None:
                edited = await edit_telegram_message(bot_token, chat_id, msg_id, full_reply, use_markdown=True)
            if not edited:
                await send_telegram_message(
                    bot_token,
                    chat_id,
                    full_reply,
                    message_thread_id=message_thread_id,
                    use_markdown=False,
                )
            await append_chat_message(
                session,
                channel="telegram",
                role="assistant",
                content=full_reply,
                external_chat_id=chat_id,
                message_data={
                    "telegram_context": telegram_context,
                    "reply_to_message_id": msg_id,
                },
            )
            await session.commit()
            logger.info(f"[Telegram] Response finalized for {chat_id}")

    except Exception as e:
        logger.error(f"[Telegram] Critical failure in process_telegram_message: {e}\n{traceback.format_exc()}")
        await send_telegram_message(
            bot_token,
            chat_id,
            "⚠️ I encountered a critical system error.",
            message_thread_id=message_thread_id,
        )


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
            # Request my_chat_member updates so we learn about groups the bot is added to.
            url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
            params = {
                "timeout": "30",
                "offset": str(offset),
                "allowed_updates": json.dumps(
                    [
                        "message",
                        "edited_message",
                        "channel_post",
                        "edited_channel_post",
                        "my_chat_member",
                        "chat_member",
                    ]
                ),
            }

            client = _get_tg_client()
            try:
                resp = await client.get(url, params=params)
            except httpx.ReadTimeout:
                continue
            except Exception as e:
                logger.warning(f"[Telegram] Polling network exception: {e}")
                await asyncio.sleep(5)
                continue

            if not resp.is_success:
                if resp.status_code == 401:
                    # Invalid or revoked bot token — auto-disconnect to stop polling
                    logger.warning(
                        "[Telegram] Bot token is invalid (HTTP 401). Auto-disconnecting to stop polling. Reconfigure in the Katana to reconnect."
                    )
                    try:
                        async with async_session_factory() as session:
                            from sqlalchemy import select

                            agent = (
                                await session.execute(
                                    select(Agent).where(
                                        Agent.agent_type == "shogun",
                                        Agent.is_primary == True,
                                        Agent.is_deleted == False,
                                    )
                                )
                            ).scalar_one_or_none()
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

                # ── Handle my_chat_member updates (bot added/removed/promoted in groups) ──
                member_update = update.get("my_chat_member") or update.get("chat_member")
                if member_update:
                    _register_group_from_member_update(member_update)

                msg, telegram_context = _telegram_context_from_update(update)
                if not msg:
                    continue

                chat = msg.get("chat", {})
                chat_id_str = str(chat.get("id"))
                text = (msg.get("text") or msg.get("caption") or "").strip()

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
                        message_thread_id=(
                            telegram_context.get("message_thread_id")
                            if telegram_context
                            else None
                        ),
                    )
                    continue

                attachments = await _extract_telegram_attachments(bot_token, chat_id_str, msg)

                if text or attachments:
                    asyncio.create_task(
                        process_telegram_message(
                            bot_token,
                            chat_id_str,
                            text,
                            attachments,
                            telegram_context,
                        )
                    )

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
