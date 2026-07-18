# Order 17 — Shogun AFM Build Paper  
# Memory Portability: OpenClaw MD Import  
## Import OpenClaw Markdown Memories into Shogun Archives, SQLite, and Qdrant

---

## 1. Executive Summary

This build paper defines **Order 17: Memory Portability — OpenClaw MD Import** for Shogun AFM.

Order 16 implemented the export side of memory portability. Order 17 completes the portability loop by allowing Shogun to import OpenClaw-style Markdown memory files into the Shogun memory system.

The import feature must support:

- Markdown files with YAML-style frontmatter
- folders of `.md` files
- `.zip` bundles containing Markdown files
- exported Shogun memory bundles from Order 16
- OpenClaw memory files with compatible but imperfect metadata
- validation before import
- preview before commit
- deduplication
- conflict handling
- embedding into Qdrant
- persistence into SQLite
- audit logging
- rollback of failed imports
- UI support in Katana
- CLI/API support for automation

The strategic goal is simple:

> **A user should be able to bring their memory context from OpenClaw into Shogun without cold-starting their agent.**

This supports Alpha Horizon’s broader position on portability, independence, and avoiding lock-in.

---

## 2. Feature Name

Use the following name in the codebase, UI, and documentation:

```text
Memory Import — OpenClaw Markdown
```

Short UI label:

```text
Import OpenClaw Memories
```

Internal service name:

```text
MemoryImportService
```

Recommended order title:

```text
Order 17 — Memory Portability: OpenClaw MD Import
```

---

## 3. Purpose

Shogun already has an Archive/memory system backed by SQLite and Qdrant. The purpose of this feature is to make that memory system portable by importing Markdown-based memories from OpenClaw or Shogun export bundles.

The feature must solve four problems:

1. **No cold start**  
   Users moving from OpenClaw to Shogun can bring useful context, skills, preferences, project history, and decision history.

2. **Portability**  
   Memory should not be trapped inside one agent framework.

3. **Backup restoration**  
   A Shogun export from Order 16 should be importable again.

4. **Operational continuity**  
   Imported memories must be usable by Shogun’s retrieval, Archive, Qdrant embeddings, and active memory injection logic.

---

## 4. Core Principle

The import process must not blindly dump Markdown into memory.

It must use a controlled pipeline:

```text
Parse → Validate → Normalize → Preview → Deduplicate → Confirm → Store → Embed → Verify → Audit
```

Core rule:

> **Imported memory must become first-class Shogun memory, not a separate imported-file archive.**

After import, Shogun should treat imported memory like native Archive memory, with source metadata showing that it came from OpenClaw/Markdown import.

---

## 5. Scope

Order 17 includes:

- Import from `.md` files
- Import from a folder of `.md` files
- Import from `.zip` bundles
- Parse YAML-style frontmatter
- Parse Markdown body content
- Map OpenClaw metadata to Shogun memory schema
- Assign memory type, importance, decay type, tags, source, timestamps
- Generate missing metadata safely
- Validate content
- Detect duplicates
- Present preview before import
- Persist imported memory into SQLite
- Embed imported memory into Qdrant
- Store import batch records
- Support rollback per import batch
- Provide UI in Katana
- Provide backend API
- Provide CLI/script entry point where useful
- Log all import actions through Shogun EventLogger

---

## 6. Non-Goals

Do not build the following in this order:

- A full cross-platform memory sync service
- Live two-way synchronization between OpenClaw and Shogun
- Automatic deletion of OpenClaw source memories
- A new memory database separate from Shogun Archives
- A new embedding store separate from Qdrant
- A new memory format that replaces Shogun’s internal schema
- Unreviewed bulk import without preview
- Import of arbitrary unknown file types beyond Markdown/ZIP
- SkillOpt optimization of imported memories
- External cloud memory migration

This order is specifically about **OpenClaw Markdown import into Shogun memory**.

---

## 7. Assumptions

This build assumes:

