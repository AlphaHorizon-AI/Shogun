"""OpenClaw Dojo MCP server.

Run with:
    python -m shogun.mcp.openclaw_dojo

This intentionally implements the small stdio JSON-RPC subset Shogun needs
instead of requiring an additional MCP SDK dependency.
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import Awaitable, Callable
from dataclasses import asdict, is_dataclass
from typing import Any

ToolHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]
MAX_PAGE_SIZE = 200


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _record_payload(record: Any) -> dict[str, Any]:
    if is_dataclass(record):
        return asdict(record)
    if isinstance(record, dict):
        return dict(record)
    return dict(getattr(record, "__dict__", {}))


def _page_args(args: dict[str, Any], default_per_page: int = 50) -> tuple[int, int]:
    page = max(1, int(args.get("page") or 1))
    per_page = min(MAX_PAGE_SIZE, max(1, int(args.get("per_page") or default_per_page)))
    return page, per_page


def _paged_response(key: str, items: list[Any], page: int, per_page: int) -> dict[str, Any]:
    total = len(items)
    start = (page - 1) * per_page
    page_items = items[start:start + per_page]
    return {
        "status": "success",
        "total": total,
        "page": page,
        "per_page": per_page,
        "has_more": start + per_page < total,
        key: page_items,
    }


def _text_response(payload: Any) -> dict[str, Any]:
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            }
        ]
    }


def _json_loads_maybe(value: str) -> dict[str, Any]:
    try:
        data = json.loads(value)
        return data if isinstance(data, dict) else {"value": data}
    except Exception:
        return {"status": "error", "message": value}


def _skill_payload(skill: Any) -> dict[str, Any]:
    if is_dataclass(skill):
        data = asdict(skill)
    elif isinstance(skill, dict):
        data = dict(skill)
    else:
        data = dict(getattr(skill, "__dict__", {}))
    return {
        "id": data.get("id"),
        "slug": data.get("slug"),
        "name": data.get("name"),
        "description": data.get("short_description") or data.get("description"),
        "faculty": data.get("faculty_id") or data.get("faculty"),
        "subcategory": data.get("subcategory_id") or data.get("subcategory"),
        "author": data.get("author_name") or data.get("author"),
        "risk_tier": data.get("risk_tier"),
        "status": data.get("status"),
        "version": data.get("version"),
        "capabilities": data.get("capabilities", []),
        "permissions": {
            "network": bool(data.get("network_access")),
            "filesystem_read": bool(data.get("filesystem_read")),
            "filesystem_write": bool(data.get("filesystem_write")),
            "credentials": bool(data.get("credential_access")),
            "shell": bool(data.get("shell_execution")),
        },
    }


async def openclaw_search_skills(args: dict[str, Any]) -> dict[str, Any]:
    from shogun.integrations.openclaw_client import get_openclaw_client

    page, per_page = _page_args(args)
    async with get_openclaw_client() as client:
        skills = await client.get_skills(
            faculty=args.get("faculty") or None,
            subcategory=args.get("subcategory") or args.get("category") or None,
            risk_tier=args.get("risk_tier") or None,
            search=args.get("search") or None,
            limit=None,
        )
    return _paged_response("skills", [_skill_payload(skill) for skill in skills], page, per_page)


async def openclaw_get_skill(args: dict[str, Any]) -> dict[str, Any]:
    from shogun.integrations.openclaw_client import get_openclaw_client

    skill_id = str(args.get("skill_id") or args.get("id") or "").strip()
    if not skill_id:
        return {"status": "error", "message": "skill_id is required."}
    async with get_openclaw_client() as client:
        skill = await client.get_skill_by_id(skill_id)
    if not skill:
        return {"status": "error", "message": f"Skill {skill_id} not found."}
    return {"status": "success", "skill": _skill_payload(skill)}


async def openclaw_get_bundles(args: dict[str, Any]) -> dict[str, Any]:
    from shogun.integrations.openclaw_client import get_openclaw_client

    async with get_openclaw_client() as client:
        bundles = await client.get_bundles(faculty=args.get("faculty") or None)
    return {"status": "success", "total": len(bundles), "bundles": [asdict(b) for b in bundles]}


async def openclaw_get_specializations(args: dict[str, Any]) -> dict[str, Any]:
    from shogun.integrations.openclaw_client import get_openclaw_client

    page, per_page = _page_args(args)
    async with get_openclaw_client() as client:
        specs = await client.get_specializations()
    return _paged_response(
        "specializations",
        [_record_payload(s) for s in specs],
        page,
        per_page,
    )


async def openclaw_get_badges(args: dict[str, Any]) -> dict[str, Any]:
    from shogun.integrations.openclaw_client import get_openclaw_client

    page, per_page = _page_args(args)
    async with get_openclaw_client() as client:
        badges = await client.get_badges()
    return _paged_response(
        "badges",
        [_record_payload(b) for b in badges],
        page,
        per_page,
    )


async def openclaw_list_installed(_args: dict[str, Any]) -> dict[str, Any]:
    from shogun.services.native_skills import _dojo_list_installed

    return _json_loads_maybe(await _dojo_list_installed())


async def openclaw_install_skill(args: dict[str, Any]) -> dict[str, Any]:
    from shogun.services.native_skills import _dojo_install_skill

    return _json_loads_maybe(await _dojo_install_skill(args))


async def openclaw_take_exam(args: dict[str, Any]) -> dict[str, Any]:
    from shogun.services.native_skills import _dojo_take_exam

    return _json_loads_maybe(await _dojo_take_exam(args))


async def openclaw_enroll_specialization(args: dict[str, Any]) -> dict[str, Any]:
    from shogun.services.native_skills import _dojo_enroll_specialization

    return _json_loads_maybe(await _dojo_enroll_specialization(args))


async def openclaw_evaluate_achievements(_args: dict[str, Any]) -> dict[str, Any]:
    from shogun.services.native_skills import _dojo_evaluate_achievements

    return _json_loads_maybe(await _dojo_evaluate_achievements())


async def openclaw_get_achievements(_args: dict[str, Any]) -> dict[str, Any]:
    from shogun.services.native_skills import _dojo_get_achievements

    return _json_loads_maybe(await _dojo_get_achievements())


async def openclaw_get_transcript(_args: dict[str, Any]) -> dict[str, Any]:
    from shogun.services.native_skills import _dojo_get_transcript

    return _json_loads_maybe(await _dojo_get_transcript())


TOOLS: dict[str, dict[str, Any]] = {
    "openclaw_search_skills": {
        "description": "Search and page through the full OpenClaw College skill catalog.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "search": {"type": "string"},
                "faculty": {"type": "string"},
                "subcategory": {"type": "string"},
                "category": {"type": "string"},
                "risk_tier": {"type": "string"},
                "page": {"type": "integer", "default": 1},
                "per_page": {"type": "integer", "default": 50, "maximum": 200},
            },
        },
        "handler": openclaw_search_skills,
    },
    "openclaw_get_skill": {
        "description": "Get detailed metadata for a single OpenClaw skill.",
        "inputSchema": {"type": "object", "properties": {"skill_id": {"type": "string"}}, "required": ["skill_id"]},
        "handler": openclaw_get_skill,
    },
    "openclaw_get_bundles": {
        "description": "List OpenClaw curated skill bundles.",
        "inputSchema": {"type": "object", "properties": {"faculty": {"type": "string"}}},
        "handler": openclaw_get_bundles,
    },
    "openclaw_get_specializations": {
        "description": "Page through OpenClaw certification specializations.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "page": {"type": "integer", "default": 1},
                "per_page": {"type": "integer", "default": 50, "maximum": 200},
            },
        },
        "handler": openclaw_get_specializations,
    },
    "openclaw_get_badges": {
        "description": "Page through OpenClaw badge catalog entries.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "page": {"type": "integer", "default": 1},
                "per_page": {"type": "integer", "default": 50, "maximum": 200},
            },
        },
        "handler": openclaw_get_badges,
    },
    "openclaw_list_installed": {
        "description": "List skills installed in the local Shogun Dojo.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": openclaw_list_installed,
    },
    "openclaw_install_skill": {
        "description": "Install an OpenClaw skill into the local Shogun Dojo.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "openclaw_skill_id": {"type": "string"},
                "skill_name": {"type": "string"},
                "description": {"type": "string"},
            },
            "required": ["openclaw_skill_id", "skill_name"],
        },
        "handler": openclaw_install_skill,
    },
    "openclaw_take_exam": {
        "description": "Take and submit the certification exam for an OpenClaw skill.",
        "inputSchema": {
            "type": "object",
            "properties": {"openclaw_skill_id": {"type": "string"}},
            "required": ["openclaw_skill_id"],
        },
        "handler": openclaw_take_exam,
    },
    "openclaw_enroll_specialization": {
        "description": "Enroll the Shogun agent in a specialization and immediately apply prior passed exams.",
        "inputSchema": {
            "type": "object",
            "properties": {"specialization_id": {"type": "string"}},
            "required": ["specialization_id"],
        },
        "handler": openclaw_enroll_specialization,
    },
    "openclaw_evaluate_achievements": {
        "description": "Reevaluate enrolled specializations and award all newly earned badges.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": openclaw_evaluate_achievements,
    },
    "openclaw_get_achievements": {
        "description": "Show the registered Shogun agent's OpenClaw achievements.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": openclaw_get_achievements,
    },
    "openclaw_get_transcript": {
        "description": "Show the registered Shogun agent's OpenClaw transcript.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": openclaw_get_transcript,
    },
}


RESOURCES = [
    {"uri": "openclaw://skills", "name": "OpenClaw skill catalog", "mimeType": "application/json"},
    {"uri": "openclaw://agent/achievements", "name": "Shogun OpenClaw achievements", "mimeType": "application/json"},
    {"uri": "openclaw://agent/transcript", "name": "Shogun OpenClaw transcript", "mimeType": "application/json"},
    {"uri": "openclaw://badges", "name": "OpenClaw badge catalog", "mimeType": "application/json"},
    {"uri": "openclaw://specializations", "name": "OpenClaw specializations", "mimeType": "application/json"},
]


async def _read_resource(uri: str) -> dict[str, Any]:
    if uri == "openclaw://skills":
        data = await openclaw_search_skills({"page": 1, "per_page": 100})
    elif uri == "openclaw://agent/achievements":
        data = await openclaw_get_achievements({})
    elif uri == "openclaw://agent/transcript":
        data = await openclaw_get_transcript({})
    elif uri == "openclaw://badges":
        data = await openclaw_get_badges({"page": 1, "per_page": 100})
    elif uri == "openclaw://specializations":
        data = await openclaw_get_specializations({"page": 1, "per_page": 100})
    elif uri.startswith("openclaw://skills/"):
        data = await openclaw_get_skill({"skill_id": uri.rsplit("/", 1)[-1]})
    else:
        raise ValueError(f"Unknown resource: {uri}")
    return {
        "contents": [
            {
                "uri": uri,
                "mimeType": "application/json",
                "text": json.dumps(data, ensure_ascii=False, indent=2, default=str),
            }
        ]
    }


async def _handle(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    request_id = message.get("id")
    params = message.get("params") or {}

    if request_id is None:
        return None

    try:
        if method == "initialize":
            result = {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}, "resources": {}},
                "serverInfo": {"name": "openclaw-dojo", "version": "1.0.0"},
            }
        elif method == "tools/list":
            result = {
                "tools": [
                    {
                        "name": name,
                        "description": meta["description"],
                        "inputSchema": meta["inputSchema"],
                    }
                    for name, meta in TOOLS.items()
                ]
            }
        elif method == "tools/call":
            name = str(params.get("name") or "")
            if name not in TOOLS:
                raise ValueError(f"Unknown tool: {name}")
            arguments = params.get("arguments") or {}
            result = _text_response(await TOOLS[name]["handler"](arguments))
        elif method == "resources/list":
            result = {"resources": RESOURCES}
        elif method == "resources/read":
            result = await _read_resource(str(params.get("uri") or ""))
        else:
            raise ValueError(f"Unknown method: {method}")
        return {"jsonrpc": "2.0", "id": request_id, "result": result}
    except Exception as exc:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32000, "message": str(exc)},
        }


async def main() -> None:
    while True:
        line = await asyncio.to_thread(sys.stdin.buffer.readline)
        if not line:
            break
        try:
            message = json.loads(line.decode("utf-8"))
        except Exception:
            continue
        response = await _handle(message)
        if response is not None:
            sys.stdout.write(json.dumps(response, separators=(",", ":"), ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    asyncio.run(main())
