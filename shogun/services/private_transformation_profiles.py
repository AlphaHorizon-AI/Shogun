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
from copy import deepcopy
from typing import Any, Literal

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


class PrivateTransformationProfileError(ValueError):
    """A portable private profile failed bounded server validation."""


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


def _compile_private_regex(pattern: str, path: str) -> None:
    if len(pattern) > 10_000:
        raise PrivateTransformationProfileError(
            f"Regex at {path} exceeds the 10,000-character safety limit."
        )
    try:
        re.compile(pattern)
    except re.error as exc:
        raise PrivateTransformationProfileError(f"Invalid regex at {path}: {exc}") from exc


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
    parameters = definition.get("parameters", {})
    if not isinstance(parameters, dict):
        raise PrivateTransformationProfileError(
            "Private transformation profile parameters must be an object."
        )
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
        definition, _report = validate_private_profile_definition(
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
        definition, _report = validate_private_profile_definition(portable.profile)
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
