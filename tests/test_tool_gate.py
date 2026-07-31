import json

import pytest

from shogun.services.tool_gate import (
    GateAction,
    apply_gensui_advanced_controls,
    apply_gensui_overrides,
    calculate_capability_risk,
    check_tool_access,
    get_gensui_overrides,
    get_local_advanced_controls,
    get_local_filesystem_controls,
    get_local_network_controls,
    get_local_overrides,
    get_toolgate_scope,
    set_local_advanced_controls,
    set_local_filesystem_controls,
    set_local_network_controls,
    set_local_overrides,
)


@pytest.fixture(autouse=True)
def restore_toolgate_overrides(tmp_path, monkeypatch):
    from shogun.services import tool_gate

    original_scopes = {
        scope: dict(overrides)
        for scope, overrides in tool_gate._local_override_scopes.items()
    }
    original_advanced_scopes = {
        scope: dict(config)
        for scope, config in tool_gate._local_advanced_scopes.items()
    }
    original_detail_scopes = {
        scope: {tool: dict(detail) for tool, detail in tools.items()}
        for scope, tools in tool_gate._local_detail_scopes.items()
    }
    original_filesystem_scopes = {
        scope: dict(config)
        for scope, config in tool_gate._local_filesystem_scopes.items()
    }
    original_network_scopes = {
        scope: dict(config)
        for scope, config in tool_gate._local_network_scopes.items()
    }
    monkeypatch.setattr(tool_gate, "_LOCAL_OVERRIDES_PATH", tmp_path / "toolgate_overrides.json")
    tool_gate._local_override_scopes = {}
    tool_gate._local_advanced_scopes = {}
    tool_gate._local_detail_scopes = {}
    tool_gate._local_filesystem_scopes = {}
    tool_gate._local_network_scopes = {}
    apply_gensui_overrides({})
    apply_gensui_advanced_controls({})
    yield
    tool_gate._local_override_scopes = original_scopes
    tool_gate._local_advanced_scopes = original_advanced_scopes
    tool_gate._local_detail_scopes = original_detail_scopes
    tool_gate._local_filesystem_scopes = original_filesystem_scopes
    tool_gate._local_network_scopes = original_network_scopes
    apply_gensui_overrides({})
    apply_gensui_advanced_controls({})


@pytest.mark.asyncio
async def test_campaign_mode_allows_high_risk_email_without_confirmation():
    decision = await check_tool_access(
        mode="campaign",
        tool_name="send_email",
        args={"to_address": "person@example.com", "subject": "Hi", "body": "Hello"},
    )

    assert decision.action == GateAction.ALLOW


@pytest.mark.asyncio
async def test_campaign_preset_override_can_still_confirm_email():
    decision = await check_tool_access(
        mode="campaign",
        tool_name="send_email",
        args={"to_address": "person@example.com", "subject": "Hi", "body": "Hello"},
        campaign_preset={
            "name": "Confirmed comms",
            "tool_overrides": {"send_email": "confirm"},
        },
    )

    assert decision.action == GateAction.CONFIRM


@pytest.mark.asyncio
async def test_campaign_cannot_relax_gensui_block():
    apply_gensui_overrides({"send_email": "block"})

    decision = await check_tool_access(
        mode="campaign",
        tool_name="send_email",
        args={"to_address": "person@example.com", "subject": "Hi", "body": "Hello"},
        campaign_preset={
            "name": "Open communications",
            "tool_overrides": {"send_email": "allow"},
        },
    )

    assert decision.action == GateAction.BLOCK
    assert "gensui" in decision.reason


@pytest.mark.asyncio
async def test_local_policy_can_tighten_gensui_allow():
    apply_gensui_overrides({"send_email": "allow"})
    set_local_overrides({"send_email": "confirm"})

    decision = await check_tool_access(
        mode="campaign",
        tool_name="send_email",
        args={"to_address": "person@example.com", "subject": "Hi", "body": "Hello"},
    )

    assert decision.action == GateAction.CONFIRM
    assert "local" in decision.reason


@pytest.mark.asyncio
async def test_local_overrides_are_isolated_by_effective_policy_scope():
    set_local_overrides({"send_email": "block"}, "policy:custom-a")
    set_local_overrides({"send_email": "allow"}, "tier:campaign")

    custom_decision = await check_tool_access(
        mode="campaign",
        tool_name="send_email",
        args={},
        local_scope="policy:custom-a",
    )
    tier_decision = await check_tool_access(
        mode="campaign",
        tool_name="send_email",
        args={},
        local_scope="tier:campaign",
    )

    assert custom_decision.action == GateAction.BLOCK
    assert tier_decision.action == GateAction.ALLOW
    assert get_local_overrides("policy:custom-a") == {"send_email": "block"}


