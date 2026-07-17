"""Map Shogun benchmark events to native JSONL and ALE-v1.0 ATIF steps."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .redaction import redact


class ALETrajectoryMapper:
    def __init__(self, output_dir: Path, run_id: str, task_id: str):
        self.output_dir = output_dir
        self.run_id = run_id
        self.task_id = task_id
        self.events: list[dict[str, Any]] = []
        self.path = output_dir / "trajectory.jsonl"
        self.native_path = output_dir / "shogun_events.jsonl"

    async def emit(self, event: dict[str, Any]) -> None:
        normalized = redact(
            {
                "run_id": self.run_id,
                "task_id": self.task_id,
                "timestamp": event.get("timestamp") or datetime.now(timezone.utc).isoformat(),
                **event,
            }
        )
        self.events.append(normalized)
        self._append(self.native_path, normalized)

    def export(self, final_status: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for index, event in enumerate(self.events, start=1):
                item = {
                    "schema_version": "ALE-v1.0",
                    "step_id": index,
                    "timestamp": event["timestamp"],
                    "source": self._source(event.get("type", "system")),
                    "event": event,
                    "final_status": final_status if index == len(self.events) else None,
                }
                handle.write(json.dumps(item, ensure_ascii=False, default=str) + "\n")

    @staticmethod
    def _source(event_type: str) -> str:
        if event_type == "tool_call":
            return "agent"
        if event_type in {"observation", "screenshot", "file_artifact"}:
            return "environment"
        return "system"

    @staticmethod
    def _append(path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(value, ensure_ascii=False, default=str) + "\n")


def load_native_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events
