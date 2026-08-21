"""Generate non-confidential release metadata and a direct-dependency SPDX SBOM."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import tomllib

REPOSITORY = "AlphaHorizon-AI/Shogun"
REPOSITORY_URL = f"https://github.com/{REPOSITORY}"
_DEPENDENCY_NAME = re.compile(r"^([A-Za-z0-9_.-]+)(?:\[[^]]+\])?(.*)$")
_FULL_GIT_SHA = re.compile(r"^[0-9a-f]{40}$")


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _resolve_git_sha(root: Path, explicit: str | None) -> str | None:
    candidate = str(explicit or "").strip().lower()
    if _FULL_GIT_SHA.fullmatch(candidate):
        return candidate
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            check=False,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        completed = None
    if completed is not None:
        candidate = completed.stdout.strip().lower()
        if completed.returncode == 0 and _FULL_GIT_SHA.fullmatch(candidate):
            return candidate
    candidate = str(os.getenv("GITHUB_SHA") or "").strip().lower()
    return candidate if _FULL_GIT_SHA.fullmatch(candidate) else None


def _spdx_id(purl: str) -> str:
    digest = hashlib.sha256(purl.encode("utf-8")).hexdigest()[:16]
    return f"SPDXRef-Dependency-{digest}"


def _python_requirement(value: str) -> tuple[str, str | None] | None:
    declaration = value.split(";", 1)[0].strip()
    if " @ " in declaration:
        name, location = declaration.split(" @ ", 1)
        clean_name = name.split("[", 1)[0].strip()
        return (clean_name, f"direct URL: {location.strip()}") if clean_name else None
    match = _DEPENDENCY_NAME.fullmatch(declaration)
    if not match:
        return None
    name, constraint = match.groups()
    return name, constraint.strip() or None


def _component(
    *,
    name: str,
    purl: str,
    version: str | None,
    source: str,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "name": name,
        "SPDXID": _spdx_id(purl),
        "downloadLocation": "NOASSERTION",
        "filesAnalyzed": False,
        "licenseConcluded": "NOASSERTION",
        "licenseDeclared": "NOASSERTION",
        "copyrightText": "NOASSERTION",
        "externalRefs": [{
            "referenceCategory": "PACKAGE-MANAGER",
            "referenceType": "purl",
            "referenceLocator": purl,
        }],
        "comment": f"Direct dependency declared by {source}.",
    }
    if version:
        item["versionInfo"] = version
    return item


def _python_components(root: Path) -> list[dict[str, Any]]:
    components: dict[str, dict[str, Any]] = {}
    sources: dict[str, set[str]] = {}

    def add_declarations(source: str, declarations: list[str]) -> None:
        for declaration in declarations:
            parsed = _python_requirement(str(declaration))
            if parsed is None:
                raise ValueError(f"Could not parse Python dependency declaration: {declaration!r}")
            name, constraint = parsed
            normalized = name.lower().replace("_", "-")
            purl = f"pkg:pypi/{quote(normalized, safe='.-')}"
            if purl not in components:
                components[purl] = _component(
                    name=name,
                    purl=purl,
                    # pyproject/requirements entries are constraints, not
                    # proof of an installed version. Preserve them in the
                    # comment without populating SPDX versionInfo.
                    version=None,
                    source=source,
                )
            declaration_note = f"{source} ({constraint or 'no version constraint'})"
            sources.setdefault(purl, set()).add(declaration_note)

    for relative in (Path("pyproject.toml"), Path("gensui/pyproject.toml")):
        pyproject_path = root / relative
        if not pyproject_path.exists():
            continue
        pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
        project = pyproject.get("project", {})
        add_declarations(
            f"{relative.as_posix()}:project.dependencies",
            project.get("dependencies", []),
        )
        for name, values in project.get("optional-dependencies", {}).items():
            if name.casefold() == "dev":
                continue
            add_declarations(
                f"{relative.as_posix()}:project.optional-dependencies.{name}",
                values,
            )

    requirements_path = root / "telemetry_service" / "requirements.txt"
    if requirements_path.exists():
        declarations = [
            line.strip()
            for line in requirements_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith(("#", "-"))
        ]
        add_declarations("telemetry_service/requirements.txt", declarations)

    for purl, component in components.items():
        component["comment"] = (
            "Direct Python runtime/optional dependency declaration(s): "
            + ", ".join(sorted(sources[purl]))
            + ". Constraints are declaration-time metadata; SPDX versionInfo is intentionally omitted."
        )
    return list(components.values())


def _npm_components(root: Path) -> list[dict[str, Any]]:
    components: dict[str, dict[str, Any]] = {}
    for relative in (
        Path("frontend/package-lock.json"),
        Path("gensui/frontend/package-lock.json"),
        Path("bridge/teams/package-lock.json"),
    ):
        lock_path = root / relative
        if not lock_path.exists():
            continue
        lock = _read_json(lock_path)
        packages = lock.get("packages", {})
        root_package = packages.get("", {}) if isinstance(packages, dict) else {}
        declarations = root_package.get("dependencies", {}) if isinstance(root_package, dict) else {}
        if not isinstance(declarations, dict):
            continue
        for name, declared in declarations.items():
            locked = packages.get(f"node_modules/{name}", {}) if isinstance(packages, dict) else {}
            version = locked.get("version") if isinstance(locked, dict) else None
            version = str(version or declared or "").strip() or None
            encoded_name = quote(str(name).lower(), safe="/")
            purl = f"pkg:npm/{encoded_name}"
            if version and re.fullmatch(r"\d+(?:\.\d+)*(?:[-+][A-Za-z0-9.-]+)?", version):
                purl = f"{purl}@{quote(version, safe='.+-')}"
            item = _component(
                name=str(name),
                purl=purl,
                version=version,
                source=relative.as_posix(),
            )
            existing = components.get(purl)
            if existing:
                existing["comment"] += f" Also declared by {relative.as_posix()}."
            else:
                components[purl] = item
    return list(components.values())


def _spdx_created(released: object) -> str:
    value = str(released or "").strip()
    if value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            pass
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _release_notes(manifest: dict[str, Any], key: str) -> list[str]:
    value = manifest.get(key, [])
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def generate(
    root: Path,
    output_dir: Path,
    git_sha: str | None,
    require_git_sha: bool,
    release_tag: str | None = None,
) -> tuple[Path, Path]:
    root = root.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = _read_json(root / "version.json")
    source_commit = _resolve_git_sha(root, git_sha)
    if require_git_sha and source_commit is None:
        raise ValueError("A full 40-character Git SHA is required for official release evidence")

    version = str(manifest.get("version") or "0.0.0")
    build = int(manifest.get("build") or 0)
    normalized_tag = str(release_tag or "").strip()
    if normalized_tag and normalized_tag not in {version, f"v{version}"}:
        raise ValueError(
            f"Release tag {normalized_tag!r} does not match version.json version {version!r}"
        )
    release_metadata = {
        "schema_version": 1,
        "product": str(manifest.get("name") or "Shogun AFM"),
        "version": version,
        "build": build,
        "release_id": f"{version}+build.{build}",
        "channel": str(manifest.get("channel") or "unknown"),
        "release_date": manifest.get("released"),
        "git_sha": source_commit,
        "developer": "Alpha Horizon",
        "official_repository": REPOSITORY,
        "official_repository_url": REPOSITORY_URL,
        "changelog": str(manifest.get("changelog") or ""),
        "security_changes": _release_notes(manifest, "security_changes"),
        "breaking_changes": _release_notes(manifest, "breaking_changes"),
    }
    metadata_path = output_dir / "release-metadata.json"
    metadata_path.write_text(json.dumps(release_metadata, indent=2) + "\n", encoding="utf-8")

    dependencies = sorted(
        _python_components(root) + _npm_components(root),
        key=lambda item: (item["name"].lower(), item["SPDXID"]),
    )
    product_id = "SPDXRef-Package-Shogun-AFM"
    namespace_sha = source_commit or "source-commit-unavailable"
    sbom = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"Shogun AFM {version} build {build} direct dependencies",
        "documentNamespace": f"{REPOSITORY_URL}/sbom/{version}/build-{build}/{namespace_sha}",
        "creationInfo": {
            "created": _spdx_created(manifest.get("released")),
            "creators": [
                "Organization: Alpha Horizon",
                "Tool: scripts/generate_release_evidence.py",
            ],
            "licenseListVersion": "3.26",
        },
        "documentDescribes": [product_id],
        "packages": [{
            "name": "Shogun AFM",
            "SPDXID": product_id,
            "versionInfo": version,
            "downloadLocation": REPOSITORY_URL,
            "filesAnalyzed": False,
            "licenseConcluded": "NOASSERTION",
            "licenseDeclared": "NOASSERTION",
            "copyrightText": "NOASSERTION",
            "supplier": "Organization: Alpha Horizon",
            "externalRefs": [{
                "referenceCategory": "PACKAGE-MANAGER",
                "referenceType": "purl",
                "referenceLocator": f"pkg:github/AlphaHorizon-AI/Shogun@{version}",
            }],
            "comment": f"Build {build}; source commit {source_commit or 'not embedded'}.",
        }, *dependencies],
        "relationships": [
            {
                "spdxElementId": product_id,
                "relationshipType": "DEPENDS_ON",
                "relatedSpdxElement": dependency["SPDXID"],
            }
            for dependency in dependencies
        ],
    }
    sbom_path = output_dir / "shogun-direct-dependencies.spdx.json"
    sbom_path.write_text(json.dumps(sbom, indent=2) + "\n", encoding="utf-8")
    return metadata_path, sbom_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--git-sha")
    parser.add_argument("--require-git-sha", action="store_true")
    parser.add_argument("--release-tag")
    args = parser.parse_args()
    metadata, sbom = generate(
        args.root,
        args.output_dir,
        args.git_sha,
        args.require_git_sha,
        args.release_tag,
    )
    print(f"Generated {metadata}")
    print(f"Generated {sbom}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
