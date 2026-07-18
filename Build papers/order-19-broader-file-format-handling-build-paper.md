# Order 19 — Shogun AFM Broader File Format Handling
## Build Paper for Native Parsing, Inspection, Transformation, Indexing, and Safe Tool Use Across Common File Types

---

## 1. Executive Summary

This build paper defines **Order 19 — Broader File Format Handling** for Shogun AFM.

Orders 1–18 are assumed implemented, including Agent Stacks, Stack Orchestrator, visual execution, context compaction, self-verification, image viewing in chat, VS Code IDE Mode, model routing, active skill usage, Ronin Desktop Control, Mado hardening, CUA/ALE plumbing, SkillOpt, OpenClaw memory portability, and improved memory decay handling.

Order 19 expands Shogun’s ability to work with real-world files beyond the currently supported PDF, Office, image, text, and memory formats.

The goal is to add a **File Format Adapter Layer** that lets Shogun safely inspect, parse, summarize, transform, validate, index, and generate artifacts from additional formats such as:

- CSV
- TSV
- JSON
- JSONL / NDJSON
- XML
- YAML
- TOML
- INI / CFG
- Markdown
- HTML
- logs
- source code files
- archives such as ZIP
- selected proprietary or domain-specific formats through pluggable adapters

The key principle is:

> **Shogun should not treat every file as generic text. It should identify the file type, apply the right parser, create a normalized representation, expose safe tools, and preserve the original artifact.**

This feature is not mainly about adding dozens of parsers. It is about building a durable architecture that allows new file formats to be added cleanly over time.

---

## 2. Strategic Purpose

Shogun is now capable of long-horizon, governed, self-verifying work. That means it will increasingly encounter files from real companies, coding projects, websites, exports, logs, APIs, ERP systems, and operational processes.

A serious agent framework cannot only handle PDFs and Office documents.

It must understand:

- data exports
- configuration files
- structured API payloads
- code repositories
- logs
- system outputs
- scraped content
- archived files
- semi-structured documents
- domain-specific data files

Order 19 strengthens Shogun in four ways:

1. **Daily usefulness** — users can send more file types and expect Shogun to understand them.
2. **ALE/test readiness** — many benchmark and sandbox tasks use structured files, code files, logs, and generated artifacts.
3. **Coding capability** — VS Code IDE Mode and Agent Stacks need native understanding of code/config/data files.
4. **Enterprise credibility** — company workflows often rely on exports from ERP, CRM, BI, procurement, finance, and operational systems.

The strategic message is:

> **Shogun can work with the files companies actually use, not only polished documents.**

---

## 3. Core Design Principle

The implementation must follow this principle:

> **Detect first. Parse deterministically. Normalize. Then let the agent reason.**

Do not let the LLM be the first parser for structured files.

Bad approach:

```text
Open CSV as raw text → send entire file to model → ask model what it means
```

Correct approach:

```text
Detect file type → parse with trusted parser → validate structure → create preview/statistics/schema → expose safe tool interface → let model reason from structured output
```

This improves:

- reliability
- security
- cost
- context efficiency
- repeatability
- auditability
- self-verification

---

## 4. Product Name

Recommended internal feature name:

# File Format Adapter Layer

User-facing feature name:

# Broader File Format Handling

Optional UI section:

```text
Files → Format Support
```

Agent-facing language:

```text
file.inspect
file.parse
file.preview
file.query
file.transform
file.validate
file.export
```

---

## 5. Scope

### 5.1 In Scope

Order 19 must add support for:

#### Structured Data

- CSV
- TSV
- JSON
- JSONL / NDJSON
- XML
- YAML
- TOML
- INI / CFG

#### Semi-Structured Content

- Markdown
- HTML
- plain text variants
- logs
- delimited text

#### Code and Development Files

- Python
- JavaScript
- TypeScript
- HTML/CSS
- SQL
- shell scripts
- PowerShell
- Dockerfile
- package manifests
- config files

#### Archives

