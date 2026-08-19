from __future__ import annotations

import inspect
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def _use_notice_file(monkeypatch, tmp_path: Path):
    import shogun.services.startup_notices as notices

    monkeypatch.setattr(notices, "_NOTICE_PATH", tmp_path / "startup_notices.json")
    return notices


def test_legacy_duplicate_notices_are_consolidated_and_upserted(tmp_path: Path, monkeypatch):
    notices = _use_notice_file(monkeypatch, tmp_path)
    legacy = [
        {
            "id": f"old-{index}",
            "code": "database_repair_incomplete",
            "severity": "warning",
            "message": "Repair failed safely.",
            "created_at": f"2026-08-19T17:42:0{index}+00:00",
        }
        for index in range(3)
    ]
    notices._NOTICE_PATH.write_text(json.dumps(legacy), encoding="utf-8")

    stored = notices.list_startup_notices()

    assert len(stored) == 1
    assert stored[0]["id"] == notices._stable_id("database_repair_incomplete")
    assert stored[0]["occurrence_count"] == 3
    assert stored[0]["first_seen_at"] == legacy[0]["created_at"]
    assert stored[0]["last_seen_at"] == legacy[-1]["created_at"]
    notices.record_startup_notice("database_repair_incomplete", "Repair still incomplete.")
    updated = notices.list_startup_notices()[0]
    assert updated["id"] == stored[0]["id"]
    assert updated["occurrence_count"] == 4
    assert updated["message"] == "Repair still incomplete."


def test_resolved_notices_are_hidden_and_can_be_reactivated(tmp_path: Path, monkeypatch):
    notices = _use_notice_file(monkeypatch, tmp_path)
    notices.record_startup_notice("skill_schema_repair_incomplete", "Repair failed.")

    assert notices.resolve_startup_notice("skill_schema_repair_incomplete") is True
    assert notices.list_startup_notices() == []
    history = notices.list_startup_notices(active_only=False)
    assert history[0]["status"] == "resolved"
    assert history[0]["active"] is False
    assert history[0]["resolved_at"] is not None

    notices.record_startup_notice("skill_schema_repair_incomplete", "Repair failed again.")
    reactivated = notices.list_startup_notices()[0]
    assert reactivated["status"] == "active"
    assert reactivated["resolved_at"] is None
    assert reactivated["occurrence_count"] == 2


def test_notice_upserts_are_thread_safe_and_atomically_parseable(tmp_path: Path, monkeypatch):
    notices = _use_notice_file(monkeypatch, tmp_path)

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(
            executor.map(
                lambda _: notices.record_startup_notice("database_migration_failed", "Migration failed."),
                range(24),
            )
        )

    payload = json.loads(notices._NOTICE_PATH.read_text(encoding="utf-8"))
    assert len(payload) == 1
    assert payload[0]["occurrence_count"] == 24
    assert not list(tmp_path.glob("*.tmp"))


async def test_provider_credential_migration_commits_once_when_records_change():
    from shogun.app import _protect_legacy_provider_credentials

    class Session:
        commits = 0

        async def commit(self):
            self.commits += 1

    class SessionContext:
        session = Session()

        async def __aenter__(self):
            return self.session

        async def __aexit__(self, exc_type, exc, traceback):
            return False

    calls = 0

    async def migrate(session):
        nonlocal calls
        calls += 1
        assert session is SessionContext.session
        return 2

    assert await _protect_legacy_provider_credentials(lambda: SessionContext(), migrate) == 2
    assert calls == 1
    assert SessionContext.session.commits == 1


def test_lifespan_runs_each_resolution_and_credential_migration_once():
    from shogun.app import lifespan

    source = inspect.getsource(lifespan)
    assert source.count("await _protect_legacy_provider_credentials()") == 1
    for code in (
        "database_migration_failed",
        "database_repair_incomplete",
        "skill_schema_repair_incomplete",
    ):
        assert source.count(f'resolve_startup_notice("{code}")') == 1
