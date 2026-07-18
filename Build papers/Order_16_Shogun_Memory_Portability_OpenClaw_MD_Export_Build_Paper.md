# Order 16 — Shogun AFM Memory Portability: OpenClaw MD Export

## Build Paper  
### Exporting Shogun Archives and Memory Records to Portable Markdown Bundles

---

## 1. Executive Summary

This build paper defines **Order 16: Memory Portability — OpenClaw MD Export**.

The goal is to allow Shogun users to export selected memory, archive, skill, project, and agent-context data into a clean, portable Markdown format compatible with OpenClaw-style `.md` memory files.

This is the first half of Shogun’s memory portability layer.

Order 16 is **export only**.

Import will be handled later in Order 17.

The strategic purpose is simple:

> Shogun should never trap a user’s context.

Exporting memory to Markdown supports:

- user ownership
- portability
- backup
- inspection
- migration
- auditability
- long-term archive preservation
- OpenClaw interoperability
- Alpha Horizon’s no-lock-in positioning

This feature should be built as a controlled export pipeline from Shogun’s existing memory and archive systems into structured `.md` files with frontmatter, metadata, and optional bundle packaging.

---

## 2. Core Principle

The export system must follow this principle:

> **Shogun memory should be portable, human-readable, machine-readable, and safe to move.**

Markdown is the right first export format because it is:

- simple
- transparent
- durable
- readable without Shogun
- easy to version in Git
- easy for other agent systems to ingest
- compatible with OpenClaw-style memory files
- useful as a backup and documentation format

The export should not be a raw database dump.

It should be a structured, readable memory package.

---

## 3. Scope

Order 16 must implement export for:

1. Shogun Archives
2. Long-term memory records
3. Agent memory records
4. Project memory records
5. Skill-related memory records where relevant
6. Analysis memories
7. User-approved sticky memories
8. Optional run summaries and trajectory summaries
9. Optional metadata manifest
10. Optional ZIP bundle download

The minimum viable export target is:

```text
/memory_exports/{export_id}/
  manifest.json
  README.md
  memories/
    memory_001.md
    memory_002.md
  archives/
    archive_001.md
    archive_002.md
```

The export must be accessible through both:

- Shogun UI
- backend API

A CLI/script entry point is recommended but not required for the first build.

---

## 4. Non-Goals

Order 16 must not implement import.

Do not build:

- OpenClaw MD import
- automatic memory merging
- automatic deduplication on import
- conflict resolution
- cross-system synchronization
- live sync with OpenClaw
- bidirectional memory sync
- memory editing UI
- external cloud backup
- automatic publishing to OpenClaw College

Those belong to later orders.

Order 16 is strictly:

> **Export Shogun memory to portable Markdown.**

---

## 5. Relationship to Order 17

Order 16 and Order 17 are related but must be separate.

| Order | Feature | Direction |
|---:|---|---|
| 16 | OpenClaw MD Export | Shogun → Markdown bundle |
| 17 | OpenClaw MD Import | Markdown bundle → Shogun |

Order 16 should produce clean and predictable output so Order 17 can later parse it reliably.

Therefore, the export format must be stable, documented, and versioned.

---

## 6. Export Format

Each exported memory should become one Markdown file.

Each file must include:

1. YAML frontmatter
2. Human-readable memory content
3. Optional metadata section
4. Optional source trace section
5. Optional related memories section

Example:

```md
---
schema_version: "1.0"
export_type: "shogun_memory"
memory_id: "mem_12345"
source_system: "shogun_afm"
target_compatibility: "openclaw_md"
title: "User prefers direct strategic feedback"
memory_type: "preference"
agent_id: "max"
project_id: "shogun_afm"
importance: 0.91
decay_type: "sticky"
created_at: "2026-07-17T09:24:00Z"
updated_at: "2026-07-17T09:24:00Z"
tags:
  - user_preference
  - communication
  - strategy
visibility: "private"
exported_at: "2026-07-17T11:02:00Z"
---

# User prefers direct strategic feedback

The user prefers responses that are direct, non-sycophantic, and strategically precise. When the user challenges an output, the assistant should defend the original reasoning if it is sound rather than automatically conceding.

## Metadata

- Memory type: preference
- Importance: 0.91
- Decay type: sticky
- Agent: Max
- Project: Shogun AFM

## Source Trace

Originally stored in Shogun Archives.

## Related

- communication_style
- strategy_advisor
```

---

## 7. YAML Frontmatter Schema

