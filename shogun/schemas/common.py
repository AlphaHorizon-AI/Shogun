"""Common schemas, envelopes, and shared types used across all modules."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


# ── Standard API Response Envelope ────────────────────────────


class ApiError(BaseModel):
    """Error detail within an API response."""

    code: str
    message: str


class ApiResponse(BaseModel, Generic[T]):
    """Standard JSON response envelope for all endpoints."""

    success: bool = True
    data: T | None = None
    error: ApiError | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


class PaginationMeta(BaseModel):
    """Pagination metadata for list endpoints."""

    total: int = 0
    page: int = 1
    per_page: int = 50
    pages: int = 1


# ── Shared Enum Types ────────────────────────────────────────


class AgentType(str, Enum):
    SHOGUN = "shogun"
    SAMURAI = "samurai"


class AgentStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    IDLE = "idle"
    PAUSED = "paused"
    SUSPENDED = "suspended"
    ERROR = "error"
    ARCHIVED = "archived"


class SpawnPolicy(str, Enum):
    MANUAL = "manual"
    AUTO = "auto"
    SHOGUN_DECIDES = "shogun_decides"


class ProviderType(str, Enum):
    OPENAI = "openai"
    GOOGLE = "google"
    ANTHROPIC = "anthropic"
    OPENROUTER = "openrouter"
    OLLAMA = "ollama"
    LOCAL = "local"
    CUSTOM = "custom"


class AuthType(str, Enum):
    API_KEY = "api_key"
    OAUTH = "oauth"
    NONE = "none"
    CUSTOM = "custom"
    TOKEN = "token"


class ProviderStatus(str, Enum):
    CONNECTED = "connected"
    NOT_CONFIGURED = "not_configured"
    ERROR = "error"
    DISABLED = "disabled"


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ConnectorType(str, Enum):
    API = "api"
    TOOL = "tool"
    MCP = "mcp"
    FILESYSTEM = "filesystem"
    DATABASE = "database"
    QUEUE = "queue"
    CUSTOM = "custom"


class ConnectorSource(str, Enum):
    BUILTIN = "builtin"
    IMPORTED = "imported"
    SKILL = "skill"
    MANUAL = "manual"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SecurityTier(str, Enum):
    SHRINE = "shrine"
    GUARDED = "guarded"
    TACTICAL = "tactical"
    CAMPAIGN = "campaign"
    RONIN = "ronin"


class SkillType(str, Enum):
    SINGLE = "single"
    BUNDLE = "bundle"
    SPECIALIZATION = "specialization"
    TOOLING = "tooling"
    WORKFLOW = "workflow"


class SkillStatus(str, Enum):
    AVAILABLE = "available"
    INSTALLED = "installed"
    DISABLED = "disabled"
    QUARANTINED = "quarantined"
    ERROR = "error"
    ARCHIVED = "archived"


class MissionType(str, Enum):
    OPERATOR_REQUEST = "operator_request"
    SUBTASK = "subtask"
    MAINTENANCE = "maintenance"
    SKILL_INSTALL = "skill_install"
    SECURITY_CHECK = "security_check"
    SYNC = "sync"


class MissionStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class MissionPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MemoryType(str, Enum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    PERSONA = "persona"
    SKILLS = "skills"


class DecayClass(str, Enum):
    """Controls how fast memory relevance decays over time."""

    FAST = "fast"          # Temporary episodic details — hours to days
    MEDIUM = "medium"      # Active workflows — days to weeks
    SLOW = "slow"          # Durable facts — weeks to months
    STICKY = "sticky"      # Important long-term operational memories — months+
    PINNED = "pinned"      # No normal decay — only manual or policy-driven


class Severity(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"
    CRITICAL = "critical"


class Tone(str, Enum):
    ANALYTICAL = "analytical"
    DIRECT = "direct"
    SUPPORTIVE = "supportive"
    STRATEGIC = "strategic"


class LevelEnum(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ToolUsageStyle(str, Enum):
    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"


class SecurityBias(str, Enum):
    STRICT = "strict"
    BALANCED = "balanced"
    OPEN = "open"


class MemoryStyle(str, Enum):
    CONSERVATIVE = "conservative"
    FOCUSED = "focused"
    EXPANSIVE = "expansive"


class CostProfile(str, Enum):
    FREE = "free"
    BUDGET = "budget"
    STANDARD = "standard"
    PREMIUM = "premium"


class LatencyProfile(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SnapshotType(str, Enum):
    MEMORY = "memory"
    CONFIG = "config"
    FULL = "full"


class BushidoJobType(str, Enum):
    MEMORY_CONSOLIDATION = "memory_consolidation"
    PERFORMANCE_AUDIT = "performance_audit"
    SKILL_HEALTH_CHECK = "skill_health_check"
    PERSONA_DRIFT_CHECK = "persona_drift_check"
    CUSTOM_TASK = "custom_task"


class BushidoFrequency(str, Enum):
    ONE_OFF = "one-off"
    HOURLY = "hourly"
    NIGHTLY = "nightly"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class BushidoJobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TriggerMode(str, Enum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    EVENT = "event"


# ── Shared Base Schemas ──────────────────────────────────────


class ShogunBase(BaseModel):
    """Base model with common config for all Shogun Pydantic schemas."""

    model_config = {"from_attributes": True}


class TimestampMixin(BaseModel):
    """Mixin for created_at / updated_at."""

    created_at: datetime
    updated_at: datetime


class IdentityMixin(BaseModel):
    """Mixin for id + timestamps."""

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
