from __future__ import annotations

import uuid
from importlib import import_module
from types import SimpleNamespace

import pytest

from shogun.api.security import (
    _active_toolgate_context,
    _ensure_standalone_custom_toolgate_context,
    _get_agent_posture,
    select_active_security_posture,
)
from shogun.schemas.security import SecurityPostureSelectRequest


class _Result:
    def __init__(self, agent):
        self._agent = agent

    def scalar_one_or_none(self):
        return self._agent


class _Session:
    def __init__(self, agent, policy):
        self._agent = agent
        self._policy = policy

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def execute(self, _query):
        return _Result(self._agent)

    async def get(self, _model, policy_id):
        assert policy_id == self._policy.id
        return self._policy

    async def commit(self):
        return None


class _ScalarResult:
    def __init__(self, *, one=None, values=None):
        self._one = one
        self._values = list(values or [])

    def scalar_one_or_none(self):
        return self._one

    def scalars(self):
        return self

    def first(self):
        return self._values[0] if self._values else None

    def all(self):
        return self._values


class _ToolGateForkSession:
    def __init__(self, agent, built_in):
        self.agent = agent
        self.built_in = built_in
        self.added = []
        self._results = [
            _ScalarResult(one=agent),
            _ScalarResult(values=[built_in]),
            _ScalarResult(values=[]),
        ]

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def execute(self, _query):
        return self._results.pop(0)

    async def get(self, _model, _record_id):
        return None

    def add(self, record):
        self.added.append(record)

    async def flush(self):
        for record in self.added:
            if record.id is None:
                record.id = uuid.uuid4()

    async def commit(self):
        return None


@pytest.mark.asyncio
async def test_posture_includes_assigned_custom_policy(monkeypatch):
    policy_id = uuid.uuid4()
    agent = SimpleNamespace(
        bushido_settings={"security_posture": {"active_tier": "guarded"}},
        security_policy_id=policy_id,
    )
    policy = SimpleNamespace(
        id=policy_id,
        name="Michael Custom Policy",
        is_builtin=False,
        tier="campaign",
        permissions={
            "filesystem": {"mode": "full"},
            "shell": {"enabled": True},
            "subagents": {"max_active": 9},
        },
    )

    engine_module = import_module("shogun.db.engine")
    monkeypatch.setattr(engine_module, "async_session_factory", lambda: _Session(agent, policy))

    posture = await _get_agent_posture()

    assert posture["active_tier"] == "campaign"
    assert posture["active_policy_id"] == policy_id
    assert posture["active_policy_name"] == "Michael Custom Policy"
    assert posture["active_policy_is_builtin"] is False
    assert posture["active_policy_tier"] == "campaign"
    assert posture["filesystem_mode"] == "full"
    assert posture["shell_enabled"] is True
    assert posture["max_active_subagents"] == 9


@pytest.mark.asyncio
async def test_toolgate_uses_custom_policy_identity_and_base_tier(monkeypatch):
    from shogun.api import security

    monkeypatch.setattr(
        security,
        "_get_agent_posture",
        lambda: _async_value(
            {
                "active_tier": "guarded",
                "active_policy_id": "custom-id",
                "active_policy_name": "Laptop Custom",
                "active_policy_is_builtin": False,
                "active_policy_tier": "campaign",
                "active_campaign_preset": None,
            }
        ),
    )

    _, _, mode, scope = await _active_toolgate_context()

    assert mode == "campaign"
    assert scope["key"] == "policy:custom-id"
    assert scope["label"] == "Laptop Custom"


