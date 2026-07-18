# Order 18 — Shogun AFM: Expose `decay_type` in `store_memory` Tool

## Build Paper  
### True Sticky Memory Support, Explicit Decay Control, and Better Archive Behavior

---

## 1. Executive Summary

This build paper defines the implementation of **Order 18: Expose `decay_type` in the `store_memory` tool**.

The Shogun Archives backend already supports multiple memory decay behaviors, including **sticky** memory. However, the current `store_memory` tool does not expose `decay_type` as a callable parameter. This creates a functional gap: agents cannot explicitly mark certain memories as sticky, persistent, or subject to a specific decay behavior at the time of storage.

The purpose of this build is to expose `decay_type` safely and cleanly through the memory tool layer, while preserving backward compatibility with all existing memory behavior.

This is a small backend/tooling change with high strategic value.

The core rule is:

> Agents should be able to explicitly store memories with an approved decay behavior, but the Archive backend and permission layer must remain the source of truth.

---

## 2. Problem Statement

Today, Shogun can store memory, but the decay behavior is either implicit, inferred, or handled internally by the backend.

This is acceptable for normal memories, but not for memories that must reliably remain available across future runs.

Examples:

- persistent user instructions
- recurring analysis signals
- stable operating conventions
- important Shogun project facts
- long-term strategic signals
- system behavior preferences
- durable lessons from failed runs
- high-value stack findings
- skill optimization conclusions

The issue is:

```text
The Archive backend supports decay behavior.
The store_memory tool does not expose it.
```

That means agents may attempt to work around the limitation by increasing importance scores instead of using the correct decay type.

That is not clean.

The right fix is to expose `decay_type` directly.

---

## 3. Goal

Add an optional `decay_type` parameter to the `store_memory` tool.

The tool should allow agents and internal Shogun services to store memory with explicit decay behavior.

Example:

```json
{
  "content": "Michael prefers Shogun communication to be direct, non-sycophantic, and strategically precise.",
  "importance": 9,
  "memory_type": "preference",
  "decay_type": "sticky",
  "tags": ["user_preference", "communication"]
}
```

The expected result is that the memory is stored as sticky and retrieved according to the backend’s sticky-memory retrieval rules.

---

## 4. Non-Goals

This build must not become a redesign of the memory system.

Do not build:

- a new memory backend
- a new archive schema unless strictly required
- a separate retrieval system
- a separate memory UI product
- a new vector database layer
- a new long-term memory policy engine
- a new memory optimizer
- a generic knowledge graph

This is a targeted change:

> Expose the existing decay behavior through the `store_memory` tool and make retrieval honor it correctly.

---

## 5. Core Design Principle

The tool layer should expose the parameter.

The backend should validate and enforce it.

The retrieval layer should respect it.

The UI should make it visible where useful.

The audit layer should record it.

```text
Tool schema
  → validates decay_type
  → Archive backend stores decay_type
  → Retrieval honors decay_type
  → Audit logs decay_type
```

---

## 6. Required Behavior

### 6.1 Backward Compatibility

If `decay_type` is omitted, Shogun must behave exactly as it does today.

Required behavior:

```json
{
  "content": "Some memory",
  "importance": 6
}
```

must still work.

No existing flow, agent, tool call, or memory should break.

Default rule:

```text
If decay_type is not provided, use the current backend default.
```

Do not change historical default behavior unless explicitly configured.

---

### 6.2 Existing Enum Must Be Used

The coding agent must first inspect the current Archives backend and identify the existing decay type enum or equivalent constants.

Do not invent a new enum if one already exists.

Implementation rule:

```text
Use the existing backend-supported decay_type values as the canonical source of truth.
```

If the backend currently has values such as:

```text
standard
sticky
linear
exponential
ttl
archive_only
```

then expose those.

If the backend uses different names, use the existing names.

The build must align the tool schema to the existing backend contract.

---

### 6.3 Sticky Memory

`sticky` is the most important decay type for this build.

Sticky memories should:

- not decay through normal importance reduction
- remain eligible for retrieval across sessions
- be prioritized in context injection
- be retrievable even when normal memories would be suppressed
- be visible as sticky in logs/UI where relevant

However, sticky does **not** mean unlimited or unsafe.

Sticky retrieval must still respect:

- context budget
- permission boundaries
- memory scope
- privacy rules
- project/user/agent boundaries
- maximum sticky memory limits if configured

Sticky means:

> This memory should remain persistently eligible and high-priority unless explicitly deleted, downgraded, or superseded.

---

## 7. Recommended Tool Schema

Update the `store_memory` tool schema with:

```json
{
  "decay_type": {
    "type": "string",
    "description": "Optional decay behavior for the stored memory. If omitted, the backend default is used.",
    "enum": ["<existing_backend_decay_types>"],
    "default": null
  }
}
```

Important:

- Use actual existing backend enum values.
- Do not hardcode unsupported values.
- Make the field optional.
- Do not require callers to supply it.
- Invalid values must be rejected clearly.

---

## 8. Suggested Canonical Parameter Contract

The final tool call should support at least this shape:

```json
{
  "content": "string",
  "importance": 1,
  "memory_type": "string",
  "tags": ["string"],
  "source": "string",
  "decay_type": "sticky",
  "metadata": {}
}
```

`decay_type` should be passed through from the tool call to the archive storage layer.

---

## 9. Validation Rules

### 9.1 Valid Values

`decay_type` must be one of the backend-supported enum values.

If invalid:

```json
{
  "error": "Invalid decay_type",
  "allowed_values": ["default", "sticky", "..."]
}
```

### 9.2 Missing Value

If missing:

```text
Use current default behavior.
```

### 9.3 Null Value

If explicitly null:

```text
Treat as omitted.
```

### 9.4 Sticky Value

If `decay_type = sticky`, store as sticky and ensure retrieval honors sticky behavior.

---

## 10. Permission and Safety Rules

Sticky memory is powerful because it can influence future behavior.

Therefore, add basic safety controls.

### 10.1 Configurable Sticky Permission

Add configuration:

```json
{
  "memory": {
    "allow_agent_sticky_memory": true,
    "sticky_memory_requires_min_importance": 7,
    "sticky_memory_allowed_types": [
      "preference",
      "signal",
      "analysis",
      "project_fact",
      "system_convention"
    ],
    "max_sticky_memories_in_context": 20
  }
}
```

If Shogun already has memory governance configuration, extend that instead of creating a new config island.

### 10.2 Default Behavior

Recommended default:

```text
Agents may create sticky memories only if:
- decay_type = sticky is allowed by config
- importance is high enough
- memory_type is allowed
```

If not allowed, the system should either:

1. reject the call, or  
2. downgrade to default decay and log the downgrade.

Preferred behavior:

```text
Reject clearly rather than silently downgrade.
```

Silent downgrades make debugging memory behavior difficult.

---

## 11. Retrieval Behavior

The retrieval layer must honor `decay_type`.

### 11.1 Sticky Retrieval Rule

Sticky memories should be considered before normal decaying memories when building context.

Recommended retrieval order:

```text
1. Scope-filtered sticky memories
2. High-importance stable memories
3. Recent relevant memories
4. Semantic/vector memories
5. Low-priority archive memories
```

### 11.2 Budgeting

Sticky memories must not flood the context window.

Add a configurable cap:

```json
{
  "memory": {
    "max_sticky_memories_in_context": 20,
    "max_sticky_context_tokens": 2000
  }
}
```

If more sticky memories exist than fit, rank by:

1. scope match
2. importance
3. recency
4. tag relevance
5. memory type priority
6. retrieval relevance score

### 11.3 Scope Respect

Sticky memories must still respect scope.

A sticky memory for one project should not automatically bleed into another unless global scope is explicitly set.

Recommended scopes:

```text
global
user
project
agent
flow
stack
session
```

Use the existing scope model if Shogun already has one.

---

## 12. Storage Layer Changes

The coding agent must inspect the current storage model.

Possible scenarios:

### Scenario A — `decay_type` already exists in database

If the database already has a `decay_type` column/field:

- pass the value through from tool to backend
- validate enum
- update tests
- update retrieval
- update audit logs

No migration needed.

### Scenario B — `decay_type` exists in backend object but not database

Add persistence.

Migration:

```sql
ALTER TABLE memories ADD COLUMN decay_type TEXT;
```

Default:

```text
NULL or backend_default
```

Do not rewrite all old memories unless required.

