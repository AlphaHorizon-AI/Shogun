import uuid
from types import SimpleNamespace

import pytest

from shogun.api.agent_flow import delete_flow_run
from shogun.config import settings


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeSession:
    def __init__(self, run):
        self.run = run
        self.deleted = None
        self.committed = False

    async def execute(self, _query):
        return _ScalarResult(self.run)

    async def delete(self, run):
        self.deleted = run

    async def commit(self):
        self.committed = True


@pytest.mark.asyncio
async def test_deleting_run_history_retains_generated_output(tmp_path, monkeypatch):
    run_id = uuid.uuid4()
    monkeypatch.setattr(settings, "workspace_path", tmp_path)
    artifact = tmp_path / "Output" / "daily_report.xlsx"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"yesterday's report")
    run = SimpleNamespace(
        id=run_id,
        status="completed",
        node_states={
            "files-node": {
                "status": "completed",
                "artifact_path": "Output/daily_report.xlsx",
            }
        },
    )
    session = _FakeSession(run)

    response = await delete_flow_run(run_id, session)

    assert artifact.read_bytes() == b"yesterday's report"
    assert session.deleted is run
    assert session.committed is True
    assert response.data["deleted_files"] == []
    assert response.data["artifacts_retained"] is True