- Order 16 Memory Export exists.
- Shogun has a SQLite-backed Archive/memory table.
- Shogun uses Qdrant for vector embeddings.
- Shogun has an EventLogger/audit pipeline.
- Shogun has a Katana UI.
- Shogun can already store memories through an internal memory service.
- The `store_memory` tool may already support or soon support `decay_type`.
- OpenClaw Markdown files use frontmatter, or at least a consistent Markdown body.

If existing schema names differ, adapt names but preserve the architecture.

---

## 8. Supported Input Formats

### 8.1 Single Markdown File

```text
memory.md
```

### 8.2 Folder Import

```text
/openclaw-memory-export/
  project_context.md
  user_preferences.md
  decisions/
    decision_001.md
    decision_002.md
```

### 8.3 ZIP Bundle

```text
openclaw_memory_export.zip
```

The ZIP may include nested folders.

Only `.md` files should be parsed.

Other files should be ignored unless they are manifest files explicitly recognized by the importer.

---

## 9. Canonical Markdown Memory Format

The importer should support this preferred format:

```md
---
id: openclaw_12345
title: Preferred AI model routing strategy
memory_type: decision
importance: 8
decay_type: sticky
tags:
  - shogun
  - model-routing
  - architecture
created_at: 2026-07-16T10:15:00Z
updated_at: 2026-07-16T10:15:00Z
source: openclaw
source_project: Shogun AFM
---

The user prefers GLM models as primary daily drivers, with stronger models escalated for complex reasoning.
```

The body after frontmatter is the memory content.

---

## 10. Frontmatter Fields

### 10.1 Canonical Fields

The importer should recognize these fields:

| Field | Type | Required | Notes |
|---|---:|---:|---|
| `id` | string | No | External/source ID. Do not use as Shogun primary key directly. |
| `title` | string | No | If missing, generate title from first heading or first line. |
| `memory_type` | string | No | Normalize to Shogun memory types. |
| `importance` | integer | No | 1–10. Default if missing. |
| `decay_type` | string | No | `normal`, `slow`, `sticky`, etc. |
| `tags` | list/string | No | Normalize to list. |
| `created_at` | datetime | No | Use source value if valid. |
| `updated_at` | datetime | No | Use source value if valid. |
| `source` | string | No | Default `openclaw_md_import`. |
| `source_project` | string | No | Optional project/workspace. |
| `agent` | string | No | Source agent name if available. |
| `confidence` | float | No | Optional, if source supports it. |
| `visibility` | string | No | Optional, future use. |

### 10.2 Accepted Synonyms

The importer should be forgiving and map common synonyms.

| Incoming Field | Canonical Field |
|---|---|
| `type` | `memory_type` |
| `category` | `memory_type` |
| `weight` | `importance` |
| `priority` | `importance` |
| `labels` | `tags` |
| `created` | `created_at` |
| `modified` | `updated_at` |
| `updated` | `updated_at` |
| `origin` | `source` |
| `project` | `source_project` |

---

## 11. Memory Type Normalization

The importer must map incoming memory types to Shogun-supported memory categories.

Recommended normalized types:

```text
fact
preference
decision
project_context
instruction
skill_note
analysis
conversation_summary
system_note
unknown
```

Example mapping:

| Incoming | Normalized |
|---|---|
| `pref` | `preference` |
| `preference` | `preference` |
| `decision` | `decision` |
| `project` | `project_context` |
| `context` | `project_context` |
| `instruction` | `instruction` |
| `skill` | `skill_note` |
| `analysis` | `analysis` |
| `summary` | `conversation_summary` |
| missing/invalid | `unknown` |

The importer must not fail only because memory type is unknown.

Unknown values should be imported as:

```text
unknown
```

with a warning in the preview.

---

## 12. Importance Normalization

Shogun should use an importance scale of `1–10`.

If source importance is missing:

```text
Default importance = 5
```

If source importance is outside range:

- below 1 → clamp to 1
- above 10 → clamp to 10

If source uses `0–1` float:

```text
importance = round(value * 10)
```

If source uses labels:

