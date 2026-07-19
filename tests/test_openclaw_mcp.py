import asyncio
import json
import sys
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

import shogun.mcp.openclaw_dojo as openclaw_dojo
from shogun.services.mcp_bridge import MCPStdioSession


async def _request(proc, request_id: int, method: str, params: dict | None = None) -> dict:
    assert proc.stdin is not None
    assert proc.stdout is not None
    proc.stdin.write(
        (json.dumps({
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params or {},
        }) + "\n").encode("utf-8")
    )
    await proc.stdin.drain()
    raw = await asyncio.wait_for(proc.stdout.readline(), timeout=10)
    return json.loads(raw.decode("utf-8"))


@pytest.mark.asyncio
async def test_openclaw_dojo_mcp_lists_tools():
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "shogun.mcp.openclaw_dojo",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        init = await _request(proc, 1, "initialize")
        assert init["result"]["serverInfo"]["name"] == "openclaw-dojo"

        tools = await _request(proc, 2, "tools/list")
        names = {tool["name"] for tool in tools["result"]["tools"]}
        assert "openclaw_search_skills" in names
        assert "openclaw_get_achievements" in names
        assert "openclaw_take_exam" in names
        assert "openclaw_enroll_specialization" in names
        assert "openclaw_evaluate_achievements" in names
    finally:
        proc.terminate()
        await proc.wait()


@pytest.mark.asyncio
async def test_mcp_bridge_lists_openclaw_tools():
    connector = SimpleNamespace(
        slug="openclaw-dojo",
        config={
            "command": "shogun-python",
            "args": ["-m", "shogun.mcp.openclaw_dojo"],
            "env": {},
            "transport": "stdio",
        },
    )
    async with MCPStdioSession(connector) as session:
        result = await session.list_tools()

    names = {tool["name"] for tool in result["tools"]}
    assert "openclaw_search_skills" in names
    assert "openclaw_list_installed" in names
    assert "openclaw_enroll_specialization" in names


@dataclass
class _FakeSpecialization:
    id: str
    name: str
    slug: str
    description: str
    faculty_id: str
    badge_count: int


@pytest.mark.asyncio
async def test_openclaw_mcp_pages_specializations(monkeypatch):
    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get_specializations(self):
            return [
                _FakeSpecialization(
                    id=f"spec-{i}",
                    name=f"Specialization {i}",
                    slug=f"specialization-{i}",
                    description="Large specialization payload",
                    faculty_id="strategy",
                    badge_count=i,
                )
                for i in range(5)
            ]

    monkeypatch.setattr(
        "shogun.integrations.openclaw_client.get_openclaw_client",
        lambda: FakeClient(),
    )

    result = await openclaw_dojo.openclaw_get_specializations({"page": 2, "per_page": 2})

    assert result["status"] == "success"
    assert result["total"] == 5
    assert result["page"] == 2
    assert result["per_page"] == 2
    assert result["has_more"] is True
    assert [item["id"] for item in result["specializations"]] == ["spec-2", "spec-3"]


@pytest.mark.asyncio
async def test_openclaw_mcp_pages_unicode_badges(monkeypatch):
    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get_badges(self):
            return [
                {"id": "badge-1", "name": "Morning Brief 🗡️", "description": "Café analysis"},
                {"id": "badge-2", "name": "Governance ✅", "description": "Unicode-safe"},
                {"id": "badge-3", "name": "Research", "description": "Final item"},
            ]

    monkeypatch.setattr(
        "shogun.integrations.openclaw_client.get_openclaw_client",
        lambda: FakeClient(),
    )

    result = await openclaw_dojo.openclaw_get_badges({"page": 1, "per_page": 2})
    wrapped = openclaw_dojo._text_response(result)
    encoded = json.dumps(wrapped, ensure_ascii=False).encode("utf-8")

    assert result["total"] == 3
    assert result["has_more"] is True
    assert [item["id"] for item in result["badges"]] == ["badge-1", "badge-2"]
    assert "Morning Brief" in encoded.decode("utf-8")
