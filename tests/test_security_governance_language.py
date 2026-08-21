"""Regression tests for supportable security and governance terminology."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_security_policy_scopes_red_teaming_and_avoids_voluntary_response_sla() -> None:
    policy = _text("SECURITY.md")

    assert "Security verification and AI-assisted red teaming" in policy
    assert "supplements rather than replaces" in policy
    assert "guarantees security" in policy
    assert "within three business days" not in policy
    assert "three business days" not in policy
    assert "aims to acknowledge and triage security reports promptly" in policy
    assert "no specific customer-support response time is promised" in " ".join(
        policy.lower().split()
    )
    assert "may include the following steps as appropriate" in policy


def test_audit_components_do_not_claim_regulatory_compliance_or_immutable_storage() -> None:
    current_surfaces = "\n".join(
        _text(path)
        for path in (
            "shogun/services/event_logger.py",
            "shogun/services/immutable_audit.py",
            "shogun/api/logs.py",
            "shogun/schemas/logs.py",
            "shogun/db/models/execution_event.py",
            "gensui/services/fleet_audit_service.py",
            "gensui/api/fleet_audit.py",
            "gensui/frontend/src/pages/Guide.tsx",
            "gensui/frontend/src/pages/FleetAudit.tsx",
            "Knowledge Item/immutable_audit_log.md",
            "frontend/src/pages/Ronin.tsx",
            "shogun/ronin/core/audit_logger.py",
            "shogun/services/mado_service.py",
            "shogun/api/kaizen.py",
        )
    ).lower()

    for claim in (
        "ai act compliant",
        "nis2/soc2-compliant",
        "compliance-ready",
        "compliance grade",
        "tamper-resistant compliance evidence",
        "immutable audit chain (hmac-sha256)",
    ):
        assert claim not in current_surfaces

    assert "does not prove record completeness" in current_surfaces
    assert "not immutable storage" in current_surfaces
    assert "host/database administrators can still alter or remove storage" in current_surfaces
    assert "every action remains visible, verified, and audited" not in current_surfaces
    assert "visible, verified, and audited" not in current_surfaces
    assert "stop ALL Ronin activity and close all sessions" not in current_surfaces
    assert "Stop all Ronin Desktop Control immediately" not in current_surfaces
    assert "logging failures are reported" in current_surfaces
    assert "all actions are validated against torii posture and emitted as audit events" not in current_surfaces
    assert "constitutional governance is always enforced" not in current_surfaces


def test_gensui_locale_claims_are_present_and_old_overclaims_are_removed() -> None:
    locale_dir = ROOT / "gensui" / "frontend" / "src" / "i18n"
    locale_paths = sorted(locale_dir.glob("*.json"))
    assert len(locale_paths) == 14

    unsafe_values = {
        "HMAC-chained immutable event log",
        "Tamper-resistant record of every administrative action.",
        "Comprehensive runtime security architecture protecting every Shogun instance in the fleet.",
        (
            "NIS2/SOC2/EU AI Act compliance report. Shows fleet size, harakiri activations, "
            "posture changes, enrollment events, token revocations, and HMAC chain integrity."
        ),
        "Immutable Audit Chain (HMAC-SHA256)",
        (
            "Create → shown once. Rotate → invalidates old key, generates new. "
            "Revoke → permanently deactivates. All actions are audit-logged."
        ),
    }
    required_guide_keys = {
        "sec_audit_desc",
        "sec_security_desc",
        "sec_fleet_audit_desc",
        "card_injection_governance_desc",
        "card_audit_compliance_desc",
        "card_compliance_tab_desc",
        "security_architecture_desc",
        "security_toolgate_confirm_desc",
        "security_toolgate_audit_desc",
        "security_fleet_audit_full_desc",
        "security_immutable_chain",
        "security_immutable_chain_full_desc",
        "key_lifecycle_desc",
        "card_raw_log_tab_desc",
        "key_lifecycle_desc",
    }

    for path in locale_paths:
        pack = json.loads(path.read_text(encoding="utf-8"))
        assert pack["audit"]["subtitle"]
        assert pack["fleet_audit"]["subtitle"]
        assert required_guide_keys <= pack["guide"].keys()
        assert pack["guide"]["card_raw_log_tab_desc"] == (
            "Available audit records with action filtering. "
            "Displayed fields depend on captured events."
        )
        assert not (unsafe_values & set(pack["guide"].values())), path.name
        assert pack["audit"]["subtitle"] not in unsafe_values, path.name

    english = json.loads((locale_dir / "en.json").read_text(encoding="utf-8"))
    assert "does not determine compliance" in english["guide"]["card_compliance_tab_desc"]
    assert "do not prove completeness" in english["guide"]["card_audit_compliance_desc"]
    assert "do not prove completeness" in english["guide"]["security_immutable_chain_full_desc"]


def test_direct_chat_discloses_ai_agent_in_every_locale() -> None:
    assert "chat.ai_agent_disclosure" in _text("frontend/src/pages/Chat.tsx")

    locale_paths = sorted((ROOT / "frontend" / "src" / "i18n").glob("*.json"))
    assert len(locale_paths) == 15
    for path in locale_paths:
        pack = json.loads(path.read_text(encoding="utf-8"))
        assert pack["chat"]["ai_agent_disclosure"].strip(), path.name
        assert "do not capture every agent activity" in pack["setup"]["step2_explainer"]
        assert "requests cancellation of supported active work" in pack["dashboard"]["harakiri_desc"]
        assert "ALL SYSTEMS FROZEN" not in pack["topbar"]["harakiri_active"]


def test_setup_docs_describe_ten_steps_and_local_security_acknowledgement() -> None:
    readme = _text("README.md")
    setup_knowledge = _text("Knowledge Item/model_provider_setup.md")

    assert "ten-step Setup Wizard" in readme
    assert "9. Security and incident-reporting information" in readme
    assert "10. Configuration review and activation" in readme
    assert "nine-step Setup Wizard" not in readme
    assert "All setup screens are available" not in readme
    assert "canonical English" in readme

    assert "security_incident_acknowledged: Literal[True]" in setup_knowledge
    assert "API rejects an absent or\nfalse value" in setup_knowledge
    assert "security_incident_acknowledgement" in setup_knowledge
    assert "excluded from telemetry" in setup_knowledge
    assert "not evidence of a\nregulatory conformity assessment" in setup_knowledge


def test_readme_states_the_factual_model_boundary_without_an_ai_act_conclusion() -> None:
    readme = _text("README.md")

    assert "not itself an LLM, foundation model, or general-purpose AI (GPAI) model" in readme
    assert "outside the EU AI Act" not in readme


def test_setup_language_selector_discloses_canonical_english_fallback() -> None:
    locale_paths = sorted((ROOT / "frontend" / "src" / "i18n").glob("*.json"))
    assert len(locale_paths) == 15

    for path in locale_paths:
        pack = json.loads(path.read_text(encoding="utf-8"))
        explainer = pack["setup"]["step1_explainer"]
        assert "professionally translated" not in explainer.lower(), path.name
        assert "professionelt oversat" not in explainer.lower(), path.name
        assert "professionell übersetzt" not in explainer.lower(), path.name
        assert "traducidos profesionalmente" not in explainer.lower(), path.name
        assert "traduits professionnellement" not in explainer.lower(), path.name

    english = json.loads(
        (ROOT / "frontend" / "src" / "i18n" / "en.json").read_text(encoding="utf-8")
    )
    assert "canonical English" in english["setup"]["step1_explainer"]


def test_guide_describes_college_telemetry_as_explicit_opt_in() -> None:
    guide = _text("frontend/src/pages/Guide.tsx")

    assert "OpenClaw College ecosystem intelligence is" in guide
    assert "disabled by default" in guide
    assert "No event is queued or sent until a local administrator explicitly opts in" in guide
    assert "https://www.openclawcollege.com/api/v1/intelligence/events" in guide
    assert "security and incident-reporting acknowledgement is separate and is never sent" in guide
    assert "anonymous ecosystem benchmark sharing is enabled by default" not in guide
    assert "20 events from five anonymous installations" not in guide
    assert "retains raw telemetry for 31 days" not in guide
    assert "HTTPS delivery necessarily exposes network connection metadata" in guide
    assert "does not assert or control the recipient&apos;s retention" in guide
    assert "configured model, provider, and task identifiers are sent as text" in guide
    assert "truncated to 120, 80, and 80 characters" in guide
    assert "token, latency, and cost values are bucketed" in guide
    assert "do not enable College sharing if a configured model" in guide
    assert "coarse model-performance signals" not in guide


def test_installation_telemetry_is_described_as_pseudonymous() -> None:
    current_surfaces = "\n".join(
        _text(path)
        for path in (
            "frontend/src/App.tsx",
            "frontend/src/pages/PrivacyTelemetry.tsx",
            "install.bat",
            "install.sh",
            "Shogun-Server-Install.bat",
            "Shogun-Server-Install.sh",
        )
    )

    assert "anonymous installation" not in current_surfaces.casefold()
    assert "pseudonymous installation" in current_surfaces.casefold()


def test_guide_avoids_audit_completeness_and_framework_applicability_claims() -> None:
    guide = _text("frontend/src/pages/Guide.tsx")

    assert "full audit history of all governance changes" not in guide
    assert "which compliance frameworks apply" not in guide
    assert "manifest provides a complete history" not in guide
    assert "do not determine legal applicability or compliance" in guide
    assert "not a guaranteed complete deletion history" in guide


def test_localized_manual_disclaimer_preserves_accuracy_and_risk_boundary() -> None:
    locale_paths = sorted((ROOT / "frontend" / "src" / "i18n").glob("*.json"))
    assert len(locale_paths) == 15

    for path in locale_paths:
        disclaimer = json.loads(path.read_text(encoding="utf-8"))["guide"]["disclaimer_body"]
        assert "does not guarantee accuracy, completeness, reliability, or suitability" in disclaimer
        assert "operator's risk to the extent permitted by law" in disclaimer
        assert "No disclaimer limits rights or responsibilities" in disclaimer


def test_guide_describes_harakiri_as_a_bounded_fail_closed_control() -> None:
    guide = _text("frontend/src/pages/Guide.tsx")

    for absolute_claim in (
        "all active agent operations are immediately stopped",
        "full emergency stop for all sessions and agents",
        "Stops everything system-wide",
        "all agents are frozen",
        "ensures instant lockdown",
        "No data is lost",
        "provides instant global shutdown",
        "cannot be disabled, overridden, or circumvented",
        "It always triggers Harakiri",
        "Hard-coded, cannot be disabled",
    ):
        assert absolute_claim not in guide

    assert "blocks new governed operations" in guide
    assert "best-effort cancellation of supported active work" in guide
    assert "not a guarantee that every external process stops immediately" in guide
    assert "while the Komainu listener is running and receiving keyboard events" in guide
    assert "Ronin/Komainu is unavailable in Server mode" in guide


def test_runtime_help_and_remote_messages_use_bounded_ronin_language() -> None:
    surfaces = "\n".join(
        _text(path)
        for path in (
            "shogun/api/security.py",
            "shogun/bootstrap.py",
            "shogun/services/teams_service.py",
            "shogun/services/telegram_poller.py",
        )
    )

    assert "RONIN (open — all permissions" not in surfaces
    assert "kill switch disabled, maximum autonomy" not in surfaces
    assert "All agent activity is suspended" not in surfaces
    assert "All agent activity suspended" not in surfaces
    assert "emergency shutdown of all AI operations" not in surfaces
    assert "RONIN is not unrestricted" in surfaces
    assert "New governed agent operations are blocked" in surfaces
    assert "best-effort basis" in surfaces


def test_guide_scopes_shrine_to_governed_operations_not_host_networking() -> None:
    guide = _text("frontend/src/pages/Guide.tsx")

    assert "most restrictive built-in policy for governed agent operations" in guide
    assert "SHRINE is not a host or container network firewall" in guide
    assert "together with host-level containment" in guide
    assert "All external connections are blocked" not in guide
    assert "Every action requires explicit human approval" not in guide


def test_guide_describes_ronin_as_high_autonomy_with_enforced_gates() -> None:
    guide = _text("frontend/src/pages/Guide.tsx")

    for unsafe_claim in (
        "credential entry is ALLOWED with no gate",
        "download and install arbitrary software without asking",
        "admin escalation is enabled",
        "Everything allowed. 10 sessions. Admin escalation enabled",
        "every dangerous action is allowed WITHOUT operator approval",
        "No restrictions whatsoever",
        "zero oversight",
        "Human approval: None",
        "RONIN (unrestricted) mode",
        "Only available at TACTICAL tier or higher",
        "Ronin is desktop_limited",
        "Ronin is desktop_full. Native apps + shell",
        "Komainu is a hardware-level safety mechanism",
        "every application on your OS is classified",
        "execute OS-level commands",
        "Always blocked, no override",
    ):
        assert unsafe_claim not in guide

    assert "RONIN is the highest-autonomy built-in tier, not a removal of safety controls" in guide
    assert "credential entry and administrative escalation remain blocked" in guide
    assert "Office send, macros, and external Office actions retain approval gates" in guide
    assert "Ronin desktop control must be enabled separately" in guide
    assert "Human approval: High-risk gates" in guide
    assert "only the RONIN tier permits an operator to enable" in guide
    assert "unknown process defaults to RESTRICTED" in guide
    assert "software input listener" in guide
    assert "raw coordinates cannot prove the semantic effect" in guide
    assert "registry coverage and foreground detection must still be verified" in guide


def test_guide_scopes_ide_checkpoints_policy_and_secret_controls() -> None:
    guide = _text("frontend/src/pages/Guide.tsx")

    assert "no lost progress" not in guide
    assert "automatic SHA-256 snapshot" not in guide
    assert "Protected files" in guide and "are always blocked" not in guide
    assert "in-memory content restore point" in guide
    assert "may resume from its last valid checkpoint" in guide
    assert "Configured server-side policy and tool gates" in guide
    assert "not a guarantee that prompt injection" in guide
    assert "Environment variables, legacy configuration, plugins" in guide


def test_guide_scopes_constitution_toolgate_a2a_and_emergency_controls() -> None:
    guide = _text("frontend/src/pages/Guide.tsx")

    for unsupported_claim in (
        "Every proposed agent action is validated against the Constitution",
        "agents cannot bypass it",
        "all agent activity is instantly frozen",
        "All A2A messages are signed",
        "never exposed in the frontend",
        "no tool call can bypass ToolGate",
        "this stops the world",
        "access are all revoked",
        "External connections are severed",
        "outgoing API calls are all paused",
        "Workspace deletion removes all peer access immediately",
    ):
        assert unsupported_claim not in guide

    assert "Covered operations routed through the Kaizen constitutional validator" in guide
    assert "Custom plugins, integrations, and future execution paths" in guide
    assert "per-peer shared-secret HMAC" in guide
    assert "verify signing and peer authentication separately for every connector" in guide
    assert "This is not a network-isolation guarantee" in guide


def test_guide_describes_toolgate_modes_and_trace_limits_factually() -> None:
    guide = _text("frontend/src/pages/Guide.tsx")

    assert "All tool usage requires human confirmation" not in guide
    assert "Human approval: Critical only" not in guide
    assert "intercepts every native tool call" not in guide
    assert "low- and medium-risk calls are allowed by the risk default" in guide
    assert "risk default allows low-, medium-, and high-risk calls and blocks critical calls" in guide
    assert "registered and instrumented native-tool paths" in guide
    assert "Custom plugins and uninstrumented execution paths require separate coverage verification" in guide
    assert "Every chat turn generates" not in guide
    assert "full workflow reconstruction" not in guide.casefold()
    assert "supports partial workflow reconstruction" in guide
    assert "missing events or a missing trace are not proof" in guide


def test_guide_describes_the_actual_nexus_endpoint_card() -> None:
    guide = _text("frontend/src/pages/Guide.tsx")

    assert "A2A Endpoint Card (Top)" in guide
    assert "A2A name and inbound endpoint URL" in guide
    assert "The card does not display a public key" in guide
    assert "Displays your Shogun's unique ID and public key" not in guide
    assert "put your agent ID on the clipboard" not in guide


def test_guides_do_not_guarantee_complete_layer_or_fleet_enforcement() -> None:
    guide = _text("frontend/src/pages/Guide.tsx")
    gensui_guide = _text("gensui/frontend/src/pages/Guide.tsx")

    for unsupported_claim in (
        "self-improvement never violates",
        'cannot "optimize its way" past your rules',
        "no single failure can compromise the system",
        "An attacker would need to bypass all of these layers simultaneously",
        "Before any agent action is executed",
    ):
        assert unsupported_claim not in guide

    for unsupported_claim in (
        "suspends all active operations gracefully",
        "immediately kills all processes",
        "Every tool call passes through ToolGate",
        "automatically wraps all untrusted external content",
        "ensures fleet-wide policy consistency",
    ):
        assert unsupported_claim not in gensui_guide

    assert "Common-mode failures, configuration errors, uninstrumented paths" in guide
    assert "Custom plugins and execution paths require separate coverage verification" in gensui_guide
    assert "may retain a cached posture" in gensui_guide

    for path in sorted((ROOT / "gensui" / "frontend" / "src" / "i18n").glob("*.json")):
        pack = json.loads(path.read_text(encoding="utf-8"))["guide"]
        assert "best-effort cancellation" in pack["card_soft_freeze_desc"], path.name
        assert "does not guarantee" in pack["card_hard_stop_desc"], path.name
        assert "instrumented Shogun tool-execution paths" in pack["security_toolgate_full_desc"], path.name
        assert "does not eliminate prompt-injection risk" in pack["security_injection_full_desc"], path.name
        assert "may retain a cached posture" in pack["security_posture_push_full_desc"], path.name


def test_torii_emergency_copy_does_not_claim_safety_gates_are_removed() -> None:
    locale_paths = sorted((ROOT / "frontend" / "src" / "i18n").glob("*.json"))
    assert len(locale_paths) == 15

    for path in locale_paths:
        pack = json.loads(path.read_text(encoding="utf-8"))
        description = pack["torii"]["emergency_desc"]
        assert "removes safety gates" not in description.casefold(), path.name
        assert "kill switch tightens" in description.casefold(), path.name
        assert "ronin" in description.casefold(), path.name

        assert pack["torii"]["tier_ronin_desc"] == (
            "Highest governed autonomy. Critical blocks, approval, and verification gates remain."
        ), path.name
        explainer = pack["setup"]["ronin_explainer"]
        assert "optional desktop automation" in explainer, path.name
        assert "cannot infer every side effect from raw GUI coordinates" in explainer, path.name


def test_privacy_policy_template_requires_qualified_review() -> None:
    templates = _text("shogun/resources/flow_templates.json")
    assert "User rights (GDPR compliant)" not in templates
    assert "privacy-policy working document for qualified review" in templates
    assert "Do not claim the draft establishes GDPR compliance" in templates


@pytest.mark.asyncio
async def test_broken_audit_chain_schedules_an_incident(monkeypatch) -> None:
    from shogun.api.logs import verify_audit_chain
    from shogun.services import immutable_audit

    monkeypatch.setattr(
        immutable_audit,
        "verify_chain",
        lambda: {
            "total_records": 2,
            "verified_records": 1,
            "broken_at": 2,
            "chain_intact": False,
        },
    )
    scheduled = []

    def capture(coroutine):
        scheduled.append(coroutine)
        coroutine.close()
        return None

    monkeypatch.setattr(asyncio, "ensure_future", capture)

    response = await verify_audit_chain()

    assert response.data["chain_intact"] is False
    assert len(scheduled) == 1


@pytest.mark.asyncio
async def test_fleet_governance_evidence_has_non_conformity_notice(monkeypatch) -> None:
    from gensui.services.fleet_audit_service import FleetAuditService

    class Result:
        @staticmethod
        def scalar():
            return 0

    class Session:
        @staticmethod
        async def execute(_query):
            return Result()

    service = FleetAuditService(Session())

    async def consistent_chain(*, limit):
        assert limit == 5000
        return {"valid": True, "checked": 0, "errors": []}

    monkeypatch.setattr(service._audit, "verify_chain", consistent_chain)

    report = await service.get_compliance_report()

    assert report["report_purpose"] == "governance_evidence"
    assert "does not establish conformity" in report["assessment_notice"]
    assert "prove that every relevant event was captured" in report["assessment_notice"]