| Incoming | Importance |
|---|---:|
| `low` | 3 |
| `medium` | 5 |
| `high` | 8 |
| `critical` | 10 |

---

## 13. Decay Type Normalization

Supported values should align with the existing Shogun Archives backend.

Recommended values:

```text
normal
slow
fast
sticky
```

If invalid or missing:

```text
normal
```

Special rule:

- `sticky` should only be accepted directly if the backend supports it.
- If the backend does not yet support sticky retrieval rules, import the value but mark it as pending support or downgrade to high importance with warning.

Preferred behavior:

```text
Do not silently discard decay_type.
```

---

## 14. Source Metadata

Every imported memory must include import source metadata.

Recommended fields:

```json
{
  "source": "openclaw_md_import",
  "source_system": "openclaw",
  "source_file": "decisions/decision_001.md",
  "source_external_id": "openclaw_12345",
  "import_batch_id": "uuid",
  "imported_at": "timestamp"
}
```

This is essential for rollback, auditing, and transparency.

---

## 15. Import Pipeline

The import pipeline must be explicit.

```text
1. Upload/select file, folder, or ZIP
2. Extract candidate Markdown files
3. Parse frontmatter and body
4. Normalize metadata
5. Validate each memory
6. Generate import preview
7. Run deduplication analysis
8. User confirms import
9. Store memory rows in SQLite
10. Embed memory content
11. Upsert vectors into Qdrant
12. Verify counts
13. Audit import
14. Produce import report
```

---

## 16. Parser Behavior

### 16.1 Frontmatter Detection

Recognize frontmatter only when the file starts with:

```text
---
```

and contains a closing:

```text
---
```

If no frontmatter is present:

- treat entire file as body
- generate metadata
- include warning in preview

### 16.2 Body Extraction

The Markdown body must be preserved as content.

Do not remove headings, bullets, code blocks, or tables.

Trim only leading/trailing whitespace.

### 16.3 Title Extraction

If `title` is missing:

1. Use first Markdown heading `# Title`
2. Else use first non-empty line, truncated to 120 chars
3. Else use filename

### 16.4 Empty Files

If body is empty:

- mark invalid
- skip by default
- show in preview as rejected

---

## 17. Validation Rules

Each candidate memory must be validated before import.

### 17.1 Valid Memory

A memory is valid if:

- body content is non-empty
- normalized memory type exists
- importance is valid or defaultable
- content size is within configured limit
- file path is safe

### 17.2 Warnings

Warnings should not block import:

- missing frontmatter
- missing title
- unknown memory type normalized to `unknown`
- missing timestamps
- invalid importance clamped
- invalid decay type defaulted
- duplicate candidate detected

### 17.3 Errors

Errors should block individual memory import:

- empty content
- unreadable file
- invalid encoding that cannot be recovered
- file too large beyond configured limit
- path traversal inside ZIP
- failed parse with no recoverable body

---

## 18. Deduplication

Deduplication is mandatory.

The importer must detect duplicates against:

1. Other files in the same import batch
2. Existing Shogun memory rows
3. Existing source external IDs
4. Similar content hashes

### 18.1 Deduplication Methods

Use multiple layers:

#### External ID Match

If `source_external_id` already exists:

```text
exact duplicate or update candidate
```

#### Content Hash Match

Compute normalized content hash:

```text
sha256(normalized_title + normalized_body)
```

If hash exists:

```text
duplicate
```

#### Similarity Match

Optional but recommended:

- embed candidate
- search Qdrant for similar memory
- if similarity above threshold, mark as possible duplicate

Recommended threshold:

```text
0.92+
```

### 18.2 Duplicate Handling Options

UI should offer:

```text
Skip duplicates
Import as new copy
Update existing memory
Ask per conflict
```

Default:

```text
Skip exact duplicates
Ask for possible duplicates
```

---

## 19. Conflict Handling

A conflict occurs when incoming memory appears to match existing memory but has different metadata or content.

Examples:

- same external ID, different content
- same title, different body
- same hash, different tags
- similar content, different importance

