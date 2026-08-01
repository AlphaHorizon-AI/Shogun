from pathlib import Path

import pytest

from shogun.services.file_formats import FileFormatError, FileSafetyGate
from shogun.services.native_skills import _validate_workspace_path


def test_workspace_path_accepts_configured_external_root(tmp_path: Path):
    workspace = tmp_path / "workspace"
    network_mount = tmp_path / "network-share"
    target = network_mount / "approved" / "report.xlsx"

    resolved = _validate_workspace_path(
        str(workspace),
        str(target),
        [str(network_mount / "approved")],
    )

    assert resolved == str(target.resolve())


def test_workspace_path_rejects_unconfigured_external_root(tmp_path: Path):
    workspace = tmp_path / "workspace"
    target = tmp_path / "network-share" / "private" / "report.xlsx"

    with pytest.raises(ValueError, match="outside the configured workspace roots"):
        _validate_workspace_path(str(workspace), str(target), [])


def test_workspace_path_rejects_parent_traversal_even_with_allowed_root(tmp_path: Path):
    workspace = tmp_path / "workspace"

    with pytest.raises(ValueError, match="cannot contain"):
        _validate_workspace_path(str(workspace), "../secret.txt", [str(tmp_path)])


def test_file_safety_gate_explicit_empty_roots_denies_all_files(tmp_path: Path):
    target = tmp_path / "report.txt"
    target.write_text("restricted", encoding="utf-8")

    with pytest.raises(FileFormatError, match="outside approved"):
        FileSafetyGate([]).validate(target)


def test_file_safety_gate_rejects_parent_traversal_before_file_access(tmp_path: Path):
    approved = tmp_path / "approved"
    approved.mkdir()
    secret = tmp_path / "secret.txt"
    secret.write_text("restricted", encoding="utf-8")

    with pytest.raises(FileFormatError, match="outside approved"):
        FileSafetyGate([approved]).validate(approved / ".." / "secret.txt")
