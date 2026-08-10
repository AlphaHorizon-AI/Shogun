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
class _SapOrder:
    kind: str
    article: str
    reference: str
    end_week: str
    end_month: str
    start_week: str
    start_month: str
    planned: int | float
    remaining: int | float
    date: str


@dataclass(slots=True)
class _SapMaterial:
    article: str
    description: str = ""
    rohling: str = ""
    rohteil: str = ""
    stock: int | float = 0
    orders: list[_SapOrder] = field(default_factory=list)


_SAP_NUMBER_PATTERN = r"[+-]?(?:\d{1,3}(?:[ .\u00a0\u202f]\d{3})+|\d+)(?:,\d+)?"
_SAP_ORDER_RE = re.compile(
    r"(?m)^\s*(?P<kind>01|06)\s+"
    r"(?P<article>\S+)\s+"
    r"(?P<reference>\S+)\s+"
    r"(?P<end_week>\d{4}/\d{2})\s+"
    r"(?P<end_month>\d{4}/\d{2})\s+"
    r"(?P<start_week>\d{4}/\d{2})\s+"
    r"(?P<start_month>\d{4}/\d{2})\s+"
    rf"(?P<planned>{_SAP_NUMBER_PATTERN})\s+"
    rf"(?P<remaining>{_SAP_NUMBER_PATTERN})\s+"
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
_SAP_MONTH_NAMES = {
    "jan": 1,
    "january": 1,
    "januar": 1,
    "feb": 2,
    "february": 2,
    "februar": 2,
    "mar": 3,
    "march": 3,
    "marz": 3,
    "märz": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "mai": 5,
    "jun": 6,
    "june": 6,
    "juni": 6,
    "jul": 7,
    "july": 7,
    "juli": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "okt": 10,
    "oktober": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
    "dez": 12,
    "dezember": 12,
}


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

        # Every parsed Sa=06 line is a source occurrence. Identical order
        # lines are intentionally preserved because SAP may list the same
        # visible order more than once and each occurrence contributes to the
        # ordered quantity.
        for order in material.orders:
            if order.kind != "06":
                continue
            row = list(base)
            row[4] = order.reference
            row[5] = order.planned
            rows.append(row)

        # Bedarf is deterministic: sum every Sa=01 Rest-Menge occurrence by
        # Endtermin Jahr/MO. Starttermin must never select the Bedarf column.
        demand_orders = [order for order in material.orders if order.kind == "01"]
        if demand_orders:
            demand_by_month: dict[str, int | float] = {}
            source_total: int | float = 0
            for order in demand_orders:
                demand_by_month[order.end_month] = _add_numbers(
                    demand_by_month.get(order.end_month, 0),
                    order.remaining,
                )
                source_total = _add_numbers(source_total, order.remaining)
            row = list(base)
            mapped_total: int | float = 0
            unmapped_months: list[str] = []
            for month, quantity in demand_by_month.items():
                column = _planning_column_for_month(month_columns, month)
                if column is None:
                    unmapped_months.append(month)
                    continue
                current = row[column] if isinstance(row[column], (int, float)) else 0
                row[column] = _add_numbers(current, quantity)
                mapped_total = _add_numbers(mapped_total, quantity)
            if unmapped_months or not _numbers_equal(source_total, mapped_total):
                missing = ", ".join(sorted(unmapped_months)) or "unknown"
                raise ValueError(
                    "SAP demand accounting failed for material "
                    f"{material.article}: Endtermin month(s) {missing} have no Excel planning bucket "
                    f"(source Rest-Menge {source_total}, mapped {mapped_total})."
                )
            rows.append(row)

    if not rows or any(len(row) != logical_width for row in rows):
        return None
    return DeterministicMatrixResult(adapter_id="sap_disposition_v1", rows=rows)


def _is_sap_planning_contract(task_description: str, source_context: str) -> bool:
    task = str(task_description or "")
    required_rules = (
        re.search(r"Sa\s*=\s*06", task, re.IGNORECASE),
        re.search(r"Sa\s*=\s*01", task, re.IGNORECASE),
        # Accept old saved flow instructions mentioning Starttermin so the
        # deterministic correction applies without requiring every flow to be
        # edited. The adapter itself always follows the canonical Endtermin
        # rule below.
        re.search(r"(?:Endtermin|Starttermin)\s+Jahr/Mo", task, re.IGNORECASE),
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
        header_text = str(header)
        backlog_label = re.sub(r"\s+", " ", header_text).strip().casefold()
        if backlog_label in {"rückstand", "ruckstand", "rueckstand", "backlog", "overdue"}:
            columns["backlog"] = index
            continue
        month = _planning_header_month(header_text)
        if month is None:
            continue
        future_bucket = bool(
            re.search(r"(?:>=|≥|\bab\b|\bfrom\b|future|sp[aä]ter)", header_text, re.IGNORECASE)
            or re.search(r"\+\s*$", header_text)
        )
        columns[f">={month}" if future_bucket else month] = index
    return columns


def _planning_column_for_month(columns: dict[str, int], month: str) -> int | None:
    exact = columns.get(month)
    if exact is not None:
        return exact
    month_key = _month_key(month)
    if month_key is None:
        return None
    eligible_future_buckets = sorted(
        (_month_key(threshold[2:]), column)
        for threshold, column in columns.items()
        if threshold.startswith(">=")
        and _month_key(threshold[2:]) is not None
        and month_key >= _month_key(threshold[2:])
    )
    if eligible_future_buckets:
        return eligible_future_buckets[-1][1]
    exact_months = sorted(
        key
        for key in (_month_key(candidate) for candidate in columns)
        if key is not None
    )
    if exact_months and month_key < exact_months[0]:
        return columns.get("backlog")
    return None


def _planning_header_month(header_text: str) -> str | None:
    numeric = re.search(r"(?<!\d)(\d{4})[-/](\d{2})(?:[-/]\d{2})?", header_text)
    if numeric:
        month = f"{numeric.group(1)}/{numeric.group(2)}"
        return month if _month_key(month) is not None else None
    named = re.search(r"(?i)\b([a-zä]+)\.?\s+(\d{4})\b", header_text)
    if not named:
        return None
    month_number = _SAP_MONTH_NAMES.get(named.group(1).casefold())
    if month_number is None:
        return None
    return f"{named.group(2)}/{month_number:02d}"


def _month_key(month: str) -> tuple[int, int] | None:
    match = re.fullmatch(r"(\d{4})/(\d{2})", str(month or "").strip())
    if not match:
        return None
    year, number = int(match.group(1)), int(match.group(2))
    return (year, number) if 1 <= number <= 12 else None


def _parse_sap_materials(source_context: str) -> dict[str, _SapMaterial]:
    text = str(source_context or "")
    starts = list(_SAP_MATERIAL_RE.finditer(text))
    materials: dict[str, _SapMaterial] = {}
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
        stock_text = _match_group(
            section,
            rf"(?m)^\s*Bestand\s*:\s*({_SAP_NUMBER_PATTERN})",
        )
        if stock_text:
            material.stock = max(material.stock, _sap_number(stock_text))
        rohling, rohteil = _sap_bom_materials(section)
        material.rohling = material.rohling or rohling
        material.rohteil = material.rohteil or rohteil

        for order_match in _SAP_ORDER_RE.finditer(section):
            row_article = order_match.group("article").strip()
            if row_article != article:
                continue
            material.orders.append(
                _SapOrder(
                    kind=order_match.group("kind"),
                    article=row_article,
                    reference=order_match.group("reference").lstrip("0") or "0",
                    end_week=order_match.group("end_week"),
                    end_month=order_match.group("end_month"),
                    start_week=order_match.group("start_week"),
                    start_month=order_match.group("start_month"),
                    planned=_sap_number(order_match.group("planned")),
                    remaining=_sap_number(order_match.group("remaining")),
                    date=order_match.group("date"),
                )
            )
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
    # SAP's German reports use both dots and whitespace (including non-breaking
    # variants emitted by PDF extractors) as thousands separators, with a comma
    # as the decimal separator. Keep the field boundaries in the row regex, then
    # normalize only the captured number so ``1 200,0`` becomes numeric 1200.
    normalized = re.sub(r"[\s.\u00a0\u202f]", "", str(value).strip()).replace(",", ".")
    number = float(normalized)
    return int(number) if number.is_integer() else number


def _add_numbers(left: int | float, right: int | float) -> int | float:
    total = float(left) + float(right)
    return int(total) if total.is_integer() else total


def _numbers_equal(left: int | float, right: int | float) -> bool:
    return abs(float(left) - float(right)) <= 1e-9


def _canonical_header(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())
