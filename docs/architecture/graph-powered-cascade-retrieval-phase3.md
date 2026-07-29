# Graph-Powered Cascade Retrieval — Phase 3

## Purpose

Phase 3 makes Shogun actively use the Kiroku MemoryGraph built in Phase 2. It
combines scoped vector retrieval with relationship expansion, deterministic
verification, Gensui/ToolGate filtering, and bounded context-pack construction.

The existing memory path remains the fallback. The external `jcode` project is
conceptual inspiration only; no source code is copied, imported, vendored,
translated, or derived from it.

## Retrieval flow

1. Phase 1 resolves the active tenant, user, workspace, project, conversation,
   topic, workflow, sensitivity ceiling, and agent boundaries.
2. Qdrant proposes semantic seed memories, pre-authorized by relational IDs.
3. Kiroku follows approved graph relationships to depth one or two.
4. Every graph-derived memory is authorized again against `memory_records`.
5. The verifier withholds superseded, conflicting, review-required, deprecated,
   expired, stale, or policy-blocked memories.
6. The context-pack builder ranks and trims accepted memories to a fixed token
   budget, then persists an auditable pack for the agent and diagnostics UI.

Graph traversal cannot bypass Phase 1 scope rules. A relationship is a relevance
signal, not an authorization grant.

## Rollout controls

Two independent settings control rollout:

- `MEMORY_RETRIEVAL_MODE=legacy|shadow|cascade` controls Phase 1 scoped cascade.
- `MEMORY_GRAPH_RETRIEVAL_MODE=off|shadow|active` controls Phase 3 graph use.

Recommended production sequence:

1. Finish the Phase 2 backfill and verify it is complete.
2. Use `MEMORY_RETRIEVAL_MODE=cascade` and
   `MEMORY_GRAPH_RETRIEVAL_MODE=shadow`.
3. Compare `graph_shadow_result_memory_ids`, verifier exclusions, warnings, and
   context-pack token estimates in retrieval diagnostics.
4. Set `MEMORY_GRAPH_RETRIEVAL_MODE=active` after the shadow results are clean.

`off` preserves the Phase 1 behavior. `shadow` builds and audits graph context
without changing returned memories. `active` returns only the verified,
context-budgeted result set.

## Governance

- Graph expansion follows only the configured relationship allowlist.
- Traversal depth is hard-capped at two.
- SQL scope and sensitivity authorization is applied after expansion.
- Gensui's `MEMORY_READ` posture can block retrieval.
- Local and Gensui advanced content rules can block or require confirmation for
  individual memories; such memories are not injected.
- Cross-agent graph reads are disabled by default. If explicitly enabled, only
  classified memories with an exact shared team/workspace/project/workflow/
  conversation/topic boundary may cross agent ownership.
- Graph errors fail safely to the scoped vector result set. A Gensui denial does
  not use that fallback; memory results are withheld.

## Context packs

Context packs group memories into relevant facts, recent context, procedures,
preferences, and capabilities. They record included IDs, graph-expanded IDs,
exclusions, warnings, policy notes, scope, and an estimated token count.

Packs expire after the configured retention period. Expired packs are purged
during subsequent pack construction. Governed Chat renders active packs as a
structured Kiroku prompt block; other agent lanes receive the same verified and
budgeted result set through the cascade service.

API inspection endpoints:

- `GET /api/v1/memory/context-packs/{pack_id}`
- `GET /api/v1/memory/context-packs/by-correlation/{correlation_id}`
- `GET /api/v1/memory/retrieval-diagnostics/{correlation_id}`

Memory search can request an inline pack with `include_context_pack: true`.
