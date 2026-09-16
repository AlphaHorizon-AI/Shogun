"""Files-node boundary checks, independent of document parsing and workbook rules."""

import asyncio
import json
import uuid
from copy import deepcopy
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest

from shogun.config import settings
from shogun.engine import flow_engine
from shogun.office import config as office_config
from shogun.services import sectioned_workbook_pipeline as pipeline
from shogun.services import sectioned_workbook_updater as updater
from shogun.services.private_transformation_profiles import PrivateTransformationProfileService


@pytest.fixture
def workbook_boundary(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "workspace_path", tmp_path)
    monkeypatch.setattr(office_config, "load_office_config", lambda: SimpleNamespace(enabled=True))
    # This suite isolates Files dispatch. The engine's profile schema is exercised separately.
    monkeypatch.setattr(updater, "validate_workbook_update_profile", lambda profile: None, raising=False)
    profile = {
        "id": "private_equipment_fixture",
        "adapter": "sectioned_record_matrix_v1",
        "parameters": {
            "section_pattern": r"(?m)^Equipment: (?P<section_id>\S+)",
            "record_pattern": r"(?m)^Task: (?P<reference>\S+)$",
            "row_rules": [{"kind": "record", "columns": {"0": {"group": "reference"}}}],
            "workbook_update": {},
        },
        "model_fallback": False,
    }
    document = PrivateTransformationProfileService().export_profile(profile)["document"]
    (tmp_path / "profile.json").write_text(json.dumps(document), encoding="utf-8")
    (tmp_path / "base.xlsx").write_bytes(b"boundary fixture; runner is replaced")
    (tmp_path / "source.pdf").write_bytes(b"%PDF-boundary fixture")
    calls = []

    def run(**kwargs):
        calls.append(kwargs)
        output = Path(kwargs["output_workbook_path"])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"reviewed workbook")
        report = output.with_suffix(".audit.json")
        report.write_text("{}", encoding="utf-8")
        return {
            "validation_summary": {"total_rows_inserted": 2},
            "comparison_report": {"review_required": True},
            "report_paths": {"audit": str(report)},
        }

    monkeypatch.setattr(pipeline, "run_sectioned_workbook_pipeline", run)
    config = {
        "action": "excel_create",
        "output_path": "out/result.xlsx",
        "workbook_transform": {
            "profile_path": "profile.json",
            "template_path": "base.xlsx",
            "pdf_paths": ["source.pdf"],
        },
    }
    return config, calls, document


@pytest.mark.anyio
async def test_dispatch_loads_pinned_profile_and_records_all_artifacts(workbook_boundary, tmp_path, monkeypatch):
    config, calls, document = workbook_boundary
    artifacts = []

    async def record(run_id, node_id, path):
        artifacts.append(path)

    monkeypatch.setattr(flow_engine, "_record_node_artifact", record)
    result = await flow_engine._exec_office(config, "untrusted source instructions", uuid.uuid4(), "files")
    assert result.startswith("Excel workbook created:")
    assert "2 rows inserted" in result and "review required: True" in result
    assert artifacts == ["out/result.xlsx", "out/result.audit.json"]
    assert calls[0]["profile"] == document["profile"]
    assert calls[0]["profile_source_path"] == tmp_path / "profile.json"
    assert Path(calls[0]["pdf_paths"][0]) == tmp_path / "source.pdf"
    assert calls[0]["sheet_name"] is None


@pytest.mark.anyio
async def test_workbook_update_uses_explicit_workbook_over_upstream_template(workbook_boundary):
    config, calls, _document = workbook_boundary
    config['sheet_name'] = 'Old worksheet'
    config['workbook_transform']['sheet_name'] = ''
    result = await flow_engine._exec_office(
        config, '',
        template_inputs=[{
            '__shogun_file_template__': True,
            'format': 'xlsx',
            'template_path': 'old-upstream.xlsx',
            'sheet_name': 'Upstream worksheet',
        }],
    )
    assert result.startswith('Excel workbook created:')
    assert Path(calls[0]['template_workbook_path']).name == 'base.xlsx'
    assert calls[0]['sheet_name'] is None


