"""Profile-driven sectioned PDF-to-Excel workbook transformation pipeline.

Generic, domain-neutral orchestrator: extracts PDF layout pages, enforces source-line
candidate accounting, evaluates profile-defined section and record rules, executes
in-place workbook updates with cell-by-cell baseline preservation, stages outputs in a
temporary folder with concurrency locking, and publishes atomically.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import logging
import math
import os
import re
import tempfile
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from threading import Event
from typing import Any

import openpyxl

from shogun.services.sectioned_workbook_updater import (
    SafeWorkbookUpdater,
    WorkbookLayoutContract,
    WorkbookPreservationComparator,
    _compute_source_identity,
    compare_reference_workbook,
)
from shogun.services.structured_transformations import (
    _apply_record_header_binding,
    _apply_resolution_groups,
    _apply_section_override,
    _compile_pattern,
    _extract_section_fields,
    _extract_selector_fields,
    _profile_regex_budget,
    _record_header_bindings,
    _record_matches,
    _required_pattern,
    _resolve_value_spec,
    _section_condition_matches,
    _validate_required_source_patterns,
    extract_pdf_layout_pages,
)
from shogun.services.transformation_profile_registry import profile_content_hash

log = logging.getLogger("shogun.services.sectioned_workbook")


@dataclass
class NormalizedRecord:
    raw: dict[str, Any] = field(default_factory=dict)
    identity: str = ""
    category: str = ""
    reference: str = ""
    quantity: float | int | None = None
    date: datetime.date | None = None
    source_file: str = ""
    source_page: int = 0
    source_line: int = 0
    source_text: str = ""
    source_text_hash: str = ""
    is_invalid: bool = False
    invalid_reason: str | None = None
    is_ambiguous_quantity: bool = False
    is_out_of_horizon: bool = False
    rule_id: str | None = None

    def __getattr__(self, name: str) -> Any:
        if "raw" in self.__dict__ and name in self.__dict__["raw"]:
            return self.__dict__["raw"][name]
        raise AttributeError(f"'NormalizedRecord' object has no attribute '{name}'")


@dataclass
class NormalizedSection:
    key: str
    fields: dict[str, Any] = field(default_factory=dict)
    records: list[NormalizedRecord] = field(default_factory=list)
    selector_exemptions: set[str] = field(default_factory=set)
    exceptions: list[dict[str, Any]] = field(default_factory=list)
    source_file: str = ""
    source_pages: list[int] = field(default_factory=list)
    selector_outcomes: dict[str, str] = field(default_factory=dict)
    resolution_states: list[dict[str, Any]] = field(default_factory=list)
    skip_output: bool = False

    @property
    def all_records(self) -> list[NormalizedRecord]:
        return self.records

    def __getattr__(self, name: str) -> Any:
        if "fields" in self.__dict__ and name in self.__dict__["fields"]:
            return self.__dict__["fields"][name]
        raise AttributeError(f"'NormalizedSection' object has no attribute '{name}'")


def _check_cancelled(cancel_event: Event | None) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise RuntimeError("Processing was cancelled before publication.")


def _eval_spec(spec: Any, section: Any, record_raw: dict[str, Any]) -> Any:
    return _resolve_value_spec(spec, section, record_raw)


class SectionedLayoutParser:
    """Generic deterministic parser for layout text extracted from multi-page documents."""

    def __init__(self, profile: dict[str, Any]):
        self.profile = profile
        self.profile_id = str(profile.get("id") or "sectioned_profile")
        self.parameters = profile.get("parameters") or {}

    def parse_pages(
        self,
        pages: list[tuple[int, str]],
        source_file: str,
    ) -> list[NormalizedSection]:
        section_pat = _required_pattern(self.parameters, "section_pattern")
        key_group = str(self.parameters.get("section_key_group") or "section_id")
        record_pat = _required_pattern(self.parameters, "record_pattern")
        header_layout_param = self.parameters.get("record_header_layout")
        header_pat = (
            _compile_pattern(header_layout_param.get("pattern"), "record header layout")
            if header_layout_param and header_layout_param.get("pattern")
            else None
        )
        positional_bindings = self.parameters.get("record_positional_bindings") or {}

        # Candidate pattern (profile configured or record pattern fallback)
        candidate_pat_str = self.parameters.get("extraction", {}).get("candidate_line_pattern")
        candidate_pat = (
            _compile_pattern(candidate_pat_str, "candidate_line_pattern") if candidate_pat_str else record_pat
        )

        sections: list[NormalizedSection] = []
        current_sec: NormalizedSection | None = None
        current_bindings: list[Any] = []
        reference_centers: dict[str, float] = {}

        # Parse sections within bounded regex budget
        with _profile_regex_budget(self.profile_id):
            for page_idx, page_text in pages:
                if not page_text.strip():
                    raise ValueError(
                        f"Blank page detected in {source_file} at page {page_idx}; refusing to process blank pages."
                    )

                s_matches = list(section_pat.finditer(page_text))
                if len(s_matches) > 1:
                    raise ValueError(f"Multiple section headers in {source_file}, page {page_idx}; review layout.")
                if not s_matches and current_sec is None:
                    raise ValueError(f"Unrecognized section page: {source_file}, page {page_idx}.")

                if s_matches:
                    s_match = s_matches[0]
                    try:
                        sec_key = str(s_match.group(key_group)).strip()
                    except (IndexError, KeyError) as exc:
                        raise ValueError(
                            f"Section pattern lacks key group '{key_group}' in {source_file}, page {page_idx}."
                        ) from exc

                    current_sec = NormalizedSection(
                        key=sec_key,
                        source_file=source_file,
                        source_pages=[page_idx],
                    )
                    for g_name, g_val in s_match.groupdict().items():
                        if g_val is not None:
                            current_sec.fields[g_name] = str(g_val).strip()

                    _extract_section_fields(current_sec, page_text, self.parameters, self.profile_id)
                    _apply_section_override(current_sec, self.parameters, self.profile_id)
                    _extract_selector_fields(current_sec, page_text, self.parameters, self.profile_id)
                    _apply_resolution_groups(current_sec, self.parameters, self.profile_id)

                    sections.append(current_sec)
                    current_bindings = []
                    reference_centers = {}
                else:
                    current_sec.source_pages.append(page_idx)
                    _extract_selector_fields(current_sec, page_text, self.parameters, self.profile_id)
                    _apply_resolution_groups(current_sec, self.parameters, self.profile_id)

                # Resolve record header bindings using generic primitive
                if header_layout_param:
                    has_header = header_pat.search(page_text) is not None if header_pat else False
                    if has_header:
                        current_bindings = _record_header_bindings(
                            page_text,
                            record_pat,
                            self.parameters,
                            self.profile_id,
                        )
                    elif not s_matches and current_bindings:
                        # Continuation page without new header inherits previous bindings with offset reset
                        from shogun.services.structured_transformations import _RecordHeaderBinding

                        current_bindings = [
                            _RecordHeaderBinding(position=0, source_by_target=b.source_by_target)
                            for b in current_bindings
                        ]
                    else:
                        if header_layout_param.get("required", True):
                            current_bindings = _record_header_bindings(
                                page_text,
                                record_pat,
                                self.parameters,
                                self.profile_id,
                            )
                        else:
                            current_bindings = []

                # Resolve positional group bindings if configured
                hdr_markers = positional_bindings.get("header_markers") or []
                slots = positional_bindings.get("slots") or []
                if hdr_markers and slots:
                    for header_line in page_text.splitlines():
                        if all(m in header_line for m in hdr_markers):
                            reference_centers = {
                                slot["name"]: header_line.index(slot["label"]) + len(slot["label"]) / 2
                                for slot in slots
                                if slot.get("label") and slot["label"] in header_line
                            }

                # Parse candidate lines on the page
                if current_sec is not None:
                    line_offset = 0
                    for line_idx, line_raw in enumerate(page_text.splitlines(keepends=True), 1):
                        line = line_raw.rstrip("\r\n")
                        if candidate_pat.search(line):
                            self._parse_record_line(
                                line=line,
                                line_pos_in_page=line_offset,
                                section=current_sec,
                                current_bindings=current_bindings,
                                source_file=source_file,
                                page_idx=page_idx,
                                line_idx=line_idx,
                                reference_centers=reference_centers,
                                record_pat=record_pat,
                            )
                        line_offset += len(line_raw)

        if not sections:
            raise ValueError(f"No sections found in {source_file}.")
        return sections

    def _parse_record_line(
        self,
        line: str,
        line_pos_in_page: int,
        section: NormalizedSection,
        current_bindings: list[Any],
        source_file: str,
        page_idx: int,
        line_idx: int,
        reference_centers: dict[str, float],
        record_pat: Any,
    ) -> None:
        rm = record_pat.match(line)
        if not rm:
            section.exceptions.append(
                {
                    "type": "MALFORMED_RECORD",
                    "line": line,
                    "file": source_file,
                    "page": page_idx,
                    "line_idx": line_idx,
                }
            )
            return

        raw = dict(rm.groupdict())
        is_invalid = False
        invalid_reasons: list[str] = []

        # Apply header bindings if configured
        if self.parameters.get("record_header_layout"):
            if current_bindings:
                try:
                    _apply_record_header_binding(
                        raw,
                        line_pos_in_page + rm.start(),
                        current_bindings,
                        self.parameters,
                        self.profile_id,
                    )
                except Exception as exc:
                    is_invalid = True
                    invalid_reasons.append("MISSING_ORIENTATION")
                    section.exceptions.append(
                        {
                            "type": "MISSING_ORIENTATION",
                            "line": line,
                            "file": source_file,
                            "page": page_idx,
                            "line_idx": line_idx,
                            "error": str(exc),
                        }
                    )
            else:
                is_invalid = True
                invalid_reasons.append("MISSING_ORIENTATION")
                section.exceptions.append(
                    {
                        "type": "MISSING_ORIENTATION",
                        "line": line,
                        "file": source_file,
                        "page": page_idx,
                        "line_idx": line_idx,
                    }
                )

        # Positional column extraction if configured
        pos_cols = self.parameters.get("record_positional_bindings") or {}
        target_grp = pos_cols.get("target_group")
        if target_grp and target_grp in raw and reference_centers:
            target_str = raw[target_grp]
            tokens = target_str.split()
            references: dict[str, str] = {}
            for token_match in re.finditer(r"\S+", target_str):
                tok = token_match.group()
                center = rm.start(target_grp) + token_match.start() + len(tok) / 2
                slots = pos_cols.get("slots") or []
                eligible_names = {slot["name"] for slot in slots if len(tokens) > 1 or not slot.get("multi_token_only")}
                centers = {name: pos for name, pos in reference_centers.items() if name in eligible_names}
                fallback_name = slots[0]["name"] if slots else "reference"
                chosen_name = min(centers, key=lambda field: abs(centers[field] - center)) if centers else fallback_name
                if chosen_name in references:
                    is_invalid = True
                    invalid_reasons.append("AMBIGUOUS_REFERENCE_COLUMNS")
                    section.exceptions.append(
                        {
                            "type": "AMBIGUOUS_REFERENCE_COLUMNS",
                            "file": source_file,
                            "page": page_idx,
                            "line_idx": line_idx,
                            "line": line,
                        }
                    )
                references[chosen_name] = tok
            for k, v in references.items():
                raw[k] = v

        # Apply record subpatterns if declared in profile
        for sub_spec in self.parameters.get("record_subpatterns", []):
            src_group = sub_spec.get("source_group")
            src_val = raw.get(src_group, "")
            sub_pat = _compile_pattern(sub_spec.get("pattern"), f"record_subpattern {src_group}")
            sub_match = sub_pat.match(src_val)
            if sub_match:
                raw.update(sub_match.groupdict())
            else:
                is_invalid = True
                exc_type = sub_spec.get("exception_type", "INVALID_SUBPATTERN")
                invalid_reasons.append(exc_type)
                section.exceptions.append(
                    {
                        "type": exc_type,
                        "line": line,
                        "file": source_file,
                        "page": page_idx,
                        "line_idx": line_idx,
                        "source_group": src_group,
                        "raw_value": src_val,
                    }
                )

        # Validate section key in record if declared
        sec_key_group = self.parameters.get("record_section_key_group")
        if sec_key_group and sec_key_group in raw:
            rec_sec_key = str(raw[sec_key_group]).strip()
            if rec_sec_key != section.key:
                is_invalid = True
                invalid_reasons.append("SECTION_KEY_MISMATCH")
                section.exceptions.append(
                    {
                        "type": "SECTION_KEY_MISMATCH",
                        "line": line,
                        "record_section_key": rec_sec_key,
                        "section_key": section.key,
                        "file": source_file,
                        "page": page_idx,
                        "line_idx": line_idx,
                    }
                )

        # Declarative rule matching against record_rules / row_rules
        rules = self.parameters.get("workbook_update", {}).get("record_rules") or self.parameters.get("row_rules") or []
        matching_rules = [
            r
            for r in rules
            if _record_matches(raw, r.get("match")) and _section_condition_matches(section, r.get("when"))
        ]
        matched_rule = None
        if len(matching_rules) == 1:
            matched_rule = matching_rules[0]
        elif len(matching_rules) > 1:
            is_invalid = True
            invalid_reasons.append("AMBIGUOUS_RECORD_RULE")
            section.exceptions.append(
                {
                    "type": "AMBIGUOUS_RECORD_RULE",
                    "line": line,
                    "file": source_file,
                    "page": page_idx,
                    "line_idx": line_idx,
                }
            )
        elif len(matching_rules) == 0 and rules:
            is_invalid = True
            invalid_reasons.append("UNMATCHED_RECORD_RULE")
            section.exceptions.append(
                {
                    "type": "UNMATCHED_RECORD_RULE",
                    "line": line,
                    "file": source_file,
                    "page": page_idx,
                    "line_idx": line_idx,
                }
            )

        rule_id = matched_rule.get("id") or matched_rule.get("name") or "record" if matched_rule else ""
        category = matched_rule.get("category") or matched_rule.get("kind") or rule_id if matched_rule else ""

        # Resolve reference
        reference = ""
        if matched_rule and "reference_spec" in matched_rule:
            try:
                reference = str(_eval_spec(matched_rule["reference_spec"], section, raw) or "").strip()
            except (ValueError, TypeError):
                reference = ""

        # Resolve quantity
        qty = None
        is_ambiguous_qty = False
        if matched_rule and "quantity_spec" in matched_rule:
            try:
                resolved_q = _eval_spec(matched_rule["quantity_spec"], section, raw)
                qty = float(resolved_q) if resolved_q is not None and resolved_q != "" else None
            except (ValueError, TypeError):
                qty = None

            if qty is None or not math.isfinite(qty):
                is_invalid = True
                invalid_reasons.append("INVALID_QUANTITY")
                section.exceptions.append(
                    {
                        "type": "INVALID_QUANTITY",
                        "line": line,
                        "file": source_file,
                        "page": page_idx,
                        "line_idx": line_idx,
                    }
                )

            if "alternative_quantity_spec" in matched_rule:
                try:
                    resolved_alt = _eval_spec(matched_rule["alternative_quantity_spec"], section, raw)
                    alt_qty = float(resolved_alt) if resolved_alt is not None and resolved_alt != "" else None
                except (ValueError, TypeError):
                    alt_qty = None

                if qty is not None and alt_qty is not None and qty != alt_qty:
                    is_ambiguous_qty = True
                    section.exceptions.append(
                        {
                            "type": "AMBIGUOUS_QUANTITY_MAPPING",
                            "section_key": section.key,
                            "category": category,
                            "quantity": qty,
                            "alternative_quantity": alt_qty,
                            "line": line,
                            "file": source_file,
                            "page": page_idx,
                            "line_idx": line_idx,
                        }
                    )

        # Resolve date
        resolved_date: datetime.date | None = None
        if matched_rule and "date_spec" in matched_rule:
            try:
                d_val = _eval_spec(matched_rule["date_spec"], section, raw)
            except (ValueError, TypeError):
                d_val = None

            if isinstance(d_val, datetime.date):
                resolved_date = d_val
            elif isinstance(d_val, datetime.datetime):
                resolved_date = d_val.date()
            elif d_val:
                try:
                    resolved_date = datetime.date.fromisoformat(str(d_val))
                except (ValueError, TypeError):
                    is_invalid = True
                    invalid_reasons.append("INVALID_SOURCE_DATE")
                    section.exceptions.append(
                        {
                            "type": "INVALID_SOURCE_DATE",
                            "file": source_file,
                            "page": page_idx,
                            "line_idx": line_idx,
                            "line": line,
                        }
                    )

        if is_invalid:
            resolved_date = None
            qty = None

        line_hash = hashlib.sha256(line.strip().encode("utf-8")).hexdigest()
        dedup_specs = (
            (matched_rule.get("deduplicate_by") if matched_rule else None)
            or self.parameters.get("workbook_update", {}).get("source_identity_fields")
            or self.parameters.get("deduplicate_by")
        )
        identity = _compute_source_identity(section, raw, dedup_specs, profile_id=self.profile_id, rule_id=rule_id)

        rec = NormalizedRecord(
            raw=raw,
            identity=identity,
            category=category,
            reference=reference,
            quantity=qty,
            date=resolved_date,
            source_file=source_file,
            source_page=page_idx,
            source_line=line_idx,
            source_text=line.strip(),
            source_text_hash=line_hash,
            is_ambiguous_quantity=is_ambiguous_qty,
            is_invalid=is_invalid,
            invalid_reason="; ".join(invalid_reasons) if is_invalid else None,
            rule_id=rule_id,
        )
        section.records.append(rec)


def run_sectioned_workbook_pipeline(
    profile: dict[str, Any],
    pdf_paths: list[Path | str],
    template_workbook_path: Path | str,
    output_workbook_path: Path | str,
    reference_workbook_path: Path | str | None = None,
    sheet_name: str | None = None,
    options: dict[str, Any] | None = None,
    cancel_event: Event | None = None,
    profile_source_path: Path | str | None = None,
    expected_input_hashes: dict[Path | str, str] | None = None,
) -> dict[str, Any]:
    from shogun.services.private_transformation_profiles import (
        PrivateTransformationProfileService,
        validate_private_profile_definition,
    )

    # Validate portable profile envelope or direct definition; never trust unverified hash overrides
    if isinstance(profile, dict) and (
        "profile" in profile
        and isinstance(profile["profile"], dict)
        and ("format" in profile or "content_hash" in profile)
    ):
        imported = PrivateTransformationProfileService().import_document(profile)
        profile_def = imported["document"]["profile"]
        profile_hash = imported["document"]["content_hash"]
    else:
        profile_def, _ = validate_private_profile_definition(profile)
        profile_hash = profile_content_hash(profile_def)

    profile = profile_def
    profile_id = str(profile.get("id") or "sectioned_workbook_pipeline")
    parameters = profile.get("parameters") or {}

    options = dict(options or {})
    supported_opts = {"max_pdf_bytes", "max_pdf_pages", "max_total_chars"}
    if set(options) - supported_opts:
        raise ValueError(f"Unsupported options: {sorted(set(options) - supported_opts)}")

    extraction_config = parameters.get("extraction") or {}
    limits = {
        "max_pdf_bytes": extraction_config.get("max_pdf_bytes", 64 * 1024 * 1024),
        "max_pdf_pages": extraction_config.get("max_pdf_pages", 2000),
        "max_total_chars": extraction_config.get("max_total_chars", 20_000_000),
    }
    for k, def_val in limits.items():
        v = options.get(k, def_val)
        if not isinstance(v, int) or isinstance(v, bool) or v < 1:
            raise ValueError(f"{k} must be a positive integer.")
        limits[k] = v

    if not isinstance(pdf_paths, (list, tuple)) or not 1 <= len(pdf_paths) <= 10:
        raise ValueError("Provide between one and ten PDF paths.")

    template = Path(template_workbook_path).resolve()
    output = Path(output_workbook_path).resolve()
    reference = Path(reference_workbook_path).resolve() if reference_workbook_path else None
    pdfs = [Path(p).resolve() for p in pdf_paths]
    profile_source = Path(profile_source_path).resolve() if profile_source_path else None
    inputs = [template, *pdfs, *([reference] if reference else []), *([profile_source] if profile_source else [])]

    if template.suffix.lower() != ".xlsx" or output.suffix.lower() != ".xlsx":
        raise ValueError("Template and output must be .xlsx workbooks.")
    if reference and reference.suffix.lower() != ".xlsx":
        raise ValueError("Reference must be an .xlsx workbook.")

    for p in inputs:
        if not p.is_file():
            raise FileNotFoundError(f"Input file not found: {p}")

    report_suffixes = [
        "_normalized_pdf_materials.json",
        "_audit_report.json",
        "_validation_report.json",
        "_comparison_report.json",
    ]
    derived_report_paths = [output.parent / f"{output.stem}{suffix}" for suffix in report_suffixes]
    all_targets = [output, *derived_report_paths]

    for inp in inputs:
        for tgt in all_targets:
            if inp == tgt or (tgt.exists() and inp.samefile(tgt)):
                raise ValueError(f"Output workbook or report path '{tgt}' aliases input file '{inp}'.")

    if len(set(pdfs)) != len(pdfs):
        raise ValueError("Duplicate input PDF path.")

    for p in pdfs:
        if p.suffix.lower() != ".pdf" or not 0 < p.stat().st_size <= limits["max_pdf_bytes"]:
            raise ValueError(f"Invalid PDF extension or configured file-size limit exceeded: {p.name}")

    # Compute upfront SHA-256 hashes
    hashes = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    if expected_input_hashes is not None:
        if not isinstance(expected_input_hashes, dict):
            raise ValueError("Expected input hashes must be a dictionary.")
        expected = {}
        for raw_path, digest in expected_input_hashes.items():
            path = Path(raw_path)
            # Keep the originally resolved path itself pinned. Resolving it
            # again could accept a symlink redirected after job preparation.
            if (not path.is_absolute() or ".." in path.parts
                    or not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest)):
                raise ValueError("Expected input hashes require absolute paths and SHA-256 digests.")
            expected[path] = digest
        if expected != hashes:
            raise ValueError("Workbook inputs changed after the Samurai step; run the flow again.")
    if len({hashes[p] for p in pdfs}) != len(pdfs):
        raise ValueError("Duplicate input PDF content.")

    _check_cancelled(cancel_event)
    output.parent.mkdir(parents=True, exist_ok=True)
    lock = output.with_name(output.name + ".lock")
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise ValueError("This output is already being processed; choose another output path.") from exc
    os.close(descriptor)

    try:
        parser = SectionedLayoutParser(profile)
        sections: list[NormalizedSection] = []
        extraction_summary = []
        remaining_chars = limits["max_total_chars"]
        candidate_pat_str = extraction_config.get("candidate_line_pattern")
        candidate_pat = (
            _compile_pattern(candidate_pat_str, "candidate_line_pattern")
            if candidate_pat_str
            else _required_pattern(parameters, "record_pattern")
        )

        for path in pdfs:
            # Extraction is outside the 20s regex budget
            pages = extract_pdf_layout_pages(
                path,
                max_pages=limits["max_pdf_pages"],
                max_chars=remaining_chars,
                cancel_event=cancel_event,
            )
            remaining_chars -= sum(len(txt) for _, txt in pages)

            # Parsing enters independent regex budget inside parse_pages
            with _profile_regex_budget(profile_id):
                _validate_required_source_patterns("\n".join(text for _, text in pages), parameters, profile_id)
            parsed_sections = parser.parse_pages(pages, source_file=path.name)
            records = [rec for sec in parsed_sections for rec in sec.records]

            # Strict source-line candidate accounting
            candidates = {
                (page_num, line_num)
                for page_num, txt in pages
                for line_num, line in enumerate(txt.splitlines(), 1)
                if candidate_pat.search(line)
            }
            accounted = {(rec.source_page, rec.source_line) for rec in records}
            accounted.update(
                (exc["page"], exc["line_idx"])
                for sec in parsed_sections
                for exc in sec.exceptions
                if "page" in exc and "line_idx" in exc
            )
            if candidates != accounted:
                raise ValueError(f"Incomplete source-line accounting in {path.name}.")

            cat_counts = Counter(rec.category or "record" for rec in records)
            summary_entry: dict[str, Any] = {
                "file": path.name,
                "sha256": hashes[path],
                "pages_extracted": len(pages),
                "sections_parsed": len(parsed_sections),
                "raw_candidates": len(candidates),
                "category_counts": dict(cat_counts),
            }
            extraction_summary.append(summary_entry)
            sections.extend(parsed_sections)

        _check_cancelled(cancel_event)

        # Stage workbook and report files in a temporary directory on the same filesystem
        with tempfile.TemporaryDirectory(prefix=".shogun-workbook-", dir=output.parent) as folder:
            staging = Path(folder).resolve()
            staged_workbook = staging / output.name

            updater = SafeWorkbookUpdater(template, profile)
            summary = updater.execute(sections, staged_workbook, sheet_name, options)
            _check_cancelled(cancel_event)

            comparator = WorkbookPreservationComparator()
            comparison = comparator.compare_workbooks(template, staged_workbook, summary)
            comparison["reference_workbook_status"] = "NOT_PROVIDED"
            if reference:
                reference_template = openpyxl.load_workbook(template, read_only=True)
                try:
                    contract_obj = WorkbookLayoutContract(
                        reference_template[summary["sheet_name"]],
                        profile["parameters"]["workbook_update"],
                    )
                finally:
                    reference_template.close()
                comparison.update(
                    compare_reference_workbook(
                        reference,
                        staged_workbook,
                        summary["sheet_name"],
                        contract=contract_obj,
                    )
                )
                comparison["reference_path"] = str(reference)

            cat_total_counts = Counter(rec.category or "record" for sec in sections for rec in sec.records)
            audit: dict[str, Any] = {
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "profile_id": profile_id,
                "profile_content_hash": profile_hash,
                "template_workbook": str(template),
                "output_workbook": str(output),
                "reference_workbook": str(reference) if reference else None,
                "input_sha256": {str(p): digest for p, digest in hashes.items()},
                "pdf_inputs": extraction_summary,
                "total_sections": len(sections),
                "total_materials": len(sections),
                "total_records_parsed": sum(len(sec.records) for sec in sections),
                "total_exceptions": sum(len(sec.exceptions) for sec in sections),
                "category_counts": dict(cat_total_counts),
                "options": options,
            }

            payloads = {
                "normalized_materials": ("normalized_pdf_materials", [asdict(sec) for sec in sections]),
                "audit_report": ("audit_report", audit),
                "validation_report": ("validation_report", summary),
                "comparison_report": ("comparison_report", comparison),
            }

            report_paths = {}
            for key, (suffix, payload) in payloads.items():
                filename = f"{output.stem}_{suffix}.json"
                (staging / filename).write_text(
                    json.dumps(payload, indent=2, default=str, ensure_ascii=False),
                    encoding="utf-8",
                )
                report_paths[key] = str(output.parent / filename)

            # Verify input immutability before publishing
            if any(hashlib.sha256(p.read_bytes()).hexdigest() != digest for p, digest in hashes.items()):
                raise ValueError("Input files changed during processing; refusing to publish inconsistent output.")

            _check_cancelled(cancel_event)
            # Atomically publish reports first
            for p_str in report_paths.values():
                target = Path(p_str)
                os.replace(staging / target.name, target)

            # Commit marker: atomically publish workbook last
            _check_cancelled(cancel_event)
            os.replace(staged_workbook, output)

        return {
            "output_workbook": str(output),
            "validation_summary": summary,
            "comparison_report": comparison,
            "audit_report": audit,
            "report_paths": report_paths,
            "profile_id": profile_id,
            "profile_content_hash": profile_hash,
        }
    finally:
        if lock.exists():
            lock.unlink()


def main() -> None:
    """CLI entry point for running a profile-driven workbook pipeline."""
    arg_parser = argparse.ArgumentParser(description="Profile-driven PDF to Excel workbook update pipeline.")
    arg_parser.add_argument("--profile", required=True, help="Path to .shogun-profile.json or JSON file")
    arg_parser.add_argument("--pdf", action="append", required=True, help="Source PDF(s)")
    arg_parser.add_argument("--template", required=True, help="Template workbook path")
    arg_parser.add_argument("--output", required=True, help="Output workbook path")
    arg_parser.add_argument("--reference", help="Reference comparison workbook path")
    arg_parser.add_argument("--sheet", help="Target sheet name")
    args = arg_parser.parse_args()

    profile_data = json.loads(Path(args.profile).read_text(encoding="utf-8"))
    res = run_sectioned_workbook_pipeline(
        profile=profile_data,
        pdf_paths=args.pdf,
        template_workbook_path=args.template,
        output_workbook_path=args.output,
        reference_workbook_path=args.reference,
        sheet_name=args.sheet,
        profile_source_path=args.profile,
    )
    print(
        json.dumps(
            {
                "output_workbook": res["output_workbook"],
                "report_paths": res["report_paths"],
                "record_dispositions": res["validation_summary"]["record_disposition_counts"],
                "review_required": res["comparison_report"]["review_required"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
