"""CLI commands for the Shogun ALE benchmark adapter."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from .config import ALETask, SandboxConfig
from .run import main as run_main
from .trajectory_mapper import load_native_events


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="shogun benchmark ale")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    for name, required, default in (
        ("task-json", True, None),
        ("sandbox-json", True, None),
        ("run-id", True, None),
        ("output-dir", True, None),
        ("model-profile", False, "ale_balanced"),
        ("posture", False, "ronin"),
        ("max-runtime-minutes", False, "180"),
    ):
        run.add_argument(f"--{name}", required=required, default=default)
    validate = sub.add_parser("validate-config")
    validate.add_argument("--task-json")
    validate.add_argument("--sandbox-json", required=True)
    dry = sub.add_parser("dry-run")
    dry.add_argument("--sandbox-json", required=True)
    export = sub.add_parser("export-trajectory")
    export.add_argument("--run-dir", required=True)
    package = sub.add_parser("package-artifacts")
    package.add_argument("--run-dir", required=True)
    args = parser.parse_args(argv)
    if args.command == "run":
        values = []
        for key, value in vars(args).items():
            if key != "command" and value is not None:
                values.extend([f"--{key.replace('_', '-')}", str(value)])
        return run_main(values)
    if args.command in {"validate-config", "dry-run"}:
        sandbox = SandboxConfig.load(args.sandbox_json)
        task = ALETask.load(args.task_json) if getattr(args, "task_json", None) else None
        print(
            json.dumps(
                {"valid": True, "sandbox": sandbox.model_dump(), "task": task.model_dump() if task else None}, indent=2
            )
        )
        return 0
    run_dir = Path(args.run_dir).resolve()
    if args.command == "export-trajectory":
        events = load_native_events(run_dir / "shogun_events.jsonl")
        target = run_dir / "trajectory.export.json"
        target.write_text(json.dumps(events, indent=2), encoding="utf-8")
        print(target)
        return 0
    archive = shutil.make_archive(str(run_dir / "shogun-ale-artifacts"), "zip", run_dir)
    print(archive)
    return 0
