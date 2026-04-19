"""A2A (Agent-to-Agent) API routes — Workspaces & Peer Messaging.

Exposes:
  /api/v1/a2a/identity           GET  — public identity card of this Shogun
  /api/v1/a2a/inbound            POST — receive signed messages from remote peers

  /api/v1/workspaces             GET  — list all workspaces
  /api/v1/workspaces             POST — create a workspace
  /api/v1/workspaces/{id}        GET  — workspace detail + document + peers + messages
  /api/v1/workspaces/{id}        PATCH — update workspace metadata
  /api/v1/workspaces/{id}/document  PATCH — update shared document
  /api/v1/workspaces/{id}/peers  POST — invite a peer
  /api/v1/workspaces/{id}/peers/{pid}/status  PATCH — update peer status
  /api/v1/workspaces/{id}/peers/{pid}  DELETE — remove peer
  /api/v1/workspaces/{id}/messages  GET   — fetch message thread
  /api/v1/workspaces/{id}/messages  POST  — post a message (fans out to peers)
"""

from __future__ import annotations

import logging
import secrets
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.api.deps import get_db
from shogun.config import settings
from shogun.db.engine import async_session_factory
from shogun.db.models.agent import Agent
from shogun.db.models.workspace import Workspace, WorkspacePeer, WorkspaceMessage
from shogun.integrations.a2a_client import (
    build_envelope,
    get_a2a_client,
    verify_signature,
)
from shogun.schemas.common import ApiResponse

logger = logging.getLogger(__name__)

# Two routers: one for the A2A protocol itself, one for Workspace CRUD
a2a_router = APIRouter(prefix="/a2a", tags=["A2A Protocol"])
workspace_router = APIRouter(prefix="/workspaces", tags=["Workspaces"])


# ── Helpers ───────────────────────────────────────────────────

async def _get_primary_agent(db: AsyncSession) -> Agent | None:
    result = await db.execute(
        select(Agent).where(Agent.is_primary == True, Agent.is_deleted == False)
    )
    return result.scalars().first()


def _self_url(path: str = "/api/v1/a2a/inbound") -> str:
    """Build a fully qualified URL for this running instance."""
    host = settings.api_host if settings.api_host != "0.0.0.0" else "localhost"
    port = settings.api_port
    return f"http://{host}:{port}{path}"


def _workspace_dict(ws: Workspace, peers: list, messages: list) -> dict:
    return {
        "id": str(ws.id),
        "name": ws.name,
        "description": ws.description,
        "topic": ws.topic,
        "status": ws.status,
        "scope": ws.scope,
        "owner_agent_id": str(ws.owner_agent_id) if ws.owner_agent_id else None,
        "shared_document": ws.shared_document,
        "document_version": ws.document_version,
        "tags": ws.tags,
        "created_at": ws.created_at.isoformat() if ws.created_at else None,
        "updated_at": ws.updated_at.isoformat() if ws.updated_at else None,
        "peer_count": len(peers),
        "message_count": len(messages),
        "peers": [_peer_dict(p) for p in peers],
        "messages": [_msg_dict(m) for m in messages],
    }


