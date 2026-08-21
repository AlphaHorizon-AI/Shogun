"""Portable, flow-local transformation profiles.

Private profile files are validated declarative data.  Importing one never
creates a registry record and never makes it discoverable in the shared
catalog.  The complete definition and an immutable hash pin travel with the
Mapping/RPA node; execution repeats server-side validation before issuing the
short-lived evidence consumed by a deterministic adapter.
"""

from __future__ import annotations

import json
import re
import warnings
from copy import deepcopy
from typing import Any, Literal

import regex as timeout_regex

from shogun.mapping.schema import (
    PRIVATE_TRANSFORMATION_PROFILE_FORMAT,
    MappingTransformationProfile,
)
from shogun.schemas.transformation_profile import PrivateTransformationProfileDocument
from shogun.services.transformation_profile_registry import (
    TransformationProfileRegistryError,
    _declared_version,
    _runtime_adapter_catalog,
    _static_profile_validation,
    profile_content_hash,
)

PRIVATE_PROFILE_FORMAT_VERSION = 1
PRIVATE_PROFILE_EVIDENCE_STATUS = "private_validated"
PRIVATE_PROFILE_EXECUTION_MODES: dict[str, Literal["contract", "profile"]] = {
    "sectioned_record_matrix_v1": "contract",
    "canonical_entity_map_v1": "profile",
}
MAX_PRIVATE_SOURCE_PATTERNS = 32


class PrivateTransformationProfileError(ValueError):
    """A portable private profile failed bounded server validation."""


class PrivateTransformationProfileRegexError(PrivateTransformationProfileError):
    """A private profile regex is invalid or unsafe to evaluate."""


class PrivateTransformationProfileRegexTimeoutError(
    PrivateTransformationProfileRegexError
):
    """A private profile regex exceeded its caller-supplied evaluation budget."""


def _profile_definition(value: Any) -> dict[str, Any]:
    raw = value.model_dump(mode="json") if hasattr(value, "model_dump") else value
    if not isinstance(raw, dict):
        raise PrivateTransformationProfileError("Private transformation profile must be an object.")
    private_file = raw.get("private_file")
    if isinstance(private_file, dict) and isinstance(private_file.get("definition"), dict):
        return deepcopy(private_file["definition"])
    definition = deepcopy(raw)
    # Registry pins and portable evidence describe a definition; they are not
    # executable mechanics and must never become part of the portable file.
    definition.pop("registry_version", None)
    definition.pop("content_hash", None)
    definition.pop("private_file", None)
    return definition


def _validate_sectioned_matrix_profile(definition: dict[str, Any]) -> None:
    """Exercise the sectioned adapter's bounded, input-independent checks."""

    try:
        from shogun.services.structured_transformations import (
            _profile_parameters,
            _required_pattern,
            _row_rules,
        )

        _profile_id, parameters = _profile_parameters(definition)
        _required_pattern(parameters, "section_pattern")
        _required_pattern(parameters, "record_pattern")
        row_rules = _row_rules(parameters)
        if not row_rules:
            raise ValueError("Transformation profile requires at least one row rule.")
    except (TypeError, ValueError) as exc:
        raise PrivateTransformationProfileError(
            f"Sectioned-matrix profile schema validation failed: {exc}"
        ) from exc

    # Compile every explicitly named pattern, including the common plain
    # ``pattern`` property that the registry's generic suffix check cannot
    # distinguish from ordinary strings.
    regex_count = 0

    def visit(value: Any, path: str = "$.parameters") -> None:
        nonlocal regex_count
        if isinstance(value, dict):
            for key, child in value.items():
                child_path = f"{path}.{key}"
                is_pattern = key == "pattern" or key.endswith("_pattern")
                is_patterns = key.endswith("_patterns")
                if is_pattern:
                    if not isinstance(child, str):
                        raise PrivateTransformationProfileError(
                            f"Regex at {child_path} must be a string."
                        )
                    _compile_private_regex(child, child_path)
                    regex_count += 1
                elif is_patterns:
                    if not isinstance(child, list):
                        raise PrivateTransformationProfileError(
                            f"Regex collection at {child_path} must be a list."
                        )
                    for index, pattern in enumerate(child):
                        if not isinstance(pattern, str):
                            raise PrivateTransformationProfileError(
                                f"Regex at {child_path}[{index}] must be a string."
                            )
                        _compile_private_regex(pattern, f"{child_path}[{index}]")
                        regex_count += 1
                visit(child, child_path)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{path}[{index}]")

    visit(definition.get("parameters") or {})
    if regex_count > 1_000:
        raise PrivateTransformationProfileError(
            "Private transformation profile exceeds the 1,000-regex safety limit."
        )