- ZIP inspection
- list contents
- extract selected files safely
- block unsafe extraction paths

#### Proprietary / Domain-Specific Adapter Hooks

- generic plugin interface
- unknown binary fallback
- metadata extraction
- safe preview where possible

---

### 5.2 Out of Scope for First Release

Do not build full native support for every proprietary format in the first release.

Out of scope initially:

- full CAD parsing
- full accounting system native formats
- full BI project file parsing
- encrypted archive cracking
- password-protected file bypassing
- malware analysis
- arbitrary binary reverse engineering
- automatic execution of scripts
- automatic macro execution
- unrestricted archive extraction
- modification of binary proprietary files without a dedicated adapter

These can be added later through the adapter system.

---

## 6. Architecture Overview

The architecture should be:

```text
User / Agent / Stack Orchestrator
        ↓
Shogun File Tool API
        ↓
File Format Adapter Layer
        ↓
Type Detection + Safety Gate
        ↓
Format-Specific Adapter
        ↓
Normalized File Representation
        ↓
Preview / Query / Transform / Validate / Export
        ↓
Artifact Registry + Memory + Audit
```

The feature must integrate with:

- Stack Orchestrator
- Agent Stacks
- VS Code IDE Mode
- Mado
- Productivity App Mode
- Memory Archive
- EventLogger
- ToolGate / posture permissions
- Self-Verification Layer

---

## 7. Core Components

### 7.1 File Format Adapter Registry

Create a central registry where supported formats are declared.

Each adapter should declare:

```json
{
  "format_id": "csv",
  "display_name": "CSV",
  "extensions": [".csv"],
  "mime_types": ["text/csv"],
  "capabilities": ["inspect", "parse", "preview", "query", "transform", "export"],
  "risk_level": "low",
  "supports_write": true,
  "supports_indexing": true
}
```

The registry should allow new adapters to be added without modifying the core file tool logic.

---

### 7.2 File Type Detection Service

Implement a robust detection pipeline.

Detection order:

1. file extension
2. MIME type where available
3. content sniffing
4. magic bytes where relevant
5. parser trial in safe mode
6. unknown fallback

The result should include confidence:

```json
{
  "detected_format": "json",
  "confidence": 0.97,
  "method": "content_sniffing",
  "extension": ".txt",
  "mime_type": "text/plain"
}
```

Do not rely only on extension.

A `.txt` file may contain JSON.
A `.csv` file may be semicolon-delimited.
A `.log` file may contain JSONL.

---

### 7.3 File Safety Gate

Before parsing, the file must pass safety checks.

Checks:

- maximum file size
- allowed path/workspace
- blocked extension list
- archive bomb protection
- binary detection
- executable/script risk classification
- protected file detection
- secret file pattern detection
- symlink/path traversal check

Example blocked or high-risk extensions:

```text
.exe
.dll
.bat
.cmd
.scr
.msi
.app
.dmg
.iso
```

Scripts are not necessarily blocked from reading, but must be blocked from execution unless the posture/tool policy allows it.

---

### 7.4 Normalized File Representation

Every adapter should return a normalized representation.

Base shape:

```json
{
  "file_id": "uuid",
  "format_id": "csv",
  "path": "/workspace/input/customers.csv",
  "size_bytes": 184920,
  "encoding": "utf-8",
  "summary": "CSV file with 1,248 rows and 14 columns.",
  "schema": {},
  "preview": {},
  "warnings": [],
  "capabilities": []
}
```

This normalized representation is what agents should consume first.

Do not send full raw files to the model unless needed and approved.

---

## 8. Adapter Requirements by Format

---

## 8.1 CSV / TSV Adapter

### Capabilities

- detect delimiter
- detect encoding
- detect header row
- count rows and columns
- infer column types
- preview first N rows
- sample rows
- query rows
- validate consistency
- detect missing values
- detect duplicate rows
- export filtered CSV
- convert to JSON/Markdown table where small enough

### Required Tools

```text
file.csv.inspect
file.csv.preview
file.csv.schema
file.csv.query
file.csv.profile
file.csv.export
```