Every exported `.md` file must include frontmatter.

### 7.1 Required Fields

```yaml
schema_version: "1.0"
export_type: "shogun_memory"
memory_id: string
source_system: "shogun_afm"
target_compatibility: "openclaw_md"
title: string
memory_type: string
created_at: string
updated_at: string
exported_at: string
```

### 7.2 Recommended Fields

```yaml
agent_id: string | null
project_id: string | null
importance: number | null
decay_type: string | null
tags: string[]
visibility: "private" | "internal" | "public"
source_table: string
source_record_id: string
related_memory_ids: string[]
```

### 7.3 Optional Fields

```yaml
run_id: string | null
stack_run_id: string | null
skill_id: string | null
skill_name: string | null
origin: string | null
confidence: number | null
last_accessed_at: string | null
access_count: integer | null
embedding_model: string | null
```

---

## 8. Markdown Body Structure

The body of each memory file should follow this structure:

```md
# {title}

{memory_content}

## Metadata

- Memory type: {memory_type}
- Importance: {importance}
- Decay type: {decay_type}
- Agent: {agent_id}
- Project: {project_id}
- Created: {created_at}
- Updated: {updated_at}

## Source Trace

{source_trace_if_available}

## Related

{related_items_if_available}
```

If some metadata is unavailable, omit the line rather than writing `"null"` in the readable body.

The frontmatter may contain null values, but the human-readable body should stay clean.

---

## 9. Export Bundle Structure

A full export should produce a folder or ZIP bundle.

Recommended folder structure:

```text
shogun_memory_export_{timestamp}/
  README.md
  manifest.json
  export_report.md
  memories/
    preferences/
    project/
    agent/
    analysis/
    sticky/
    general/
  archives/
    daily/
    runs/
    decisions/
    research/
  skills/
    used_skills/
    skill_notes/
  trajectories/
    summaries/
  raw/
    optional_json/
```

The first implementation can start simpler:

```text
shogun_memory_export_{timestamp}/
  README.md
  manifest.json
  memories/
  archives/
```

But the architecture should allow later expansion.

---

## 10. Manifest File

Every export bundle must include:

```text
manifest.json
```

The manifest is machine-readable and should describe the bundle.

Example:

```json
{
  "schema_version": "1.0",
  "export_type": "shogun_memory_bundle",
  "source_system": "shogun_afm",
  "target_compatibility": "openclaw_md",
  "export_id": "exp_20260717_110200",
  "exported_at": "2026-07-17T11:02:00Z",
  "exported_by": "local_user",
  "counts": {
    "memories": 142,
    "archives": 37,
    "skills": 12,
    "trajectories": 0
  },
  "filters": {
    "date_from": null,
    "date_to": null,
    "memory_types": ["preference", "project", "analysis"],
    "agents": ["max"],
    "projects": ["shogun_afm"],
    "include_private": true,
    "include_archives": true
  },
  "files": [
    {
      "path": "memories/preferences/mem_12345.md",
      "memory_id": "mem_12345",
      "title": "User prefers direct strategic feedback",
      "memory_type": "preference"
    }
  ]
}
```

The manifest is important for:

- later import
- validation
- audit
- troubleshooting
- bundle inspection

---

## 11. README File

Every export bundle must include:

```text
README.md
```

The README should explain:

- what the bundle contains
- when it was exported
- which filters were used
- how many records were exported
- that the content may contain private information
- that Markdown files are human-readable
- that `manifest.json` is the machine-readable index

Example:

```md
# Shogun Memory Export

This bundle contains memory and archive records exported from Shogun AFM.

- Export ID: exp_20260717_110200
- Exported at: 2026-07-17T11:02:00Z
- Source system: Shogun AFM
- Target compatibility: OpenClaw MD
- Total memories: 142
- Total archives: 37

## Warning

This export may contain private user context, project information, personal preferences, internal strategy, and operational notes. Store it securely.
```

---

## 12. Export Filters

The user must be able to choose what to export.

### 12.1 Required Filters

- all memories
- all archives
- selected project
- selected agent
- selected memory type
- selected date range
- include/exclude private memories
- include/exclude sticky memories
- include/exclude analysis memories

### 12.2 Recommended Filters

- importance threshold
- decay type
- tags
- source run ID
- stack run ID
- skill ID
- only memories used in last N days
- only memories created after date
- only memories updated after date

### 12.3 UI Defaults

Default export should be safe and useful:

```text
Export type: Selected project
Include archives: Yes
Include private memories: Yes, with warning
Include sticky memories: Yes
Include analysis memories: Yes
Include raw JSON: No
Package as ZIP: Yes
```

The user should be warned before exporting private memory.

---

## 13. UI Requirements

Add UI section:

```text
Settings → Memory → Export
```

or:

```text
Archives → Export
```

Recommended final location:

```text
Archives → Export Memory
```

The export UI should include:

1. Export scope
2. Agent selector
3. Project selector
4. Memory type selector
5. Date range
6. Include archives toggle
7. Include private memories toggle
8. Include raw JSON toggle
9. ZIP bundle toggle
10. Export preview
11. Export button
12. Download link after export
13. Export history

### 13.1 Export Preview

Before generating the bundle, show:

```text
This export will include:
- 142 memory records
- 37 archive records
- 12 sticky memories
- 18 analysis memories
- 1 project: Shogun AFM
- 1 agent: Max
```

### 13.2 Private Data Warning

If private memories are included, show:

```text
This export may contain private user context, preferences, project information, and operational memory. Store the exported files securely.
```

The user must confirm.

---

## 14. Backend API Requirements

Add API endpoints.

### 14.1 Preview Export

```http
POST /api/v1/memory/export/preview
```

Request:

```json
{
  "scope": "project",
  "project_id": "shogun_afm",
  "agent_id": "max",
  "include_archives": true,
  "include_private": true,
  "include_raw_json": false,
  "memory_types": ["preference", "project", "analysis", "sticky"],
  "date_from": null,
  "date_to": null
}
```

Response:

```json
{
  "estimated_counts": {
    "memories": 142,
    "archives": 37,
    "skills": 0,
    "trajectories": 0
  },
  "warnings": [
    "Private memories are included."
  ]
}
```

### 14.2 Start Export

```http
POST /api/v1/memory/export
```

Response:

```json
{
  "export_id": "exp_20260717_110200",
  "status": "running"
}
```

### 14.3 Export Status

```http
GET /api/v1/memory/export/{export_id}
```

Response:

```json
{
  "export_id": "exp_20260717_110200",
  "status": "completed",
  "records_exported": 179,
  "download_url": "/api/v1/memory/export/exp_20260717_110200/download"
}
```

### 14.4 Download Export

```http
GET /api/v1/memory/export/{export_id}/download
```

Returns:

```text
application/zip
```

### 14.5 Export History

```http
GET /api/v1/memory/export/history
```

Returns recent export jobs.

---

## 15. Backend Services

Add the following services:

```text
MemoryExportService
MemoryExportQueryService
MemoryMarkdownRenderer
MemoryExportManifestBuilder
MemoryExportBundleBuilder
MemoryExportPreviewService
MemoryExportAuditService
```

### 15.1 MemoryExportService

Primary orchestration service.

Responsibilities:

- validate export request
- query memory records
- query archive records
- call Markdown renderer
- build manifest
- build README
- write files
- package ZIP
- record export job status
- audit export action

### 15.2 MemoryMarkdownRenderer

Converts memory records into Markdown.

Responsibilities:

- create YAML frontmatter
- sanitize unsafe characters
- render body
- include metadata
- include source trace
- preserve original content
- normalize line endings
- avoid broken YAML

### 15.3 MemoryExportManifestBuilder

Builds `manifest.json`.

Responsibilities:

- bundle metadata
- filter metadata
- counts
- file list
- schema version
- export timestamps

### 15.4 MemoryExportBundleBuilder

Writes folder structure and creates ZIP.

Responsibilities:

- create export directory
- write `.md` files
- write `README.md`
- write `manifest.json`
- optionally write raw JSON
- create ZIP file
- return download path

---

## 16. Data Model Additions

Add an export jobs table.

```sql
CREATE TABLE memory_export_jobs (
  id TEXT PRIMARY KEY,
  status TEXT NOT NULL,
  requested_at TEXT NOT NULL,
  started_at TEXT,
  completed_at TEXT,
  requested_by TEXT,
  filters_json TEXT NOT NULL,
  counts_json TEXT,
  output_dir TEXT,
  zip_path TEXT,
  error_json TEXT,
  metadata_json TEXT
);
```

Status values:

```text
pending
running
completed
failed
cancelled
```

Optional: add `memory_export_items`.

```sql
CREATE TABLE memory_export_items (
  id TEXT PRIMARY KEY,
  export_job_id TEXT NOT NULL,
  source_type TEXT NOT NULL,
  source_id TEXT NOT NULL,
  output_path TEXT NOT NULL,
  title TEXT,
  metadata_json TEXT
);
```

