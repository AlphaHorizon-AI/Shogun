"""Preview and reusable-template API for the deterministic Mapping / RPA node."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.api.deps import get_db
from shogun.db.models.mapping_template import MappingTemplate
from shogun.mapping.engine import execute_mapping
from shogun.mapping.errors import MappingError, MappingSchemaError
from shogun.mapping.schema import MappingPreviewRequest, MappingTemplateCreate, MappingTemplateUpdate
from shogun.schemas.common import ApiResponse
from shogun.services.enterprise_transformations import execute_enterprise_profile
from shogun.services.private_transformation_profiles import (
    PrivateTransformationProfileError,
    PrivateTransformationProfileService,
)
from shogun.services.transformation_profile_registry import (
    TransformationProfileRegistryError,
    TransformationProfileRegistryService,
)

router = APIRouter(prefix="/mapping-rpa", tags=["Mapping / RPA"])


def _template_data(template: MappingTemplate) -> dict:
    return {
        "id": str(template.id),
        "name": template.name,
        "description": template.description,
        "version": template.version,
        "scope": template.scope,
        "owner_id": template.owner_id,
        "team_id": template.team_id,
        "config": template.config,
        "created_at": template.created_at,
        "updated_at": template.updated_at,
    }


@router.post("/preview", response_model=ApiResponse)
async def preview_mapping(body: MappingPreviewRequest, db: AsyncSession = Depends(get_db)):
    """Run a bounded, side-effect-free preview using the production engine."""
    try:
        if body.config.execution_mode == "profile":
            profile = body.config.transformation_profile
            if profile is None:  # Defensive for direct callers bypassing request validation.
                raise MappingSchemaError(
                    "Mapping / RPA profile preview requires a transformation profile",
                    field="transformation_profile",
                )
            try:
                if profile.is_private_file:
                    definition, evidence = PrivateTransformationProfileService().resolve_reference(
                        profile,
                        execution_mode="profile",
                    )
                else:
                    resolved = await TransformationProfileRegistryService(db).resolve_active_definition(
                        profile.id,
                        expected_version=profile.registry_version,
                        expected_hash=(profile.content_hash.lower() if profile.content_hash else None),
                    )
                    definition = resolved["definition"]
                    evidence = resolved["registry_evidence"]
            except (PrivateTransformationProfileError, TransformationProfileRegistryError) as exc:
                raise MappingSchemaError(str(exc), field="transformation_profile") from exc
            if profile.adapter != evidence.get("adapter_id"):
                raise MappingSchemaError(
                    "Resolved transformation profile adapter does not match the preview configuration",
                    field="transformation_profile.adapter",
                )
            result = execute_enterprise_profile(
                definition,
                body.input,
                context={"preview": True, "node_id": "mapping-rpa-preview"},
                registry_evidence=evidence,
            )
            result.update(
                {
                    "type": body.config.output.type,
                    "start_cell": body.config.output.start_cell,
                    "sheet": body.config.output.sheet,
                    "include_headers": body.config.output.include_headers,
                }
            )
        elif body.config.execution_mode == "contract":
            raise MappingSchemaError(
                "PDF contract mode contributes profile metadata and has no source-row preview",
                field="execution_mode",
            )
        else:
            result = execute_mapping(body.input, body.config)
    except MappingError as exc:
        result = {
            "__shogun_mapping_output__": True,
            "status": exc.code,
            "type": body.config.output.type,
            "records_received": 0,
            "records_written": 0,
            "records_failed": 1,
            "errors": [exc.as_dict()],
        }
    return ApiResponse(data=result)


@router.get("/templates", response_model=ApiResponse)
async def list_mapping_templates(
    owner_id: str = Query(default="system", max_length=255),
    team_id: str | None = Query(default=None, max_length=255),
    db: AsyncSession = Depends(get_db),
):
    visibility = [
        MappingTemplate.scope == "global",
        (MappingTemplate.scope == "private") & (MappingTemplate.owner_id == owner_id),
    ]
    if team_id:
        visibility.append((MappingTemplate.scope == "team") & (MappingTemplate.team_id == team_id))
    result = await db.execute(
        select(MappingTemplate)
        .where(MappingTemplate.is_deleted.is_(False), or_(*visibility))
        .order_by(MappingTemplate.name, MappingTemplate.version.desc())
    )
    records = result.scalars().all()
    return ApiResponse(data=[_template_data(record) for record in records], meta={"total": len(records)})


@router.post("/templates", response_model=ApiResponse, status_code=201)
async def create_mapping_template(body: MappingTemplateCreate, db: AsyncSession = Depends(get_db)):
    record = MappingTemplate(
        name=body.name,
        description=body.description,
        scope=body.scope,
        owner_id=body.owner_id,
        team_id=body.team_id,
        config=body.config.model_dump(mode="json"),
        created_by=body.owner_id,
        updated_by=body.owner_id,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return ApiResponse(data=_template_data(record))


async def _editable_template(template_id: uuid.UUID, actor: str, db: AsyncSession) -> MappingTemplate:
    record = await db.get(MappingTemplate, template_id)
    if not record or record.is_deleted:
        raise HTTPException(404, "Mapping template not found")
    if actor not in {"system", record.owner_id}:
        raise HTTPException(403, "Only the template owner may modify this mapping template")
    return record


@router.put("/templates/{template_id}", response_model=ApiResponse)
async def update_mapping_template(
    template_id: uuid.UUID,
    body: MappingTemplateUpdate,
    actor: str = Query(default="system", max_length=255),
    db: AsyncSession = Depends(get_db),
):
    record = await _editable_template(template_id, actor, db)
    changes = body.model_dump(exclude_unset=True, exclude={"config"})
    for key, value in changes.items():
        setattr(record, key, value)
    if record.scope == "team" and not record.team_id:
        raise HTTPException(422, "team_id is required for a team mapping template")
    if "config" in body.model_fields_set and body.config is not None:
        record.config = body.config.model_dump(mode="json")
    record.version += 1
    record.updated_by = actor
    await db.commit()
    await db.refresh(record)
    return ApiResponse(data=_template_data(record))


@router.delete("/templates/{template_id}", response_model=ApiResponse)
async def delete_mapping_template(
    template_id: uuid.UUID,
    actor: str = Query(default="system", max_length=255),
    db: AsyncSession = Depends(get_db),
):
    record = await _editable_template(template_id, actor, db)
    record.is_deleted = True
    record.deleted_at = datetime.now(timezone.utc)
    record.updated_by = actor
    await db.commit()
    return ApiResponse(data={"id": str(record.id), "deleted": True})
