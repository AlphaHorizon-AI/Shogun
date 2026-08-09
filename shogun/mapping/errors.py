"""Structured Mapping / RPA errors.

Mapping failures are intentionally data-oriented: callers receive the field,
record and source context needed to diagnose a flow without exposing unrelated
payload data.
"""

from __future__ import annotations

from typing import Any


class MappingError(ValueError):
    code = "MAPPING_FAILED"

    def __init__(
        self,
        message: str,
        *,
        field: str | None = None,
        record_index: int | None = None,
        expected: str | None = None,
        received: Any = None,
        source: str | None = None,
        document: str | None = None,
        page: int | None = None,
    ) -> None:
        super().__init__(message)
        self.field = field
        self.record_index = record_index
        self.expected = expected
        self.received = received
        self.source = source
        self.document = document
        self.page = page

    def as_dict(self) -> dict[str, Any]:
        details = {
            "code": self.code,
            "error_type": type(self).__name__,
            "message": str(self),
            "field": self.field,
            "record_index": self.record_index,
            "expected": self.expected,
            "received": self._safe_received(),
            "source": self.source,
            "document": self.document,
            "page": self.page,
        }
        return {key: value for key, value in details.items() if value is not None}

    def _safe_received(self) -> Any:
        value = self.received
        if isinstance(value, (str, int, float, bool)) or value is None:
            text = value if not isinstance(value, str) else value[:200]
            return text
        if isinstance(value, list):
            return {"type": "array", "length": len(value)}
        if isinstance(value, dict):
            return {"type": "object", "fields": sorted(str(key) for key in value)[:20]}
        return type(value).__name__


class MappingInputError(MappingError):
    code = "MAPPING_INPUT_ERROR"


class MappingSchemaError(MappingError):
    code = "MAPPING_SCHEMA_ERROR"


class MappingFieldMissing(MappingError):  # noqa: N818 - public error name from the build contract
    code = "VALIDATION_FAILED"


class MappingTypeError(MappingError):
    code = "VALIDATION_FAILED"


class MappingTransformationError(MappingError):
    code = "MAPPING_TRANSFORMATION_ERROR"


class MappingTargetError(MappingError):
    code = "MAPPING_TARGET_ERROR"


class MappingOutputError(MappingError):
    code = "MAPPING_OUTPUT_ERROR"
