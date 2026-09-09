"""Keep private transformation data out of fallback diagnostics."""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from shogun.engine import flow_engine


@pytest.mark.asyncio
@pytest.mark.parametrize("model_fallback", [False, True])
async def test_private_profile_failure_logs_only_error_category(monkeypatch, caplog, model_fallback):
    private_id = "private-operator-profile-7d4676"
    private_source = "customer-private-source-204c3b"
    profile = {
        "id": private_id,
        "adapter": "sectioned_record_matrix_v1",
        "model_fallback": model_fallback,
        "parameters": {
            "required_source_patterns": [r"(?m)^Record: "],
            "section_pattern": r"(?m)^Record: (?P<section_id>\S+)",
        },
    }

    @asynccontextmanager
    async def session_context():
        yield object()

    provider = SimpleNamespace(is_local=False, provider_type="openai_compatible")
    resolve_route = AsyncMock(
        return_value=(
            [(provider, "matrix-model", "https://model.invalid/v1", {})],
            {
                "selected_max_input_tokens": 24_576,
                "selected_max_output_tokens": 4_096,
            },
        )
    )
    call_rows = AsyncMock(return_value=[["model fallback", 1]])
    monkeypatch.setattr(flow_engine, "async_session_factory", session_context)
    monkeypatch.setattr(flow_engine, "_resolve_task_llm_chain", resolve_route)
    monkeypatch.setattr(flow_engine, "_call_llm_chain_rows_with_fallback", call_rows)
    caplog.set_level(logging.INFO, logger=flow_engine.log.name)

    config = {
        "task_description": "Populate the template from the supplied source.",
        "_transformation_profiles": [profile],
        "_transformation_source_contexts": [{"label": private_source, "content": "Object: B1\nQuantity: 12"}],
    }
    arguments = {
        "config": config,
        "context_str": "Object: B1\nQuantity: 12",
        "fixed_context_str": (
            "[FILE TEMPLATE CONTRACT]\nFormat: xlsx\n"
            '[MACHINE-READABLE TEMPLATE MANIFEST]\n{"kind": "excel", "logical_columns": 2}'
        ),
    }

    if model_fallback:
        result = await flow_engine._exec_samurai(**arguments)
        assert json.loads(result) == [["model fallback", 1]]
        resolve_route.assert_awaited_once()
        call_rows.assert_awaited_once()
        assert "explicit model fallback is enabled (error_type=ValueError)" in caplog.text
    else:
        with pytest.raises(ValueError, match="does not match transformation profile"):
            await flow_engine._exec_samurai(**arguments)
        resolve_route.assert_not_awaited()
        call_rows.assert_not_awaited()
        assert "model fallback is enabled" not in caplog.text

    assert private_id not in caplog.text
    assert private_source not in caplog.text
    assert "Object: B1" not in caplog.text
    assert "does not match transformation profile" not in caplog.text
