"""Deterministic, safety-first file format adapter layer (Order 19)."""

from __future__ import annotations

import asyncio
import configparser
import csv
import hashlib
import io
import json
import mimetypes
import os
import re
import stat
import uuid
import zipfile
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from typing import Any, ClassVar
from xml.etree import ElementTree

import tomllib
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.config import PROJECT_ROOT, settings
from shogun.db.models.file_artifact import FileArtifact
from shogun.services.event_logger import EventLogger


class FileFormatError(ValueError):
    """Safe, user-facing file handling failure."""

    def __init__(self, message: str, error_type: str = "file_error"):
        super().__init__(message)
        self.error_type = error_type


@dataclass(frozen=True)
class AdapterSpec:
    format_id: str
    display_name: str
    extensions: tuple[str, ...]
    mime_types: tuple[str, ...]
    capabilities: tuple[str, ...]
    risk_level: str = "low"
    supports_write: bool = False
    supports_indexing: bool = True
    status: str = "native"


@dataclass(frozen=True)
class DetectionResult:
    detected_format: str
    confidence: float
    method: str
    extension: str
    mime_type: str | None


@dataclass
class Inspection:
    summary: str
    data: dict[str, Any] = field(default_factory=dict)
    schema: dict[str, Any] = field(default_factory=dict)
    preview: Any = None
    warnings: list[str] = field(default_factory=list)
    encoding: str | None = None


SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret|token|password|passwd)\s*[:=]\s*['\"]?([^\s,'\"]{6,})"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\b(?:sk|ghp|xox[baprs])[-_][A-Za-z0-9_-]{16,}\b"),
    re.compile(r"(?i)(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?)://[^\s]+"),
]
BLOCKED_BINARY_EXTENSIONS = {".exe", ".dll", ".msi", ".scr", ".com", ".dmg", ".iso", ".app"}
SCRIPT_EXTENSIONS = {".bat", ".cmd", ".ps1", ".sh", ".py", ".js", ".ts"}
FORMULA_PREFIXES = ("=", "+", "-", "@")


def _read_text(path: Path, limit: int | None = None) -> tuple[str, str]:
    raw = path.read_bytes() if limit is None else path.read_bytes()[:limit]
    for encoding in ("utf-8-sig", "utf-8", "utf-16", "cp1252"):
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace"), "utf-8-replacement"


def _masked(text: str) -> tuple[str, int]:
    count = 0
    result = text
    for pattern in SECRET_PATTERNS:

        def replace(match: re.Match[str]) -> str:
            nonlocal count
            count += 1
            if match.lastindex and match.lastindex >= 2:
                return f"{match.group(1)}=[REDACTED]"
            return "[REDACTED SECRET]"

        result = pattern.sub(replace, result)
    return result, count


def _mask_preview(value: Any) -> tuple[Any, int]:
    if isinstance(value, str):
        return _masked(value)
    if isinstance(value, list):
        masked_items = []
        total = 0
        for item in value:
            masked, count = _mask_preview(item)
            masked_items.append(masked)
            total += count
        return masked_items, total
    if isinstance(value, dict):
        masked_mapping = {}
        total = 0
        for key, item in value.items():
            if re.search(r"(?i)(?:api[_-]?key|secret|token|password|passwd|private[_-]?key)", str(key)):
                masked_mapping[key] = "[REDACTED]"
                total += 1
            else:
                masked, count = _mask_preview(item)
                masked_mapping[key] = masked
                total += count
        return masked_mapping, total
    return value, 0


def _depth(value: Any, level: int = 0) -> int:
    if isinstance(value, dict):
        return max((_depth(item, level + 1) for item in value.values()), default=level)
    if isinstance(value, list):
        return max((_depth(item, level + 1) for item in value), default=level)
    return level


def _scalar_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "string"


def _merge_schema(records: list[Any]) -> dict[str, Any]:
    fields: dict[str, set[str]] = {}
    for record in records:
        if isinstance(record, dict):
            for key, value in record.items():
                fields.setdefault(str(key), set()).add(_scalar_type(value))
    return {key: sorted(types) for key, types in sorted(fields.items())}


class BaseAdapter:
    spec: ClassVar[AdapterSpec]

    def inspect(self, path: Path, max_rows: int) -> Inspection:
        raise NotImplementedError

    def query(self, path: Path, query: str, limit: int) -> Any:
        raise FileFormatError(f"Query is not supported for {self.spec.display_name}.", "unsupported_operation")


class DelimitedAdapter(BaseAdapter):
    spec = AdapterSpec(
        "csv",
        "CSV / TSV",
        (".csv", ".tsv"),
        ("text/csv", "text/tab-separated-values"),
        ("inspect", "parse", "preview", "schema", "query", "validate", "transform", "export", "index"),
        supports_write=True,
    )

    @staticmethod
    def _dialect(text: str, suffix: str) -> csv.Dialect:
        try:
            return csv.Sniffer().sniff(text[:65536], delimiters=",;\t|")
        except csv.Error:
            return csv.excel_tab if suffix == ".tsv" else csv.excel

    def inspect(self, path: Path, max_rows: int) -> Inspection:
        text, encoding = _read_text(path)
        dialect = self._dialect(text, path.suffix.lower())
        stream = io.StringIO(text)
        reader = csv.reader(stream, dialect)
        rows = list(reader)
        if not rows:
            return Inspection("Empty delimited file.", {"rows": 0, "columns": 0}, preview=[], encoding=encoding)
        try:
            has_header = csv.Sniffer().has_header(text[:65536])
        except csv.Error:
            has_header = True
        width = max(len(row) for row in rows)
        headers = rows[0] if has_header else [f"column_{index + 1}" for index in range(width)]
        body = rows[1:] if has_header else rows
        missing = {
            headers[i]: sum(1 for row in body if i >= len(row) or not row[i].strip()) for i in range(len(headers))
        }
        inconsistent = sum(1 for row in body if len(row) != width)
        duplicates = len(body) - len({tuple(row) for row in body})
        typed: dict[str, str] = {}
        for index, header in enumerate(headers):
            values = [row[index].strip() for row in body[:1000] if index < len(row) and row[index].strip()]
            if values and all(re.fullmatch(r"[-+]?\d+", value) for value in values):
                typed[header] = "integer"
            elif values and all(re.fullmatch(r"[-+]?(?:\d+\.\d*|\d*\.\d+)", value) for value in values):
                typed[header] = "number"
            elif values and all(re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:[T ][^ ]+)?", value) for value in values):
                typed[header] = "date"
            else:
                typed[header] = "string"
        preview = [dict(zip(headers, row, strict=False)) for row in body[:max_rows]]
        warnings = [f"{inconsistent} rows have inconsistent column counts."] if inconsistent else []
        return Inspection(
            f"Delimited file with {len(body):,} rows and {width} columns.",
            {
                "rows": len(body),
                "columns": width,
                "delimiter": dialect.delimiter,
                "has_header": has_header,
                "missing_values": missing,
                "duplicate_rows": duplicates,
                "inconsistent_rows": inconsistent,
            },
            {"columns": typed},
            preview,
            warnings,
            encoding,
        )

    def query(self, path: Path, query: str, limit: int) -> Any:
        inspection = self.inspect(path, max(limit, 1000))
        rows = inspection.preview or []
        query = query.strip()
        if not query or query == "*":
            return rows[:limit]
        key, separator, expected = query.partition("=")
        if not separator:
            raise FileFormatError("CSV query must be '*' or 'column=value'.", "invalid_query")
        return [row for row in rows if str(row.get(key.strip(), "")) == expected.strip()][:limit]