def test_shared_filesystem_controls_are_persisted_and_isolated_by_scope():
    from shogun.services import tool_gate

    set_local_filesystem_controls(
        {
            "enabled": True,
            "folders": [
                {
                    "id": "input",
                    "path": "input",
                    "kind": "internal",
                    "read": True,
                    "write": False,
                    "create": False,
                    "delete": False,
                },
            ],
        },
        "tier:guarded",
    )

    assert get_local_filesystem_controls("tier:guarded")["folders"][0]["read"] is True
    assert get_local_filesystem_controls("tier:campaign") == {"enabled": False, "folders": []}
    payload = json.loads(tool_gate._LOCAL_OVERRIDES_PATH.read_text(encoding="utf-8"))
    assert payload["version"] == 6
    assert payload["filesystem_scopes"]["tier:guarded"]["folders"][0]["path"] == "input"


def test_legacy_per_tool_folders_migrate_to_one_shared_policy():
    from shogun.services.tool_gate import _legacy_filesystem_controls

    migrated = _legacy_filesystem_controls(
        {
            "workspace_read": {
                "allowed_internal_paths": ["input"],
                "allowed_network_paths": [],
            },
            "workspace_write": {
                "allowed_internal_paths": ["output"],
                "allowed_network_paths": [r"\\server\generated"],
            },
            "workspace_delete": {
                "allowed_internal_paths": ["output"],
                "allowed_network_paths": [],
            },
        }
    )

    folders = {(folder["kind"], folder["path"]): folder for folder in migrated["folders"]}
    assert migrated["enabled"] is True
    assert folders[("internal", "input")]["read"] is True
    assert folders[("internal", "output")]["write"] is True
    assert folders[("internal", "output")]["create"] is True
    assert folders[("internal", "output")]["delete"] is True
    assert folders[("network", r"\\server\generated")]["create"] is True


@pytest.mark.asyncio
async def test_shared_filesystem_controls_enforce_operations_per_folder(tmp_path, monkeypatch):
    from shogun.config import settings

    workspace = tmp_path / "workspace"
    (workspace / "input").mkdir(parents=True)
    (workspace / "input" / "report.txt").write_text("report", encoding="utf-8")
    (workspace / "output").mkdir()
    monkeypatch.setattr(settings, "workspace_path", workspace)
    set_local_filesystem_controls(
        {
            "enabled": True,
            "folders": [
                {
                    "path": "input",
                    "kind": "internal",
                    "read": True,
                    "write": False,
                    "create": False,
                    "delete": False,
                },
                {
                    "path": "output",
                    "kind": "internal",
                    "read": True,
                    "write": True,
                    "create": True,
                    "delete": False,
                },
            ],
        },
        "tier:tactical",
    )

    read_allowed = await check_tool_access(
        mode="standard",
        tool_name="workspace_read",
        args={"path": "input/report.txt"},
        local_scope="tier:tactical",
    )
    write_blocked = await check_tool_access(
        mode="standard",
        tool_name="workspace_write",
        args={"path": "input/report.txt"},
        local_scope="tier:tactical",
    )
    create_allowed = await check_tool_access(
        mode="standard",
        tool_name="workspace_write",
        args={"path": "output/new-report.txt"},
        local_scope="tier:tactical",
    )
    delete_blocked = await check_tool_access(
        mode="standard",
        tool_name="workspace_delete",
        args={"path": "input/report.txt"},
        local_scope="tier:tactical",
    )

    assert read_allowed.action == GateAction.ALLOW
    assert write_blocked.action == GateAction.BLOCK
    assert write_blocked.parameter_flags == ["filesystem_permission_denied:write:$.path"]
    assert create_allowed.action == GateAction.ALLOW
    assert delete_blocked.action == GateAction.BLOCK
    assert delete_blocked.parameter_flags == ["filesystem_permission_denied:delete:$.path"]


@pytest.mark.asyncio
async def test_file_transform_requires_input_read_and_output_create(tmp_path, monkeypatch):
    from shogun.config import settings

    workspace = tmp_path / "workspace"
    input_folder = workspace / "input"
    input_folder.mkdir(parents=True)
    source = input_folder / "report.csv"
    source.write_text("name\nShogun\n", encoding="utf-8")
    monkeypatch.setattr(settings, "workspace_path", workspace)
    set_local_filesystem_controls(
        {
            "enabled": True,
            "folders": [
                {
                    "path": "input",
                    "kind": "internal",
                    "read": True,
                    "write": False,
                    "create": False,
                    "delete": False,
                },
                {
                    "path": ".",
                    "kind": "internal",
                    "read": False,
                    "write": False,
                    "create": False,
                    "delete": False,
                },
            ],
        },
        "tier:tactical",
    )

    blocked = await check_tool_access(
        mode="standard",
        tool_name="file_transform",
        args={"path": str(source), "target_format": "json", "output_filename": "report.json"},
        local_scope="tier:tactical",
    )

    assert blocked.action == GateAction.BLOCK
    assert blocked.parameter_flags == [
        "filesystem_permission_denied:create:$.output_filename",
    ]


