from __future__ import annotations

import asyncio
import uuid

import pytest

from shogun.db.models.agent_flow_run import AgentFlowRun
from shogun.engine import flow_engine


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _ConcurrentSession:
    def __init__(self, store):
        self.store = store

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def execute(self, _query):
        self.store["active"] += 1
        self.store["max_active"] = max(self.store["max_active"], self.store["active"])
        await asyncio.sleep(0)
        return _ScalarResult(self.store["run"])

    async def commit(self):
        await asyncio.sleep(0)
        self.store["active"] -= 1


@pytest.mark.asyncio
async def test_parallel_node_state_updates_are_serialized_per_run(monkeypatch):
    run_id = uuid.uuid4()
    node_ids = [str(uuid.uuid4()) for _ in range(4)]
    store = {
        "run": AgentFlowRun(
            node_states={
                node_id: {
                    "status": "pending",
                    "output": None,
                    "error": None,
                    "started_at": None,
                    "completed_at": None,
                }
                for node_id in node_ids
            }
        ),
        "active": 0,
        "max_active": 0,
    }
    monkeypatch.setattr(flow_engine, "async_session_factory", lambda: _ConcurrentSession(store))
    flow_engine._run_state_locks.pop(str(run_id), None)

    await asyncio.gather(
        *(flow_engine._update_node_state(run_id, node_id, "running") for node_id in node_ids)
    )

    assert store["max_active"] == 1
    assert all(store["run"].node_states[node_id]["status"] == "running" for node_id in node_ids)
    assert all(store["run"].node_states[node_id]["started_at"] for node_id in node_ids)
