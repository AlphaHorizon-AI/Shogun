"""Native-tool surface for the protected Enterprise Transformation Architect."""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from shogun.services import native_skills
from shogun.services.tool_gate import TOOL_RISK_REGISTRY

TOOL_RISKS = {
    "transformation_profiles_list": "low",
    "transformation_profiles_get": "low",
    "transformation_profiles_propose": "medium",
    "transformation_profiles_validate": "medium",
    "transformation_profiles_promote": "high",
    "transformation_profiles_rollback": "high",
}


def _tool_map() -> dict[str, dict]:
    return {
        item["function"]["name"]: item
        for item in native_skills.NATIVE_TOOLS
        if item["function"]["name"].startswith("transformation_profiles_")
    }


def _db() -> SimpleNamespace:
    return SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())


def test_profile_tools_declare_governed_risks_and_no_client_trust_flags() -> None:
    tools = _tool_map()
    assert set(tools) == set(TOOL_RISKS)

    forbidden = {
        "actor",
        "origin",
        "approved",
        "passed",
        "validation_passed",
        "validation_score",
        "skip_validation",
        "active",
    }
    for name, risk in TOOL_RISKS.items():
        assert tools[name]["risk"] == risk
        assert tools[name]["category"] == "transformation_profiles"
        assert TOOL_RISK_REGISTRY[name] == {
            "risk": risk,
            "category": "transformation_profiles",
        }
        properties = tools[name]["function"]["parameters"]["properties"]
        assert forbidden.isdisjoint(properties)

    validation = tools["transformation_profiles_validate"]["function"]["parameters"]
    assert set(validation["required"]) == {
        "version_id",
        "positive_fixtures",
        "negative_fixtures",
    }


@pytest.mark.asyncio
async def test_profile_read_tools_dispatch_through_registry(monkeypatch) -> None:
    calls: dict[str, object] = {}

    class FakeRegistry:
        def __init__(self, session):
            calls["session"] = session

        async def list_profiles(self, **filters):
            calls["filters"] = filters
            return [{"profile_id": "d365_products_v1", "lifecycle": "candidate"}]

        async def get_profile(self, profile_id):
            calls["profile_id"] = profile_id
            return SimpleNamespace(profile_key=profile_id)

        async def profile_data(self, profile, *, include_versions):
            calls["include_versions"] = include_versions
            return {"profile_id": profile.profile_key, "versions": []}

    monkeypatch.setattr(
        "shogun.services.transformation_profile_registry.TransformationProfileRegistryService",
        FakeRegistry,
    )
    db = _db()

    listed = json.loads(
        await native_skills.execute_native_tool(
            "transformation_profiles_list",
            {"lifecycle": "candidate", "platform": "D365 Finance"},
            db,
        )
    )
    assert listed["status"] == "success"
    assert listed["total"] == 1
    assert calls["filters"] == {
        "lifecycle": "candidate",
        "platform": "D365 Finance",
        "include_deleted": False,
    }

    fetched = json.loads(
        await native_skills.execute_native_tool(
            "transformation_profiles_get",
            {"profile_id": "d365_products_v1"},
            db,
        )
    )
    assert fetched["profile"]["profile_id"] == "d365_products_v1"
    assert calls["include_versions"] is True
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_propose_and_validate_force_architect_provenance(monkeypatch) -> None:
    captured: dict[str, object] = {}
    candidate_version = SimpleNamespace(id=uuid.uuid4(), status="candidate")
    validated_version = SimpleNamespace(id=uuid.uuid4(), status="validated")

    class FakeRegistry:
        def __init__(self, _session):
            pass

        async def create_candidate(self, body):
            captured["candidate"] = body
            return candidate_version

        async def validate_candidate(self, version_id, evidence):
            captured["version_id"] = version_id
            captured["evidence"] = evidence
            return validated_version

        async def version_data(self, version):
            return {"id": str(version.id), "status": version.status}

    monkeypatch.setattr(
        "shogun.services.transformation_profile_registry.TransformationProfileRegistryService",
        FakeRegistry,
    )
    db = _db()

    proposed = json.loads(
        await native_skills.execute_native_tool(
            "transformation_profiles_propose",
            {
                "profile_id": "tenant_items_v1",
                "display_name": "Tenant items",
                "adapter_id": "canonical_entity_map_v1",
                "definition": {
                    "id": "tenant_items_v1",
                    "adapter": "canonical_entity_map_v1",
                },
                # These untrusted fields are deliberately ignored by the helper.
                "actor": "attacker",
                "origin": "operator",
                "active": True,
            },
            db,
        )
    )
    candidate = captured["candidate"]
    assert candidate.actor == native_skills.ENTERPRISE_TRANSFORMATION_ARCHITECT_ACTOR
    assert candidate.origin == "skillopt"
    assert proposed["origin"] == "skillopt"

    version_id = uuid.uuid4()
    validated = json.loads(
        await native_skills.execute_native_tool(
            "transformation_profiles_validate",
            {
                "version_id": str(version_id),
                "positive_fixtures": [{"name": "valid", "payload": {"items": []}}],
                "negative_fixtures": [{"name": "wrong shape", "payload": {}}],
                "actor": "attacker",
                "passed": True,
                "validation_score": 1.0,
            },
            db,
        )
    )
    evidence = captured["evidence"]
    assert captured["version_id"] == version_id
    assert evidence.actor == native_skills.ENTERPRISE_TRANSFORMATION_ARCHITECT_ACTOR
    assert not hasattr(evidence, "passed")
    assert not hasattr(evidence, "validation_score")
    assert validated["validation_source"] == "server_executed_fixtures"
    assert db.commit.await_count == 2

@pytest.mark.asyncio
async def test_promote_and_rollback_keep_registry_lifecycle_and_fixed_actor(monkeypatch) -> None:
    captured: dict[str, object] = {}
    promoted_version = SimpleNamespace(id=uuid.uuid4(), status="active")
    rollback_version = SimpleNamespace(id=uuid.uuid4(), status="active")

    class FakeRegistry:
        def __init__(self, _session):
            pass

        async def promote(self, version_id, *, actor):
            captured["promote"] = (version_id, actor)
            return promoted_version

        async def rollback(self, profile_id, *, target_version, actor):
            captured["rollback"] = (profile_id, target_version, actor)
            return rollback_version

        async def version_data(self, version):
            return {"id": str(version.id), "status": version.status}

    monkeypatch.setattr(
        "shogun.services.transformation_profile_registry.TransformationProfileRegistryService",
        FakeRegistry,
    )
    db = _db()
    actor = native_skills.ENTERPRISE_TRANSFORMATION_ARCHITECT_ACTOR

    promoted_id = uuid.uuid4()
    promoted = json.loads(
        await native_skills.execute_native_tool(
            "transformation_profiles_promote",
            {"version_id": str(promoted_id), "actor": "attacker", "skip_validation": True},
            db,
        )
    )
    assert promoted["status"] == "success"
    assert captured["promote"] == (promoted_id, actor)

    rolled_back = json.loads(
        await native_skills.execute_native_tool(
            "transformation_profiles_rollback",
            {
                "profile_id": "tenant_items_v1",
                "target_version": 2,
                "actor": "attacker",
                "approved": True,
            },
            db,
        )
    )
    assert rolled_back["status"] == "success"
    assert captured["rollback"] == ("tenant_items_v1", 2, actor)
    assert db.commit.await_count == 2