class JsonAdapter(BaseAdapter):
    spec = AdapterSpec(
        "json",
        "JSON",
        (".json",),
        ("application/json",),
        ("inspect", "parse", "preview", "schema", "query", "validate", "transform", "export", "index"),
        supports_write=True,
    )

    def inspect(self, path: Path, max_rows: int) -> Inspection:
        text, encoding = _read_text(path)
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise FileFormatError(
                f"Invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}", "parse_error"
            ) from exc
        if _depth(value) > settings.file_max_json_depth:
            raise FileFormatError("JSON exceeds the configured nesting-depth limit.", "structure_too_deep")
        records = value if isinstance(value, list) else [value]
        preview = records[:max_rows] if isinstance(value, list) else value
        schema = {"root_type": _scalar_type(value), "fields": _merge_schema(records)}
        size = len(value) if isinstance(value, (list, dict)) else 1
        return Inspection(
            f"Valid JSON {schema['root_type']} containing {size:,} top-level item(s).",
            {"items": size},
            schema,
            preview,
            encoding=encoding,
        )

    def query(self, path: Path, query: str, limit: int) -> Any:
        text, _ = _read_text(path)
        value = json.loads(text)
        if query in {"", "$"}:
            return value
        if not query.startswith("$."):
            raise FileFormatError("JSON query must start with '$.'.", "invalid_query")
        current: list[Any] = [value]
        for token in query[2:].split("."):
            next_values: list[Any] = []
            match = re.fullmatch(r"([^\[]+)(?:\[(\*|\d+)\])?", token)
            if not match:
                raise FileFormatError(f"Unsupported JSON path token: {token}", "invalid_query")
            key, index = match.groups()
            for item in current:
                selected = item.get(key) if isinstance(item, dict) else None
                if index == "*" and isinstance(selected, list):
                    next_values.extend(selected)
                elif index is not None and isinstance(selected, list) and int(index) < len(selected):
                    next_values.append(selected[int(index)])
                elif index is None and selected is not None:
                    next_values.append(selected)
            current = next_values[:limit]
        return current[0] if len(current) == 1 else current


class JsonLinesAdapter(BaseAdapter):
    spec = AdapterSpec(
        "jsonl",
        "JSON Lines / NDJSON",
        (".jsonl", ".ndjson"),
        ("application/x-ndjson",),
        ("inspect", "parse", "preview", "schema", "query", "validate", "export", "index"),
        supports_write=True,
    )

    def inspect(self, path: Path, max_rows: int) -> Inspection:
        text, encoding = _read_text(path)
        valid: list[Any] = []
        invalid: list[dict[str, Any]] = []
        for line_number, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                if _depth(record) > settings.file_max_json_depth:
                    raise FileFormatError("Record exceeds the configured nesting-depth limit.", "structure_too_deep")
                valid.append(record)
            except FileFormatError:
                raise
            except json.JSONDecodeError as exc:
                invalid.append({"line": line_number, "error": exc.msg})
        warnings = [f"{len(invalid)} invalid record line(s)."] if invalid else []
        return Inspection(
            f"JSON Lines file with {len(valid):,} valid and {len(invalid):,} invalid records.",
            {"valid_records": len(valid), "invalid_records": len(invalid), "invalid_lines": invalid[:100]},
            {"fields": _merge_schema(valid)},
            valid[:max_rows],
            warnings,
            encoding,
        )

    def query(self, path: Path, query: str, limit: int) -> Any:
        records = self.inspect(path, 100000).preview or []
        if query in {"", "*"}:
            return records[:limit]
        key, separator, expected = query.partition("=")
        if not separator:
            raise FileFormatError("JSONL filter must be '*' or 'field=value'.", "invalid_query")
        return [row for row in records if isinstance(row, dict) and str(row.get(key.strip())) == expected.strip()][
            :limit
        ]


class XmlAdapter(BaseAdapter):
    spec = AdapterSpec(
        "xml",
        "XML",
        (".xml",),
        ("application/xml", "text/xml"),
        ("inspect", "parse", "preview", "schema", "query", "validate", "transform", "index"),
        risk_level="medium",
    )

    @staticmethod
    def _root(path: Path) -> tuple[ElementTree.Element, str]:
        text, encoding = _read_text(path)
        if re.search(r"<!\s*(?:DOCTYPE|ENTITY)", text, re.IGNORECASE):
            raise FileFormatError(
                "XML DTD and entity declarations are blocked to prevent XXE/entity expansion.", "unsafe_xml"
            )
        try:
            return ElementTree.fromstring(text), encoding
        except ElementTree.ParseError as exc:
            raise FileFormatError(f"Invalid XML: {exc}", "parse_error") from exc

    def inspect(self, path: Path, max_rows: int) -> Inspection:
        root, encoding = self._root(path)
        tags = Counter(element.tag.split("}")[-1] for element in root.iter())
        preview = [
            {
                "tag": element.tag.split("}")[-1],
                "attributes": element.attrib,
                "text": (element.text or "").strip()[:500],
            }
            for element in list(root.iter())[:max_rows]
        ]
        return Inspection(
            f"Well-formed XML with root <{root.tag.split('}')[-1]}> and {sum(tags.values()):,} elements.",
            {"root": root.tag.split("}")[-1], "tag_counts": dict(tags)},
            {"tags": sorted(tags)},
            preview,
            encoding=encoding,
        )

    def query(self, path: Path, query: str, limit: int) -> Any:
        root, _ = self._root(path)
        safe_query = query.lstrip("/")
        if any(token in safe_query for token in ("::", "(", ")", "@")):
            raise FileFormatError("Only basic element paths are supported.", "invalid_query")
        return [
            {"tag": item.tag, "attributes": item.attrib, "text": (item.text or "").strip()}
            for item in root.findall(f".//{safe_query}")[:limit]
        ]


class YamlAdapter(BaseAdapter):
    spec = AdapterSpec(
        "yaml",
        "YAML",
        (".yaml", ".yml"),
        ("application/yaml", "text/yaml"),
        ("inspect", "parse", "preview", "schema", "query", "validate", "transform", "index"),
        risk_level="medium",
    )

    def inspect(self, path: Path, max_rows: int) -> Inspection:
        try:
            import yaml
        except ImportError as exc:
            raise FileFormatError("PyYAML is required for YAML support.", "adapter_unavailable") from exc
        text, encoding = _read_text(path)
        try:
            value = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise FileFormatError(f"Invalid YAML: {exc}", "parse_error") from exc
        if _depth(value) > settings.file_max_json_depth:
            raise FileFormatError("YAML exceeds the configured nesting-depth limit.", "structure_too_deep")
        records = value if isinstance(value, list) else [value]
        return Inspection(
            f"Safely parsed YAML {_scalar_type(value)}.",
            {},
            {"root_type": _scalar_type(value), "fields": _merge_schema(records)},
            records[:max_rows] if isinstance(value, list) else value,
            encoding=encoding,
        )


