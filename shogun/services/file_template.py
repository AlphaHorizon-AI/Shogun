"""Template extraction and rendering for AgentFlow File Template nodes.

The template source is always treated as immutable. Rendering copies it to a
new output path before applying generated content.
"""

from __future__ import annotations

import json
import re
import shutil
from copy import copy
from pathlib import Path
from typing import Any

TEMPLATE_MARKER = "__shogun_file_template__"
SUPPORTED_TEMPLATE_SUFFIXES = {".docx", ".xlsx"}
_PLACEHOLDER_RE = re.compile(r"{{\s*([A-Za-z0-9_.-]+)\s*}}")


def resolve_workspace_template(template_path: str, workspace_root: Path) -> Path:
    """Resolve and validate a template path inside the configured workspace."""
    raw = str(template_path or "").strip().replace("\\", "/")
    if not raw:
        raise ValueError("Select a Word (.docx) or Excel (.xlsx) template file.")
    if ".." in Path(raw).parts:
        raise ValueError(f"Template path traversal blocked: {raw}")

    root = workspace_root.resolve()
    target = (root / raw).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError("Template file must remain inside the configured workspace.") from exc
    if target.suffix.lower() not in SUPPORTED_TEMPLATE_SUFFIXES:
        raise ValueError("File Template nodes currently support .docx and .xlsx files.")
    if not target.is_file():
        raise ValueError(f"Template file was not found: {raw}")
    return target


def extract_file_template(
    template_path: str,
    workspace_root: Path,
    guidance_mode: str = "structure_only",
    example_handling: str = "replace",
    max_chars: int = 12_000,
) -> dict[str, Any]:
    """Build a bounded template contract for the Samurai and Files node."""
    mode = guidance_mode if guidance_mode in {"structure_only", "one_shot"} else "structure_only"
    handling = example_handling if example_handling in {"replace", "append", "preserve"} else "replace"
    source = resolve_workspace_template(template_path, workspace_root)
    relative = source.relative_to(workspace_root.resolve()).as_posix()

    if source.suffix.lower() == ".docx":
        contract, example = _extract_word_contract(source)
        file_format = "docx"
    else:
        contract, example = _extract_excel_contract(source)
        file_format = "xlsx"

    return {
        TEMPLATE_MARKER: True,
        "template_path": relative,
        "format": file_format,
        "guidance_mode": mode,
        "example_handling": handling,
        "contract": contract[:max_chars],
        "example": example[:max_chars] if mode == "one_shot" else "",
    }


def format_template_guidance(payload: dict[str, Any]) -> str:
    """Format a template payload as a precise model-facing output contract."""
    mode = payload.get("guidance_mode", "structure_only")
    lines = [
        "[FILE TEMPLATE CONTRACT]",
        f"Template: {payload.get('template_path', '')}",
        f"Format: {payload.get('format', '')}",
        f"Guidance mode: {'one-shot example' if mode == 'one_shot' else 'structure only'}",
        f"Output handling: {payload.get('example_handling', 'replace')}",
        "Generate the requested content so it fits this exact template contract. Do not output the template itself.",
        "Return only the content/data that should be inserted into the new file.",
        "",
        str(payload.get("contract") or ""),
    ]
    if mode == "one_shot" and payload.get("example"):
        lines.extend(
            [
                "",
                "[POPULATED ONE-SHOT EXAMPLE]",
                "Use the following existing content as a formatting example, not as factual input for the new result:",
                str(payload["example"]),
            ]
        )
    return "\n".join(lines).strip()


def render_word_template(source: Path, output: Path, context: str, handling: str) -> int:
    """Copy a Word template and populate the copy. Returns changed item count."""
    from docx import Document

    _copy_template(source, output)
    doc = Document(str(output))
    content = _unwrap_flow_context(context)
    replacements = _context_replacements(content)
    changed = _replace_docx_placeholders(doc, replacements)

    if handling == "append":
        for line in content.splitlines() or [content]:
            doc.add_paragraph(line)
            changed += 1
    elif handling == "preserve":
        if changed == 0:
            raise ValueError("Preserve unchanged requires at least one {{placeholder}} in the Word template.")
    elif changed == 0:
        changed = _replace_word_example_content(doc, content)

    doc.save(str(output))
    return changed


def render_excel_template(
    source: Path,
    output: Path,
    context: str,
    handling: str,
    sheet_name: str | None = None,
) -> int:
    """Copy an Excel template and populate the copy. Returns written cell count."""
    import openpyxl

    _copy_template(source, output)
    wb = openpyxl.load_workbook(str(output))
    try:
        ws = wb[sheet_name] if sheet_name and sheet_name in wb.sheetnames else wb[wb.sheetnames[0]]
        content = _unwrap_flow_context(context)
        replacements = _context_replacements(content)
        changed = _replace_excel_placeholders(ws, replacements)

        if handling == "preserve":
            if changed == 0:
                raise ValueError("Preserve unchanged requires at least one {{placeholder}} in the Excel template.")
        else:
            rows = _rows_from_context(content)
            if handling == "replace" and changed == 0:
                changed += _replace_excel_example_rows(ws, rows)
            elif handling == "append":
                changed += _append_excel_rows(ws, rows)
        wb.save(str(output))
        return changed
    finally:
        wb.close()


