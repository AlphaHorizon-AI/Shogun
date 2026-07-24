from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from shogun.api.agent_flow import _sync_live_flow_schedule, update_flow
from shogun.api.bushido import create_schedule, list_schedules
from shogun.db.models.agent_flow import AgentFlow, AgentFlowEdge, AgentFlowNode
from shogun.db.models.bushido import BushidoSchedule
from shogun.schemas.agent_flow import AgentFlowUpdate
from shogun.schemas.bushido import BushidoScheduleCreate
from shogun.services.bushido_service import BushidoScheduleService


def test_custom_schedule_validation_rejects_incomplete_jobs():
    with pytest.raises(ValidationError, match="at least one active day"):
        BushidoScheduleCreate(
            name="Weekly audit",
            job_type="performance_audit",
            frequency="weekly",
            schedule_days=[],
        )

    with pytest.raises(ValidationError, match="future date and time"):
        BushidoScheduleCreate(
            name="One off",
            job_type="memory_consolidation",
            frequency="one-off",
        )

    with pytest.raises(ValidationError, match="task instruction"):
        BushidoScheduleCreate(
            name="Custom",
            job_type="custom_task",
            frequency="nightly",
            task_instruction="",
        )


@pytest.mark.asyncio
async def test_register_schedule_creates_one_live_scheduler_job(monkeypatch):
    import shogun.scheduler as scheduler_module

    scheduler = AsyncIOScheduler()
    monkeypatch.setattr(scheduler_module, "_scheduler", scheduler)
    schedule = BushidoSchedule(
        id=uuid.uuid4(),
        name="Morning audit",
        job_type="performance_audit",
        frequency="nightly",
        schedule_time="08:00",
        scope={},
        is_enabled=True,
    )

    await scheduler_module.register_schedule(schedule)
    snapshot = scheduler_module.scheduler_job_snapshot(f"bushido_{schedule.id}")

    assert snapshot["scheduler_registered"] is True
    assert len(scheduler.get_jobs()) == 1
    assert schedule.next_run_at is not None


@pytest.mark.asyncio
async def test_create_custom_job_persists_and_registers(monkeypatch):
    import shogun.scheduler as scheduler_module

    scheduler = AsyncIOScheduler()
    monkeypatch.setattr(scheduler_module, "_scheduler", scheduler)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection: BushidoSchedule.__table__.create(sync_connection)
        )

    async with sessions() as session:
        body = BushidoScheduleCreate(
            name="Morning memory audit",
            job_type="memory_consolidation",
            frequency="nightly",
            schedule_time="08:00",
            scope={"memory_types": ["episodic"], "agent_ids": []},
        )
        response = await create_schedule(body, BushidoScheduleService(session))
        await session.commit()

        assert response.meta["scheduler_registered"] is True
        assert scheduler.get_job(response.meta["scheduler_job_id"]) is not None
        persisted = await session.get(BushidoSchedule, response.data.id)
        assert persisted is not None
        assert persisted.schedule_time == "08:00"

    await engine.dispose()


@pytest.mark.asyncio
async def test_agent_flow_activation_and_pause_share_scheduler_lifecycle(monkeypatch):
    import shogun.scheduler as scheduler_module

    calls: list[tuple[str, uuid.UUID]] = []

    async def register(flow):
        calls.append(("register", flow.id))
        return {"scheduler_registered": True, "next_run_at": None}

    async def deregister(flow_id):
        calls.append(("deregister", flow_id))

    monkeypatch.setattr(scheduler_module, "register_flow_schedule", register)
    monkeypatch.setattr(scheduler_module, "deregister_flow_schedule", deregister)

    flow_id = uuid.uuid4()
    active = SimpleNamespace(
        id=flow_id,
        trigger_type="scheduled",
        status="active",
        is_deleted=False,
    )
    paused = SimpleNamespace(
        id=flow_id,
        trigger_type="scheduled",
        status="paused",
        is_deleted=False,
    )

    await _sync_live_flow_schedule(active)
    await _sync_live_flow_schedule(paused)

    assert calls == [("register", flow_id), ("deregister", flow_id)]


@pytest.mark.asyncio
async def test_saving_scheduled_agentflow_activates_and_registers(monkeypatch):
    import shogun.scheduler as scheduler_module

    flow_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    flow = SimpleNamespace(
        id=flow_id,
        name="Scheduled briefing",
        description="",
        status="draft",
        trigger_type="manual",
        schedule_config={},
        viewport={},
        is_deleted=False,
        created_at=now,
        updated_at=now,
        created_by=None,
        nodes=[],
        edges=[],
    )
    calls: list[tuple[str, uuid.UUID]] = []

    class FakeFlowService:
        async def get_by_id(self, requested_id):
            assert requested_id == flow_id
            return flow

        async def update(self, requested_id, **kwargs):
            assert requested_id == flow_id
            for key, value in kwargs.items():
                setattr(flow, key, value)
            flow.updated_at = datetime.now(timezone.utc)
            return flow

        async def get_flow_full(self, requested_id):
            assert requested_id == flow_id
            return flow

    async def register(saved_flow):
        calls.append(("register", saved_flow.id))
        return {"scheduler_registered": True, "next_run_at": None}

    async def deregister(saved_flow_id):
        calls.append(("deregister", saved_flow_id))

    monkeypatch.setattr(scheduler_module, "register_flow_schedule", register)
    monkeypatch.setattr(scheduler_module, "deregister_flow_schedule", deregister)

    body = AgentFlowUpdate(
        trigger_type="scheduled",
        schedule_config={"frequency": "nightly", "schedule_time": "08:30"},
    )
    response = await update_flow(flow_id, body, FakeFlowService())

    assert response.data.status == "active"
    assert response.data.trigger_type == "scheduled"
    assert response.data.schedule_config["schedule_time"] == "08:30"
    assert calls == [("register", flow_id)]