class ConfigAdapter(BaseAdapter):
    spec = AdapterSpec(
        "config",
        "TOML / INI / CFG",
        (".toml", ".ini", ".cfg", ".conf"),
        ("application/toml", "text/plain"),
        ("inspect", "parse", "preview", "schema", "query", "validate", "transform", "index"),
        supports_write=True,
    )

    def _parse(self, path: Path) -> tuple[dict[str, Any], str, str]:
        text, encoding = _read_text(path)
        if path.suffix.lower() == ".toml":
            try:
                return tomllib.loads(text), encoding, "toml"
            except tomllib.TOMLDecodeError as exc:
                raise FileFormatError(f"Invalid TOML: {exc}", "parse_error") from exc
        parser = configparser.ConfigParser(interpolation=None)
        try:
            parser.read_string(text)
        except configparser.Error as exc:
            raise FileFormatError(f"Invalid INI/CFG: {exc}", "parse_error") from exc
        return {section: dict(parser[section]) for section in parser.sections()}, encoding, "ini"

    def inspect(self, path: Path, max_rows: int) -> Inspection:
        value, encoding, subtype = self._parse(path)
        return Inspection(
            f"Valid {subtype.upper()} configuration with {len(value)} top-level section(s).",
            {"subtype": subtype, "sections": list(value)},
            {"sections": list(value)},
            value,
            encoding=encoding,
        )

    def query(self, path: Path, query: str, limit: int) -> Any:
        value, _, _ = self._parse(path)
        current: Any = value
        for key in query.strip("$.").split("."):
            if not key:
                continue
            if not isinstance(current, dict) or key not in current:
                return None
            current = current[key]
        return current


class MarkdownAdapter(BaseAdapter):
    spec = AdapterSpec(
        "markdown",
        "Markdown",
        (".md", ".markdown", ".mdown"),
        ("text/markdown",),
        ("inspect", "parse", "preview", "query", "validate", "transform", "index"),
        supports_write=True,
    )

    def inspect(self, path: Path, max_rows: int) -> Inspection:
        text, encoding = _read_text(path)
        headings = [
            {
                "level": len(match.group(1)),
                "title": match.group(2).strip(),
                "line": text[: match.start()].count("\n") + 1,
            }
            for match in re.finditer(r"(?m)^(#{1,6})\s+(.+?)\s*$", text)
        ]
        links = [
            {"text": match.group(1), "target": match.group(2)}
            for match in re.finditer(r"(?<!!)\[([^]]+)\]\(([^)]+)\)", text)
        ]
        table_rows = [line for line in text.splitlines() if line.strip().startswith("|") and line.count("|") >= 2]
        preview, secrets = _masked(text[: settings.file_max_preview_bytes])
        warnings = [f"Masked {secrets} likely secret(s) in preview."] if secrets else []
        return Inspection(
            f"Markdown document with {len(headings)} headings, {len(links)} links, and {len(table_rows)} table rows.",
            {"headings": headings, "links": links, "table_rows": table_rows[:max_rows]},
            {"outline": headings},
            preview,
            warnings,
            encoding,
        )

    def query(self, path: Path, query: str, limit: int) -> Any:
        text, _ = _read_text(path)
        heading = query.strip().lstrip("#").strip().lower()
        pattern = re.compile(r"(?m)^(#{1,6})\s+(.+?)\s*$")
        matches = list(pattern.finditer(text))
        for index, match in enumerate(matches):
            if match.group(2).strip().lower() == heading:
                end = next(
                    (item.start() for item in matches[index + 1 :] if len(item.group(1)) <= len(match.group(1))),
                    len(text),
                )
                return text[match.end() : end].strip()[: settings.file_max_preview_bytes]
        return None


class _StaticHtmlParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.links: list[dict[str, str]] = []
        self.text: list[str] = []
        self._in_title = False
        self._ignored = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "title":
            self._in_title = True
        if tag in {"script", "style", "noscript"}:
            self._ignored += 1
        if tag == "a" and values.get("href"):
            self.links.append({"target": values["href"] or ""})

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        if tag in {"script", "style", "noscript"} and self._ignored:
            self._ignored -= 1

    def handle_data(self, data: str) -> None:
        if self._ignored:
            return
        clean = " ".join(data.split())
        if clean:
            self.text.append(clean)
            if self._in_title:
                self.title += clean


class HtmlAdapter(BaseAdapter):
    spec = AdapterSpec(
        "html",
        "Static HTML",
        (".html", ".htm"),
        ("text/html",),
        ("inspect", "parse", "preview", "query", "validate", "transform", "index"),
        supports_write=True,
    )

    def inspect(self, path: Path, max_rows: int) -> Inspection:
        text, encoding = _read_text(path)
        parser = _StaticHtmlParser()
        parser.feed(text)
        visible = "\n".join(parser.text)
        preview, secrets = _masked(visible[: settings.file_max_preview_bytes])
        warnings = [f"Masked {secrets} likely secret(s) in preview."] if secrets else []
        return Inspection(
            f"Static HTML titled '{parser.title or path.name}' with {len(parser.links)} links.",
            {"title": parser.title, "links": parser.links[:max_rows], "visible_text_chars": len(visible)},
            preview=preview,
            warnings=warnings,
            encoding=encoding,
        )


class LogAdapter(BaseAdapter):
    spec = AdapterSpec(
        "log",
        "Log File",
        (".log", ".out", ".trace"),
        ("text/plain",),
        ("inspect", "parse", "preview", "query", "validate", "index"),
    )
    LEVEL = re.compile(r"\b(TRACE|DEBUG|INFO|WARN(?:ING)?|ERROR|FATAL|CRITICAL)\b", re.IGNORECASE)

    def inspect(self, path: Path, max_rows: int) -> Inspection:
        text, encoding = _read_text(path)
        lines = text.splitlines()
        levels = Counter(
            (match.group(1).upper().replace("WARNING", "WARN") if (match := self.LEVEL.search(line)) else "UNKNOWN")
            for line in lines
        )
        errors = [
            line for line in lines if re.search(r"\b(ERROR|FATAL|CRITICAL|exception|traceback)\b", line, re.IGNORECASE)
        ]
        repeated = Counter(errors)
        preview, secrets = _masked("\n".join(lines[:max_rows]))
        warnings = [f"Masked {secrets} likely secret(s) in preview."] if secrets else []
        return Inspection(
            f"Log with {len(lines):,} lines, {len(errors):,} error-related lines, "
            f"and {levels.get('WARN', 0):,} warnings.",
            {
                "lines": len(lines),
                "levels": dict(levels),
                "errors": errors[:max_rows],
                "repeated_errors": repeated.most_common(20),
            },
            preview=preview,
            warnings=warnings,
            encoding=encoding,
        )

    def query(self, path: Path, query: str, limit: int) -> Any:
        text, _ = _read_text(path)
        return [line for line in text.splitlines() if query.lower() in line.lower()][:limit]


