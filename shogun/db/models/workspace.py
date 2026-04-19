"""Workspace, WorkspacePeer, and WorkspaceMessage ORM models.

A Workspace is a shared project context between multiple Shogun agents.
Agents communicate via the A2A protocol — direct authenticated HTTP calls.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shogun.db.base import AuditMixin, Base, GUID, JSONType, UUIDMixin


class Workspace(Base, UUIDMixin, AuditMixin):
    """A shared project context owned by a Shogun agent.

    Multiple peers (remote Shogun instances) can be invited to join.
    """

    __tablename__ = "workspaces"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    topic: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")
    # "local" | "federated"
    scope: Mapped[str] = mapped_column(String(50), nullable=False, default="local")
    owner_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("agents.id"), nullable=True
    )
    # Shared living document — free-form markdown text agreed upon by all peers
    shared_document: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_version: Mapped[int] = mapped_column(default=0, nullable=False)
    tags: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)

    peers: Mapped[list[WorkspacePeer]] = relationship(
        "WorkspacePeer", back_populates="workspace", cascade="all, delete-orphan"
    )
    messages: Mapped[list[WorkspaceMessage]] = relationship(
        "WorkspaceMessage", back_populates="workspace", cascade="all, delete-orphan"
    )


class WorkspacePeer(Base, UUIDMixin, AuditMixin):
    """A remote Shogun agent participating in a workspace.

    Identified by their public A2A endpoint URL.
    """

    __tablename__ = "workspace_peers"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("workspaces.id"), nullable=False
    )
    # The remote agent's human-readable name (self-reported on invite)
    peer_name: Mapped[str] = mapped_column(String(255), nullable=False, default="Unknown Shogun")
    # URL of the remote Shogun's /api/v1/a2a/inbound endpoint
    peer_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    # "owner" | "collaborator" | "observer"
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="collaborator")
    # "pending" | "active" | "declined" | "offline"
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Shared secret agreed at invite time (HMAC verify key)
    shared_secret: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Metadata from their registration reply
    peer_meta: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)

    workspace: Mapped[Workspace] = relationship("Workspace", back_populates="peers")


class WorkspaceMessage(Base, UUIDMixin):
    """A single A2A message posted in a workspace thread."""

    __tablename__ = "workspace_messages"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("workspaces.id"), nullable=False
    )
    # who sent it — either the local agent ID or a peer identifier
    from_agent_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    from_peer_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    from_name: Mapped[str] = mapped_column(String(255), nullable=False, default="Unknown")
    # proposal | task | reply | update | plan_revision | approval | signal | system
    message_type: Mapped[str] = mapped_column(String(50), nullable=False, default="update")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # thread reply support
    parent_message_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("workspace_messages.id"), nullable=True
    )
    # sent | delivered | failed | local
    delivery_status: Mapped[str] = mapped_column(String(50), nullable=False, default="local")
    extra_meta: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        nullable=False,
    )

    workspace: Mapped[Workspace] = relationship("Workspace", back_populates="messages")
    replies: Mapped[list[WorkspaceMessage]] = relationship(
        "WorkspaceMessage",
        foreign_keys=[parent_message_id],
        back_populates="parent",
    )
    parent: Mapped[WorkspaceMessage | None] = relationship(
        "WorkspaceMessage",
        foreign_keys=[parent_message_id],
        back_populates="replies",
        remote_side="WorkspaceMessage.id",
    )
