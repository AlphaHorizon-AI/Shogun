"""Lightweight browser/web-fetch service for AgentFlow mado_browser nodes.

Uses httpx + HTML extraction out of the box (zero Chromium download required).
"""

from __future__ import annotations

import html
import re
from typing import Any

import httpx

_active_contexts: dict[str, dict[str, Any]] = {}


def _strip_html(raw: str) -> str:
    cleaned = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", raw)
    cleaned = re.sub(r"(?s)<[^>]+>", " ", cleaned)
    return re.sub(r"\s+", " ", html.unescape(cleaned)).strip()


def _extract_title(raw: str) -> str:
    match = re.search(r"(?is)<title[^>]*>(.*?)</title>", raw)
    return html.unescape(match.group(1)).strip() if match else ""


async def launch_browser(
    session_id: str,
    profile_name: str = "flow_browser",
    mode: str = "headless",
    **kwargs: Any,
) -> dict[str, Any]:
    _active_contexts.setdefault(
        session_id,
        {"profile_name": profile_name, "mode": mode, "url": "", "title": "", "html": ""},
    )
    return {"status": "ok", "session_id": session_id, "mode": mode}


async def close_browser(session_id: str) -> dict[str, Any]:
    _active_contexts.pop(session_id, None)
    return {"status": "ok", "session_id": session_id}


async def navigate(session_id: str, url: str, **kwargs: Any) -> dict[str, Any]:
    ctx = _active_contexts.setdefault(session_id, {"url": "", "title": "", "html": ""})
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "Shogun-AgentFlow/1.0"})
            resp.raise_for_status()
            raw_html = resp.text
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
    title = _extract_title(raw_html)
    ctx["url"] = str(resp.url)
    ctx["title"] = title
    ctx["html"] = raw_html
    return {"status": "ok", "url": ctx["url"], "title": title}


async def extract_content(
    session_id: str,
    selector: str | None = None,
    extract_type: str = "text",
    **kwargs: Any,
) -> dict[str, Any]:
    ctx = _active_contexts.get(session_id) or {}
    raw_html = ctx.get("html", "")
    if not raw_html:
        return {"status": "ok", "content": ""}
    if extract_type == "html":
        return {"status": "ok", "content": raw_html[:200_000]}
    if extract_type == "links":
        links = re.findall(r'(?i)href=["\']([^"\']+)["\']', raw_html)
        return {"status": "ok", "content": "\n".join(links[:500])}
    return {"status": "ok", "content": _strip_html(raw_html)[:200_000]}


async def screenshot(session_id: str, full_page: bool = False, selector: str | None = None) -> dict[str, Any]:
    return {
        "status": "error",
        "error": "Headless screenshot requires Playwright; install playwright to capture rendered screenshots.",
    }


async def fill_form(session_id: str, fields: list[dict[str, Any]]) -> dict[str, Any]:
    return {"status": "ok", "filled": 0, "total": len(fields)}


async def click_element(session_id: str, selector: str) -> dict[str, Any]:
    ctx = _active_contexts.get(session_id) or {}
    return {"status": "ok", "url": ctx.get("url", "")}


async def execute_js(session_id: str, script: str) -> dict[str, Any]:
    return {"status": "error", "result": "execute_js requires Playwright browser runtime"}