This makes export traceability easier.

---

## 17. Source Data Mapping

The implementation must map Shogun memory fields into export fields.

### 17.1 Memory Record Mapping

| Shogun Field | Markdown Field |
|---|---|
| id | memory_id |
| title / summary | title |
| content | body |
| memory_type | memory_type |
| agent_id | agent_id |
| project_id | project_id |
| importance | importance |
| decay_type | decay_type |
| tags | tags |
| created_at | created_at |
| updated_at | updated_at |
| source_run_id | run_id |
| stack_run_id | stack_run_id |
| visibility | visibility |

### 17.2 Archive Record Mapping

Archive records should use:

```yaml
export_type: "shogun_archive"
archive_id: string
archive_type: string
```

Archive files should go under:

```text
archives/
```

Archive body should include the archived content and metadata.

---

## 18. File Naming Rules

File names must be safe and predictable.

Recommended pattern:

```text
{memory_type}_{created_date}_{short_id}_{slugified_title}.md
```

Example:

```text
preference_2026-07-17_mem12345_direct-strategic-feedback.md
```

Rules:

- lowercase
- spaces replaced with hyphens
- remove unsafe characters
- max filename length: 120 characters
- include short ID to avoid collisions
- preserve `.md` extension

If title is missing:

```text
memory_2026-07-17_mem12345.md
```

---

## 19. Privacy and Security Requirements

Memory export is sensitive.

### 19.1 Required Controls

- Export disabled unless user explicitly starts it
- Private memory warning
- Export audit event
- No automatic upload to cloud
- Local file generation only
- ZIP generated locally
- Download link must expire or be protected
- Export folder should be inside Shogun-controlled storage
- Secrets should not be exported unless explicitly included
- Protected memory types may require confirmation

### 19.2 Optional Redaction

Add optional redaction mode later.

First build can include simple toggles:

```text
Include private memories: on/off
Include secret-like content: off by default
```

If Shogun has any secret memory class, it should be excluded by default.

---

## 20. Audit Events

All export actions must be logged through existing Shogun EventLogger.

Required events:

```text
memory.export.preview_requested
memory.export.started
memory.export.completed
memory.export.failed
memory.export.downloaded
memory.export.cancelled
```

Each event should include:

- export_id
- filters
- counts
- include_private flag
- include_raw_json flag
- output type
- timestamp
- requesting user/session
- agent if applicable

Do not create a separate audit system.

---

## 21. Error Handling

The export process must fail safely.

### 21.1 Common Errors

| Error | Handling |
|---|---|
| No records found | Complete export with README and manifest showing zero records |
| Invalid filter | Return validation error |
| File write failure | Mark export failed and log error |
| YAML render failure | Skip failed record, log item error, continue if possible |
| ZIP creation failure | Keep folder export if available, mark partial failure |
| Permission denied | Stop export and log failure |
| Disk full | Stop export and show clear error |

### 21.2 Partial Failure

If some records fail to export, the job should complete as:

```text
completed_with_warnings
```

or include warning metadata in the manifest.

Recommended status values can be extended to:

```text
completed_with_warnings
```

---

## 22. Raw JSON Option

Add optional raw JSON export.

Default:

```text
include_raw_json = false
```

If enabled, write:

```text
raw/memories.json
raw/archives.json
```

This helps debugging and later import development.

The Markdown files remain the primary portability format.

---

## 23. Compatibility With OpenClaw MD

The exported files should be compatible with OpenClaw-style Markdown memory files.

This means:

- YAML frontmatter
- readable body content
- stable metadata fields
- one memory per file
- bundle manifest
- no Shogun-only binary format
- no hidden database dependency

Do not overfit the first export to OpenClaw if OpenClaw’s exact schema changes.

Instead, use:

```yaml
target_compatibility: "openclaw_md"
schema_version: "1.0"
source_system: "shogun_afm"
```

This keeps the format portable and future-proof.

---

## 24. Testing Requirements

### 24.1 Unit Tests

Test:

- YAML frontmatter generation
- Markdown rendering
- filename slugification
- manifest generation
- README generation
- filter validation
- private memory warning
- archive export
- raw JSON export
- ZIP packaging

### 24.2 Integration Tests

Test:

