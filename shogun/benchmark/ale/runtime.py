"""Headless Shogun harness lifecycle for ALE benchmark units."""

from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from shogun.benchmark.ale.artifact_exporter import ALEArtifactExporter
from shogun.benchmark.ale.config import ALEBenchmarkConfig, ALETask, SandboxConfig, write_json
from shogun.benchmark.ale.stack_template import as_stack_plan
from shogun.benchmark.ale.trajectory_mapper import ALETrajectoryMapper
from shogun.benchmark.ale.verification import ALEInstructionVerifier
from shogun.integrations.cua import CUAMCPAdapter
from shogun.integrations.mcp import MCPBridgeClient, MCPConnectionConfig


class ALEBenchmarkRunner:
    def __init__(
        self,
        *,
        task: ALETask,
        sandbox: SandboxConfig,
        output_dir: Path,
        run_id: str,
        config: ALEBenchmarkConfig,
    ):
        self.task = task
        self.sandbox = sandbox
        self.output_dir = output_dir.resolve()
        self.run_id = run_id
        self.config = config
        self.started = time.monotonic()
        self.started_at = datetime.now(timezone.utc)
        self.trajectory = ALETrajectoryMapper(self.output_dir, run_id, task.task_id)
        self.exporter = ALEArtifactExporter(self.output_dir)
        self.exported_files: list[Path] = []
        self.stack_run_id: uuid.UUID | None = None

    async def run(self) -> dict[str, Any]:
        import shogun.db.models  # noqa: F401
        from shogun.db.base import Base
        from shogun.db.engine import async_session_factory, engine
        from shogun.services.stack_orchestrator import StackOrchestratorService

        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        desktop = MCPBridgeClient(MCPConnectionConfig.from_dict(self.sandbox.desktop_mcp.model_dump()))
        vm = MCPBridgeClient(MCPConnectionConfig.from_dict(self.sandbox.vm_mcp.model_dump()))
        adapter = CUAMCPAdapter(
            desktop=desktop,
            vm=vm,
            run_id=self.run_id,
            posture=self.config.posture,
            event_sink=self.trajectory.emit,
        )
        status = "failed"
        failure_reason: str | None = None
        verification: dict[str, Any] = {"status": "not_run", "checks": []}
        await self.trajectory.emit({"type": "task_started", "instruction": self.task.instruction})
        self._write_status("starting", 0, "Parse Task")
        async with async_session_factory() as session:
            service = StackOrchestratorService(session)
            stack = await service.create_external_run(
                objective=self.task.instruction,
                plan=as_stack_plan(),
                posture=self.config.posture,
                model_profile=self.config.model_profile,
                max_runtime_minutes=self.config.max_runtime_minutes,
                allowed_tools=["cua", "sandbox"],
                metadata={"benchmark": "ale", "run_id": self.run_id, "task_id": self.task.task_id},
            )
            self.stack_run_id = stack.id
            await service.complete_external_step(
                stack.id, 1, output={"task_id": self.task.task_id, "expected_outputs": self.task.expected_outputs}
            )
        try:
            tools = await adapter.connect()
            screenshot = await self.exporter.screenshot(adapter, "initial")
            await self.trajectory.emit({"type": "screenshot", "path": str(screenshot), "status": "success"})
            inspection = await adapter.call(
                "sandbox.shell.run", {"command": self._inspection_command(), "timeout_seconds": 30}
            )
            await self._phase(2, {"tools": tools, "inspection": inspection.structured_content}, screenshot)
            await self._phase(
                3, {"os": self.sandbox.os, "work_dir": self.sandbox.work_dir, "output_dir": self.sandbox.output_dir}
            )

            actions = self._plan_actions()
            await self._phase(4, {"actions": actions})
            for action in actions:
                self._assert_budget()
                await adapter.call(str(action["tool"]), dict(action.get("arguments") or {}))
            await self._phase(5, {"executed_actions": len(actions)})

            final_shot = await self.exporter.screenshot(adapter, "final")
            await self._phase(6, {"screenshot": str(final_shot)}, final_shot)
            for remote_path in self._remote_outputs():
                self.exported_files.append(await self.exporter.download(adapter, remote_path))
            verification = ALEInstructionVerifier.verify(self.task, self.exported_files)
            await self._phase(7, verification, verification_status=verification["status"])
            await self._phase(
                8, {"repair_needed": verification["retry_recommended"]}, verification_status=verification["status"]
            )
            await self._phase(9, {"artifacts": [self.exporter.describe(path) for path in self.exported_files]})
            answer = self._final_answer(verification)
            final_answer_path = self.exporter.write_final_answer(answer)
            await self._phase(10, {"final_answer": str(final_answer_path)}, final_answer_path)
            status = "completed" if verification["status"] == "passed" else "failed"
        except asyncio.CancelledError:
            status = "timeout"
            failure_reason = "ALE cancelled the harness after the unit wall-time budget expired"
            raise
        except Exception as exc:
            failure_reason = f"{type(exc).__name__}: {exc}"
            await self.trajectory.emit({"type": "task_failed", "status": "failed", "error": failure_reason})
        finally:
            await adapter.close()
            await self.trajectory.emit(
                {
                    "type": "task_completed" if status == "completed" else "task_failed",
                    "status": status,
                    "error": failure_reason,
                }
            )
            self.trajectory.export(status)
            if self.stack_run_id:
                try:
                    await self._phase(
                        11, {"trajectory": str(self.trajectory.path)}, self.trajectory.path, allow_failed=True
                    )
                except Exception:
                    pass
                async with async_session_factory() as session:
                    await StackOrchestratorService(session).finalize_external_run(
                        self.stack_run_id,
                        status="completed" if status == "completed" else "failed",
                        summary={
                            "benchmark_status": status,
                            "verification": verification,
                            "failure_reason": failure_reason,
                        },
                    )
            manifest = self._manifest(status, verification, failure_reason)
            self.exporter.manifest(manifest)
            self._write_status(status, 11, "Finished", manifest)
            await engine.dispose()
        return manifest

    async def _phase(
        self,
        sequence: int,
        output: dict[str, Any],
        artifact: Path | None = None,
        *,
        verification_status: str = "passed",
        allow_failed: bool = False,
    ) -> None:
        from shogun.db.engine import async_session_factory
        from shogun.services.stack_orchestrator import StackOrchestratorService

        self._write_status("running", sequence, as_stack_plan()[sequence - 1]["name"])
        await self.trajectory.emit({"type": "checkpoint", "phase": sequence, "output": output})
        if self.stack_run_id and (allow_failed or verification_status == "passed"):
            async with async_session_factory() as session:
                await StackOrchestratorService(session).complete_external_step(
                    self.stack_run_id,
                    sequence,
                    output=output,
                    verification_status=verification_status,
                    artifact_path=str(artifact) if artifact else None,
                )

    def _plan_actions(self) -> list[dict[str, Any]]:
        if self.task.actions:
            return self.task.actions
        instruction = self.task.instruction.lower()
        if "hello.txt" in instruction and "hello from shogun" in instruction:
            remote = self._remote_outputs()[0]
            return [{"tool": "sandbox.file.write", "arguments": {"path": remote, "content": "Hello from Shogun"}}]
        raise RuntimeError(
            "Task requires a model-generated action plan; provide task actions "
            "or run through a configured Shogun model profile"
        )

    def _remote_outputs(self) -> list[str]:
        outputs = self.task.expected_outputs or ["hello.txt"]
        path_cls = PureWindowsPath if self.sandbox.os == "windows" else PurePosixPath
        return [str(path_cls(self.sandbox.output_dir) / path_cls(item).name) for item in outputs]

    def _inspection_command(self) -> str:
        if self.sandbox.os == "windows":
            return (
                'powershell -NoProfile -Command "Get-Location; '
                'Get-ChildItem -Force | Select-Object -First 50 Name,Length"'
            )
        return "pwd && find . -maxdepth 2 -type f | head -50"

    def _assert_budget(self) -> None:
        if time.monotonic() - self.started >= self.config.max_runtime_minutes * 60:
            raise TimeoutError("Internal benchmark runtime budget exceeded")

    def _final_answer(self, verification: dict[str, Any]) -> str:
        files = "\n".join(f"- `{path.name}`" for path in self.exported_files) or "- No file artifacts"
        return (
            "# Shogun ALE Result\n\n"
            f"Task `{self.task.task_id}` finished with verification "
            f"**{verification['status']}**.\n\nArtifacts:\n{files}"
        )

    def _manifest(self, status: str, verification: dict[str, Any], failure_reason: str | None) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "benchmark": "ale",
            "agent": "shogun-afm",
            "run_id": self.run_id,
            "task_id": self.task.task_id,
            "posture": self.config.posture,
            "model_profile": self.config.model_profile,
            "stack_run_id": str(self.stack_run_id) if self.stack_run_id else None,
            "started_at": self.started_at.isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "final_answer_path": "final_answer.md",
            "trajectory_path": "trajectory.jsonl",
            "artifacts_dir": "artifacts/",
            "events_path": "shogun_events.jsonl",
            "verification_status": verification.get("status"),
            "failure_reason": failure_reason,
        }

    def _write_status(self, status: str, phase: int, current_step: str, extra: dict[str, Any] | None = None) -> None:
        elapsed = time.monotonic() - self.started
        write_json(
            self.output_dir / "status.json",
            {
                "run_id": self.run_id,
                "task_id": self.task.task_id,
                "status": status,
                "posture": self.config.posture,
                "model_profile": self.config.model_profile,
                "current_stack_step": current_step,
                "phase": phase,
                "elapsed_seconds": round(elapsed, 2),
                "remaining_budget_seconds": max(0, round(self.config.max_runtime_minutes * 60 - elapsed, 2)),
                "stack_run_id": str(self.stack_run_id) if self.stack_run_id else None,
                **(extra or {}),
            },
        )
