"""Shogun IDE Mode REST and localhost WebSocket bridge."""

from __future__ import annotations

import uuid
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.api.deps import get_db
from shogun.schemas.common import ApiResponse
from shogun.services.ide_service import ide_service

router = APIRouter(prefix="/ide", tags=["IDE Mode"])

class EnableBody(BaseModel):
    confirmed: bool = False
    remember_workspace: bool = False
class PairBody(BaseModel): token: str
class WorkspaceBody(BaseModel):
    workspace_id: str | None = None; workspace_name: str; workspace_root: str
    git_enabled: bool = False; git_branch: str | None = None; languages_detected: list[str] = Field(default_factory=list)
    package_managers: list[str] = Field(default_factory=list); available_tasks: list[str] = Field(default_factory=list)
    diagnostics_available: bool = True; extension_version: str = "0.1.0"
class FileBody(BaseModel):
    workspace_id: str; path: str; content: str | None = None; query: str | None = None; glob: str = "*"; approved: bool = False
class CommandBody(BaseModel):
    workspace_id: str; command: str; approved: bool = False; timeout: int = 300
class GitBody(BaseModel):
    workspace_id: str; operation: str; args: list[str] = Field(default_factory=list); approved: bool = False

@router.get("/status")
async def status(): return ApiResponse(data=await ide_service.status())
@router.post("/enable")
async def enable(body: EnableBody): return ApiResponse(data=await ide_service.enable(body.confirmed, body.remember_workspace))
@router.post("/disable")
async def disable(): return ApiResponse(data=await ide_service.disable())
@router.post("/pairing/create")
async def pairing_create(): return ApiResponse(data=await ide_service.create_pairing())
@router.post("/pairing/confirm")
async def pairing_confirm(body: PairBody): return ApiResponse(data={"session_id": await ide_service.confirm_pairing(body.token)})
@router.post("/pairing/revoke")
async def pairing_revoke(): ide_service.pairings.clear(); return ApiResponse(data={"revoked": True})
@router.get("/providers")
async def providers(): return ApiResponse(data=[{"id": "vscode", "name": "VS Code Adapter", "capabilities": (await ide_service.status())["capabilities"]}])
@router.get("/providers/vscode/capabilities")
async def capabilities(): return ApiResponse(data=(await ide_service.status())["capabilities"])
@router.post("/providers/vscode/disconnect")
async def disconnect_provider():
    for socket in list(ide_service.connections.values()): await socket.close(code=4002, reason="Disconnected by operator")
    ide_service.connections.clear(); return ApiResponse(data={"disconnected": True})
@router.post("/workspaces/register")
async def register(body: WorkspaceBody): return ApiResponse(data=await ide_service.register_workspace(body.model_dump()))
@router.get("/workspaces")
async def workspaces(): return ApiResponse(data=[ide_service.public_workspace(item) for item in ide_service.workspaces.values()])
@router.get("/workspaces/{workspace_id}")
async def workspace(workspace_id: str):
    item=ide_service.workspaces.get(workspace_id)
    if not item: raise HTTPException(404, "Workspace not found.")
    return ApiResponse(data=ide_service.public_workspace(item))
@router.post("/workspaces/{workspace_id}/approve")
async def approve(workspace_id: str):
    await ide_service.gate("workspace.approve"); item=ide_service.workspaces.get(workspace_id)
    if not item: raise HTTPException(404, "Workspace not found.")
    item.approved=True; await ide_service.event("ide.workspace.approved", f"Workspace approved: {item.name}", workspace_id=workspace_id)
    return ApiResponse(data=ide_service.public_workspace(item))
@router.post("/workspaces/{workspace_id}/revoke")
async def revoke(workspace_id: str):
    item=ide_service.workspaces.get(workspace_id)
    if not item: raise HTTPException(404, "Workspace not found.")
    item.approved=False; await ide_service.event("ide.workspace.revoked", f"Workspace revoked: {item.name}", workspace_id=workspace_id)
    return ApiResponse(data=ide_service.public_workspace(item))
@router.post("/files/read")
async def read_file(body: FileBody): return ApiResponse(data=await ide_service.read_file(body.workspace_id, body.path, body.approved))
@router.post("/files/list")
async def list_files(body: FileBody): return ApiResponse(data=await ide_service.list_files(body.workspace_id, body.glob))
@router.post("/files/search")
async def search(body: FileBody): return ApiResponse(data=await ide_service.search(body.workspace_id, body.query or "", body.glob))
@router.post("/files/create")
async def create(body: FileBody): return ApiResponse(data=await ide_service.write(body.workspace_id, body.path, body.content or "", approval=body.approved))
@router.post("/files/apply-patch")
async def apply_patch(body: FileBody):
    # The bridge supplies the fully reviewed resulting content; the server snapshots and returns a unified diff.
    if body.content is None: raise HTTPException(400, "Resulting file content is required.")
    return ApiResponse(data=await ide_service.write(body.workspace_id, body.path, body.content, approval=body.approved))