@pytest.mark.asyncio
async def test_agentflow_schedule_replaces_same_live_cron_instead_of_duplicating(monkeypatch):
    import shogun.scheduler as scheduler_module

    scheduler = AsyncIOScheduler()
    monkeypatch.setattr(scheduler_module, "_scheduler", scheduler)
    flow = SimpleNamespace(
        id=uuid.uuid4(),
        name="Morning news",
        trigger_type="scheduled",
        status="active",
        schedule_config={"frequency": "nightly", "schedule_time": "08:00"},
    )

    await scheduler_module.register_flow_schedule(flow)
    await scheduler_module.register_flow_schedule(flow)

    jobs = scheduler.get_jobs()
    assert len(jobs) == 1
    assert jobs[0].id == f"agentflow_{flow.id}"


@pytest.mark.asyncio
async def test_agentflow_cron_callback_starts_a_scheduled_flow_run(monkeypatch):
    import shogun.scheduler as scheduler_module
    from shogun.engine import flow_engine

    flow_id = uuid.uuid4()
    calls: list[tuple[uuid.UUID, str]] = []

    async def start_flow_run(requested_flow_id, trigger_type="manual", **_kwargs):
        calls.append((requested_flow_id, trigger_type))
        return uuid.uuid4()

    monkeypatch.setattr(flow_engine, "start_flow_run", start_flow_run)

    await scheduler_module._fire_flow_schedule(str(flow_id))

    assert calls == [(flow_id, "scheduled")]


@pytest.mark.asyncio
async def test_operational_cadence_lists_bushido_and_agentflow(monkeypatch):
    import shogun.scheduler as scheduler_module

    scheduler = AsyncIOScheduler()
    monkeypatch.setattr(scheduler_module, "_scheduler", scheduler)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection: BushidoSchedule.__table__.create(sync_connection)
        )
        await connection.run_sync(
            lambda sync_connection: AgentFlow.__table__.create(sync_connection)
        )
        await connection.run_sync(
            lambda sync_connection: AgentFlowNode.__table__.create(sync_connection)
        )
        await connection.run_sync(
            lambda sync_connection: AgentFlowEdge.__table__.create(sync_connection)
        )

    async with sessions() as session:
        bushido = BushidoSchedule(
            name="Nightly",
            job_type="memory_consolidation",
            frequency="nightly",
            schedule_time="02:00",
            scope={},
            is_enabled=True,
            is_preset=False,
        )
        flow = AgentFlow(
            name="Morning news",
            description="Daily briefing",
            status="active",
            trigger_type="scheduled",
            schedule_config={"frequency": "nightly", "schedule_time": "08:00"},
            viewport={},
        )
        session.add_all([bushido, flow])
        await session.commit()
        await scheduler_module.register_flow_schedule(flow)

        response = await list_schedules(BushidoScheduleService(session))
        sources = {item["source"] for item in response.data}

        assert sources == {"bushido", "agent_flow"}
        flow_item = next(item for item in response.data if item["source"] == "agent_flow")
        assert flow_item["schedule_time"] == "08:00"
        assert flow_item["scheduler_job_id"] == f"agentflow_{flow.id}"
        assert flow_item["scheduler_registered"] is True

        from shogun.services.native_skills import execute_native_tool

        tool_result = json.loads(
            await execute_native_tool("list_cron_jobs", {}, session)
        )
        tool_flow = next(
            item
            for item in tool_result["schedules"]
            if item["source"] == "agent_flow"
        )
        assert tool_flow["id"] == str(flow.id)
        assert tool_flow["scheduler_registered"] is True

    await engine.dispose()