def _copy_template(source: Path, output: Path) -> None:
    source = source.resolve()
    output = output.resolve()
    if source == output:
        raise ValueError("Template output must be a new file; it cannot overwrite the source template.")
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, output)


def _extract_word_contract(path: Path) -> tuple[str, str]:
    from docx import Document

    doc = Document(str(path))
    headings: list[str] = []
    placeholders: set[str] = set()
    example_parts: list[str] = []
    for paragraph in doc.paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue
        example_parts.append(text)
        placeholders.update(_PLACEHOLDER_RE.findall(text))
        if str(paragraph.style.name).lower().startswith("heading"):
            headings.append(text)

    table_shapes: list[str] = []
    for index, table in enumerate(doc.tables, 1):
        rows = [[cell.text.strip() for cell in row.cells] for row in table.rows]
        width = max((len(row) for row in rows), default=0)
        headers = rows[0] if rows else []
        table_shapes.append(f"Table {index}: {len(rows)} row(s) x {width} column(s); header: " + " | ".join(headers))
        for row in rows[:12]:
            example_parts.append("| " + " | ".join(row) + " |")
            for cell in row:
                placeholders.update(_PLACEHOLDER_RE.findall(cell))

    contract_lines = ["Word document structure:"]
    contract_lines.append("- Headings: " + (" > ".join(headings) if headings else "none detected"))
    contract_lines.append("- Placeholders: " + (", ".join(sorted(placeholders)) if placeholders else "none detected"))
    contract_lines.extend(f"- {shape}" for shape in table_shapes)
    contract_lines.append("- Preserve the document's page setup, styles, headers, footers, tables, and branding.")
    return "\n".join(contract_lines), "\n".join(example_parts)


def _extract_excel_contract(path: Path) -> tuple[str, str]:
    import openpyxl

    wb = openpyxl.load_workbook(str(path), data_only=False, read_only=True)
    try:
        contract_lines = ["Excel workbook structure:"]
        example_parts: list[str] = []
        placeholders: set[str] = set()
        for ws in wb.worksheets:
            rows = list(
                ws.iter_rows(
                    min_row=1,
                    max_row=min(ws.max_row, 12),
                    max_col=min(ws.max_column, 20),
                    values_only=True,
                )
            )
            first_nonempty = next((row for row in rows if any(value not in (None, "") for value in row)), ())
            headers = [str(value) if value is not None else "" for value in first_nonempty]
            formula_count = sum(1 for row in rows for value in row if isinstance(value, str) and value.startswith("="))
            contract_lines.append(
                f"- Sheet '{ws.title}': used range {ws.max_row} row(s) x {ws.max_column} column(s); "
                f"header: {' | '.join(headers) or 'none detected'}; formulas in preview: {formula_count}"
            )
            example_parts.append(f"[Sheet: {ws.title}]")
            for row in rows:
                values = ["" if value is None else str(value) for value in row]
                example_parts.append("\t".join(values))
                for value in values:
                    placeholders.update(_PLACEHOLDER_RE.findall(value))
        contract_lines.append(
            "- Placeholders: " + (", ".join(sorted(placeholders)) if placeholders else "none detected")
        )
        contract_lines.append(
            "- Preserve sheet names, formulas, formatting, widths, frozen panes, and workbook structure."
        )
        return "\n".join(contract_lines), "\n".join(example_parts)
    finally:
        wb.close()


def _unwrap_flow_context(context: str) -> str:
    text = str(context or "").strip()
    match = re.fullmatch(r"\[Output from '[^']+'\]:\n([\s\S]*)", text)
    return match.group(1).strip() if match else text


