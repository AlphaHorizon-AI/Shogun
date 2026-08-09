"""Application-agnostic deterministic field mapping engine."""

from __future__ import annotations

import ast
import csv
import io
import json
import logging
import re
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from shogun.mapping.errors import (
    MappingError,
    MappingFieldMissing,
    MappingInputError,
    MappingOutputError,
    MappingSchemaError,
    MappingTargetError,
    MappingTransformationError,
    MappingTypeError,
)
from shogun.mapping.schema import MappingConfig, MappingRule

log = logging.getLogger("shogun.mapping")
_MISSING = object()
_CELL_RE = re.compile(r"^([A-Z]{1,3})([1-9][0-9]*)$")


def _column_number(column: str) -> int:
    value = 0
    for char in column.upper():
        if not "A" <= char <= "Z":
            raise MappingTargetError(f"Invalid Excel column target: {column}", received=column)
        value = value * 26 + ord(char) - 64
    if value > 16384:
        raise MappingTargetError(f"Excel column exceeds XFD: {column}", received=column)
    return value


def _path_get(data: Any, path: str | None) -> Any:
    if not path:
        return data
    current = data
    for part in path.split("."):
        if part.endswith("[]"):
            key = part[:-2]
            if key:
                if not isinstance(current, dict) or key not in current:
                    return _MISSING
                current = current[key]
            if not isinstance(current, list):
                return _MISSING
            continue
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return _MISSING
    return current


def _json_from_text(text: str) -> Any:
    stripped = text.strip()
    if not stripped:
        raise MappingInputError("Mapping input is empty")
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", stripped, re.IGNORECASE)
        if fenced:
            try:
                return json.loads(fenced.group(1).strip())
            except json.JSONDecodeError:
                pass
        decoder = json.JSONDecoder()
        for match in re.finditer(r"[\[{]", stripped):
            try:
                value, _ = decoder.raw_decode(stripped[match.start() :])
                return value
            except json.JSONDecodeError:
                continue
    raise MappingInputError("Input text does not contain valid JSON and no delimiter is configured")


def _parse_input(payload: Any, delimiter: str | None) -> Any:
    if not isinstance(payload, str):
        return deepcopy(payload)
    if delimiter:
        if len(delimiter) != 1:
            raise MappingSchemaError("delimiter must be exactly one character")
        rows = list(csv.DictReader(io.StringIO(payload), delimiter=delimiter))
        if not rows:
            raise MappingInputError("Delimited input contained no records")
        return rows
    return _json_from_text(payload)


def _normalize_transform(item: Any) -> tuple[str, dict[str, Any]]:
    if isinstance(item, str):
        return item.strip().lower(), {}
    if hasattr(item, "name"):
        return str(item.name).strip().lower(), dict(item.options or {})
    if isinstance(item, dict):
        name = str(item.get("name") or item.get("type") or "").strip().lower()
        options = dict(item.get("options") or {})
        options.update({key: value for key, value in item.items() if key not in {"name", "type", "options"}})
        return name, options
    raise MappingTransformationError("Invalid transformation configuration", received=item)


def _decimal_value(value: Any) -> Decimal:
    if isinstance(value, bool):
        raise InvalidOperation
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value))
    text = str(value).strip().replace("\u00a0", "").replace(" ", "")
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    return Decimal(text)


def _parse_date(value: Any, *, datetime_output: bool = False, input_format: str | None = None) -> str:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, datetime.min.time())
    else:
        text = str(value).strip()
        formats = [input_format] if input_format else []
        formats += ["%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"]
        parsed = None
        for fmt in formats:
            if not fmt:
                continue
            try:
                parsed = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
        if parsed is None:
            try:
                parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            except ValueError as exc:
                raise MappingTypeError("Value is not a supported date", expected="date", received=value) from exc
    return parsed.isoformat() if datetime_output else parsed.date().isoformat()


def _apply_transform(value: Any, name: str, options: dict[str, Any]) -> Any:
    if name in {"", "none"}:
        return value
    if name == "trim":
        return value.strip() if isinstance(value, str) else value
    if name == "uppercase":
        return str(value).upper()
    if name == "lowercase":
        return str(value).lower()
    if name in {"decimal_normalize", "number_normalize"}:
        number = _decimal_value(value)
        return int(number) if number == number.to_integral_value() else float(number)
    if name in {"date_format", "date_normalize"}:
        return _parse_date(value, input_format=options.get("input_format"))
    if name == "replace":
        return str(value).replace(str(options.get("old", "")), str(options.get("new", "")))
    if name == "prefix":
        return f"{options.get('value', '')}{value}"
    if name == "suffix":
        return f"{value}{options.get('value', '')}"
    if name in {"convert", "type_convert", "default"}:
        return value
    raise MappingTransformationError(f"Unsupported transformation: {name}", received=name)