### Output Example

```json
{
  "rows": 1248,
  "columns": 14,
  "delimiter": ",",
  "has_header": true,
  "column_types": {
    "customer_id": "string",
    "created_at": "date",
    "revenue": "number"
  },
  "missing_values": {
    "email": 23,
    "phone": 118
  }
}
```

### Security Notes

CSV formula injection must be considered when exporting.

If exporting CSV values that begin with:

```text
= + - @
```

then add safe export option:

```json
{"sanitize_formulas": true}
```

---

## 8.2 JSON Adapter

### Capabilities

- validate JSON
- infer schema
- preview structure
- query by path
- extract keys
- summarize nested structures
- convert to table where possible
- pretty-print
- minify
- export selected paths

### Required Tools

```text
file.json.inspect
file.json.validate
file.json.schema
file.json.query_path
file.json.extract
file.json.pretty_print
```

### JSON Path Support

Support simple path expressions first:

```text
$.customers[0].name
$.orders[*].total
```

Advanced JSONPath can be added later.

---

## 8.3 JSONL / NDJSON Adapter

### Capabilities

- parse line-delimited JSON
- validate line-by-line
- count valid/invalid records
- infer schema across records
- sample records
- filter records
- export subset
- detect log-like structures

### Required Tools

```text
file.jsonl.inspect
file.jsonl.sample
file.jsonl.schema
file.jsonl.filter
file.jsonl.invalid_lines
```

This is important for logs, event streams, LLM traces, and ALE trajectories.

---

## 8.4 XML Adapter

### Capabilities

- parse XML safely
- prevent XXE attacks
- extract root structure
- list tags
- infer repeating elements
- query basic XPath-like paths
- convert selected branches to JSON
- validate well-formedness

### Required Tools

```text
file.xml.inspect
file.xml.validate
file.xml.list_tags
file.xml.query
file.xml.to_json
```

### Security Notes

Use safe XML parsing only.

Disable:

- external entity resolution
- DTD loading unless explicitly needed
- network fetching

This is mandatory.

---

## 8.5 YAML Adapter

### Capabilities

- safe parse
- validate syntax
- inspect keys
- query paths
- convert to JSON
- pretty-print
- detect config-like structures

### Required Tools

```text
file.yaml.inspect
file.yaml.validate
file.yaml.query
file.yaml.to_json
```

### Security Notes

Use safe loader only.

Never execute YAML tags or constructors.

---

## 8.6 TOML / INI / CFG Adapter

### Capabilities

- parse config files
- list sections
- query keys
- validate syntax
- convert to JSON
- compare config files

### Required Tools

```text
file.config.inspect
file.config.query
file.config.validate
file.config.diff
```

---

## 8.7 Markdown Adapter

### Capabilities

- parse headings
- extract outline
- extract links
- extract tables
- split by sections
- generate summary
- validate internal links where possible
- convert to HTML where needed

### Required Tools

```text
file.markdown.inspect
file.markdown.outline
file.markdown.extract_tables
file.markdown.extract_links
file.markdown.section
```

This supports OpenClaw memory exports, documentation, README files, and generated skill files.

---

## 8.8 HTML Adapter

### Capabilities

- parse static HTML
- extract title
- extract visible text
- extract links
- extract tables
- extract forms metadata
- clean boilerplate where possible
- convert to Markdown

### Required Tools

```text
file.html.inspect
file.html.extract_text
file.html.extract_links
file.html.extract_tables
file.html.to_markdown
```

### Relationship to Mado

Mado handles live browser interaction.

The HTML adapter handles saved/static HTML files.

Do not duplicate Mado functionality.

---

## 8.9 Log File Adapter

### Capabilities

- detect timestamp patterns
- detect severity levels
- group errors/warnings
- extract stack traces
- summarize events
- identify repeated errors
- filter by time/severity
- detect JSONL logs

### Required Tools

```text
file.log.inspect
file.log.errors
file.log.warnings
file.log.timeline
file.log.search
file.log.summarize
```