### Scenario C — backend supports decay internally but not as a field

Add explicit field to the memory record and map it to the existing decay logic.

### Scenario D — no real enum exists

If the previous assumption is wrong and the backend does not actually have a formal enum, create one minimally.

Recommended enum:

```text
default
sticky
decaying
ttl
archive_only
```

Only do this if no existing enum exists.

---

## 13. API Changes

Update any internal memory APIs that call storage.

Example:

```http
POST /api/v1/memory/store
```

Request body should allow:

```json
{
  "content": "string",
  "importance": 8,
  "memory_type": "analysis",
  "tags": ["signal"],
  "decay_type": "sticky"
}
```

Response should include:

```json
{
  "memory_id": "uuid",
  "stored": true,
  "decay_type": "sticky"
}
```

---

## 14. Tool Description Update

Update the agent-facing tool description.

Recommended wording:

```text
Use store_memory to save durable information into Shogun Archives. Optionally set decay_type to control memory decay behavior. Use sticky only for important long-term memories that should remain persistently eligible for retrieval, such as stable user preferences, project facts, durable analysis signals, and important operating conventions.
```

Also include warning:

```text
Do not use sticky for temporary observations, low-confidence claims, one-off task details, or information likely to change soon.
```

---

## 15. Memory Type Guidance

Add clear guidance for when to use sticky.

### Good sticky candidates

```text
Stable user preference
Project architecture decision
Long-term Shogun convention
Repeated analysis signal
Important lesson learned
Durable skill improvement
Validated operating rule
```

### Bad sticky candidates

```text
Temporary task state
One-off error
Low-confidence assumption
Outdated news
Transient file path
Single conversation detail
Speculative idea
Unverified claim
```

---

## 16. Audit Events

Update audit logging to include `decay_type`.

Required event:

```text
memory.stored
```

Payload should include:

```json
{
  "memory_id": "uuid",
  "memory_type": "analysis",
  "importance": 9,
  "decay_type": "sticky",
  "tags": ["signal", "analysis"],
  "source": "store_memory_tool",
  "agent_id": "max",
  "run_id": "uuid"
}
```

Also add events where relevant:

```text
memory.sticky.rejected
memory.decay_type.invalid
memory.decay_type.defaulted
memory.retrieval.sticky_injected
```

Do not create a separate logging system.

Use Shogun’s existing EventLogger/audit pipeline.

---

## 17. UI Changes

This is a small feature, but the UI should expose enough visibility for debugging.

### 17.1 Memory Detail View

Show:

```text
Decay Type: sticky
```

or equivalent.

### 17.2 Memory List Filters

Add optional filter:

```text
Decay Type
```

Values:

```text
All
Default
Sticky
Other backend-supported values
```

### 17.3 Store Memory Tester / Tool Debugger

If Shogun has a tool testing UI, add a dropdown:

```text
decay_type
```

Default:

```text
backend default
```

### 17.4 Sticky Badge

In archive/memory views, sticky memories should display a badge:

```text
Sticky
```

This is useful for debugging why certain memories keep appearing.

---

## 18. Retrieval Debugging

Add retrieval debug output where relevant.

When memory context is built, logs should indicate:

```text
Sticky memories considered: 12
Sticky memories injected: 5
Sticky memories skipped due to token budget: 7
```

This avoids confusion when sticky memories are stored but not injected because of scope or budget.

---

## 19. Tests

### 19.1 Unit Tests

Add tests for:

- `store_memory` works without `decay_type`
- `store_memory` accepts valid `decay_type`
- invalid `decay_type` is rejected
- null `decay_type` behaves like omitted
- sticky memory is stored correctly
- sticky memory respects permission/config
- audit event includes `decay_type`
- existing calls remain compatible

### 19.2 Storage Tests

Test:

- memory persists with `decay_type`
- old memories without `decay_type` still load
- migration works if required
- retrieval can filter by `decay_type`

### 19.3 Retrieval Tests

Test:

- sticky memories are prioritized
- sticky memories respect scope
- sticky memories respect token cap
- sticky memories do not decay
- non-sticky memories continue current behavior

### 19.4 Tool Integration Tests

Test agent/tool call:

```json
{
  "content": "This is a sticky test memory.",
  "importance": 8,
  "memory_type": "analysis",
  "decay_type": "sticky",
  "tags": ["test"]
}
```

