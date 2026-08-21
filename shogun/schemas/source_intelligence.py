"""Strict contracts for registry-driven source discovery.

Source Intelligence may identify an already trusted transformation profile or
prepare a bounded request for semantic classification.  Semantic
classification is advisory: these contracts deliberately have no field that
can carry executable profile mechanics.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from shogun.mapping.schema import MappingTransformationProfile

MAX_SOURCE_ARTIFACTS = 16
MAX_SOURCE_TEXT_CHARS = 2_097_152
MAX_SOURCE_REQUEST_BYTES = 12_000_000
MAX_CLASSIFIER_REQUEST_BYTES = 256_000
MAX_SEMANTIC_PROFILE_CANDIDATES = 100

SpecialistSkillSlug = Literal[
    "sap-transformation-specialist",
    "d365-transformation-specialist",
    "business-central-transformation-specialist",
    "salesforce-transformation-specialist",
    "oracle-fusion-transformation-specialist",
    "netsuite-transformation-specialist",
    "ifs-cloud-transformation-specialist",
    "epicor-kinetic-transformation-specialist",
    "servicenow-transformation-specialist",
    "hubspot-transformation-specialist",
    "accounting-transformation-specialist",
    "workday-transformation-specialist",
    "enterprise-transformation-architect",
]


class SourceContext(BaseModel):
    """Non-secret provenance and format hints supplied by the ingress node."""

    model_config = ConfigDict(extra="forbid")

    transport: str | None = Field(default=None, max_length=100)
    object: str | None = Field(default=None, max_length=500)
    record_shape: str | None = Field(default=None, max_length=100)
    record_path: str | None = Field(default=None, max_length=500)
    content_type: str | None = Field(default=None, max_length=255)
    file_name: str | None = Field(default=None, max_length=500)
    connector: str | None = Field(default=None, max_length=100)
    platform_hint: str | None = Field(default=None, max_length=100)


class SourceArtifactInput(BaseModel):
    """One bounded text or JSON-like source presented to the resolver."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(min_length=1, max_length=255)
    label: str | None = Field(default=None, max_length=500)
    text: str | None = Field(default=None, max_length=MAX_SOURCE_TEXT_CHARS)
    payload: Any | None = None
    context: SourceContext = Field(default_factory=SourceContext)

    @model_validator(mode="after")
    def exactly_one_source_body(self):
        if (self.text is None) == (self.payload is None):
            raise ValueError("Each source artifact requires exactly one of text or payload")
        if self.payload is not None:
            try:
                encoded = json.dumps(
                    self.payload,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                ).encode("utf-8")
            except (TypeError, ValueError) as exc:
                raise ValueError("Structured source payload must be JSON serializable") from exc
            if len(encoded) > MAX_SOURCE_TEXT_CHARS:
                raise ValueError("Structured source payload exceeds the 2 MiB artifact limit")
        return self


class SourceIntelligenceRequest(BaseModel):
    """Preview or runtime request for known-profile resolution."""

    model_config = ConfigDict(extra="forbid")

    artifacts: list[SourceArtifactInput] = Field(
        min_length=1,
        max_length=MAX_SOURCE_ARTIFACTS,
    )
    private_profiles: list[MappingTransformationProfile] = Field(
        default_factory=list,
        max_length=32,
    )

    @model_validator(mode="after")
    def request_is_bounded(self):
        encoded = json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        if len(encoded) > MAX_SOURCE_REQUEST_BYTES:
            raise ValueError("Source Intelligence request exceeds the 12 MB safety limit")
        return self


class SourceArtifactSummary(BaseModel):
    """Bounded, generic structural observations for one source."""

    model_config = ConfigDict(extra="forbid")

    source_id: str
    label: str | None = None
    source_kind: Literal["text", "structured"]
    content_hash: str
    byte_size: int = Field(ge=0)
    character_count: int = Field(ge=0)
    line_count: int = Field(ge=0)
    top_level_type: str
    top_level_keys: list[str] = Field(default_factory=list, max_length=128)
    field_paths: list[str] = Field(default_factory=list, max_length=256)
    repeated_lines: list[str] = Field(default_factory=list, max_length=20)
    vocabulary: list[str] = Field(default_factory=list, max_length=64)
    sample_excerpts: list[str] = Field(default_factory=list, max_length=3)
    context: SourceContext