This is especially important for:

- debugging Shogun
- coding campaigns
- ALE trajectories
- VS Code/terminal output
- browser automation failures

---

## 8.10 Code File Adapter

### Capabilities

For source files, the first version should not try to fully compile all languages.

It should support:

- language detection
- line count
- imports/dependencies where easy
- functions/classes extraction where available
- comments/docstrings extraction
- outline generation
- symbol search
- safe preview
- diff support

### Required Tools

```text
file.code.inspect
file.code.outline
file.code.symbols
file.code.imports
file.code.search
file.code.preview
```

### Integration With VS Code IDE Mode

If VS Code IDE Mode is active, deeper code intelligence should be delegated to IDE/LSP tools when available.

Rule:

> **File Format Handling gives baseline code understanding. VS Code IDE Mode gives IDE-grade code intelligence.**

Do not duplicate LSP features unnecessarily.

---

## 8.11 ZIP Archive Adapter

### Capabilities

- list archive contents
- inspect file sizes
- detect nested archives
- identify suspicious paths
- extract selected files safely
- extract to approved workspace only
- block path traversal
- block absolute paths
- block overwrite unless approved

### Required Tools

```text
file.archive.inspect
file.archive.list
file.archive.extract_selected
file.archive.safety_report
```

### Archive Safety Rules

Block:

```text
../ path traversal
absolute extraction paths
symlink escape
archive bombs
unexpected executable extraction
silent overwrite
```

Extraction must always happen under an approved workspace/artifact directory.

---

## 8.12 Unknown / Proprietary File Adapter

For unsupported files, return a safe fallback.

Capabilities:

- metadata extraction
- binary/text classification
- extension/MIME report
- safe hex/text preview for small files
- recommendation for required adapter
- optional user-provided description

Required tool:

```text
file.unknown.inspect
```

The agent should say:

```text
This file type is not natively supported yet. I can inspect metadata and safe previews, but I should not claim to fully parse it.
```

This prevents false confidence.

---

## 9. Agent-Facing Tool Layer

Expose a provider-neutral file tool set.

### 9.1 Generic Tools

```text
file.detect_type
file.inspect
file.preview
file.schema
file.query
file.extract
file.transform
file.validate
file.export
file.compare
file.index
```

The agent should usually call:

```text
file.inspect
```

first. Shogun then routes to the correct adapter.

---

### 9.2 Tool Output Shape

All file tools must return:

```json
{
  "status": "success",
  "file_id": "uuid",
  "format_id": "csv",
  "operation": "inspect",
  "summary": "CSV with 1,248 rows and 14 columns.",
  "data": {},
  "warnings": [],
  "artifacts": [],
  "audit_event_id": "uuid"
}
```

If parsing fails:

```json
{
  "status": "failed",
  "error_type": "parse_error",
  "message": "Invalid JSON at line 42, column 9.",
  "safe_preview_available": true,
  "warnings": []
}
```

---

## 10. File Registry Integration

All handled files should be registered in Shogun’s artifact/file registry.

Required metadata:

```json
{
  "file_id": "uuid",
  "original_filename": "orders.csv",
  "path": "/workspace/uploads/orders.csv",
  "format_id": "csv",
  "detected_at": "timestamp",
  "size_bytes": 184920,
  "hash_sha256": "...",
  "source": "telegram_upload | workspace | ide | mado_download | generated",
  "permissions": {},
  "last_inspected_at": "timestamp"
}
```

This allows Stack Orchestrator and agents to reference files by `file_id`, not raw paths.

Rule:

> **Agents should prefer file IDs over raw paths.**

---

## 11. Memory and Indexing Integration

Some file types should be indexable into Shogun memory/archive.

### 11.1 Indexable Formats

- Markdown
- text
- HTML text extraction
- JSON/JSONL selected fields
- XML selected branches
- logs summaries
- code summaries
- CSV schema/profiles and selected rows

### 11.2 Do Not Blindly Embed Everything

