"""Exercise workbook jobs through the complete DAG and persistence boundaries."""

import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import openpyxl
import pytest

from shogun.db.models.agent_flow import AgentFlow
from shogun.db.models.agent_flow_run import AgentFlowRun, AgentFlowRunEdge
from shogun.engine import flow_engine
from shogun.services.samurai_workbook_job import JOB_MARKER, WorkbookTransformJob
from tests.test_samurai_workbook_jobs import workbook_flow as workbook_flow


@pytest.mark.anyio
async def test_workbook_job_survives_dag_handoff_and_serialized_run_history(workbook_flow, monkeypatch):
    fixture = workbook_flow
    flow_id = uuid.uuid4()

    def node(node_type, label, config, node_id=None):
        return SimpleNamespace(
            id=node_id or uuid.uuid4(), flow_id=flow_id,
            node_type=node_type, label=label, config=config,
        )

    input_node = node("input", "Start", {"input_type": "manual", "manual_input": "Prepare this schedule"})
    samurai = node("samurai", "Build schedule", {
        "transformation_mode": "profile",
        "transformation_profile": fixture.exported["profile_reference"],
        "task_description": "Populate current equipment jobs",
    }, fixture.samurai_id)
    writer = node("office", "Write workbook", {
        "action": "excel_create", "output_path": "Output", "output_filename": "schedule.xlsx",
        # The ordinary Files editor's default must not override the private profile.
        "sheet_name": "Sheet1",
    }, fixture.writer_id)
    output = node("output", "Result", {"format": "plain"})
    sources = list(fixture.nodes.values())
    for source in sources:
        source.flow_id = flow_id
    connections = [
        *[(input_node, source) for source in sources],
        *[(source, samurai) for source in sources],
        (samurai, writer), (writer, output),
    ]
    flow = SimpleNamespace(
        id=flow_id, name="Equipment schedule", nodes=[input_node, *sources, samurai, writer, output],
        edges=[SimpleNamespace(source_node_id=source.id, target_node_id=target.id, source_handle=None)
               for source, target in connections],
    )
    run = AgentFlowRun(
        id=fixture.run_id, flow_id=flow_id, status="pending", trigger_type="manual",
        input_payload={}, governance_context=fixture.governance, node_states={},
        output_payload={}, result_summary={}, artifacts=[],
    )
    commits = []

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def execute(self, query):
            entity = query.column_descriptions[0]["entity"]
            assert entity in {AgentFlow, AgentFlowRun, AgentFlowRunEdge}
            value = flow if entity is AgentFlow else run if entity is AgentFlowRun else None
            return SimpleNamespace(scalar_one_or_none=lambda: value)

        async def get(self, entity, identifier, **_kwargs):
            assert entity is AgentFlowRun and identifier == run.id
            return run

        async def commit(self):
            # Simulate the JSON storage boundary, including loss of runtime subclasses.
            for field in ("node_states", "artifacts", "output_payload", "result_summary"):
                setattr(run, field, json.loads(json.dumps(getattr(run, field))))
            commits.append(json.loads(json.dumps(run.node_states)))

    monkeypatch.setattr(flow_engine, "async_session_factory", Session)
    forbidden_model = AsyncMock(side_effect=AssertionError("Workbook jobs must not call a model"))
    monkeypatch.setattr(flow_engine, "_exec_samurai", forbidden_model)
    monkeypatch.setattr(flow_engine, "_record_node_failure_event", AsyncMock(return_value=None))
    original_office = flow_engine._exec_office
    writer_handoffs = []

    async def inspect_office_handoff(config, *args, **kwargs):
        if config.get("action") == "excel_create":
            predecessors = kwargs["predecessor_outputs"]
            assert set(predecessors) == {str(samurai.id)}
            job = predecessors[str(samurai.id)]
            assert isinstance(job, WorkbookTransformJob)
            assert run.node_states[str(samurai.id)]["status"] == "completed"
            assert JOB_MARKER in run.node_states[str(samurai.id)]["output"]
            templates = kwargs["template_inputs"]
            assert len(templates) == 1
            assert templates[0]["template_path"] == "empty.xlsx"
            assert templates[0]["format"] == "xlsx"
            writer_handoffs.append(json.loads(json.dumps(job)))
        return await original_office(config, *args, **kwargs)

    monkeypatch.setattr(flow_engine, "_exec_office", inspect_office_handoff)
    original_template = (fixture.root / "empty.xlsx").read_bytes()

    try:
        await flow_engine._execute_flow(run.id, flow_id)
    finally:
        flow_engine._run_state_locks.pop(str(run.id), None)

    assert run.status == "completed", run.error_message
    assert all(state["status"] == "completed" for state in run.node_states.values())
    assert len(writer_handoffs) == 1
    assert type(writer_handoffs[0]) is dict
    assert "section_pattern" not in json.dumps(commits)
    assert "Excel workbook created:" in run.output_payload["Result"]
    assert "Output/schedule.xlsx" in run.output_payload["Result"]
    writer_artifacts = [item["path_or_ref"] for item in run.artifacts
                        if item["created_by_node_id"] == str(writer.id)]
    assert len(writer_artifacts) == 5
    assert "Output/schedule.xlsx" in writer_artifacts
    assert all((fixture.root / path).is_file() for path in writer_artifacts)
    book = openpyxl.load_workbook(fixture.root / "Output/schedule.xlsx")
    try:
        assert book.active.title == "Schedule"
        actual_jobs = {(row[0], row[1], row[3])
                       for row in book.active.iter_rows(min_row=3, values_only=True) if row[1]}
        assert actual_jobs == {("ASSET-0", "JOB-0", 2), ("ASSET-1", "JOB-1", 3), ("ASSET-2", "JOB-2", 4)}
    finally:
        book.close()
    assert (fixture.root / "empty.xlsx").read_bytes() == original_template
    forbidden_model.assert_not_awaited()
