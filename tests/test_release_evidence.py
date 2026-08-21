from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from scripts import generate_release_evidence

ROOT = Path(__file__).resolve().parent.parent


def _purl(package: dict) -> str:
    return package["externalRefs"][0]["referenceLocator"]


def test_release_evidence_generates_traceable_metadata_and_structural_spdx(tmp_path):
    metadata_path, sbom_path = generate_release_evidence.generate(
        ROOT,
        tmp_path,
        "c" * 40,
        require_git_sha=True,
    )

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "version.json").read_text(encoding="utf-8"))
    assert metadata["version"] == manifest["version"]
    assert metadata["build"] == manifest["build"]
    assert metadata["git_sha"] == "c" * 40
    assert metadata["official_repository"] == "AlphaHorizon-AI/Shogun"

    sbom = json.loads(sbom_path.read_text(encoding="utf-8"))
    assert sbom["spdxVersion"] == "SPDX-2.3"
    assert sbom["dataLicense"] == "CC0-1.0"
    assert sbom["SPDXID"] == "SPDXRef-DOCUMENT"
    assert sbom["documentDescribes"] == ["SPDXRef-Package-Shogun-AFM"]
    assert "c" * 40 in sbom["documentNamespace"]

    packages = sbom["packages"]
    package_ids = [package["SPDXID"] for package in packages]
    assert len(package_ids) == len(set(package_ids))
    assert len(sbom["relationships"]) == len(packages) - 1
    for package in packages:
        assert package["name"]
        assert package["downloadLocation"]
        assert package["filesAnalyzed"] is False
        assert package["licenseConcluded"] == "NOASSERTION"
        assert package["licenseDeclared"] == "NOASSERTION"
        assert package["copyrightText"] == "NOASSERTION"


def test_sbom_covers_all_shipped_runtime_manifests_without_claiming_python_resolution(tmp_path):
    _, sbom_path = generate_release_evidence.generate(ROOT, tmp_path, "d" * 40, True)
    packages = json.loads(sbom_path.read_text(encoding="utf-8"))["packages"]
    by_name: dict[str, list[dict]] = {}
    for package in packages:
        by_name.setdefault(package["name"].casefold(), []).append(package)

    assert "fastapi" in by_name  # root + Gensui + telemetry Python manifests
    assert "psycopg" in by_name  # telemetry_service/requirements.txt
    assert "react" in by_name  # Tenshu/Gensui frontend locks
    assert "@microsoft/agents-hosting" in by_name  # Teams bridge lock

    fastapi = by_name["fastapi"][0]
    assert "versionInfo" not in fastapi
    assert "Constraints are declaration-time metadata" in fastapi["comment"]
    assert _purl(fastapi) == "pkg:pypi/fastapi"

    locked_react = by_name["react"][0]
    assert locked_react["versionInfo"]
    assert _purl(locked_react).startswith("pkg:npm/react@")


def test_official_release_evidence_requires_full_git_sha(tmp_path, monkeypatch):
    monkeypatch.setattr(generate_release_evidence, "_resolve_git_sha", lambda *_args: None)

    with pytest.raises(ValueError, match="full 40-character Git SHA"):
        generate_release_evidence.generate(ROOT, tmp_path, "short", require_git_sha=True)


def test_release_tag_must_match_manifest_version(tmp_path):
    with pytest.raises(ValueError, match="does not match version.json"):
        generate_release_evidence.generate(
            ROOT,
            tmp_path,
            "e" * 40,
            require_git_sha=True,
            release_tag="v0.0.1",
        )


def test_privileged_release_workflow_pins_third_party_actions_to_full_shas():
    workflow = (ROOT / ".github" / "workflows" / "release-evidence.yml").read_text(
        encoding="utf-8"
    )
    action_refs = re.findall(r"uses:\s+actions/[^@\s]+@([^\s#]+)", workflow)

    assert action_refs
    assert all(re.fullmatch(r"[0-9a-f]{40}", ref) for ref in action_refs)
    assert "permissions:\n  contents: read" in workflow
    assert "attach-to-release:" in workflow
    assert "contents: write" in workflow
    assert "GH_REPO: ${{ github.repository }}" in workflow
