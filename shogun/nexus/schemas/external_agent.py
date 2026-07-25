"""Pydantic schemas for ExternalAgent."""

from __future__ import annotations

import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_serializer


class ExternalAgentBase(BaseModel):
    name: str = Field(..., description="Name of the external agent, e.g. Microsoft 365 Sales Agent")
    platform: str = Field(..., description="Platform type (microsoft_365, salesforce, google, servicenow, custom)")
    is_active: bool = Field(True, description="True if the agent is allowed to connect")


class ExternalAgentRegister(BaseModel):
    """Schema used to register an external agent."""
    name: str = Field(..., description="Name of the external agent")
    platform: str = Field(..., description="Platform type")
    token: str | None = Field(None, description="Optional custom authentication token. If not provided, one will be generated.")
    endpoint_url: str | None = Field(None, description="Callback URL for bidirectional communication. Shogun can dispatch tasks to this URL.")
    direction: str = Field("bidirectional", description="Communication direction: inbound, outbound, or bidirectional")


class ExternalAgentResponse(ExternalAgentBase):
    id: uuid.UUID
    token: str = Field(..., description="Authentication API token for the agent")
    endpoint_url: str | None = Field(None, description="Callback URL for outbound dispatch")
    direction: str = Field("bidirectional", description="Communication direction")
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("token")
    def redact_token(self, _token: str) -> str:
        return "********"
