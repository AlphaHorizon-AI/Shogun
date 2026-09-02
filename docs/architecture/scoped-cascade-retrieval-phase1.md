# Scoped Cascade Retrieval — Phase 1

## Purpose

Phase 1 adds governed memory scopes and narrow-to-broad cascade retrieval without replacing Shogun's existing memory records or Qdrant collection.

The relational `memory_records` table remains authoritative. Qdrant remains a rebuildable semantic index. The future Kiroku Graph is not part of this phase.

## Clean-room implementation constraint

The external jcode project is conceptual inspiration only. Shogun does not copy, import, vendor, translate, or derive implementation code from jcode. Phase 1 is implemented exclusively against Shogun's existing architecture, models, services, policies, and tests.

## Scope envelope

Every newly stored memory receives a canonical scope envelope:

```text
tenant_id
user_id
team_id
workspace_id
project_id
workflow_id
conversation_provider
conversation_id
topic_id
sensitivity
scope_status
policy_version
```

Existing records are migrated safely as `tenant_id=local`, `sensitivity=internal`, and `scope_status=agent_private`. They are not promoted to global memory.

Telegram requests resolve `chat_id + message_thread_id` into conversation/topic scope. Private chats also carry user scope; group/forum memories are shared only inside the matching conversation/topic.

## Authorization order

Scoped retrieval is deny-by-default:

1. Resolve the active scope.
2. Select authorized memory IDs from the relational database.
3. Pass only those IDs into the Qdrant query.
4. Reapply relational authorization when loading full records.
5. Rerank authorized results using the existing salience engine.
6. Persist content-free diagnostics using a query hash and memory IDs.

This prevents an unauthorized vector candidate from becoming model context. Qdrant metadata is not treated as the sole access-control boundary.

## Cascade order

Available stages execute from narrow to broad:

```text
topic
conversation
workspace
project
workflow
team
user
agent fallback
```

Only stages represented by the current scope are planned. Retrieval stops when its result budget is satisfied.

## Rollout modes

Set `MEMORY_RETRIEVAL_MODE` to one of:

- `legacy`: current retrieval is returned; diagnostics are recorded.
- `shadow`: current retrieval is returned while the scoped cascade runs for comparison.
- `cascade`: only authorized cascade results are returned.

The default is `legacy`. Recommended rollout:

1. Deploy the migration in `legacy` mode.
2. Reindex Qdrant so new scope metadata is present.
3. Run `shadow` mode and inspect retrieval diagnostics.
4. Classify historical memories that need project, workspace, or connector visibility.
5. Enable `cascade` for selected workspaces/topics.
6. Expand only after isolation and relevance evaluations pass.

Rollback is a configuration change back to `legacy`; existing memory IDs and records are unchanged.

## API

`POST /api/v1/memory/search` accepts the existing request plus:

```json
{
  "scope": {
    "tenant_id": "local",
    "workspace_id": "shogun",
    "project_id": "shogun-afm",
    "sensitivity_ceiling": "internal"
  },
  "retrieval_mode": "shadow",
  "include_diagnostics": true
}
```

Diagnostics are available at:

```text
GET /api/v1/memory/retrieval-diagnostics
GET /api/v1/memory/retrieval-diagnostics/{correlation_id}
```

Raw queries are not stored in the diagnostics table.

## Reindexing

The existing reindex operation rebuilds Qdrant payloads with the new scope, sensitivity, lifecycle, and policy metadata. A failed index rebuild does not delete relational memory records.

## Security invariants

- Multiple requested memory types are an OR group nested inside mandatory filters.
- Agent, authorized-ID, importance, and pinned constraints remain mandatory.
- Populated scope dimensions require a matching request dimension.
- Missing request dimensions cannot retrieve records populated in those dimensions.
- Sensitivity may not exceed the request ceiling.
- Legacy records remain agent-private.
- Connector context is request-local and cannot leak between concurrent requests.
