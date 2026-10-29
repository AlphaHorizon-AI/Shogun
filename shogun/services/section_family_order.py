"""Keep configured section families contiguous while respecting dependencies."""

from __future__ import annotations

import heapq
from collections.abc import Callable
from typing import Any


def order_section_families(
    sections: list[Any],
    family_key: Callable[[Any], Any],
    dependency_fields: list[str],
    profile_id: str,
) -> list[Any]:
    """Stable topological ordering of families, retaining their member order."""
    families: dict[str, list[Any]] = {}
    family_by_section: dict[str, str] = {}
    for section in sections:
        value = family_key(section)
        if value in (None, ""):
            value = section.key
        if not isinstance(value, str):
            raise ValueError("section_order.family_key must resolve to text or a blank value.")
        if section.key in family_by_section:
            raise ValueError("Section family ordering requires unique section keys.")
        family_by_section[section.key] = value
        families.setdefault(value, []).append(section)

    prerequisites: dict[str, set[str]] = {key: set() for key in families}
    dependents: dict[str, set[str]] = {key: set() for key in families}
    for section in sections:
        family = family_by_section[section.key]
        for field in dependency_fields:
            target = str(section.fields.get(field) or "").strip()
            dependency_family = family_by_section.get(target)
            if dependency_family is not None and dependency_family != family:
                prerequisites[family].add(dependency_family)
                dependents[dependency_family].add(family)

    ranks = {key: index for index, key in enumerate(families)}
    remaining = {key: len(values) for key, values in prerequisites.items()}
    ready = [(ranks[key], key) for key in families if not remaining[key]]
    heapq.heapify(ready)
    result: list[Any] = []
    emitted = 0
    while ready:
        _, family = heapq.heappop(ready)
        result.extend(families[family])
        emitted += 1
        for dependent in dependents[family]:
            remaining[dependent] -= 1
            if remaining[dependent] == 0:
                heapq.heappush(ready, (ranks[dependent], dependent))
    if emitted != len(families):
        raise ValueError(
            f"Transformation profile '{profile_id}' cannot keep section families together "
            "without violating dependency order."
        )
    return result