@router.post("/files/delete")
async def delete(body: FileBody): return ApiResponse(data=await ide_service.write(body.workspace_id, body.path, "", approval=body.approved, delete=True))
@router.get("/files/diff")
async def file_diff(workspace_id: str): return ApiResponse(data=(await ide_service.git(workspace_id, "diff")))
@router.post("/tasks/run")
async def run_task(body: CommandBody, db: AsyncSession = Depends(get_db)):
    from shogun.api.security import _get_agent_posture
    from shogun.schemas.skills import SkillActivationRequest
    from shogun.services.active_skill_service import SkillActivationService

    posture = await _get_agent_posture()
    activation = await SkillActivationService(db).activate(SkillActivationRequest(
        run_id=f"ide:{body.workspace_id}:{uuid.uuid4()}",
        objective=body.command,
        context="Run an approved IDE task in the connected workspace.",
        posture=posture.get("active_tier", "guarded"),
        available_tools=["ide.file.read", "ide.file.apply_patch", "ide.task.run"],
        max_skills=3,
        usage_location="ide_mode",
        ide_enabled=bool(posture.get("ide_enabled", False)),
    ))
    result = await ide_service.run_command(body.workspace_id, body.command, body.approved, body.timeout)
    outcome_service = SkillActivationService(db)
    for item in activation["active_skills"]:
        await outcome_service.outcome(item["active_skill_run_id"], "success", "IDE task completed")
    await db.commit()
    return ApiResponse(data={**result, "active_skills": activation["active_skills"]})
@router.get("/tasks")
async def tasks(workspace_id: str):
    _, item = await ide_service.gate("task.list", workspace_id=workspace_id)
    return ApiResponse(data=(item.metadata.get("available_tasks", []) if item else []))
@router.get("/tasks/{run_id}/output")
async def task_output(run_id: str):
    if run_id not in ide_service.task_runs: raise HTTPException(404, "Task run not found.")
    return ApiResponse(data=ide_service.task_runs[run_id])
@router.post("/tasks/{run_id}/stop")
async def stop_task(run_id: str): return ApiResponse(data=await ide_service.stop_task(run_id))
@router.post("/terminal/run")
async def terminal(body: CommandBody): return ApiResponse(data=await ide_service.run_command(body.workspace_id, body.command, body.approved, body.timeout))
@router.post("/git")
async def git(body: GitBody): return ApiResponse(data=await ide_service.git(body.workspace_id, body.operation, body.args, body.approved))
@router.get("/diagnostics")
async def diagnostics():
    result = await ide_service.request_bridge("diagnostics.get")
    await ide_service.event("ide.diagnostics.read", "VS Code diagnostics read")
    return ApiResponse(data=result)
@router.get("/editor/context")
async def editor_context(): return ApiResponse(data=await ide_service.request_bridge("editor.context"))
@router.post("/workspaces/{workspace_id}/rollback/{snapshot_id}")
async def rollback(workspace_id: str, snapshot_id: str): return ApiResponse(data=await ide_service.rollback(workspace_id, snapshot_id))
@router.post("/kill-switch")
async def kill_switch(): return ApiResponse(data=await ide_service.disable())

@router.websocket("/bridge")
async def bridge(websocket: WebSocket):
    if websocket.client and websocket.client.host not in {"127.0.0.1", "::1", "localhost", "testclient"}:
        await websocket.close(code=4403); return
    token = websocket.query_params.get("token", "")
    try: session_id = await ide_service.confirm_pairing(token)
    except HTTPException: await websocket.close(code=4401); return
    await websocket.accept(); ide_service.connections[session_id]=websocket
    await ide_service.event("ide.provider.connected", "VS Code Adapter connected", session_id=session_id)
    await websocket.send_json({"type": "session.ready", "session_id": session_id, "status": await ide_service.status()})
    try:
        while True:
            message: dict[str, Any] = await websocket.receive_json()
            kind=message.get("type"); payload=message.get("payload") or {}; request_id=message.get("request_id")
            if kind == "response":
                future=ide_service.pending.get(str(request_id))
                if future and not future.done():
                    if message.get("status") == "error": future.set_exception(RuntimeError((message.get("error") or {}).get("message", "VS Code request failed")))
                    else: future.set_result(payload)
                continue
            if kind == "workspace.register": result=await ide_service.register_workspace(payload)
            elif kind == "event": result={"received": True}
            else: result={"received": True, "type": kind}
            await websocket.send_json({"type": "response", "request_id": request_id, "session_id": session_id, "status": "success", "payload": result})
    except WebSocketDisconnect: pass
    finally:
        ide_service.connections.pop(session_id, None)
        await ide_service.event("ide.provider.disconnected", "VS Code Adapter disconnected", session_id=session_id)
