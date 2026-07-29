# Kiroku MemoryGraph — Phase 2

## Purpose

Phase 2 adds a portable, relationship-aware graph beside Shogun's existing
memory records and Qdrant vectors. It does not replace either store:

- `memory_records` remains the authoritative memory content and lifecycle store.
- Qdrant remains the rebuildable semantic index.
- `memory_graph_nodes` and `memory_graph_edges` add explicit relationships.
- `memory_graph_conflicts` records contradiction review and resolution history.

The external `jcode` project remains conceptual inspiration only. No source code
is copied, imported, vendored, translated, or derived from it. This phase is a
clean-room implementation against Shogun's own models, policies, and APIs.

## Compatibility and identity

Every legacy memory becomes a `memory_chunk` node whose node UUID is the same as
the original memory UUID. The graph node points back to `memory_records.id`, and
Qdrant receives `graph_node_id` metadata. This stable identity makes backfill
idempotent and avoids copying or rewriting the memory content.

Scope nodes are generated deterministically for the memory's agent, user, team,
workspace, project, workflow, conversation, and topic. Re-running backfill
updates existing nodes and creates only missing edges.

## Safe rollout

`MEMORY_GRAPH_WRITE_MODE` supports three states:

- `off` (default): existing memory behavior is unchanged.
- `manual`: graph APIs and backfill are available, but new memories are not
  automatically graph-linked.
- `dual`: each new memory is also linked into the graph. A database savepoint
  prevents an optional graph failure from losing the primary memory write.

Recommended rollout:

1. Deploy migration `20260729memorygraph` with write mode `off`.
2. Call `POST /api/v1/memory-graph/backfill` in bounded batches. If a response
   provides `next_after_memory_id`, submit it as `after_memory_id` in the next
   request. Continue until `complete` is true.
3. Inspect nodes, edges, neighborhoods, and conflicts through the graph APIs.
4. Set write mode to `manual` while operators verify the backfilled graph.
5. Set write mode to `dual` to graph-link new memories automatically.

At any point, setting write mode back to `off` leaves normal memory creation and
retrieval intact. Graph nodes can be rebuilt from `memory_records`.

## Conflict and supersession behavior

Creating a conflict marks both graph nodes as `conflicting` and adds a
`conflicts_with` edge. Resolving with a `superseding_memory_id` marks the older
node `superseded` and creates a `supersedes` edge. Neither original memory is
deleted or silently modified, so history remains auditable and reversible.

## API surface

- `GET|POST /api/v1/memory-graph/nodes`
- `GET|PUT|DELETE /api/v1/memory-graph/nodes/{node_id}`
- `GET /api/v1/memory-graph/nodes/{node_id}/neighborhood`
- `GET|POST /api/v1/memory-graph/edges`
- `GET /api/v1/memory-graph/search`
- `POST /api/v1/memory-graph/backfill`
- `GET|POST /api/v1/memory-graph/conflicts`
- `POST /api/v1/memory-graph/conflicts/{conflict_id}/resolve`

Graph expansion is capped at depth two. Cross-tenant edges and conflicts are
rejected. Phase 3 will consume this graph during governed cascade retrieval;
Phase 2 only establishes and validates the graph foundation.