class CodeAdapter(BaseAdapter):
    EXTENSIONS = (
        ".py",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".css",
        ".sql",
        ".sh",
        ".bash",
        ".ps1",
        ".bat",
        ".cmd",
        ".java",
        ".go",
        ".rs",
        ".c",
        ".cpp",
        ".h",
        ".dockerfile",
    )
    spec = AdapterSpec(
        "code",
        "Source Code",
        EXTENSIONS,
        ("text/x-python", "text/javascript", "text/css", "application/sql"),
        ("inspect", "parse", "preview", "query", "validate", "compare", "index"),
        risk_level="medium",
    )
    LANGUAGES = {
        ".py": "Python",
        ".js": "JavaScript",
        ".jsx": "JavaScript JSX",
        ".ts": "TypeScript",
        ".tsx": "TypeScript JSX",
        ".css": "CSS",
        ".sql": "SQL",
        ".sh": "Shell",
        ".bash": "Shell",
        ".ps1": "PowerShell",
        ".bat": "Batch",
        ".cmd": "Batch",
        ".java": "Java",
        ".go": "Go",
        ".rs": "Rust",
        ".c": "C",
        ".cpp": "C++",
        ".h": "C/C++ Header",
    }

    def inspect(self, path: Path, max_rows: int) -> Inspection:
        text, encoding = _read_text(path)
        suffix = path.suffix.lower()
        language = "Dockerfile" if path.name.lower() == "dockerfile" else self.LANGUAGES.get(suffix, "Source code")
        symbols = []
        imports = []
        for number, line in enumerate(text.splitlines(), 1):
            if match := re.match(
                r"\s*(?:async\s+)?(?:def|class|function|interface|type|enum)\s+([A-Za-z_$][\w$]*)", line
            ):
                symbols.append({"name": match.group(1), "line": number, "declaration": line.strip()[:300]})
            if re.match(r"\s*(?:from\s+\S+\s+import|import\s+|require\(|#include|using\s+)", line):
                imports.append({"line": number, "text": line.strip()[:300]})
        preview, secrets = _masked("\n".join(text.splitlines()[:max_rows]))
        warnings = ["Script content was inspected as text and was not executed."]
        if secrets:
            warnings.append(f"Masked {secrets} likely secret(s) in preview.")
        return Inspection(
            f"{language} source with {len(text.splitlines()):,} lines and {len(symbols)} baseline symbols.",
            {"language": language, "lines": len(text.splitlines()), "symbols": symbols, "imports": imports},
            {"symbols": symbols},
            preview,
            warnings,
            encoding,
        )

    def query(self, path: Path, query: str, limit: int) -> Any:
        text, _ = _read_text(path)
        return [
            {"line": number, "text": line}
            for number, line in enumerate(text.splitlines(), 1)
            if query.lower() in line.lower()
        ][:limit]


class ZipAdapter(BaseAdapter):
    spec = AdapterSpec(
        "zip",
        "ZIP Archive",
        (".zip",),
        ("application/zip",),
        ("inspect", "preview", "validate", "extract", "export"),
        risk_level="high",
        supports_write=True,
        supports_indexing=False,
    )

    @staticmethod
    def _entry_risk(info: zipfile.ZipInfo) -> list[str]:
        risks = []
        pure = PurePosixPath(info.filename.replace("\\", "/"))
        if pure.is_absolute() or ".." in pure.parts or re.match(r"^[A-Za-z]:", info.filename):
            risks.append("path_traversal")
        mode = info.external_attr >> 16
        if stat.S_ISLNK(mode):
            risks.append("symlink")
        if Path(info.filename).suffix.lower() in BLOCKED_BINARY_EXTENSIONS:
            risks.append("executable")
        if (
            info.file_size
            and info.compress_size
            and info.file_size / max(info.compress_size, 1) > settings.file_archive_max_ratio
        ):
            risks.append("suspicious_compression_ratio")
        return risks

    def inspect(self, path: Path, max_rows: int) -> Inspection:
        try:
            with zipfile.ZipFile(path) as archive:
                entries = []
                total = 0
                risky = 0
                nested = 0
                for info in archive.infolist():
                    risks = self._entry_risk(info)
                    total += info.file_size
                    risky += bool(risks)
                    nested += Path(info.filename).suffix.lower() == ".zip"
                    entries.append(
                        {
                            "name": info.filename,
                            "compressed_bytes": info.compress_size,
                            "uncompressed_bytes": info.file_size,
                            "is_directory": info.is_dir(),
                            "risks": risks,
                        }
                    )
        except zipfile.BadZipFile as exc:
            raise FileFormatError("Invalid or corrupted ZIP archive.", "parse_error") from exc
        warnings = []
        if total > settings.file_archive_max_uncompressed_bytes:
            warnings.append("Archive exceeds the configured uncompressed size limit and cannot be extracted.")
        if risky:
            warnings.append(f"{risky} unsafe archive entries detected; they will not be extracted.")
        return Inspection(
            f"ZIP archive with {len(entries):,} entries ({total:,} uncompressed bytes).",
            {
                "entries": entries,
                "entry_count": len(entries),
                "uncompressed_bytes": total,
                "nested_archives": nested,
                "unsafe_entries": risky,
            },
            preview=entries[:max_rows],
            warnings=warnings,
        )


class TextAdapter(BaseAdapter):
    spec = AdapterSpec(
        "text",
        "Plain Text",
        (".txt", ".text"),
        ("text/plain",),
        ("inspect", "preview", "query", "validate", "transform", "index"),
        supports_write=True,
    )

    def inspect(self, path: Path, max_rows: int) -> Inspection:
        text, encoding = _read_text(path)
        preview, secrets = _masked(text[: settings.file_max_preview_bytes])
        warnings = [f"Masked {secrets} likely secret(s) in preview."] if secrets else []
        return Inspection(
            f"Plain text with {len(text.splitlines()):,} lines and {len(text):,} characters.",
            {"lines": len(text.splitlines()), "characters": len(text)},
            preview=preview,
            warnings=warnings,
            encoding=encoding,
        )

    def query(self, path: Path, query: str, limit: int) -> Any:
        text, _ = _read_text(path)
        return [
            {"line": number, "text": line}
            for number, line in enumerate(text.splitlines(), 1)
            if query.lower() in line.lower()
        ][:limit]


class ExistingPipelineAdapter(BaseAdapter):
    def __init__(self, spec: AdapterSpec):
        self.spec = spec

    def inspect(self, path: Path, max_rows: int) -> Inspection:
        return Inspection(
            f"{self.spec.display_name} is recognized and remains handled by Shogun's existing dedicated adapter.",
            {"delegated_adapter": True},
            warnings=["Use the dedicated PDF, Office, or Visual Intake tools for content-level operations."],
        )


class UnknownAdapter(BaseAdapter):
    spec = AdapterSpec(
        "unknown",
        "Unknown / Proprietary",
        (),
        ("application/octet-stream",),
        ("inspect", "preview"),
        risk_level="medium",
        supports_indexing=False,
        status="fallback",
    )

    def inspect(self, path: Path, max_rows: int) -> Inspection:
        raw = path.read_bytes()[: min(settings.file_max_preview_bytes, 4096)]
        binary = b"\x00" in raw
        if binary:
            preview: Any = raw[:256].hex(" ")
        else:
            preview, secrets = _masked(raw.decode("utf-8", errors="replace"))
            if secrets:
                return Inspection(
                    "Unsupported text-like file; metadata and a masked safe preview are available only.",
                    {"binary": False},
                    preview=preview,
                    warnings=[
                        f"Masked {secrets} likely secret(s).",
                        "This file is not natively parsed; no structural claims are made.",
                    ],
                )
        return Inspection(
            "Unsupported file; metadata and a safe preview are available only.",
            {"binary": binary},
            preview=preview,
            warnings=["This file is not natively supported; Shogun is not claiming to parse it."],
        )