def _peer_dict(p: WorkspacePeer) -> dict:
    return {
        "id": str(p.id),
        "workspace_id": str(p.workspace_id),
        "peer_name": p.peer_name,
        "peer_url": p.peer_url,
        "role": p.role,
        "status": p.status,
        "last_seen_at": p.last_seen_at.isoformat() if p.last_seen_at else None,
        "peer_meta": p.peer_meta,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


def _msg_dict(m: WorkspaceMessage) -> dict:
    return {
        "id": str(m.id),
        "workspace_id": str(m.workspace_id),
        "from_agent_id": m.from_agent_id,
        "from_peer_url": m.from_peer_url,
        "from_name": m.from_name,
        "message_type": m.message_type,
        "content": m.content,
        "parent_message_id": str(m.parent_message_id) if m.parent_message_id else None,
        "delivery_status": m.delivery_status,
        "extra_meta": m.extra_meta,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


async def _fan_out(
    workspace_id: str,
    envelope: dict,
    db: AsyncSession,
) -> None:
    """Background task: send a message to all active peers of a workspace."""
    result = await db.execute(
        select(WorkspacePeer).where(
            WorkspacePeer.workspace_id == uuid.UUID(workspace_id),
            WorkspacePeer.status == "active",
        )
    )
    peers = result.scalars().all()
    client = get_a2a_client()

    for peer in peers:
        try:
            await client.send(peer.peer_url, envelope)
            # mark last_seen / delivery status
            peer.last_seen_at = datetime.now(timezone.utc)
        except Exception as exc:
            logger.warning("A2A fan-out to %s failed: %s", peer.peer_url, exc)

    await db.commit()


# ── A2A Protocol Endpoints ────────────────────────────────────

@a2a_router.get("/identity", response_model=ApiResponse)
async def a2a_identity(db: AsyncSession = Depends(get_db)):
    """Return this Shogun's public identity card.

    Remote agents call this to discover name, inbound URL, and capabilities.
    """
    agent = await _get_primary_agent(db)
    return ApiResponse(data={
        "name": agent.name if agent else "Shogun",
        "agent_id": str(agent.id) if agent else None,
        "inbound_url": _self_url("/api/v1/a2a/inbound"),
        "platform": "shogun",
        "version": "1.0.0",
        "capabilities": ["workspace", "messaging", "plan_revision", "task_delegation"],
    })


class InboundEnvelope(BaseModel):
    from_name: str
    from_url: str
    workspace_id: str
    message_type: str
    content: str
    metadata: dict = Field(default_factory=dict)
    ts: int
    sig: str


@a2a_router.post("/inbound", response_model=ApiResponse)
async def a2a_inbound(
    envelope: InboundEnvelope,
    db: AsyncSession = Depends(get_db),
):
    """Receive a signed message from a remote Shogun peer.

    Verifies the HMAC signature, finds or creates the local workspace record,
    stores the message, and returns an ACK.
    """
    # Build the unsigned payload for verification
    unsigned = {
        "from_name": envelope.from_name,
        "from_url": envelope.from_url,
        "workspace_id": envelope.workspace_id,
        "message_type": envelope.message_type,
        "content": envelope.content,
        "metadata": envelope.metadata,
        "ts": envelope.ts,
    }

    # Find the peer to get their shared_secret
    try:
        ws_id = uuid.UUID(envelope.workspace_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid workspace_id")

    peer_result = await db.execute(
        select(WorkspacePeer).where(
            WorkspacePeer.workspace_id == ws_id,
            WorkspacePeer.peer_url == envelope.from_url,
        )
    )
    peer = peer_result.scalars().first()

    # Verify signature if we know this peer
    if peer and peer.shared_secret:
        if not verify_signature(unsigned, envelope.sig, peer.shared_secret):
            raise HTTPException(status_code=403, detail="Invalid A2A signature")
        # Update last_seen
        peer.last_seen_at = datetime.now(timezone.utc)
        if peer.status == "pending":
            peer.status = "active"

    # Store the message
    msg = WorkspaceMessage(
        workspace_id=ws_id,
        from_agent_id=None,
        from_peer_url=envelope.from_url,
        from_name=envelope.from_name,
        message_type=envelope.message_type,
        content=envelope.content,
        delivery_status="delivered",
        extra_meta=envelope.metadata,
    )
    db.add(msg)
    await db.commit()

    return ApiResponse(data={
        "ack": True,
        "message_id": str(msg.id),
        "ts": envelope.ts,
    })


# ── Workspace CRUD ────────────────────────────────────────────

class CreateWorkspaceRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    topic: str | None = None
    tags: list[str] = Field(default_factory=list)


@workspace_router.get("", response_model=ApiResponse)
async def list_workspaces(db: AsyncSession = Depends(get_db)):
    """List all workspaces owned by or participated in by this Shogun."""
    result = await db.execute(
        select(Workspace).where(Workspace.status != "archived").order_by(desc(Workspace.created_at))
    )
    workspaces = result.scalars().all()

    out = []
    for ws in workspaces:
        peers_r = await db.execute(select(WorkspacePeer).where(WorkspacePeer.workspace_id == ws.id))
        msgs_r = await db.execute(select(WorkspaceMessage).where(WorkspaceMessage.workspace_id == ws.id))
        peers = peers_r.scalars().all()
        msgs = msgs_r.scalars().all()
        out.append(_workspace_dict(ws, peers, msgs))

    return ApiResponse(data=out, meta={"total": len(out)})


@workspace_router.post("", response_model=ApiResponse, status_code=201)
async def create_workspace(
    body: CreateWorkspaceRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a new workspace and seed a system message."""
    agent = await _get_primary_agent(db)
    now = datetime.now(timezone.utc)

    ws = Workspace(
        name=body.name,
        description=body.description,
        topic=body.topic,
        tags=body.tags,
        scope="local",
        status="active",
        owner_agent_id=agent.id if agent else None,
        shared_document=f"# {body.name}\n\n{body.description or ''}\n\n## Topic\n{body.topic or '(none yet)'}\n",
        document_version=1,
        created_at=now,
        updated_at=now,
        created_by="system",
        updated_by="system",
    )
    db.add(ws)
    await db.flush()

    # Seed a system message
    seed = WorkspaceMessage(
        workspace_id=ws.id,
        from_name="System",
        from_agent_id="system",
        message_type="system",
        content=f'Workspace **{ws.name}** created. Invite peers using their Shogun endpoint URL.',
        delivery_status="local",
        created_at=now,
    )
    db.add(seed)
    await db.commit()
    await db.refresh(ws)

    return ApiResponse(
        data=_workspace_dict(ws, [], [seed]),
        meta={"workspace_id": str(ws.id)},
    )


@workspace_router.get("/{workspace_id}", response_model=ApiResponse)
async def get_workspace(workspace_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get full workspace detail including peers and messages."""
    ws = await db.get(Workspace, workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")

    peers_r = await db.execute(select(WorkspacePeer).where(WorkspacePeer.workspace_id == ws.id))
    msgs_r = await db.execute(
        select(WorkspaceMessage)
        .where(WorkspaceMessage.workspace_id == ws.id)
        .order_by(WorkspaceMessage.created_at)
    )
    return ApiResponse(data=_workspace_dict(ws, peers_r.scalars().all(), msgs_r.scalars().all()))


class PatchWorkspaceRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    topic: str | None = None
    status: str | None = None
    tags: list[str] | None = None


@workspace_router.patch("/{workspace_id}", response_model=ApiResponse)
async def patch_workspace(
    workspace_id: uuid.UUID,
    body: PatchWorkspaceRequest,
    db: AsyncSession = Depends(get_db),
):
    ws = await db.get(Workspace, workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")

    for field, val in body.model_dump(exclude_unset=True).items():
        setattr(ws, field, val)
    ws.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(ws)

    peers_r = await db.execute(select(WorkspacePeer).where(WorkspacePeer.workspace_id == ws.id))
    msgs_r = await db.execute(select(WorkspaceMessage).where(WorkspaceMessage.workspace_id == ws.id))
    return ApiResponse(data=_workspace_dict(ws, peers_r.scalars().all(), msgs_r.scalars().all()))


class PatchDocumentRequest(BaseModel):
    content: str


@workspace_router.patch("/{workspace_id}/document", response_model=ApiResponse)
async def patch_document(
    workspace_id: uuid.UUID,
    body: PatchDocumentRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Update the workspace's shared document and fan it out to all peers."""
    ws = await db.get(Workspace, workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")

    ws.shared_document = body.content
    ws.document_version = (ws.document_version or 0) + 1
    ws.updated_at = datetime.now(timezone.utc)
    await db.commit()

    # Fan-out doc update to peers
    agent = await _get_primary_agent(db)
    envelope = build_envelope(
        from_name=agent.name if agent else "Shogun",
        from_url=_self_url(),
        workspace_id=str(workspace_id),
        message_type="plan_revision",
        content=body.content,
        metadata={"document_version": ws.document_version},
        secret=settings.secret_key,
    )
    background_tasks.add_task(_fan_out, str(workspace_id), envelope, db)

    return ApiResponse(data={
        "document_version": ws.document_version,
        "content": ws.shared_document,
    })


@workspace_router.delete("/{workspace_id}", response_model=ApiResponse)
async def delete_workspace(
    workspace_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Permanently delete a workspace and all its peers and messages."""
    ws = await db.get(Workspace, workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")

    name = ws.name
    await db.delete(ws)   # cascade handles peers + messages
    await db.commit()
    return ApiResponse(data={"deleted": True, "workspace_id": str(workspace_id), "name": name})



class InvitePeerRequest(BaseModel):
    peer_url: str = Field(..., min_length=5)
    peer_name: str = Field(default="Remote Shogun")
    role: str = Field(default="collaborator")


@workspace_router.post("/{workspace_id}/peers", response_model=ApiResponse, status_code=201)
async def invite_peer(
    workspace_id: uuid.UUID,
    body: InvitePeerRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Invite a remote Shogun to the workspace.

    1. Pings the remote to get their identity (best-effort).
    2. Creates a WorkspacePeer record (status=pending).
    3. Sends them a signed invitation message in the background.
    """
    ws = await db.get(Workspace, workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # Ping remote to get real name
    client = get_a2a_client()
    identity = await client.ping(body.peer_url)
    resolved_name = (
        identity.get("data", {}).get("name") or body.peer_name
        if identity else body.peer_name
    )

    # Generate a shared secret for this peer relationship
    shared_secret = secrets.token_hex(32)
    now = datetime.now(timezone.utc)

    peer = WorkspacePeer(
        workspace_id=workspace_id,
        peer_name=resolved_name,
        peer_url=body.peer_url,
        role=body.role,
        status="pending",
        shared_secret=shared_secret,
        peer_meta=identity.get("data", {}) if identity else {},
        created_at=now,
        updated_at=now,
        created_by="system",
        updated_by="system",
    )
    db.add(peer)

    # System message about the invite
    sys_msg = WorkspaceMessage(
        workspace_id=workspace_id,
        from_name="System",
        from_agent_id="system",
        message_type="system",
        content=f"📨 Invitation sent to **{resolved_name}** (`{body.peer_url}`). Awaiting acceptance.",
        delivery_status="local",
        created_at=now,
    )
    db.add(sys_msg)
    await db.commit()
    await db.refresh(peer)

    # Fire invitation in background
    agent = await _get_primary_agent(db)

    async def _send_invite():
        try:
            await client.send_invitation(
                body.peer_url,
                workspace_id=str(workspace_id),
                workspace_name=ws.name,
                from_name=agent.name if agent else "Shogun",
                from_url=_self_url(),
                secret=shared_secret,
            )
            # Mark peer active if invite was delivered
            async with async_session_factory() as s:
                p = await s.get(WorkspacePeer, peer.id)
                if p:
                    p.status = "active"
                    p.last_seen_at = datetime.now(timezone.utc)
                    await s.commit()
        except Exception as exc:
            logger.warning("Invitation send failed to %s: %s", body.peer_url, exc)

    background_tasks.add_task(_send_invite)

    return ApiResponse(data=_peer_dict(peer), meta={"shared_secret": shared_secret})


class PatchPeerStatusRequest(BaseModel):
    status: str  # active | declined | offline | pending


@workspace_router.patch("/{workspace_id}/peers/{peer_id}/status", response_model=ApiResponse)
async def update_peer_status(
    workspace_id: uuid.UUID,
    peer_id: uuid.UUID,
    body: PatchPeerStatusRequest,
    db: AsyncSession = Depends(get_db),
):
    peer = await db.get(WorkspacePeer, peer_id)
    if not peer or peer.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Peer not found")
    peer.status = body.status
    peer.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return ApiResponse(data=_peer_dict(peer))


@workspace_router.delete("/{workspace_id}/peers/{peer_id}", response_model=ApiResponse)
async def remove_peer(
    workspace_id: uuid.UUID,
    peer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    peer = await db.get(WorkspacePeer, peer_id)
    if not peer or peer.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Peer not found")
    await db.delete(peer)
    await db.commit()
    return ApiResponse(data={"deleted": True, "peer_id": str(peer_id)})


# ── Messaging ─────────────────────────────────────────────────

class PostMessageRequest(BaseModel):
    content: str = Field(..., min_length=1)
    message_type: str = Field(default="update")
    parent_message_id: str | None = None
    metadata: dict = Field(default_factory=dict)


@workspace_router.get("/{workspace_id}/messages", response_model=ApiResponse)
async def list_messages(
    workspace_id: uuid.UUID,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """Fetch the message thread for a workspace (oldest first)."""
    result = await db.execute(
        select(WorkspaceMessage)
        .where(WorkspaceMessage.workspace_id == workspace_id)
        .order_by(WorkspaceMessage.created_at)
        .limit(limit)
    )
    msgs = result.scalars().all()
    return ApiResponse(data=[_msg_dict(m) for m in msgs], meta={"total": len(msgs)})


@workspace_router.post("/{workspace_id}/messages", response_model=ApiResponse, status_code=201)
async def post_message(
    workspace_id: uuid.UUID,
    body: PostMessageRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Post a message to the workspace thread and fan it out to all peers."""
    ws = await db.get(Workspace, workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")

    agent = await _get_primary_agent(db)
    now = datetime.now(timezone.utc)

    parent_id = None
    if body.parent_message_id:
        try:
            parent_id = uuid.UUID(body.parent_message_id)
        except ValueError:
            pass

    msg = WorkspaceMessage(
        workspace_id=workspace_id,
        from_agent_id=str(agent.id) if agent else "system",
        from_peer_url=_self_url(),
        from_name=agent.name if agent else "Shogun",
        message_type=body.message_type,
        content=body.content,
        parent_message_id=parent_id,
        delivery_status="local",
        extra_meta=body.metadata,
        created_at=now,
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)

    # Fan-out to peers in background
    envelope = build_envelope(
        from_name=agent.name if agent else "Shogun",
        from_url=_self_url(),
        workspace_id=str(workspace_id),
        message_type=body.message_type,
        content=body.content,
        metadata={**body.metadata, "local_message_id": str(msg.id)},
        secret=settings.secret_key,
    )
    background_tasks.add_task(_fan_out, str(workspace_id), envelope, db)

    # Update message delivery status to "sent" (fan-out is async)
    msg.delivery_status = "sent"
    await db.commit()

    return ApiResponse(data=_msg_dict(msg))
