# Order 15 — Shogun AFM Build Paper
# OpenClaw College Content Loop
## Skill Creation, Publishing, Usage, Optimization, and Re-Publishing Pipeline

---

## 1. Executive Summary

This build paper defines **Order 15: OpenClaw College Content Loop** for Shogun AFM.

The purpose is to create a closed-loop skill ecosystem where Shogun can:

1. create high-quality skill content,
2. validate the skill through local tests,
3. publish the skill to OpenClaw College,
4. install the skill into Shogun,
5. actively use the skill during real work,
6. capture usage trajectories,
7. optimize the skill through SkillOpt,
8. re-test the improved skill,
9. re-publish the improved version,
10. preserve a full audit trail of skill evolution.

This turns OpenClaw College from a passive skill repository into a living skill supply chain for Shogun.

The core idea:

> **Shogun should not only consume skills. Shogun should create, use, evaluate, improve, and republish them.**

Order 15 assumes that Orders 1–14 are already implemented, especially:

- Agent Stacks
- Stack Orchestrator
- Visual Execution / Stack Trace View
- Context Compaction
- Self-Verification Layer
- Image Viewing in Chat
- VS Code IDE Mode
- Model Routing Profiles
- Active Skill Usage
- Skill Usage Logging / Trajectory Capture
- Ronin Desktop Control
- Mado Hardening
- CUA MCP Bridge + ALE Deployer
- SkillOpt Integration

Order 15 builds on these foundations.

---

## 2. Strategic Purpose

OpenClaw College should become Shogun’s skill distribution and improvement ecosystem.

The strategic purpose is to make Shogun better over time without depending only on larger frontier models.

The value proposition is:

> **Better skills + real trajectories + validation gates + SkillOpt = higher effective agent capability.**

This supports the broader Shogun thesis:

> **The future is not only bigger models. It is better harnesses, better skills, better memory, better evaluation, and better orchestration around models.**

OpenClaw College Content Loop is the mechanism that makes that thesis operational.

---

## 3. Product Positioning

Recommended internal feature name:

# OpenClaw College Content Loop

Recommended shorter UI name:

# Skill Publishing Loop

Recommended technical name:

# Skill Lifecycle Pipeline

Recommended external language:

> OpenClaw College allows Shogun skills to move through a complete lifecycle: creation, validation, publishing, installation, active use, optimization, and re-publication.

---

## 4. Core Principle

The core principle is:

> **A Shogun skill is not complete when it is written. It is complete when it has been used, measured, improved, validated, and versioned.**

This means skills must be treated as managed assets, not loose markdown files.

Each skill must have:

- identity
- version
- author/source
- category
- description
- requirements
- expected use cases
- validation tests
- usage history
- performance metrics
- optimization history
- compatibility metadata
- publication status
- rollback path

---

## 5. Problem Statement

Currently, installed skills can exist as catalog items.

That is not enough.

The gap is that skills need a full operational lifecycle:

```text
Create skill
  → validate skill
  → publish skill
  → install skill
  → use skill in daily work
  → log trajectories
  → optimize skill
  → validate improved skill
  → publish new version
```

Without this loop:

- skills become stale,
- low-quality skills enter the catalog,
- SkillOpt lacks useful trajectory data,
- users cannot trust skill quality,
- OpenClaw College becomes a storage site instead of a learning ecosystem,
- Shogun cannot prove that its skill system improves over time.

---

## 6. Scope

Order 15 must implement the full OpenClaw College content loop.

The scope includes:

1. Skill content schema
2. Skill authoring workflow
3. Skill quality gate
4. Skill validation tests
5. Local skill registry integration
6. OpenClaw College publishing adapter
7. Skill installation verification
8. Skill usage tracking integration
9. Skill performance metrics
10. SkillOpt handoff and re-ingestion
11. Skill versioning
12. Skill re-publication
13. Skill rollback
14. Skill lifecycle UI in Katana
15. Audit logging
16. Demo workflow

---

## 7. Non-Goals

This build must not attempt to build a full marketplace.

Do not build:

- payment system
- user ratings
- public review moderation
- paid skill licensing
- complex author profiles
- social/community layer
- third-party developer portal
- web-scale package registry
- automatic public publishing without validation
- automatic skill overwrite without versioning

The first release should be a controlled skill lifecycle loop for Shogun and OpenClaw College.

---

## 8. Required Skill Lifecycle

The skill lifecycle must support the following states.

```text
Draft
Validated
Published
Installed
Active
Observed
Optimized
Revalidated
Republished
Deprecated
Archived
```

### 8.1 State Definitions

| State | Meaning |
|---|---|
| Draft | Skill has been created but not validated. |
| Validated | Skill passed local validation tests. |
| Published | Skill has been published to OpenClaw College. |
| Installed | Skill has been installed into a Shogun instance. |
| Active | Skill is available for active use during tasks. |
| Observed | Skill has real usage trajectories attached. |
| Optimized | SkillOpt has proposed an improved version. |
| Revalidated | Improved version passed validation. |
| Republished | Improved version published as a new version. |
| Deprecated | Skill should no longer be used by default. |
| Archived | Skill is retained for history but removed from active use. |

---

## 9. Skill Package Format

Each OpenClaw College skill should be packaged as a folder or archive.

Recommended structure:

```text
skill_name/
  skill.md
  manifest.json
  validation.yaml
  examples/
    example_001.md
    example_002.md
  tests/
    test_001.yaml
    test_002.yaml
  changelog.md
  metrics.json
```

---

## 10. Skill Manifest

Each skill must have a manifest.

File:

```text
manifest.json
```

Example:

```json
{
  "skill_id": "business_email_reply_v1",
  "name": "Business Email Reply",
  "version": "1.0.0",
  "description": "Helps Shogun draft concise and professional business email replies.",
  "category": "communication",
  "author": "Alpha Horizon",
  "source": "shogun_generated",
  "created_at": "2026-07-17T00:00:00Z",
  "updated_at": "2026-07-17T00:00:00Z",
  "minimum_shogun_version": "0.0.0",
  "compatible_postures": ["guarded", "supervised", "campaign", "ronin"],
  "required_tools": [],
  "optional_tools": ["gmail", "productivity.document"],
  "risk_tier": "low",
  "activation_triggers": [
    "email reply",
    "business response",
    "professional email",
    "reply to client"
  ],
  "input_types": ["text", "email_thread"],
  "output_types": ["draft_text"],
  "validation_status": "validated",
  "publication_status": "draft",
  "parent_skill_id": null,
  "supersedes": null,
  "license": "OpenClaw College Skill License",
  "tags": ["email", "communication", "business"]
}
```

---

## 11. Skill Markdown Format

File:

```text
skill.md
```

Recommended format:

```md
---
skill_id: business_email_reply_v1
name: Business Email Reply
version: 1.0.0
category: communication
risk_tier: low
activation_triggers:
  - email reply
  - business response
  - professional email
required_tools: []
optional_tools:
  - gmail
  - productivity.document
---

# Skill: Business Email Reply

## Purpose

Use this skill when drafting concise, clear, professional business email replies.

## When To Use

Use when the user asks to:

- reply to a business email
- draft a client response
- answer a recruiter
- respond to a partner
- make an email sharper or more professional

## Operating Instructions

1. Read the source message carefully.
2. Identify the sender's intent.
3. Identify required response points.
4. Keep the reply concise unless the user asks for detail.
5. Avoid unnecessary enthusiasm.
6. Match the user’s desired tone if provided.
7. Do not send the email unless explicitly instructed.

## Output Standard

The output should be:

- clear
- professional
- concise
- ready to copy or save as draft

## Failure Modes

Avoid:

- over-explaining
- inventing commitments
- using excessive praise
- sending without approval

## Validation Criteria

The skill passes if the produced reply:

- answers the source message
- preserves factual accuracy
- uses appropriate tone
- does not invent unsupported details
- is concise and usable
```

---

## 12. Validation Test Format

File:

```text
tests/test_001.yaml
```

Example:

```yaml
id: test_business_email_reply_001
skill_id: business_email_reply_v1
test_type: output_quality
input:
  user_request: "Write a short reply to this client asking for a follow-up meeting next week."
  source_message: "Hi Michael, can we schedule a follow-up next week to discuss the AI operating model?"
expected:
  must_include:
    - willingness to meet
    - next week
    - request for proposed times or offer times
  must_not_include:
    - unsupported promises
    - excessive length
    - casual slang
scoring:
  pass_threshold: 0.80
  criteria:
    relevance: 0.30
    factuality: 0.25
    tone: 0.20
    concision: 0.15
    safety: 0.10
```

---

## 13. Skill Quality Gate

No skill should be published to OpenClaw College unless it passes a quality gate.

Required checks:

1. Manifest exists
2. Skill markdown exists
3. Required metadata exists
4. Activation triggers exist
5. Risk tier is assigned
6. Tool requirements are declared
7. Validation tests exist
8. At least one validation test passes
9. No forbidden instructions exist
10. No hidden credential requests exist
11. No posture bypass instructions exist
12. Version number is valid
13. Changelog exists
14. Audit event is recorded

### 13.1 Quality Gate Result

Example:

```json
{
  "skill_id": "business_email_reply_v1",
  "version": "1.0.0",
  "status": "passed",
  "checks": {
    "manifest_exists": true,
    "skill_markdown_exists": true,
    "activation_triggers_exist": true,
    "validation_tests_exist": true,
    "validation_tests_passed": true,
    "risk_tier_declared": true,
    "no_forbidden_instructions": true,
    "version_valid": true
  },
  "score": 0.92
}
```

---

## 14. Skill Authoring Workflow

Shogun must support skill creation through a controlled workflow.

### 14.1 Manual Skill Creation

User creates a skill manually in Katana.

Flow:

```text
Create Skill
  → Fill metadata
  → Write skill instructions
  → Add triggers
  → Add validation tests
  → Run quality gate
  → Save as draft or publish
```

### 14.2 Shogun-Generated Skill Creation

Shogun creates a skill from observed repeated work.

Example:

```text
User frequently asks Max to summarize LinkedIn posts.
Shogun detects repeated pattern.
Shogun proposes a new skill: LinkedIn Reply Assistant.
User approves.
Shogun creates skill draft.
Shogun validates it.
User publishes it.
```

### 14.3 Skill Creation From Trajectory

Shogun creates a skill from a successful task trajectory.

Flow:

```text
Completed task
  → identify reusable procedure
  → extract operating instructions
  → create draft skill
  → create tests from original task
  → validate
  → publish
```

---

## 15. OpenClaw College Publishing Adapter

Build an adapter that allows Shogun to publish validated skills to OpenClaw College.

Recommended internal service:

```text
OpenClawCollegePublisherService
```

Responsibilities:

- package skill folder
- validate manifest
- validate version
- authenticate publishing request if required
- upload skill package
- receive published URL or package ID
- update local skill registry
- log publication event

### 15.1 Publishing Endpoint Abstraction

Do not hard-code the publishing mechanism too tightly.

Create a provider abstraction:

```text
SkillPublishingProvider
```

Initial provider:

```text
OpenClawCollegeProvider
```

Future providers:

```text
GitHubSkillProvider
LocalFolderProvider
PrivateCompanySkillRegistryProvider
```

---

## 16. Publishing Flow

Required publishing flow:

```text
Skill draft
  → quality gate
  → validation tests
  → package skill
  → publish to OpenClaw College
  → receive publication metadata
  → update local registry
  → mark as Published
  → log event
```

### 16.1 Publish Request

Example:

```json
{
  "skill_id": "business_email_reply_v1",
  "version": "1.0.0",
  "provider": "openclaw_college",
  "visibility": "public",
  "package_path": "/skills/business_email_reply_v1",
  "quality_gate_required": true
}
```

### 16.2 Publish Result

Example:

```json
{
  "skill_id": "business_email_reply_v1",
  "version": "1.0.0",
  "status": "published",
  "provider": "openclaw_college",
  "published_url": "https://openclawcollege.com/skills/business-email-reply",
  "published_at": "2026-07-17T00:00:00Z"
}
```