def _regex_tree_contains_flexible_repeat(value: Any) -> bool:
    """Inspect the stdlib parser tree without evaluating caller-controlled text."""

    for operation, argument in value:
        operation_name = str(operation)
        if operation_name in {"MAX_REPEAT", "MIN_REPEAT", "POSSESSIVE_REPEAT"}:
            minimum, maximum, child = argument
            if minimum != maximum or _regex_tree_contains_flexible_repeat(child):
                return True
        elif operation_name == "SUBPATTERN":
            if _regex_tree_contains_flexible_repeat(argument[-1]):
                return True
        elif operation_name == "BRANCH":
            if any(_regex_tree_contains_flexible_repeat(branch) for branch in argument[1]):
                return True
        elif operation_name in {"ASSERT", "ASSERT_NOT", "ATOMIC_GROUP"}:
            child = argument[-1] if operation_name != "ATOMIC_GROUP" else argument
            if _regex_tree_contains_flexible_repeat(child):
                return True
    return False


def _validate_private_regex_complexity(pattern: str, path: str) -> None:
    """Reject constructs with known catastrophic-backtracking risk.

    Runtime matching is separately time-bounded.  This static gate keeps
    obviously hostile patterns out of portable profile files altogether and
    protects other deterministic adapters that use the stdlib regex engine.
    """

    try:
        # ``re._parser`` is the parser used by the supported stdlib ``re``
        # engine.  Parsing performs no source-text evaluation and lets us
        # reject unsafe structure without maintaining a second regex parser.
        try:
            from re import _parser as re_parser
        except ImportError:  # Python 3.10 compatibility.
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                import sre_parse as re_parser

        parsed = re_parser.parse(pattern, 0)
    except (ImportError, RecursionError, re.error, ValueError) as exc:
        raise PrivateTransformationProfileRegexError(
            f"Regex at {path} could not pass safety analysis: {exc}"
        ) from exc

    def visit(value: Any, *, inside_flexible_repeat: bool = False) -> None:
        for operation, argument in value:
            operation_name = str(operation)
            if operation_name in {"GROUPREF", "GROUPREF_EXISTS"}:
                raise PrivateTransformationProfileRegexError(
                    f"Unsafe regex at {path}: backreferences are not allowed in private profiles."
                )
            if operation_name in {"MAX_REPEAT", "MIN_REPEAT", "POSSESSIVE_REPEAT"}:
                minimum, maximum, child = argument
                flexible = minimum != maximum
                repeats_many = flexible and maximum > 1
                if repeats_many and _regex_tree_contains_flexible_repeat(child):
                    raise PrivateTransformationProfileRegexError(
                        f"Unsafe regex at {path}: nested variable quantifiers are not allowed."
                    )
                visit(
                    child,
                    inside_flexible_repeat=inside_flexible_repeat or repeats_many,
                )
                continue
            if operation_name == "SUBPATTERN":
                visit(argument[-1], inside_flexible_repeat=inside_flexible_repeat)
                continue
            if operation_name == "BRANCH":
                branches = argument[1]
                if inside_flexible_repeat and any(branch.getwidth()[0] == 0 for branch in branches):
                    raise PrivateTransformationProfileRegexError(
                        f"Unsafe regex at {path}: an empty alternative is repeated."
                    )
                for branch in branches:
                    visit(branch, inside_flexible_repeat=inside_flexible_repeat)
                continue
            if operation_name in {"ASSERT", "ASSERT_NOT", "ATOMIC_GROUP"}:
                child = argument[-1] if operation_name != "ATOMIC_GROUP" else argument
                visit(child, inside_flexible_repeat=inside_flexible_repeat)

    visit(parsed)


def _compile_private_regex(pattern: str, path: str) -> None:
    if len(pattern) > 10_000:
        raise PrivateTransformationProfileRegexError(
            f"Regex at {path} exceeds the 10,000-character safety limit."
        )
    try:
        re.compile(pattern)
    except (RecursionError, re.error) as exc:
        raise PrivateTransformationProfileRegexError(
            f"Invalid regex at {path}: {exc}"
        ) from exc
    _validate_private_regex_complexity(pattern, path)
    try:
        timeout_regex.compile(pattern)
    except (RecursionError, timeout_regex.error) as exc:
        raise PrivateTransformationProfileRegexError(
            f"Invalid regex at {path}: {exc}"
        ) from exc


def _validate_private_source_patterns(parameters: dict[str, Any]) -> None:
    patterns = parameters.get("required_source_patterns")
    if patterns is None:
        return
    if not isinstance(patterns, list):
        raise PrivateTransformationProfileRegexError(
            "Private transformation profile required_source_patterns must be an array."
        )
    if len(patterns) > MAX_PRIVATE_SOURCE_PATTERNS:
        raise PrivateTransformationProfileRegexError(
            "Private transformation profile exceeds the 32 source-fingerprint regex limit."
        )
    for index, pattern in enumerate(patterns):
        if not isinstance(pattern, str):
            raise PrivateTransformationProfileRegexError(
                f"Regex at $.parameters.required_source_patterns[{index}] must be a string."
            )
        _compile_private_regex(
            pattern,
            f"$.parameters.required_source_patterns[{index}]",
        )