Do not embed entire large CSVs, JSON dumps, or logs as raw chunks.

Instead:

- create schema summaries
- create profiles
- embed meaningful summaries
- embed selected rows/records only when requested
- store raw artifact reference separately

Correct approach:

```text
Store file profile + schema + summary in memory.
Keep full file as artifact.
Query file through structured file tools when needed.
```

---

## 12. Stack Orchestrator Integration

The Stack Orchestrator must be able to use file tools as stack steps.

Example stack:

```text
Inspect uploaded ZIP
  → Extract selected CSV files
  → Profile CSVs
  → Validate JSON config
  → Read logs
  → Generate issue summary
  → Verify expected files were processed
```

The Stack Orchestrator should:

- inspect file type before deciding action
- use deterministic parser first
- checkpoint after file extraction or transformation
- store generated artifacts
- self-verify output files
- retry failed parsing with fallback strategy
- escalate if unsupported/proprietary format is encountered

---

## 13. Self-Verification Integration

Order 19 must support verification.

Examples:

### CSV Verification

```text
Expected: Output CSV has same number of rows as input and includes new column "status".
Verify: parse output CSV, count rows, check columns.
```

### JSON Verification

```text
Expected: JSON is valid and contains key $.config.enabled.
Verify: validate JSON and query key.
```

### Archive Verification

```text
Expected: ZIP extraction produced 3 CSV files and no executable files.
Verify: inspect extracted artifact list.
```

### Markdown Verification

```text
Expected: README contains sections Installation, Usage, Configuration.
Verify: parse headings.
```

The Self-Verification Layer should use file adapters rather than LLM-only checks when possible.

---

## 14. Posture and Permission Rules

File handling must respect Shogun posture rules.

### 14.1 Default Access

| Posture | Behavior |
|---|---|
| Locked | No file handling unless system/internal allowed |
| Guarded | Read/inspect approved files only |
| Supervised | Read/inspect/limited transform with approvals |
| Campaign | Full approved workspace file handling |
| Ronin | Broad file handling according to Ronin permissions |

### 14.2 Risk-Based Actions

| Action | Risk | Default |
|---|---:|---|
| Inspect CSV/JSON/Markdown | Low | Allow in approved workspace |
| Parse XML safely | Medium | Allow with safe parser |
| Extract ZIP | Medium/High | Approval or policy required |
| Modify config file | Medium | Approval depending on posture |
| Execute script | Critical | Not part of file handling; blocked unless separate tool allows |
| Access secrets file | Critical | Block by default |
| Parse unknown binary | Medium | Metadata only |
| Export transformed file | Medium | Allow in approved output folder |

---

## 15. Security Requirements

### 15.1 General Security

- Never execute files while parsing.
- Never run macros.
- Never resolve XML external entities.
- Never extract archives outside approved directories.
- Never trust file extensions alone.
- Never expose secrets by default.
- Never overwrite user files without approval or versioned output.
- Never parse unbounded large files into memory.

---

### 15.2 Large File Handling

Set limits:

```json
{
  "max_preview_bytes": 1048576,
  "max_parse_bytes_default": 52428800,
  "max_rows_preview": 100,
  "max_json_depth": 100,
  "max_archive_uncompressed_bytes": 524288000
}
```

For large files, use streaming where possible.

---

### 15.3 Secret Detection

Before previewing or indexing, scan for likely secrets:

- API keys
- private keys
- tokens
- passwords
- `.env` style variables
- connection strings

If detected, mask in previews unless explicit permission exists.

---

## 16. UI Requirements

Add a file inspection panel in Shogun/Katana.

### 16.1 File Detail View

Show:

- filename
- detected format
- confidence
- size
- source
- hash
- parser used
- capabilities
- warnings
- preview
- schema/profile
- available actions

---

### 16.2 Supported Formats Page

Add:

```text
Settings → File Formats
```

Show table:

| Format | Extensions | Read | Write | Query | Export | Index | Adapter Status |
|---|---|---:|---:|---:|---:|---:|---|

---

