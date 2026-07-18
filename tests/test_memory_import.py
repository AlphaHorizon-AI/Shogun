from __future__ import annotations

import io
import uuid
import zipfile
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import shogun.db.models  # noqa: F401
import shogun.services.memory_import_service as import_module
from shogun.api.memory import router as memory_router
from shogun.db.base import Base
from shogun.db.models.agent import Agent
from shogun.db.models.memory_record import MemoryRecord
from shogun.services.event_logger import EventLogger
from shogun.services.memory_import_service import (
    MarkdownMemoryParser,
    MemoryImportService,
    content_hash,
    normalize_decay,
    normalize_importance,
    normalize_memory_type,
    normalize_tags,
    safe_archive_name,
    zip_info_is_symlink,
)


class FakeVectorStore:
    def __init__(self):
        self.points: dict[str, dict] = {}
        self.fail = False

    def upsert(self, memory_id, text, payload):
        if self.fail:
            raise RuntimeError("simulated Qdrant failure")
        self.points[memory_id] = {"text": text, "payload": payload}

    def delete_point(self, memory_id):
        self.points.pop(memory_id, None)


@pytest.fixture
async def import_context(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    vector_store = FakeVectorStore()

    async def no_audit(*_args, **_kwargs):
        return "evt_test"

    monkeypatch.setattr(EventLogger, "emit", no_audit)
    monkeypatch.setattr(import_module, "get_vector_store", lambda: vector_store)
    async with sessions() as session:
        agent = Agent(
            id=uuid.uuid4(),
            agent_type="shogun",
            name="Max",
            slug=f"max-import-{uuid.uuid4().hex[:6]}",
            status="active",
            is_primary=True,
        )
        session.add(agent)
        await session.commit()
        yield session, agent, vector_store
    await engine.dispose()


def markdown(**overrides) -> bytes:
    fields = {
        "id": "openclaw_123",
        "title": "Routing strategy",
        "memory_type": "decision",
        "importance": 8,
        "decay_type": "sticky",
        "tags": ["shogun", "routing"],
        "created_at": "2026-07-16T10:15:00Z",
        "source": "openclaw",
    }
    fields.update(overrides)
    lines = ["---"]
    for key, value in fields.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            lines.extend(f"  - {item}" for item in value)
        else:
            lines.append(f"{key}: {value}")
    lines.extend(["---", "", "The user prefers governed model routing."])
    return "\n".join(lines).encode()


def test_parser_preserves_markdown_and_normalizes_metadata():
    parsed = MarkdownMemoryParser().parse(
        "decision.md",
        markdown(type="pref", weight="high", labels="alpha, beta", decay_type="normal"),
        defaults={"memory_type": "semantic", "importance": 5, "decay_type": "medium"},
    )

    assert parsed["body"] == "The user prefers governed model routing."
    assert parsed["memory_type"] == "persona"
    assert parsed["importance"] == 8
    assert parsed["decay_type"] == "medium"
    assert parsed["tags"] == ["alpha", "beta"]
    assert parsed["source_external_id"] == "openclaw_123"


def test_parser_without_frontmatter_extracts_heading_and_warns():
    parsed = MarkdownMemoryParser().parse(
        "plain.md",
        b"# Project Context\n\n- Keep tables\n- Keep code blocks",
        defaults={"memory_type": "semantic", "importance": 5, "decay_type": "medium"},
    )

    assert parsed["title"] == "Project Context"
    assert parsed["body"].startswith("# Project Context")
    assert any("Missing frontmatter" in warning for warning in parsed["warnings"])


def test_normalizers_and_content_hash_are_stable():
    assert normalize_tags("one, two;one") == ["one", "two"]
    assert normalize_importance(0.8)[0] == 8
    assert normalize_importance(99)[0] == 10
    assert normalize_memory_type("skill_note")[0] == "skills"
    assert normalize_memory_type("unrecognized")[0] == "semantic"
    assert normalize_decay("normal")[0] == "medium"
    assert content_hash("Title", "Some   BODY") == content_hash(" title ", "some body")


@pytest.mark.parametrize(
    "name", ["../../outside.md", "/etc/passwd.md", r"C:\Users\user\.ssh\id.md", "nested/../../../escape.md"]
)
def test_zip_paths_are_rejected(name):
    assert safe_archive_name(name) is False


def test_zip_symlink_entries_are_rejected():
    info = zipfile.ZipInfo("linked.md")
    info.create_system = 3
    info.external_attr = 0o120777 << 16
    assert zip_info_is_symlink(info) is True


def test_single_file_size_limit_marks_candidate_invalid(monkeypatch):
    config = import_module.memory_import_config()
    config["max_single_file_mb"] = 0
    monkeypatch.setattr(import_module, "memory_import_config", lambda: config)
    items = MemoryImportService(None)._expand_uploads([("large.md", b"content")])
    assert items == [("large.md", b"content", "File exceeds configured size limit")]


@pytest.mark.asyncio
async def test_zip_preview_blocks_traversal_but_keeps_valid_items(import_context):
    session, agent, _store = import_context
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("safe/memory.md", markdown())
        archive.writestr("../../outside.md", b"malicious")
        archive.writestr("manifest.json", "{}")

    batch = await MemoryImportService(session).preview_uploads(
        [("bundle.zip", buffer.getvalue())],
        agent_id=agent.id,
    )
    items = await MemoryImportService(session)._items(batch.id)

    assert batch.total_files == 2
    assert {item.status for item in items} == {"valid", "invalid"}
    assert next(item for item in items if item.status == "invalid").error_json["message"] == "Unsafe ZIP path rejected"


@pytest.mark.asyncio
async def test_preview_confirm_creates_native_memory_and_qdrant_payload(import_context):
    session, agent, store = import_context
    service = MemoryImportService(session)
    batch = await service.preview_uploads([("memory.md", markdown())], agent_id=agent.id)

    assert await session.scalar(select(func.count()).select_from(MemoryRecord)) == 0
    completed = await service.confirm(batch.id)
    await session.commit()
    record = (await session.execute(select(MemoryRecord))).scalar_one()

    assert completed.status == "completed"
    assert completed.imported_count == completed.embedded_count == 1
    assert record.source_type == "openclaw_md_import"
    assert record.source_system == "openclaw"
    assert record.source_external_id == "openclaw_123"
    assert record.import_batch_id == batch.id
    assert record.memory_type == "procedural"
    assert record.importance_score == 0.8
    assert record.tags == ["shogun", "routing"]
    assert str(record.id) in store.points
    assert store.points[str(record.id)]["payload"]["import_batch_id"] == batch.id


@pytest.mark.asyncio
async def test_exact_duplicates_are_detected_and_skipped(import_context):
    session, agent, _store = import_context
    service = MemoryImportService(session)
    first = await service.preview_uploads([("first.md", markdown())], agent_id=agent.id)
    await service.confirm(first.id)
    second = await service.preview_uploads([("again.md", markdown())], agent_id=agent.id)
    items = await service._items(second.id)

    assert items[0].status == "duplicate"
    completed = await service.confirm(second.id)
    assert completed.skipped_count == 1
    assert await session.scalar(select(func.count()).select_from(MemoryRecord)) == 1


@pytest.mark.asyncio
async def test_external_id_conflict_does_not_overwrite_existing_memory(import_context):
    session, agent, _store = import_context
    service = MemoryImportService(session)
    first = await service.preview_uploads([("first.md", markdown())], agent_id=agent.id)
    await service.confirm(first.id)
    conflict = await service.preview_uploads(
        [("changed.md", markdown(title="Changed", id="openclaw_123"))],
        agent_id=agent.id,
    )
    item = (await service._items(conflict.id))[0]

    assert item.duplicate_kind == "conflict_external_id"
    completed = await service.confirm(conflict.id, conflict_policy="skip")
    records = list((await session.execute(select(MemoryRecord))).scalars())
    assert completed.skipped_count == 1
    assert len(records) == 1
    assert records[0].title == "Routing strategy"


@pytest.mark.asyncio
async def test_embedding_failure_is_partial_and_retryable(import_context):
    session, agent, store = import_context
    store.fail = True
    service = MemoryImportService(session)
    batch = await service.preview_uploads([("memory.md", markdown())], agent_id=agent.id)
    partial = await service.confirm(batch.id)

    assert partial.status == "completed_with_warnings"
    assert (await service._items(batch.id))[0].status == "partial_failed"
    assert await session.scalar(select(func.count()).select_from(MemoryRecord)) == 1

    store.fail = False
    repaired = await service.retry_embeddings(batch.id)
    assert repaired.status == "completed"
    assert repaired.embedded_count == 1
    assert (await service._items(batch.id))[0].status == "embedded"


@pytest.mark.asyncio
async def test_rollback_removes_only_batch_memories_and_vectors(import_context):
    session, agent, store = import_context
    native = MemoryRecord(memory_type="semantic", agent_id=agent.id, title="Existing", content="Keep me")
    session.add(native)
    await session.flush()
    service = MemoryImportService(session)
    batch = await service.preview_uploads([("memory.md", markdown())], agent_id=agent.id)
    await service.confirm(batch.id)
    imported_id = (await service._items(batch.id))[0].shogun_memory_id

    rolled_back = await service.rollback(batch.id)
    await session.commit()

    assert rolled_back.status == "rolled_back"
    assert await session.get(MemoryRecord, native.id) is not None
    assert await session.get(MemoryRecord, uuid.UUID(imported_id)) is None
    assert imported_id not in store.points


@pytest.mark.asyncio
async def test_folder_preview_recurses_markdown_only(import_context, tmp_path: Path):
    session, agent, _store = import_context
    (tmp_path / "nested").mkdir()
    (tmp_path / "one.md").write_bytes(markdown(id="one"))
    (tmp_path / "nested" / "two.md").write_bytes(markdown(id="two", title="Second"))
    (tmp_path / "ignored.txt").write_text("ignored")

    batch = await MemoryImportService(session).preview_folder(tmp_path, agent_id=agent.id)

    assert batch.total_files == 2
    assert {item.source_file for item in await MemoryImportService(session)._items(batch.id)} == {
        "one.md",
        "nested/two.md",
    }


def test_memory_import_api_surface_is_registered():
    routes = {(method, route.path) for route in memory_router.routes for method in (route.methods or set())}
    assert {
        ("POST", "/memory/import/openclaw/preview"),
        ("POST", "/memory/import/openclaw/confirm"),
        ("GET", "/memory/import/batches"),
        ("GET", "/memory/import/batches/{batch_id}"),
        ("POST", "/memory/import/batches/{batch_id}/rollback"),
        ("POST", "/memory/import/batches/{batch_id}/retry-embeddings"),
        ("GET", "/memory/import/batches/{batch_id}/report"),
    } <= routes
