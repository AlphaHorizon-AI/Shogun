"""Microsoft Teams adapter application service.

Microsoft protocol handling stays in the bridge. This service owns tenant policy,
identity mapping, command governance, audit, and safe channel-neutral responses.
"""

from __future__ import annotations

import hashlib
import io
import json
import secrets
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.config import settings
from shogun.db.models.agent import Agent
from shogun.db.models.teams import (
    TeamsApprovalRequest,
    TeamsCommandLog,
    TeamsConfig,
    TeamsConversation,
    TeamsUserMap,
)
from shogun.schemas.teams import CommandEnvelope, ResponseEnvelope, ResponseTarget, TeamsConfigUpdate
from shogun.services.command_channel import COMMAND_POLICY, authorize, parse_command, teams_rate_limiter

DEFAULT_COMMANDS = [
    "help",
    "status",
    "agents",
    "workflows",
    "approvals",
    "ask",
    "run",
    "pause",
    "resume",
    "summarize",
    "logs",
    "approve",
    "reject",
    "harakiri",
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _config_dict(config: TeamsConfig) -> dict:
    return {
        "id": str(config.id),
        "enabled": config.enabled,
        "deployment_mode": config.deployment_mode,
        "tenant_mode": config.tenant_mode,
        "allowed_tenant_ids": config.allowed_tenant_ids,
        "bot_app_id": config.bot_app_id,
        "bot_name": config.bot_name,
        "client_secret_ref": config.client_secret_ref,
        "public_messaging_endpoint": config.public_messaging_endpoint,
        "valid_domains": config.valid_domains,
        "graph_enabled": config.graph_enabled,
        "proactive_enabled": config.proactive_enabled,
        "sso_enabled": config.sso_enabled,
        "allowed_commands": config.allowed_commands,
        "allowed_channels": config.allowed_channels,
        "destructive_commands_enabled": config.destructive_commands_enabled,
        "dual_approval_fleet": config.dual_approval_fleet,
        "approval_ttl_seconds": config.approval_ttl_seconds,
        "last_inbound_at": config.last_inbound_at,
        "last_outbound_at": config.last_outbound_at,
        "last_error": config.last_error,
        "created_at": config.created_at,
        "updated_at": config.updated_at,
    }


class TeamsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_config_model(self) -> TeamsConfig:
        config = await self.db.scalar(select(TeamsConfig).limit(1))
        if config:
            return config
        config = TeamsConfig(
            enabled=settings.teams_adapter_enabled,
            deployment_mode=settings.teams_deployment_mode,
            tenant_mode=settings.teams_tenant_mode,
            allowed_tenant_ids=[x.strip() for x in settings.teams_allowed_tenant_ids.split(",") if x.strip()],
            bot_app_id=settings.teams_bot_app_id,
            client_secret_ref=settings.teams_bot_client_secret_ref,
            public_messaging_endpoint=settings.teams_public_messaging_endpoint,
            valid_domains=[x.strip() for x in settings.teams_manifest_valid_domains.split(",") if x.strip()],
            graph_enabled=settings.teams_graph_enabled,
            proactive_enabled=settings.teams_proactive_enabled,
            sso_enabled=settings.teams_sso_enabled,
            allowed_commands=DEFAULT_COMMANDS,
        )
        self.db.add(config)
        await self.db.flush()
        return config

    async def get_config(self) -> dict:
        return _config_dict(await self.get_config_model())

    async def update_config(self, body: TeamsConfigUpdate) -> dict:
        config = await self.get_config_model()
        for key, value in body.model_dump().items():
            setattr(config, key, value)
        await self.db.flush()
        return _config_dict(config)

    async def health(self) -> dict:
        config = await self.get_config_model()
        configured = bool(config.bot_app_id and config.allowed_tenant_ids and config.public_messaging_endpoint)
        endpoint_https = bool(
            config.public_messaging_endpoint and urlparse(config.public_messaging_endpoint).scheme == "https"
        )
        issues = []
        if not config.bot_app_id:
            issues.append("Bot/App ID is not configured")
        if not config.allowed_tenant_ids:
            issues.append("No allowed Microsoft tenant is configured")
        if not endpoint_https:
            issues.append("Public messaging endpoint must use HTTPS")
        if config.sso_enabled and not config.bot_app_id:
            issues.append("SSO requires an App ID")
        return {
            "status": "healthy" if config.enabled and configured and endpoint_https else "not_ready",
            "enabled": config.enabled,
            "configured": configured,
            "bridge": "external",
            "tenant_status": "configured" if config.allowed_tenant_ids else "missing",
            "sso_status": "enabled" if config.sso_enabled else "disabled",
            "proactive_status": "enabled" if config.proactive_enabled else "disabled",
            "issues": issues,
            "last_inbound_at": config.last_inbound_at,
            "last_outbound_at": config.last_outbound_at,
            "last_error": config.last_error,
            "active_approvals": await self.db.scalar(
                select(func.count()).select_from(TeamsApprovalRequest).where(TeamsApprovalRequest.status == "pending")
            )
            or 0,
        }

    async def _resolve_user(self, envelope: CommandEnvelope) -> TeamsUserMap:
        user = await self.db.scalar(
            select(TeamsUserMap).where(
                TeamsUserMap.tenant_id == envelope.tenant_id,
                TeamsUserMap.teams_user_id == envelope.user.teams_user_id,
            )
        )
        if not user:
            user = TeamsUserMap(
                tenant_id=envelope.tenant_id,
                teams_user_id=envelope.user.teams_user_id,
                aad_object_id=envelope.user.aad_object_id,
                user_principal_name=envelope.user.user_principal_name,
                display_name=envelope.user.display_name,
                shogun_role="viewer",
            )
            self.db.add(user)
        user.last_seen_at = _now()
        user.display_name = envelope.user.display_name
        user.aad_object_id = envelope.user.aad_object_id
        user.user_principal_name = envelope.user.user_principal_name
        from shogun.services.team_identity import resolve_channel_member

        member = await resolve_channel_member(
            self.db,
            channel="microsoft_teams",
            external_user_id=envelope.user.teams_user_id,
            aad_object_id=envelope.user.aad_object_id,
            user_principal_name=envelope.user.user_principal_name,
        )
        if member:
            user.shogun_user_id = str(member.id)
            user.display_name = member.display_name
            user.shogun_role = "admin" if member.role == "owner" else "viewer"
        await self.db.flush()
        return user

    async def _store_conversation(self, envelope: CommandEnvelope) -> None:
        conversation_id = envelope.conversation_reference_id or envelope.chat_id or envelope.channel_id
        if not conversation_id:
            return
        conversation = await self.db.scalar(
            select(TeamsConversation).where(
                TeamsConversation.tenant_id == envelope.tenant_id,
                TeamsConversation.conversation_id == conversation_id,
            )
        )
        if not conversation:
            conversation = TeamsConversation(
                tenant_id=envelope.tenant_id,
                conversation_id=conversation_id,
                conversation_type=envelope.conversation_type,
            )
            self.db.add(conversation)
        conversation.team_id = envelope.team_id
        conversation.channel_id = envelope.channel_id
        conversation.chat_id = envelope.chat_id
        conversation.last_activity_id = envelope.message_id
        conversation.service_url = envelope.service_url
        if envelope.conversation_reference:
            conversation.conversation_reference = envelope.conversation_reference

    def _response(
        self,
        envelope: CommandEnvelope,
        text: str,
        *,
        response_type: str = "text",
        title: str | None = None,
        severity: str = "info",
        card_payload: dict | None = None,
    ) -> ResponseEnvelope:
        return ResponseEnvelope(
            correlation_id=envelope.correlation_id,
            target=ResponseTarget(
                conversation_reference_id=envelope.conversation_reference_id,
                reply_to_id=envelope.message_id,
            ),
            response_type=response_type,
            title=title,
            text=text,
            severity=severity,
            card_payload=card_payload or {},
        )

    async def dispatch(self, envelope: CommandEnvelope) -> ResponseEnvelope:
        config = await self.get_config_model()
        parsed = parse_command(envelope.raw_text)
        envelope.normalized_text = parsed.normalized_text
        envelope.command_name = parsed.name
        envelope.arguments = parsed.arguments
        envelope.risk_level = parsed.risk_level
        envelope.requires_approval = parsed.requires_approval
        config.last_inbound_at = _now()

        response: ResponseEnvelope
        auth_result = "denied"
        error_code: str | None = None

        if not config.enabled:
            error_code = "adapter_disabled"
            response = self._response(
                envelope, "The Microsoft Teams adapter is disabled in Katana.", response_type="error"
            )
        elif envelope.tenant_id not in config.allowed_tenant_ids:
            error_code = "unknown_tenant"
            response = self._response(envelope, "This Microsoft tenant is not authorized.", response_type="error")
        elif config.allowed_channels and envelope.channel_id and envelope.channel_id not in config.allowed_channels:
            error_code = "channel_denied"
            response = self._response(envelope, "This Teams channel is not authorized.", response_type="error")
        elif not teams_rate_limiter.allow(
            f"user:{envelope.tenant_id}:{envelope.user.teams_user_id}",
            settings.teams_rate_limit_per_user_per_minute,
        ):
            error_code = "user_rate_limit"
            response = self._response(
                envelope, "Too many commands. Please wait a moment and try again.", response_type="error"
            )
        elif envelope.channel_id and not teams_rate_limiter.allow(
            f"channel:{envelope.tenant_id}:{envelope.channel_id}",
            settings.teams_rate_limit_per_channel_per_minute,
        ):
            error_code = "channel_rate_limit"
            response = self._response(envelope, "This channel is sending commands too quickly.", response_type="error")
        elif envelope.attachments:
            error_code = "attachments_disabled"
            response = self._response(
                envelope,
                "Attachments are disabled for Teams commands until they have been scanned.",
                response_type="error",
            )
        else:
            user = await self._resolve_user(envelope)
            configured_command = "harakiri" if parsed.name == "harakiri_control" else parsed.name
            command_enabled = not config.allowed_commands or configured_command in config.allowed_commands
            allowed, auth_result = authorize(parsed.name, user.shogun_role, config.destructive_commands_enabled)
            if not command_enabled:
                allowed, auth_result = False, "command_disabled"
            if not allowed:
                error_code = auth_result
                required = COMMAND_POLICY.get(parsed.name, ("L0", "viewer"))[1]
                response = self._response(
                    envelope,
                    f"You are not authorized to run this command.\n\n"
                    f"Command: {parsed.name}\nRequired role: {required.replace('_', ' ').title()}\n"
                    f"Your role: {user.shogun_role.replace('_', ' ').title()}\n"
                    f"Correlation ID: {envelope.correlation_id}",
                    response_type="error",
                    severity="warning",
                )
            else:
                auth_result = "allowed"
                response = await self._execute_safe(envelope, user.shogun_role, config)

        await self._store_conversation(envelope)
        self.db.add(
            TeamsCommandLog(
                correlation_id=envelope.correlation_id,
                tenant_id=envelope.tenant_id,
                user_id=envelope.user.teams_user_id,
                aad_object_id=envelope.user.aad_object_id,
                conversation_id=envelope.conversation_reference_id or envelope.chat_id or envelope.channel_id,
                raw_text=envelope.raw_text,
                normalized_text=envelope.normalized_text,
                command_name=envelope.command_name,
                arguments=envelope.arguments,
                risk_level=envelope.risk_level,
                authorization_result=auth_result,
                response_type=response.response_type,
                success=response.response_type != "error",
                error_code=error_code,
                created_at=_now(),
            )
        )
        config.last_outbound_at = _now()
        await self.db.flush()
        return response

    async def _execute_safe(self, envelope: CommandEnvelope, role: str, config: TeamsConfig) -> ResponseEnvelope:
        command = envelope.command_name
        if command == "harakiri_control":
            from shogun.services.harakiri_control import execute_harakiri_control

            action = envelope.arguments["action"]
            await execute_harakiri_control(
                action,
                source="microsoft_teams",
                actor=envelope.user.aad_object_id or envelope.user.teams_user_id,
            )
            if action == "activate":
                return self._response(
                    envelope,
                    "HARAKIRI ACTIVATED. All agent activity is suspended and posture is now SHRINE.",
                    title="Emergency shutdown active",
                    severity="critical",
                )
            return self._response(
                envelope,
                "HARAKIRI RESET. The kill switch is inactive and posture is now TACTICAL.",
                title="Emergency shutdown cleared",
                severity="success",
            )
        if command == "unknown":
            return self._response(
                envelope,
                "I did not recognize that command.\n\nTry: status, agents, help, show pending approvals",
                response_type="error",
            )
        if command == "help":
            available = [
                name for name in DEFAULT_COMMANDS if authorize(name, role, config.destructive_commands_enabled)[0]
            ]
            return self._response(
                envelope, "Available commands:\n" + "\n".join(f"• {x}" for x in available), title="Help"
            )
        if command == "status":
            counts = dict((await self.db.execute(select(Agent.status, func.count()).group_by(Agent.status))).all())
            pending = (
                await self.db.scalar(
                    select(func.count())
                    .select_from(TeamsApprovalRequest)
                    .where(TeamsApprovalRequest.status == "pending")
                )
                or 0
            )
            text = (
                f"Shogun: Online\nGensui: {'Connected' if settings.gensui_enabled else 'Standalone'}\n"
                f"Active agents: {counts.get('active', 0)}\nPaused agents: {counts.get('paused', 0)}\n"
                f"Agents in error: {counts.get('error', 0)}\nPending approvals: {pending}"
            )
            card = {
                "type": "AdaptiveCard",
                "version": "1.5",
                "body": [
                    {"type": "TextBlock", "text": "Shogun Fleet Status", "weight": "Bolder", "size": "Medium"},
                    {"type": "TextBlock", "text": text, "wrap": True},
                ],
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            }
            return self._response(envelope, text, response_type="status_card", title="Fleet Status", card_payload=card)
        if command == "agents":
            query = select(Agent.name, Agent.slug, Agent.status).order_by(Agent.name).limit(25)
            rows = (await self.db.execute(query)).all()
            text = "\n".join(f"• {name} ({slug}) — {status}" for name, slug, status in rows) or "No agents found."
            return self._response(envelope, text, title="Agents")
        if command == "ask":
            from shogun.api.governed_chat import _shogun_governed_chat
            from shogun.services.agent_service import AgentService
            from shogun.services.team_identity import member_context_text, resolve_channel_member

            member = await resolve_channel_member(
                self.db,
                channel="microsoft_teams",
                external_user_id=envelope.user.teams_user_id,
                aad_object_id=envelope.user.aad_object_id,
                user_principal_name=envelope.user.user_principal_name,
            )
            message = member_context_text(envelope.arguments["message"], member, channel="Microsoft Teams")
            classification = {
                "mode": "governed",
                "reason": "teams_member_chat",
                "matched": [],
                **(
                    {
                        "_speaker_name": member.display_name,
                        "_speaker_member_id": str(member.id),
                        "_speaker_role": "Primary Admin" if member.role == "owner" else "Team Member",
                    }
                    if member
                    else {}
                ),
            }
            response_stream = await _shogun_governed_chat(
                user_msg=message,
                history=[],
                svc=AgentService(self.db),
                classification=classification,
            )
            reply = ""
            buffer = ""
            generator = getattr(response_stream, "body_iterator", response_stream)
            async for chunk in generator:
                buffer += chunk.decode("utf-8") if isinstance(chunk, bytes) else str(chunk)
                while "\n\n" in buffer:
                    event, buffer = buffer.split("\n\n", 1)
                    for line in event.splitlines():
                        if not line.startswith("data: ") or line[6:].strip() == "[DONE]":
                            continue
                        try:
                            data = json.loads(line[6:])
                        except json.JSONDecodeError:
                            continue
                        if data.get("type") == "token":
                            reply += str(data.get("content") or "")
                        elif data.get("type") == "error" and not reply:
                            reply = str(data.get("content") or "Unable to answer right now.")
            return self._response(envelope, reply.strip() or "I could not generate a response.")
        if command == "approvals":
            rows = (
                await self.db.execute(
                    select(
                        TeamsApprovalRequest.approval_request_id,
                        TeamsApprovalRequest.risk_level,
                        TeamsApprovalRequest.expires_at,
                    )
                    .where(TeamsApprovalRequest.status == "pending")
                    .order_by(TeamsApprovalRequest.created_at.desc())
                    .limit(20)
                )
            ).all()
            text = "\n".join(f"• {rid} — {risk}, expires {expiry:%Y-%m-%d %H:%M UTC}" for rid, risk, expiry in rows)
            return self._response(envelope, text or "No pending approvals.", title="Pending Approvals")
        if command in {"approve", "reject"}:
            request_id = envelope.arguments["request_id"]
            approval = await self.db.scalar(
                select(TeamsApprovalRequest).where(TeamsApprovalRequest.approval_request_id == request_id)
            )
            if not approval:
                return self._response(envelope, f"Approval request {request_id} was not found.", response_type="error")
            now = _now()
            expires_at = approval.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if approval.status not in {"pending", "awaiting_second_approval"}:
                return self._response(
                    envelope, f"Approval request {request_id} has already been used.", response_type="error"
                )
            if expires_at <= now:
                approval.status = "expired"
                return self._response(envelope, f"Approval request {request_id} has expired.", response_type="error")
            if command == "reject":
                approval.status = "rejected"
                approval.rejected_by_user_id = envelope.user.teams_user_id
                return self._response(
                    envelope, f"Approval request {request_id} was rejected and closed.", severity="warning"
                )
            first_approver = approval.action_payload.get("first_approver")
            dual = bool(approval.action_payload.get("dual_approval"))
            if dual and not first_approver:
                approval.action_payload = {**approval.action_payload, "first_approver": envelope.user.teams_user_id}
                approval.status = "awaiting_second_approval"
                return self._response(
                    envelope, f"First approval recorded for {request_id}. A second administrator is required."
                )
            if dual and first_approver == envelope.user.teams_user_id:
                return self._response(
                    envelope, "The second approval must come from a different administrator.", response_type="error"
                )
            approval.status = "approved"
            approval.approved_by_user_id = envelope.user.teams_user_id
            return self._response(
                envelope,
                f"Approval request {request_id} is approved. "
                "Gensui remains responsible for final policy validation and execution.",
                severity="success",
            )
        if command in {"harakiri", "pause", "resume"}:
            request_id = f"REQ-{uuid.uuid4().hex[:10].upper()}"
            confirmation_code = f"HARA-{secrets.randbelow(9000) + 1000}"
            dual = command == "harakiri" and envelope.arguments.get("scope") == "fleet" and config.dual_approval_fleet
            approval = TeamsApprovalRequest(
                approval_request_id=request_id,
                conversation_id=envelope.conversation_reference_id
                or envelope.chat_id
                or envelope.channel_id
                or "unknown",
                requested_by_user_id=envelope.user.teams_user_id,
                required_role="admin" if command == "harakiri" else "operator",
                risk_level="L4",
                status="pending",
                expires_at=_now() + timedelta(seconds=config.approval_ttl_seconds),
                action_payload={
                    "command": command,
                    "arguments": envelope.arguments,
                    "dual_approval": dual,
                    "confirmation_required": True,
                },
                confirmation_code_hash=hashlib.sha256(confirmation_code.encode()).hexdigest(),
            )
            self.db.add(approval)
            return self._response(
                envelope,
                f"This critical command has not executed.\nRequest: {request_id}\n"
                f"Confirmation code: {confirmation_code}\nExpires in: {config.approval_ttl_seconds // 60} minutes"
                + ("\nTwo distinct administrators must approve." if dual else ""),
                response_type="approval_card",
                severity="warning",
                title="Gensui confirmation required",
                card_payload={
                    "type": "AdaptiveCard",
                    "version": "1.5",
                    "body": [
                        {"type": "TextBlock", "text": "Critical action confirmation", "weight": "Bolder"},
                        {"type": "TextBlock", "text": envelope.normalized_text, "wrap": True},
                        {
                            "type": "FactSet",
                            "facts": [
                                {"title": "Request", "value": request_id},
                                {"title": "Risk", "value": "L4"},
                                {"title": "Expires", "value": f"{config.approval_ttl_seconds // 60} minutes"},
                            ],
                        },
                        {
                            "type": "TextBlock",
                            "text": "Execution remains blocked until Gensui validates the approval.",
                            "wrap": True,
                        },
                    ],
                    "actions": [
                        {
                            "type": "Action.Submit",
                            "title": "Approve",
                            "data": {"action": "approve", "request_id": request_id},
                        },
                        {
                            "type": "Action.Submit",
                            "title": "Reject",
                            "data": {"action": "reject", "request_id": request_id},
                        },
                    ],
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                },
            )
        return self._response(
            envelope,
            f"Command “{envelope.normalized_text}” was authorized and submitted to the Gensui command boundary.",
            severity="success",
        )

    async def list_commands(self, limit: int = 100) -> list[dict]:
        rows = (
            await self.db.scalars(
                select(TeamsCommandLog).order_by(TeamsCommandLog.created_at.desc()).limit(min(limit, 500))
            )
        ).all()
        return [
            {
                "id": str(row.id),
                "correlation_id": row.correlation_id,
                "tenant_id": row.tenant_id,
                "user_id": row.user_id,
                "normalized_text": row.normalized_text,
                "command_name": row.command_name,
                "risk_level": row.risk_level,
                "authorization_result": row.authorization_result,
                "success": row.success,
                "error_code": row.error_code,
                "created_at": row.created_at,
            }
            for row in rows
        ]

    async def list_users(self) -> list[dict]:
        rows = (await self.db.scalars(select(TeamsUserMap).order_by(TeamsUserMap.display_name))).all()
        return [
            {
                "id": str(row.id),
                "tenant_id": row.tenant_id,
                "teams_user_id": row.teams_user_id,
                "aad_object_id": row.aad_object_id,
                "user_principal_name": row.user_principal_name,
                "display_name": row.display_name,
                "shogun_role": row.shogun_role,
                "allowed_command_groups": row.allowed_command_groups,
                "last_seen_at": row.last_seen_at,
            }
            for row in rows
        ]

    async def generate_manifest_package(self) -> bytes:
        config = await self.get_config_model()
        if not config.bot_app_id:
            raise ValueError("Bot/App ID is required before generating a manifest")
        manifest = {
            "$schema": "https://developer.microsoft.com/en-us/json-schemas/teams/v1.22/MicrosoftTeams.schema.json",
            "manifestVersion": "1.22",
            "version": "1.0.0",
            "id": config.bot_app_id,
            "developer": {
                "name": "Alpha Horizon",
                "websiteUrl": "https://alphahorizon.com",
                "privacyUrl": "https://alphahorizon.com/privacy",
                "termsOfUseUrl": "https://alphahorizon.com/terms",
            },
            "name": {"short": "Shogun", "full": "Shogun AFM"},
            "description": {
                "short": "Agent Fleet Management command channel",
                "full": "Governed Microsoft Teams command channel for Shogun Agent Fleet Management.",
            },
            "icons": {"outline": "outline.png", "color": "color.png"},
            "accentColor": "#111827",
            "bots": [
                {
                    "botId": config.bot_app_id,
                    "scopes": ["personal", "team", "groupchat"],
                    "isNotificationOnly": False,
                    "supportsFiles": False,
                    "commandLists": [
                        {
                            "scopes": ["personal", "team", "groupchat"],
                            "commands": [
                                {"title": "status", "description": "Show Shogun fleet status"},
                                {"title": "agents", "description": "Show active agents"},
                                {"title": "approvals", "description": "Show pending approvals"},
                                {"title": "help", "description": "Show available commands"},
                            ],
                        }
                    ],
                }
            ],
            "permissions": ["identity"],
            "validDomains": config.valid_domains,
        }
        if config.sso_enabled:
            manifest["webApplicationInfo"] = {
                "id": config.bot_app_id,
                "resource": f"api://{config.bot_app_id}",
            }
        # Valid transparent 1x1 PNG. Customers can replace the generated placeholders.
        png = bytes.fromhex(
            "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
            "0000000d49444154789c63606060f80f0001040100b51c0c020000000049454e44ae426082"
        )
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps(manifest, indent=2))
            archive.writestr("color.png", png)
            archive.writestr("outline.png", png)
        return stream.getvalue()
