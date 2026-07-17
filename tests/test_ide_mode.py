from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException

from shogun.services.ide_service import IDEService
from shogun.services.posture_guard import filter_tools_by_posture


def tool(name: str) -> dict:
    return {"type": "function", "function": {"name": name}}


@pytest.mark.asyncio
async def test_ide_is_deterministically_blocked_below_campaign(monkeypatch):
    service = IDEService()
    monkeypatch.setattr(service, "posture", lambda: async_value({"active_tier": "tactical", "ide_enabled": True}))
    allow_ide(monkeypatch, service)
    with pytest.raises(HTTPException, match="unavailable below Campaign"):
        await service.gate("file.read")
    allowed, denied = filter_tools_by_posture([tool("ide_read_file")], {"active_tier": "tactical", "ide_enabled": True})
    assert not allowed and denied == ["ide_read_file"]


@pytest.mark.asyncio
async def test_ide_requires_explicit_enablement(monkeypatch):
    service = IDEService()
    monkeypatch.setattr(service, "posture", lambda: async_value({"active_tier": "campaign", "ide_enabled": False}))
    allow_ide(monkeypatch, service)
    with pytest.raises(HTTPException, match="IDE Mode is disabled"):
        await service.gate("workspace.register")


@pytest.mark.asyncio
async def test_pairing_token_is_one_time(monkeypatch):
    service = IDEService()
    monkeypatch.setattr(service, "posture", lambda: async_value({"active_tier": "campaign", "ide_enabled": True}))
    allow_ide(monkeypatch, service)
    monkeypatch.setattr(service, "event", noop_event)
    pairing = await service.create_pairing()
    assert await service.confirm_pairing(pairing["token"])
    with pytest.raises(HTTPException, match="already used"):
        await service.confirm_pairing(pairing["token"])


@pytest.mark.asyncio
async def test_workspace_boundary_snapshot_and_rollback(monkeypatch, tmp_path: Path):
    service = IDEService()
    monkeypatch.setattr(service, "posture", lambda: async_value({"active_tier": "campaign", "ide_enabled": True, "kill_switch_active": False}))
    allow_ide(monkeypatch, service)
    monkeypatch.setattr(service, "event", noop_event)
    source = tmp_path / "app.py"; source.write_text("old\n", encoding="utf-8")
    workspace = await service.register_workspace({"workspace_name": "demo", "workspace_root": str(tmp_path)})
    service.workspaces[workspace["id"]].approved = True
    change = await service.write(workspace["id"], "app.py", "new\n")
    assert source.read_text(encoding="utf-8") == "new\n"
    assert "-old" in change["diff"] and "+new" in change["diff"]
    await service.rollback(workspace["id"], change["snapshot_id"])
    assert source.read_text(encoding="utf-8") == "old\n"
    with pytest.raises(HTTPException, match="escapes"):
        await service.read_file(workspace["id"], "../outside.txt")
    (tmp_path / ".env").write_text("SECRET=x", encoding="utf-8")
    with pytest.raises(HTTPException, match="Protected files"):
        await service.read_file(workspace["id"], ".env")


@pytest.mark.asyncio
async def test_campaign_command_gate_and_git_push(monkeypatch, tmp_path: Path):
    service = IDEService()
    monkeypatch.setattr(service, "posture", lambda: async_value({"active_tier": "campaign", "ide_enabled": True, "kill_switch_active": False}))
    allow_ide(monkeypatch, service)
    monkeypatch.setattr(service, "event", noop_event)
    workspace = await service.register_workspace({"workspace_name": "demo", "workspace_root": str(tmp_path)})
    service.workspaces[workspace["id"]].approved = True
    with pytest.raises(HTTPException, match="not allowlisted"):
        await service.run_command(workspace["id"], "powershell Get-ChildItem")
    with pytest.raises(HTTPException, match="disabled by default"):
        await service.git(workspace["id"], "push", approval=True)


async def async_value(value):
    return value


async def noop_event(*args, **kwargs):
    return "evt_test"


def allow_ide(monkeypatch, service):
    monkeypatch.setattr(service, "permission_config", lambda: async_value({
        "enabled": True, "file_read": True, "file_search": True, "file_patch": True,
        "file_delete": True, "diagnostics": True, "terminal_approved_only": True,
        "git_status": True, "git_diff": True, "git_branch_create": True, "git_commit": True,
    }))