---

## 17. Installation Verification

After publication, Shogun should be able to install the skill from OpenClaw College and verify it.

Flow:

```text
Published skill
  → install from OpenClaw College
  → verify package integrity
  → register locally
  → run smoke test
  → mark as Installed
```

This proves that OpenClaw College is not only receiving skill content, but also serving installable, usable skill packages.

---

## 18. Active Usage Integration

Order 15 depends on Order 9 and Order 10 being implemented.

When a skill is installed and active, Shogun should use it during daily work when activation triggers match.

Required behavior:

1. User asks a task.
2. Skill matcher checks installed skills.
3. Relevant skills are selected.
4. Skill instructions are injected or referenced.
5. Shogun executes task.
6. Trajectory logs include skill usage.
7. Outcome is evaluated.
8. Skill performance metrics are updated.

Example usage event:

```json
{
  "skill_id": "business_email_reply_v1",
  "version": "1.0.0",
  "task_id": "task_123",
  "activation_reason": "matched trigger: business email reply",
  "used_at": "2026-07-17T00:00:00Z",
  "outcome": "success",
  "user_accepted_output": true,
  "verification_score": 0.89
}
```

---

## 19. Skill Performance Metrics

Each skill should accumulate metrics.

Metrics:

- usage count
- success count
- failure count
- average verification score
- user acceptance rate
- retry count
- escalation count
- average cost per use
- model used most often
- tasks where skill failed
- last used timestamp
- last optimized timestamp

Example:

```json
{
  "skill_id": "business_email_reply_v1",
  "version": "1.0.0",
  "usage_count": 42,
  "success_count": 38,
  "failure_count": 4,
  "user_acceptance_rate": 0.90,
  "average_verification_score": 0.87,
  "average_retry_count": 0.4,
  "last_used_at": "2026-07-17T00:00:00Z",
  "last_optimized_at": null
}
```

---

## 20. SkillOpt Integration Loop

Order 15 must integrate with SkillOpt, which is already implemented in Order 14.

The loop is:

```text
Active skill usage
  → trajectory capture
  → performance evaluation
  → SkillOpt proposes edits
  → candidate skill version created
  → validation tests run
  → held-out task tests run
  → accept or reject candidate
  → republish if accepted
```

### 20.1 Candidate Skill Version

SkillOpt must never overwrite a live skill directly.

It must create a candidate version.

Example:

```text
business_email_reply_v1 → business_email_reply_v1.1.0_candidate
```

Candidate states:

```text
candidate_created
candidate_testing
candidate_accepted
candidate_rejected
candidate_published
```

---

## 21. Validation Gate for Optimized Skills

An optimized skill version may only be accepted if it outperforms or matches the previous version on validation tasks.

Minimum acceptance rules:

1. Candidate must pass all safety checks.
2. Candidate must pass existing validation tests.
3. Candidate must not regress on held-out tasks.
4. Candidate must improve at least one target metric or fix a known failure.
5. Candidate must preserve posture/tool restrictions.
6. Candidate must have changelog entry.

Example acceptance result:

```json
{
  "base_skill": "business_email_reply_v1@1.0.0",
  "candidate_skill": "business_email_reply_v1@1.1.0",
  "accepted": true,
  "reason": "Candidate improved concision and reduced unsupported detail in 4/5 held-out tests without safety regression.",
  "base_score": 0.84,
  "candidate_score": 0.89
}
```

---

## 22. Re-Publishing Flow

If an optimized skill candidate is accepted, Shogun must publish it as a new version.

Flow:

```text
Candidate accepted
  → version number assigned
  → changelog updated
  → package built
  → quality gate run
  → publish new version
  → update OpenClaw College metadata
  → update local registry
  → optionally upgrade installed skill
```

Never overwrite old versions.

Old versions must remain available for rollback unless explicitly archived.

---

## 23. Versioning Rules

Use semantic versioning.

```text
MAJOR.MINOR.PATCH
```

Recommended rules:

| Change Type | Version Change |
|---|---|
| Typo, clarity, small wording improvement | Patch |
| Better instruction logic, improved examples, better trigger rules | Minor |
| Major behavior change, new tool requirements, changed risk tier | Major |

Examples:

```text
1.0.0 → 1.0.1 = small wording fix
1.0.0 → 1.1.0 = optimized instructions
1.0.0 → 2.0.0 = changed tool behavior or posture requirements
```

---

## 24. Rollback

Shogun must support rollback to a previous skill version.

Rollback triggers:

- optimized version performs worse
- user reports degradation
- validation failure discovered later
- safety issue discovered
- compatibility issue discovered

Rollback behavior:

```text
Select previous version
  → mark current version deprecated or inactive
  → activate previous version
  → log rollback event
  → optionally notify/publish status update
```

---

## 25. Katana UI Requirements

Add a new section in Katana:

# Skills → OpenClaw College Loop

or:

# Skills → Publishing Loop

### 25.1 Skill Lifecycle View

Show each skill with:

- name
- version
- lifecycle state
- validation score
- usage count
- success rate
- last used
- last optimized
- publication status
- installed status

### 25.2 Skill Detail View

Show:

- skill markdown
- manifest
- triggers
- tests
- examples
- metrics
- trajectory links
- optimization history
- changelog
- publish/re-publish buttons
- rollback options

### 25.3 Skill Authoring Screen

Allow user to:

- create skill
- edit skill
- generate skill from trajectory
- generate validation test
- run quality gate
- save draft
- publish

### 25.4 SkillOpt Candidate Review Screen

Show:

- base version
- candidate version
- diff
- test result comparison
- trajectory evidence
- accept/reject buttons
- publish accepted version button

### 25.5 OpenClaw College Publishing Status

Show:

- provider connection status
- last publish result
- published URL
- version status
- install verification status

---

## 26. Backend Data Model

Add or extend tables as needed.

### 26.1 Skills Table

```sql
CREATE TABLE skills (
  id TEXT PRIMARY KEY,
  skill_id TEXT NOT NULL,
  name TEXT NOT NULL,
  version TEXT NOT NULL,
  category TEXT,
  description TEXT,
  lifecycle_state TEXT,
  publication_status TEXT,
  installation_status TEXT,
  risk_tier TEXT,
  manifest_json TEXT,
  skill_markdown TEXT,
  created_at TEXT,
  updated_at TEXT,
  published_at TEXT,
  archived_at TEXT
);
```

### 26.2 Skill Tests Table

```sql
CREATE TABLE skill_tests (
  id TEXT PRIMARY KEY,
  skill_id TEXT NOT NULL,
  version TEXT NOT NULL,
  test_type TEXT,
  test_definition_json TEXT,
  last_result_json TEXT,
  last_run_at TEXT,
  created_at TEXT
);
```

### 26.3 Skill Metrics Table

```sql
CREATE TABLE skill_metrics (
  id TEXT PRIMARY KEY,
  skill_id TEXT NOT NULL,
  version TEXT NOT NULL,
  usage_count INTEGER DEFAULT 0,
  success_count INTEGER DEFAULT 0,
  failure_count INTEGER DEFAULT 0,
  average_verification_score REAL,
  user_acceptance_rate REAL,
  average_retry_count REAL,
  last_used_at TEXT,
  last_optimized_at TEXT,
  metrics_json TEXT
);
```

### 26.4 Skill Trajectories Link Table

```sql
CREATE TABLE skill_trajectory_links (
  id TEXT PRIMARY KEY,
  skill_id TEXT NOT NULL,
  version TEXT NOT NULL,
  trajectory_id TEXT NOT NULL,
  task_id TEXT,
  outcome TEXT,
  verification_score REAL,
  created_at TEXT
);
```

### 26.5 Skill Publication Table

```sql
CREATE TABLE skill_publications (
  id TEXT PRIMARY KEY,
  skill_id TEXT NOT NULL,
  version TEXT NOT NULL,
  provider TEXT NOT NULL,
  published_url TEXT,
  publication_status TEXT,
  published_at TEXT,
  response_json TEXT
);
```

