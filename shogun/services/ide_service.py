"""Governed IDE Mode runtime and local VS Code adapter."""

from __future__ import annotations

import asyncio
import difflib
import fnmatch
import hashlib
import json
import os
import secrets
import shlex
import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException, WebSocket

from shogun.services.event_logger import EventLogger


CAMPAIGN_COMMANDS = {"pytest", "python", "npm", "npx", "pnpm", "yarn", "ruff", "mypy", "tsc", "cargo", "go"}
PROTECTED = {".env", ".env.*", "*.pem", "*.key", "id_rsa*", "credentials*", "secrets.*"}
DENIED_PARTS = {".ssh", ".aws", ".azure", ".gnupg", ".kube"}


@dataclass
class Pairing:
    token_hash: str
    expires_at: datetime
    used: bool = False


@dataclass
class WorkspaceState:
    id: str
    name: str
    root: Path
    approved: bool = False
    provider: str = "vscode"
    metadata: dict[str, Any] = field(default_factory=dict)
    snapshots: dict[str, dict[str, str | None]] = field(default_factory=dict)
    recent_changes: list[dict[str, Any]] = field(default_factory=list)


class IDEService:
    """Structured IDE capability layer. Authorization always happens server-side."""

    def __init__(self) -> None:
        self.pairings: dict[str, Pairing] = {}
        self.workspaces: dict[str, WorkspaceState] = {}
        self.connections: dict[str, WebSocket] = {}
        self.pending: dict[str, asyncio.Future] = {}
        self.task_runs: dict[str, dict[str, Any]] = {}
        self.active_processes: dict[str, asyncio.subprocess.Process] = {}
        self.last_action: dict[str, Any] | None = None

    async def posture(self) -> dict[str, Any]:
        from shogun.api.security import _get_agent_posture
        return await _get_agent_posture()

    async def permission_config(self) -> dict[str, Any]:
        """Resolve the explicit Shogun IDE permission block; missing means denied."""
        from sqlalchemy import select
        from shogun.db.engine import async_session_factory
        from shogun.db.models.agent import Agent
        from shogun.db.models.security_policy import SecurityPolicy
        async with async_session_factory() as session:
            result = await session.execute(select(Agent).where(Agent.agent_type == "shogun", Agent.is_primary == True, Agent.is_deleted == False).limit(1))
            agent = result.scalar_one_or_none()
            if not agent: return {}
            permissions = (agent.bushido_settings or {}).get("custom_permissions")
            if permissions is None and agent.security_policy_id:
                policy = await session.get(SecurityPolicy, agent.security_policy_id)
                permissions = policy.permissions if policy else None
            return dict((permissions or {}).get("ide_mode", {}))

    async def gate(self, action: str, *, workspace_id: str | None = None, path: str | None = None,
                   command: str | None = None, approval: bool = False) -> tuple[dict[str, Any], WorkspaceState | None]:
        posture = await self.posture()
        tier = str(posture.get("active_tier", "tactical")).lower()
        if tier not in {"campaign", "ronin"}:
            raise HTTPException(403, "IDE Mode is unavailable below Campaign posture.")
        if not posture.get("ide_enabled", False):
            raise HTTPException(403, "IDE Mode is disabled. Enable it explicitly in Shogun Permissions.")
        if posture.get("kill_switch_active", False):
            raise HTTPException(423, "The global kill switch is active.")
        permission = await self.permission_config()
        if not permission.get("enabled", False):
            raise HTTPException(403, "IDE Mode permission is disabled in the Shogun profile.")
        permission_map = {
            "file.read": "file_read", "workspace.list": "file_read", "workspace.list_files": "file_read",
            "file.search": "file_search", "file.write": "file_patch", "file.delete": "file_delete",
            "memory.search": "file_read", "memory.store": "file_patch", "memory.reinforce": "file_patch",
            "task.list": "diagnostics", "diagnostics.get": "diagnostics", "terminal.run": "terminal_approved_only",
            "git.status": "git_status", "git.diff": "git_diff", "git.create-branch": "git_branch_create", "git.commit": "git_commit",
        }
        required = permission_map.get(action)
        if required and not permission.get(required, False):
            raise HTTPException(403, f"IDE permission '{required}' is disabled.")
        workspace = None
        if workspace_id:
            workspace = self.workspaces.get(workspace_id)
            if not workspace or not workspace.approved:
                raise HTTPException(403, "The requested VS Code workspace is not approved.")
        if workspace and path:
            self.resolve_path(workspace, path, action, approval)
        if command:
            executable = Path(shlex.split(command, posix=os.name != "nt")[0]).name.lower()
            if tier == "campaign" and executable not in CAMPAIGN_COMMANDS:
                raise HTTPException(403, f"Command '{executable}' is not allowlisted in Campaign posture.")
            if any(part in command.lower() for part in ("git push", "--force", "rm -rf", "format ", "shutdown")) and not approval:
                raise HTTPException(403, "This high-impact command requires explicit approval.")
        return posture, workspace

    def resolve_path(self, workspace: WorkspaceState, relative: str, action: str = "read", approval: bool = False) -> Path:
        candidate = (workspace.root / relative).resolve(strict=False)
        root = workspace.root.resolve(strict=True)
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise HTTPException(403, "Path escapes the approved workspace boundary.") from exc
        relative_parts = {part.lower() for part in candidate.relative_to(root).parts}
        if relative_parts & DENIED_PARTS:
            raise HTTPException(403, "Credential directories are protected from IDE Mode.")
        if any(fnmatch.fnmatch(candidate.name.lower(), item) for item in PROTECTED) and not approval:
            raise HTTPException(403, "Protected files require explicit approval and are never added to model context automatically.")
        if candidate.exists() and candidate.is_symlink():
            resolved = candidate.resolve(strict=True)
            try:
                resolved.relative_to(root)
            except ValueError as exc:
                raise HTTPException(403, "Symlink escape blocked.") from exc
        return candidate

    async def event(self, event_type: str, action: str, **detail: Any) -> str:
        self.last_action = {"type": event_type, "action": action, "at": datetime.now(timezone.utc).isoformat(), **detail}
        return await EventLogger.emit(category="ide", event_type=event_type, action=action,
                                      risk_score=str(detail.pop("risk", "low")), detail=detail)

    async def enable(self, confirmed: bool, remember: bool = False) -> dict[str, Any]:
        posture = await self.posture()
        if posture.get("active_tier") not in {"campaign", "ronin"}:
            raise HTTPException(403, "Switch to Campaign or Ronin before enabling IDE Mode.")
        if not confirmed:
            raise HTTPException(400, "Explicit confirmation is required.")
        if not (await self.permission_config()).get("enabled", False):
            raise HTTPException(403, "Enable the IDE Mode permission in Shogun Profile → Permissions first.")
        posture["ide_enabled"] = True
        posture["ide_remember_workspace"] = bool(remember)
        from shogun.api.security import _save_agent_posture
        await _save_agent_posture(posture)
        await self.event("ide.mode.enabled", "IDE Mode enabled", posture=posture["active_tier"], remembered=remember)
        return await self.status()

    async def disable(self) -> dict[str, Any]:
        posture = await self.posture()
        posture["ide_enabled"] = False
        from shogun.api.security import _save_agent_posture
        await _save_agent_posture(posture)
        for process in list(self.active_processes.values()):
            if process.returncode is None:
                process.kill()
        self.active_processes.clear()
        for ws in list(self.connections.values()):
            await ws.close(code=4001, reason="IDE Mode disabled")
        self.connections.clear()
        self.pairings.clear()
        await self.event("ide.mode.disabled", "IDE Mode disabled and bridge sessions revoked")
        return await self.status()

    async def status(self) -> dict[str, Any]:
        posture = await self.posture()
        return {
            "enabled": bool(posture.get("ide_enabled", False)), "posture": posture.get("active_tier"),
            "available": posture.get("active_tier") in {"campaign", "ronin"}, "provider": "vscode",
            "connected_instances": len(self.connections), "approved_workspaces": sum(w.approved for w in self.workspaces.values()),
            "last_action": self.last_action,
            "capabilities": {"workspace_tree": True, "file_read": True, "file_search": True, "file_patch": True,
                "file_create": True, "file_delete": True, "active_editor": True, "selection": True,
                "diagnostics": True, "tasks": True, "terminal": True, "git_status": True, "git_diff": True,
                "git_commit": posture.get("active_tier") == "ronin", "git_push": False},
        }

    async def create_pairing(self) -> dict[str, Any]:
        await self.gate("pairing.create")
        token = f"SHG-{secrets.token_urlsafe(18)}"
        pairing_id = str(uuid.uuid4())
        expires = datetime.now(timezone.utc) + timedelta(minutes=10)
        self.pairings[pairing_id] = Pairing(hashlib.sha256(token.encode()).hexdigest(), expires)
        await self.event("ide.pairing.created", "One-time VS Code pairing created", pairing_id=pairing_id, expires_at=expires.isoformat())
        return {"pairing_id": pairing_id, "token": token, "expires_at": expires.isoformat(), "bridge_url": "ws://127.0.0.1:8000/api/v1/ide/bridge"}

    async def confirm_pairing(self, token: str) -> str:
        digest = hashlib.sha256(token.encode()).hexdigest()
        pairing = next((p for p in self.pairings.values() if secrets.compare_digest(p.token_hash, digest)), None)
        if not pairing or pairing.used or pairing.expires_at < datetime.now(timezone.utc):
            raise HTTPException(401, "Pairing token is invalid, expired, or already used.")
        pairing.used = True
        session_id = str(uuid.uuid4())
        await self.event("ide.pairing.confirmed", "VS Code bridge paired", session_id=session_id)
        return session_id

    async def register_workspace(self, payload: dict[str, Any]) -> dict[str, Any]:
        await self.gate("workspace.register")
        root = Path(str(payload.get("workspace_root", ""))).expanduser().resolve(strict=True)
        if not root.is_dir():
            raise HTTPException(400, "Workspace root must be an existing directory.")
        workspace_id = str(payload.get("workspace_id") or uuid.uuid4())
        state = WorkspaceState(workspace_id, str(payload.get("workspace_name") or root.name), root,
                               metadata={k: v for k, v in payload.items() if k not in {"workspace_root", "workspace_name"}})
        self.workspaces[workspace_id] = state
        await self.event("ide.workspace.registered", f"VS Code workspace registered: {state.name}", workspace_id=workspace_id, root_path=str(root))
        return self.public_workspace(state)

    async def request_bridge(self, request_type: str, payload: dict[str, Any] | None = None, timeout: int = 20) -> Any:
        await self.gate(request_type)
        if not self.connections:
            raise HTTPException(503, "No paired VS Code instance is connected.")
        session_id, socket = next(iter(self.connections.items()))
        request_id = str(uuid.uuid4())
        future = asyncio.get_running_loop().create_future()
        self.pending[request_id] = future
        await socket.send_json({"type": "request", "request_id": request_id, "session_id": session_id,
                                "timestamp": datetime.now(timezone.utc).isoformat(), "action": request_type,
                                "payload": payload or {}})
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError as exc:
            raise HTTPException(504, "VS Code Adapter request timed out.") from exc
        finally:
            self.pending.pop(request_id, None)

    def public_workspace(self, workspace: WorkspaceState) -> dict[str, Any]:
        return {"id": workspace.id, "name": workspace.name, "root_path": str(workspace.root),
                "approved": workspace.approved, "provider": workspace.provider, "metadata": workspace.metadata,
                "recent_changes": workspace.recent_changes[-20:]}

    async def snapshot(self, workspace: WorkspaceState, paths: list[str]) -> str:
        snapshot_id = str(uuid.uuid4())
        snapshot: dict[str, str | None] = {}
        for rel in paths:
            target = self.resolve_path(workspace, rel, "snapshot", True)
            snapshot[rel] = target.read_text(encoding="utf-8") if target.exists() and target.is_file() else None
        workspace.snapshots[snapshot_id] = snapshot
        await self.event("ide.snapshot.created", "IDE restore point created", workspace_id=workspace.id, snapshot_id=snapshot_id, paths=paths)
        return snapshot_id

    async def rollback(self, workspace_id: str, snapshot_id: str) -> dict[str, Any]:
        _, workspace = await self.gate("rollback", workspace_id=workspace_id)
        snapshot = workspace.snapshots.get(snapshot_id) if workspace else None
        if snapshot is None:
            raise HTTPException(404, "Snapshot not found.")
        for rel, content in snapshot.items():
            target = self.resolve_path(workspace, rel, "rollback", True)
            if content is None:
                if target.exists(): target.unlink()
            else:
                target.parent.mkdir(parents=True, exist_ok=True); target.write_text(content, encoding="utf-8")
        await self.event("ide.rollback.executed", "IDE snapshot restored", workspace_id=workspace_id, snapshot_id=snapshot_id)
        return {"snapshot_id": snapshot_id, "restored": list(snapshot)}

    async def read_file(self, workspace_id: str, path: str, approval: bool = False) -> dict[str, Any]:
        _, workspace = await self.gate("file.read", workspace_id=workspace_id, path=path, approval=approval)
        target = self.resolve_path(workspace, path, "read", approval)
        if not target.is_file(): raise HTTPException(404, "File not found.")
        text = target.read_text(encoding="utf-8", errors="replace")
        await self.event("ide.file.read", f"Read file: {path}", workspace_id=workspace_id, target_path=path)
        return {"path": path, "content": text, "size": target.stat().st_size, "sha256": hashlib.sha256(text.encode()).hexdigest()}

    async def list_files(self, workspace_id: str, pattern: str = "*") -> list[str]:
        _, workspace = await self.gate("workspace.list", workspace_id=workspace_id)
        files = []
        for item in workspace.root.rglob(pattern):
            if item.is_file() and not ({p.lower() for p in item.relative_to(workspace.root).parts} & DENIED_PARTS):
                files.append(item.relative_to(workspace.root).as_posix())
            if len(files) >= 5000: break
        await self.event("ide.workspace.tree_loaded", f"Repository tree loaded: {len(files)} files", workspace_id=workspace_id)
        return files

    async def search(self, workspace_id: str, query: str, glob: str = "*") -> list[dict[str, Any]]:
        files = await self.list_files(workspace_id, glob)
        workspace = self.workspaces[workspace_id]; hits = []
        for rel in files:
            try:
                for line_no, line in enumerate(self.resolve_path(workspace, rel).read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                    if query.lower() in line.lower(): hits.append({"path": rel, "line": line_no, "text": line[:500]})
                    if len(hits) >= 500: return hits
            except OSError: continue
        await self.event("ide.file.search", f"Searched workspace for: {query}", workspace_id=workspace_id, matches=len(hits))
        return hits

    async def search_programming_memory(
        self, workspace_id: str, query: str, limit: int = 8, include_global: bool = False
    ) -> list[dict[str, Any]]:
        _, workspace = await self.gate("memory.search", workspace_id=workspace_id)
        from shogun.db.engine import async_session_factory
        from shogun.services.programming_memory import ProgrammingMemoryService

        async with async_session_factory() as session:
            service = ProgrammingMemoryService(session)
            results = await service.search(
                workspace_key=service.workspace_key(workspace.root),
                query=query,
                limit=limit,
                include_global=include_global,
            )
            await session.commit()
        await self.event(
            "ide.memory.searched",
            f"Programming memory searched: {query[:120]}",
            workspace_id=workspace_id,
            matches=len(results),
        )
        return results

    async def remember_programming_solution(self, workspace_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        _, workspace = await self.gate("memory.store", workspace_id=workspace_id)
        from sqlalchemy import select

        from shogun.db.engine import async_session_factory
        from shogun.db.models.agent import Agent
        from shogun.services.programming_memory import ProgrammingMemoryService

        async with async_session_factory() as session:
            agent_id = await session.scalar(
                select(Agent.id).where(
                    Agent.agent_type == "shogun",
                    Agent.is_primary.is_(True),
                    Agent.is_deleted.is_(False),
                ).limit(1)
            )
            if not agent_id:
                raise HTTPException(404, "Primary Shogun agent not found.")
            service = ProgrammingMemoryService(session)
            record, created = await service.remember(
                agent_id=agent_id,
                workspace_key=service.workspace_key(workspace.root),
                workspace_name=workspace.name,
                title=str(payload.get("title") or "Programming solution"),
                problem=str(payload.get("problem") or ""),
                solution=str(payload.get("solution") or ""),
                kind=str(payload.get("kind") or "solution"),
                evidence=payload.get("evidence"),
                validation_status=str(payload.get("validation_status") or "unverified"),
                confidence_score=float(payload.get("confidence_score", 0.7)),
                languages=list(payload.get("languages") or []),
                files=list(payload.get("files") or []),
                source_urls=list(payload.get("source_urls") or []),
                tags=list(payload.get("tags") or []),
            )
            await session.commit()
            result = service.serialize(record)
        await self.event(
            "ide.memory.stored",
            f"Programming memory {'stored' if created else 'reinforced'}: {result['title']}",
            workspace_id=workspace_id,
            programming_memory_id=result["id"],
            validation_status=result["validation_status"],
        )
        return {**result, "created": created}

    async def reinforce_programming_memory(
        self, workspace_id: str, memory_id: str, successful: bool = True
    ) -> dict[str, Any]:
        _, workspace = await self.gate("memory.reinforce", workspace_id=workspace_id)
        from shogun.db.engine import async_session_factory
        from shogun.services.programming_memory import ProgrammingMemoryService

        async with async_session_factory() as session:
            service = ProgrammingMemoryService(session)
            record = await service.reinforce(
                uuid.UUID(memory_id),
                successful=successful,
                workspace_key=service.workspace_key(workspace.root),
            )
            if not record:
                raise HTTPException(404, "Programming memory not found.")
            await session.commit()
            result = service.serialize(record)
        return result

    async def write(self, workspace_id: str, path: str, content: str, *, approval: bool = False, delete: bool = False) -> dict[str, Any]:
        action = "file.delete" if delete else "file.write"
        posture, workspace = await self.gate(action, workspace_id=workspace_id, path=path, approval=approval)
        if delete and posture.get("active_tier") == "campaign" and not approval:
            raise HTTPException(403, "File deletion requires approval in Campaign posture.")
        target = self.resolve_path(workspace, path, action, approval)
        snapshot_id = await self.snapshot(workspace, [path])
        before = target.read_text(encoding="utf-8", errors="replace") if target.exists() and target.is_file() else ""
        if delete:
            if not target.is_file(): raise HTTPException(404, "File not found.")
            target.unlink()
        else:
            target.parent.mkdir(parents=True, exist_ok=True); target.write_text(content, encoding="utf-8")
        diff = "\n".join(difflib.unified_diff(before.splitlines(), ("" if delete else content).splitlines(), fromfile=f"a/{path}", tofile=f"b/{path}", lineterm=""))
        change = {"path": path, "action": "deleted" if delete else "modified" if before else "created", "snapshot_id": snapshot_id,
                  "at": datetime.now(timezone.utc).isoformat()}
        workspace.recent_changes.append(change)
        await self.event("ide.file.deleted" if delete else "ide.file.modified" if before else "ide.file.created",
                         f"{'Deleted' if delete else 'Updated'} file: {path}", workspace_id=workspace_id, target_path=path, snapshot_id=snapshot_id)
        return {**change, "diff": diff}

    async def run_command(self, workspace_id: str, command: str, approval: bool = False, timeout: int = 300) -> dict[str, Any]:
        _, workspace = await self.gate("terminal.run", workspace_id=workspace_id, command=command, approval=approval)
        run_id = str(uuid.uuid4()); await self.event("ide.task.started", f"Task started: {command}", workspace_id=workspace_id, task_run_id=run_id, command=command)
        self.task_runs[run_id] = {"id": run_id, "command": command, "status": "running", "exit_code": None, "output": ""}
        try:
            proc = await asyncio.create_subprocess_exec(*shlex.split(command, posix=os.name != "nt"), cwd=str(workspace.root),
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
            self.active_processes[run_id] = proc
            output, _ = await asyncio.wait_for(proc.communicate(), timeout=min(max(timeout, 1), 1800))
            result = {"id": run_id, "command": command, "status": "completed" if proc.returncode == 0 else "failed",
                      "exit_code": proc.returncode, "output": output.decode(errors="replace")[-200000:]}
        except asyncio.TimeoutError:
            proc.kill(); result = {"id": run_id, "command": command, "status": "failed", "exit_code": -1, "output": "Task timed out."}
        finally:
            self.active_processes.pop(run_id, None)
        self.task_runs[run_id] = result
        await self.event("ide.task.completed" if result["exit_code"] == 0 else "ide.task.failed",
                         f"Task {result['status']}: {command}", workspace_id=workspace_id, task_run_id=run_id, exit_code=result["exit_code"])
        return result

    async def stop_task(self, run_id: str) -> dict[str, Any]:
        process = self.active_processes.get(run_id)
        if not process or process.returncode is not None:
            raise HTTPException(409, "Task is not currently running.")
        process.kill()
        current = self.task_runs.get(run_id, {"id": run_id})
        current.update({"status": "stopped", "exit_code": -2})
        await self.event("ide.task.stopped", "IDE task stopped by operator", task_run_id=run_id)
        return current

    async def git(self, workspace_id: str, operation: str, args: list[str] | None = None, approval: bool = False) -> dict[str, Any]:
        args = args or []
        if operation == "push": raise HTTPException(403, "Git push is disabled by default; configure it explicitly in Ronin posture.")
        allowed = {"status": ["status", "--short", "--branch"], "diff": ["diff", "--no-ext-diff"], "branch": ["branch", "--show-current"],
                   "create-branch": ["switch", "-c", *args], "commit": ["commit", *args]}
        if operation not in allowed: raise HTTPException(400, "Unsupported Git operation.")
        posture, workspace = await self.gate(f"git.{operation}", workspace_id=workspace_id, approval=approval)
        if operation in {"create-branch", "commit"} and (posture.get("active_tier") != "ronin" or not approval):
            raise HTTPException(403, "Git mutations require Ronin posture and explicit approval.")
        proc = await asyncio.create_subprocess_exec("git", *allowed[operation], cwd=str(workspace.root), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        output, _ = await proc.communicate()
        await self.event(f"ide.git.{operation.replace('-', '_')}", f"Git {operation} executed", workspace_id=workspace_id, result_code=proc.returncode)
        return {"operation": operation, "exit_code": proc.returncode, "output": output.decode(errors="replace")}


ide_service = IDEService()
