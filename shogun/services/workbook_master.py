"""Serialize workbook-master updates and promote validated generated workbooks."""

from __future__ import annotations

import datetime
import hashlib
import os
import re
import shutil
import tempfile
import uuid
from pathlib import Path
from threading import Event
from typing import Any

from shogun.services.sectioned_workbook_pipeline import run_sectioned_workbook_pipeline

_REPORT_SUFFIXES = (
    "_normalized_pdf_materials.json",
    "_audit_report.json",
    "_validation_report.json",
    "_comparison_report.json",
)


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _aliases(first: Path, second: Path) -> bool:
    return first == second or (first.exists() and second.exists() and first.samefile(second))


def _check_cancelled(cancel_event: Event | None) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise RuntimeError("Processing was cancelled before master promotion.")


def _assert_inputs_unchanged(hashes: dict[Path, str]) -> None:
    if any(not path.is_file() or _file_hash(path) != digest for path, digest in hashes.items()):
        raise ValueError("Workbook inputs changed during processing; the master was not promoted.")


def run_workbook_master_pipeline(
    *,
    master_workbook_path: Path | str,
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
    """Build a selected-PDF snapshot, preserving planner details independently.

    The caller confines paths to its workspace. An exclusive master lock spans
    baseline selection, pipeline execution, backup and atomic promotion. The
    existing pipeline continues to publish the output and its diagnostic reports.
    Explicit master_refresh_mode='rolling' retains the legacy forward-only mode.
    """
    definition = profile.get("profile", profile) if isinstance(profile, dict) else {}
    parameters = definition.get("parameters") if isinstance(definition, dict) else None
    policy = parameters.get("workbook_update") if isinstance(parameters, dict) else None
    if not isinstance(policy, dict) or policy.get("mode") != "maintain_master":
        raise ValueError("A workbook master requires a maintain_master profile.")
    if reference_workbook_path is not None:
        raise ValueError("Reference workbooks cannot be inputs to the workbook master lifecycle.")
    if not isinstance(pdf_paths, (list, tuple)) or not 1 <= len(pdf_paths) <= 10:
        raise ValueError("Provide between one and ten PDF paths.")

    master = Path(master_workbook_path).resolve()
    template = Path(template_workbook_path).resolve()
    output = Path(output_workbook_path).resolve()
    pdfs = [Path(path).resolve() for path in pdf_paths]
    profile_source = Path(profile_source_path).resolve() if profile_source_path else None
    if any(path.suffix.lower() != ".xlsx" for path in (master, template, output)):
        raise ValueError("Master, seed template and output must be .xlsx workbooks.")
    protected = [template, *pdfs, *([profile_source] if profile_source else [])]
    targets = [output, *(output.parent / f"{output.stem}{suffix}" for suffix in _REPORT_SUFFIXES)]
    if any(_aliases(master, path) for path in [*protected, *targets]):
        raise ValueError("The master must be separate from the template, PDFs, profile, output and reports.")

    master.parent.mkdir(parents=True, exist_ok=True)
    lock = master.with_name(master.name + ".lock")
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise ValueError("This workbook master is already being processed; try again after that run finishes.") from exc
    os.close(descriptor)

    temporary: Path | None = None
    try:
        _check_cancelled(cancel_event)
        initialized = not master.exists()
        baseline = template if initialized else master
        if not baseline.is_file():
            raise ValueError("The workbook master or its initial seed template is not a file.")
        input_paths = [baseline, *pdfs, *([profile_source] if profile_source else [])]
        hashes = {path: _file_hash(path) for path in input_paths}
        if expected_input_hashes is not None:
            if not isinstance(expected_input_hashes, dict):
                raise ValueError("Expected input hashes must be a dictionary.")
            expected = {}
            for raw_path, digest in expected_input_hashes.items():
                path = Path(raw_path)
                if (not path.is_absolute() or ".." in path.parts
                        or not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest)):
                    raise ValueError("Expected input hashes require absolute paths and SHA-256 digests.")
                expected[path] = digest
            if expected != hashes:
                raise ValueError("Workbook inputs changed after job preparation; run the flow again.")
        result = run_sectioned_workbook_pipeline(
            profile=profile,
            pdf_paths=pdfs,
            template_workbook_path=baseline,
            output_workbook_path=output,
            sheet_name=sheet_name,
            options={"master_refresh_mode": "selected_pdfs", **(options or {})},
            cancel_event=cancel_event,
            profile_source_path=profile_source,
            expected_input_hashes=hashes,
        )
        comparison = result.get("comparison_report", {})
        if comparison.get("status") != "PASS":
            raise ValueError("Workbook preservation validation failed; the master was not promoted.")
        summary = result.get("validation_summary", {})
        normalized = summary.get("normalized_record_count")
        accounted = summary.get("accounted_record_count")
        dispositions = summary.get("record_disposition_counts")
        if (type(normalized) is not int or normalized < 0 or type(accounted) is not int
                or accounted != normalized or not isinstance(dispositions, dict)
                or any(type(count) is not int or count < 0 for count in dispositions.values())
                or sum(dispositions.values()) != normalized):
            raise ValueError("Source record accounting is incomplete; the master was not promoted.")
        expected_output_hash = result.get("output_sha256")
        if not isinstance(expected_output_hash, str) or not re.fullmatch(r"[a-f0-9]{64}", expected_output_hash):
            raise ValueError("The validated output hash is missing or invalid; the master was not promoted.")
        _check_cancelled(cancel_event)
        _assert_inputs_unchanged(hashes)
        if initialized and master.exists():
            raise ValueError("The workbook master appeared during processing; it was not replaced.")

        descriptor, filename = tempfile.mkstemp(prefix=".shogun-master-", suffix=".xlsx", dir=master.parent)
        temporary = Path(filename)
        with os.fdopen(descriptor, "wb") as destination, output.open("rb") as source:
            shutil.copyfileobj(source, destination)
            destination.flush()
            os.fsync(destination.fileno())
        generated_hash = _file_hash(temporary)
        if generated_hash != expected_output_hash or _file_hash(output) != expected_output_hash:
            raise ValueError("The generated workbook changed before promotion; the master was not promoted.")

        backup: Path | None = None
        if not initialized:
            timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
            backup = master.with_name(f"{master.stem}_previous_v{timestamp}_{uuid.uuid4().hex[:12]}.xlsx")
            with backup.open("xb") as destination, master.open("rb") as source:
                shutil.copyfileobj(source, destination)
                destination.flush()
                os.fsync(destination.fileno())
            if _file_hash(backup) != hashes[master]:
                raise ValueError("The workbook master changed during backup; it was not promoted.")

        _check_cancelled(cancel_event)
        _assert_inputs_unchanged(hashes)
        if initialized and master.exists():
            raise ValueError("The workbook master appeared during processing; it was not replaced.")
        os.replace(temporary, master)
        temporary = None
        return {
            **result,
            "master_lifecycle": {
                "master_workbook": str(master),
                "initialized": initialized,
                "promoted": True,
                "backup_workbook": str(backup) if backup else None,
                "sha256": generated_hash,
                "review_required": bool(comparison.get("review_required", False)),
            },
        }
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        lock.unlink(missing_ok=True)
