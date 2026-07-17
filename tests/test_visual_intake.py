from __future__ import annotations

import io

import pytest
from PIL import Image
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import shogun.db.models  # noqa: F401 - registers all tables
from shogun.config import settings
from shogun.db.base import Base
from shogun.services.visual_intake import VisualIntakeError, VisualIntakeService


def _png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (120, 80), (15, 90, 160)).save(buffer, "PNG")
    return buffer.getvalue()


@pytest.fixture
async def visual_service(tmp_path, monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    monkeypatch.setattr(settings, "visual_artifacts_path", tmp_path / "images")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield VisualIntakeService(session)
    await engine.dispose()


@pytest.mark.asyncio
async def test_image_intake_creates_thumbnail_metadata_and_deduplicates(visual_service):
    first = await visual_service.ingest(_png(), filename="screen.png", source="chat", chat_session_id="one")
    second = await visual_service.ingest(_png(), filename="again.png", source="chat", chat_session_id="one")

    assert first.id == second.id
    assert first.width == 120 and first.height == 80
    assert first.mime_type == "image/png"
    assert first.pinned is False
    assert (
        settings.visual_artifacts_path / first.created_at.strftime("%Y/%m/%d") / str(first.id) / "thumbnail.webp"
    ).is_file()


@pytest.mark.asyncio
async def test_image_intake_rejects_fake_image(visual_service):
    with pytest.raises(VisualIntakeError, match="valid, safe image"):
        await visual_service.ingest(b"not an image", filename="fake.png", declared_mime="image/png")


@pytest.mark.asyncio
async def test_deleted_image_is_not_returned(visual_service):
    artifact = await visual_service.ingest(_png(), filename="screen.png")
    await visual_service.delete(artifact)
    assert await visual_service.get(artifact.id) is None