def _has_conversion_transform(rule: MappingRule) -> bool:
    names = {_normalize_transform(item)[0] for item in rule.transform}
    return bool(
        names & {"convert", "type_convert", "decimal_normalize", "number_normalize", "date_format", "date_normalize"}
    )


def _coerce(value: Any, expected: str, *, allow_coercion: bool, field: str) -> Any:
    if expected == "any":
        return value
    exact = {
        "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, (int, float, Decimal)) and not isinstance(value, bool),
        "decimal": isinstance(value, (int, float, Decimal)) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "array": isinstance(value, list),
        "object": isinstance(value, dict),
        "date": isinstance(value, (date, datetime))
        or (isinstance(value, str) and bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value))),
        "datetime": isinstance(value, datetime),
        "currency": isinstance(value, str),
    }.get(expected, False)
    if exact:
        if expected in {"number", "decimal"} and isinstance(value, Decimal):
            return float(value)
        if expected == "date" and isinstance(value, (date, datetime)):
            return _parse_date(value)
        if expected == "datetime" and isinstance(value, datetime):
            return value.isoformat()
        return value
    if not allow_coercion:
        raise MappingTypeError(
            f'Field "{field}" expected {expected}, received {type(value).__name__}',
            field=field,
            expected=expected,
            received=value,
        )
    try:
        if expected in {"string", "currency"}:
            return str(value)
        if expected == "integer":
            number = _decimal_value(value)
            if number != number.to_integral_value():
                raise InvalidOperation
            return int(number)
        if expected in {"number", "decimal"}:
            number = _decimal_value(value)
            return int(number) if number == number.to_integral_value() else float(number)
        if expected == "boolean":
            if isinstance(value, str) and value.strip().lower() in {"true", "yes", "1", "on"}:
                return True
            if isinstance(value, str) and value.strip().lower() in {"false", "no", "0", "off"}:
                return False
            if value in {0, 1}:
                return bool(value)
        if expected == "date":
            return _parse_date(value)
        if expected == "datetime":
            return _parse_date(value, datetime_output=True)
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise MappingTypeError(
            f'Field "{field}" could not be converted to {expected}',
            field=field,
            expected=expected,
            received=value,
        ) from exc
    raise MappingTypeError(
        f'Field "{field}" expected {expected}, received {type(value).__name__}',
        field=field,
        expected=expected,
        received=value,
    )


_ALLOWED_BINARY = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
    ast.Mod: lambda a, b: a % b,
}
_ALLOWED_COMPARE = {
    ast.Eq: lambda a, b: a == b,
    ast.NotEq: lambda a, b: a != b,
    ast.Gt: lambda a, b: a > b,
    ast.GtE: lambda a, b: a >= b,
    ast.Lt: lambda a, b: a < b,
    ast.LtE: lambda a, b: a <= b,
}


def _safe_expression(expression: str, values: dict[str, Any]) -> Any:
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise MappingTransformationError(f"Invalid expression: {expression}") from exc

    def evaluate(node: ast.AST) -> Any:
        if isinstance(node, ast.Expression):
            return evaluate(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (str, int, float, bool, type(None))):
            return node.value
        if isinstance(node, ast.Name):
            if node.id not in values:
                raise MappingFieldMissing(f'Expression field "{node.id}" not found', field=node.id)
            return values[node.id]
        if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINARY:
            return _ALLOWED_BINARY[type(node.op)](evaluate(node.left), evaluate(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd, ast.Not)):
            operand = evaluate(node.operand)
            return (
                -operand
                if isinstance(node.op, ast.USub)
                else +operand
                if isinstance(node.op, ast.UAdd)
                else not operand
            )
        if (
            isinstance(node, ast.Compare)
            and len(node.ops) == len(node.comparators) == 1
            and type(node.ops[0]) in _ALLOWED_COMPARE
        ):
            return _ALLOWED_COMPARE[type(node.ops[0])](evaluate(node.left), evaluate(node.comparators[0]))
        if isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
            results = [bool(evaluate(value)) for value in node.values]
            return all(results) if isinstance(node.op, ast.And) else any(results)
        raise MappingTransformationError("Expression contains an unsupported operation")

    try:
        return evaluate(tree)
    except MappingError:
        raise
    except Exception as exc:
        raise MappingTransformationError(f"Expression failed: {expression}") from exc


