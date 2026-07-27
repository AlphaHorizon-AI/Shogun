from __future__ import annotations

import base64
import io
import uuid

import pytest
from PIL import Image
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import shogun.db.models  # noqa: F401 - registers all tables
from shogun.config import settings
from shogun.db.base import Base
from shogun.db.models.model_provider import ModelProvider
from shogun.engine.flow_engine import _resolve_vision_chain
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
    payload = visual_service._vision_data_url(first.normalized_path)
    assert payload.startswith("data:image/png;base64,")
    with Image.open(io.BytesIO(base64.b64decode(payload.split(",", 1)[1]))) as decoded:
        assert decoded.format == "PNG" and decoded.size == (120, 80)


@pytest.mark.asyncio
async def test_image_intake_rejects_fake_image(visual_service):
    with pytest.raises(VisualIntakeError, match="valid, safe image"):
        await visual_service.ingest(b"not an image", filename="fake.png", declared_mime="image/png")


@pytest.mark.asyncio
async def test_deleted_image_is_not_returned(visual_service):
    artifact = await visual_service.ingest(_png(), filename="screen.png")
    await visual_service.delete(artifact)
    assert await visual_service.get(artifact.id) is None


@pytest.mark.asyncio
async def test_attachment_resolution_rejects_client_paths(visual_service, tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("not an image", encoding="utf-8")

    resolved = await visual_service.resolve_attachments([
        {"path": str(secret), "mime_type": "image/png"},
        {"artifact_id": str(uuid.uuid4()), "path": str(secret), "mime_type": "image/png"},
    ])

    assert resolved == []


@pytest.mark.asyncio
async def test_vision_chain_skips_text_model_and_selects_connected_local_vision_model(visual_service):
    text_provider = ModelProvider(
        provider_type="openrouter",
        name="qwen/qwen3-next-80b",
        slug="text-only",
        status="connected",
        is_local=False,
        config={"model_id": "qwen/qwen3-next-80b"},
    )
    vision_provider = ModelProvider(
        provider_type="ollama",
        name="gemma3:12b-it-qat",
        slug="local-vision",
        status="connected",
        is_local=True,
        base_url="http://127.0.0.1:11434",
        config={"model_id": "gemma3:12b-it-qat"},
    )
    visual_service.session.add_all([text_provider, vision_provider])
    await visual_service.session.flush()

    chain = await _resolve_vision_chain(visual_service.session)

    assert [target[1] for target in chain] == ["gemma3:12b-it-qat"]