def compile_private_source_regex(pattern: str, *, path: str) -> Any:
    """Return a timeout-capable compiled regex after the import safety gate."""

    _compile_private_regex(pattern, path)
    return timeout_regex.compile(pattern)


def bounded_private_regex_search(
    compiled: Any,
    text: str,
    *,
    timeout_seconds: float,
    path: str,
) -> bool:
    """Evaluate one private fingerprint within an explicit wall-clock budget."""

    if timeout_seconds <= 0:
        raise PrivateTransformationProfileRegexTimeoutError(
            "Private source fingerprint inspection exceeded its total time budget."
        )
    try:
        return compiled.search(
            text,
            timeout=timeout_seconds,
            concurrent=True,
        ) is not None
    except TimeoutError as exc:
        raise PrivateTransformationProfileRegexTimeoutError(
            f"Private source fingerprint at {path} exceeded its evaluation time budget."
        ) from exc


def _execution_mode_for_adapter(adapter_id: str) -> Literal["contract", "profile"]:
    try:
        return PRIVATE_PROFILE_EXECUTION_MODES[adapter_id]
    except KeyError as exc:
        raise PrivateTransformationProfileError(
            f"Transformation adapter '{adapter_id}' is not supported for portable private files."
        ) from exc


def validate_private_profile_definition(
    definition: dict[str, Any],
    *,
    execution_mode: Literal["contract", "profile"] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return an isolated definition and static validation report."""

    definition = deepcopy(definition)
    profile_id = str(definition.get("id") or "").strip()
    adapter_id = str(definition.get("adapter") or "").strip()
    if not profile_id or not adapter_id:
        raise PrivateTransformationProfileError(
            "Private transformation profile requires an id and adapter."
        )
    inferred_mode = _execution_mode_for_adapter(adapter_id)
    if execution_mode is not None and execution_mode != inferred_mode:
        raise PrivateTransformationProfileError(
            f"Adapter '{adapter_id}' executes in '{inferred_mode}' mode, not '{execution_mode}'."
        )

    runtime_adapter = _runtime_adapter_catalog().get(adapter_id)
    if not isinstance(runtime_adapter, dict) or str(
        runtime_adapter.get("status") or ""
    ).lower() != "available":
        raise PrivateTransformationProfileError(
            f"Transformation adapter '{adapter_id}' is not available in this installation."
        )

    parameters = definition.get("parameters", {})
    if not isinstance(parameters, dict):
        raise PrivateTransformationProfileError(
            "Private transformation profile parameters must be an object."
        )
    _validate_private_source_patterns(parameters)

    try:
        report = _static_profile_validation(
            definition,
            expected_profile_id=profile_id,
            expected_adapter_id=adapter_id,
        )
    except TransformationProfileRegistryError as exc:
        raise PrivateTransformationProfileError(str(exc)) from exc

    if adapter_id == "sectioned_record_matrix_v1":
        _validate_sectioned_matrix_profile(definition)
    model_fallback = definition.get("model_fallback", False)
    if not isinstance(model_fallback, bool):
        raise PrivateTransformationProfileError(
            "Private transformation profile model_fallback must be a boolean."
        )
    return definition, {
        **report,
        "execution_mode": inferred_mode,
        "adapter_status": "available",
    }


def _private_profile_reference(
    definition: dict[str, Any],
    *,
    content_hash: str,
) -> dict[str, Any]:
    return {
        "id": str(definition["id"]),
        "adapter": str(definition["adapter"]),
        "parameters": deepcopy(definition.get("parameters") or {}),
        "model_fallback": bool(definition.get("model_fallback", False)),
        "private_file": {
            "format": PRIVATE_TRANSFORMATION_PROFILE_FORMAT,
            "format_version": PRIVATE_PROFILE_FORMAT_VERSION,
            "content_hash": content_hash,
            "definition": deepcopy(definition),
        },
    }


def _safe_filename(profile_id: str, display_name: str | None = None) -> str:
    stem = str(display_name or profile_id).strip()
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "-", stem).strip(".-") or profile_id
    return f"{stem[:180]}.shogun-profile.json"


class PrivateTransformationProfileService:
    """Stateless import/export and execution resolution for private files."""

    def export_profile(
        self,
        profile: Any,
        *,
        execution_mode: Literal["contract", "profile"] | None = None,
        display_name: str | None = None,
    ) -> dict[str, Any]:
        definition, report = validate_private_profile_definition(
            _profile_definition(profile),
            execution_mode=execution_mode,
        )
        digest = profile_content_hash(definition)
        document = PrivateTransformationProfileDocument(
            profile=definition,
            content_hash=digest,
        ).model_dump(mode="json")
        return {
            "filename": _safe_filename(str(definition["id"]), display_name),
            "execution_mode": report["execution_mode"],
            "document": document,
            "profile_reference": _private_profile_reference(
                definition,
                content_hash=digest,
            ),
        }

    async def export_profile_reference(
        self,
        profile: Any,
        *,
        registry_service: Any,
        execution_mode: Literal["contract", "profile"] | None = None,
        display_name: str | None = None,
    ) -> dict[str, Any]:
        """Export inline mechanics or resolve an immutable registry reference."""

        raw = profile.model_dump(mode="json") if hasattr(profile, "model_dump") else profile
        if not isinstance(raw, dict):
            raise PrivateTransformationProfileError(
                "Private transformation profile must be an object."
            )
        registry_version = raw.get("registry_version")
        registry_hash = raw.get("content_hash")
        if registry_version is not None or registry_hash is not None:
            if (
                isinstance(registry_version, bool)
                or not isinstance(registry_version, int)
                or registry_version < 1
                or not isinstance(registry_hash, str)
            ):
                raise PrivateTransformationProfileError(
                    "Registry-backed exports require a complete version/content-hash pin."
                )
            resolved = await registry_service.resolve_active_definition(
                str(raw.get("id") or ""),
                expected_version=registry_version,
                expected_hash=registry_hash.lower(),
            )
            definition = resolved.get("definition")
            evidence = resolved.get("registry_evidence")
            if not isinstance(definition, dict) or not isinstance(evidence, dict):
                raise PrivateTransformationProfileError(
                    "Transformation profile registry returned an invalid export definition."
                )
            if str(raw.get("adapter") or "") != str(evidence.get("adapter_id") or ""):
                raise PrivateTransformationProfileError(
                    "Transformation profile registry adapter does not match the export reference."
                )
            return self.export_profile(
                definition,
                execution_mode=execution_mode,
                display_name=display_name,
            )
        return self.export_profile(
            raw,
            execution_mode=execution_mode,
            display_name=display_name,
        )

    def import_document(self, document: Any) -> dict[str, Any]:
        try:
            portable = (
                document
                if isinstance(document, PrivateTransformationProfileDocument)
                else PrivateTransformationProfileDocument.model_validate(document)
            )
        except (TypeError, ValueError) as exc:
            raise PrivateTransformationProfileError(str(exc)) from exc
        definition, report = validate_private_profile_definition(portable.profile)
        digest = profile_content_hash(definition)
        if portable.content_hash != digest:
            raise PrivateTransformationProfileError(
                "Private transformation profile file content_hash does not match profile."
            )
        normalized_document = PrivateTransformationProfileDocument(
            profile=definition,
            content_hash=digest,
        ).model_dump(mode="json")
        return {
            "filename": _safe_filename(str(definition["id"])),
            "execution_mode": report["execution_mode"],
            "document": normalized_document,
            "profile_reference": _private_profile_reference(
                definition,
                content_hash=digest,
            ),
        }

    def resolve_reference(
        self,
        profile: MappingTransformationProfile | dict[str, Any],
        *,
        execution_mode: Literal["contract", "profile"],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        try:
            reference = (
                profile
                if isinstance(profile, MappingTransformationProfile)
                else MappingTransformationProfile.model_validate(profile)
            )
        except (TypeError, ValueError) as exc:
            raise PrivateTransformationProfileError(str(exc)) from exc
        if reference.private_file is None:
            raise PrivateTransformationProfileError(
                "Transformation profile is not backed by a private profile file."
            )
        definition, report = validate_private_profile_definition(
            reference.private_file.definition,
            execution_mode=execution_mode,
        )
        digest = profile_content_hash(definition)
        if digest != reference.private_file.content_hash:
            raise PrivateTransformationProfileError(
                "Private transformation profile definition does not match its content-hash pin."
            )
        evidence = {
            "profile_id": reference.id,
            "adapter_id": reference.adapter,
            "status": PRIVATE_PROFILE_EVIDENCE_STATUS,
            "adapter_status": "available",
            "version": _declared_version(definition, reference.id),
            "content_hash": digest,
            "source": "private_file",
            "format": PRIVATE_TRANSFORMATION_PROFILE_FORMAT,
            "format_version": PRIVATE_PROFILE_FORMAT_VERSION,
            "schema_valid": bool(report.get("schema_valid")),
            "server_validated": True,
        }
        return definition, evidence


def private_profile_document_size(document: dict[str, Any]) -> int:
    """Expose deterministic byte accounting for focused boundary tests."""

    return len(
        json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    )
