# Append-only HMAC Audit Log — Chain-Consistency Evidence

## Overview

Shogun uses a **two-layer logging architecture** that can support incident
investigation and an organisation's NIS2, SOC 2, or EU AI Act assessment. The
architecture does not establish compliance or prove that every event was
captured.

| Layer | Storage | Purpose | Retention | Mutability |
|-------|---------|---------|-----------|------------|
| **Layer 1** — Operational Log | Main SQLite (`shogun.db` → `execution_events` table) | Fast, searchable event log | Operator policy | Mutable (can be cleared) |
| **Layer 2** — Append-only HMAC Chain | Separate SQLite (`data/audit_immutable.db`) | Chain-consistency evidence for instrumented events | Operator policy | The application service exposes append only; host/database administrators can still alter or remove storage |

Instrumented Shogun actions emit through the `EventLogger` service, which
dual-writes to both layers. Operators must verify coverage for their deployment
and must define, implement, and test their own retention and protected-backup
policy.

---

## Architecture

### File Locations

- **Append-only audit DB** (legacy filename): `{PROJECT_ROOT}/data/audit_immutable.db`
- **Service**: `shogun/services/immutable_audit.py`
- **Event emitter**: `shogun/services/event_logger.py`
- **ORM model (Layer 1)**: `shogun/db/models/execution_event.py`
- **API routes**: `shogun/api/logs.py`
- **Schemas**: `shogun/schemas/logs.py`

### HMAC Hash Chain

Each record is cryptographically chained to the previous one using **HMAC-SHA256**:

```
Record N:
  message = "{event_id}|{timestamp}|{category}|{event_type}|{action}|{result}|{prev_hash}"
  record_hash = HMAC-SHA256(key, message)

Record N+1:
  prev_hash = Record N's record_hash
  ...
```

- The first record uses `prev_hash = "GENESIS"`.
- HMAC key: `b"shogun-audit-integrity-key-v1"` (currently hardcoded). This is a
  material limitation: an actor able to read the application code and modify
  the database can recompute covered hashes. A production deployment should
  use protected, installation-specific key material and a documented rotation
  and recovery design.

### Audit Chain Table Schema (`audit_chain`)

```sql
CREATE TABLE audit_chain (
    seq_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    event_category TEXT NOT NULL,      -- auth, memory, tool, model, policy, incident, decision, oversight, risk, governance, system
    event_type TEXT NOT NULL,          -- e.g. "memory.write", "auth.credential_added"
    severity TEXT NOT NULL DEFAULT 'info',
    action TEXT NOT NULL,
    result TEXT NOT NULL DEFAULT 'success',
    user_id TEXT,
    agent_id TEXT,
    session_id TEXT,
    trace_id TEXT,                     -- links related events into a workflow chain
    model_used TEXT,
    provider_used TEXT,
    tool_name TEXT,
    policy_ref TEXT,
    policy_decision TEXT,
    policy_reason TEXT,
    risk_score TEXT DEFAULT 'low',
    detail TEXT DEFAULT '{}',          -- JSON blob
    memory_ids TEXT DEFAULT '[]',      -- JSON array
    prev_hash TEXT NOT NULL,           -- hash of previous record (or "GENESIS")
    record_hash TEXT NOT NULL          -- HMAC-SHA256 of this record
);
```

Indexed on: `timestamp`, `event_category`, `trace_id`.

---

## Core Functions

### `immutable_audit.append(**kwargs)` — Application Append Operation

```python
immutable_audit.append(
    event_id="evt_abc123",
    event_category="memory",
    event_type="memory.write",
    action="Stored operator name in Archives",
    result="success",
    severity="info",
    agent_id="...",
    trace_id="trc_xyz789",
    detail={"title": "Operator name"},
)
```

- Automatically fetches the last record's hash to chain from.
- Computes HMAC-SHA256 and inserts atomically.
- This module exposes no update or delete method. That application-level design
  does not prevent an administrator or process with filesystem/database access
  from changing or deleting the SQLite file.

### `immutable_audit.verify_chain()` — Integrity Verification

Walks the entire chain sequentially and verifies:
1. Each record's `prev_hash` matches the previous record's `record_hash`.
2. Each record's `record_hash` matches the recomputed HMAC.

Returns:
```python
{
    "total_records": 1500,
    "verified_records": 1500,
    "chain_intact": True,
    "last_verified_at": "2026-06-04T19:00:00Z",
    "message": "All 1500 available audit records matched the HMAC chain. This check does not prove record completeness."
}
```

