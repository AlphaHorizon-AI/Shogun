"""Module entry point: python -m shogun.benchmark.ale.run."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(prog="shogun benchmark ale run")
    value.add_argument("--task-json", required=True)
    value.add_argument("--sandbox-json", required=True)
    value.add_argument("--run-id", required=True)
    value.add_argument("--output-dir", required=True)
    value.add_argument("--model-profile", default="ale_balanced")
    value.add_argument("--posture", choices=["campaign", "ronin"], default="ronin")
    value.add_argument("--max-runtime-minutes", type=int, default=180)
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    state_dir = output_dir / ".shogun_state"
    state_dir.mkdir(exist_ok=True)
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{(state_dir / 'benchmark.db').as_posix()}"
    os.environ["QDRANT_PATH"] = str(state_dir / "qdrant")
    os.environ["LOG_PATH"] = str(output_dir / "logs")
    os.environ["CONFIG_PATH"] = str(state_dir / "config")
    from .config import ALEBenchmarkConfig, ALETask, SandboxConfig
    from .runtime import ALEBenchmarkRunner

    config = ALEBenchmarkConfig(
        posture=args.posture,
        model_profile=args.model_profile,
        max_runtime_minutes=args.max_runtime_minutes,
    )
    runner = ALEBenchmarkRunner(
        task=ALETask.load(args.task_json),
        sandbox=SandboxConfig.load(args.sandbox_json),
        output_dir=output_dir,
        run_id=args.run_id,
        config=config,
    )
    try:
        manifest = asyncio.run(runner.run())
    except KeyboardInterrupt:
        return 130
    print(json.dumps(manifest, indent=2))
    return 0 if manifest["status"] == "completed" else 1


if __name__ == "__main__":
    sys.exit(main())