### 26.6 Skill Optimization Table

```sql
CREATE TABLE skill_optimizations (
  id TEXT PRIMARY KEY,
  base_skill_id TEXT NOT NULL,
  base_version TEXT NOT NULL,
  candidate_version TEXT NOT NULL,
  status TEXT,
  proposed_diff TEXT,
  validation_result_json TEXT,
  heldout_result_json TEXT,
  decision_reason TEXT,
  created_at TEXT,
  decided_at TEXT
);
```

---

## 27. Backend Services

Implement these services:

```text
SkillLifecycleService
SkillAuthoringService
SkillValidationService
SkillQualityGateService
SkillPackagingService
SkillPublishingService
OpenClawCollegeProvider
SkillInstallationVerifier
SkillMetricsService
SkillOptimizationReviewService
SkillRollbackService
SkillChangelogService
```

---

## 28. Backend API Endpoints

### 28.1 Skill Lifecycle

```http
GET /api/v1/skills
GET /api/v1/skills/{skill_id}
POST /api/v1/skills/create
POST /api/v1/skills/{skill_id}/update
POST /api/v1/skills/{skill_id}/archive
```

### 28.2 Validation

```http
POST /api/v1/skills/{skill_id}/validate
POST /api/v1/skills/{skill_id}/quality-gate
GET /api/v1/skills/{skill_id}/validation-results
```

### 28.3 Publishing

```http
POST /api/v1/skills/{skill_id}/package
POST /api/v1/skills/{skill_id}/publish
POST /api/v1/skills/{skill_id}/republish
GET /api/v1/skills/{skill_id}/publication-status
```

### 28.4 Installation Verification

```http
POST /api/v1/skills/{skill_id}/install-from-openclaw
POST /api/v1/skills/{skill_id}/verify-installation
```

### 28.5 Metrics and Trajectories

```http
GET /api/v1/skills/{skill_id}/metrics
GET /api/v1/skills/{skill_id}/trajectories
POST /api/v1/skills/{skill_id}/link-trajectory
```

### 28.6 SkillOpt Review

```http
GET /api/v1/skills/{skill_id}/optimization-candidates
GET /api/v1/skills/{skill_id}/optimization-candidates/{candidate_id}
POST /api/v1/skills/{skill_id}/optimization-candidates/{candidate_id}/accept
POST /api/v1/skills/{skill_id}/optimization-candidates/{candidate_id}/reject
POST /api/v1/skills/{skill_id}/optimization-candidates/{candidate_id}/publish
```

### 28.7 Rollback

```http
POST /api/v1/skills/{skill_id}/rollback
GET /api/v1/skills/{skill_id}/versions
```

---

## 29. Stack Orchestrator Integration

OpenClaw College Content Loop should be executable as an Agent Stack.

Create a built-in stack template:

# Skill Publishing Loop Stack

Steps:

```text
1. Identify skill opportunity
2. Generate skill draft
3. Generate validation tests
4. Run quality gate
5. Run validation tests
6. Package skill
7. Publish skill
8. Install skill from OpenClaw College
9. Run smoke test
10. Mark skill as active
11. Track first usage
12. Prepare summary
```

Create another stack template:

# Skill Optimization Loop Stack

Steps:

```text
1. Select underperforming or high-value skill
2. Gather usage trajectories
3. Run SkillOpt
4. Create candidate version
5. Run validation tests
6. Run held-out tests
7. Compare base vs candidate
8. Accept or reject candidate
9. Publish accepted version
10. Update local registry
11. Prepare optimization report
```

---

## 30. Self-Verification Integration

Each major skill loop action must verify itself.

### 30.1 Publication Verification

After publishing:

- confirm published URL exists or provider returned success
- confirm version metadata matches
- confirm skill package is retrievable

### 30.2 Installation Verification

After installing from OpenClaw College:

- confirm local manifest exists
- confirm skill.md exists
- confirm version matches published version
- run smoke test

### 30.3 Optimization Verification

After SkillOpt candidate creation:

- compare base vs candidate
- run validation tests
- run held-out tests
- confirm no safety regression