@pytest.mark.asyncio
async def test_save_flow_graph_syncs_scheduled_input_node():
    from shogun.db.models.agent_flow import AgentFlowEdge, AgentFlowNode
    from shogun.services.agent_flow_service import AgentFlowService

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection: AgentFlow.__table__.create(sync_connection)
        )
        await connection.run_sync(
            lambda sync_connection: AgentFlowNode.__table__.create(sync_connection)
        )
        await connection.run_sync(
            lambda sync_connection: AgentFlowEdge.__table__.create(sync_connection)
        )

    async with sessions() as session:
        svc = AgentFlowService(session)
        flow = await svc.create(name="Scheduled Briefing Flow", status="draft", trigger_type="manual")

        nodes_data = [
            {
                "id": str(uuid.uuid4()),
                "node_type": "input",
                "label": "Schedule Input",
                "position_x": 0.0,
                "position_y": 0.0,
                "config": {
                    "input_type": "scheduled",
                    "schedule_frequency": "nightly",
                    "schedule_time": "09:15",
                },
            }
        ]

        updated_flow = await svc.save_flow_graph(flow.id, nodes_data, [])
        assert updated_flow.trigger_type == "scheduled"
        assert updated_flow.status == "active"
        assert updated_flow.schedule_config["schedule_time"] == "09:15"
        assert updated_flow.schedule_config["frequency"] == "nightly"

    await engine.dispose()


@pytest.mark.asyncio
async def test_sync_flow_schedules_auto_heals_unregistered_input_nodes(monkeypatch):
    import shogun.scheduler as scheduler_module
    from shogun.db.models.agent_flow import AgentFlowEdge, AgentFlowNode

    scheduler = AsyncIOScheduler()
    monkeypatch.setattr(scheduler_module, "_scheduler", scheduler)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection: AgentFlow.__table__.create(sync_connection)
        )
        await connection.run_sync(
            lambda sync_connection: AgentFlowNode.__table__.create(sync_connection)
        )
        await connection.run_sync(
            lambda sync_connection: AgentFlowEdge.__table__.create(sync_connection)
        )

    async with sessions() as session:
        flow = AgentFlow(
            name="Legacy Unsynced Scheduled Flow",
            status="draft",
            trigger_type="manual",
            schedule_config={},
        )
        session.add(flow)
        await session.flush()

        node = AgentFlowNode(
            flow_id=flow.id,
            node_type="input",
            label="Schedule Input",
            config={
                "input_type": "scheduled",
                "schedule_frequency": "weekly",
                "schedule_time": "06:30",
                "schedule_days": ["mon", "wed", "fri"],
            },
        )
        session.add(node)
        await session.commit()

        registered_count = await scheduler_module.sync_flow_schedules(session)
        assert registered_count == 1
        assert scheduler.get_job(f"agentflow_{flow.id}") is not None

        await session.refresh(flow)
        assert flow.trigger_type == "scheduled"
        assert flow.status == "active"
        assert flow.schedule_config["schedule_time"] == "06:30"
        assert flow.schedule_config["schedule_days"] == ["mon", "wed", "fri"]

    await engine.dispose()


@pytest.mark.asyncio
async def test_agentflow_watchdog_repairs_missing_job_and_removes_stale_job(monkeypatch):
    import shogun.scheduler as scheduler_module
    from shogun.db.models.agent_flow import AgentFlowEdge, AgentFlowNode

    scheduler = AsyncIOScheduler()
    monkeypatch.setattr(scheduler_module, "_scheduler", scheduler)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection: AgentFlow.__table__.create(sync_connection)
        )
        await connection.run_sync(
            lambda sync_connection: AgentFlowNode.__table__.create(sync_connection)
        )
        await connection.run_sync(
            lambda sync_connection: AgentFlowEdge.__table__.create(sync_connection)
        )

    async with sessions() as session:
        flow = AgentFlow(
            name="Watchdog briefing",
            status="active",
            trigger_type="scheduled",
            schedule_config={"frequency": "nightly", "schedule_time": "13:15"},
        )
        session.add(flow)
        await session.flush()
        session.add(
            AgentFlowNode(
                flow_id=flow.id,
                node_type="input",
                label="Scheduled input",
                config={
                    "input_type": "scheduled",
                    "schedule_frequency": "nightly",
                    "schedule_time": "07:00",
                },
            )
        )
        await session.commit()

        job_id = f"agentflow_{flow.id}"
        await scheduler_module.sync_flow_schedules(session, missing_only=True)
        job = scheduler.get_job(job_id)
        assert job is not None
        assert str(job.trigger) == "cron[hour='13', minute='15']"
        assert flow.schedule_config["schedule_time"] == "13:15"

        scheduler.remove_job(job_id)
        assert scheduler.get_job(job_id) is None

        await scheduler_module.sync_flow_schedules(session, missing_only=True)
        assert scheduler.get_job(job_id) is not None

        flow.status = "paused"
        await session.flush()
        await scheduler_module.sync_flow_schedules(session, missing_only=True)
        assert scheduler.get_job(job_id) is None

    await engine.dispose()


@pytest.mark.asyncio
async def test_scheduler_starts_agentflow_reconciliation_watchdog(monkeypatch):
    import shogun.scheduler as scheduler_module

    scheduler = AsyncIOScheduler()
    monkeypatch.setattr(scheduler_module, "_scheduler", scheduler)

    await scheduler_module.start_scheduler()
    try:
        assert scheduler.running is True
        assert scheduler.get_job("agentflow_schedule_reconcile") is not None
    finally:
        scheduler.shutdown(wait=False)
