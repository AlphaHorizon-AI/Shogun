"""Deterministic adapters for explicit, machine-readable file transformations.

These adapters are deliberately narrow.  They only run when both the runtime
source and the user's instructions identify a supported contract.  Every
other transformation remains on the normal Samurai/model path.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class DeterministicMatrixResult:
    adapter_id: str
    rows: list[list[Any]]


@dataclass(slots=True)
class _SapMaterial:
    article: str
    description: str = ""
    rohling: str = ""
    rohteil: str = ""
    stock: int | float = 0
    production_orders: dict[str, int | float] = field(default_factory=dict)
    demand_by_month: dict[str, int | float] = field(default_factory=dict)
    demand_references: set[str] = field(default_factory=set)


_SAP_ORDER_RE = re.compile(
    r"(?m)^\s*(?P<kind>01|06)\s+"
    r"(?P<article>\S+)\s+"
    r"(?P<reference>\S+)\s+"
    r"(?P<end_week>\d{4}/\d{2})\s+"
    r"(?P<end_month>\d{4}/\d{2})\s+"
    r"(?P<start_week>\d{4}/\d{2})\s+"
    r"(?P<start_month>\d{4}/\d{2})\s+"
    r"(?P<planned>[\d.,-]+)\s+"
    r"(?P<remaining>[\d.,-]+)\s+"
    r"(?P<date>\d{2}\.\d{2}\.\d{4})\s*$"
)
_SAP_MATERIAL_RE = re.compile(r"(?m)^\s*Sachnummer\s*:\s*(\S+)")
_SAP_AUXILIARY_BOM_TERMS = (
    "beutel",
    "box",
    "duese",
    "düse",
    "faltkiste",
    "kiste",
    "pack",
    "spannstift",
    "teleskop",
    "verpack",
)


def try_deterministic_matrix_transform(
    *,
    task_description: str,
    source_context: str,
    fixed_context: str,
) -> DeterministicMatrixResult | None:
    """Return an authoritative matrix when a narrow adapter can prove the mapping."""

    template = _excel_template_contract(fixed_context)
    if template is None or not _is_sap_planning_contract(task_description, source_context):
        return None
    headers, logical_width = template
    month_columns = _planning_month_columns(headers)
    if logical_width < 10 or not month_columns:
        return None

    materials = _parse_sap_materials(source_context)
    if not materials:
        return None

    rows: list[list[Any]] = []
    for material in materials.values():
        base = [""] * logical_width
        base[0] = material.description
        base[1] = material.article
        base[2] = material.rohling
        base[3] = material.rohteil

        if material.stock > 0:
            row = list(base)
            row[4] = "Lager 0031"
            row[5] = material.stock
            rows.append(row)

        for order, quantity in material.production_orders.items():
            row = list(base)
            row[4] = order
            row[5] = quantity
            rows.append(row)

        # Keep one planning row for every material with Sa=01 records.  Values
        # outside the template horizon remain excluded rather than shifted.
        if material.demand_references:
            row = list(base)
            for month, quantity in material.demand_by_month.items():
                column = month_columns.get(month)
                if column is not None:
                    row[column] = quantity
            rows.append(row)

    if not rows or any(len(row) != logical_width for row in rows):
        return None
    return DeterministicMatrixResult(adapter_id="sap_disposition_v1", rows=rows)


def _is_sap_planning_contract(task_description: str, source_context: str) -> bool:
    task = str(task_description or "")
    required_rules = (
        re.search(r"Sa\s*=\s*06", task, re.IGNORECASE),
        re.search(r"Sa\s*=\s*01", task, re.IGNORECASE),
        re.search(r"Starttermin\s+Jahr/Mo", task, re.IGNORECASE),
        re.search(r"Soll-Menge", task, re.IGNORECASE),
        re.search(r"Rest-Menge", task, re.IGNORECASE),
    )
    return bool(
        all(required_rules)
        and _SAP_MATERIAL_RE.search(source_context or "")
        and re.search(r"(?m)^\s*Teilebez\.\s*:", source_context or "")
        and re.search(r"(?m)^\s*Sa\s+Artikelnummer\b", source_context or "")
    )


def _excel_template_contract(fixed_context: str) -> tuple[list[Any], int] | None:
    marker = "[MACHINE-READABLE TEMPLATE MANIFEST]"
    marker_index = str(fixed_context or "").find(marker)
    if marker_index < 0:
        return None
    json_start = fixed_context.find("{", marker_index + len(marker))
    if json_start < 0:
        return None
    try:
        manifest, _ = json.JSONDecoder().raw_decode(fixed_context[json_start:])
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(manifest, dict) or manifest.get("kind") != "excel":
        return None
    sheets = manifest.get("sheets") or []
    if not sheets or not isinstance(sheets[0], dict):
        return None
    sheet = sheets[0]
    preview_rows = sheet.get("preview_rows") or []
    headers = list(preview_rows[0]) if preview_rows and isinstance(preview_rows[0], list) else []
    try:
        logical_width = int(sheet.get("logical_columns") or len(headers))
    except (TypeError, ValueError):
        return None
    if logical_width < 6 or len(headers) < logical_width:
        return None
    canonical = [_canonical_header(value) for value in headers]
    if canonical[1] not in {"artikelnr", "artikelnummer"} or canonical[4] != "fertigungsauftrag":
        return None
    return headers[:logical_width], logical_width


def _planning_month_columns(headers: list[Any]) -> dict[str, int]:
    columns: dict[str, int] = {}
    for index, header in enumerate(headers):
        if index < 10 or header in (None, ""):
            continue
        match = re.search(r"(?<!\d)(\d{4})[-/](\d{2})(?:[-/]\d{2})?", str(header))
        if match:
            columns[f"{match.group(1)}/{match.group(2)}"] = index
    return columns


def _parse_sap_materials(source_context: str) -> dict[str, _SapMaterial]:
    text = str(source_context or "")
    starts = list(_SAP_MATERIAL_RE.finditer(text))
    materials: dict[str, _SapMaterial] = {}
    seen_production: set[tuple[str, str]] = set()
    seen_demand: set[tuple[str, str]] = set()
    for index, match in enumerate(starts):
        article = match.group(1).strip()
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        section = text[match.start() : end]
        material = materials.setdefault(article, _SapMaterial(article=article))

        description = _match_group(
            section,
            r"(?m)^\s*Teilebez\.\s*:\s*(.*?)\s+Werkstoff\s*:",
        )
        if description and not material.description:
            material.description = description
        stock_text = _match_group(section, r"(?m)^\s*Bestand\s*:\s*([\d.,-]+)")
        if stock_text:
            material.stock = max(material.stock, _sap_number(stock_text))
        rohling, rohteil = _sap_bom_materials(section)
        material.rohling = material.rohling or rohling
        material.rohteil = material.rohteil or rohteil

        for order_match in _SAP_ORDER_RE.finditer(section):
            row_article = order_match.group("article").strip()
            if row_article != article:
                continue
            reference = order_match.group("reference").lstrip("0") or "0"
            if order_match.group("kind") == "06":
                key = (article, reference)
                if key not in seen_production:
                    material.production_orders[reference] = _sap_number(order_match.group("planned"))
                    seen_production.add(key)
                continue

            key = (article, reference)
            if key in seen_demand:
                continue
            month = order_match.group("start_month")
            quantity = _sap_number(order_match.group("remaining"))
            material.demand_by_month[month] = _add_numbers(
                material.demand_by_month.get(month, 0),
                quantity,
            )
            material.demand_references.add(reference)
            seen_demand.add(key)
    return materials


def _sap_bom_materials(section: str) -> tuple[str, str]:
    match = re.search(
        r"(?ims)^\s*St(?:ü|Ã¼|u)ckliste\s*:.*?\n(?P<body>.*?)^\s*Bemerkungen\s*:",
        section,
    )
    if not match:
        return "", ""
    rohling = ""
    rohteil = ""
    for line in match.group("body").splitlines():
        item = re.match(r"^\s*\d{4}\s+(\S+)\s+(.+?)\s+[\d.,-]+\s+\S+\s*$", line)
        if not item:
            continue
        number, description = item.group(1).strip(), item.group(2).strip()
        lowered = description.casefold()
        if any(term in lowered for term in _SAP_AUXILIARY_BOM_TERMS):
            continue
        if "rohling" in lowered and not rohling:
            rohling = number
        elif any(term in lowered for term in ("rohteil", "halbzeug", "vorbearb", "kolben")) and not rohteil:
            rohteil = number
    return rohling, rohteil


def _match_group(text: str, pattern: str) -> str:
    match = re.search(pattern, text)
    return match.group(1).strip() if match else ""


def _sap_number(value: str) -> int | float:
    normalized = str(value).strip().replace(".", "").replace(",", ".")
    number = float(normalized)
    return int(number) if number.is_integer() else number


def _add_numbers(left: int | float, right: int | float) -> int | float:
    total = float(left) + float(right)
    return int(total) if total.is_integer() else total


def _canonical_header(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())
