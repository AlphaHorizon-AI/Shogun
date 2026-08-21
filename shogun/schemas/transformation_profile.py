"""API contracts for the governed transformation profile registry."""

from __future__ import annotations

import hashlib
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
    expected_rows: list[list[Any]] | None = Field(default=None, max_length=1_000)


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


class PrivateTransformationProfileDocument(BaseModel):
    """Portable JSON file containing one private, declarative profile."""

    model_config = ConfigDict(extra="forbid")

    format: Literal["shogun.private-transformation-profile"] = (
        "shogun.private-transformation-profile"
    )
    format_version: Literal[1] = 1
    content_hash: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[a-fA-F0-9]{64}$",
    )
    profile: dict[str, Any]

    @model_validator(mode="after")
    def file_is_bounded(self):
        profile_hash = hashlib.sha256(
            json.dumps(
                self.profile,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()
        if self.content_hash.lower() != profile_hash:
            raise ValueError(
                "Private transformation profile file content_hash does not match profile"
            )
        self.content_hash = self.content_hash.lower()
        encoded = json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        if len(encoded) > 2_000_000:
            raise ValueError("Private transformation profile file exceeds the 2 MB safety limit")
        return self


class PrivateTransformationProfileExportRequest(BaseModel):
    """Build a portable private file from an inline profile definition."""

    model_config = ConfigDict(extra="forbid")

    profile: dict[str, Any]
    execution_mode: Literal["contract", "profile"] | None = None
    display_name: str | None = Field(default=None, min_length=1, max_length=255)


class PrivateTransformationProfileImportRequest(BaseModel):
    """Validate a portable private file without adding it to the registry."""

    model_config = ConfigDict(extra="forbid")

    document: PrivateTransformationProfileDocument
