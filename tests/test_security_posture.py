from __future__ import annotations

import uuid
from importlib import import_module
from types import SimpleNamespace

import pytest

from shogun.api.security import _active_toolgate_context, _get_agent_posture


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
    )

    engine_module = import_module("shogun.db.engine")
    monkeypatch.setattr(engine_module, "async_session_factory", lambda: _Session(agent, policy))

    posture = await _get_agent_posture()

    assert posture["active_tier"] == "guarded"
    assert posture["active_policy_id"] == policy_id
    assert posture["active_policy_name"] == "Michael Custom Policy"
    assert posture["active_policy_is_builtin"] is False
    assert posture["active_policy_tier"] == "campaign"


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


async def _async_value(value):
    return value