Expected:

```text
Stored successfully with decay_type=sticky.
```

---

## 20. Acceptance Criteria

The build is complete when:

1. `store_memory` accepts optional `decay_type`.
2. Existing `store_memory` calls without `decay_type` still work.
3. Tool schema exposes backend-supported decay types.
4. Invalid `decay_type` values are rejected.
5. Sticky memories can be stored through the tool.
6. Sticky memories persist correctly.
7. Retrieval honors sticky behavior.
8. Sticky memories respect scope and context budget.
9. Sticky memory use is governed by config/permission.
10. Audit events include `decay_type`.
11. Memory UI shows decay type.
12. Sticky memories are visibly identifiable.
13. Tests cover storage, retrieval, validation, and backward compatibility.
14. No existing memory behavior is broken.
15. Documentation/tool description explains when to use sticky.

---

## 21. Recommended Implementation Order

### Step 1 — Inspect Existing Memory Backend

Find:

- decay enum
- archive schema
- memory model
- retrieval logic
- current defaults

### Step 2 — Update Tool Schema

Add optional `decay_type`.

Use existing enum values.

### Step 3 — Update Validation

Reject unsupported decay types.

Preserve default behavior when omitted.

### Step 4 — Pass Through to Backend

Ensure `decay_type` reaches storage.

### Step 5 — Update Persistence

Add migration only if needed.

### Step 6 — Update Retrieval

Ensure sticky is prioritized and does not decay.

### Step 7 — Add Config/Safety Controls

Add minimal sticky governance.

### Step 8 — Update Audit Logging

Include `decay_type` in memory events.

### Step 9 — Update UI

Show decay type and sticky badge.

### Step 10 — Add Tests

Cover backward compatibility and sticky behavior.

---

## 22. Example Usage

### 22.1 Store Sticky User Preference

```json
{
  "content": "User prefers direct, non-sycophantic feedback and wants sound arguments defended when questioned.",
  "importance": 10,
  "memory_type": "preference",
  "decay_type": "sticky",
  "tags": ["user_preference", "communication"]
}
```

### 22.2 Store Sticky Project Fact

```json
{
  "content": "Shogun uses Agent Stacks for reusable hierarchical flow execution and Stack Orchestrator instances to manage individual stack runs.",
  "importance": 9,
  "memory_type": "project_fact",
  "decay_type": "sticky",
  "tags": ["shogun", "agent_stacks", "architecture"]
}
```

### 22.3 Store Normal Temporary Memory

```json
{
  "content": "The current coding run failed because a test expected the old API response shape.",
  "importance": 5,
  "memory_type": "task_state",
  "tags": ["temporary", "test_failure"]
}
```

No `decay_type` needed.

---

## 23. Critical Constraints for Coding Agent

The coding agent must follow these constraints:

1. Do not redesign the memory system.
2. Do not break existing `store_memory` calls.
3. Do not invent decay values if the backend already defines them.
4. Do not silently downgrade invalid sticky requests.
5. Do not allow sticky memories to bypass scope rules.
6. Do not allow sticky memories to flood context.
7. Do not bypass existing EventLogger/audit pipeline.
8. Do not create a separate memory persistence layer.
9. Do not make all high-importance memories sticky automatically.
10. Do not treat sticky as permanent truth; it must still be editable/deletable.
11. Do not store temporary observations as sticky by default.
12. Keep this build small and targeted.

---

## 24. Strategic Value

This feature is small but important.

It gives Shogun cleaner long-term memory control.

Instead of using high importance scores as a workaround, agents can now explicitly say:

```text
This memory should be sticky.
```

That matters for:

- long-running Stack Orchestrator runs
- Agent Stack continuity
- SkillOpt lessons
- OpenClaw College skill conventions
- project-specific operating rules
- user preference memory
- durable analysis signals
- reduced repeated explanations
- better context injection

This aligns with Shogun’s broader direction:

> governed agents need governed memory.

---

## 25. Final Design Sentence

Build Order 18 around this sentence:

> **Expose `decay_type` in `store_memory` so Shogun agents can explicitly create sticky and other decay-controlled memories, while preserving backend authority, posture-safe retrieval, context budgeting, auditability, and backward compatibility.**

---