Conflict resolution options:

```text
Skip
Replace existing
Merge metadata
Import as new
Review manually
```

Default:

```text
Review manually
```

For first implementation, it is acceptable to support:

```text
Skip / Import as new
```

and add replace/merge later.

---

## 20. SQLite Persistence

Imported memories must be stored in the existing memory/archive SQLite schema if possible.

If necessary, add import tracking tables.

### 20.1 Import Batch Table

```sql
CREATE TABLE IF NOT EXISTS memory_import_batches (
  id TEXT PRIMARY KEY,
  source_type TEXT NOT NULL,
  source_name TEXT,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  completed_at TEXT,
  total_files INTEGER DEFAULT 0,
  valid_count INTEGER DEFAULT 0,
  imported_count INTEGER DEFAULT 0,
  skipped_count INTEGER DEFAULT 0,
  failed_count INTEGER DEFAULT 0,
  warnings_json TEXT,
  metadata_json TEXT
);
```

### 20.2 Import Item Table

```sql
CREATE TABLE IF NOT EXISTS memory_import_items (
  id TEXT PRIMARY KEY,
  batch_id TEXT NOT NULL,
  source_file TEXT,
  source_external_id TEXT,
  status TEXT NOT NULL,
  shogun_memory_id TEXT,
  title TEXT,
  memory_type TEXT,
  content_hash TEXT,
  warnings_json TEXT,
  error_json TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY(batch_id) REFERENCES memory_import_batches(id)
);
```

### 20.3 Existing Memory Table Extension

If the memory table does not already support these fields, add them or include them in metadata JSON:

```text
source_system
source_file
source_external_id
import_batch_id
content_hash
```

Do not disrupt existing memory retrieval.

---

## 21. Qdrant Upsert

Each imported memory must be embedded and upserted into Qdrant.

Recommended Qdrant payload:

```json
{
  "memory_id": "uuid",
  "title": "Preferred AI model routing strategy",
  "memory_type": "decision",
  "importance": 8,
  "decay_type": "sticky",
  "tags": ["shogun", "model-routing"],
  "source_system": "openclaw",
  "source_file": "decisions/decision_001.md",
  "import_batch_id": "uuid",
  "created_at": "2026-07-16T10:15:00Z",
  "updated_at": "2026-07-16T10:15:00Z"
}
```

Embedding text should include:

```text
Title
Tags
Memory type
Body content
```

Recommended embedding input:

```text
Title: {title}
Type: {memory_type}
Tags: {tags}
Content:
{body}
```

---

## 22. Transaction and Rollback Behavior

The import should be batch-safe.

### 22.1 Recommended Behavior

For each batch:

1. Create import batch record.
2. Parse and preview without writing memories.
3. On confirmation, write memories in controlled transaction chunks.
4. Upsert Qdrant vectors.
5. Verify counts.
6. Mark batch complete.

### 22.2 Failure Handling

If SQLite insert succeeds but Qdrant upsert fails:

- mark item as `partial_failed`
- retry Qdrant upsert
- provide repair endpoint

Do not silently report success.

### 22.3 Rollback

Support rollback by batch:

```text
Rollback Import Batch
```

Rollback should:

- delete imported memory rows from SQLite if source is the batch
- delete associated vectors from Qdrant
- mark batch as rolled back
- log rollback event

Do not delete memories that existed before the import.

---

## 23. Backend Service Architecture

Add or extend these services:

```text
MemoryImportService
MarkdownMemoryParser
MemoryImportValidator
MemoryImportNormalizer
MemoryDeduplicationService
MemoryConflictService
MemoryEmbeddingService
MemoryImportBatchService
MemoryImportRollbackService
```

Suggested responsibilities:

| Service | Responsibility |
|---|---|
| `MemoryImportService` | Main orchestration service |
| `MarkdownMemoryParser` | Reads frontmatter/body |
| `MemoryImportValidator` | Validates candidates |
| `MemoryImportNormalizer` | Maps metadata to Shogun schema |
| `MemoryDeduplicationService` | Detects duplicates/conflicts |
| `MemoryEmbeddingService` | Embeds and upserts Qdrant vectors |
| `MemoryImportBatchService` | Creates batch/item records |
| `MemoryImportRollbackService` | Reverts imported batch |