### 16.3 Unsupported File UI

When unsupported:

```text
This file type is not natively supported yet.
Shogun can inspect metadata and safe preview only.
```

Add option:

```text
Request/Create Adapter
```

This can later feed OpenClaw College skill/content loops.

---

## 17. Backend API Design

Add endpoints:

```http
POST /api/v1/files/detect
POST /api/v1/files/inspect
POST /api/v1/files/preview
POST /api/v1/files/query
POST /api/v1/files/validate
POST /api/v1/files/transform
POST /api/v1/files/export
GET  /api/v1/files/{file_id}
GET  /api/v1/files/{file_id}/capabilities
GET  /api/v1/files/formats
```

For archives:

```http
POST /api/v1/files/archive/inspect
POST /api/v1/files/archive/extract-selected
```

For code files:

```http
POST /api/v1/files/code/outline
POST /api/v1/files/code/symbols
```

---

## 18. Configuration

Add to `setup.json`:

```json
{
  "file_format_handling": {
    "enabled": true,
    "detect_by_content": true,
    "safe_parsing": true,
    "max_preview_bytes": 1048576,
    "max_parse_bytes_default": 52428800,
    "max_rows_preview": 100,
    "mask_secrets_in_preview": true,
    "archive_extraction": {
      "enabled": true,
      "requires_approval": true,
      "max_uncompressed_bytes": 524288000,
      "block_executables": true
    },
    "indexing": {
      "enabled": true,
      "embed_full_large_files": false,
      "store_profiles_in_memory": true
    }
  }
}
```

---

## 19. Recommended Python Libraries

Use stable, common libraries where possible.

Suggested:

```text
csv / pandas / polars        CSV/TSV profiling
json                         JSON
ijson                        streaming JSON if needed
jsonlines                    JSONL
defusedxml                   safe XML parsing
pyyaml                       YAML safe_load only
tomllib / tomli              TOML
configparser                 INI/CFG
markdown-it-py               Markdown parsing
beautifulsoup4 / lxml        HTML parsing, with safety constraints
zipfile                      ZIP handling with safety wrapper
chardet / charset-normalizer encoding detection
pygments                     code language detection/highlighting
```

Do not overbuild first release with heavy dependencies unless needed.

---

## 20. Implementation Order

### Phase 1 — Core Infrastructure

1. Build File Format Adapter Registry
2. Build File Type Detection Service
3. Build File Safety Gate
4. Build Normalized File Representation
5. Integrate with File Registry/Artifact Registry
6. Add audit events

### Phase 2 — Structured Data Adapters

7. CSV/TSV adapter
8. JSON adapter
9. JSONL/NDJSON adapter
10. XML safe adapter
11. YAML adapter
12. TOML/INI/CFG adapter

### Phase 3 — Semi-Structured and Code Adapters

13. Markdown adapter
14. HTML adapter
15. Log adapter
16. Code file adapter

### Phase 4 — Archive and Unknown Fallback

17. ZIP archive adapter
18. Unknown/proprietary fallback adapter
19. Safe metadata/preview handling
20. Adapter capability reporting

### Phase 5 — Agent and Stack Integration

21. Generic agent-facing file tools
22. Stack Orchestrator file step support
23. Self-verification file checks
24. Memory/indexing integration
25. Context-efficient summaries

### Phase 6 — UI and Testing

26. File detail view
27. Supported formats page
28. Unsupported file messaging
29. Unit tests
30. Integration tests
31. Security tests
32. Demo flows

---

## 21. Audit Events

Add events:

```text
file.format.detected
file.format.detection_failed
file.inspect.started
file.inspect.completed
file.inspect.failed
file.parse.started
file.parse.completed
file.parse.failed
file.preview.generated
file.schema.generated
file.query.executed
file.validation.completed
file.transform.started
file.transform.completed
file.export.created
file.archive.inspected
file.archive.extraction_requested
file.archive.extraction_completed
file.archive.extraction_blocked
file.secret.detected
file.unsupported.detected
file.adapter.error
```

