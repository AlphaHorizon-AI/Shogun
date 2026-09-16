"""Runtime-only workbook jobs between a configured Samurai and its Files writer.

Only the harmless dictionary summary is serializable. The executable contract
travels in a Python type created from validated flow configuration; user JSON,
model responses and persisted run summaries cannot impersonate that type.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from shogun.services.private_transformation_profiles import validate_private_profile_definition
from shogun.services.transformation_profile_registry import profile_content_hash

JOB_MARKER = "__shogun_workbook_job__"


def _file_hash(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _workspace_file(raw: Any, root: Path, suffix: str) -> Path:
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("Workbook jobs require configured workspace file paths.")
    path = (root / raw).resolve()
    if ".." in Path(raw).parts or not path.is_relative_to(root.resolve()):
        raise ValueError("Workbook job paths must remain inside the workspace.")
    if path.suffix.lower() != suffix or not path.is_file():
        raise ValueError(f"Workbook job requires an existing {suffix} file.")
    return path


def _validate_profile(profile: dict, evidence: dict) -> None:
    validate_private_profile_definition(profile)
    if not isinstance(profile.get("parameters", {}).get("workbook_update"), dict):
        raise ValueError("Samurai workbook jobs require workbook rules.")
    if (
        evidence.get("profile_id") != profile.get("id")
        or evidence.get("adapter_id") != profile.get("adapter")
        or evidence.get("content_hash") != profile_content_hash(profile)
    ):
        raise ValueError("Workbook job profile does not match its immutable evidence.")


def validate_workbook_permissions(governance: dict[str, Any] | None) -> None:
    """Respect explicit run restrictions in addition to the Office App gate."""
    context = governance or {}
    permissions = context.get("permissions", context)
    if permissions.get("kill_switch_active"):
        raise ValueError("Workbook execution is blocked by the emergency stop.")
    for key in ("workspace_enabled", "office_enabled", "office_excel_enabled"):
        if key in permissions and not permissions[key]:
            raise ValueError("Workbook execution requires workspace and Excel permissions.")
    allowed = context.get("allowed_tools")
    if isinstance(allowed, list) and "office" not in allowed:
        raise ValueError("Workbook execution requires the Office tool permission.")


class WorkbookTransformJob(dict):
    """A non-replayable, destination-bound runtime contract with a safe summary."""

    def __init__(self, *, profile: dict, evidence: dict, template: Path,
                 pdfs: list[Path], root: Path, run_id: str, source_node_id: str,
                 target_node_id: str):
        super().__init__({
            JOB_MARKER: True,
            "status": "SUCCESS",
            "profile_id": profile["id"],
            "source_pdf_count": len(pdfs),
            "message": "Workbook rules validated; connected Files step will create the workbook.",
        })
        self._profile_json = json.dumps(profile)
        self._evidence_json = json.dumps(evidence)
        self._template = template.relative_to(root).as_posix()
        self._pdfs = tuple(path.relative_to(root).as_posix() for path in pdfs)
        self._run_id = run_id
        self._source_node_id = source_node_id
        self._target_node_id = target_node_id
        self._input_hashes = {
            path.relative_to(root).as_posix(): _file_hash(path)
            for path in [template, *pdfs]
        }

    def resolve(self, *, root: Path, run_id: str, source_node_id: str,
                target_node_id: str) -> tuple[dict, dict, dict[Path, str]]:
        if (run_id, source_node_id, target_node_id) != (
            self._run_id, self._source_node_id, self._target_node_id,
        ):
            raise ValueError("Workbook job does not belong to this run and connected Files step.")
        profile = json.loads(self._profile_json)
        _validate_profile(profile, json.loads(self._evidence_json))
        _workspace_file(self._template, root, ".xlsx")
        for path in self._pdfs:
            _workspace_file(path, root, ".pdf")
        for relative, expected in self._input_hashes.items():
            if _file_hash(root / relative) != expected:
                raise ValueError("A workbook job input changed after the Samurai step; run the flow again.")
        return profile, {
            "template_path": self._template,
            "pdf_paths": list(self._pdfs),
            # The private rules own the sheet contract; the Files node's legacy
            # Sheet1 default must not override it.
            "sheet_name": None,
        }, {root / relative: digest for relative, digest in self._input_hashes.items()}


def create_workbook_job(*, profile: dict, evidence: dict, predecessor_outputs: dict,
                        node_map: dict, downstream_contracts: list[dict], root: Path,
                        run_id: str, source_node_id: str,
                        governance: dict | None) -> WorkbookTransformJob:
    """Read authority from connected node configuration, never document content."""
    validate_workbook_permissions(governance)
    _validate_profile(profile, evidence)
    root = root.resolve()
    templates, pdfs = [], []
    for predecessor_id, output in predecessor_outputs.items():
        node = node_map.get(predecessor_id)
        if node is None or output is None:
            continue
        config = dict(node.config or {})
        if node.node_type == "file_template":
            if not isinstance(output, dict) or output.get("format") != "xlsx":
                raise ValueError("Samurai workbook rules require an Excel File Template.")
            template = _workspace_file(config.get("template_path"), root, ".xlsx")
            if _workspace_file(output.get("template_path"), root, ".xlsx") != template:
                raise ValueError("File Template output does not match its configured workbook.")
            templates.append(template)
        elif node.node_type == "office" and config.get("action") == "pdf_read":
            if int(config.get("start_page") or 1) != 1 or config.get("end_page"):
                raise ValueError("Samurai workbook rules require full PDFs; clear the PDF page range.")
            if (not isinstance(output, str) or not output.strip()
                    or output.lstrip().startswith(("[ERROR]", "[BLOCKED]"))):
                raise ValueError("Samurai workbook source PDF did not finish reading successfully.")
            pdfs.append(_workspace_file(config.get("input_path"), root, ".pdf"))
    if len(templates) != 1:
        raise ValueError("Connect exactly one Excel File Template directly to the Samurai.")
    if not 1 <= len(pdfs) <= 10 or len(set(pdfs)) != len(pdfs):
        raise ValueError("Connect between one and ten distinct PDF Read nodes directly to the Samurai.")
    writers = [item for item in downstream_contracts
               if item.get("node_type") == "office" and item.get("action") == "excel_create"]
    if len(writers) != 1:
        raise ValueError("Connect the Samurai to exactly one Files > Excel - Create step.")
    return WorkbookTransformJob(
        profile=profile, evidence=evidence, template=templates[0], pdfs=pdfs, root=root,
        run_id=run_id, source_node_id=source_node_id, target_node_id=str(writers[0]["node_id"]),
    )


def connected_workbook_job(predecessor_outputs: dict | None) -> tuple[str, WorkbookTransformJob] | None:
    jobs = []
    for node_id, output in (predecessor_outputs or {}).items():
        if isinstance(output, WorkbookTransformJob):
            jobs.append((node_id, output))
        elif isinstance(output, dict) and output.get(JOB_MARKER):
            raise ValueError("Workbook jobs must come from the current configured Samurai execution.")
    if len(jobs) > 1:
        raise ValueError("Files received multiple Samurai workbook jobs; connect exactly one.")
    return jobs[0] if jobs else None