---

## 24. Backend API

Add API endpoints.

### 24.1 Preview Import

```http
POST /api/v1/memory/import/openclaw/preview
```

Input:

- uploaded `.md`
- uploaded `.zip`
- local folder path if running local Shogun

Response:

```json
{
  "batch_preview_id": "uuid",
  "total_files": 42,
  "valid_count": 39,
  "warning_count": 8,
  "error_count": 3,
  "duplicate_count": 5,
  "items": []
}
```

### 24.2 Confirm Import

```http
POST /api/v1/memory/import/openclaw/confirm
```

Request:

```json
{
  "batch_preview_id": "uuid",
  "duplicate_policy": "skip_exact_ask_possible",
  "conflict_policy": "skip",
  "default_memory_type": "unknown",
  "default_importance": 5,
  "default_decay_type": "normal"
}
```

### 24.3 Import Batch Status

```http
GET /api/v1/memory/import/batches/{batch_id}
```

### 24.4 List Import Batches

```http
GET /api/v1/memory/import/batches
```

### 24.5 Rollback Batch

```http
POST /api/v1/memory/import/batches/{batch_id}/rollback
```

### 24.6 Retry Failed Embeddings

```http
POST /api/v1/memory/import/batches/{batch_id}/retry-embeddings
```

---

## 25. Katana UI Requirements

Add a UI area:

```text
Katana → Memory → Import
```

or:

```text
Katana → Archives → Import
```

Recommended label:

```text
Import OpenClaw Memories
```

### 25.1 Import Screen

Fields:

- select file/folder/ZIP
- source type: OpenClaw / Shogun Export / Generic Markdown
- default memory type
- default importance
- default decay type
- duplicate policy
- conflict policy
- preview button

### 25.2 Preview Screen

Show:

- total files found
- valid memories
- warnings
- errors
- duplicates
- possible duplicates
- memory type distribution
- tag distribution
- estimated import count

Each item should show:

- title
- memory type
- importance
- decay type
- tags
- source file
- warning/error status
- duplicate status
- preview body excerpt

Actions:

```text
Import Valid Memories
Cancel
Download Preview Report
```

### 25.3 Conflict Review Screen

For possible duplicates, show:

- incoming memory
- existing memory
- similarity score
- metadata differences
- action: skip / import as new / replace later

First version can implement skip/import-as-new only.

### 25.4 Import Result Screen

Show:

- imported count
- skipped count
- failed count
- Qdrant upsert count
- warnings
- failed files
- rollback button
- import report download

---

## 26. CLI Support

Optional but recommended for power users and testing.

Example:

```bash
python -m shogun.memory.import_openclaw \
  --path ./openclaw_export.zip \
  --preview
```

Confirm import:

```bash
python -m shogun.memory.import_openclaw \
  --path ./openclaw_export.zip \
  --import \
  --duplicate-policy skip_exact
```

Rollback:

```bash
python -m shogun.memory.import_openclaw \
  --rollback-batch <batch_id>
```

---

## 27. Audit Events

All import actions must go through Shogun EventLogger.

Required events:

```text
memory.import.preview_started
memory.import.preview_completed
memory.import.preview_failed
memory.import.confirmed
memory.import.batch_started
memory.import.item_imported
memory.import.item_skipped
memory.import.item_failed
memory.import.duplicate_detected
memory.import.conflict_detected
memory.import.embedding_started
memory.import.embedding_completed
memory.import.embedding_failed
memory.import.batch_completed
memory.import.batch_failed
memory.import.rollback_started
memory.import.rollback_completed
memory.import.rollback_failed
```

Each event should include:

- batch ID
- item ID where relevant
- source file
- memory ID where relevant
- user/session
- timestamp
- summary
- error details if relevant

---