1. Export all memories
2. Export selected project
3. Export selected agent
4. Export archives only
5. Export sticky memories only
6. Export with private memories excluded
7. Export with raw JSON enabled
8. Download ZIP
9. Verify manifest matches files
10. Verify all Markdown files have valid frontmatter

### 24.3 Security Tests

Test:

- export cannot write outside export folder
- unsafe filenames are sanitized
- private warning appears
- protected/secret memory excluded by default
- download URL cannot access arbitrary files
- path traversal attempts are blocked

---

## 25. Acceptance Criteria

Order 16 is complete when:

1. User can open Memory Export UI.
2. User can preview export counts before exporting.
3. User can select project, agent, memory types, date range, and archive inclusion.
4. User gets a warning when private memories are included.
5. User can start an export job.
6. Export job status is trackable.
7. Export creates Markdown files with YAML frontmatter.
8. Export creates `manifest.json`.
9. Export creates `README.md`.
10. Export can package files as ZIP.
11. User can download ZIP.
12. Exported Markdown files are human-readable.
13. Exported Markdown files are machine-readable.
14. Exported files include stable schema version.
15. Archive records can be exported.
16. Memory records can be exported.
17. Raw JSON export can be optionally included.
18. Export action is audit logged.
19. Failed records are handled without corrupting the whole export.
20. Export does not implement import.
21. Existing Shogun memory behavior remains unchanged.
22. Exported bundle is suitable as input for future Order 17 import.

---

## 26. Recommended First Demo

Demo name:

```text
Order 16 — Memory Export Demo
```

Demo steps:

1. Open Shogun Archives.
2. Go to Export Memory.
3. Select project: Shogun AFM.
4. Select agent: Max.
5. Include archives: Yes.
6. Include private memories: Yes.
7. Preview export.
8. Confirm private-memory warning.
9. Start export.
10. Download ZIP.
11. Open exported folder.
12. Show `manifest.json`.
13. Open one `.md` memory file.
14. Show YAML frontmatter and readable body.
15. Show audit event.

Demo message:

> Shogun can export its memory and archive records into portable Markdown bundles with metadata, manifest, and audit logging. This gives users ownership of their context and prepares Shogun for OpenClaw-compatible memory portability.

---

## 27. Implementation Order

Build in this order.

### Phase 1 — Backend Export Skeleton

- Add export job table
- Add MemoryExportService
- Add preview endpoint
- Add start export endpoint
- Add status endpoint
- Add download endpoint

### Phase 2 — Query and Filtering

- Query memory records
- Query archive records
- Apply filters
- Count records for preview
- Validate filters

### Phase 3 — Markdown Renderer

- YAML frontmatter
- Markdown body
- metadata section
- safe rendering
- filename generation

### Phase 4 — Bundle Builder

- Export folder
- file writing
- README
- manifest
- optional raw JSON
- ZIP creation

### Phase 5 — UI

- Export screen
- filters
- preview
- private warning
- job status
- download link
- export history

### Phase 6 — Audit and Security

- EventLogger integration
- private memory warning
- safe path handling
- protected memory exclusions
- download protection

### Phase 7 — Tests and Demo

- unit tests
- integration tests
- security tests
- demo export

---

## 28. Critical Constraints for Coding Agent

The coding agent must follow these constraints:

1. Do not implement import in Order 16.
2. Do not modify existing memory storage behavior.
3. Do not replace Qdrant or SQLite.
4. Do not create a raw database dump as the main export.
5. Do not export secrets by default.
6. Do not write files outside the controlled export directory.
7. Do not create download paths vulnerable to traversal.
8. Do not bypass EventLogger.
9. Do not omit `manifest.json`.
10. Do not omit schema versioning.
11. Do not omit YAML frontmatter.
12. Do not make export automatic.
13. Do not upload exported memory to any external service.
14. Do not assume OpenClaw import exists yet.
15. Build export output so Order 17 can import it later.

---

## 29. Future Enhancements

After Order 16, consider:

- Order 17: OpenClaw MD Import
- export encryption
- export redaction profiles
- scheduled backups
- Git-based memory backup
- selective public skill export
- OpenClaw College skill publishing
- memory diff between exports
- signed export manifest
- compressed memory bundle
- portable memory viewer
- import validation tool
- cross-agent memory migration

---

## 30. Final Design Sentence

Order 16 should be built around this sentence:

> **Shogun can export its memory and archive records into portable, human-readable, machine-readable Markdown bundles so users own their context and can move it without vendor lock-in.**

That is the feature.

That is the strategy.

That is the build.

---
