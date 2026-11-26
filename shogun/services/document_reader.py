"""Lightweight document text extraction for AgentFlow Input and Samurai instruction uploads."""

from __future__ import annotations

import csv
import io
import json
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path


def read_document_text(file_path: Path, *, max_chars: int = 5_000_000) -> dict[str, object]:
    """Extract plain text from supported workflow documents without heavy Office dependencies."""
    if not file_path.is_file():
        raise FileNotFoundError(f"Document not found: {file_path}")

    ext = file_path.suffix.lower()
    if ext in {".txt", ".md"}:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    elif ext == ".json":
        raw = file_path.read_text(encoding="utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
            content = json.dumps(parsed, indent=2, ensure_ascii=False)
        except json.JSONDecodeError:
            content = raw
    elif ext == ".csv":
        raw = file_path.read_text(encoding="utf-8", errors="replace")
        reader = csv.reader(io.StringIO(raw))
        content = "\n".join("\t".join(row) for row in reader)
    elif ext == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(file_path))
        pages = [page.extract_text() or "" for page in reader.pages]
        content = "\n\n".join(part for part in pages if part.strip())
    elif ext == ".docx":
        content = _read_docx(file_path)
    elif ext == ".xlsx":
        content = _read_xlsx(file_path)
    else:
        content = file_path.read_text(encoding="utf-8", errors="replace")

    truncated = len(content) > max_chars
    if truncated:
        content = content[:max_chars]

    return {
        "filename": file_path.name,
        "content": content,
        "truncated": truncated,
    }


def _read_docx(file_path: Path) -> str:
    paragraphs: list[str] = []
    with zipfile.ZipFile(file_path) as archive:
        if "word/document.xml" not in archive.namelist():
            return ""
        root = ET.fromstring(archive.read("word/document.xml"))
        for elem in root.iter():
            if elem.tag.endswith("}p"):
                texts = [t.text for t in elem.iter() if t.tag.endswith("}t") and t.text]
                if texts:
                    paragraphs.append("".join(texts))
    return "\n".join(paragraphs)


def _read_xlsx(file_path: Path) -> str:
    lines: list[str] = []
    with zipfile.ZipFile(file_path) as archive:
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            sst = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for si in sst.iter():
                if si.tag.endswith("}si"):
                    shared_strings.append(
                        "".join(t.text for t in si.iter() if t.tag.endswith("}t") and t.text)
                    )
        sheet_names = sorted(
            name for name in archive.namelist()
            if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")
        )
        for sheet_name in sheet_names:
            root = ET.fromstring(archive.read(sheet_name))
            sheet_rows: list[str] = []
            for row in root.iter():
                if not row.tag.endswith("}row"):
                    continue
                values: list[str] = []
                for cell in row:
                    if not cell.tag.endswith("}c"):
                        continue
                    cell_type = cell.attrib.get("t", "")
                    val_text = ""
                    for child in cell:
                        if child.tag.endswith("}v") and child.text is not None:
                            if cell_type == "s":
                                idx = int(child.text)
                                val_text = shared_strings[idx] if 0 <= idx < len(shared_strings) else child.text
                            else:
                                val_text = child.text
                        elif child.tag.endswith("}is"):
                            val_text = "".join(t.text for t in child.iter() if t.tag.endswith("}t") and t.text)
                    values.append(val_text)
                if any(values):
                    sheet_rows.append("\t".join(values))
            if sheet_rows:
                lines.append(f"[{Path(sheet_name).stem}]\n" + "\n".join(sheet_rows))
    return "\n\n".join(lines)