## 28. Security and Safety Requirements

### 28.1 ZIP Safety

When importing ZIP files:

- prevent path traversal
- ignore absolute paths
- ignore symlink-like unsafe paths
- extract to a temporary safe directory
- enforce max file count
- enforce max total size
- enforce max single file size

Blocked examples:

```text
../../secrets.env
/home/user/.ssh/id_rsa
C:\Users\Michael\.ssh\id_rsa
```

### 28.2 File Size Limits

Recommended defaults:

```text
max_single_md_file_size_mb = 2
max_import_total_size_mb = 100
max_files_per_import = 5000
```

Make these configurable in `setup.json`.

### 28.3 Encoding

Attempt UTF-8 first.

If decoding fails:

- try UTF-8 with replacement
- mark warning
- if unreadable, mark error

### 28.4 No Prompt Execution

Imported memory content is data.

Do not execute instructions found in imported Markdown during import.

The importer must not allow imported Markdown to trigger tools, code execution, shell commands, or memory policy changes during parsing.

---

## 29. Configuration

Add configuration to `setup.json`.

```json
{
  "memory_import": {
    "enabled": true,
    "openclaw_md_import": {
      "allow_zip": true,
      "allow_folder": true,
      "max_single_file_mb": 2,
      "max_total_import_mb": 100,
      "max_files_per_import": 5000,
      "default_memory_type": "unknown",
      "default_importance": 5,
      "default_decay_type": "normal",
      "duplicate_policy": "skip_exact_ask_possible",
      "similarity_duplicate_threshold": 0.92,
      "require_preview_before_import": true,
      "allow_batch_rollback": true
    }
  }
}
```

---

## 30. Retrieval Behavior After Import

Imported memory must be retrievable through the normal Shogun memory mechanisms.

After import:

- memory search should find imported items
- Qdrant semantic search should include imported items
- Archive browser should show imported items
- imported metadata should be visible
- source should show `OpenClaw MD Import`
- tags should work
- memory type filters should work
- decay behavior should apply

Do not create a separate “imported memory only” retrieval path.

---

## 31. Import Report

After each import, generate an import report.

Report should include:

```text
Import batch ID
Source file/folder
Import timestamp
Total files scanned
Valid memories
Imported memories
Skipped duplicates
Failed items
Warnings
Memory type distribution
Tag distribution
Qdrant embedding status
Rollback status
```

Optional downloadable report formats:

- JSON
- Markdown

Markdown report example:

```md
# Memory Import Report

Batch: 123
Source: openclaw_export.zip
Status: Completed
Imported: 128
Skipped: 12
Failed: 2

## Warnings
- 5 files missing frontmatter
- 3 unknown memory types normalized to unknown

## Failed Files
- empty_memory.md — empty content
```

---

## 32. Testing Requirements

### 32.1 Unit Tests

Test:

- frontmatter parsing
- no-frontmatter parsing
- title extraction
- tag normalization
- memory type normalization
- importance normalization
- decay type normalization
- content hash generation
- invalid files
- duplicate detection
- ZIP path traversal blocking
- file size limits

### 32.2 Integration Tests

Test:

- preview import from single MD
- preview import from folder
- preview import from ZIP
- confirm import writes SQLite rows
- confirm import upserts Qdrant vectors
- imported memory appears in search
- rollback removes imported rows/vectors
- failed Qdrant upsert produces partial failure
- retry embeddings works

### 32.3 UI Tests

Test:

- import screen loads
- file selection works
- preview displays counts
- warnings/errors display correctly
- duplicate handling appears
- import confirmation works
- result screen appears
- rollback button works

### 32.4 Security Tests

Test malicious ZIP entries:

```text
../../outside.md
/etc/passwd
C:\Users\user\.ssh\id_rsa
nested/../../../escape.md
```

All must be blocked.

---

## 33. Acceptance Criteria

Order 17 is complete when:

1. User can import a single OpenClaw Markdown memory file.
2. User can import a folder of Markdown memory files.
3. User can import a ZIP bundle of Markdown memory files.
4. Frontmatter is parsed correctly.
5. Markdown body content is preserved.
6. Missing frontmatter is handled with warnings, not hard failure.
7. Metadata is normalized to Shogun schema.
8. Memory type normalization works.
9. Importance normalization works.
10. Decay type normalization works.
11. Tags are normalized.
12. Duplicate detection works.
13. Preview is shown before import.
14. User can confirm or cancel import.
15. Imported memories are stored in SQLite.
16. Imported memories are embedded into Qdrant.
17. Imported memories appear in normal Shogun memory search.
18. Imported memories show source metadata.
19. Import batches are tracked.
20. Failed imports are reported clearly.
21. Partial embedding failures are detectable and retryable.
22. Batch rollback removes imported memories and vectors.
23. Import actions are logged through EventLogger.
24. ZIP path traversal is blocked.
25. Existing Shogun memories are not overwritten without explicit conflict handling.
26. Import report is generated.
27. Existing memory system behavior remains compatible.

---

## 34. Recommended Demo

Demo name:

```text
Order 17 — OpenClaw Memory Import Demo
```

Demo steps:

```text
1. Open Katana → Archives/Memory → Import
2. Select OpenClaw Markdown ZIP bundle
3. Click Preview
4. Show parsed memories, warnings, duplicates
5. Confirm import
6. Show import result report
7. Search for imported memory in Shogun Archives
8. Demonstrate Qdrant semantic retrieval
9. Roll back a test batch
10. Confirm memories are removed
```

Demo success message:

> Shogun can now import OpenClaw Markdown memories, normalize them into the native Archive system, embed them into Qdrant, make them searchable, and roll them back safely.

---

## 35. Build Order

Implement in this order:

### Phase 1 — Parser and Normalizer

- Markdown file reader
- frontmatter parser
- body extractor
- title extraction
- metadata normalization
- validation warnings/errors

### Phase 2 — Preview Pipeline

- scan file/folder/ZIP
- create candidate memory objects
- produce preview response
- show preview in UI

### Phase 3 — Import Batch Tracking

- add import batch tables
- add import item tables
- create batch preview records or temporary preview cache

### Phase 4 — Deduplication

- content hash
- source external ID matching
- duplicate status in preview
- skip exact duplicates by default

### Phase 5 — Confirm Import

- write imported memories to SQLite
- preserve source metadata
- create import item records

### Phase 6 — Qdrant Embedding

- embed imported memories
- upsert vectors
- mark embedding status
- retry failed embeddings

### Phase 7 — UI Completion

- import screen
- preview screen
- conflict/duplicate status
- result report
- rollback button

### Phase 8 — Rollback

- rollback batch from SQLite
- delete Qdrant vectors
- mark batch rolled back
- audit rollback

### Phase 9 — Testing and Hardening

- unit tests
- integration tests
- security tests
- import demo bundle

---

## 36. Critical Constraints for Coding Agent

The coding agent must follow these constraints:

1. Do not create a separate memory system for imported memories.
2. Imported memories must become native Shogun memories.
3. Do not bypass SQLite Archive persistence.
4. Do not bypass Qdrant embedding/upsert.
5. Do not bypass EventLogger.
6. Do not import without preview.
7. Do not overwrite existing memories silently.
8. Do not execute imported Markdown as instructions during import.
9. Do not allow ZIP path traversal.
10. Do not silently discard unknown metadata.
11. Do not silently discard `decay_type`.
12. Do not fail entire batch because one file is invalid.
13. Do not report success if Qdrant embedding failed.
14. Do not delete pre-existing memories during rollback.
15. Keep the implementation compatible with Order 16 export format.

---

## 37. Final Design Sentence

Build Order 17 around this sentence:

> **OpenClaw Markdown Import turns external Markdown memories into native Shogun Archive memories by parsing, validating, normalizing, deduplicating, storing, embedding, auditing, and making them searchable through the existing Shogun memory system.**

That is the feature.

That is the portability promise.

That is what completes the memory import/export loop.

---