@pytest.mark.asyncio
async def test_standalone_toolgate_edit_forks_and_activates_builtin_posture(monkeypatch):
    from shogun.api import security
    from shogun.services import event_logger, tool_gate

    agent = SimpleNamespace(
        bushido_settings={"security_posture": {"active_tier": "tactical"}},
        security_policy_id=None,
    )
    built_in = SimpleNamespace(
        permissions={"network": {"mode": "allowlist", "allowed_domains": ["example.com"]}},
        kill_switch_enabled=True,
        dry_run_supported=True,
    )
    session = _ToolGateForkSession(agent, built_in)
    calls = 0

    async def context():
        nonlocal calls
        calls += 1
        if calls == 1:
            return (
                {"active_tier": "tactical"},
                None,
                "standard",
                {
                    "key": "tier:tactical",
                    "kind": "tier",
                    "label": "TACTICAL",
                    "base_tier": "tactical",
                    "policy_id": None,
                },
            )
        policy = session.added[0]
        return (
            {"active_tier": "tactical", "active_policy_id": policy.id},
            None,
            "standard",
            {
                "key": f"policy:{policy.id}",
                "kind": "custom_policy",
                "label": policy.name,
                "base_tier": "tactical",
                "policy_id": str(policy.id),
            },
        )

    cloned = []

    async def no_audit(*_args, **_kwargs):
        return None

    monkeypatch.setattr(security, "_toolgate_authority", lambda: {"editable": True})
    monkeypatch.setattr(security, "_active_toolgate_context", context)
    monkeypatch.setattr(
        import_module("shogun.db.engine"),
        "async_session_factory",
        lambda: session,
    )
    monkeypatch.setattr(
        tool_gate,
        "clone_local_toolgate_scope",
        lambda source, target: cloned.append((source, target)),
    )
    monkeypatch.setattr(event_logger.EventLogger, "emit_policy_event", no_audit)

    posture, _, _, scope, created = await _ensure_standalone_custom_toolgate_context()

    policy = session.added[0]
    assert created == {"id": str(policy.id), "name": "Custom Tactical", "tier": "tactical"}
    assert agent.security_policy_id == policy.id
    assert policy.is_builtin is False
    assert policy.permissions["network"]["allowed_domains"] == ["example.com"]
    assert posture["active_policy_id"] == policy.id
    assert scope["kind"] == "custom_policy"
    assert cloned == [("tier:tactical", f"policy:{policy.id}")]


@pytest.mark.asyncio
async def test_select_custom_posture_assigns_policy_and_base_tier(monkeypatch):
    policy_id = uuid.uuid4()
    agent = SimpleNamespace(
        bushido_settings={"security_posture": {"active_tier": "guarded"}},
        security_policy_id=None,
    )
    policy = SimpleNamespace(
        id=policy_id,
        name="Laptop Custom",
        is_builtin=False,
        is_deleted=False,
        tier="campaign",
        permissions={"network": {"mode": "full"}},
    )

    engine_module = import_module("shogun.db.engine")
    monkeypatch.setattr(engine_module, "async_session_factory", lambda: _Session(agent, policy))

    response = await select_active_security_posture(
        SecurityPostureSelectRequest(policy_id=policy_id, confirmed=True)
    )

    assert agent.security_policy_id == policy_id
    assert agent.bushido_settings["security_posture"]["active_tier"] == "campaign"
    assert response.data["active_policy_id"] == policy_id
    assert response.data["active_policy_name"] == "Laptop Custom"
    assert response.data["network_mode"] == "full"


@pytest.mark.asyncio
async def test_select_builtin_posture_clears_custom_assignment(monkeypatch):
    policy_id = uuid.uuid4()
    agent = SimpleNamespace(
        bushido_settings={
            "custom_permissions": {"network": {"mode": "full"}},
            "security_posture": {
                "active_tier": "campaign",
                "active_policy_id": str(policy_id),
                "active_policy_name": "Stale Custom",
            },
        },
        security_policy_id=policy_id,
    )
    policy = SimpleNamespace(
        id=policy_id,
        name="Stale Custom",
        is_builtin=False,
        is_deleted=False,
        tier="campaign",
        permissions={},
    )

    engine_module = import_module("shogun.db.engine")
    monkeypatch.setattr(engine_module, "async_session_factory", lambda: _Session(agent, policy))

    response = await select_active_security_posture(
        SecurityPostureSelectRequest(tier="guarded")
    )

    stored = agent.bushido_settings["security_posture"]
    assert agent.security_policy_id is None
    assert "custom_permissions" not in agent.bushido_settings
    assert "active_policy_id" not in stored
    assert stored["active_tier"] == "guarded"
    assert response.data["active_policy_id"] is None
    assert response.data["active_tier"] == "guarded"


async def _async_value(value):
    return value