class AdapterRegistry:
    def __init__(self):
        adapters: list[BaseAdapter] = [
            DelimitedAdapter(),
            JsonAdapter(),
            JsonLinesAdapter(),
            XmlAdapter(),
            YamlAdapter(),
            ConfigAdapter(),
            MarkdownAdapter(),
            HtmlAdapter(),
            LogAdapter(),
            CodeAdapter(),
            ZipAdapter(),
            TextAdapter(),
        ]
        adapters.extend(
            [
                ExistingPipelineAdapter(
                    AdapterSpec(
                        "pdf",
                        "PDF",
                        (".pdf",),
                        ("application/pdf",),
                        ("inspect", "preview", "extract", "index"),
                        status="existing",
                    )
                ),
                ExistingPipelineAdapter(
                    AdapterSpec(
                        "office",
                        "Microsoft Office",
                        (".docx", ".xlsx", ".pptx"),
                        ("application/vnd.openxmlformats-officedocument.wordprocessingml.document",),
                        ("inspect", "preview", "transform", "export", "index"),
                        status="existing",
                    )
                ),
                ExistingPipelineAdapter(
                    AdapterSpec(
                        "image",
                        "Image",
                        (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"),
                        ("image/png", "image/jpeg", "image/webp"),
                        ("inspect", "preview", "extract", "index"),
                        status="existing",
                    )
                ),
            ]
        )
        self.adapters: dict[str, BaseAdapter] = {}
        self._extensions: dict[str, str] = {}
        self._mimes: dict[str, str] = {}
        for adapter in adapters:
            self.register(adapter)
        self.register(UnknownAdapter())

    def register(self, adapter: BaseAdapter, *, replace: bool = False) -> None:
        """Register a native or proprietary adapter without changing generic tool logic."""
        format_id = adapter.spec.format_id
        if format_id in self.adapters and not replace:
            raise ValueError(f"Adapter '{format_id}' is already registered.")
        self.adapters[format_id] = adapter
        for extension in adapter.spec.extensions:
            self._extensions[extension.lower()] = format_id
        for mime in adapter.spec.mime_types:
            self._mimes[mime.lower()] = format_id

    def get(self, format_id: str) -> BaseAdapter:
        return self.adapters.get(format_id, self.adapters["unknown"])

    def formats(self) -> list[dict[str, Any]]:
        return [asdict(adapter.spec) for adapter in self.adapters.values()]

    def detect(self, path: Path, declared_mime: str | None = None) -> DetectionResult:
        extension = path.suffix.lower()
        name = path.name.lower()
        mime = declared_mime or mimetypes.guess_type(path.name)[0]
        if mime:
            mime = mime.split(";", 1)[0].strip().lower()
        sample = path.read_bytes()[:65536]
        stripped = sample.lstrip()
        if sample.startswith(b"PK\x03\x04") and extension in {".docx", ".xlsx", ".pptx"}:
            return DetectionResult("office", 0.99, "magic_bytes_and_extension", extension, mime)
        if sample.startswith(b"PK\x03\x04"):
            return DetectionResult("zip", 1.0, "magic_bytes", extension, mime)
        if sample.startswith(b"%PDF-"):
            return DetectionResult("pdf", 1.0, "magic_bytes", extension, mime)
        if sample.startswith((b"\x89PNG", b"\xff\xd8\xff", b"RIFF")):
            return DetectionResult("image", 0.99, "magic_bytes", extension, mime)
        if not settings.file_detect_by_content:
            if extension in self._extensions:
                return DetectionResult(self._extensions[extension], 0.9, "extension", extension, mime)
            if mime in self._mimes:
                return DetectionResult(self._mimes[mime], 0.75, "mime_type", extension, mime)
            return DetectionResult("unknown", 0.2, "fallback", extension, mime or "application/octet-stream")
        text = sample.decode("utf-8", errors="ignore")
        if stripped.startswith((b"{", b"[")):
            try:
                json.loads(text)
                return DetectionResult("json", 0.98, "content_sniffing", extension, mime)
            except json.JSONDecodeError:
                pass
        lines = [line for line in text.splitlines() if line.strip()][:20]
        if len(lines) >= 2:
            valid_json_lines = 0
            for line in lines:
                try:
                    json.loads(line)
                    valid_json_lines += 1
                except json.JSONDecodeError:
                    break
            if valid_json_lines == len(lines):
                return DetectionResult("jsonl", 0.96, "content_sniffing", extension, mime)
        if re.match(r"\s*<(?:\?xml\b|[A-Za-z_][\w:.-]*(?:\s|>|/))", text):
            fmt = "html" if re.search(r"<\s*(?:html|head|body)\b", text, re.IGNORECASE) else "xml"
            return DetectionResult(fmt, 0.94, "content_sniffing", extension, mime)
        if name == "dockerfile":
            return DetectionResult("code", 0.98, "filename", extension, mime)
        if extension in self._extensions:
            return DetectionResult(self._extensions[extension], 0.9, "extension", extension, mime)
        if mime in self._mimes:
            return DetectionResult(self._mimes[mime], 0.75, "mime_type", extension, mime)
        if text and "\x00" not in text:
            try:
                dialect = csv.Sniffer().sniff(text, delimiters=",;\t|")
                if len(lines) >= 2 and dialect.delimiter:
                    return DetectionResult("csv", 0.72, "parser_trial", extension, mime)
            except csv.Error:
                pass
            if re.search(r"(?m)^#{1,6}\s+", text):
                return DetectionResult("markdown", 0.7, "content_sniffing", extension, mime)
            return DetectionResult("text", 0.6, "content_sniffing", extension, mime)
        return DetectionResult("unknown", 0.2, "fallback", extension, mime or "application/octet-stream")


registry = AdapterRegistry()


class FileSafetyGate:
    def __init__(self, allowed_roots: list[Path] | None = None):
        roots = (
            allowed_roots
            if allowed_roots is not None
            else [
                settings.workspace_path,
                settings.uploads_path,
                settings.office_path,
                settings.mado_path,
                settings.memory_imports_path,
                settings.memory_exports_path,
                PROJECT_ROOT,
            ]
        )
        self.allowed_roots = [root.resolve() for root in roots]

    def resolve(self, path: Path, *, allow_archive: bool = False) -> tuple[Path, list[str]]:
        """Return an approved existing file without dereferencing a client path.

        Directory entries are walked from a trusted root. The requested path is
        used only for lexical comparison, never as an operand of a filesystem
        call. This also blocks symlinks in every path component.
        """
        lexical = Path(os.path.abspath(os.fspath(path)))
        matched: tuple[Path, Path] | None = None
        for root in self.allowed_roots:
            try:
                relative = lexical.relative_to(root)
            except ValueError:
                continue
            matched = (root, relative)
            break
        if matched is None:
            raise FileFormatError("File is outside approved workspace/artifact directories.", "path_outside_workspace")

        root, relative = matched
        current = root
        final_entry: os.DirEntry[str] | None = None
        for component in relative.parts:
            if component in {"", ".", ".."}:
                raise FileFormatError("The requested path is invalid.", "invalid_path")
            try:
                with os.scandir(current) as entries:
                    expected = os.path.normcase(component)
                    final_entry = next(
                        (entry for entry in entries if os.path.normcase(entry.name) == expected),
                        None,
                    )
            except OSError as exc:
                raise FileFormatError("The requested path could not be accessed.", "invalid_path") from exc
            if final_entry is None:
                raise FileFormatError("The requested path does not exist.", "invalid_path")
            if final_entry.is_symlink():
                raise FileFormatError("Symbolic-link file access is blocked.", "path_escape")
            current = Path(final_entry.path)

        if final_entry is None or not final_entry.is_file(follow_symlinks=False):
            raise FileFormatError("The requested path is not a regular file.", "invalid_path")
        size = final_entry.stat(follow_symlinks=False).st_size
        if size > settings.file_max_parse_bytes:
            raise FileFormatError(
                f"File exceeds the {settings.file_max_parse_bytes:,}-byte parsing limit.", "file_too_large"
            )
        if current.suffix.lower() in BLOCKED_BINARY_EXTENSIONS:
            raise FileFormatError(
                "Executable or high-risk binary formats are metadata-only and blocked from parsing.",
                "blocked_file_type",
            )
        warnings = []
        if current.suffix.lower() in SCRIPT_EXTENSIONS:
            warnings.append("Executable script content is read-only; file handling will never execute it.")
        if current.name.lower() in {".env", "id_rsa", "id_ed25519"}:
            warnings.append("Protected/secret-like filename detected; preview content will be masked.")
        return current, warnings

    def validate(self, path: Path, *, allow_archive: bool = False) -> list[str]:
        """Validate a file path while preserving the legacy warnings-only API."""
        _, warnings = self.resolve(path, allow_archive=allow_archive)
        return warnings


class FileFormatService:
    def __init__(self, session: AsyncSession | None = None, allowed_roots: list[Path] | None = None):
        self.session = session
        self.safety = FileSafetyGate(allowed_roots)

    async def _path(self, path: str | None = None, file_id: uuid.UUID | None = None) -> Path:
        if not settings.file_format_handling_enabled:
            raise FileFormatError("File format handling is disabled by configuration.", "policy_blocked")
        if file_id:
            if not self.session:
                raise FileFormatError("A database session is required for file IDs.")
            artifact = await self.session.get(FileArtifact, file_id)
            if not artifact:
                raise FileFormatError("File ID was not found.", "not_found")
            return Path(artifact.path)
        if not path:
            raise FileFormatError("path or file_id is required.", "invalid_request")
        return Path(path)

    async def detect(
        self, path: str | None = None, file_id: uuid.UUID | None = None, mime_type: str | None = None
    ) -> dict[str, Any]:
        target = await self._path(path, file_id)
        target, warnings = self.safety.resolve(target, allow_archive=True)
        result = registry.detect(target, mime_type)
        await self._audit(
            "file.format.detected",
            f"Detected {result.detected_format} for {target.name}",
            target,
            result.detected_format,
        )
        return {**asdict(result), "path": str(target.resolve()), "warnings": warnings}

    async def inspect(
        self,
        path: str | None = None,
        file_id: uuid.UUID | None = None,
        source: str = "workspace",
        mime_type: str | None = None,
    ) -> dict[str, Any]:
        target = await self._path(path, file_id)
        target, safety_warnings = self.safety.resolve(target, allow_archive=True)
        detection = registry.detect(target, mime_type)
        adapter = registry.get(detection.detected_format)
        await self._audit("file.inspect.started", f"Inspecting {target.name}", target, detection.detected_format)
        try:
            result = adapter.inspect(target, settings.file_max_rows_preview)
        except FileFormatError:
            await self._audit(
                "file.inspect.failed",
                f"Inspection failed for {target.name}",
                target,
                detection.detected_format,
                "failed",
            )
            raise
        preview = result.preview
        if settings.file_mask_secrets_in_preview:
            preview, masked_count = _mask_preview(preview)
            if masked_count and not any("Masked" in warning for warning in result.warnings):
                result.warnings.append(f"Masked {masked_count} likely secret(s) in preview.")
        warnings = safety_warnings + result.warnings
        artifact = await self._register(target, detection, adapter.spec, source, warnings, result)
        payload = {
            "status": "success",
            "file_id": str(artifact.id) if artifact else None,
            "format_id": detection.detected_format,
            "operation": "inspect",
            "path": str(target.resolve()),
            "filename": target.name,
            "size_bytes": target.stat().st_size,
            "hash_sha256": self._hash(target),
            "encoding": result.encoding,
            "detection": asdict(detection),
            "summary": result.summary,
            "data": result.data,
            "schema": result.schema,
            "preview": preview,
            "warnings": warnings,
            "capabilities": list(adapter.spec.capabilities),
            "artifacts": [],
        }
        event_id = await self._audit("file.inspect.completed", result.summary, target, detection.detected_format)
        payload["audit_event_id"] = event_id
        return payload

    async def query(
        self, query: str, path: str | None = None, file_id: uuid.UUID | None = None, limit: int = 100
    ) -> dict[str, Any]:
        target = await self._path(path, file_id)
        target, _ = self.safety.resolve(target)
        detection = registry.detect(target)
        result = registry.get(detection.detected_format).query(target, query, limit)
        event_id = await self._audit("file.query.executed", f"Queried {target.name}", target, detection.detected_format)
        return {
            "status": "success",
            "file_id": str(file_id) if file_id else None,
            "format_id": detection.detected_format,
            "operation": "query",
            "summary": f"Query returned {len(result) if isinstance(result, list) else 1} result(s).",
            "data": result,
            "warnings": [],
            "artifacts": [],
            "audit_event_id": event_id,
        }

    async def read(
        self,
        path: str | None = None,
        file_id: uuid.UUID | None = None,
        *,
        start: int = 1,
        end: int | None = None,
        sheet: str | None = None,
        max_chars: int = 40000,
    ) -> dict[str, Any]:
        """Read bounded content from a registered or approved file.

        This is the content-level counterpart to ``inspect``. It never
        executes file content and caps the returned payload before it reaches
        an LLM context window.
        """
        target = await self._path(path, file_id)
        target, warnings = self.safety.resolve(target)
        detection = registry.detect(target)
        format_id = detection.detected_format
        # Ordinary chat callers still request a conservative 40k-100k limit.
        # AgentFlow may deliberately request more so a long document can be
        # divided into model-sized chunks instead of silently losing everything
        # after the first 100,000 characters.
        limit = max(1000, min(int(max_chars or 40000), settings.file_max_parse_bytes))
        start = max(1, int(start or 1))
        content: Any
        metadata: dict[str, Any] = {}

        try:
            if format_id == "pdf":
                from pypdf import PdfReader

                reader = PdfReader(str(target))
                page_count = len(reader.pages)
                last = min(int(end or page_count), page_count)
                if start > page_count or last < start:
                    raise FileFormatError("Requested PDF page range is outside the document.", "invalid_request")
                page_text: dict[int, str] = {}
                ocr_candidates: list[int] = []
                for page_number in range(start - 1, last):
                    display_number = page_number + 1
                    extracted = reader.pages[page_number].extract_text() or ""
                    page_text[display_number] = extracted
                    if len(extracted.strip()) < 10:
                        ocr_candidates.append(display_number)

                ocr_pages = ocr_candidates[:25]
                if ocr_pages:
                    from shogun.services.pdf_ocr import PdfOcrError, windows_ocr_pdf_pages

                    try:
                        recognized = await asyncio.to_thread(windows_ocr_pdf_pages, target, ocr_pages)
                        applied = []
                        for page_number, recognized_text in recognized.items():
                            if recognized_text and len(recognized_text) > len(page_text.get(page_number, "").strip()):
                                page_text[page_number] = recognized_text
                                applied.append(page_number)
                        if applied:
                            warnings.append(
                                "Applied local Windows OCR to PDF page(s): "
                                + ", ".join(str(number) for number in applied)
                                + "."
                            )
                    except PdfOcrError as exc:
                        warnings.append(f"Local PDF OCR was unavailable: {exc}")
                if len(ocr_candidates) > len(ocr_pages):
                    warnings.append("OCR was limited to the first 25 image-only pages in the requested range.")

                chunks = [
                    f"--- Page {page_number} ---\n{page_text.get(page_number, '')}"
                    for page_number in range(start, last + 1)
                ]
                content = "\n\n".join(chunks)
                metadata = {
                    "page_count": page_count,
                    "start_page": start,
                    "end_page": last,
                    "ocr_candidate_pages": ocr_candidates,
                }
            elif format_id in {"docx", "word"} or (format_id == "office" and target.suffix.lower() == ".docx"):
                from shogun.office.adapters.word_adapter import close_document, open_document, read_text

                handle = open_document(str(target))
                try:
                    content = read_text(handle)
                finally:
                    close_document(handle)
            elif format_id in {"xlsx", "excel"} or (format_id == "office" and target.suffix.lower() == ".xlsx"):
                from shogun.office.adapters.excel_adapter import close_workbook, list_sheets, open_workbook, read_used_range

                handle = open_workbook(str(target))
                try:
                    sheets = list_sheets(handle)
                    selected = sheet or (sheets[0] if sheets else None)
                    if not selected:
                        content = []
                    else:
                        content = read_used_range(handle, selected)[: settings.file_max_rows_preview]
                    metadata = {"sheets": sheets, "selected_sheet": selected}
                finally:
                    close_workbook(handle)
            elif format_id in {"pptx", "powerpoint"} or (format_id == "office" and target.suffix.lower() == ".pptx"):
                from shogun.office.adapters.pptx_adapter import close_presentation, open_presentation, read_slide_text

                handle = open_presentation(str(target))
                try:
                    slide_count = len(handle.presentation.slides)
                    last = min(int(end or slide_count), slide_count)
                    if start > slide_count or last < start:
                        raise FileFormatError("Requested slide range is outside the presentation.", "invalid_request")
                    content = "\n\n".join(
                        f"--- Slide {number} ---\n{read_slide_text(handle, number - 1)}"
                        for number in range(start, last + 1)
                    )
                    metadata = {"slide_count": slide_count, "start_slide": start, "end_slide": last}
                finally:
                    close_presentation(handle)
            else:
                inspected = registry.get(format_id).inspect(target, settings.file_max_rows_preview)
                content = inspected.preview
                metadata = {"schema": inspected.schema, "profile": inspected.data}
                warnings.extend(inspected.warnings)
        except FileFormatError:
            raise
        except Exception as exc:
            raise FileFormatError(f"Could not read {target.name}: {exc}", "parse_error") from exc

        serialized = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False, default=str)
        if settings.file_mask_secrets_in_preview:
            serialized, masked_count = _masked(serialized)
            if masked_count:
                warnings.append(f"Masked {masked_count} likely secret(s) in file content.")
        truncated = len(serialized) > limit
        if truncated:
            serialized = serialized[:limit]
            warnings.append(f"Content was truncated to {limit:,} characters for safe chat use.")
        event_id = await self._audit("file.read.completed", f"Read bounded content from {target.name}", target, format_id)
        return {
            "status": "success",
            "file_id": str(file_id) if file_id else None,
            "format_id": format_id,
            "operation": "read",
            "filename": target.name,
            "content": serialized,
            "truncated": truncated,
            "metadata": metadata,
            "warnings": warnings,
            "audit_event_id": event_id,
        }

    async def validate(self, **reference: Any) -> dict[str, Any]:
        try:
            result = await self.inspect(**reference)
            return {**result, "operation": "validate", "valid": True}
        except FileFormatError as exc:
            return {
                "status": "failed",
                "operation": "validate",
                "valid": False,
                "error_type": exc.error_type,
                "message": str(exc),
                "warnings": [],
                "artifacts": [],
            }

    async def compare(self, left_path: str, right_path: str) -> dict[str, Any]:
        left = await self.inspect(path=left_path)
        right = await self.inspect(path=right_path)
        event_id = await self._audit(
            "file.compare.completed",
            f"Compared {Path(left_path).name} and {Path(right_path).name}",
            Path(left_path),
            left["format_id"],
        )
        return {
            "status": "success",
            "operation": "compare",
            "summary": "Compared deterministic file profiles and content hashes.",
            "left": left,
            "right": right,
            "same_format": left["format_id"] == right["format_id"],
            "same_hash": left["hash_sha256"] == right["hash_sha256"],
            "audit_event_id": event_id,
        }

    async def transform(
        self,
        target_format: str,
        output_filename: str | None = None,
        options: dict[str, Any] | None = None,
        **reference: Any,
    ) -> dict[str, Any]:
        target = await self._path(reference.get("path"), reference.get("file_id"))
        target, _ = self.safety.resolve(target)
        detection = registry.detect(target)
        output_root = settings.workspace_path.resolve()
        output_root.mkdir(parents=True, exist_ok=True)
        filename = Path(output_filename or f"{target.stem}.{target_format}").name
        output = (output_root / filename).resolve()
        if output.exists():
            output = output.with_name(f"{output.stem}-{uuid.uuid4().hex[:8]}{output.suffix}")
        inspected = registry.get(detection.detected_format).inspect(target, 100000)
        value = inspected.preview
        if detection.detected_format == "json":
            value = json.loads(_read_text(target)[0])
        if target_format == "json":
            output.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
        elif (
            target_format in {"csv", "tsv"} and isinstance(value, list) and all(isinstance(row, dict) for row in value)
        ):
            headers = sorted({key for row in value for key in row})
            delimiter = "\t" if target_format == "tsv" else ","
            sanitize = (options or {}).get("sanitize_formulas", True)
            with output.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=headers, delimiter=delimiter)
                writer.writeheader()
                for row in value:
                    safe_row = {
                        key: ("'" + str(item) if sanitize and str(item).startswith(FORMULA_PREFIXES) else item)
                        for key, item in row.items()
                    }
                    writer.writerow(safe_row)
        elif target_format in {"md", "markdown"} and isinstance(value, list) and value and isinstance(value[0], dict):
            headers = list(value[0])
            lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
            lines.extend(
                "| " + " | ".join(str(row.get(key, "")).replace("|", "\\|") for key in headers) + " |" for row in value
            )
            output.write_text("\n".join(lines) + "\n", encoding="utf-8")
        else:
            raise FileFormatError(
                f"Transformation from {detection.detected_format} to {target_format} is not supported.",
                "unsupported_operation",
            )
        event_id = await self._audit(
            "file.transform.completed", f"Created transformed file {output.name}", output, target_format
        )
        return {
            "status": "success",
            "file_id": None,
            "format_id": target_format,
            "operation": "transform",
            "summary": f"Created {output.name} without overwriting the source.",
            "data": {},
            "warnings": [],
            "artifacts": [{"path": str(output), "filename": output.name}],
            "audit_event_id": event_id,
        }

    async def extract_archive(
        self,
        members: list[str],
        output_directory: str | None = None,
        allow_overwrite: bool = False,
        approved: bool = False,
        **reference: Any,
    ) -> dict[str, Any]:
        if not settings.file_archive_extraction_enabled:
            raise FileFormatError("Archive extraction is disabled by configuration.", "policy_blocked")
        if settings.file_archive_requires_approval and not approved:
            raise FileFormatError("Archive extraction requires explicit approval.", "approval_required")
        target = await self._path(reference.get("path"), reference.get("file_id"))
        target, _ = self.safety.resolve(target, allow_archive=True)
        if registry.detect(target).detected_format != "zip":
            raise FileFormatError("Selected file is not a ZIP archive.", "wrong_format")
        output_root = (
            Path(output_directory).resolve()
            if output_directory
            else (settings.workspace_path / f"extracted-{target.stem}").resolve()
        )
        approved_root = settings.workspace_path.resolve()
        if output_root != approved_root and approved_root not in output_root.parents:
            raise FileFormatError("Archive output must remain under the approved workspace directory.", "path_escape")
        output_root.mkdir(parents=True, exist_ok=True)
        extracted = []
        total = 0
        with zipfile.ZipFile(target) as archive:
            by_name = {info.filename: info for info in archive.infolist()}
            for member in members:
                info = by_name.get(member)
                if not info:
                    raise FileFormatError(f"Archive member not found: {member}", "not_found")
                risks = ZipAdapter._entry_risk(info)
                if risks:
                    await self._audit(
                        "file.archive.extraction_blocked",
                        f"Blocked unsafe archive member {member}",
                        target,
                        "zip",
                        "blocked",
                    )
                    raise FileFormatError(f"Unsafe archive member '{member}': {', '.join(risks)}", "unsafe_archive")
                total += info.file_size
                if total > settings.file_archive_max_uncompressed_bytes:
                    raise FileFormatError(
                        "Selected archive contents exceed the uncompressed size limit.", "archive_bomb"
                    )
                destination = (output_root / PurePosixPath(member)).resolve()
                if destination != output_root and output_root not in destination.parents:
                    raise FileFormatError("Archive member escapes the output directory.", "path_escape")
                if info.is_dir():
                    destination.mkdir(parents=True, exist_ok=True)
                    continue
                if destination.exists() and not allow_overwrite:
                    raise FileFormatError(
                        f"Extraction would overwrite {destination.name}; overwrite was not approved.",
                        "overwrite_blocked",
                    )
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as source, destination.open("wb") as output:
                    while chunk := source.read(1024 * 1024):
                        output.write(chunk)
                extracted.append(str(destination))
        event_id = await self._audit(
            "file.archive.extraction.completed", f"Extracted {len(extracted)} selected archive files", target, "zip"
        )
        return {
            "status": "success",
            "file_id": str(reference.get("file_id")) if reference.get("file_id") else None,
            "format_id": "zip",
            "operation": "extract",
            "summary": f"Safely extracted {len(extracted)} selected files.",
            "data": {"output_directory": str(output_root)},
            "warnings": [],
            "artifacts": [{"path": path} for path in extracted],
            "audit_event_id": event_id,
        }

    async def index_profile(self, agent_id: uuid.UUID, title: str | None = None, **reference: Any) -> dict[str, Any]:
        if not self.session:
            raise FileFormatError("A database session is required to index file profiles.")
        inspection = await self.inspect(**reference)
        adapter = registry.get(inspection["format_id"])
        if not adapter.spec.supports_indexing:
            raise FileFormatError("This format is not eligible for profile indexing.", "unsupported_operation")
        from shogun.services.memory_service import MemoryService

        content = json.dumps(
            {
                "summary": inspection["summary"],
                "schema": inspection["schema"],
                "profile": inspection["data"],
                "file_id": inspection["file_id"],
                "hash_sha256": inspection["hash_sha256"],
            },
            ensure_ascii=False,
            default=str,
        )
        memory = await MemoryService(self.session).create_memory(
            memory_type="semantic",
            agent_id=agent_id,
            title=title or f"File profile: {inspection['filename']}",
            content=content,
            summary=inspection["summary"],
            importance_score=0.5,
            confidence_score=0.95,
            decay_class="slow",
            tags=["file-profile", inspection["format_id"]],
            source_type="file_artifact",
            source_ref_id=uuid.UUID(inspection["file_id"]) if inspection["file_id"] else None,
        )
        await self.session.commit()
        event_id = await self._audit(
            "file.profile.indexed",
            f"Indexed file profile {inspection['filename']}",
            Path(inspection["path"]),
            inspection["format_id"],
        )
        return {
            "status": "success",
            "file_id": inspection["file_id"],
            "format_id": inspection["format_id"],
            "operation": "index",
            "summary": "Stored the normalized file profile without embedding the full file.",
            "data": {"memory_id": str(memory.id)},
            "warnings": [],
            "artifacts": [],
            "audit_event_id": event_id,
        }

    async def get_artifact(self, file_id: uuid.UUID) -> dict[str, Any]:
        if not self.session:
            raise FileFormatError("A database session is required for file IDs.")
        item = await self.session.get(FileArtifact, file_id)
        if not item:
            raise FileFormatError("File ID was not found.", "not_found")
        return self._public(item)

    async def _register(
        self,
        path: Path,
        detection: DetectionResult,
        spec: AdapterSpec,
        source: str,
        warnings: list[str],
        inspection: Inspection,
    ) -> FileArtifact | None:
        if not self.session:
            return None
        resolved = str(path.resolve())
        item = (
            await self.session.execute(select(FileArtifact).where(FileArtifact.path == resolved))
        ).scalar_one_or_none()
        if not item:
            item = FileArtifact(
                original_filename=path.name,
                path=resolved,
                format_id=detection.detected_format,
                mime_type=detection.mime_type,
                size_bytes=path.stat().st_size,
                hash_sha256=self._hash(path),
                source=source,
                detection_confidence=detection.confidence,
                detection_method=detection.method,
                permissions={},
                capabilities=list(spec.capabilities),
                warnings=warnings,
                inspection_json={},
            )
            self.session.add(item)
        item.format_id = detection.detected_format
        item.size_bytes = path.stat().st_size
        item.hash_sha256 = self._hash(path)
        item.detection_confidence = detection.confidence
        item.detection_method = detection.method
        item.capabilities = list(spec.capabilities)
        item.warnings = warnings
        item.inspection_json = {"summary": inspection.summary, "data": inspection.data, "schema": inspection.schema}
        item.last_inspected_at = datetime.now(timezone.utc)
        await self.session.flush()
        return item

    @staticmethod
    def _hash(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _public(item: FileArtifact) -> dict[str, Any]:
        return {
            "file_id": str(item.id),
            "original_filename": item.original_filename,
            "path": item.path,
            "format_id": item.format_id,
            "mime_type": item.mime_type,
            "size_bytes": item.size_bytes,
            "hash_sha256": item.hash_sha256,
            "source": item.source,
            "confidence": item.detection_confidence,
            "detection_method": item.detection_method,
            "capabilities": item.capabilities,
            "warnings": item.warnings,
            "inspection": item.inspection_json,
            "last_inspected_at": item.last_inspected_at,
        }

    @staticmethod
    async def _audit(event_type: str, action: str, path: Path, format_id: str, result: str = "success") -> str:
        return await EventLogger.emit(
            "file",
            event_type,
            action,
            result=result,
            tool_name="file_formats",
            risk_score="high" if format_id == "zip" else "medium" if format_id in {"xml", "code", "unknown"} else "low",
            detail={"path": str(path), "format_id": format_id},
        )
