"""Current ALE BaseAgentDeployer contract for the Shogun external harness."""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import ClassVar

from ale_run.base_interface import (
    AgentRunResult,
    BaseAgentDeployer,
    ContentPart,
    Observation,
    ToolCall,
    ToolResult,
    TrajectoryBuilder,
)

from .config import ShogunALEConfig
from .trajectory_mapper import load_native_events


class ShogunALEDeployer(BaseAgentDeployer):
    """Run Shogun outside the sandbox and drive it through ALE's CUA endpoint."""

    default_executor: ClassVar[str] = "local"
    supported_executors: ClassVar[frozenset[str]] = frozenset({"local", "docker"})
    hot_artifacts: ClassVar[tuple[str, ...]] = ("benchmark_output/shogun_events.jsonl", "benchmark_output/status.json")

    @property
    def version(self) -> str | None:
        from shogun import __version__

        return __version__

    async def install(self) -> None:
        from ale_run.agents._bootstrap import ensure_cua_mcp_server_at, ensure_node_npm, ensure_vm_mcp_server

        work_dir = Path(self.executor.work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)
        await ensure_node_npm()
        await ensure_cua_mcp_server_at(str(work_dir / "mcp" / "desktop"))
        await ensure_vm_mcp_server(str(work_dir / "mcp" / "vm"))

    async def launch(self, prompt: str) -> AgentRunResult:
        work_dir = Path(self.executor.work_dir)
        output_dir = work_dir / "benchmark_output"
        output_dir.mkdir(parents=True, exist_ok=True)
        task_path = work_dir / "ale_task.json"
        sandbox_path = work_dir / "ale_sandbox.json"
        run_id = work_dir.name
        cfg: ShogunALEConfig = self.config  # type: ignore[assignment]
        task_path.write_text(
            json.dumps({"task_id": run_id, "instruction": prompt, "task_path": run_id}), encoding="utf-8"
        )
        sandbox = self.executor.sandbox
        node = sandbox.node or "node"
        endpoint_env = {"CUA_SERVER_URL": self.executor.cua_bridge_url()}
        sandbox_path.write_text(
            json.dumps(
                {
                    "sandbox_id": sandbox.id,
                    "os": sandbox.os,
                    "endpoint": sandbox.endpoint,
                    "work_dir": sandbox.task_data_root,
                    "output_dir": sandbox.task_data_root,
                    "desktop_mcp": {
                        "transport": "stdio",
                        "command": node,
                        "args": [str(work_dir / "mcp" / "desktop" / "src" / "index.js")],
                        "env": endpoint_env,
                    },
                    "vm_mcp": {
                        "transport": "stdio",
                        "command": node,
                        "args": [str(work_dir / "mcp" / "vm" / "src" / "index.js")],
                        "env": endpoint_env,
                    },
                    "metadata": {"ale_sandbox_id": sandbox.id},
                }
            ),
            encoding="utf-8",
        )
        command = [
            sys.executable,
            "-m",
            "shogun.benchmark.ale.run",
            "--task-json",
            str(task_path),
            "--sandbox-json",
            str(sandbox_path),
            "--run-id",
            run_id,
            "--output-dir",
            str(output_dir),
            "--model-profile",
            cfg.model,
            "--posture",
            cfg.posture,
            "--max-runtime-minutes",
            str(cfg.max_runtime_minutes),
        ]
        started = time.monotonic()
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await process.communicate()
        except asyncio.CancelledError:
            process.kill()
            await process.wait()
            raise
        (work_dir / "shogun.stdout.log").write_bytes(stdout)
        (work_dir / "shogun.stderr.log").write_bytes(stderr)
        status = "completed" if process.returncode == 0 else "failed"
        return AgentRunResult(
            status=status,
            transcript_path=str(output_dir / "shogun_events.jsonl"),
            stderr_path=str(work_dir / "shogun.stderr.log"),
            pid=process.pid,
            exit_code=process.returncode,
            duration_s=time.monotonic() - started,
            error=None if status == "completed" else stderr.decode(errors="replace")[-2000:],
        )

    @classmethod
    def parse_artifacts(
        cls,
        *,
        work_dir: Path,
        config: ShogunALEConfig,
        run_result: AgentRunResult,
        builder: TrajectoryBuilder,
    ) -> None:
        events = load_native_events(work_dir / "benchmark_output" / "shogun_events.jsonl")
        if not events:
            builder.add_step(
                source="system",
                message="Shogun benchmark trajectory was unavailable",
                extra={"status": run_result.status},
            )
            return
        pending: dict[str, ToolCall] = {}
        for event in events:
            if event.get("type") == "tool_call" and event.get("status") == "started":
                call = ToolCall(name=str(event.get("tool", "unknown")), arguments=dict(event.get("input") or {}))
                pending[str(event.get("tool"))] = call
                builder.add_step(source="agent", tool_calls=[call], extra={"shogun_tool": event.get("shogun_tool")})
            elif event.get("type") == "tool_call" and event.get("status") in {"success", "failed"}:
                call = pending.pop(str(event.get("tool")), None)
                if call:
                    content = [
                        ContentPart(type="text", text=json.dumps(event.get("observation") or event.get("error") or ""))
                    ]
                    builder.add_step(
                        source="environment",
                        observation=Observation(
                            results=[
                                ToolResult(
                                    tool_call_id=call.id, content=content, is_error=event.get("status") == "failed"
                                )
                            ]
                        ),
                    )
            else:
                builder.add_step(source="system", message=str(event.get("type", "event")), extra=event)
        builder.trajectory.extra["shogun_manifest"] = "origin_log/shogun-afm/benchmark_output/run_manifest.json"