---

## 31. Audit Events

All actions must be logged through Shogun EventLogger.

Required events:

```text
skill.created
skill.updated
skill.validated
skill.validation_failed
skill.quality_gate_started
skill.quality_gate_passed
skill.quality_gate_failed
skill.packaged
skill.publish_requested
skill.published
skill.publish_failed
skill.installed_from_openclaw
skill.installation_verified
skill.installation_failed
skill.activated
skill.used
skill.trajectory_linked
skill.metrics_updated
skill.optimization_candidate_created
skill.optimization_candidate_tested
skill.optimization_candidate_accepted
skill.optimization_candidate_rejected
skill.republished
skill.rollback_requested
skill.rollback_completed
skill.deprecated
skill.archived
```

Do not create a separate logging system.

---

## 32. Permissions and Governance

Skill publishing should respect Shogun permissions.

### 32.1 Default Permissions

| Action | Default |
|---|---|
| Create local skill draft | Allowed |
| Run local validation | Allowed |
| Publish to OpenClaw College | Approval required |
| Install from OpenClaw College | Approval required unless trusted source enabled |
| Activate skill | Approval required |
| Run SkillOpt | Allowed if SkillOpt enabled |
| Republish optimized skill | Approval required |
| Deprecate skill | Approval required |
| Rollback skill | Approval required |

### 32.2 Posture Rules

| Posture | Behavior |
|---|---|
| Locked | No skill publishing loop |
| Guarded | Local draft/validation only |
| Supervised | Draft, validation, install with approval |
| Campaign | Full governed skill loop with approvals |
| Ronin | Full skill loop, broader automation if configured |

---

## 33. Configuration

Add configuration to `setup.json`.

Example:

```json
{
  "skills": {
    "openclaw_college_loop": {
      "enabled": true,
      "default_provider": "openclaw_college",
      "publish_requires_approval": true,
      "install_requires_approval": true,
      "activate_requires_approval": true,
      "republish_requires_approval": true,
      "quality_gate_required": true,
      "minimum_validation_score": 0.8,
      "allow_skillopt_candidates": true,
      "auto_accept_skillopt_candidates": false,
      "auto_republish": false,
      "retain_old_versions": true
    }
  }
}
```

---

## 34. Error Handling

### 34.1 Quality Gate Failure

If quality gate fails:

- mark skill as Draft
- show failed checks
- suggest fixes
- do not publish

### 34.2 Publish Failure

If publishing fails:

- preserve local package
- log provider error
- mark publication status as failed
- allow retry

### 34.3 Install Verification Failure

If installation verification fails:

- do not mark as installed
- preserve failure details
- suggest package repair

### 34.4 SkillOpt Candidate Failure

If optimized candidate fails validation:

- reject candidate by default
- preserve candidate for review
- do not republish

### 34.5 Regression Detected After Publication

If a published version later performs worse:

- mark version as degraded
- recommend rollback
- allow user to rollback to previous version

---

## 35. Recommended First Demo

Demo name:

```text
OpenClaw College Content Loop Demo
```

Demo objective:

```text
Create a new skill, validate it, publish it to OpenClaw College, install it back into Shogun, use it in a task, optimize it, and republish the improved version.
```

Demo skill:

```text
LinkedIn Comment Assistant
```

Demo flow:

```text
1. Shogun creates skill draft
2. Shogun creates validation tests
3. Shogun runs quality gate
4. User approves publication
5. Shogun publishes to OpenClaw College
6. Shogun installs the skill back from OpenClaw College
7. Shogun uses the skill on a LinkedIn reply task
8. Usage trajectory is captured
9. SkillOpt proposes improvement
10. Candidate version is validated
11. User approves re-publication
12. New version is published
13. Final lifecycle report is generated
```

Expected proof:

```text
Shogun can create, publish, install, use, optimize, and republish a skill through a governed lifecycle.
```

---

## 36. Acceptance Criteria

Order 15 is complete when:

