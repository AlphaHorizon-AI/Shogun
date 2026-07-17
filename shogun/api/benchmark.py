"""Benchmark Mode API for headless ALE harness runs and UI visibility."""

from __future__ import annotations

import asyncio
import json
import sys
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from shogun.api.setup import _read_setup, _write_setup
from shogun.benchmark.ale.config import ALETask, SandboxConfig
from shogun.config import PROJECT_ROOT
from shogun.schemas.common import ApiResponse

router = APIRouter(prefix="/benchmark", tags=["Benchmark Mode"])
_processes: dict[str, asyncio.subprocess.Process] = {}


def _config() -> dict[str, Any]:
    return dict(_read_setup().get("benchmark_mode") or {})


def _root() -> Path:
    configured = str(_config().get("output_root") or "./data/benchmarks")
    path = Path(configured)
    return (PROJECT_ROOT / path).resolve() if not path.is_absolute() else path.resolve()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _run_record(path: Path) -> dict[str, Any]:
    status = _read_json(path / "status.json")
    manifest = _read_json(path / "run_manifest.json")
    value = {**manifest, **status}
    value.setdefault("run_id", path.name)
    value["output_dir"] = str(path)
    value["trajectory_exported"] = (path / "trajectory.jsonl").exists()
    value["artifact_count"] = sum(1 for item in (path / "artifacts").rglob("*") if item.is_file()) if (path / "artifacts").exists() else 0
    return value


class BenchmarkRunRequest(BaseModel):
    task_json: str
    sandbox_json: str
    run_id: str | None = None
    posture: str = "ronin"
    model_profile: str = "ale_balanced"
    max_runtime_minutes: int = Field(default=180, ge=1, le=1440)


class BenchmarkConfigUpdate(BaseModel):
    enabled: bool | None = None
    default_posture: str | None = None
    default_model_profile: str | None = None
    max_runtime_minutes: int | None = Field(default=None, ge=1, le=1440)
    trajectory_export: bool | None = None
    artifact_export: bool | None = None
    redact_secrets: bool | None = None


@router.get("/config", response_model=ApiResponse)
async def benchmark_config():
    return ApiResponse(data=_config())


@router.patch("/config", response_model=ApiResponse)
async def update_benchmark_config(body: BenchmarkConfigUpdate):
    setup = _read_setup()
    config = dict(setup.get("benchmark_mode") or {})
    ale = dict((config.get("providers") or {}).get("ale") or {})
    for key, value in body.model_dump(exclude_none=True).items():
        if key == "enabled":
            config["enabled"] = value
        else:
            ale[key] = value
    config["providers"] = {**dict(config.get("providers") or {}), "ale": ale}
    setup["benchmark_mode"] = config
    _write_setup(setup)
    return ApiResponse(data=config)


@router.get("/runs", response_model=ApiResponse)
async def list_benchmark_runs():
    root = _root()
    root.mkdir(parents=True, exist_ok=True)
    runs = sorted((_run_record(path) for path in root.iterdir() if path.is_dir()), key=lambda item: str(item.get("started_at", "")), reverse=True)
    return ApiResponse(data={"runs": runs, "active": list(_processes), "config": _config()})


@router.get("/runs/{run_id}", response_model=ApiResponse)
async def get_benchmark_run(run_id: str):
    path = (_root() / Path(run_id).name).resolve()
    if path.parent != _root() or not path.exists():
        raise HTTPException(status_code=404, detail="Benchmark run not found")
    return ApiResponse(data=_run_record(path))


@router.post("/validate", response_model=ApiResponse)
async def validate_benchmark(body: BenchmarkRunRequest):
    task = ALETask.load(body.task_json)
    sandbox = SandboxConfig.load(body.sandbox_json)
    return ApiResponse(data={"valid": True, "task": task.model_dump(), "sandbox": sandbox.model_dump()})


@router.post("/runs", response_model=ApiResponse)
async def start_benchmark_run(body: BenchmarkRunRequest):
    if not _config().get("enabled", True):
        raise HTTPException(status_code=403, detail="Benchmark Mode is disabled")
    ALETask.load(body.task_json)
    SandboxConfig.load(body.sandbox_json)
    run_id = body.run_id or f"ale_{uuid.uuid4().hex[:12]}"
    output_dir = _root() / Path(run_id).name
    output_dir.mkdir(parents=True, exist_ok=True)
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "shogun.benchmark.ale.run",
        "--task-json",
        str(Path(body.task_json).resolve()),
        "--sandbox-json",
        str(Path(body.sandbox_json).resolve()),
        "--run-id",
        run_id,
        "--output-dir",
        str(output_dir),
        "--model-profile",
        body.model_profile,
        "--posture",
        body.posture,
        "--max-runtime-minutes",
        str(body.max_runtime_minutes),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    _processes[run_id] = process

    async def reap() -> None:
        await process.wait()
        _processes.pop(run_id, None)

    asyncio.create_task(reap())
    return ApiResponse(data={"run_id": run_id, "pid": process.pid, "output_dir": str(output_dir)})


@router.post("/runs/{run_id}/cancel", response_model=ApiResponse)
async def cancel_benchmark_run(run_id: str):
    process = _processes.get(run_id)
    if not process or process.returncode is not None:
        raise HTTPException(status_code=409, detail="Benchmark run is not active")
    process.terminate()
    return ApiResponse(data={"run_id": run_id, "status": "cancelling"})
