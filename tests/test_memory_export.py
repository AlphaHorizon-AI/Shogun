from __future__ import annotations

import json
import uuid
import zipfile
from datetime import datetime, timezone

import pytest
import yaml
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import shogun.db.models  # noqa: F401
from shogun.api.memory import router as memory_router
from shogun.db.base import Base
from shogun.db.models.agent import Agent
from shogun.db.models.memory_record import MemoryRecord
from shogun.schemas.memory import MemoryExportRequest
from shogun.services.event_logger import EventLogger
from shogun.services.memory_export_service import (
    MemoryExportService,
    render_frontmatter,
    safe_filename,
)


@pytest.fixture
async def export_context(tmp_path, monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def no_audit(*_args, **_kwargs):
        return "evt_test"

    monkeypatch.setattr(EventLogger, "emit", no_audit)
    async with sessions() as session:
        agent = Agent(
            id=uuid.uuid4(),
            agent_type="shogun",
            name="Max",
            slug="max-export",
            status="active",
            is_primary=True,
        )
        records = [
            MemoryRecord(
                id=uuid.uuid4(),
                memory_type="semantic",
                agent_id=agent.id,
                source_type="project:shogun_afm",
                title="Portable strategy memory",
                content="A human-readable memory body.",
                importance_score=0.91,
                confidence_score=0.88,
                decay_class="slow",
                is_archived=False,
            ),
            MemoryRecord(
                id=uuid.uuid4(),
                memory_type="episodic",
                agent_id=agent.id,
                source_type="daily_archive",
                title="Archived decision",
                content="The archived decision body.",
                importance_score=0.7,
                confidence_score=0.8,
                decay_class="medium",
                is_archived=True,
            ),
            MemoryRecord(
                id=uuid.uuid4(),
                memory_type="persona",
                agent_id=agent.id,
                source_type="private",
                title="Private preference",
                content="Private context.",
                importance_score=0.9,
                confidence_score=0.9,
                decay_class="sticky",
                is_pinned=True,
                is_archived=False,
            ),
            MemoryRecord(
                id=uuid.uuid4(),
                memory_type="semantic",
                agent_id=agent.id,
                source_type="credential_secret",
                title="API token memory",
                content="Must not be exported by default.",
                is_archived=False,
            ),
        ]
        session.add_all([agent, *records])
        await session.commit()
        yield session, tmp_path / "exports", agent, records
    await engine.dispose()


def test_frontmatter_quotes_untrusted_yaml_values():
    rendered = render_frontmatter({"title": "unsafe: value\n---", "tags": ["a:b", "safe"]})

    assert rendered.startswith("---\n")
    assert 'title: "unsafe: value\\n---"' in rendered
    assert '  - "a:b"' in rendered
    assert rendered.endswith("\n---")


def test_filename_is_safe_predictable_and_bounded():
    record = MemoryRecord(
        id=uuid.UUID("12345678-1234-1234-1234-123456789abc"),
        memory_type="Semantic / Project",
        agent_id=uuid.uuid4(),
        title="../../Unsafe: title? " + "x" * 200,
        content="body",
        created_at=datetime(2026, 7, 18, tzinfo=timezone.utc),
    )

    filename = safe_filename(record)
    assert filename.startswith("semantic-project_2026-07-18_1234567812_")
    assert ".." not in filename and "/" not in filename and "\\" not in filename
    assert filename.endswith(".md")
    assert len(filename) <= 120


@pytest.mark.asyncio
async def test_preview_applies_project_privacy_archive_and_secret_filters(export_context):
    session, export_root, agent, _records = export_context
    service = MemoryExportService(session, export_root)

    preview = await service.preview(MemoryExportRequest(
        scope="project",
        project_id="shogun_afm",
        agent_id=agent.id,
        include_archives=True,
        include_private=False,
    ))

    assert preview["estimated_counts"]["memories"] == 1
    assert preview["estimated_counts"]["archives"] == 0
    assert preview["estimated_counts"]["private"] == 0
    assert "Private memories are included" not in " ".join(preview["warnings"])


@pytest.mark.asyncio
async def test_private_export_requires_explicit_confirmation(export_context):
    session, export_root, _agent, _records = export_context
    service = MemoryExportService(session, export_root)

    with pytest.raises(ValueError, match="explicit confirmation"):
        await service.create_job(MemoryExportRequest(include_private=True))


@pytest.mark.asyncio
async def test_export_builds_markdown_manifest_raw_json_and_zip(export_context):
    session, export_root, agent, records = export_context
    service = MemoryExportService(session, export_root)
    request = MemoryExportRequest(
        scope="all",
        agent_id=agent.id,
        include_archives=True,
        include_private=True,
        include_raw_json=True,
        package_as_zip=True,
        private_export_confirmed=True,
    )
    job = await service.create_job(request)
    await session.commit()

    completed = await service.execute(job.id)

    assert completed.status == "completed"
    assert completed.counts_json["memories"] == 2
    assert completed.counts_json["archives"] == 1
    assert completed.counts_json["files"] == 3
    bundle = export_root / job.id
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "1.0"
    assert manifest["target_compatibility"] == "openclaw_md"
    assert len(manifest["files"]) == 3
    assert (bundle / "README.md").is_file()
    assert (bundle / "raw" / "memories.json").is_file()
    assert (bundle / "raw" / "archives.json").is_file()

    markdown_files = list((bundle / "memories").rglob("*.md")) + list((bundle / "archives").rglob("*.md"))
    assert len(markdown_files) == 3
    markdown = markdown_files[0].read_text(encoding="utf-8")
    assert markdown.startswith("---\nschema_version: \"1.0\"")
    assert "target_compatibility: \"openclaw_md\"" in markdown
    assert "\n## Metadata\n" in markdown
    assert "\n## Source Trace\n" in markdown
    for markdown_path in markdown_files:
        frontmatter = markdown_path.read_text(encoding="utf-8").split("---", 2)[1]
        parsed = yaml.safe_load(frontmatter)
        assert parsed["schema_version"] == "1.0"
        assert parsed["source_system"] == "shogun_afm"

    with zipfile.ZipFile(export_root / f"{job.id}.zip") as archive:
        names = archive.namelist()
        assert "manifest.json" in names
        assert "README.md" in names
        assert sum(name.endswith(".md") and name not in {"README.md", "export_report.md"} for name in names) == 3

    raw_memories = json.loads((bundle / "raw" / "memories.json").read_text(encoding="utf-8"))
    assert all(item["id"] != str(records[3].id) for item in raw_memories)


@pytest.mark.asyncio
async def test_download_path_blocks_tampered_or_traversing_paths(export_context, tmp_path):
    session, export_root, _agent, _records = export_context
    service = MemoryExportService(session, export_root)
    job = await service.create_job(MemoryExportRequest(
        include_private=False,
        package_as_zip=True,
    ))
    await session.commit()
    completed = await service.execute(job.id)
    assert service.download_path(completed).parent == export_root.resolve()

    outside = tmp_path / "outside.zip"
    outside.write_bytes(b"not a bundle")
    completed.zip_path = str(outside)
    with pytest.raises(ValueError, match="outside controlled storage"):
        service.download_path(completed)


@pytest.mark.asyncio
async def test_pending_export_can_be_cancelled_and_will_not_execute(export_context):
    session, export_root, _agent, _records = export_context
    service = MemoryExportService(session, export_root)
    job = await service.create_job(MemoryExportRequest(include_private=False))
    await session.commit()

    cancelled = await service.cancel(job.id)
    attempted = await service.execute(job.id)

    assert cancelled.status == "cancelled"
    assert attempted.status == "cancelled"
    assert not (export_root / job.id).exists()


def test_memory_export_api_surface_is_registered():
    routes = {
        (method, route.path)
        for route in memory_router.routes
        for method in (route.methods or set())
        if "/export" in route.path
    }

    assert {
        ("POST", "/memory/export/preview"),
        ("POST", "/memory/export"),
        ("GET", "/memory/export/history"),
        ("GET", "/memory/export/{export_id}"),
        ("POST", "/memory/export/{export_id}/cancel"),
        ("GET", "/memory/export/{export_id}/download"),
    } <= routes


@pytest.mark.asyncio
async def test_archives_only_and_sticky_exclusion_filters(export_context):
    session, export_root, agent, _records = export_context
    service = MemoryExportService(session, export_root)

    archives = await service.preview(MemoryExportRequest(
        scope="archives",
        agent_id=agent.id,
        include_private=False,
    ))
    without_sticky = await service.preview(MemoryExportRequest(
        scope="all",
        agent_id=agent.id,
        include_archives=False,
        include_private=True,
        include_sticky=False,
    ))

    assert archives["estimated_counts"]["archives"] == 1
    assert archives["estimated_counts"]["memories"] == 0
    assert without_sticky["estimated_counts"]["sticky"] == 0
    assert without_sticky["estimated_counts"]["memories"] == 1


@pytest.mark.asyncio
async def test_partial_renderer_failure_keeps_valid_bundle(export_context, monkeypatch):
    session, export_root, agent, records = export_context
    service = MemoryExportService(session, export_root)
    original_render = service.renderer.render

    def render(record, **kwargs):
        if record.id == records[0].id:
            raise ValueError("simulated render failure")
        return original_render(record, **kwargs)

    monkeypatch.setattr(service.renderer, "render", render)
    job = await service.create_job(MemoryExportRequest(
        agent_id=agent.id,
        include_archives=False,
        include_private=False,
        private_export_confirmed=False,
    ))
    await session.commit()

    completed = await service.execute(job.id)
    manifest = json.loads((export_root / job.id / "manifest.json").read_text(encoding="utf-8"))

    assert completed.status == "completed_with_warnings"
    assert completed.counts_json["files"] == 0
    assert any("simulated render failure" in warning for warning in manifest["warnings"])


def test_export_filter_validation_rejects_ambiguous_scopes_and_dates():
    with pytest.raises(ValueError, match="agent_id is required"):
        MemoryExportRequest(scope="agent")
    with pytest.raises(ValueError, match="project_id is required"):
        MemoryExportRequest(scope="project")
    with pytest.raises(ValueError, match="date_from"):
        MemoryExportRequest(
            date_from=datetime(2026, 7, 19, tzinfo=timezone.utc),
            date_to=datetime(2026, 7, 18, tzinfo=timezone.utc),
        )


@pytest.mark.asyncio
async def test_empty_export_still_produces_valid_portable_bundle(export_context):
    session, export_root, _agent, _records = export_context
    service = MemoryExportService(session, export_root)
    job = await service.create_job(MemoryExportRequest(
        memory_types=["nonexistent"],
        include_private=False,
    ))
    await session.commit()

    completed = await service.execute(job.id)
    manifest = json.loads((export_root / job.id / "manifest.json").read_text(encoding="utf-8"))

    assert completed.status == "completed"
    assert manifest["counts"]["total"] == 0
    assert manifest["files"] == []
    assert (export_root / job.id / "README.md").is_file()