1. Skill lifecycle states exist.
2. Skill package structure is supported.
3. Skill manifest schema is implemented.
4. Skill markdown format is supported.
5. Validation test format is supported.
6. Quality gate exists.
7. Skill authoring workflow exists.
8. Shogun can generate a skill draft from a task or trajectory.
9. Shogun can run local validation tests.
10. Shogun can package a validated skill.
11. OpenClaw College publishing adapter exists.
12. Shogun can publish a skill to OpenClaw College.
13. Shogun can receive and store publication metadata.
14. Shogun can install a skill from OpenClaw College.
15. Installation verification works.
16. Active skill usage links to published skill identity/version.
17. Skill metrics update after usage.
18. Skill trajectories link to skill versions.
19. SkillOpt can create candidate versions from real trajectories.
20. Candidate versions are tested before acceptance.
21. Accepted candidates are republished as new versions.
22. Old versions are retained.
23. Rollback to previous version works.
24. Katana UI shows lifecycle state, metrics, tests, publications, and candidates.
25. Skill Publishing Loop Stack template exists.
26. Skill Optimization Loop Stack template exists.
27. All actions are audited through EventLogger.
28. Publishing and activation respect posture/permission rules.
29. A complete demo can run end-to-end.
30. Existing skill installation and active usage features remain compatible.

---

## 37. Build Order

Implement in this order.

### Phase 1 — Skill Schema and Lifecycle

- skill manifest
- skill package structure
- lifecycle states
- local skill registry extensions

### Phase 2 — Validation and Quality Gate

- validation test parser
- validation runner
- quality gate checks
- validation result storage

### Phase 3 — Skill Authoring

- manual skill creation
- Shogun-generated skill draft
- generate skill from trajectory
- changelog generation

### Phase 4 — Publishing Adapter

- SkillPublishingProvider abstraction
- OpenClawCollegeProvider
- package upload
- publication metadata storage

### Phase 5 — Installation Verification

- install from OpenClaw College
- verify package
- run smoke test
- mark installed/active

### Phase 6 — Metrics and Trajectories

- skill usage metrics
- trajectory links
- performance dashboard data

### Phase 7 — SkillOpt Loop

- create candidate version
- compare base/candidate
- held-out validation
- accept/reject candidate

### Phase 8 — Re-Publishing and Rollback

- publish accepted candidate
- version management
- rollback previous version
- deprecation/archive states

### Phase 9 — Katana UI

- lifecycle overview
- skill detail view
- authoring screen
- publishing status
- SkillOpt candidate review
- rollback controls

### Phase 10 — Stack Templates and Demo

- Skill Publishing Loop Stack
- Skill Optimization Loop Stack
- end-to-end demo
- acceptance test suite

---

## 38. Critical Constraints for Coding Agent

The coding agent must follow these constraints:

1. Do not publish unvalidated skills.
2. Do not overwrite existing skill versions.
3. Do not allow SkillOpt to modify live skills directly.
4. Do not accept optimized candidates without validation.
5. Do not republish without approval unless explicitly configured.
6. Do not bypass Shogun EventLogger.
7. Do not bypass Shogun posture permissions.
8. Do not allow skills to declare hidden tool access.
9. Do not allow skills to bypass approval gates.
10. Do not store skill metrics without version linkage.
11. Do not lose trajectory links during optimization.
12. Do not auto-activate newly published skills without configured approval.
13. Do not remove old versions unless explicitly archived.
14. Preserve compatibility with existing installed skill system.
15. Use `setup.json` for configuration, not a separate config format.

---

## 39. Final Design Sentence

Order 15 should be built around this sentence:

> **OpenClaw College Content Loop turns Shogun skills into managed, testable, publishable, installable, measurable, optimizable, and versioned assets.**

That is the missing layer between skill creation and real self-improving agent capability.

---

## 40. Completion Definition

Order 15 is finished when Shogun can complete this loop:

```text
Create skill
  → validate skill
  → publish to OpenClaw College
  → install skill back into Shogun
  → actively use skill
  → capture trajectory
  → optimize through SkillOpt
  → validate candidate
  → republish improved version
  → retain rollback history
```

That is the full OpenClaw College Content Loop.

---
