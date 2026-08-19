"""Pydantic contracts for deterministic Mapping / RPA execution."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

MappingTypeName = Literal[
    "any",
    "string",
    "integer",
    "number",
    "decimal",
    "boolean",
    "date",
    "datetime",
    "currency",
    "array",
    "object",
]
OutputType = Literal["table", "range", "cells", "object"]


class MappingTransform(BaseModel):
    name: str
    options: dict[str, Any] = Field(default_factory=dict)


class MappingRule(BaseModel):
    source: str | None = None
    target: str
    type: MappingTypeName = "any"
    required: bool = False
    default: Any = None
    has_default: bool = False
    aliases: list[str] = Field(default_factory=list)
    transform: list[str | MappingTransform | dict[str, Any]] = Field(default_factory=list)
    expression: str | None = None
    condition: str | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_rule(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        if "default" in normalized and "has_default" not in normalized:
            normalized["has_default"] = True
        transforms = normalized.get("transform", [])
        if isinstance(transforms, (str, dict)):
            normalized["transform"] = [transforms]
        return normalized

    @model_validator(mode="after")
    def validate_source(self):
        if not self.source and not self.expression and not self.has_default:
            raise ValueError("mapping rule requires source, expression, or default")
        if not self.target.strip():
            raise ValueError("mapping target cannot be empty")
        return self


class MappingOutputConfig(BaseModel):
    type: OutputType = "table"
    start_cell: str = "A1"
    sheet: str | None = None
    include_headers: bool = False

    @model_validator(mode="after")
    def validate_start_cell(self):
        if self.type in {"table", "range"} and not re.fullmatch(r"[A-Za-z]{1,3}[1-9][0-9]*", self.start_cell):
            raise ValueError("output.start_cell must be an Excel cell such as A1 or B12")
        return self


class MappingTransformationProfile(BaseModel):
    """Explicit, flow-scoped deterministic transformation configuration."""

    # Enterprise ingress profiles are versioned data manifests. Keep their
    # vendor/source/contract metadata intact when an AgentFlow node snapshots a
    # registry profile, while retaining the compact SAP contract shape.
    model_config = ConfigDict(extra="allow")

    id: str = Field(min_length=1, max_length=255, pattern=r"^[A-Za-z0-9_.-]+$")
    adapter: str = Field(min_length=1, max_length=255, pattern=r"^[A-Za-z0-9_.-]+$")
    parameters: dict[str, Any] = Field(default_factory=dict)
    model_fallback: bool = False
    registry_version: int | None = Field(default=None, ge=1)
    content_hash: str | None = Field(default=None, min_length=64, max_length=64, pattern=r"^[a-fA-F0-9]{64}$")

    @model_validator(mode="after")
    def validate_registry_pin(self):
        """Require an all-or-nothing immutable registry pin."""

        if (self.registry_version is None) != (self.content_hash is None):
            raise ValueError(
                "transformation_profile registry_version and content_hash must be supplied together"
            )
        if self.content_hash is not None:
            self.content_hash = self.content_hash.lower()
        return self

    @property
    def is_registry_pinned(self) -> bool:
        return self.registry_version is not None and self.content_hash is not None


class MappingConfig(BaseModel):
    version: int = Field(default=1, ge=1)
    name: str = Field(default="Mapping / RPA", min_length=1, max_length=255)
    execution_mode: Literal["transform", "contract", "profile"] = "transform"
    mode: Literal["strict", "lenient"] = "strict"
    input_path: str | None = None
    input_source_node_id: str | None = None
    delimiter: str | None = None
    output: MappingOutputConfig = Field(default_factory=MappingOutputConfig)
    mappings: list[MappingRule] = Field(default_factory=list, max_length=500)
    aliases: dict[str, list[str]] = Field(default_factory=dict)
    duplicate_key: str | None = None
    duplicate_policy: Literal["allow", "skip", "replace", "merge", "error"] = "allow"
    on_record_error: Literal["fail", "skip"] = "fail"
    route_failures: bool = True
    confidence_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    retain_lineage: bool = True
    include_metadata: bool = False
    transformation_profile: MappingTransformationProfile | None = None

    @model_validator(mode="after")
    def validate_targets(self):
        if self.execution_mode == "transform" and not self.mappings:
            raise ValueError("transform execution requires at least one mapping rule")
        if self.execution_mode in {"contract", "profile"} and self.transformation_profile is None:
            raise ValueError(f"{self.execution_mode} execution requires a transformation_profile")
        if self.execution_mode == "contract" and self.mappings:
            raise ValueError("contract execution uses its resolved transformation profile; mappings must be empty")
        if self.execution_mode == "profile":
            if self.mappings:
                raise ValueError("profile execution uses transformation_profile.field_map; mappings must be empty")
            if self.output.type not in {"table", "range"}:
                raise ValueError("profile execution currently supports table or range output")
        targets = [rule.target.upper() for rule in self.mappings]
        if len(targets) != len(set(targets)):
            raise ValueError("mapping targets must be unique")
        if self.output.type == "cells":
            invalid = [target for target in targets if not re.fullmatch(r"[A-Z]{1,3}[1-9][0-9]*", target)]
            if invalid:
                raise ValueError(f"cell output requires cell targets; invalid: {', '.join(invalid)}")
        if self.output.type in {"table", "range"}:
            invalid = [target for target in targets if not re.fullmatch(r"[A-Z]{1,3}", target)]
            if invalid:
                raise ValueError(f"table/range output requires Excel column targets; invalid: {', '.join(invalid)}")
        return self


class MappingPreviewRequest(BaseModel):
    config: MappingConfig
    input: Any


class MappingTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    scope: Literal["private", "team", "global"] = "private"
    owner_id: str = Field(default="system", min_length=1, max_length=255)
    team_id: str | None = Field(default=None, max_length=255)
    config: MappingConfig

    @model_validator(mode="after")
    def validate_scope(self):
        if self.scope == "team" and not self.team_id:
            raise ValueError("team_id is required for a team mapping template")
        return self


class MappingTemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    scope: Literal["private", "team", "global"] | None = None
    team_id: str | None = Field(default=None, max_length=255)
    config: MappingConfig | None = None