class MappingEngine:
    """Execute a validated mapping configuration without model calls or I/O."""

    def __init__(self, config: MappingConfig | dict[str, Any]) -> None:
        self.config = config if isinstance(config, MappingConfig) else MappingConfig.model_validate(config)

    def execute(self, payload: Any, *, context: dict[str, Any] | None = None) -> dict[str, Any]:
        parsed = _parse_input(payload, self.config.delimiter)
        records = self._records(parsed)
        received = len(records)
        records = self._deduplicate(records)
        mapped: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        review_required = False
        lineage: list[dict[str, Any]] = []
        log.info("mapping_started records_received=%d mapping=%s", received, self.config.name)
        for index, record in enumerate(records):
            try:
                result, review = self._map_record(record, index)
                mapped.append(result)
                review_required = review_required or review
                if self.config.retain_lineage:
                    lineage.append(self._lineage(record, index, context or {}))
                log.debug("mapping_record_processed record_index=%d", index)
            except MappingError as exc:
                exc.record_index = index if exc.record_index is None else exc.record_index
                errors.append(exc.as_dict())
                log.warning("mapping_validation_failed record_index=%d error=%s", index, exc)
                if self.config.on_record_error == "fail":
                    raise
        output = self._render(mapped)
        status = "REVIEW_REQUIRED" if review_required else "PARTIAL" if errors else "SUCCESS"
        result = {
            "__shogun_mapping_output__": True,
            "status": status,
            **output,
            "records_received": received,
            "records_written": len(mapped),
            "records_failed": len(errors),
            "errors": errors,
            "mapping": {"name": self.config.name, "version": self.config.version, "mode": self.config.mode},
        }
        if self.config.retain_lineage:
            result["lineage"] = lineage
        log.info(
            "mapping_completed records_received=%d records_written=%d records_failed=%d status=%s",
            received,
            len(mapped),
            len(errors),
            status,
        )
        return result

    def _records(self, parsed: Any) -> list[dict[str, Any]]:
        data = _path_get(parsed, self.config.input_path)
        if data is _MISSING:
            raise MappingInputError(f'Input path "{self.config.input_path}" not found', field=self.config.input_path)
        if not self.config.input_path:
            repeated_prefixes = {
                rule.source.split("[]", 1)[0].rstrip(".")
                for rule in self.config.mappings
                if rule.source and "[]" in rule.source
            }
            if len(repeated_prefixes) == 1:
                repeated = _path_get(data, next(iter(repeated_prefixes)))
                if isinstance(repeated, list):
                    data = repeated
        if isinstance(data, dict):
            return [data]
        if not isinstance(data, list):
            raise MappingInputError("Mapping input must resolve to an object or array of objects", received=data)
        if any(not isinstance(record, dict) for record in data):
            raise MappingInputError("Every mapping record must be an object", received=data)
        return data

    def _source_for_record(self, source: str | None) -> str | None:
        if not source:
            return None
        if "[]" in source:
            return source.split("[]", 1)[1].lstrip(".")
        return source

    def _find_value(self, record: dict[str, Any], rule: MappingRule) -> tuple[Any, str | None]:
        source = self._source_for_record(rule.source)
        candidates = [source] if source else []
        candidates.extend(rule.aliases)
        if rule.source:
            candidates.extend(self.config.aliases.get(rule.source, []))
        for candidate in candidates:
            if not candidate:
                continue
            value = _path_get(record, candidate)
            if value is not _MISSING:
                return value, candidate
        return _MISSING, source

    def _map_record(self, record: dict[str, Any], index: int) -> tuple[dict[str, Any], bool]:
        values = dict(record)
        result: dict[str, Any] = {}
        consumed_roots: set[str] = set()
        review_required = False
        for rule in self.config.mappings:
            if rule.condition and not bool(_safe_expression(rule.condition, values)):
                continue
            if rule.expression:
                value = _safe_expression(rule.expression, values)
                matched_source = None
            else:
                value, matched_source = self._find_value(record, rule)
            if value is _MISSING:
                if rule.has_default:
                    value = deepcopy(rule.default)
                elif rule.required:
                    raise MappingFieldMissing(
                        f'Required field "{rule.source}" not found',
                        field=rule.source,
                        expected=rule.type,
                    )
                else:
                    value = None
            if matched_source:
                consumed_roots.add(matched_source.split(".", 1)[0])
            if (
                isinstance(value, dict)
                and "value" in value
                and set(value) <= {"value", "confidence", "source", "metadata"}
            ):
                confidence = value.get("confidence")
                if (
                    self.config.confidence_threshold is not None
                    and confidence is not None
                    and float(confidence) < self.config.confidence_threshold
                ):
                    review_required = True
                value = value.get("value")
            if value is not None:
                for transform in rule.transform:
                    name, options = _normalize_transform(transform)
                    try:
                        value = _apply_transform(value, name, options)
                    except MappingError as exc:
                        exc.field = exc.field or rule.source
                        raise
                    except Exception as exc:
                        raise MappingTransformationError(
                            f'Transformation failed for field "{rule.source}": {name}',
                            field=rule.source,
                            received=value,
                        ) from exc
                value = _coerce(
                    value,
                    rule.type,
                    allow_coercion=self.config.mode == "lenient" or _has_conversion_transform(rule),
                    field=rule.source or rule.target,
                )
            result[rule.target.upper()] = value
            if rule.source:
                values[rule.source.split(".")[-1]] = value
            values[rule.target] = value
        if self.config.mode == "strict":
            ignored = {"_metadata", "metadata", "source_page", "page"}
            unknown = sorted(set(record) - consumed_roots - ignored)
            if unknown:
                raise MappingSchemaError(
                    f"Unknown fields in strict mapping: {', '.join(unknown)}",
                    received={key: record[key] for key in unknown},
                )
        return result, review_required

    def _deduplicate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        key = self.config.duplicate_key
        policy = self.config.duplicate_policy
        if not key or policy == "allow":
            return records
        ordered: list[dict[str, Any]] = []
        positions: dict[str, int] = {}
        for record in records:
            value = _path_get(record, key)
            if value is _MISSING:
                raise MappingFieldMissing(f'Duplicate key "{key}" not found', field=key)
            marker = json.dumps(value, sort_keys=True, default=str)
            if marker not in positions:
                positions[marker] = len(ordered)
                ordered.append(record)
                continue
            existing_index = positions[marker]
            if policy == "skip":
                continue
            if policy == "replace":
                ordered[existing_index] = record
            elif policy == "merge":
                ordered[existing_index] = {**ordered[existing_index], **record}
            else:
                raise MappingSchemaError(f'Duplicate value for "{key}": {value}', field=key, received=value)
        return ordered

    def _render(self, records: list[dict[str, Any]]) -> dict[str, Any]:
        output_type = self.config.output.type
        if output_type == "object":
            return {"type": "object", "data": records[0] if len(records) == 1 else records}
        if output_type == "cells":
            if len(records) > 1:
                raise MappingOutputError("Cell mapping accepts exactly one input record", received=records)
            return {"type": "cells", "cells": records[0] if records else {}, "sheet": self.config.output.sheet}
        columns = {rule.target.upper(): _column_number(rule.target) for rule in self.config.mappings}
        min_column = (
            _column_number(_CELL_RE.match(self.config.output.start_cell.upper()).group(1))
            if self.config.output.type == "range"
            else 1
        )
        max_column = max(columns.values(), default=min_column)
        if min_column > max_column:
            raise MappingTargetError("start_cell is after all configured target columns")
        rows: list[list[Any]] = []
        if self.config.output.include_headers:
            rows.append(
                [
                    next(
                        (
                            rule.source or rule.target
                            for rule in self.config.mappings
                            if columns[rule.target.upper()] == column
                        ),
                        "",
                    )
                    for column in range(min_column, max_column + 1)
                ]
            )
        for record in records:
            rows.append(
                [
                    next((record[target] for target, number in columns.items() if number == column), None)
                    for column in range(min_column, max_column + 1)
                ]
            )
        result = {"type": output_type, "rows": rows, "sheet": self.config.output.sheet}
        if output_type == "range":
            result["start_cell"] = self.config.output.start_cell.upper()
        elif self.config.output.start_cell.upper() != "A1":
            result["start_cell"] = self.config.output.start_cell.upper()
        return result

    @staticmethod
    def _lineage(record: dict[str, Any], index: int, context: dict[str, Any]) -> dict[str, Any]:
        metadata = record.get("_metadata") or record.get("metadata") or {}
        return {
            "record_index": index,
            "source_file": metadata.get("source_file") or context.get("source_file"),
            "page": record.get("source_page") or record.get("page") or metadata.get("page") or context.get("page"),
            "flow_id": context.get("flow_id"),
            "node_id": context.get("node_id"),
        }


def execute_mapping(
    payload: Any, config: MappingConfig | dict[str, Any], *, context: dict[str, Any] | None = None
) -> dict[str, Any]:
    return MappingEngine(config).execute(payload, context=context)