def test_shared_network_controls_are_persisted_and_isolated_by_scope():
    from shogun.services import tool_gate

    set_local_network_controls(
        {
            "enabled": True,
            "mode": "allowlist",
            "allowed_domains": ["*.openai.com", "*.*", "*.openai.com"],
        },
        "tier:guarded",
    )

    assert get_local_network_controls("tier:guarded") == {
        "enabled": True,
        "mode": "allowlist",
        "allowed_domains": ["*.openai.com", "*.*"],
    }
    assert get_local_network_controls("tier:campaign") == {
        "enabled": False,
        "mode": "allowlist",
        "allowed_domains": [],
    }
    payload = json.loads(tool_gate._LOCAL_OVERRIDES_PATH.read_text(encoding="utf-8"))
    assert payload["version"] == 6
    assert payload["network_scopes"]["tier:guarded"]["allowed_domains"] == ["*.openai.com", "*.*"]


@pytest.mark.asyncio
async def test_network_allowlist_accepts_exact_and_wildcard_domains():
    set_local_network_controls(
        {
            "enabled": True,
            "mode": "allowlist",
            "allowed_domains": ["example.com", "*.openai.com"],
        },
        "tier:tactical",
    )

    exact = await check_tool_access(
        mode="standard",
        tool_name="browse_web",
        args={"url": "https://example.com/report"},
        local_scope="tier:tactical",
    )
    wildcard = await check_tool_access(
        mode="standard",
        tool_name="browse_web",
        args={"url": "https://api.openai.com/v1/models"},
        local_scope="tier:tactical",
    )
    blocked = await check_tool_access(
        mode="standard",
        tool_name="browse_web",
        args={"url": "https://not-allowed.test"},
        local_scope="tier:tactical",
    )

    assert exact.action == GateAction.ALLOW
    assert wildcard.action == GateAction.ALLOW
    assert blocked.action == GateAction.BLOCK
    assert blocked.parameter_flags == ["network_domain_not_allowlisted:not-allowed.test"]


@pytest.mark.asyncio
async def test_network_star_dot_star_allows_every_domain_and_disabled_blocks():
    set_local_network_controls(
        {"enabled": True, "mode": "allowlist", "allowed_domains": ["*.*"]},
        "tier:tactical",
    )
    allowed = await check_tool_access(
        mode="standard",
        tool_name="browse_web",
        args={"url": "https://anywhere.example/path"},
        local_scope="tier:tactical",
    )

    set_local_network_controls(
        {"enabled": True, "mode": "disabled", "allowed_domains": []},
        "tier:tactical",
    )
    disabled = await check_tool_access(
        mode="standard",
        tool_name="browse_web",
        args={"url": "https://example.com"},
        local_scope="tier:tactical",
    )

    assert allowed.action == GateAction.ALLOW
    assert disabled.action == GateAction.BLOCK
    assert disabled.parameter_flags == ["network_access_disabled"]

def test_custom_policy_gets_stable_scope_and_inherits_its_base_tier():
    scope = get_toolgate_scope(
        {
            "active_tier": "guarded",
            "active_policy_id": "policy-id",
            "active_policy_name": "Laptop Custom",
            "active_policy_is_builtin": False,
            "active_policy_tier": "campaign",
        }
    )

    assert scope == {
        "key": "policy:policy-id",
        "kind": "custom_policy",
        "label": "Laptop Custom",
        "base_tier": "campaign",
        "policy_id": "policy-id",
    }


def test_capability_risk_index_reflects_policy_exposure():
    restrictive = {
        "filesystem": {"mode": "scoped", "allow_home_access": False},
        "network": {"mode": "disabled"},
        "shell": {"enabled": False},
        "skills": {"require_approval": True},
    }
    permissive = {
        "filesystem": {"mode": "full", "allow_home_access": True, "allow_arbitrary_paths": True},
        "network": {"mode": "full", "allow_arbitrary_requests": True},
        "shell": {"enabled": True},
        "skills": {"require_approval": False, "allow_auto_install": True, "allow_untrusted": True},
    }

    assert calculate_capability_risk(restrictive) == 0
    assert calculate_capability_risk(permissive) == 95


