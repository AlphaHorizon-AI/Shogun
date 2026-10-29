from types import SimpleNamespace

import pytest

from shogun.services.structured_transformations import _order_sections


def section(key, family, component=""):
    return SimpleNamespace(key=key, fields={"family": family, "component": component}, skip_output=False)


def ordering(dependencies=True):
    policy = {"family_key": {"field": "family"}}
    if dependencies:
        policy["dependencies_before"] = {"fields": ["component"], "missing": "error"}
    return {"section_order": policy}


def test_families_remain_together_when_members_have_different_original_priorities():
    root = section("ASSEMBLY", "ASSEMBLY", "PART-A")
    unrelated = section("OTHER", "OTHER")
    variant = section("PART-B", "PART", "PART-A")
    base = section("PART-A", "PART")
    result = _order_sections([root, unrelated, variant, base], ordering(), "equipment")
    assert [item.key for item in result] == ["PART-A", "PART-B", "ASSEMBLY", "OTHER"]
    assert {id(item) for item in result} == {id(root), id(unrelated), id(variant), id(base)}


def test_family_dependencies_are_resolved_before_all_family_members():
    base = section("BASE", "FAMILY")
    raw = section("RAW", "RAW")
    variant = section("VARIANT", "FAMILY", "RAW")
    result = _order_sections([base, variant, raw], ordering(), "equipment")
    assert [item.key for item in result] == ["RAW", "BASE", "VARIANT"]


def test_conflicting_contiguous_families_fail_instead_of_breaking_dependency_order():
    a = section("A", "FAMILY")
    b = section("B", "OTHER", "A")
    c = section("C", "FAMILY", "B")
    with pytest.raises(ValueError, match="cannot keep section families together"):
        _order_sections([a, b, c], ordering(), "equipment")


def test_grouping_without_dependencies_and_blank_family_values():
    a = section("A", "FAMILY")
    b = section("B", "")
    c = section("C", "FAMILY")
    result = _order_sections([a, b, c], ordering(False), "equipment")
    assert [item.key for item in result] == ["A", "C", "B"]


def test_omitting_family_key_preserves_original_dependency_order():
    a = section("A", "FAMILY")
    b = section("B", "OTHER", "A")
    c = section("C", "FAMILY", "B")
    policy = ordering()
    del policy["section_order"]["family_key"]
    assert _order_sections([a, b, c], policy, "equipment") == [a, b, c]


def test_unsupported_family_value_is_rejected():
    with pytest.raises(ValueError, match="family_key must resolve to text"):
        _order_sections([section("A", ["invalid"])], ordering(False), "equipment")
