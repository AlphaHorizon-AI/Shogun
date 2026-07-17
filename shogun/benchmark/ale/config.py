"""Validated configuration for isolated ALE benchmark runs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, Field, model_validator


@dataclass
class ShogunALEConfig:
    """ALE factory-owned deployer configuration."""

    name: ClassVar[str] = "shogun-afm"
    model: str = "ale_balanced"
    posture: str = "ronin"
    max_runtime_minutes: int = 180


class ALETask(BaseModel):
    task_id: str
    instruction: str = Field(min_length=1)
    task_path: str = ""
    variant_index: int = 0
    expected_outputs: list[str] = Field(default_factory=list)
    actions: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path) -> ALETask:
        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))


class MCPServerConfig(BaseModel):
    transport: Literal["stdio"] = "stdio"
    command: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    cwd: str | None = None
    timeout_seconds: float = Field(default=45.0, gt=0, le=600)


class SandboxConfig(BaseModel):
    sandbox_id: str = "ale-sandbox"
    os: Literal["linux", "windows"] = "linux"
    endpoint: str | None = None
    work_dir: str
    output_dir: str
    desktop_mcp: MCPServerConfig | None = None
    vm_mcp: MCPServerConfig | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_bridges(self):
        if not self.desktop_mcp or not self.vm_mcp:
            raise ValueError("Both desktop_mcp and vm_mcp are required for ALE benchmark runs")
        return self

    @classmethod
    def load(cls, path: str | Path) -> SandboxConfig:
        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))


class ALEBenchmarkConfig(BaseModel):
    enabled: bool = True
    posture: Literal["campaign", "ronin"] = "ronin"
    model_profile: str = "ale_balanced"
    max_runtime_minutes: int = Field(default=180, ge=1, le=1440)
    trajectory_export: bool = True
    artifact_export: bool = True
    redact_secrets: bool = True
    budget_shares: dict[str, float] = Field(
        default_factory=lambda: {"planning": 0.10, "execution": 0.70, "verification": 0.15, "finalization": 0.05}
    )

    @model_validator(mode="after")
    def validate_budget(self):
        if abs(sum(self.budget_shares.values()) - 1.0) > 0.001:
            raise ValueError("Benchmark phase budget shares must total 1.0")
        return self


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