def _context_replacements(context: str) -> dict[str, str]:
    replacements = {"context": context}
    candidate = context.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*([\s\S]*?)\s*```", candidate, re.IGNORECASE)
    if fenced:
        candidate = fenced.group(1)
    try:
        parsed = json.loads(candidate)
    except (json.JSONDecodeError, TypeError):
        parsed = None
    if isinstance(parsed, dict):
        for key, value in parsed.items():
            if isinstance(value, (str, int, float, bool)) or value is None:
                replacements[str(key)] = "" if value is None else str(value)
    return replacements


def _replace_text(text: str, replacements: dict[str, str]) -> tuple[str, int]:
    count = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal count
        key = match.group(1)
        if key not in replacements:
            return match.group(0)
        count += 1
        return replacements[key]

    return _PLACEHOLDER_RE.sub(replace, text), count


def _replace_paragraph(paragraph: Any, replacements: dict[str, str]) -> int:
    updated, count = _replace_text(paragraph.text, replacements)
    if count:
        if paragraph.runs:
            paragraph.runs[0].text = updated
            for run in paragraph.runs[1:]:
                run.text = ""
        else:
            paragraph.text = updated
    return count


def _replace_docx_placeholders(doc: Any, replacements: dict[str, str]) -> int:
    count = sum(_replace_paragraph(paragraph, replacements) for paragraph in doc.paragraphs)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                count += sum(_replace_paragraph(paragraph, replacements) for paragraph in cell.paragraphs)
    for section in doc.sections:
        for container in (section.header, section.footer):
            count += sum(_replace_paragraph(paragraph, replacements) for paragraph in container.paragraphs)
    return count


def _replace_word_example_content(doc: Any, content: str) -> int:
    lines = content.splitlines() or [content]
    editable = [
        paragraph
        for paragraph in doc.paragraphs
        if paragraph.text.strip() and not str(paragraph.style.name).lower().startswith("heading")
    ]
    changed = 0
    for index, paragraph in enumerate(editable):
        paragraph.text = lines[index] if index < len(lines) else ""
        changed += 1
    for line in lines[len(editable) :]:
        doc.add_paragraph(line)
        changed += 1
    return changed


def _replace_excel_placeholders(ws: Any, replacements: dict[str, str]) -> int:
    changed = 0
    for row in ws.iter_rows():
        for cell in row:
            if not isinstance(cell.value, str):
                continue
            updated, count = _replace_text(cell.value, replacements)
            if count:
                cell.value = updated
                changed += count
    return changed


def _rows_from_context(context: str) -> list[list[str]]:
    lines = context.strip().splitlines() if context.strip() else []
    markdown_rows: list[list[str]] = []
    saw_separator = False
    for line in lines:
        stripped = line.strip()
        if not (stripped.startswith("|") and stripped.endswith("|")):
            continue
        cells = [cell.strip() for cell in stripped[1:-1].split("|")]
        if cells and all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells):
            saw_separator = True
            continue
        if cells:
            markdown_rows.append(cells)
    if saw_separator and markdown_rows:
        return markdown_rows
    return [line.split("\t") for line in lines]


def _template_header_row(ws: Any) -> int:
    for row_index in range(1, ws.max_row + 1):
        if any(ws.cell(row_index, column).value not in (None, "") for column in range(1, ws.max_column + 1)):
            return row_index
    return 1


def _copy_row_style(ws: Any, source_row: int, target_row: int, width: int) -> None:
    if source_row > ws.max_row:
        return
    for column in range(1, width + 1):
        source = ws.cell(source_row, column)
        target = ws.cell(target_row, column)
        if source.has_style:
            target._style = copy(source._style)
        if source.number_format:
            target.number_format = source.number_format


def _replace_excel_example_rows(ws: Any, rows: list[list[str]]) -> int:
    if not rows:
        return 0
    header_row = _template_header_row(ws)
    template_headers = [str(ws.cell(header_row, col).value or "").strip() for col in range(1, ws.max_column + 1)]
    if rows and [cell.strip() for cell in rows[0]][: len(template_headers)] == template_headers:
        rows = rows[1:]
    start_row = header_row + 1
    existing_end = ws.max_row
    for row_index in range(start_row, existing_end + 1):
        for column in range(1, ws.max_column + 1):
            cell = ws.cell(row_index, column)
            if not (isinstance(cell.value, str) and cell.value.startswith("=")):
                cell.value = None
    width = max([ws.max_column, *(len(row) for row in rows)])
    style_row = start_row if start_row <= existing_end else header_row
    changed = 0
    for offset, values in enumerate(rows):
        target_row = start_row + offset
        _copy_row_style(ws, style_row, target_row, width)
        for column, value in enumerate(values, 1):
            ws.cell(target_row, column, value=value.strip())
            changed += 1
    return changed


def _append_excel_rows(ws: Any, rows: list[list[str]]) -> int:
    if not rows:
        return 0
    header_row = _template_header_row(ws)
    template_headers = [str(ws.cell(header_row, col).value or "").strip() for col in range(1, ws.max_column + 1)]
    if [cell.strip() for cell in rows[0]][: len(template_headers)] == template_headers:
        rows = rows[1:]
    start_row = ws.max_row + 1
    width = max([ws.max_column, *(len(row) for row in rows)], default=ws.max_column)
    style_row = ws.max_row
    changed = 0
    for offset, values in enumerate(rows):
        target_row = start_row + offset
        _copy_row_style(ws, style_row, target_row, width)
        for column, value in enumerate(values, 1):
            ws.cell(target_row, column, value=value.strip())
            changed += 1
    return changed
