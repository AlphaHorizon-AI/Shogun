"""Compact native tool registry for bare-bones AgentFlow nodes."""

from __future__ import annotations

import html
import json
import os
import re
from pathlib import Path
from typing import Any

import httpx

from shogun.config import settings

NATIVE_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "fetch_inbox",
            "description": "Read recent emails from the configured IMAP mailbox.",
            "parameters": {
                "type": "object",
                "properties": {
                    "folder": {"type": "string", "default": "INBOX"},
                    "page": {"type": "integer", "default": 1},
                    "per_page": {"type": "integer", "default": 10},
                    "unread_only": {"type": "boolean", "default": True},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_calendar_events",
            "description": "List calendar events within a date window.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                    "days_ahead": {"type": "integer", "default": 1},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": "Fetch text content from an HTTP/HTTPS URL.",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "workspace_list",
            "description": "List files inside the configured local workspace folder.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "default": ""}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "workspace_read",
            "description": "Read a text file inside the configured local workspace folder.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "workspace_write",
            "description": "Write text content to a file inside the configured local workspace folder.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
]


def generate_tool_prompt(tools: list[dict[str, Any]] | None = None) -> str:
    items = tools if tools is not None else NATIVE_TOOLS
    if not items:
        return ""
    lines = ["Available tools:"]
    for item in items:
        fn = item.get("function") or {}
        lines.append(f"- {fn.get('name', 'tool')}: {fn.get('description', '')}")
    return "\n".join(lines)


def _safe_workspace_path(rel_path: str) -> Path:
    root = Path(settings.workspace_path).resolve()
    target = (root / (rel_path or "").lstrip("/\\")).resolve()
    if target != root and root not in target.parents:
        raise ValueError("Path escapes configured local workspace folder")
    return target


async def execute_native_tool(
    tool_name: str,
    args: dict[str, Any] | None = None,
    session: Any = None,
) -> str:
    params = dict(args or {})
    try:
        if tool_name == "fetch_inbox":
            from shogun.services.email_service import EmailService

            messages = await EmailService(session).list_messages(
                folder=str(params.get("folder") or "INBOX"),
                page=int(params.get("page") or 1),
                per_page=int(params.get("per_page") or 10),
                unread_only=bool(params.get("unread_only", True)),
            )
            return json.dumps({"status": "success", "messages": messages, "count": len(messages)})

        if tool_name == "list_calendar_events":
            ics_url = os.environ.get("CALENDAR_ICS_URL", "").strip()
            if not ics_url:
                return json.dumps(
                    {
                        "status": "error",
                        "message": "No calendar configured. Set CALENDAR_ICS_URL in .env to enable calendar_read.",
                    }
                )
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                resp = await client.get(ics_url)
                resp.raise_for_status()
            events = []
            for block in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", resp.text, flags=re.S):
                summary = re.search(r"SUMMARY:(.*)", block)
                dtstart = re.search(r"DTSTART[^:]*:(.*)", block)
                dtend = re.search(r"DTEND[^:]*:(.*)", block)
                events.append(
                    {
                        "summary": summary.group(1).strip() if summary else "(Untitled)",
                        "start": dtstart.group(1).strip() if dtstart else "",
                        "end": dtend.group(1).strip() if dtend else "",
                    }
                )
            return json.dumps({"status": "success", "events": events[:50], "count": len(events)})

        if tool_name == "web_fetch":
            url = str(params.get("url") or "").strip()
            if not url:
                return json.dumps({"status": "error", "message": "url is required"})
            async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": "Shogun-AgentFlow/1.0"})
                resp.raise_for_status()
            cleaned = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", resp.text)
            cleaned = re.sub(r"(?s)<[^>]+>", " ", cleaned)
            text = re.sub(r"\s+", " ", html.unescape(cleaned)).strip()[:50_000]
            return json.dumps({"status": "success", "url": str(resp.url), "content": text})

        if tool_name == "workspace_list":
            target = _safe_workspace_path(str(params.get("path") or ""))
            if not target.exists():
                return json.dumps({"status": "success", "entries": []})
            entries = [
                {"name": p.name, "is_dir": p.is_dir(), "size": p.stat().st_size if p.is_file() else 0}
                for p in sorted(target.iterdir())[:200]
            ]
            return json.dumps({"status": "success", "entries": entries})

        if tool_name == "workspace_read":
            target = _safe_workspace_path(str(params.get("path") or ""))
            if not target.is_file():
                return json.dumps({"status": "error", "message": f"File not found: {params.get('path')}"})
            content = target.read_text(encoding="utf-8", errors="replace")[:100_000]
            return json.dumps({"status": "success", "path": str(params.get("path")), "content": content})

        if tool_name == "workspace_write":
            target = _safe_workspace_path(str(params.get("path") or ""))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(str(params.get("content") or ""), encoding="utf-8")
            return json.dumps({"status": "success", "path": str(params.get("path"))})

        return json.dumps({"status": "error", "message": f"Unknown native tool: {tool_name}"})
    except Exception as exc:
        return json.dumps({"status": "error", "message": str(exc)})
