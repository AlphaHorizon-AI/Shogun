# AI Model Selector & Provider Setup — Multi-Provider Architecture

## Overview

Shogun uses a **three-layer model architecture** for AI provider management:

```
ModelProvider (connection)  ←→  ModelDefinition (specific model)  ←→  ModelRoutingProfile (task routing)
```

| Layer | Table | Purpose |
|-------|-------|---------|
| **ModelProvider** | `model_providers` | API connection: type, credentials, base URL, health status |
| **ModelDefinition** | `models` | Specific model: capabilities, cost/latency profile, context window |
| **ModelRoutingProfile** | `model_routing_profiles` | Rules for routing task types to specific models |

---

## Layer 1: Model Providers

### ORM Model (`shogun/db/models/model_provider.py`)

```python
class ModelProvider(Base, UUIDMixin, AuditMixin):
    __tablename__ = "model_providers"

    provider_type: str          # openai, google, anthropic, openrouter, ollama, local, custom
    name: str                   # Display name
    slug: str                   # Unique identifier (e.g. "openai-my-key")
    base_url: str | None        # Custom endpoint (for Ollama, LM Studio, etc.)
    auth_type: str              # api_key, oauth, none, custom, token
    is_local: bool              # True for ollama, lmstudio, local
    status: str                 # connected, not_configured, error, disabled
    health_status: str          # healthy, degraded, unhealthy, unknown
    config: dict                # JSON blob — holds api_key, models list, etc.
```

### Provider Types (Enum)

```python
class ProviderType(str, Enum):
    OPENAI = "openai"
    GOOGLE = "google"
    ANTHROPIC = "anthropic"
    OPENROUTER = "openrouter"
    OLLAMA = "ollama"
    LOCAL = "local"
    CUSTOM = "custom"
```

### Provider Status Flow

```
not_configured → connected → error / disabled
                     ↑              ↓
                     └──────────────┘
```

### Health Status

```python
class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"       # Default on creation
```

---

## Layer 2: Model Definitions

### ORM Model (`shogun/db/models/model_definition.py`)

```python
class ModelDefinition(Base, UUIDMixin, AuditMixin):
    __tablename__ = "models"

    provider_id: uuid.UUID       # FK → model_providers.id
    model_key: str               # API model identifier (e.g. "gpt-4o", "claude-3.5-sonnet")
    display_name: str            # Human-readable name
    family: str | None           # Model family (e.g. "GPT-4", "Claude 3.5")
    modality: str                # "text" (default), "vision", "audio", etc.
    context_window: int | None   # Max tokens
    supports_tools: bool         # Function calling support
    supports_json_mode: bool     # JSON output mode
    supports_vision: bool        # Image input support
    cost_profile: str            # free, budget, standard, premium
    latency_profile: str         # low, medium, high
    status: str                  # "available" default
    metadata_: dict              # JSON blob for extra metadata

    provider = relationship("ModelProvider", lazy="joined")  # Eager-loaded
```

### Cost & Latency Profiles

```python
class CostProfile(str, Enum):
    FREE = "free"
    BUDGET = "budget"
    STANDARD = "standard"
    PREMIUM = "premium"

class LatencyProfile(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
```

---

## Layer 3: Model Routing Profiles

### ORM Model (`shogun/db/models/model_routing.py`)

```python
class ModelRoutingProfile(Base, UUIDMixin, AuditMixin):
    __tablename__ = "model_routing_profiles"

    name: str                    # e.g. "Balanced (Default)"
    description: str | None
    rules: list                  # JSON array of RoutingRule objects
    is_default: bool             # Only one profile should be default
```

### Routing Rule Schema

```python
class RoutingRule(ShogunBase):
    task_type: str                         # e.g. "*", "reasoning", "coding"
    primary_model_id: uuid.UUID | str      # ModelDefinition ID or provider::model key
    fallback_model_ids: list[uuid.UUID | str]
    latency_bias: str | None               # Optional preference
    cost_bias: str | None                  # Optional preference
```

### Default Profiles (seeded by bootstrap)

| Name | Description |
|------|-------------|
| **Balanced (Default)** | General-purpose routing |
| **Quality First** | Prefers premium models |
| **Cost Optimized** | Prefers budget models |

Each is seeded with a wildcard rule: `task_type: "*"` matching all task types.

---

## Model Selection Format

Models are referenced throughout the system using a **composite key**:

```
{providerUUID}::{modelName}
```

Example: `"a1b2c3d4-...:gpt-4o"`

This format is used in:
- `Agent.bushido_settings.primary_model`
- `Agent.bushido_settings.fallback_models`
- `RoutingRule.primary_model_id`

---

## Setup Wizard Flow (`shogun/api/setup.py`)

The Setup Wizard is a first-run experience that registers providers and configures the primary Shogun agent in a single `POST /setup/complete` call.

### Payload Structure

```python
class SetupCompletePayload(BaseModel):
    language: str = "en"
    operator_name: str = "Daimyo"
    agent_name: str = "Shogun Prime"
    description: str
    persona_id: str | None
    # ... persona knobs (autonomy, tone, risk_tolerance, etc.)
    providers: list[ProviderSetup]      # List of providers to register
    primary_model: str                  # "providerUUID::modelName"
    fallback_models: list[str]          # ["providerUUID::modelName", ...]
    constitution: str | None
    mandate: str | None
    security_incident_acknowledged: Literal[True]
    license_terms_accepted: Literal[True]
```