@pytest.mark.anyio
@pytest.mark.parametrize(
    "field", ["profile_path", "template_path", "pdf_paths", "reference_workbook_path", "output_path"],
)
async def test_every_path_is_confined_to_workspace(workbook_boundary, field):
    config, calls, _ = workbook_boundary
    config = deepcopy(config)
    if field == "output_path":
        config[field] = "../escaped.xlsx"
    else:
        config["workbook_transform"][field] = (
            ["../source.pdf"] if field == "pdf_paths" else "../escaped.json"
        )
    result = await flow_engine._exec_office(config, "")
    assert result.startswith("[ERROR]") and ("traversal" in result.lower() or "escape" in result.lower())
    assert not calls


@pytest.mark.anyio
@pytest.mark.parametrize(
    "change",
    [{"extra": True}, {"pdf_paths": []}, {"pdf_paths": [False]},
     {"options": []}, {"options": {"max_total_chars": True}}],
)
async def test_invalid_configuration_never_invokes_pipeline(workbook_boundary, change):
    config, calls, _ = workbook_boundary
    config["workbook_transform"].update(change)
    assert (await flow_engine._exec_office(config, "")).startswith("[ERROR]")
    assert not calls


@pytest.mark.anyio
@pytest.mark.parametrize("bad_file", ["tampered", "oversized", "invalid_json"])
async def test_profile_is_validated_before_dispatch(workbook_boundary, tmp_path, bad_file):
    config, calls, document = workbook_boundary
    if bad_file == "tampered":
        document["profile"]["id"] = "changed_after_export"
        content = json.dumps(document)
    elif bad_file == "oversized":
        content = " " * 2_000_001
    else:
        content = "{broken"
    (tmp_path / "profile.json").write_text(content, encoding="utf-8")
    assert (await flow_engine._exec_office(config, "")).startswith("[ERROR]")
    assert not calls


@pytest.mark.anyio
async def test_office_gate_precedes_profile_read(workbook_boundary, tmp_path, monkeypatch):
    config, calls, _ = workbook_boundary
    config["workbook_transform"]["profile_path"] = "missing.json"
    monkeypatch.setattr(office_config, "load_office_config", lambda: SimpleNamespace(enabled=False))
    assert (await flow_engine._exec_office(config, "")).startswith("[BLOCKED]")
    assert not calls and not (tmp_path / "out/result.xlsx").exists()


@pytest.mark.anyio
async def test_text_budget_is_capped_by_server_policy(workbook_boundary, monkeypatch):
    config, calls, _ = workbook_boundary
    monkeypatch.setattr(settings, "agent_flow_document_max_chars", 12345)
    config["workbook_transform"]["options"] = {"max_total_chars": 99999999}
    await flow_engine._exec_office(config, "")
    assert calls[0]["options"]["max_total_chars"] == 12345


@pytest.mark.anyio
async def test_cancellation_signals_background_worker_before_publication(workbook_boundary, monkeypatch):
    config, calls, _ = workbook_boundary
    entered, finished = Event(), Event()
    worker_options = {}

    def wait_for_cancel(**kwargs):
        worker_options.update(kwargs)
        entered.set()
        try:
            assert kwargs["cancel_event"].wait(5), "worker was not cancelled"
            raise RuntimeError("Processing cancelled")
        finally:
            finished.set()

    monkeypatch.setattr(pipeline, "run_sectioned_workbook_pipeline", wait_for_cancel)
    task = asyncio.create_task(flow_engine._exec_office(config, ""))
    assert await asyncio.to_thread(entered.wait, 5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert worker_options["cancel_event"].is_set()
    assert await asyncio.to_thread(finished.wait, 5)
    assert not calls