class SourceSummary(BaseModel):
    """Aggregate summary suitable for a bounded semantic-classifier call."""

    model_config = ConfigDict(extra="forbid")

    artifact_count: int = Field(ge=1, le=MAX_SOURCE_ARTIFACTS)
    total_bytes: int = Field(ge=0, le=MAX_SOURCE_REQUEST_BYTES)
    source_kinds: list[Literal["text", "structured"]] = Field(max_length=2)
    artifacts: list[SourceArtifactSummary] = Field(max_length=MAX_SOURCE_ARTIFACTS)


class SourceMatchEvidence(BaseModel):
    """Safe evidence returned for a candidate; private mechanics are omitted."""

    model_config = ConfigDict(extra="forbid")

    matched: list[str] = Field(default_factory=list, max_length=100)
    missing: list[str] = Field(default_factory=list, max_length=100)
    negative_matches: list[str] = Field(default_factory=list, max_length=100)


class SourceProfileCandidate(BaseModel):
    """A safe candidate identity and deterministic match score."""

    model_config = ConfigDict(extra="forbid")

    profile_id: str
    profile_source: Literal["registry", "private"]
    platform: str
    domain: str
    adapter_id: str
    version: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    score: float = Field(ge=0, le=1)
    exact: bool
    specialist_skill: SpecialistSkillSlug
    evidence: SourceMatchEvidence


class SemanticProfileCandidate(BaseModel):
    """Non-private candidate metadata allowed to leave the deterministic tier."""

    model_config = ConfigDict(extra="forbid")

    profile_id: str
    platform: str
    domain: str
    source_transport: str | None = None
    source_object: str | None = None
    canonical_record_kind: str | None = None
    specialist_skill: SpecialistSkillSlug


class SemanticClassifierRequest(BaseModel):
    """Bounded handoff contract for an optional LLM classifier.

    It contains only structural source observations and public registry
    summaries.  Private profile definitions and executable rules are never
    included.
    """

    model_config = ConfigDict(extra="forbid")

    contract: Literal["shogun.source-classifier.v1"] = "shogun.source-classifier.v1"
    summary: SourceSummary
    candidates: list[SemanticProfileCandidate] = Field(
        default_factory=list,
        max_length=MAX_SEMANTIC_PROFILE_CANDIDATES,
    )
    allowed_profile_ids: list[str] = Field(
        default_factory=list,
        max_length=MAX_SEMANTIC_PROFILE_CANDIDATES,
    )
    allowed_specialist_skills: list[SpecialistSkillSlug] = Field(
        default_factory=list,
        max_length=14,
    )

    @model_validator(mode="after")
    def classifier_handoff_is_bounded(self):
        encoded = json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        if len(encoded) > MAX_CLASSIFIER_REQUEST_BYTES:
            raise ValueError("Semantic classifier request exceeds the 256 KB safety limit")
        return self


class SemanticClassificationEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observation: str = Field(min_length=1, max_length=500)
    source_ids: list[str] = Field(default_factory=list, max_length=MAX_SOURCE_ARTIFACTS)


class SemanticClassifierResponse(BaseModel):
    """Strict advisory response; it cannot define or activate a profile."""

    model_config = ConfigDict(extra="forbid")

    contract: Literal["shogun.source-classifier.v1"] = "shogun.source-classifier.v1"
    classification: Literal["classified", "unknown"]
    platform_family: str = Field(min_length=1, max_length=100)
    product: str | None = Field(default=None, max_length=200)
    business_object: str | None = Field(default=None, max_length=200)
    candidate_profile_ids: list[str] = Field(default_factory=list, max_length=10)
    specialist_skill: SpecialistSkillSlug
    confidence: float = Field(ge=0, le=1)
    evidence: list[SemanticClassificationEvidence] = Field(default_factory=list, max_length=20)
    unknowns: list[str] = Field(default_factory=list, max_length=20)


class SourceIntelligenceResult(BaseModel):
    """Safe resolution result returned to APIs and recorded in flow evidence."""

    model_config = ConfigDict(extra="forbid")

    outcome: Literal["exact", "ambiguous", "unknown"]
    execution_allowed: bool
    summary: SourceSummary
    selected_profile: SourceProfileCandidate | None = None
    candidates: list[SourceProfileCandidate] = Field(default_factory=list, max_length=20)
    specialist_skill: SpecialistSkillSlug
    classifier_request: SemanticClassifierRequest | None = None

    @model_validator(mode="after")
    def exact_is_the_only_executable_outcome(self):
        if self.execution_allowed != (self.outcome == "exact"):
            raise ValueError("Only an exact Source Intelligence result may allow execution")
        if (self.selected_profile is not None) != (self.outcome == "exact"):
            raise ValueError("Exactly one selected profile is required for an exact result")
        return self