All events must go through the existing Shogun EventLogger pipeline.

---

## 22. Testing Requirements

### 22.1 Unit Tests

Test:

- detection by extension
- detection by content
- wrong extension handling
- CSV delimiter inference
- CSV schema inference
- JSON validation
- JSONL invalid line handling
- XML external entity blocking
- YAML safe loading
- Markdown outline extraction
- HTML text extraction
- ZIP path traversal blocking
- unknown file fallback
- secret masking
- large file limits

---

### 22.2 Integration Tests

Test end-to-end:

- upload CSV through Telegram/chat
- inspect JSON from workspace
- parse logs from coding run
- inspect ZIP and extract selected files
- use Stack Orchestrator to process multiple files
- self-verify transformed output
- index file profile into memory

---

### 22.3 Security Tests

Must block:

- XML XXE payload
- ZIP slip path traversal
- archive bomb above threshold
- file outside workspace
- preview of secrets without masking
- script execution through file handling
- unsafe YAML constructor execution
- overwrite without approval

---

## 23. Acceptance Criteria

Order 19 is complete when:

1. File Format Adapter Registry exists.
2. File type detection works by extension, MIME, and content sniffing.
3. File Safety Gate blocks unsafe parsing/extraction.
4. CSV/TSV inspection works.
5. JSON validation and querying works.
6. JSONL inspection works.
7. XML safe parsing works with external entities disabled.
8. YAML safe parsing works.
9. TOML/INI/CFG parsing works.
10. Markdown outline extraction works.
11. HTML text/link/table extraction works.
12. Log inspection and error grouping works.
13. Code file baseline inspection works.
14. ZIP inspection and safe selected extraction works.
15. Unknown/proprietary fallback works honestly.
16. Agent-facing generic file tools are available.
17. Stack Orchestrator can use file tools as steps.
18. Self-Verification can validate file outputs.
19. File profiles can be stored/indexed without embedding entire large files.
20. Secrets are masked in previews by default.
21. All file actions are audited.
22. UI shows detected format, preview, capabilities, and warnings.
23. Tests cover normal, large, malformed, and hostile files.
24. Existing PDF/Office/image/text support is not broken.

---

## 24. Recommended Demo

Demo name:

```text
Order 19 — Multi-File Processing Demo
```

Demo input:

```text
A ZIP file containing:
- customers.csv
- orders.jsonl
- config.yaml
- error.log
- README.md
```

Expected Shogun flow:

```text
1. Inspect ZIP
2. Safety-check archive
3. Extract selected files to approved workspace
4. Detect each file format
5. Profile CSV
6. Inspect JSONL schema
7. Validate YAML config
8. Summarize log errors
9. Extract README outline
10. Generate combined analysis report
11. Self-verify report contains required sections
12. Store report as artifact
```

This demo proves Shogun can handle messy operational file packages, not just polished documents.

---

## 25. Coding Agent Constraints

The coding agent must follow these constraints:

1. Do not treat all files as raw text.
2. Do not send full large files to the model by default.
3. Do not execute files while parsing.
4. Do not run macros.
5. Do not allow XML external entity resolution.
6. Do not allow unsafe YAML constructors.
7. Do not extract archives outside approved directories.
8. Do not trust extensions alone.
9. Do not overwrite source files without approval or versioning.
10. Do not index entire large structured files blindly.
11. Do not bypass File Registry or Artifact Registry.
12. Do not bypass posture/tool permissions.
13. Do not create a separate audit pipeline.
14. Do not claim unsupported proprietary files are parsed.
15. Preserve existing Shogun file handling behavior.

---

## 26. Final Design Sentence

Order 19 should be built around this sentence:

> **Shogun’s File Format Adapter Layer lets agents safely understand, query, transform, verify, and index real-world file formats through deterministic parsers, normalized representations, posture-aware permissions, and full auditability.**

That is the purpose of Broader File Format Handling.

It makes Shogun better prepared for real company files, coding projects, ALE tasks, and long autonomous workflows.

---
