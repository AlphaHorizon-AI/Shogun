"""Transformation tools must not publish or log private exception diagnostics."""

from __future__ import annotations

import json
import logging
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from shogun.services import native_skills, source_intelligence, transformation_profile_registry

PRIVATE_DIAGNOSTIC = "credential=private-profile-secret at /private/shogun/tenant-profile.json"


@pytest.mark.parametrize(
    "exception_type,expected_guidance",
    [
        (transformation_profile_registry.TransformationProfileRegistryError, "profile definition"),
        (transformation_profile_registry.TransformationProfileNotFoundError, "List available profiles"),
        (transformation_profile_registry.ProtectedTransformationProfileError, "protected"),
        (transformation_profile_registry.TransformationAdapterUnavailableError, "adapter is unavailable"),
        (transformation_profile_registry.TransformationProfileLifecycleError, "validation evidence"),
    ],
)
@pytest.mark.parametrize("mutating", [False, True])
async def test_registry_failures_are_safe_without_changing_transaction_behavior(
    monkeypatch, caplog, exception_type, expected_guidance, mutating,
):
    db = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    failure = AsyncMock(side_effect=exception_type(PRIVATE_DIAGNOSTIC))
    method = "promote" if mutating else "get_profile"
    monkeypatch.setattr(transformation_profile_registry.TransformationProfileRegistryService, method, failure)
    tool = "transformation_profiles_promote" if mutating else "transformation_profiles_get"
    arguments = {"version_id": str(uuid.uuid4())} if mutating else {"profile_id": "valid-profile"}

    with caplog.at_level(logging.WARNING):
        raw_result = await native_skills.execute_native_tool(tool, arguments, db)

    result = json.loads(raw_result)
    assert result["status"] == "error"
    assert result["error_type"] == exception_type.__name__
    assert expected_guidance in result["message"]
    assert set(result) == {"status", "error_type", "message"}
    assert "private-profile-secret" not in raw_result + caplog.text
    assert "/private/shogun" not in raw_result + caplog.text
    failure.assert_awaited_once()
    db.commit.assert_not_awaited()
    if mutating:
        db.rollback.assert_awaited_once()
    else:
        db.rollback.assert_not_awaited()


@pytest.mark.parametrize(
    "exception_type,expected_guidance",
    [
        (source_intelligence.SourceIntelligenceError, "supplied artifacts"),
        (source_intelligence.SourceIntelligenceConfigurationError, "profile configuration"),
        (source_intelligence.SourceIntelligenceRegexTimeoutError, "matching time limit"),
        (source_intelligence.SourceProfileUnknownError, "No installed transformation profile"),
        (source_intelligence.SourceProfileAmbiguousError, "Multiple transformation profiles"),
    ],
)
async def test_source_failures_do_not_expose_diagnostics_or_attached_private_resolution(
    monkeypatch, caplog, exception_type, expected_guidance,
):
    db = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    error = exception_type(PRIVATE_DIAGNOSTIC)
    # Some source errors carry a rich result; it must stay inside the service.
    error.result = {"private_profile": PRIVATE_DIAGNOSTIC}
    monkeypatch.setattr(source_intelligence.SourceIntelligenceService, "inspect", AsyncMock(side_effect=error))

    with caplog.at_level(logging.WARNING):
        raw_result = await native_skills.execute_native_tool(
            "transformation_sources_inspect",
            {"artifacts": [{"source_id": "input", "payload": {"InvoiceId": "I-1"}}]},
            db,
        )

    result = json.loads(raw_result)
    assert result["status"] == "error"
    assert expected_guidance in result["message"]
    assert set(result) == {"status", "error_type", "message"}
    assert "private-profile-secret" not in raw_result + caplog.text
    assert "/private/shogun" not in raw_result + caplog.text
    db.commit.assert_not_awaited()
    db.rollback.assert_not_awaited()


@pytest.mark.parametrize("exception_type", [TypeError, ValueError, RuntimeError])
async def test_other_tool_failures_keep_private_diagnostics_out_of_response_and_logs(
    monkeypatch, caplog, exception_type,
):
    db = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    monkeypatch.setattr(
        transformation_profile_registry.TransformationProfileRegistryService,
        "get_profile",
        AsyncMock(side_effect=exception_type(PRIVATE_DIAGNOSTIC)),
    )

    with caplog.at_level(logging.WARNING):
        raw_result = await native_skills.execute_native_tool(
            "transformation_profiles_get", {"profile_id": "valid-profile"}, db,
        )

    assert json.loads(raw_result)["status"] == "error"
    assert "private-profile-secret" not in raw_result + caplog.text
    assert "/private/shogun" not in raw_result + caplog.text
    assert exception_type.__name__ in caplog.text
    db.commit.assert_not_awaited()
    db.rollback.assert_awaited_once()


async def test_invalid_source_request_reports_field_errors_without_input_values(caplog):
    db = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())

    with caplog.at_level(logging.WARNING):
        raw_result = await native_skills.execute_native_tool(
            "transformation_sources_inspect",
            {"artifacts": [{"source_id": "", "payload": {"secret": PRIVATE_DIAGNOSTIC}}]},
            db,
        )

    result = json.loads(raw_result)
    assert result["status"] == "error"
    assert result["error_type"] == "ValidationError"
    assert result["errors"] == [{"location": "artifacts.0.source_id", "type": "string_too_short"}]
    assert "private-profile-secret" not in raw_result + caplog.text
    assert "/private/shogun" not in raw_result + caplog.text
    db.commit.assert_not_awaited()
    db.rollback.assert_awaited_once()
