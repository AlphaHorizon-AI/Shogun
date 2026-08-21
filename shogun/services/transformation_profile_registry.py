"""Governed, versioned registry for enterprise transformation profiles.

Bundled JSON resources are seeds, not the live source of truth.  At startup
they are discovered and repaired into protected database records.  Learned
profiles follow a candidate -> validated -> active -> retired lifecycle and
promotion always fails closed when their execution adapter is unavailable.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib.resources import files
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.models.transformation_profile import (
    RegisteredTransformationProfile,
    TransformationAdapter,
    TransformationProfileVersion,
)
from shogun.schemas.transformation_profile import (
    TransformationProfileCandidateCreate,
    TransformationProfileValidationRequest,
)

LIFECYCLE_STATES = {"candidate", "validated", "active", "retired"}
ADAPTER_STATES = {"available", "planned", "unavailable", "disabled", "error"}
VALIDATION_THRESHOLD = 0.80
MAX_PROFILE_BYTES = 2_000_000
_FORBIDDEN_PROFILE_KEYS = {
    "access_token",
    "api_key",
    "authorization",
    "client_secret",
    "code",
    "command",
    "credential",
    "credentials",
    "eval",
    "exec",
    "password",
    "private_key",
    "python",
    "refresh_token",
    "script",
    "secret",
    "shell",
    "tenant_url",
}


class TransformationProfileRegistryError(ValueError):
    """Base error for registry and lifecycle violations."""


class TransformationProfileNotFoundError(TransformationProfileRegistryError):
    pass


class TransformationProfileLifecycleError(TransformationProfileRegistryError):
    pass


class TransformationAdapterUnavailableError(TransformationProfileRegistryError):
    pass


class ProtectedTransformationProfileError(TransformationProfileRegistryError):
    pass


@dataclass(frozen=True, slots=True)
class BundledProfileDescriptor:
    profile_id: str
    display_name: str
    description: str | None
    platform: str
    domain: str
    version: int
    lifecycle: str
    adapter_id: str
    required_adapter_status: str
    definition: dict[str, Any]
    source_resource: str
    metadata: dict[str, Any]

    @property
    def content_hash(self) -> str:
        return profile_content_hash(self.definition)


def profile_content_hash(definition: dict[str, Any]) -> str:
    """Return a stable SHA-256 over a profile definition."""

    encoded = json.dumps(
        definition,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _contains_forbidden_profile_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = re.sub(r"[^a-z0-9]+", "_", str(key).casefold()).strip("_")
            if normalized in _FORBIDDEN_PROFILE_KEYS or _contains_forbidden_profile_key(child):
                return True
    elif isinstance(value, list):
        return any(_contains_forbidden_profile_key(item) for item in value)
    return False


def _clean_identifier(value: Any, *, label: str) -> str:
    identifier = str(value or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9_.-]*[A-Za-z0-9])?", identifier):
        raise TransformationProfileRegistryError(f"{label} is invalid: {identifier!r}")
    return identifier


def _normalized_lifecycle(value: Any, *, default: str = "candidate") -> str:
    if isinstance(value, dict):
        value = value.get("status") or value.get("state")
    state = str(value or default).strip().lower()
    # ``bundled`` is provenance, not a lifecycle state.  Package profiles
    # still enter the governed candidate gate unless the manifest explicitly
    # declares them validated/active.
    if state == "bundled":
        state = "candidate"
    if state not in LIFECYCLE_STATES:
        raise TransformationProfileRegistryError(f"Unsupported profile lifecycle {state!r}")
    return state


def _normalized_adapter_status(value: Any, *, default: str = "planned") -> str:
    state = str(value or default).strip().lower().replace("-", "_")
    aliases = {
        "ready": "available",
        "implemented": "available",
        "not_implemented": "planned",
        "missing": "unavailable",
        "fail_closed": "unavailable",
    }
    state = aliases.get(state, state)
    if state not in ADAPTER_STATES:
        raise TransformationProfileRegistryError(f"Unsupported adapter status {state!r}")
    return state


def _adapter_requirement(definition: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    raw = definition.get("adapter_requirements")
    requirement: dict[str, Any]
    if isinstance(raw, list):
        requirement = next((item for item in raw if isinstance(item, dict)), {})
    elif isinstance(raw, dict):
        requirement = raw
    else:
        requirement = {}
    adapter_id = (
        definition.get("adapter")
        or requirement.get("adapter_id")
        or requirement.get("id")
        or requirement.get("adapter")
    )
    adapter_id = _clean_identifier(adapter_id, label="Transformation adapter id")
    status = _normalized_adapter_status(
        requirement.get("status") or definition.get("adapter_status"),
        default="available" if definition.get("adapter") else "planned",
    )
    return adapter_id, status, requirement


def _declared_version(definition: dict[str, Any], profile_id: str) -> int:
    raw = (
        definition.get("registry_version")
        or definition.get("profile_version")
        or definition.get("version")
    )
    if isinstance(raw, int) and raw >= 1:
        return raw
    if raw is not None:
        match = re.search(r"\d+", str(raw))
        if match and int(match.group()) >= 1:
            return int(match.group())
    suffix = re.search(r"(?:^|[_-])v(\d+)$", profile_id, re.IGNORECASE)
    return int(suffix.group(1)) if suffix else 1


def _platform_name(definition: dict[str, Any]) -> str:
    platform = definition.get("platform")
    if isinstance(platform, dict):
        return str(platform.get("product") or platform.get("vendor") or "generic")
    return str(platform or definition.get("vendor") or "generic")


def _domain_name(definition: dict[str, Any]) -> str:
    platform = definition.get("platform")
    contract = definition.get("canonical_contract")
    if definition.get("domain"):
        return str(definition["domain"])
    if isinstance(platform, dict) and platform.get("family"):
        return str(platform["family"])
    if isinstance(contract, dict) and contract.get("record_kind"):
        return str(contract["record_kind"])
    return str(definition.get("object_type") or "document")


def _descriptor_from_resource(name: str, definition: Any) -> BundledProfileDescriptor | None:
    """Normalize one resource, returning ``None`` for catalog/index files."""

    if not isinstance(definition, dict):
        return None
    resource_type = str(definition.get("resource_type") or definition.get("kind") or "").lower()
    if resource_type in {
        "catalog",
        "profile_catalog",
        "transformation_profile_catalog",
        "registry",
        "index",
    } or name.lower().startswith("catalog"):
        return None
    # Catalogs are intentionally not duplicated into the live registry.
    if "profiles" in definition and not definition.get("id"):
        return None
    if not definition.get("id"):
        return None

    profile_id = _clean_identifier(definition.get("id"), label="Transformation profile id")
    adapter_id, adapter_status, requirement = _adapter_requirement(definition)
    metadata = dict(definition.get("metadata") or {})
    source = definition.get("source") if isinstance(definition.get("source"), dict) else {}
    metadata.update(
        {
            "canonical_contract": definition.get("canonical_contract"),
            "platform": definition.get("platform"),
            "source_modes": definition.get("source_modes")
            or definition.get("source_kinds")
            or ([source.get("transport")] if source.get("transport") else []),
            "adapter_requirements": requirement,
        }
    )
    return BundledProfileDescriptor(
        profile_id=profile_id,
        display_name=str(
            definition.get("display_name")
            or definition.get("title")
            or definition.get("name")
            or profile_id.replace("_", " ").title()
        )[:255],
        description=(str(definition.get("description"))[:5000] if definition.get("description") else None),
        platform=_platform_name(definition)[:100],
        domain=_domain_name(definition)[:100],
        version=_declared_version(definition, profile_id),
        lifecycle=_normalized_lifecycle(
            definition.get("lifecycle") or definition.get("status"),
            default="candidate",
        ),
        adapter_id=adapter_id,
        required_adapter_status=adapter_status,
        definition=definition,
        source_resource=name,
        metadata={key: value for key, value in metadata.items() if value is not None},
    )


def discover_bundled_profile_manifests(resource_root: Any | None = None) -> list[BundledProfileDescriptor]:
    """Discover individual bundled JSON manifests without a duplicated index."""

    root = resource_root or files("shogun").joinpath("resources", "transformation_profiles")
    descriptors: list[BundledProfileDescriptor] = []
    seen: set[str] = set()
    for resource in sorted(root.iterdir(), key=lambda item: item.name.lower()):
        if not resource.name.lower().endswith(".json") or not resource.is_file():
            continue
        try:
            raw = json.loads(resource.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeError) as exc:
            raise TransformationProfileRegistryError(
                f"Bundled transformation profile resource '{resource.name}' is invalid."
            ) from exc
        descriptor = _descriptor_from_resource(resource.name, raw)
        if descriptor is None:
            continue
        if descriptor.profile_id in seen:
            raise TransformationProfileRegistryError(
                f"Bundled transformation profile id '{descriptor.profile_id}' is duplicated."
            )
        seen.add(descriptor.profile_id)
        descriptors.append(descriptor)
    return descriptors


def _runtime_adapter_catalog() -> dict[str, dict[str, Any]]:
    """Return implementations actually registered in this running build."""

    try:
        from shogun.services.enterprise_transformations import registered_transformation_adapters

        raw = registered_transformation_adapters()
        if isinstance(raw, dict):
            return {
                str(adapter_id): (
                    dict(metadata) if isinstance(metadata, dict) else {"status": str(metadata)}
                )
                for adapter_id, metadata in raw.items()
            }
    except (ImportError, AttributeError):
        pass

    # Compatibility while older installations are upgraded: the original
    # deterministic adapter is known to exist in structured_transformations.
    try:
        from shogun.services.structured_transformations import SUPPORTED_ADAPTER

        return {
            str(SUPPORTED_ADAPTER): {
                "status": "available",
                "implementation": (
                    "shogun.services.structured_transformations:"
                    "try_deterministic_matrix_transform"
                ),
                "capabilities": ["pdf_text", "excel_template", "matrix_output"],
            }
        }
    except (ImportError, AttributeError):
        return {}


def _static_profile_validation(
    definition: dict[str, Any],
    *,
    expected_profile_id: str,
    expected_adapter_id: str,
) -> dict[str, Any]:
    """Perform bounded structural and regex checks before fixture evidence."""

    if not isinstance(definition, dict):
        raise TransformationProfileRegistryError("Profile definition must be an object.")
    if _contains_forbidden_profile_key(definition):
        raise TransformationProfileRegistryError(
            "Profile definitions cannot contain credentials, tenant URLs, or executable code."
        )
    encoded = json.dumps(definition, sort_keys=True, ensure_ascii=False).encode("utf-8")
    if len(encoded) > MAX_PROFILE_BYTES:
        raise TransformationProfileRegistryError(
            f"Profile definition exceeds the {MAX_PROFILE_BYTES}-byte safety limit."
        )
    declared_id = _clean_identifier(definition.get("id"), label="Transformation profile id")
    if declared_id != expected_profile_id:
        raise TransformationProfileRegistryError("Profile definition id does not match its registry id.")
    adapter_id, _status, _requirement = _adapter_requirement(definition)
    if adapter_id != expected_adapter_id:
        raise TransformationProfileRegistryError("Profile definition adapter does not match its version.")

    regex_count = 0

    def visit(value: Any, path: str = "$") -> None:
        nonlocal regex_count
        if isinstance(value, dict):
            for key, nested in value.items():
                child_path = f"{path}.{key}"
                if key.endswith("_pattern") and isinstance(nested, str):
                    if len(nested) > 10_000:
                        raise TransformationProfileRegistryError(
                            f"Regex at {child_path} exceeds the safety limit."
                        )
                    try:
                        re.compile(nested)
                    except (RecursionError, re.error) as exc:
                        raise TransformationProfileRegistryError(
                            f"Invalid regex at {child_path}: {exc}"
                        ) from exc
                    regex_count += 1
                elif key.endswith("_patterns") and isinstance(nested, list):
                    for index, pattern in enumerate(nested):
                        if not isinstance(pattern, str):
                            raise TransformationProfileRegistryError(
                                f"Regex at {child_path}[{index}] must be a string."
                            )
                        if len(pattern) > 10_000:
                            raise TransformationProfileRegistryError(
                                f"Regex at {child_path}[{index}] exceeds the safety limit."
                            )
                        try:
                            re.compile(pattern)
                        except (RecursionError, re.error) as exc:
                            raise TransformationProfileRegistryError(
                                f"Invalid regex at {child_path}[{index}]: {exc}"
                            ) from exc
                        regex_count += 1
                visit(nested, child_path)
        elif isinstance(value, list):
            for index, nested in enumerate(value):
                visit(nested, f"{path}[{index}]")

    visit(definition)
    enterprise_schema_valid = None
    try:
        from shogun.mapping.errors import MappingError
        from shogun.services.enterprise_transformations import (
            CANONICAL_ENTITY_ADAPTER,
            validate_enterprise_profile_manifest,
        )

        if expected_adapter_id == CANONICAL_ENTITY_ADAPTER:
            try:
                validate_enterprise_profile_manifest(definition)
            except MappingError as exc:
                raise TransformationProfileRegistryError(
                    f"Enterprise profile schema validation failed: {exc}"
                ) from exc
            enterprise_schema_valid = True
    except ImportError:
        pass
    return {
        "schema_valid": True,
        "enterprise_schema_valid": enterprise_schema_valid,
        "definition_bytes": len(encoded),
        "regexes_compiled": regex_count,
        "content_hash": profile_content_hash(definition),
    }


def _fixture_minimums(definition: dict[str, Any]) -> tuple[int, int]:
    governance = definition.get("governance")
    if not isinstance(governance, dict):
        governance = {}
    try:
        positives = int(governance.get("minimum_positive_fixtures", 1))
        negatives = int(governance.get("minimum_negative_fixtures", 1))
    except (TypeError, ValueError) as exc:
        raise TransformationProfileRegistryError(
            "Profile fixture governance counts must be integers."
        ) from exc
    if not 1 <= positives <= 20 or not 1 <= negatives <= 20:
        raise TransformationProfileRegistryError(
            "Profile fixture governance counts must be between 1 and 20."
        )
    return positives, negatives


def _validation_manifest(definition: dict[str, Any]) -> dict[str, Any]:
    """Return an isolated executable copy; never mutate the candidate payload."""

    manifest = json.loads(json.dumps(definition))
    manifest["lifecycle"] = "validated"
    requirements = manifest.get("adapter_requirements")
    if not isinstance(requirements, dict):
        requirements = {}
    requirements["status"] = "available"
    requirements.setdefault("adapter", manifest.get("adapter"))
    manifest["adapter_requirements"] = requirements
    return manifest


def _assert_positive_fixture(result: dict[str, Any], fixture: Any) -> int:
    """Check optional deterministic fixture assertions and return check count."""

    checks = 1  # successful adapter execution
    if fixture.expected_record_count is not None:
        actual = int(result.get("records_written", len(result.get("rows") or [])))
        if actual != fixture.expected_record_count:
            raise TransformationProfileLifecycleError(
                f"Fixture '{fixture.name}' expected {fixture.expected_record_count} record(s), "
                f"but produced {actual}."
            )
        checks += 1
    canonical = result.get("canonical") or {}
    contract = canonical.get("contract") or {}
    if fixture.expected_contract_id is not None:
        if str(contract.get("id") or "") != fixture.expected_contract_id:
            raise TransformationProfileLifecycleError(
                f"Fixture '{fixture.name}' produced an unexpected canonical contract."
            )
        checks += 1
    if fixture.expected_record_kind is not None:
        if str(canonical.get("record_kind") or "") != fixture.expected_record_kind:
            raise TransformationProfileLifecycleError(
                f"Fixture '{fixture.name}' produced an unexpected record kind."
            )
        checks += 1
    if fixture.expected_headers is not None:
        if list(result.get("headers") or []) != fixture.expected_headers:
            raise TransformationProfileLifecycleError(
                f"Fixture '{fixture.name}' produced unexpected headers."
            )
        checks += 1
    if fixture.expected_records is not None:
        if list(canonical.get("records") or []) != fixture.expected_records:
            raise TransformationProfileLifecycleError(
                f"Fixture '{fixture.name}' produced unexpected canonical records."
            )
        checks += 1
    if fixture.expected_rows is not None:
        if list(result.get("rows") or []) != fixture.expected_rows:
            raise TransformationProfileLifecycleError(
                f"Fixture '{fixture.name}' produced unexpected table rows."
            )
        checks += 1
    return checks


def _execute_validation_fixture(
    adapter_id: str,
    manifest: dict[str, Any],
    payload: Any,
    context: dict[str, Any],
) -> dict[str, Any]:
    if adapter_id == "canonical_entity_map_v1":
        from shogun.services.enterprise_transformations import (
            enterprise_profile_content_hash,
            execute_enterprise_profile,
            validate_enterprise_profile_manifest,
        )

        normalized = validate_enterprise_profile_manifest(manifest)
        registry_evidence = {
            "profile_id": str(normalized["id"]),
            "adapter_id": adapter_id,
            "status": "validation",
            "adapter_status": "available",
            "version": _declared_version(normalized, str(normalized["id"])),
            "content_hash": enterprise_profile_content_hash(normalized),
        }
        return execute_enterprise_profile(
            normalized,
            payload,
            context=context,
            registry_evidence=registry_evidence,
        )
    if adapter_id == "sectioned_record_matrix_v1":
        from shogun.services.structured_transformations import (
            try_deterministic_matrix_transform,
        )

        if not isinstance(payload, dict):
            raise TransformationProfileLifecycleError(
                "Sectioned-matrix fixtures require source_context and fixed_context."
            )
        result = try_deterministic_matrix_transform(
            profile=manifest,
            source_context=str(payload.get("source_context") or ""),
            fixed_context=str(payload.get("fixed_context") or ""),
        )
        return {
            "status": "SUCCESS",
            "rows": result.rows,
            "records_written": len(result.rows),
            "adapter_id": result.adapter_id,
        }
    raise TransformationAdapterUnavailableError(
        f"Adapter '{adapter_id}' has no executable registry validation harness."
    )


def _execute_fixture_evidence(
    *,
    adapter_id: str,
    definition: dict[str, Any],
    evidence: TransformationProfileValidationRequest,
) -> tuple[dict[str, Any], float]:
    from shogun.mapping.errors import MappingError

    minimum_positive, minimum_negative = _fixture_minimums(definition)
    if len(evidence.positive_fixtures) < minimum_positive:
        raise TransformationProfileLifecycleError(
            f"Profile requires at least {minimum_positive} positive validation fixture(s)."
        )
    if len(evidence.negative_fixtures) < minimum_negative:
        raise TransformationProfileLifecycleError(
            f"Profile requires at least {minimum_negative} negative validation fixture(s)."
        )
    manifest = _validation_manifest(definition)
    positive_report: list[dict[str, Any]] = []
    negative_report: list[dict[str, Any]] = []
    passed_checks = 0
    total_checks = 0

    for fixture in evidence.positive_fixtures:
        total_checks += 1
        try:
            result = _execute_validation_fixture(
                adapter_id,
                manifest,
                fixture.payload,
                fixture.context,
            )
            checks = _assert_positive_fixture(result, fixture)
        except (MappingError, TransformationProfileRegistryError, ValueError) as exc:
            positive_report.append(
                {"name": fixture.name, "passed": False, "error_type": type(exc).__name__}
            )
            raise TransformationProfileLifecycleError(
                f"Positive fixture '{fixture.name}' failed executable validation: {exc}"
            ) from exc
        passed_checks += checks
        total_checks += checks - 1
        positive_report.append(
            {
                "name": fixture.name,
                "passed": True,
                "records_written": int(
                    result.get("records_written", len(result.get("rows") or []))
                ),
                "assertions": checks - 1,
            }
        )

    for fixture in evidence.negative_fixtures:
        total_checks += 1
        try:
            _execute_validation_fixture(
                adapter_id,
                manifest,
                fixture.payload,
                fixture.context,
            )
        except (MappingError, TransformationProfileRegistryError, ValueError) as exc:
            code = str(getattr(exc, "code", type(exc).__name__))
            if fixture.expected_error_code and code != fixture.expected_error_code:
                negative_report.append(
                    {
                        "name": fixture.name,
                        "passed": False,
                        "error_code": code,
                    }
                )
                raise TransformationProfileLifecycleError(
                    f"Negative fixture '{fixture.name}' failed with {code}, expected "
                    f"{fixture.expected_error_code}."
                ) from exc
            passed_checks += 1
            negative_report.append(
                {"name": fixture.name, "passed": True, "error_code": code}
            )
        else:
            negative_report.append({"name": fixture.name, "passed": False})
            raise TransformationProfileLifecycleError(
                f"Negative fixture '{fixture.name}' was incorrectly accepted."
            )

    score = passed_checks / total_checks if total_checks else 0.0
    return (
        {
            "minimum_positive_fixtures": minimum_positive,
            "minimum_negative_fixtures": minimum_negative,
            "positive_fixtures": positive_report,
            "negative_fixtures": negative_report,
            "passed_checks": passed_checks,
            "total_checks": total_checks,
        },
        score,
    )


class TransformationProfileRegistryService:
    """Database-backed profile lifecycle and bundled repair service."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def _adapter(
        self,
        adapter_id: str,
        *,
        required_status: str = "planned",
        requirement: dict[str, Any] | None = None,
    ) -> TransformationAdapter:
        runtime = _runtime_adapter_catalog().get(adapter_id)
        if runtime is not None:
            status = _normalized_adapter_status(runtime.get("status"), default="available")
            implementation = runtime.get("implementation")
            capabilities = list(runtime.get("capabilities") or [])
            managed_by = "runtime"
            adapter_metadata = {
                "managed_by": managed_by,
                "version": runtime.get("version"),
                "input_kinds": list(runtime.get("input_kinds") or []),
            }
        else:
            # A manifest cannot claim that missing code is executable.
            requested = _normalized_adapter_status(required_status)
            status = "unavailable" if requested == "available" else requested
            implementation = None
            capabilities = list((requirement or {}).get("capabilities") or [])
            managed_by = "manifest"
            adapter_metadata = {
                "managed_by": managed_by,
                "version": (requirement or {}).get("minimum_version"),
                "input_kinds": list((requirement or {}).get("input_kinds") or []),
            }

        adapter = await self.session.get(TransformationAdapter, adapter_id)
        if adapter is None:
            adapter = TransformationAdapter(
                adapter_id=adapter_id,
                display_name=str((runtime or {}).get("display_name") or adapter_id)[:255],
                status=status,
                implementation=implementation,
                capabilities=capabilities,
                metadata_json=adapter_metadata,
            )
            self.session.add(adapter)
        else:
            adapter.status = status
            adapter.implementation = implementation
            adapter.capabilities = capabilities
            adapter.metadata_json = {**(adapter.metadata_json or {}), **adapter_metadata}
        await self.session.flush()
        return adapter

    async def sync_bundled_profiles(self, resource_root: Any | None = None) -> dict[str, int]:
        """Seed and repair all bundled profiles, preserving learned active versions."""

        descriptors = discover_bundled_profile_manifests(resource_root)
        stats = {
            "discovered": len(descriptors),
            "profiles_created": 0,
            "profiles_repaired": 0,
            "profiles_localized": 0,
            "versions_created": 0,
            "versions_reused": 0,
            "validated": 0,
            "validation_reused": 0,
            "validation_failed": 0,
            "activated": 0,
            "tenant_active_preserved": 0,
            "active_profiles": 0,
            "candidate_profiles": 0,
            "bundled_active_profiles": 0,
            "bundled_candidate_profiles": 0,
        }
        package_trusted = resource_root is None
        bundled_ids = {descriptor.profile_id for descriptor in descriptors}
        previously_bundled = list(
            (
                await self.session.execute(
                    select(RegisteredTransformationProfile).where(
                        RegisteredTransformationProfile.bundled.is_(True)
                    )
                )
            ).scalars().all()
        )
        for profile in previously_bundled:
            if profile.profile_key in bundled_ids:
                continue
            # A removed package resource may be a customer-owned profile from
            # an older build. Preserve every version and active pointer, but
            # stop presenting or protecting it as a bundled standard.
            metadata = dict(profile.metadata_json or {})
            metadata.pop("bundled_manifest_hash", None)
            metadata.update(
                {
                    "distribution": "local_private",
                    "former_bundled": True,
                }
            )
            profile.metadata_json = metadata
            profile.bundled = False
            profile.protected = False
            profile.source_resource = None
            stats["profiles_localized"] += 1

        for descriptor in descriptors:
            static_validation = _static_profile_validation(
                descriptor.definition,
                expected_profile_id=descriptor.profile_id,
                expected_adapter_id=descriptor.adapter_id,
            )
            requirement = descriptor.metadata.get("adapter_requirements") or {}
            adapter = await self._adapter(
                descriptor.adapter_id,
                required_status=descriptor.required_adapter_status,
                requirement=requirement if isinstance(requirement, dict) else {},
            )
            profile = await self.session.scalar(
                select(RegisteredTransformationProfile).where(
                    RegisteredTransformationProfile.profile_key == descriptor.profile_id
                )
            )
            if profile is None:
                profile = RegisteredTransformationProfile(
                    profile_key=descriptor.profile_id,
                    display_name=descriptor.display_name,
                    description=descriptor.description,
                    platform=descriptor.platform,
                    domain=descriptor.domain,
                    lifecycle_status="candidate",
                    protected=True,
                    bundled=True,
                    source_resource=descriptor.source_resource,
                    metadata_json={},
                )
                self.session.add(profile)
                await self.session.flush()
                stats["profiles_created"] += 1
            else:
                stats["profiles_repaired"] += 1
                profile.display_name = descriptor.display_name
                profile.description = descriptor.description
                profile.platform = descriptor.platform
                profile.domain = descriptor.domain
                profile.protected = True
                profile.bundled = True
                profile.is_deleted = False
                profile.deleted_at = None
                profile.source_resource = descriptor.source_resource
            profile.metadata_json = {
                **(profile.metadata_json or {}),
                **descriptor.metadata,
                "bundled_manifest_hash": descriptor.content_hash,
            }

            version = await self.session.scalar(
                select(TransformationProfileVersion)
                .where(
                    TransformationProfileVersion.profile_id == profile.id,
                    TransformationProfileVersion.content_hash == descriptor.content_hash,
                    TransformationProfileVersion.origin == "bundled",
                )
                .order_by(TransformationProfileVersion.version_number.desc())
            )
            if version is None:
                maximum = await self.session.scalar(
                    select(func.max(TransformationProfileVersion.version_number)).where(
                        TransformationProfileVersion.profile_id == profile.id
                    )
                )
                next_version = max(descriptor.version, int(maximum or 0) + 1)
                parent = await self._active_version(profile)
                initial_status = "candidate"
                version = TransformationProfileVersion(
                    profile_id=profile.id,
                    version_number=next_version,
                    status=initial_status,
                    adapter_id=descriptor.adapter_id,
                    required_adapter_status=descriptor.required_adapter_status,
                    origin="bundled",
                    content_hash=descriptor.content_hash,
                    definition=descriptor.definition,
                    parent_version_id=parent.id if parent else None,
                    validation_score=1.0 if initial_status == "validated" else None,
                    validation_report={
                        "static": static_validation,
                        "bundled": True,
                        "package_validated": initial_status == "validated",
                    },
                    metadata_json={"source_resource": descriptor.source_resource},
                    created_by="bundled_profile_sync",
                    updated_by="bundled_profile_sync",
                )
                self.session.add(version)
                await self.session.flush()
                stats["versions_created"] += 1
            else:
                stats["versions_reused"] += 1

            validation_gates = (version.validation_report or {}).get("gates") or {}
            has_server_evidence = bool(validation_gates) and all(
                bool(value) for value in validation_gates.values()
            )
            if (
                version.origin == "bundled"
                and not has_server_evidence
                and version.status != "candidate"
            ):
                if profile.active_version_id == version.id:
                    profile.active_version_id = None
                version.status = "candidate"
                version.activated_at = None
                version.retired_at = None
                profile.lifecycle_status = "candidate"

            active = await self._active_version(profile)
            if (
                package_trusted
                and version.origin == "bundled"
                and descriptor.adapter_id == "canonical_entity_map_v1"
                and descriptor.required_adapter_status == "available"
                and adapter.status == "available"
            ):
                validated_now = await self._validate_bundled_version(
                    profile=profile,
                    version=version,
                    static_validation=static_validation,
                    adapter=adapter,
                )
                if validated_now is None:
                    stats["validation_failed"] += 1
                elif validated_now:
                    stats["validated"] += 1
                else:
                    stats["validation_reused"] += 1

                active = await self._active_version(profile)
                if version.status == "validated" and (
                    active is None
                    or active.id == version.id
                    or active.origin == "bundled"
                ):
                    was_active = active is not None
                    activates_new_version = active is None or active.id != version.id
                    await self._activate(
                        profile,
                        version,
                        actor="bundled_profile_validation",
                    )
                    if not was_active or activates_new_version:
                        stats["activated"] += 1
                    active = version
                elif version.status == "validated" and active.id != version.id:
                    # A locally learned/SkillOpt version always wins over a
                    # package seed. The new package version remains validated
                    # and can be promoted explicitly later.
                    stats["tenant_active_preserved"] += 1
            if active is not None and active.status == "active":
                profile.lifecycle_status = "active"
            elif active is None:
                profile.lifecycle_status = version.status

        stats["active_profiles"] = int(
            await self.session.scalar(
                select(func.count(RegisteredTransformationProfile.id)).where(
                    RegisteredTransformationProfile.is_deleted.is_(False),
                    RegisteredTransformationProfile.lifecycle_status == "active",
                )
            )
            or 0
        )
        stats["candidate_profiles"] = int(
            await self.session.scalar(
                select(func.count(RegisteredTransformationProfile.id)).where(
                    RegisteredTransformationProfile.is_deleted.is_(False),
                    RegisteredTransformationProfile.lifecycle_status == "candidate",
                )
            )
            or 0
        )
        stats["bundled_active_profiles"] = int(
            await self.session.scalar(
                select(func.count(RegisteredTransformationProfile.id)).where(
                    RegisteredTransformationProfile.is_deleted.is_(False),
                    RegisteredTransformationProfile.bundled.is_(True),
                    RegisteredTransformationProfile.lifecycle_status == "active",
                )
            )
            or 0
        )
        stats["bundled_candidate_profiles"] = int(
            await self.session.scalar(
                select(func.count(RegisteredTransformationProfile.id)).where(
                    RegisteredTransformationProfile.is_deleted.is_(False),
                    RegisteredTransformationProfile.bundled.is_(True),
                    RegisteredTransformationProfile.lifecycle_status == "candidate",
                )
            )
            or 0
        )
        await self.session.flush()
        return stats

    async def _validate_bundled_version(
        self,
        *,
        profile: RegisteredTransformationProfile,
        version: TransformationProfileVersion,
        static_validation: dict[str, Any],
        adapter: TransformationAdapter,
    ) -> bool | None:
        """Validate one trusted package version, returning new/reused/failed.

        Package provenance alone never grants execution. The immutable version
        must pass the same server-side fixture gates used by learned profiles.
        The evidence signature includes profile content and runtime adapter
        version so an updated adapter is revalidated automatically.
        """

        from shogun.services.bundled_transformation_profile_fixtures import (
            BUNDLED_FIXTURE_POLICY,
            build_bundled_validation_request,
        )

        adapter_version = (adapter.metadata_json or {}).get("version")
        validation_report = version.validation_report or {}
        package_validation = validation_report.get("package_validation") or {}
        gates = validation_report.get("gates") or {}
        stored_fixtures = validation_report.get("fixtures") or {}
        if not isinstance(package_validation, dict):
            package_validation = {}
        if not isinstance(gates, dict):
            gates = {}
        if not isinstance(stored_fixtures, dict):
            stored_fixtures = {}
        stored_positive = stored_fixtures.get("positive_fixtures") or []
        stored_negative = stored_fixtures.get("negative_fixtures") or []
        if not isinstance(stored_positive, list):
            stored_positive = []
        if not isinstance(stored_negative, list):
            stored_negative = []
        minimum_positive, minimum_negative = _fixture_minimums(version.definition)
        evidence_current = (
            package_validation.get("policy") == BUNDLED_FIXTURE_POLICY
            and package_validation.get("profile_content_hash") == version.content_hash
            and package_validation.get("adapter_version") == adapter_version
            and bool(gates)
            and all(bool(value) for value in gates.values())
            and len(stored_positive) >= minimum_positive
            and len(stored_negative) >= minimum_negative
            and all(
                isinstance(item, dict) and bool(item.get("passed"))
                for item in stored_positive
            )
            and all(
                isinstance(item, dict) and bool(item.get("passed"))
                for item in stored_negative
            )
            and (version.validation_score or 0.0) >= VALIDATION_THRESHOLD
        )
        if evidence_current:
            active = await self._active_version(profile)
            if active is None or active.id != version.id:
                version.status = "validated"
                version.updated_by = "bundled_profile_validation"
            return False

        try:
            evidence = build_bundled_validation_request(version.definition)
            fixture_report, validation_score = _execute_fixture_evidence(
                adapter_id=version.adapter_id,
                definition=version.definition,
                evidence=evidence,
            )
            gates = {
                "schema_valid": bool(static_validation.get("schema_valid")),
                "fixtures_passed": all(
                    item.get("passed") for item in fixture_report["positive_fixtures"]
                ),
                "negative_fixtures_passed": all(
                    item.get("passed") for item in fixture_report["negative_fixtures"]
                ),
                "security_passed": True,
                "reconciliation_passed": fixture_report["passed_checks"]
                == fixture_report["total_checks"],
            }
            if not all(gates.values()) or validation_score < VALIDATION_THRESHOLD:
                raise TransformationProfileLifecycleError(
                    "Bundled executable fixture gates did not reconcile."
                )
        except (TransformationProfileRegistryError, ValueError) as exc:
            active = await self._active_version(profile)
            if active is not None and active.id == version.id:
                profile.active_version_id = None
                profile.lifecycle_status = "candidate"
            version.status = "candidate"
            version.validation_score = None
            version.activated_at = None
            version.validation_report = {
                "static": static_validation,
                "bundled": True,
                "package_validation": {
                    "policy": BUNDLED_FIXTURE_POLICY,
                    "profile_content_hash": version.content_hash,
                    "adapter_version": adapter_version,
                    "passed": False,
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:2000],
                },
            }
            version.updated_by = "bundled_profile_validation"
            return None

        version.validation_score = validation_score
        version.validation_report = {
            "static": static_validation,
            "gates": gates,
            "fixtures": fixture_report,
            "report": evidence.report,
            "bundled": True,
            "package_validation": {
                "policy": BUNDLED_FIXTURE_POLICY,
                "profile_content_hash": version.content_hash,
                "adapter_version": adapter_version,
                "passed": True,
            },
            "validated_by": evidence.actor,
            "validated_at": datetime.now(timezone.utc).isoformat(),
        }
        version.status = "validated"
        version.updated_by = evidence.actor
        return True

    async def list_profiles(
        self,
        *,
        lifecycle: str | None = None,
        platform: str | None = None,
        include_deleted: bool = False,
    ) -> list[dict[str, Any]]:
        query = select(RegisteredTransformationProfile)
        if not include_deleted:
            query = query.where(RegisteredTransformationProfile.is_deleted.is_(False))
        if lifecycle:
            query = query.where(
                RegisteredTransformationProfile.lifecycle_status == _normalized_lifecycle(lifecycle)
            )
        if platform:
            query = query.where(RegisteredTransformationProfile.platform == platform)
        query = query.order_by(
            RegisteredTransformationProfile.platform,
            RegisteredTransformationProfile.display_name,
        )
        records = list((await self.session.execute(query)).scalars().all())
        return [await self.profile_data(record, include_versions=False) for record in records]

    async def list_adapters(self) -> list[dict[str, Any]]:
        records = list(
            (
                await self.session.execute(
                    select(TransformationAdapter).order_by(TransformationAdapter.adapter_id)
                )
            ).scalars().all()
        )
        return [self.adapter_data(record) for record in records]

    async def get_profile(self, profile_key: str) -> RegisteredTransformationProfile:
        profile = await self.session.scalar(
            select(RegisteredTransformationProfile).where(
                RegisteredTransformationProfile.profile_key == profile_key,
                RegisteredTransformationProfile.is_deleted.is_(False),
            )
        )
        if profile is None:
            raise TransformationProfileNotFoundError(
                f"Transformation profile '{profile_key}' was not found."
            )
        return profile

    async def get_version(self, version_id: uuid.UUID) -> TransformationProfileVersion:
        version = await self.session.get(TransformationProfileVersion, version_id)
        if version is None:
            raise TransformationProfileNotFoundError(
                f"Transformation profile version '{version_id}' was not found."
            )
        return version

    async def create_candidate(
        self, body: TransformationProfileCandidateCreate
    ) -> TransformationProfileVersion:
        _static_profile_validation(
            body.definition,
            expected_profile_id=body.profile_id,
            expected_adapter_id=body.adapter_id,
        )
        adapter_id, required_status, requirement = _adapter_requirement(body.definition)
        adapter = await self._adapter(
            adapter_id,
            required_status=required_status,
            requirement=requirement,
        )
        profile = await self.session.scalar(
            select(RegisteredTransformationProfile).where(
                RegisteredTransformationProfile.profile_key == body.profile_id
            )
        )
        if profile is None:
            profile = RegisteredTransformationProfile(
                profile_key=body.profile_id,
                display_name=body.display_name,
                description=body.description,
                platform=body.platform,
                domain=body.domain,
                lifecycle_status="candidate",
                protected=False,
                bundled=False,
                metadata_json=dict(body.metadata),
                created_by=body.actor,
                updated_by=body.actor,
            )
            self.session.add(profile)
            await self.session.flush()
        elif profile.is_deleted:
            if profile.protected:
                profile.is_deleted = False
                profile.deleted_at = None
            else:
                raise TransformationProfileLifecycleError(
                    f"Transformation profile '{body.profile_id}' is retired/deleted."
                )

        content_hash = profile_content_hash(body.definition)
        duplicate = await self.session.scalar(
            select(TransformationProfileVersion).where(
                TransformationProfileVersion.profile_id == profile.id,
                TransformationProfileVersion.content_hash == content_hash,
            )
        )
        if duplicate is not None:
            raise TransformationProfileLifecycleError(
                "An identical transformation profile version already exists."
            )
        maximum = await self.session.scalar(
            select(func.max(TransformationProfileVersion.version_number)).where(
                TransformationProfileVersion.profile_id == profile.id
            )
        )
        parent = None
        if body.parent_version_id:
            parent = await self.get_version(body.parent_version_id)
            if parent.profile_id != profile.id:
                raise TransformationProfileLifecycleError(
                    "parent_version_id belongs to a different transformation profile."
                )
        else:
            parent = await self._active_version(profile)
        version = TransformationProfileVersion(
            profile_id=profile.id,
            version_number=int(maximum or 0) + 1,
            status="candidate",
            adapter_id=body.adapter_id,
            required_adapter_status=required_status,
            origin=body.origin,
            content_hash=content_hash,
            definition=json.loads(json.dumps(body.definition)),
            parent_version_id=parent.id if parent else None,
            validation_report={"static": _static_profile_validation(
                body.definition,
                expected_profile_id=body.profile_id,
                expected_adapter_id=body.adapter_id,
            )},
            metadata_json={**body.metadata, "adapter_status_at_creation": adapter.status},
            created_by=body.actor,
            updated_by=body.actor,
        )
        self.session.add(version)
        await self.session.flush()
        return version

    async def validate_candidate(
        self,
        version_id: uuid.UUID,
        evidence: TransformationProfileValidationRequest,
    ) -> TransformationProfileVersion:
        version = await self.get_version(version_id)
        if version.status != "candidate":
            raise TransformationProfileLifecycleError(
                f"Only candidate versions can be validated; version is {version.status}."
            )
        profile = await self.session.get(RegisteredTransformationProfile, version.profile_id)
        if profile is None:
            raise TransformationProfileNotFoundError("Transformation profile was not found.")
        static = _static_profile_validation(
            version.definition,
            expected_profile_id=profile.profile_key,
            expected_adapter_id=version.adapter_id,
        )
        _adapter_id, required_status, requirement = _adapter_requirement(version.definition)
        adapter = await self._adapter(
            version.adapter_id,
            required_status=required_status,
            requirement=requirement,
        )
        if adapter.status != "available":
            raise TransformationAdapterUnavailableError(
                f"Adapter '{version.adapter_id}' is {adapter.status}; executable validation "
                "is unavailable and promotion remains fail-closed."
            )
        fixture_report, validation_score = _execute_fixture_evidence(
            adapter_id=version.adapter_id,
            definition=version.definition,
            evidence=evidence,
        )
        gates = {
            "schema_valid": bool(static.get("schema_valid")),
            "fixtures_passed": all(
                item.get("passed") for item in fixture_report["positive_fixtures"]
            ),
            "negative_fixtures_passed": all(
                item.get("passed") for item in fixture_report["negative_fixtures"]
            ),
            "security_passed": True,
            "reconciliation_passed": fixture_report["passed_checks"]
            == fixture_report["total_checks"],
        }
        version.validation_score = validation_score
        version.validation_report = {
            "static": static,
            "gates": gates,
            "fixtures": fixture_report,
            "report": evidence.report,
            "validated_by": evidence.actor,
            "validated_at": datetime.now(timezone.utc).isoformat(),
        }
        version.updated_by = evidence.actor
        if not all(gates.values()) or validation_score < VALIDATION_THRESHOLD:
            raise TransformationProfileLifecycleError(
                "Server-executed profile validation failed: all fixture, security, schema, "
                "and reconciliation gates must pass with score "
                f">= {VALIDATION_THRESHOLD:.2f}."
            )
        version.status = "validated"
        if profile.active_version_id is None:
            profile.lifecycle_status = "validated"
        await self.session.flush()
        return version

    async def promote(
        self, version_id: uuid.UUID, *, actor: str = "system"
    ) -> TransformationProfileVersion:
        version = await self.get_version(version_id)
        if version.status != "validated":
            raise TransformationProfileLifecycleError(
                f"Only validated versions can be promoted; version is {version.status}."
            )
        validation_gates = (version.validation_report or {}).get("gates") or {}
        if (
            not validation_gates
            or not all(bool(value) for value in validation_gates.values())
            or (version.validation_score or 0.0) < VALIDATION_THRESHOLD
        ):
            raise TransformationProfileLifecycleError(
                "Profile promotion requires successful server-executed validation evidence."
            )
        required_adapter_status = _normalized_adapter_status(
            version.required_adapter_status
        )
        if required_adapter_status != "available":
            raise TransformationAdapterUnavailableError(
                f"Profile version requires adapter status '{required_adapter_status}'; "
                "only profiles whose declared adapter requirements are available can be promoted."
            )
        adapter = await self.session.get(TransformationAdapter, version.adapter_id)
        if adapter is None or adapter.status != "available":
            status = adapter.status if adapter else "unavailable"
            raise TransformationAdapterUnavailableError(
                f"Adapter '{version.adapter_id}' is {status}; profile promotion fails closed."
            )
        profile = await self.session.get(RegisteredTransformationProfile, version.profile_id)
        if profile is None or profile.is_deleted:
            raise TransformationProfileNotFoundError("Transformation profile was not found.")
        await self._activate(profile, version, actor=actor)
        await self.session.flush()
        return version

    async def retire(
        self,
        version_id: uuid.UUID,
        *,
        actor: str = "system",
        reason: str | None = None,
    ) -> TransformationProfileVersion:
        version = await self.get_version(version_id)
        if version.status == "retired":
            return version
        profile = await self.session.get(RegisteredTransformationProfile, version.profile_id)
        if profile is None:
            raise TransformationProfileNotFoundError("Transformation profile was not found.")
        version.status = "retired"
        version.retired_at = datetime.now(timezone.utc)
        version.updated_by = actor
        version.metadata_json = {**(version.metadata_json or {}), "retirement_reason": reason}
        if profile.active_version_id == version.id:
            profile.active_version_id = None
            remaining = await self.session.scalar(
                select(TransformationProfileVersion)
                .where(
                    TransformationProfileVersion.profile_id == profile.id,
                    TransformationProfileVersion.id != version.id,
                    TransformationProfileVersion.status.in_(["validated", "candidate"]),
                )
                .order_by(TransformationProfileVersion.version_number.desc())
            )
            profile.lifecycle_status = remaining.status if remaining else "retired"
        await self.session.flush()
        return version

    async def rollback(
        self,
        profile_key: str,
        *,
        target_version: int,
        actor: str = "system",
    ) -> TransformationProfileVersion:
        """Reactivate historical content as a new, auditable version."""

        profile = await self.get_profile(profile_key)
        target = await self.session.scalar(
            select(TransformationProfileVersion).where(
                TransformationProfileVersion.profile_id == profile.id,
                TransformationProfileVersion.version_number == target_version,
            )
        )
        if target is None:
            raise TransformationProfileNotFoundError(
                f"Transformation profile '{profile_key}' has no version {target_version}."
            )
        if target.status not in {"validated", "retired", "active"}:
            raise TransformationProfileLifecycleError(
                "Only validated, active, or retired versions can be rollback targets."
            )
        adapter = await self.session.get(TransformationAdapter, target.adapter_id)
        if adapter is None or adapter.status != "available":
            raise TransformationAdapterUnavailableError(
                f"Adapter '{target.adapter_id}' is not available; rollback fails closed."
            )
        maximum = await self.session.scalar(
            select(func.max(TransformationProfileVersion.version_number)).where(
                TransformationProfileVersion.profile_id == profile.id
            )
        )
        current = await self._active_version(profile)
        clone_definition = json.loads(json.dumps(target.definition))
        clone = TransformationProfileVersion(
            profile_id=profile.id,
            version_number=int(maximum or 0) + 1,
            status="validated",
            adapter_id=target.adapter_id,
            required_adapter_status=target.required_adapter_status,
            origin="rollback",
            content_hash=target.content_hash,
            definition=clone_definition,
            parent_version_id=current.id if current else target.id,
            validation_score=target.validation_score,
            validation_report={
                **(target.validation_report or {}),
                "rollback_of_version": target.version_number,
                "rollback_by": actor,
            },
            metadata_json={"rollback_of_version_id": str(target.id)},
            created_by=actor,
            updated_by=actor,
        )
        self.session.add(clone)
        await self.session.flush()
        await self._activate(profile, clone, actor=actor)
        await self.session.flush()
        return clone

    async def delete_profile(self, profile_key: str, *, actor: str = "system") -> None:
        profile = await self.get_profile(profile_key)
        if profile.protected:
            raise ProtectedTransformationProfileError(
                f"Bundled transformation profile '{profile_key}' is protected and cannot be deleted."
            )
        active = await self._active_version(profile)
        if active:
            await self.retire(active.id, actor=actor, reason="profile_deleted")
        profile.is_deleted = True
        profile.deleted_at = datetime.now(timezone.utc)
        profile.updated_by = actor
        await self.session.flush()

    async def resolve_active_definition(
        self,
        profile_key: str,
        *,
        expected_version: int | None = None,
        expected_hash: str | None = None,
    ) -> dict[str, Any]:
        """Resolve an immutable definition plus server-created trust evidence.

        Caller-provided lifecycle and adapter flags never establish trust.
        Optional version/hash pins let AgentFlow reject configuration drift.
        """

        profile = await self.get_profile(profile_key)
        version = await self._active_version(profile)
        if version is None or version.status != "active":
            raise TransformationProfileLifecycleError(
                f"Transformation profile '{profile_key}' has no active version."
            )
        if profile.lifecycle_status != "active":
            raise TransformationProfileLifecycleError(
                f"Transformation profile '{profile_key}' is not active."
            )
        if expected_version is not None and version.version_number != expected_version:
            raise TransformationProfileLifecycleError(
                f"Transformation profile '{profile_key}' active version is "
                f"{version.version_number}, not pinned version {expected_version}."
            )
        if expected_hash is not None and version.content_hash != expected_hash:
            raise TransformationProfileLifecycleError(
                f"Transformation profile '{profile_key}' active content hash does not match "
                "the AgentFlow pin."
            )
        actual_hash = profile_content_hash(version.definition)
        if actual_hash != version.content_hash:
            raise TransformationProfileLifecycleError(
                f"Transformation profile '{profile_key}' failed its registry integrity check."
            )
        _static_profile_validation(
            version.definition,
            expected_profile_id=profile.profile_key,
            expected_adapter_id=version.adapter_id,
        )
        _adapter_id, required_status, requirement = _adapter_requirement(version.definition)
        adapter = await self._adapter(
            version.adapter_id,
            required_status=required_status,
            requirement=requirement,
        )
        if adapter.status != "available":
            status = adapter.status
            raise TransformationAdapterUnavailableError(
                f"Transformation profile '{profile_key}' requires adapter "
                f"'{version.adapter_id}', which is {status}."
            )
        return {
            "definition": json.loads(json.dumps(version.definition)),
            "registry_evidence": {
                "profile_id": profile.profile_key,
                "version": version.version_number,
                "content_hash": version.content_hash,
                "status": "active",
                "adapter_id": version.adapter_id,
                "adapter_status": "available",
                "version_id": str(version.id),
            },
        }

    async def list_active_definitions(self) -> list[dict[str, Any]]:
        """Return every executable active profile as an integrity-checked envelope.

        This bulk resolver is intended for trusted in-process selectors such as
        Source Intelligence.  Definitions are never exposed by its preview API.
        A corrupt active row fails the complete lookup closed instead of being
        silently omitted and changing profile-selection behavior.
        """

        rows = (
            await self.session.execute(
                select(
                    RegisteredTransformationProfile,
                    TransformationProfileVersion,
                    TransformationAdapter,
                )
                .outerjoin(
                    TransformationProfileVersion,
                    TransformationProfileVersion.id
                    == RegisteredTransformationProfile.active_version_id,
                )
                .outerjoin(
                    TransformationAdapter,
                    TransformationAdapter.adapter_id
                    == TransformationProfileVersion.adapter_id,
                )
                .where(
                    RegisteredTransformationProfile.is_deleted.is_(False),
                    RegisteredTransformationProfile.lifecycle_status == "active",
                )
                .order_by(RegisteredTransformationProfile.profile_key)
            )
        ).all()
        resolved: list[dict[str, Any]] = []
        for profile, version, adapter in rows:
            if version is None or version.status != "active":
                raise TransformationProfileLifecycleError(
                    f"Transformation profile '{profile.profile_key}' has no valid active version."
                )
            if version.profile_id != profile.id:
                raise TransformationProfileLifecycleError(
                    f"Transformation profile '{profile.profile_key}' has an invalid active pointer."
                )
            if profile_content_hash(version.definition) != version.content_hash:
                raise TransformationProfileLifecycleError(
                    f"Transformation profile '{profile.profile_key}' failed its registry integrity check."
                )
            _static_profile_validation(
                version.definition,
                expected_profile_id=profile.profile_key,
                expected_adapter_id=version.adapter_id,
            )
            if (
                adapter is None
                or version.required_adapter_status != "available"
                or adapter.status != "available"
            ):
                adapter_status = adapter.status if adapter is not None else "unavailable"
                raise TransformationAdapterUnavailableError(
                    f"Transformation profile '{profile.profile_key}' requires adapter "
                    f"'{version.adapter_id}', which is {adapter_status}."
                )
            resolved.append(
                {
                    "definition": json.loads(json.dumps(version.definition)),
                    "registry_evidence": {
                        "profile_id": profile.profile_key,
                        "version": version.version_number,
                        "content_hash": version.content_hash,
                        "status": "active",
                        "adapter_id": version.adapter_id,
                        "adapter_status": "available",
                        "version_id": str(version.id),
                    },
                    "profile_metadata": {
                        "display_name": profile.display_name,
                        "platform": profile.platform,
                        "domain": profile.domain,
                        "protected": profile.protected,
                        "bundled": profile.bundled,
                    },
                }
            )
        return resolved

    async def profile_data(
        self,
        profile: RegisteredTransformationProfile,
        *,
        include_versions: bool = True,
    ) -> dict[str, Any]:
        versions: list[TransformationProfileVersion] = []
        if include_versions:
            versions = list(
                (
                    await self.session.execute(
                        select(TransformationProfileVersion)
                        .where(TransformationProfileVersion.profile_id == profile.id)
                        .order_by(TransformationProfileVersion.version_number.desc())
                    )
                ).scalars().all()
            )
        active = await self._active_version(profile)
        latest = versions[0] if versions else await self.session.scalar(
            select(TransformationProfileVersion)
            .where(TransformationProfileVersion.profile_id == profile.id)
            .order_by(TransformationProfileVersion.version_number.desc())
        )
        adapter_version = active or latest
        adapter = (
            await self.session.get(TransformationAdapter, adapter_version.adapter_id)
            if adapter_version is not None
            else None
        )
        execution_mode = None
        if adapter_version is not None:
            execution_mode = {
                "canonical_entity_map_v1": "profile",
                "sectioned_record_matrix_v1": "contract",
            }.get(adapter_version.adapter_id)
        blockers: list[str] = []
        if adapter_version is None:
            blockers.append("Profile has no registered version.")
        else:
            if active is None or active.status != "active" or profile.lifecycle_status != "active":
                failed_package_validation = (
                    (adapter_version.validation_report or {}).get("package_validation") or {}
                )
                if failed_package_validation.get("passed") is False:
                    blockers.append(
                        "Packaged executable fixture validation failed for this build."
                    )
                else:
                    blockers.append(
                        "Profile has not passed executable fixture validation and promotion."
                    )
            if adapter_version.required_adapter_status != "available":
                blockers.append(
                    "Profile requires adapter capabilities that are not implemented in this build."
                )
            if adapter is None or adapter.status != "available":
                blockers.append(
                    f"Runtime adapter '{adapter_version.adapter_id}' is not available."
                )
            if execution_mode is None:
                blockers.append(
                    f"Runtime adapter '{adapter_version.adapter_id}' has no AgentFlow execution mode."
                )
        source = (
            adapter_version.definition.get("source")
            if adapter_version is not None
            and isinstance(adapter_version.definition.get("source"), dict)
            else {}
        )
        data = {
            "id": str(profile.id),
            "profile_id": profile.profile_key,
            "display_name": profile.display_name,
            "description": profile.description,
            "platform": profile.platform,
            "domain": profile.domain,
            "lifecycle": profile.lifecycle_status,
            "protected": profile.protected,
            "bundled": profile.bundled,
            "active_version_id": str(profile.active_version_id) if profile.active_version_id else None,
            "active_version": active.version_number if active else None,
            "latest_version": latest.version_number if latest else None,
            "adapter_id": adapter_version.adapter_id if adapter_version else None,
            "adapter_status": adapter.status if adapter else None,
            "required_adapter_status": (
                adapter_version.required_adapter_status if adapter_version else None
            ),
            "selectable": not blockers,
            "execution_mode": execution_mode,
            "blockers": blockers,
            "source_requirement": {
                "input_kinds": list((adapter.metadata_json or {}).get("input_kinds") or [])
                if adapter is not None
                else [],
                "transport": source.get("transport"),
                "object": source.get("object"),
                "record_shape": source.get("record_shape"),
                "record_path": source.get("record_path"),
            },
            "source_resource": profile.source_resource,
            "metadata": profile.metadata_json or {},
            "created_at": profile.created_at,
            "updated_at": profile.updated_at,
        }
        if include_versions:
            data["versions"] = [await self.version_data(item) for item in versions]
        return data

    async def version_data(self, version: TransformationProfileVersion) -> dict[str, Any]:
        adapter = await self.session.get(TransformationAdapter, version.adapter_id)
        return {
            "id": str(version.id),
            "profile_id": str(version.profile_id),
            "version": version.version_number,
            "status": version.status,
            "adapter_id": version.adapter_id,
            "adapter_status": adapter.status if adapter else "unavailable",
            "required_adapter_status": version.required_adapter_status,
            "origin": version.origin,
            "content_hash": version.content_hash,
            "parent_version_id": str(version.parent_version_id) if version.parent_version_id else None,
            "validation_score": version.validation_score,
            "validation_report": version.validation_report or {},
            "definition": version.definition,
            "metadata": version.metadata_json or {},
            "activated_at": version.activated_at,
            "retired_at": version.retired_at,
            "created_at": version.created_at,
            "updated_at": version.updated_at,
        }

    @staticmethod
    def adapter_data(adapter: TransformationAdapter) -> dict[str, Any]:
        metadata = adapter.metadata_json or {}
        return {
            "adapter_id": adapter.adapter_id,
            "display_name": adapter.display_name,
            "status": adapter.status,
            "version": metadata.get("version"),
            "implementation": adapter.implementation,
            "input_kinds": metadata.get("input_kinds") or [],
            "capabilities": adapter.capabilities or [],
            "metadata": metadata,
            "updated_at": adapter.updated_at,
        }

    async def _active_version(
        self, profile: RegisteredTransformationProfile
    ) -> TransformationProfileVersion | None:
        if not profile.active_version_id:
            return None
        version = await self.session.get(
            TransformationProfileVersion, profile.active_version_id
        )
        if version is None or version.profile_id != profile.id:
            profile.active_version_id = None
            if profile.lifecycle_status == "active":
                profile.lifecycle_status = "validated"
            return None
        return version

    async def _activate(
        self,
        profile: RegisteredTransformationProfile,
        version: TransformationProfileVersion,
        *,
        actor: str,
    ) -> None:
        if version.profile_id != profile.id:
            raise TransformationProfileLifecycleError(
                "Cannot activate a version belonging to another profile."
            )
        current = await self._active_version(profile)
        now = datetime.now(timezone.utc)
        if current is not None and current.id != version.id:
            current.status = "retired"
            current.retired_at = now
            current.updated_by = actor
        version.status = "active"
        version.activated_at = now
        version.retired_at = None
        version.updated_by = actor
        profile.active_version_id = version.id
        profile.lifecycle_status = "active"
        profile.updated_by = actor


async def sync_bundled_transformation_profiles(
    session: AsyncSession,
    resource_root: Any | None = None,
) -> dict[str, int]:
    """Convenience entry point used by application startup repair."""

    return await TransformationProfileRegistryService(session).sync_bundled_profiles(
        resource_root
    )
