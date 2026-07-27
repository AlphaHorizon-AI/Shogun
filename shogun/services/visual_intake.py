"""Secure, source-neutral image intake and vision analysis."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.config import settings
from shogun.db.models.stack_orchestrator import StackArtifact, StackRun
from shogun.db.models.visual_artifact import ChatArtifactLink, ImageAnalysis, ImageArtifact

ALLOWED_FORMATS = {
    "JPEG": ("image/jpeg", ".jpg"),
    "PNG": ("image/png", ".png"),
    "WEBP": ("image/webp", ".webp"),
    "GIF": ("image/gif", ".gif"),
}


class VisualIntakeError(ValueError):
    pass


class VisualIntakeService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def permissions(self) -> dict:
        """Resolve enforced visual permissions; privacy-sensitive options default off."""
        from shogun.db.models.agent import Agent
        from shogun.db.models.security_policy import SecurityPolicy

        defaults = {
            "allow_image_intake": True,
            "allow_local_vision": True,
            "allow_cloud_vision": False,
            "allow_ocr": True,
            "allow_attach_to_stack": True,
            "allow_auto_memory": False,
            "allow_delete": True,
        }
        agent = await self.session.scalar(
            select(Agent).where(Agent.agent_type == "shogun", Agent.is_deleted.is_(False)).limit(1)
        )
        configured: dict = {}
        if agent:
            configured = ((agent.bushido_settings or {}).get("custom_permissions") or {}).get("visual_intake", {})
            if not configured and agent.security_policy_id:
                policy = await self.session.get(SecurityPolicy, agent.security_policy_id)
                configured = ((policy.permissions if policy else {}) or {}).get("visual_intake", {})
        return {**defaults, **configured}

    @staticmethod
    def _public(artifact: ImageArtifact) -> dict:
        aid = str(artifact.id)
        return {
            "type": "image",
            "artifact_id": aid,
            "source": artifact.source,
            "filename": artifact.original_filename,
            "mime_type": artifact.mime_type,
            "size": artifact.byte_size,
            "width": artifact.width,
            "height": artifact.height,
            "caption": artifact.caption,
            "status": artifact.analysis_status,
            "pinned": artifact.pinned,
            "created_at": artifact.created_at.isoformat(),
            "content_url": f"/api/v1/visual/{aid}/content",
            "thumbnail_url": f"/api/v1/visual/{aid}/thumbnail",
        }

    @staticmethod
    def _vision_data_url(path: str) -> str:
        """Return a metadata-free PNG payload accepted by local and cloud vision APIs."""
        output = io.BytesIO()
        with Image.open(path) as image:
            normalized = image.convert("RGB") if image.mode not in ("RGB", "RGBA") else image.copy()
            normalized.save(output, "PNG", optimize=True)
        return f"data:image/png;base64,{base64.b64encode(output.getvalue()).decode('ascii')}"

    async def ingest(
        self,
        content: bytes,
        *,
        filename: str,
        declared_mime: str | None = None,
        source: str = "chat",
        source_chat_id: str | None = None,
        source_message_id: str | None = None,
        sender_id: str | None = None,
        caption: str | None = None,
        chat_session_id: str | None = None,
    ) -> ImageArtifact:
        if not (await self.permissions()).get("allow_image_intake", True):
            raise VisualIntakeError("Image intake is disabled by the Shogun visual intake policy.")
        if not content:
            raise VisualIntakeError("The image is empty.")
        if len(content) > settings.visual_max_upload_mb * 1024 * 1024:
            raise VisualIntakeError(f"Images may be at most {settings.visual_max_upload_mb} MB.")
        try:
            with Image.open(io.BytesIO(content)) as probe:
                fmt = str(probe.format or "").upper()
                probe.verify()
            if fmt not in ALLOWED_FORMATS:
                raise VisualIntakeError("Supported image formats are JPEG, PNG, WebP, and static GIF.")
            image = Image.open(io.BytesIO(content))
            image.seek(0)
            image = ImageOps.exif_transpose(image)
            image.load()
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
            raise VisualIntakeError("The upload is not a valid, safe image.") from exc

        mime_type, extension = ALLOWED_FORMATS[fmt]
        if declared_mime and declared_mime.startswith("image/") and declared_mime != mime_type:
            # Trust decoded bytes, not the user-controlled header.
            declared_mime = mime_type
        digest = hashlib.sha256(content).hexdigest()
        existing = await self.session.scalar(
            select(ImageArtifact).where(ImageArtifact.sha256 == digest, ImageArtifact.is_deleted.is_(False)).limit(1)
        )
        if existing:
            self.session.add(
                ChatArtifactLink(
                    artifact_id=existing.id,
                    chat_session_id=chat_session_id or source_chat_id,
                    external_message_id=source_message_id,
                    source=source,
                )
            )
            await self.session.flush()
            return existing

        artifact_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        folder = (
            settings.visual_artifacts_path
            / now.strftime("%Y")
            / now.strftime("%m")
            / now.strftime("%d")
            / str(artifact_id)
        )
        folder.mkdir(parents=True, exist_ok=False)
        original_path = folder / f"original{extension}"
        normalized_path = folder / "normalized.webp"
        thumbnail_path = folder / "thumbnail.webp"
        original_path.write_bytes(content)

        normalized = image.convert("RGB") if image.mode not in ("RGB", "RGBA") else image.copy()
        normalized.save(normalized_path, "WEBP", quality=92, method=6)
        thumb = normalized.copy()
        thumb.thumbnail((640, 640), Image.Resampling.LANCZOS)
        thumb.save(thumbnail_path, "WEBP", quality=82, method=6)

        artifact = ImageArtifact(
            id=artifact_id,
            source=source,
            source_message_id=source_message_id,
            source_chat_id=source_chat_id,
            sender_id=sender_id,
            original_filename=Path(filename or f"image{extension}").name[:500],
            mime_type=mime_type,
            byte_size=len(content),
            width=image.width,
            height=image.height,
            color_mode=image.mode,
            has_exif=bool(image.getexif()),
            sha256=digest,
            original_path=str(original_path),
            normalized_path=str(normalized_path),
            thumbnail_path=str(thumbnail_path),
            caption=caption,
            retention_expires_at=now + timedelta(days=settings.visual_retention_days),
            metadata_json={
                "decoded_format": fmt,
                "declared_mime": declared_mime,
                "animated_frames": getattr(image, "n_frames", 1),
            },
        )
        self.session.add(artifact)
        await self.session.flush()
        self.session.add(
            ChatArtifactLink(
                artifact_id=artifact.id,
                chat_session_id=chat_session_id or source_chat_id,
                external_message_id=source_message_id,
                source=source,
            )
        )
        metadata = self._public(artifact) | {
            "sha256": digest,
            "retention_expires_at": artifact.retention_expires_at.isoformat(),
        }
        (folder / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        if caption:
            (folder / "caption.json").write_text(json.dumps({"caption": caption}, indent=2), encoding="utf-8")
        return artifact

    async def get(self, artifact_id: uuid.UUID, *, include_deleted: bool = False) -> ImageArtifact | None:
        query = select(ImageArtifact).where(ImageArtifact.id == artifact_id)
        if not include_deleted:
            query = query.where(ImageArtifact.is_deleted.is_(False))
        return await self.session.scalar(query)

    async def recent(self, limit: int = 30, chat_session_id: str | None = None) -> list[ImageArtifact]:
        query = select(ImageArtifact).where(ImageArtifact.is_deleted.is_(False))
        if chat_session_id:
            query = query.join(ChatArtifactLink).where(ChatArtifactLink.chat_session_id == chat_session_id)
        result = await self.session.execute(query.order_by(ImageArtifact.created_at.desc()).limit(min(limit, 100)))
        return list(result.scalars().unique().all())

    async def resolve_attachments(self, attachments: list[dict]) -> list[dict]:
        resolved: list[dict] = []
        for item in attachments:
            raw_id = item.get("artifact_id") or item.get("artifactId")
            if not raw_id:
                # Never trust client-provided paths. Attachments must refer to a
                # server-side artifact created by the visual intake service.
                continue
            try:
                artifact = await self.get(uuid.UUID(str(raw_id)))
            except ValueError:
                artifact = None
            if artifact:
                resolved.append(self._public(artifact) | {"path": artifact.normalized_path})
        return resolved

    async def analyze(
        self, artifact: ImageArtifact, prompt: str, analysis_type: str = "describe", allow_cloud: bool = False
    ) -> ImageAnalysis:
        from shogun.engine.flow_engine import _call_llm_chain, _resolve_task_llm_chain

        permissions = await self.permissions()
        allow_cloud = bool(allow_cloud and permissions.get("allow_cloud_vision", False))
        chain, _routing = await _resolve_task_llm_chain(
            self.session,
            prompt=prompt,
            task_type="visual_understanding",
            required_capabilities=["chat", "vision"],
            context_size_estimate=len(prompt),
            local_only=not allow_cloud,
        )
        if not permissions.get("allow_local_vision", True):
            chain = [
                entry
                for entry in chain
                if not (entry[0].is_local or entry[0].provider_type in {"ollama", "lmstudio", "local"})
            ]
        if not allow_cloud:
            chain = [
                entry
                for entry in chain
                if entry[0].is_local or entry[0].provider_type in {"ollama", "lmstudio", "local"}
            ]
        if not chain:
            raise VisualIntakeError(
                "No permitted vision-capable model is connected. Enable cloud vision or connect a local vision model."
            )
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": self._vision_data_url(artifact.normalized_path)},
                    },
                ],
            }
        ]
        result = await _call_llm_chain(
            messages,
            chain,
            timeout=180,
            retry_count=0,
            context="visual analysis",
            max_tokens=192,
            routing_context=_routing,
            usage_session=self.session,
        )
        provider, model_name, _, _ = chain[0]
        analysis = ImageAnalysis(
            artifact_id=artifact.id,
            analysis_type=analysis_type,
            prompt=prompt,
            result_text=result,
            model_used=model_name,
            provider_used=provider.name,
        )
        artifact.analysis_status = "analyzed"
        self.session.add(analysis)
        await self.session.flush()
        return analysis

    async def compare(
        self, first: ImageArtifact, second: ImageArtifact, prompt: str, allow_cloud: bool = False
    ) -> ImageAnalysis:
        from shogun.engine.flow_engine import _call_llm_chain, _resolve_task_llm_chain

        permissions = await self.permissions()
        allow_cloud = bool(allow_cloud and permissions.get("allow_cloud_vision", False))
        chain, _routing = await _resolve_task_llm_chain(
            self.session,
            prompt=prompt,
            task_type="visual_self_verification",
            required_capabilities=["chat", "vision", "reasoning"],
            context_size_estimate=len(prompt),
            local_only=not allow_cloud,
        )
        if not permissions.get("allow_local_vision", True):
            chain = [
                entry
                for entry in chain
                if not (entry[0].is_local or entry[0].provider_type in {"ollama", "lmstudio", "local"})
            ]
        if not allow_cloud:
            chain = [
                entry
                for entry in chain
                if entry[0].is_local or entry[0].provider_type in {"ollama", "lmstudio", "local"}
            ]
        if not chain:
            raise VisualIntakeError("No permitted vision-capable model is connected.")
        content: list[dict] = [{"type": "text", "text": prompt}]
        for label, artifact in (("FIRST IMAGE", first), ("SECOND IMAGE", second)):
            content.append({"type": "text", "text": label})
            content.append({"type": "image_url", "image_url": {"url": self._vision_data_url(artifact.normalized_path)}})
        result = await _call_llm_chain(
            [{"role": "user", "content": content}],
            chain,
            timeout=180,
            retry_count=0,
            context="visual comparison",
            max_tokens=256,
            routing_context=_routing,
            usage_session=self.session,
        )
        provider, model_name, _, _ = chain[0]
        analysis = ImageAnalysis(
            artifact_id=first.id,
            analysis_type="compare",
            prompt=prompt,
            result_text=result,
            model_used=model_name,
            provider_used=provider.name,
            metadata_json={"compared_with": str(second.id)},
        )
        self.session.add(analysis)
        await self.session.flush()
        return analysis

    async def attach_to_stack(self, artifact: ImageArtifact, stack_run_id: uuid.UUID) -> StackArtifact:
        if not (await self.permissions()).get("allow_attach_to_stack", True):
            raise VisualIntakeError("Image-to-stack attachment is disabled by the Shogun visual intake policy.")
        if not await self.session.get(StackRun, stack_run_id):
            raise VisualIntakeError("Stack run not found.")
        linked = StackArtifact(
            stack_run_id=stack_run_id,
            artifact_type="image",
            path=artifact.normalized_path,
            summary=artifact.caption or artifact.original_filename,
            metadata_json={"image_artifact_id": str(artifact.id), **self._public(artifact)},
        )
        artifact.pinned = True
        self.session.add(linked)
        await self.session.flush()
        return linked

    async def delete(self, artifact: ImageArtifact) -> None:
        if not (await self.permissions()).get("allow_delete", True):
            raise VisualIntakeError("Image deletion is disabled by the Shogun visual intake policy.")
        artifact.is_deleted = True
        artifact.deleted_at = datetime.now(timezone.utc)
        await self.session.flush()

    async def cleanup_expired(self) -> int:
        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            select(ImageArtifact).where(
                ImageArtifact.is_deleted.is_(False),
                ImageArtifact.pinned.is_(False),
                ImageArtifact.retention_expires_at.is_not(None),
                ImageArtifact.retention_expires_at < now,
            )
        )
        count = 0
        for artifact in result.scalars():
            folder = Path(artifact.original_path).parent
            artifact.is_deleted = True
            artifact.deleted_at = now
            if folder.is_dir() and settings.visual_artifacts_path.resolve() in folder.resolve().parents:
                shutil.rmtree(folder)
            count += 1
        await self.session.flush()
        return count