If tampered:
```python
{
    "total_records": 1500,
    "verified_records": 742,
    "broken_at": 743,        # seq_id of the broken record
    "chain_intact": False,
    "message": "HMAC mismatch at record seq_id=743: record may have been tampered with."
}
```

### `immutable_audit.export_records(...)` — Governance-Evidence Export

Exports filtered records for auditor review. Supports filters:
- `category` — event category
- `trace_id` — specific workflow chain
- `date_from` / `date_to` — date range
- `limit` — max records (default 10,000)

---

## EventLogger — The Central Emitter

The `EventLogger` class in `shogun/services/event_logger.py` is the central
integration point for instrumented event emission. It dual-writes to both
layers; code paths that do not emit an event are not made complete merely by
the existence of the service.

### Core Method

```python
event_id = await EventLogger.emit(
    category="memory",
    event_type="memory.write",
    action="Stored operator name in Archives",
    agent_id=str(agent.id),
    user_id="operator",
    detail={"title": "Operator name"},
)
```

### Trace Correlation

```python
async with EventLogger.trace() as trace_id:
    await EventLogger.emit(..., trace_id=trace_id)
    await EventLogger.emit(..., trace_id=trace_id)  # linked
```

Trace IDs are formatted as `trc_{uuid_hex[:16]}`.

### Category-Specific Convenience Methods

| Method | Category | Example Event Types |
|--------|----------|-------------------|
| `emit_model_event()` | `model` | model selection, inference |
| `emit_memory_event()` | `memory` | memory.write, memory.forget |
| `emit_tool_event()` | `tool` | tool invocations |
| `emit_policy_event()` | `policy` | policy decisions |
| `emit_auth_event()` | `auth` | credential added/removed |
| `emit_incident_event()` | `incident` | chain broken, anomalies |
| `emit_decision_event()` | `decision` | EU AI Act Article 14/15 |
| `emit_oversight_event()` | `oversight` | human oversight events |
| `emit_risk_event()` | `risk` | sensitive data, bias warnings |
| `emit_governance_event()` | `governance` | mode changes, framework applied |
| `emit_system_event()` | `system` | startup, shutdown, backup |

### Governance Metadata Fields

The `ExecutionEvent` ORM model includes governance fields that may be relevant
to an EU AI Act assessment:
- `confidence_score: float` — AI decision confidence
- `governance_flags: dict` — governance metadata
- `use_case_context: dict` — context for the AI use case

Populating these fields does not determine whether the EU AI Act applies and
does not establish conformity.

---

## API Endpoints

All routes are under `/api/logs`:

| Method | Path | Description |
|--------|------|-------------|
| `GET /logs` | List operational events (filterable by severity, category, trace_id, agent_id, date range) |
| `GET /logs/categories` | Event count by category (dashboard summary) |
| `GET /logs/trace/{trace_id}` | Reconstruct a full workflow chain |
| `GET /logs/audit/verify` | Check available HMAC-chain links and covered fields |
| `GET /logs/audit/export` | Export audit records (JSON or CSV) |
| `DELETE /logs` | Clear operational logs only; this route does not delete the separate audit database |

> When operational logs are cleared through `DELETE /logs`, Shogun attempts to
> record that action in the separate append-only audit log. Verify the write and
> preserve an external copy when the record is material to an investigation.

---

## Key Design Decisions

1. **Separate SQLite database** — The append-only audit chain lives in
   `data/audit_immutable.db`, separate from `shogun.db`. This reduces accidental
   coupling to operational-log maintenance; it does not prevent host-level
   deletion or alteration.
2. **WAL journal mode** — `PRAGMA journal_mode=WAL` for concurrent read/write performance.
3. **Sync writes** — The append-only audit layer uses synchronous SQLite (not async SQLAlchemy). The operational layer uses async SQLAlchemy.
4. **Genesis record** — The chain starts from a `"GENESIS"` sentinel value, not a null.
5. **Lazy initialization** — The audit table is created on first use via `_ensure_table()` with a module-level `_initialized` flag.
6. **Error isolation** — If either layer fails to write, the error is logged but does not crash the operation. Both writes are independent.

## Assurance Boundaries

- The HMAC covers selected fields, not every column in each record.
- Verification checks available records and links; it cannot identify a
  completely omitted event on its own.
- The current hardcoded HMAC key is not a protected installation secret.
- SQLite is not write-once storage. Administrators with host access can alter
  or remove it.
- The application does not automatically enforce one universal audit-retention
  period. The deploying organisation must define and test retention, backup,
  access control, clock synchronization, export, and incident-evidence policy.
- Passing chain verification can support investigation and assessment, but is
  not a certification, legal conclusion, or guarantee of security or
  compliance.
