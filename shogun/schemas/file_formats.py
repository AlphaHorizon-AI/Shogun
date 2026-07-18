"""Request models for the File Format Adapter API."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field, model_validator


class FileReferenceRequest(BaseModel):
    path: str | None = None
    file_id: uuid.UUID | None = None
    source: str = "workspace"
    mime_type: str | None = None

    @model_validator(mode="after")
    def require_reference(self):
        if not self.path and not self.file_id:
            raise ValueError("path or file_id is required")
        return self


class FileQueryRequest(FileReferenceRequest):
    query: str
    limit: int = Field(default=100, ge=1, le=1000)


class FileTransformRequest(FileReferenceRequest):
    target_format: str
    output_filename: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)


class ArchiveExtractRequest(FileReferenceRequest):
    members: list[str] = Field(min_length=1, max_length=1000)
    output_directory: str | None = None
    allow_overwrite: bool = False
    approved: bool = False


class FileIndexRequest(FileReferenceRequest):
    agent_id: uuid.UUID
    title: str | None = None


class FileCompareRequest(BaseModel):
    left_path: str
    right_path: str
