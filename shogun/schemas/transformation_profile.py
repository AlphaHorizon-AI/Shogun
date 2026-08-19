"""API contracts for the governed transformation profile registry."""

from __future__ import annotations

import json
import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ProfileLifecycle = Literal["candidate", "validated", "active", "retired"]
AdapterAvailability = Literal["available", "planned", "unavailable", "disabled", "error"]


class TransformationProfileCandidateCreate(BaseModel):
    """Create a learned or tenant profile as a non-executable candidate."""

    model_config = ConfigDict(extra="forbid")

    profile_id: str = Field(min_length=1, max_length=255, pattern=r"^[A-Za-z0-9_.-]+$")
    display_name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    platform: str = Field(default="generic", min_length=1, max_length=100)
    domain: str = Field(default="document", min_length=1, max_length=100)
    adapter_id: str = Field(min_length=1, max_length=255, pattern=r"^[A-Za-z0-9_.-]+$")
    definition: dict[str, Any]
    parent_version_id: uuid.UUID | None = None
    origin: Literal["skillopt", "tenant", "operator"] = "skillopt"
    actor: str = Field(default="system", min_length=1, max_length=255)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def definition_matches_identity(self):
        declared_id = str(self.definition.get("id") or "").strip()
        if declared_id and declared_id != self.profile_id:
            raise ValueError("definition.id must match profile_id")
        declared_adapter = self.definition.get("adapter")
        if declared_adapter and str(declared_adapter).strip() != self.adapter_id:
            raise ValueError("definition.adapter must match adapter_id")
        encoded = json.dumps(
            {"definition": self.definition, "metadata": self.metadata},
            default=str,
        ).encode()
        if len(encoded) > 2_000_000:
            raise ValueError("Transformation profile candidate exceeds the 2 MB safety limit")
        return self


class TransformationPositiveFixture(BaseModel):
    """Bounded executable example and optional deterministic assertions."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    payload: Any
    context: dict[str, Any] = Field(default_factory=dict)
    expected_record_count: int | None = Field(default=None, ge=0, le=100_000)
    expected_contract_id: str | None = Field(default=None, max_length=255)
    expected_record_kind: str | None = Field(default=None, max_length=255)
    expected_headers: list[str] | None = Field(default=None, max_length=500)
    expected_records: list[dict[str, Any]] | None = Field(default=None, max_length=1_000)


class TransformationNegativeFixture(BaseModel):
    """Input that must be rejected by the selected profile."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    payload: Any
    context: dict[str, Any] = Field(default_factory=dict)
    expected_error_code: str | None = Field(default=None, max_length=100)


class TransformationProfileValidationRequest(BaseModel):
    """Server-executed evidence required before candidate promotion."""

    model_config = ConfigDict(extra="forbid")

    positive_fixtures: list[TransformationPositiveFixture] = Field(
        default_factory=list, max_length=20
    )
    negative_fixtures: list[TransformationNegativeFixture] = Field(
        default_factory=list, max_length=20
    )
    report: dict[str, Any] = Field(default_factory=dict)
    actor: str = Field(default="system", min_length=1, max_length=255)

    @model_validator(mode="after")
    def fixtures_are_bounded(self):
        encoded = json.dumps(
            {
                "positive": [item.model_dump(mode="json") for item in self.positive_fixtures],
                "negative": [item.model_dump(mode="json") for item in self.negative_fixtures],
                "report": self.report,
            },
            default=str,
        ).encode()
        if len(encoded) > 2_000_000:
            raise ValueError("Transformation validation fixtures exceed the 2 MB safety limit")
        return self


class TransformationProfilePromotionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor: str = Field(default="system", min_length=1, max_length=255)


class TransformationProfileRollbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_version: int = Field(ge=1)
    actor: str = Field(default="system", min_length=1, max_length=255)


class TransformationProfileRetireRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, max_length=2000)
    actor: str = Field(default="system", min_length=1, max_length=255)