@pytest.mark.asyncio
async def test_parameter_safety_cannot_be_relaxed_by_explicit_allow():
    apply_gensui_overrides({"desktop_type": "allow"})

    decision = await check_tool_access(
        mode="ronin_desktop",
        tool_name="desktop_type",
        args={"text": "api_key=secret"},
    )

    assert decision.action == GateAction.CONFIRM
    assert "credential" in decision.reason.lower()


@pytest.mark.asyncio
@pytest.mark.parametrize("tool_name", ["send_telegram_message", "channel_send"])
async def test_channel_message_content_is_not_treated_as_a_destructive_command(tool_name):
    decision = await check_tool_access(
        mode="campaign",
        tool_name=tool_name,
        args={
            "message": (
                "News update: the operator issued a shutdown, halt, and kill "
                "order for the affected service."
            )
        },
    )

    assert decision.action == GateAction.ALLOW
    assert not any(
        flag.startswith("destructive_command:")
        for flag in decision.parameter_flags
    )


@pytest.mark.asyncio
async def test_non_channel_tool_still_blocks_destructive_command_content():
    decision = await check_tool_access(
        mode="campaign",
        tool_name="mcp_call_tool",
        args={"command": "shutdown now"},
    )

    assert decision.action == GateAction.BLOCK
    assert any(
        flag.startswith("destructive_command:")
        for flag in decision.parameter_flags
    )


@pytest.mark.asyncio
async def test_advanced_phrase_rule_confirms_nested_tool_argument():
    set_local_advanced_controls(
        {
            "enabled": True,
            "rules": [
                {
                    "id": "confidential",
                    "label": "Confidential data",
                    "pattern": "confidential",
                    "match_type": "word",
                    "action": "confirm",
                    "tools": ["send_email"],
                }
            ],
        },
        "policy:laptop",
    )

    decision = await check_tool_access(
        mode="campaign",
        tool_name="send_email",
        args={"message": {"body": "This is CONFIDENTIAL material."}},
        local_scope="policy:laptop",
    )

    assert decision.action == GateAction.CONFIRM
    assert "Confidential data" in decision.reason
    assert any(flag.endswith("$.message.body") for flag in decision.parameter_flags)
    assert get_local_advanced_controls("policy:laptop")["enabled"] is True


@pytest.mark.asyncio
async def test_advanced_rule_only_applies_to_targeted_tools():
    set_local_advanced_controls(
        {
            "enabled": True,
            "rules": [
                {
                    "id": "internal",
                    "pattern": "internal only",
                    "action": "block",
                    "tools": ["send_email"],
                }
            ],
        },
        "tier:campaign",
    )

    decision = await check_tool_access(
        mode="campaign",
        tool_name="store_memory",
        args={"content": "internal only"},
        local_scope="tier:campaign",
    )

    assert decision.action == GateAction.ALLOW


@pytest.mark.asyncio
async def test_gensui_advanced_block_cannot_be_relaxed_by_local_confirm():
    set_local_advanced_controls(
        {
            "enabled": True,
            "rules": [{"id": "local", "pattern": "restricted", "action": "confirm"}],
        }
    )
    apply_gensui_advanced_controls(
        {
            "enabled": True,
            "rules": [{"id": "central", "pattern": "restricted", "action": "block"}],
        }
    )

    decision = await check_tool_access(
        mode="campaign",
        tool_name="send_email",
        args={"body": "restricted"},
    )

    assert decision.action == GateAction.BLOCK
    assert "gensui" in decision.reason


@pytest.mark.asyncio
async def test_cached_gensui_policy_is_reapplied_for_offline_startup(tmp_path):
    from shogun.services.gensui_client import GensuiClient

    cache_path = tmp_path / "gensui_membership.json"
    cache_path.write_text(
        json.dumps(
            {
                "shogun_id": "managed-shogun",
                "effective_posture": {
                    "tool_overrides": {"send_email": "block"},
                    "advanced_controls": {
                        "enabled": True,
                        "rules": [
                            {
                                "id": "central-secret",
                                "pattern": "fleet secret",
                                "action": "block",
                            }
                        ],
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    client = GensuiClient.__new__(GensuiClient)
    client._cache_path = cache_path
    client._shogun_id = None
    client._effective_posture = None

    client._load_cache()

    assert client._shogun_id == "managed-shogun"
    assert client._effective_posture["tool_overrides"]["send_email"] == "block"
    assert get_gensui_overrides()["send_email"] == "block"

    decision = await check_tool_access(
        mode="campaign",
        tool_name="send_email",
        args={"body": "fleet secret"},
    )
    assert decision.action == GateAction.BLOCK
    assert "gensui" in decision.reason
