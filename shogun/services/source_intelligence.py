"""Registry-driven, fail-closed source intelligence.

Known active registry profiles and explicitly supplied private profile
references may be matched deterministically.  Unknown or ambiguous sources
produce a bounded semantic-classifier handoff, but semantic output is never an
execution authority and can never carry profile definitions.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from copy import deepcopy
from dataclasses import dataclass
from pathlib import PurePath
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from shogun.mapping.schema import MappingTransformationProfile
from shogun.schemas.source_intelligence import (
    MAX_SEMANTIC_PROFILE_CANDIDATES,
    SemanticClassifierRequest,
    SemanticClassifierResponse,
    SemanticProfileCandidate,
    SourceArtifactInput,
    SourceArtifactSummary,
    SourceIntelligenceRequest,
    SourceIntelligenceResult,
    SourceMatchEvidence,
    SourceProfileCandidate,
    SourceSummary,
    SpecialistSkillSlug,
)
from shogun.services.private_transformation_profiles import (
    MAX_PRIVATE_SOURCE_PATTERNS,
    PRIVATE_PROFILE_EXECUTION_MODES,
    PrivateTransformationProfileError,
    PrivateTransformationProfileRegexTimeoutError,
    PrivateTransformationProfileService,
    bounded_private_regex_search,
    compile_private_source_regex,
)
from shogun.services.transformation_profile_registry import (
    TransformationProfileRegistryError,
    TransformationProfileRegistryService,
)

MAX_STRUCTURAL_PATHS = 512
MAX_STRUCTURAL_NODES = 10_000
MAX_SUMMARY_EXCERPT_CHARS = 1_000
SHORTLIST_SCORE = 2 / 3
PRIVATE_REGEX_INSPECTION_BUDGET_SECONDS = 2.0
PRIVATE_REGEX_PER_MATCH_TIMEOUT_SECONDS = 0.1

_ALL_SPECIALISTS: tuple[SpecialistSkillSlug, ...] = (
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
)


class SourceIntelligenceError(ValueError):
    """Base error for source inspection and resolution failures."""


class SourceIntelligenceConfigurationError(SourceIntelligenceError):
    """A trusted profile contains unusable selection metadata."""


class SourceIntelligenceRegexTimeoutError(SourceIntelligenceConfigurationError):
    """Private source fingerprint matching exceeded its bounded runtime."""


class SourceProfileUnknownError(SourceIntelligenceError):
    """No installed profile proved an exact deterministic match."""

    def __init__(self, result: SourceIntelligenceResult):
        super().__init__("No installed transformation profile exactly matches the source.")
        self.result = result


class SourceProfileAmbiguousError(SourceIntelligenceError):
    """Several installed profiles remain plausible or exact."""

    def __init__(self, result: SourceIntelligenceResult):
        super().__init__(
            "Source profile selection is ambiguous; deterministic execution is blocked."
        )
        self.result = result


@dataclass(frozen=True, slots=True)
class ExecutableSourceProfile:
    """In-process exact match.  The definition must never be returned by preview APIs."""

    definition: dict[str, Any]
    evidence: dict[str, Any]
    resolution: SourceIntelligenceResult


@dataclass(frozen=True, slots=True)
class SemanticProfileNomination:
    """Trusted existing profile nominated by a model, pending adapter validation."""

    definition: dict[str, Any]
    evidence: dict[str, Any]
    classification: SemanticClassifierResponse
    execution_allowed: bool = False
    requires_deterministic_validation: bool = True


@dataclass(frozen=True, slots=True)
class _TrustedProfile:
    definition: dict[str, Any]
    trust_evidence: dict[str, Any]
    profile_source: str
    platform: str
    domain: str


@dataclass(slots=True)
class _Observations:
    texts: dict[str, str]
    keys: set[str]
    paths: set[str]
    scalar_by_key: dict[str, set[str]]
    context_by_key: dict[str, set[str]]
    file_extensions: set[str]
    content_types: set[str]


@dataclass(frozen=True, slots=True)
class _PrivateRegexBudget:
    deadline: float

    @classmethod
    def start(cls) -> _PrivateRegexBudget:
        return cls(deadline=time.monotonic() + PRIVATE_REGEX_INSPECTION_BUDGET_SECONDS)

    def next_timeout(self) -> float:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise SourceIntelligenceRegexTimeoutError(
                "Private source fingerprint inspection exceeded its total time budget."
            )
        return min(PRIVATE_REGEX_PER_MATCH_TIMEOUT_SECONDS, remaining)


@dataclass(frozen=True, slots=True)
class _MatchedProfile:
    trusted: _TrustedProfile
    candidate: SourceProfileCandidate


def _normalized(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def _definition_platform(definition: dict[str, Any], fallback: str) -> str:
    platform = definition.get("platform")
    if isinstance(platform, dict):
        return str(platform.get("product") or platform.get("vendor") or fallback)
    return str(platform or fallback or "generic")


def specialist_for_profile(
    definition: dict[str, Any],
    *,
    profile_id: str = "",
    platform: str = "",
) -> SpecialistSkillSlug:
    """Map public manifest identity to the corresponding specialist skill."""

    declared = definition.get("platform")
    pieces = [profile_id, platform]
    if isinstance(declared, dict):
        pieces.extend(str(declared.get(key) or "") for key in ("vendor", "product", "family"))
    else:
        pieces.append(str(declared or ""))
    haystack = " ".join(pieces).casefold().replace("_", " ")
    if "business central" in haystack:
        return "business-central-transformation-specialist"
    if "d365" in haystack or "dynamics 365" in haystack:
        return "d365-transformation-specialist"
    if "salesforce" in haystack:
        return "salesforce-transformation-specialist"
    if "oracle" in haystack and "fusion" in haystack:
        return "oracle-fusion-transformation-specialist"
    if "netsuite" in haystack:
        return "netsuite-transformation-specialist"
    if "ifs cloud" in haystack or re.search(r"(?:^|\s)ifs(?:\s|$)", haystack):
        return "ifs-cloud-transformation-specialist"
    if "epicor" in haystack or "kinetic" in haystack:
        return "epicor-kinetic-transformation-specialist"
    if "servicenow" in haystack:
        return "servicenow-transformation-specialist"
    if "hubspot" in haystack:
        return "hubspot-transformation-specialist"
    if "workday" in haystack:
        return "workday-transformation-specialist"
    if any(
        marker in haystack
        for marker in ("quickbooks", "xero", "e-conomic", "economic", "sage intacct")
    ):
        return "accounting-transformation-specialist"
    if any(marker in haystack for marker in ("sap", "s/4hana", "s4hana")):
        return "sap-transformation-specialist"
    return "enterprise-transformation-architect"


def _walk_structure(
    value: Any,
    *,
    path: str = "$",
    paths: set[str],
    keys: set[str],
    scalar_by_key: dict[str, set[str]],
    budget: list[int],
    depth: int = 0,
) -> None:
    if budget[0] <= 0 or depth > 12 or len(paths) >= MAX_STRUCTURAL_PATHS:
        return
    budget[0] -= 1
    if isinstance(value, dict):
        for raw_key, child in value.items():
            if budget[0] <= 0:
                return
            key = str(raw_key)[:500]
            normalized_key = _normalized(key)
            keys.add(normalized_key)
            child_path = f"{path}.{key}"
            paths.add(_normalized(child_path)[-500:])
            if child is None or isinstance(child, (str, int, float, bool)):
                scalar = _normalized(child)
                if scalar and len(scalar) <= 500:
                    scalar_by_key[normalized_key].add(scalar)
            _walk_structure(
                child,
                path=child_path,
                paths=paths,
                keys=keys,
                scalar_by_key=scalar_by_key,
                budget=budget,
                depth=depth + 1,
            )
    elif isinstance(value, list):
        list_path = f"{path}[]"
        paths.add(_normalized(list_path)[-500:])
        for child in value:
            if budget[0] <= 0:
                return
            _walk_structure(
                child,
                path=list_path,
                paths=paths,
                keys=keys,
                scalar_by_key=scalar_by_key,
                budget=budget,
                depth=depth + 1,
            )


def _sample_excerpts(text: str) -> list[str]:
    clean = text.replace("\x00", " ").strip()
    if not clean:
        return []
    if len(clean) <= MAX_SUMMARY_EXCERPT_CHARS:
        return [clean]
    starts = (0, max(0, len(clean) // 2 - 500), max(0, len(clean) - 1_000))
    excerpts: list[str] = []
    for start in starts:
        excerpt = clean[start : start + MAX_SUMMARY_EXCERPT_CHARS].strip()
        if excerpt and excerpt not in excerpts:
            excerpts.append(excerpt)
    return excerpts


def _vocabulary(text: str) -> list[str]:
    words = re.findall(r"[^\W_][\w./-]{2,80}", text.casefold(), flags=re.UNICODE)
    return [word for word, _count in Counter(words).most_common(64)]


def _artifact_summary(artifact: SourceArtifactInput) -> SourceArtifactSummary:
    if artifact.text is not None:
        encoded = artifact.text.encode("utf-8")
        lines = [line.strip() for line in artifact.text.splitlines() if line.strip()]
        repeated = [
            line[:200]
            for line, count in Counter(lines).most_common()
            if count > 1 and len(line) <= 500
        ][:20]
        return SourceArtifactSummary(
            source_id=artifact.source_id,
            label=artifact.label,
            source_kind="text",
            content_hash=hashlib.sha256(encoded).hexdigest(),
            byte_size=len(encoded),
            character_count=len(artifact.text),
            line_count=len(artifact.text.splitlines()),
            top_level_type="text",
            repeated_lines=repeated,
            vocabulary=_vocabulary(artifact.text),
            sample_excerpts=_sample_excerpts(artifact.text),
            context=artifact.context,
        )

    encoded_text = json.dumps(
        artifact.payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    encoded = encoded_text.encode("utf-8")
    paths: set[str] = set()
    keys: set[str] = set()
    scalars: dict[str, set[str]] = defaultdict(set)
    _walk_structure(
        artifact.payload,
        paths=paths,
        keys=keys,
        scalar_by_key=scalars,
        budget=[MAX_STRUCTURAL_NODES],
    )
    top_keys = list(artifact.payload) if isinstance(artifact.payload, dict) else []
    return SourceArtifactSummary(
        source_id=artifact.source_id,
        label=artifact.label,
        source_kind="structured",
        content_hash=hashlib.sha256(encoded).hexdigest(),
        byte_size=len(encoded),
        character_count=len(encoded_text),
        line_count=0,
        top_level_type=type(artifact.payload).__name__,
        top_level_keys=[str(item)[:200] for item in top_keys[:128]],
        field_paths=sorted(paths)[:256],
        vocabulary=_vocabulary(" ".join(sorted(keys))),
        sample_excerpts=_sample_excerpts(encoded_text),
        context=artifact.context,
    )


def summarize_sources(artifacts: Sequence[SourceArtifactInput]) -> SourceSummary:
    """Create a generic bounded summary without vendor-specific parsing."""

    summaries = [_artifact_summary(artifact) for artifact in artifacts]
    return SourceSummary(
        artifact_count=len(summaries),
        total_bytes=sum(item.byte_size for item in summaries),
        source_kinds=sorted({item.source_kind for item in summaries}),
        artifacts=summaries,
    )


def _observations(artifacts: Sequence[SourceArtifactInput]) -> _Observations:
    keys: set[str] = set()
    paths: set[str] = set()
    scalars: dict[str, set[str]] = defaultdict(set)
    contexts: dict[str, set[str]] = defaultdict(set)
    texts: dict[str, str] = {}
    extensions: set[str] = set()
    content_types: set[str] = set()
    for artifact in artifacts:
        context = artifact.context
        for key in (
            "transport",
            "object",
            "record_shape",
            "record_path",
            "connector",
            "platform_hint",
        ):
            value = getattr(context, key)
            if value:
                contexts[key].add(_normalized(value))
        if context.content_type:
            content_types.add(_normalized(context.content_type))
        if context.file_name:
            suffix = PurePath(context.file_name).suffix.lstrip(".")
            if suffix:
                extensions.add(_normalized(suffix))
        if artifact.text is not None:
            texts[artifact.source_id] = artifact.text
        else:
            _walk_structure(
                artifact.payload,
                paths=paths,
                keys=keys,
                scalar_by_key=scalars,
                budget=[MAX_STRUCTURAL_NODES],
            )
    return _Observations(
        texts=texts,
        keys=keys,
        paths=paths,
        scalar_by_key=dict(scalars),
        context_by_key=dict(contexts),
        file_extensions=extensions,
        content_types=content_types,
    )


def _alternatives(value: str) -> list[str]:
    return [_normalized(item) for item in value.split("|") if _normalized(item)]


def _fingerprint_matches(fingerprint: str, observations: _Observations) -> bool:
    kind, separator, value = fingerprint.partition(":")
    if not separator or not value.strip():
        return False
    kind = _normalized(kind).replace("-", "_")
    choices = _alternatives(value)
    if not choices:
        return False
    if kind in {"transport", "object", "record_shape", "record_path", "connector"}:
        observed = observations.context_by_key.get(kind, set()) | observations.scalar_by_key.get(
            kind, set()
        )
        if kind == "object":
            observed |= observations.keys
        return any(choice in observed for choice in choices)
    if kind in {"field", "key"}:
        return any(
            choice in observations.keys
            or any(path.endswith(f".{choice}") or path.endswith(f".{choice}[]") for path in observations.paths)
            for choice in choices
        )
    if kind in {"path", "field_path"}:
        return any(
            choice in observations.paths
            or any(path.endswith(f".{choice}") for path in observations.paths)
            for choice in choices
        )
    if kind in {"text", "marker", "header"}:
        normalized_text = "\n".join(_normalized(text) for text in observations.texts.values())
        return any(choice in normalized_text for choice in choices)
    if kind in {"extension", "file_type"}:
        return any(choice.lstrip(".") in observations.file_extensions for choice in choices)
    if kind == "content_type":
        return any(choice in observations.content_types for choice in choices)
    return False


def _selection_fingerprints(definition: dict[str, Any]) -> tuple[list[str], list[str]]:
    selection = definition.get("selection")
    if selection is not None and not isinstance(selection, dict):
        raise SourceIntelligenceConfigurationError("Profile selection must be an object.")
    selection = selection or {}
    positive = selection.get("positive_fingerprints") or []
    negative = selection.get("negative_fingerprints") or []
    if not isinstance(positive, list) or not all(isinstance(item, str) for item in positive):
        raise SourceIntelligenceConfigurationError(
            "Profile positive_fingerprints must be a list of strings."
        )
    if not isinstance(negative, list) or not all(isinstance(item, str) for item in negative):
        raise SourceIntelligenceConfigurationError(
            "Profile negative_fingerprints must be a list of strings."
        )
    if not positive:
        source = definition.get("source") if isinstance(definition.get("source"), dict) else {}
        for key in ("transport", "object", "record_shape", "record_path"):
            if source.get(key):
                positive.append(f"{key}:{source[key]}")
    return list(dict.fromkeys(positive)), list(dict.fromkeys(negative))


def _private_regex_evidence(
    definition: dict[str, Any],
    observations: _Observations,
    budget: _PrivateRegexBudget,
) -> tuple[list[str], list[str]] | None:
    parameters = definition.get("parameters")
    if not isinstance(parameters, dict):
        return None
    patterns = parameters.get("required_source_patterns")
    if not patterns:
        return None
    if not isinstance(patterns, list) or not all(isinstance(item, str) for item in patterns):
        raise SourceIntelligenceConfigurationError(
            "Private required_source_patterns must be a list of strings."
        )
    if len(patterns) > MAX_PRIVATE_SOURCE_PATTERNS:
        raise SourceIntelligenceConfigurationError(
            "Private source fingerprint exceeds the configured pattern limit."
        )
    if not observations.texts:
        return [], [f"private_required_pattern:{index + 1}" for index in range(len(patterns))]
    matched: list[str] = []
    missing: list[str] = []
    for index, pattern in enumerate(patterns):
        marker = f"private_required_pattern:{index + 1}"
        pattern_path = f"$.parameters.required_source_patterns[{index}]"
        try:
            compiled = compile_private_source_regex(pattern, path=pattern_path)
        except PrivateTransformationProfileError as exc:
            raise SourceIntelligenceConfigurationError(
                "Private source fingerprint failed validation."
            ) from exc
        failed_sources: list[str] = []
        for source_id, text in observations.texts.items():
            try:
                matched_source = bounded_private_regex_search(
                    compiled,
                    text,
                    timeout_seconds=budget.next_timeout(),
                    path=pattern_path,
                )
            except PrivateTransformationProfileRegexTimeoutError as exc:
                raise SourceIntelligenceRegexTimeoutError(str(exc)) from exc
            if not matched_source:
                failed_sources.append(source_id)
        if failed_sources:
            missing.append(marker)
        else:
            matched.append(marker)
    return matched, missing


def _match_profile(
    profile: _TrustedProfile,
    observations: _Observations,
    private_regex_budget: _PrivateRegexBudget,
) -> _MatchedProfile:
    definition = profile.definition
    profile_id = str(profile.trust_evidence.get("profile_id") or definition.get("id") or "")
    adapter_id = str(profile.trust_evidence.get("adapter_id") or definition.get("adapter") or "")
    version = profile.trust_evidence.get("version") or 1
    content_hash = str(profile.trust_evidence.get("content_hash") or "").lower()
    positives, negatives = _selection_fingerprints(definition)
    private_regex = (
        _private_regex_evidence(definition, observations, private_regex_budget)
        if profile.profile_source == "private"
        else None
    )
    if private_regex is not None and not positives:
        matched, missing = private_regex
        safe_positive_count = len(matched) + len(missing)
    else:
        matched = [item for item in positives if _fingerprint_matches(item, observations)]
        missing = [item for item in positives if item not in matched]
        safe_positive_count = len(positives)
        if profile.profile_source == "private":
            # Private profile fingerprints are local mechanics.  Only return
            # opaque ordinal evidence to callers and never to the classifier.
            matched = [f"private_fingerprint:{index + 1}" for index, _ in enumerate(matched)]
            missing = [f"private_fingerprint_missing:{index + 1}" for index, _ in enumerate(missing)]
    negative_matches = [item for item in negatives if _fingerprint_matches(item, observations)]
    if profile.profile_source == "private":
        negative_matches = [
            f"private_negative_fingerprint:{index + 1}"
            for index, _ in enumerate(negative_matches)
        ]
    score = len(matched) / safe_positive_count if safe_positive_count else 0.0
    if negative_matches:
        score = 0.0
    exact = bool(safe_positive_count) and not missing and not negative_matches
    platform = _definition_platform(definition, profile.platform)
    specialist = specialist_for_profile(
        definition,
        profile_id=profile_id,
        platform=platform,
    )
    candidate = SourceProfileCandidate(
        profile_id=profile_id,
        profile_source=profile.profile_source,
        platform=platform,
        domain=profile.domain,
        adapter_id=adapter_id,
        version=int(version),
        content_hash=content_hash,
        score=round(score, 6),
        exact=exact,
        specialist_skill=specialist,
        evidence=SourceMatchEvidence(
            matched=matched,
            missing=missing,
            negative_matches=negative_matches,
        ),
    )
    return _MatchedProfile(trusted=profile, candidate=candidate)


def _specialist_from_summary(summary: SourceSummary) -> SpecialistSkillSlug:
    pieces: list[str] = []
    for artifact in summary.artifacts:
        pieces.extend(artifact.vocabulary)
        pieces.extend(
            value
            for value in (
                artifact.context.platform_hint,
                artifact.context.connector,
                artifact.context.object,
            )
            if value
        )
    synthetic = {"platform": " ".join(pieces)}
    return specialist_for_profile(synthetic, platform=" ".join(pieces))


def _semantic_candidate(profile: _MatchedProfile) -> SemanticProfileCandidate:
    definition = profile.trusted.definition
    source = definition.get("source") if isinstance(definition.get("source"), dict) else {}
    contract = (
        definition.get("canonical_contract")
        if isinstance(definition.get("canonical_contract"), dict)
        else {}
    )
    return SemanticProfileCandidate(
        profile_id=profile.candidate.profile_id,
        platform=profile.candidate.platform,
        domain=profile.candidate.domain,
        source_transport=(str(source["transport"]) if source.get("transport") else None),
        source_object=(str(source["object"]) if source.get("object") else None),
        canonical_record_kind=(
            str(contract["record_kind"]) if contract.get("record_kind") else None
        ),
        specialist_skill=profile.candidate.specialist_skill,
    )


class SourceIntelligenceService:
    """Resolve known profiles and prepare safe discovery handoffs."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        registry_service: TransformationProfileRegistryService | None = None,
    ) -> None:
        self.session = session
        self.registry = registry_service or TransformationProfileRegistryService(session)

    async def _trusted_profiles(
        self,
        private_profiles: Iterable[MappingTransformationProfile],
    ) -> list[_TrustedProfile]:
        trusted: list[_TrustedProfile] = []
        try:
            public = await self.registry.list_active_definitions()
        except TransformationProfileRegistryError as exc:
            raise SourceIntelligenceConfigurationError(str(exc)) from exc
        for envelope in public:
            trusted.append(
                _TrustedProfile(
                    definition=envelope["definition"],
                    trust_evidence=envelope["registry_evidence"],
                    profile_source="registry",
                    platform=str(envelope["profile_metadata"].get("platform") or "generic"),
                    domain=str(envelope["profile_metadata"].get("domain") or "document"),
                )
            )

        private_service = PrivateTransformationProfileService()
        for reference in private_profiles:
            adapter_id = str(reference.adapter)
            execution_mode = PRIVATE_PROFILE_EXECUTION_MODES.get(adapter_id)
            if execution_mode is None:
                raise SourceIntelligenceConfigurationError(
                    f"Private profile adapter '{adapter_id}' is not eligible for source discovery."
                )
            try:
                definition, evidence = private_service.resolve_reference(
                    reference,
                    execution_mode=execution_mode,
                )
            except PrivateTransformationProfileError as exc:
                raise SourceIntelligenceConfigurationError(str(exc)) from exc
            trusted.append(
                _TrustedProfile(
                    definition=definition,
                    trust_evidence=evidence,
                    profile_source="private",
                    platform=_definition_platform(definition, "private"),
                    domain=str(definition.get("domain") or "document"),
                )
            )
        return trusted

    async def inspect(
        self,
        request: SourceIntelligenceRequest | dict[str, Any],
    ) -> SourceIntelligenceResult:
        """Return exact, ambiguous, or unknown without executing anything."""

        parsed = (
            request
            if isinstance(request, SourceIntelligenceRequest)
            else SourceIntelligenceRequest.model_validate(request)
        )
        summary = summarize_sources(parsed.artifacts)
        observations = _observations(parsed.artifacts)
        profiles = await self._trusted_profiles(parsed.private_profiles)
        private_regex_budget = _PrivateRegexBudget.start()
        matches = [
            _match_profile(profile, observations, private_regex_budget)
            for profile in profiles
        ]
        matches.sort(
            key=lambda item: (
                not item.candidate.exact,
                -item.candidate.score,
                item.candidate.profile_id,
                item.candidate.profile_source,
            )
        )
        exact = [item for item in matches if item.candidate.exact]
        shortlist = [
            item
            for item in matches
            if not item.candidate.evidence.negative_matches
            and item.candidate.score >= SHORTLIST_SCORE
        ]
        visible = (exact or shortlist or [item for item in matches if item.candidate.score > 0])[:20]

        if len(exact) == 1:
            selected = exact[0].candidate
            inferred_specialist = _specialist_from_summary(summary)
            if (
                selected.specialist_skill == "enterprise-transformation-architect"
                and inferred_specialist != "enterprise-transformation-architect"
            ):
                # Private profiles may deliberately use opaque, customer-local
                # identifiers and omit distributable platform metadata.  Keep
                # the exact deterministic profile match, but route advisory
                # follow-up from the source evidence rather than guessing from
                # that private identifier.
                selected = selected.model_copy(
                    update={"specialist_skill": inferred_specialist}
                )
                visible = [
                    selected
                    if item.candidate.profile_id == selected.profile_id
                    and item.candidate.profile_source == selected.profile_source
                    else item.candidate
                    for item in visible
                ]
            else:
                visible = [item.candidate for item in visible]
            return SourceIntelligenceResult(
                outcome="exact",
                execution_allowed=True,
                summary=summary,
                selected_profile=selected,
                candidates=visible,
                specialist_skill=selected.specialist_skill,
            )

        outcome = "ambiguous" if len(exact) > 1 or len(shortlist) > 1 else "unknown"
        relevant = exact if exact else shortlist
        inferred_specialist = _specialist_from_summary(summary)
        candidate_specialists = {item.candidate.specialist_skill for item in relevant}
        specialist = (
            next(iter(candidate_specialists))
            if len(candidate_specialists) == 1
            else inferred_specialist
        )
        private_ambiguity = outcome == "ambiguous" and any(
            item.candidate.profile_source == "private" for item in relevant
        )
        public_for_classifier: list[_MatchedProfile] = []
        if not private_ambiguity:
            # Prioritize deterministic evidence, then the inferred platform,
            # but keep the rest of the installed public catalogue available.
            # This lets the advisory model identify a known source whose
            # vendor/object hints were absent without ever seeing executable
            # profile definitions. The 256 KiB request contract remains the
            # ultimate bound.
            ranked_groups = [
                [
                    item
                    for item in (relevant or visible)
                    if item.candidate.profile_source == "registry"
                ],
                [
                    item
                    for item in matches
                    if item.candidate.profile_source == "registry"
                    and item.candidate.specialist_skill == inferred_specialist
                ],
                [
                    item
                    for item in matches
                    if item.candidate.profile_source == "registry"
                ],
            ]
            seen_public: set[tuple[str, str]] = set()
            for group in ranked_groups:
                for item in group:
                    identity = (
                        item.candidate.profile_id,
                        item.candidate.content_hash,
                    )
                    if identity in seen_public:
                        continue
                    seen_public.add(identity)
                    public_for_classifier.append(item)
                    if len(public_for_classifier) >= MAX_SEMANTIC_PROFILE_CANDIDATES:
                        break
                if len(public_for_classifier) >= MAX_SEMANTIC_PROFILE_CANDIDATES:
                    break
        classifier_request = SemanticClassifierRequest(
            summary=summary,
            candidates=[_semantic_candidate(item) for item in public_for_classifier],
            allowed_profile_ids=[item.candidate.profile_id for item in public_for_classifier],
            allowed_specialist_skills=list(_ALL_SPECIALISTS),
        )
        return SourceIntelligenceResult(
            outcome=outcome,
            execution_allowed=False,
            summary=summary,
            candidates=[item.candidate for item in visible],
            specialist_skill=specialist,
            classifier_request=classifier_request,
        )

    async def resolve_executable(
        self,
        artifacts: Sequence[SourceArtifactInput | dict[str, Any]],
        *,
        private_profiles: Sequence[MappingTransformationProfile | dict[str, Any]] | None = None,
    ) -> ExecutableSourceProfile:
        """Resolve exactly one trusted profile or raise a fail-closed error."""

        request = SourceIntelligenceRequest.model_validate(
            {
                "artifacts": list(artifacts),
                "private_profiles": list(private_profiles or []),
            }
        )
        result = await self.inspect(request)
        if result.outcome == "ambiguous":
            raise SourceProfileAmbiguousError(result)
        if result.outcome != "exact" or result.selected_profile is None:
            raise SourceProfileUnknownError(result)

        trusted = await self._trusted_profiles(request.private_profiles)
        selected = result.selected_profile
        eligible = [
            item
            for item in trusted
            if str(item.trust_evidence.get("profile_id")) == selected.profile_id
            and str(item.trust_evidence.get("content_hash")).lower() == selected.content_hash
            and item.profile_source == selected.profile_source
        ]
        if len(eligible) != 1:
            raise SourceIntelligenceConfigurationError(
                "Selected profile trust evidence changed during source resolution."
            )
        chosen = eligible[0]
        return ExecutableSourceProfile(
            definition=deepcopy(chosen.definition),
            evidence=deepcopy(chosen.trust_evidence),
            resolution=result,
        )

    @staticmethod
    def validate_semantic_response(
        request: SemanticClassifierRequest | dict[str, Any],
        response: SemanticClassifierResponse | dict[str, Any],
    ) -> SemanticClassifierResponse:
        """Validate advisory output against the bounded request allow-list.

        A valid response still does not authorize execution.  Its nominated
        profile must return through deterministic validation and exact
        resolution before an adapter can run.
        """

        parsed_request = (
            request
            if isinstance(request, SemanticClassifierRequest)
            else SemanticClassifierRequest.model_validate(request)
        )
        parsed_response = (
            response
            if isinstance(response, SemanticClassifierResponse)
            else SemanticClassifierResponse.model_validate(response)
        )
        if any(
            profile_id not in parsed_request.allowed_profile_ids
            for profile_id in parsed_response.candidate_profile_ids
        ):
            raise SourceIntelligenceError(
                "Semantic classifier nominated a profile outside the request allow-list."
            )
        if parsed_response.specialist_skill not in parsed_request.allowed_specialist_skills:
            raise SourceIntelligenceError(
                "Semantic classifier nominated a specialist outside the request allow-list."
            )
        return parsed_response

    async def resolve_semantic_nomination(
        self,
        request: SemanticClassifierRequest | dict[str, Any],
        response: SemanticClassifierResponse | dict[str, Any],
        *,
        private_profiles: Sequence[MappingTransformationProfile | dict[str, Any]] | None = None,
        minimum_confidence: float = 0.85,
    ) -> SemanticProfileNomination:
        """Resolve one advisory nomination to an existing trusted definition.

        This never authorizes execution.  Callers must dry-run the selected
        adapter and validate its source fingerprints, fields, identities, and
        invariants before they may execute or persist output.
        """

        if not 0 <= minimum_confidence <= 1:
            raise SourceIntelligenceError("Semantic confidence threshold must be between 0 and 1.")
        parsed_request = (
            request
            if isinstance(request, SemanticClassifierRequest)
            else SemanticClassifierRequest.model_validate(request)
        )
        classification = self.validate_semantic_response(parsed_request, response)
        if classification.classification != "classified":
            raise SourceProfileUnknownError(
                SourceIntelligenceResult(
                    outcome="unknown",
                    execution_allowed=False,
                    summary=parsed_request.summary,
                    specialist_skill=classification.specialist_skill,
                    classifier_request=parsed_request,
                )
            )
        if classification.confidence < minimum_confidence:
            raise SourceIntelligenceError(
                "Semantic classifier confidence is below the required threshold."
            )
        if not classification.evidence:
            raise SourceIntelligenceError(
                "Semantic classifier must provide source-linked evidence."
            )
        nominated = classification.candidate_profile_ids
        if len(nominated) != 1:
            raise SourceIntelligenceError(
                "Semantic classifier must nominate exactly one existing profile."
            )

        parsed_private: list[MappingTransformationProfile] = []
        for raw in private_profiles or []:
            parsed_private.append(
                raw
                if isinstance(raw, MappingTransformationProfile)
                else MappingTransformationProfile.model_validate(raw)
            )
        trusted = await self._trusted_profiles(parsed_private)
        eligible = [
            profile
            for profile in trusted
            if profile.profile_source == "registry"
            and str(profile.trust_evidence.get("profile_id")) == nominated[0]
        ]
        if len(eligible) != 1:
            raise SourceIntelligenceConfigurationError(
                "Semantic nomination no longer resolves to one active public profile."
            )
        selected = eligible[0]
        evidence = deepcopy(selected.trust_evidence)
        evidence.update(
            {
                "selection_authority": "semantic_advisory",
                "semantic_confidence": classification.confidence,
                "execution_allowed": False,
                "requires_deterministic_validation": True,
            }
        )
        return SemanticProfileNomination(
            definition=deepcopy(selected.definition),
            evidence=evidence,
            classification=classification,
        )
