"""Regression coverage for source-level Unicode encoding corruption."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MOJIBAKE_MARKERS = ("Ã", "Â", "â", "ð", "ï")
CONTROL_CHARACTERS = re.compile(r"[\x80-\x9f]")
ENCODING_SENSITIVE_FILES = (
    "pyproject.toml",
    "shogun/api/agents.py",
    "shogun/__init__.py",
    "frontend/src/pages/Chat.tsx",
)


@pytest.mark.parametrize("relative_path", ENCODING_SENSITIVE_FILES)
def test_encoding_sensitive_source_has_no_mojibake(relative_path: str) -> None:
    source = (ROOT / relative_path).read_text(encoding="utf-8")

    for marker in MOJIBAKE_MARKERS:
        assert marker not in source, f"{relative_path} contains mojibake marker {marker!r}"
    assert CONTROL_CHARACTERS.search(source) is None


def test_no_provider_message_is_defined_once_and_reused_by_both_chat_paths() -> None:
    source_path = ROOT / "shogun" / "api" / "agents.py"
    source = source_path.read_text(encoding="utf-8")
    module = ast.parse(source, filename=str(source_path))

    assignments = {
        target.id: ast.literal_eval(node.value)
        for node in module.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name) and target.id == "NO_ACTIVE_MODEL_PROVIDER_MESSAGE"
    }

    assert assignments["NO_ACTIVE_MODEL_PROVIDER_MESSAGE"] == (
        "⚠️ No active model provider found. "
        "Go to The Katana → Model Providers and add one."
    )
    assert source.count("NO_ACTIVE_MODEL_PROVIDER_MESSAGE") == 3