Both literal-`true` fields are required. The client sends
`security_incident_acknowledged` only after showing the security and
incident-reporting information, and sends `license_terms_accepted` only after the
installer reads and accepts the bundled `LICENSE.md` on the final step. The API
rejects an absent or false value; it does not infer either action from continuing
through the wizard.

### ProviderSetup Schema

```python
class ProviderSetup(BaseModel):
    provider_type: str          # "openai", "anthropic", etc.
    name: str                   # Display name
    auth_type: str = "api_key"
    api_key: str | None         # Stored in config JSON
    base_url: str | None        # Custom endpoint
    models: list[str]           # Available model names
```

### UUID Remapping Logic

The frontend generates temporary UUIDs for providers before they exist in the database. The setup endpoint **remaps these**:

```
Frontend: "temp-uuid-abc::gpt-4o"
                ↓ (after DB insert)
Database: "real-db-uuid-xyz::gpt-4o"
```

Remapping strategy:
1. Extract all unique frontend UUIDs from `primary_model` and `fallback_models`.
2. Match to DB providers by checking which provider's `models` list contains the referenced model names.
3. Fallback: if only one provider exists, map directly.

### Complete Setup Sequence

```
POST /setup/complete
  ├─ 0. Create/update Operator record
  ├─ 1. Create ModelProvider records (upsert by slug)
  │     └─ Slug format: "{provider_type}-{name}".lower().replace(" ", "-")
  ├─ 1b. Build frontend→DB UUID mapping
  ├─ 2. Create/update Shogun Agent with:
  │     └─ bushido_settings.primary_model / fallback_models (remapped)
  ├─ 3. Write constitution.yaml (if provided)
  ├─ 4. Write mandate.md (if provided)
  ├─ 5. Create data directory (if custom path)
  └─ 6. Write setup.json (marks setup_complete=true and stores local security
        acknowledgement and licence-acceptance records)
```

The server generates `security_incident_acknowledgement` rather than accepting a
client-supplied record. It includes the acknowledgement statement and UTC timestamp,
the acknowledging role (`installer` or `primary_admin`), and the installed release's
version, build, identifier, and release date. This record remains in local
`setup.json`, is returned by `GET /setup/status`, and is excluded from telemetry. It
records that the information was presented and acknowledged; it is not evidence of a
regulatory conformity assessment or of incident-response performance.

The server also generates `license_terms_acceptance`, including a UTC timestamp,
the installed release identity, and the SHA-256 hash of the exact `LICENSE.md` that
was shown. The legal record remains local, is returned by `GET /setup/status`, and is
excluded from telemetry.

### API Key Storage

API keys are stored in the `config` JSON blob of the `ModelProvider` record:

```json
{
    "api_key": "sk-abc123...",
    "models": ["gpt-4o", "gpt-4o-mini", "o1-preview"]
}
```

> **Note**: API keys are stored in plaintext in the SQLite database. The Vault system (`shogun/vault/`) is available for encrypted secret storage but is not yet integrated into the provider flow.

---

## Services

### ModelProviderService (`shogun/services/model_service.py`)

Extends `BaseService[ModelProvider]` with:
- `get_by_slug(slug)` — Find provider by unique slug

### ModelDefinitionService

Extends `BaseService[ModelDefinition]` with:
- `get_by_provider(provider_id)` — List all models for a provider

### ModelRoutingProfileService

Extends `BaseService[ModelRoutingProfile]` with:
- `get_default()` — Get the default routing profile

All services inherit generic CRUD from `BaseService[T]`: `get_by_id`, `get_all`, `create`, `update`, `delete`.

---

## API Endpoints

### Provider CRUD (`/api/model-providers`)

| Method | Path | Description |
|--------|------|-------------|
| `GET /model-providers` | List all providers |
| `POST /model-providers` | Register a new provider |
| `PATCH /model-providers/{id}` | Update provider config |
| `POST /model-providers/{id}/test` | Test provider connectivity (stub) |
| `DELETE /model-providers/{id}` | Remove a provider |

Provider creation/update/deletion emits **auth events** via `EventLogger.emit_auth_event()`.

### Routing Profile CRUD (`/api/model-routing-profiles`)

| Method | Path | Description |
|--------|------|-------------|
| `GET /model-routing-profiles` | List all profiles |
| `POST /model-routing-profiles` | Create a profile |
| `PATCH /model-routing-profiles/{id}` | Update a profile |
| `DELETE /model-routing-profiles/{id}` | Delete a profile |

### Setup Endpoints (`/api/setup`)

| Method | Path | Description |
|--------|------|-------------|
| `GET /setup/status` | Check if setup is complete |
| `POST /setup/complete` | Process the full wizard payload |
| `POST /setup/reset` | Reset setup state (triggers wizard again) |

---

## Key Design Decisions

1. **Config-in-JSON**: Provider configuration (API keys, model lists) is stored as a JSON blob in the `config` column rather than as separate columns. This allows flexible, provider-specific configuration without schema migrations.

2. **Slug-based dedup**: Providers are deduplicated by slug (`{provider_type}-{name}` normalized). The setup wizard upserts rather than creating duplicates.

3. **Composite model keys**: The `providerUUID::modelName` format allows a single string to fully identify both the provider connection and the specific model, which simplifies storage in agent settings.

4. **Lazy relationship loading**: `ModelDefinition.provider` uses `lazy="joined"` for eager loading — provider info is always available when querying models.

5. **Local provider detection**: Providers with type `ollama`, `lmstudio`, or `local` automatically get `is_local=True`, which affects UI presentation and health check behavior.

6. **Provider test endpoint**: `POST /model-providers/{id}/test` is a stub (`test_not_implemented`). Health checking is not yet wired up to actually ping provider APIs.
