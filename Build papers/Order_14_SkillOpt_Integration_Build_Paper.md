# Build Paper — Order 14: SkillOpt Integration
## Shogun AFM — Trainable Agent Skills, Validation-Gated Optimization, and Governed Skill Promotion

---

## 1. Executive Summary

This build paper defines **Order 14: SkillOpt Integration** for Shogun AFM.

The objective is to turn Shogun skills from static instruction files into **trainable, versioned, validation-gated skill artifacts**. Shogun should learn from real task trajectories, propose small edits to skill files, validate those edits against held-out tasks, and promote only the versions that demonstrably improve performance.

The integration must not modify model weights. It must optimize the **external skill document** used by Shogun agents.

The principle is:

> **Shogun should not merely collect skills. Shogun should train, test, version, govern, and improve them.**

This should be built only after the following foundations exist:

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

Those features provide the raw material SkillOpt needs: **real trajectories, scored outcomes, task state, verification results, and repeatable evaluation tasks**.

---

## 2. Background

SkillOpt-style optimization treats a compact natural-language skill document as a trainable external state for a frozen LLM agent. The optimizer model reads task trajectories, reflects on what helped or failed, proposes bounded edits to the skill document, and accepts a candidate only if it improves validation performance.

For Shogun, this maps naturally to existing concepts:

| SkillOpt Concept | Shogun Equivalent |
|---|---|
| Skill document | Shogun `SKILL.md` / skill instruction artifact |
| Target model | The model executing Shogun tasks |
| Optimizer model | Model that proposes skill edits |
| Rollout / trajectory | Shogun EventLogger + Stack Trace + verification results |
| Held-out validation | Shogun skill evaluation task set |
| Accepted skill | New promoted skill version |
| Rejected edit | Stored rejected candidate with reason |
| Deployment artifact | Versioned Shogun skill package |

The goal is not ad hoc self-rewriting.

The goal is disciplined, validation-gated skill improvement.

---

## 3. Core Product Principle

Build around this sentence:

> **A Shogun skill is a governed, versioned, trainable operational artifact. It may be optimized from trajectories, but only validated improvements are promoted.**

That means:

- no silent skill overwrites
- no unvalidated production updates
- no uncontrolled self-modification
- no model-weight training
- no bypassing governance
- no accepting edits merely because they “sound better”
- no promoting skills without evaluation evidence

---

## 4. Feature Name

Recommended product/UI name:

# SkillOpt Integration

Recommended Shogun module wording:

# Kaizen Skill Optimization

Recommended internal service names:

```text
SkillOptService
SkillOptimizerService
SkillEvaluationService
SkillPromotionService
SkillTrajectoryService
```

Recommended user-facing language:

> **Kaizen Skill Optimization helps Shogun improve its installed skills by learning from real executions, proposing controlled edits, validating them, and promoting only better-performing skill versions.**

---

## 5. Strategic Purpose

SkillOpt Integration strengthens Shogun in four ways.

### 5.1 Smaller Models Become More Capable

If Shogun can improve skill documents over time, smaller or cheaper models may perform better inside Shogun than they would as standalone agents.

This supports Shogun’s broader thesis:

> **The harness matters. Skills, memory, tools, verification, and orchestration can raise the effective capability of the model.**

### 5.2 Shogun Becomes Self-Improving in a Governed Way

Kaizen should not only mean passive reflection.

It should become an active improvement loop:

```text
Execute task
Capture trajectory
Score outcome
Reflect on failures
Propose skill edits
Validate candidate
Promote if better
Reject if not better
```

### 5.3 OpenClaw College Becomes a Real Skill Supply Chain

Shogun can create, install, use, optimize, and republish improved skills.

This creates a loop:

```text
OpenClaw College skill
  → installed in Shogun
  → used in real work
  → optimized by SkillOpt
  → validated
  → republished as improved skill version
```

### 5.4 Enterprise Trust Improves

Skills become inspectable, versioned, auditable, testable, and rollbackable.

That matters for enterprise use.

---

## 6. Scope

The SkillOpt Integration must include:

1. Skill versioning
2. Skill usage tracking
3. Trajectory capture
4. Skill evaluation task sets
5. Optimizer model integration
6. Bounded skill edit generation
7. Candidate skill validation
8. Held-out evaluation gate
9. Skill promotion workflow
10. Rejected edit archive
11. Rollback to prior skill version
12. UI for skill diffs and evaluation results
13. Integration with Agent Stacks and Stack Orchestrator
14. Integration with Model Routing Profiles
15. Integration with OpenClaw College publishing/export later

---

## 7. Non-Goals

Do not build the following in this phase:

- model fine-tuning
- reinforcement learning on model weights
- unrestricted autonomous skill rewriting
- auto-publishing to OpenClaw College without approval
- optimization of every skill simultaneously
- uncontrolled recursive self-improvement
- optimization based only on subjective LLM preference
- replacing Shogun’s existing skill system
- replacing existing EventLogger / audit trail
- production deployment of unvalidated skill candidates

---

## 8. Required Precondition

SkillOpt must not run meaningfully until **Active Skill Usage** and **Trajectory Capture** are implemented.

SkillOpt needs real evidence.

Minimum required trajectory fields:

- task ID
- stack run ID, if applicable
- agent ID
- model used
- skill used
- skill version used
- input context summary
- actions taken
- tools called
- errors encountered
- self-verification result
- final task score
- human intervention count
- runtime
- token usage / cost, if available
- final artifact references

Without this, the optimizer has no reliable feedback signal.

---

## 9. High-Level Architecture

```text
Shogun Runtime
  ↓
Active Skill Usage
  ↓
Trajectory Capture / EventLogger
  ↓
Skill Trajectory Store
  ↓
SkillOpt Service
  ├── Skill Selection
  ├── Training Batch Builder
  ├── Reflection Generator
  ├── Candidate Edit Generator
  ├── Static Skill Validator
  ├── Held-Out Evaluation Runner
  ├── Promotion Gate
  └── Rejected Edit Buffer
  ↓
Skill Registry / Version Store
  ↓
Approved Skill Deployment
```

The optimizer must be a controlled service, not a free-running agent.

---

## 10. Core Components

### 10.1 Skill Registry

The Skill Registry stores all installed skills and their versions.

It must know:

- skill ID
- skill name
- current active version
- available versions
- provenance
- trust level
- allowed tools
- compatible task types
- validation status
- performance history
- rollback options

---

### 10.2 Skill Version Store

Each skill version must be immutable after creation.

A new optimization creates a new version.

Do not overwrite the old version.

Example:

```text
skills/
  browser_research/
    v1/SKILL.md
    v2/SKILL.md
    v3/SKILL.md
    metadata.json
```

---

### 10.3 Skill Trajectory Store

Stores real usage trajectories where the skill was active.

Sources:

- Agent Stack runs
- IDE Mode coding runs
- Mado browser tasks
- Ronin desktop actions
- Productivity App Mode tasks
- Telegram/Max daily interactions
- ALE tasks

---

### 10.4 Optimizer Model

The optimizer model proposes edits.

It can be different from the target model.

Example:

```text
Target model: Gemma 3 12B
Optimizer model: GLM 5.2 / Claude Opus / other stronger model
```

The target model is the model whose performance the skill should improve.

The optimizer model is the model used to edit the skill.

The optimizer model must not directly promote changes. It only proposes candidate edits.

---

### 10.5 Candidate Edit Generator

Generates bounded edits to `SKILL.md`.

Allowed edit types:

- add instruction
- delete instruction
- replace instruction
- reorder section
- add checklist
- add failure recovery rule
- add tool-use convention
- add verification convention
- clarify ambiguous instruction

Disallowed edit types:

- add hidden prompt-injection text
- remove safety constraints
- grant new tool permissions
- instruct the agent to bypass Shogun permissions
- instruct the agent to ignore user approval rules
- add external exfiltration behavior
- add unbounded autonomy

---

### 10.6 Static Skill Validator

Before runtime validation, candidate skills must pass static checks.

Checks:

- valid markdown
- valid frontmatter
- no forbidden instruction patterns
- no permission escalation
- no removal of required safety sections
- no tool scope expansion without approval
- no external URL injection unless allowed
- no secret/credential handling instruction unless explicitly part of the skill

---

### 10.7 Held-Out Evaluation Runner

Runs baseline skill and candidate skill against held-out tasks.

The candidate is accepted only if it improves objective metrics.

The evaluation should support:

- deterministic task set
- repeated runs, if feasible
- same model profile
- same posture
- same tool permissions
- same input artifacts
- same success criteria

---

### 10.8 Promotion Gate

Promotion Gate decides whether the candidate becomes the new active skill version.

The gate must require:

- static validation passed
- held-out score improved
- no safety regression
- no excessive cost increase unless approved
- no reliability regression
- no increase in permission violations
- no degradation on critical tasks

Candidate edits must be rejected if they only improve training trajectories but fail validation.

---

### 10.9 Rejected Edit Buffer

Rejected edits must be stored.

Purpose:

- avoid repeating failed edits
- help optimizer learn what does not work
- support auditability
- support manual review

Rejected edit record should include:

- candidate version
- diff
- reason rejected
- failed metrics
- validation results
- timestamp
- optimizer model used

---

### 10.10 Skill Promotion Workflow

Promotion may be automatic or manual depending on settings.

Recommended default:

```text
Campaign posture: promotion requires approval
Ronin posture: auto-promotion may be allowed if configured
Enterprise mode: promotion always requires approval
```

---

## 11. Skill Document Format

Each skill should be stored as `SKILL.md` with frontmatter.

Example:

```md
---
skill_id: browser_research
name: Browser Research
description: Helps Shogun perform reliable browser-based research tasks.
version: 3
status: active
trust_level: verified
allowed_tools:
  - mado.browser.search
  - mado.browser.open
  - mado.browser.extract
compatible_postures:
  - supervised
  - campaign
  - ronin
optimized_by: skillopt
source_version: 2
validation_score: 0.86
created_at: 2026-07-17T10:00:00Z
---

# Browser Research Skill

## Purpose
...

## When To Use
...

## Procedure
...

## Tool Use Rules
...

## Verification Rules
...

## Failure Recovery
...

## Safety Constraints
...
```

Required sections:

- Purpose
- When To Use
- Procedure
- Tool Use Rules
- Verification Rules
- Failure Recovery
- Safety Constraints

The optimizer may edit operational sections, but it must not remove Safety Constraints.

---

## 12. Skill Optimization Lifecycle

### 12.1 Step 1 — Select Skill

Skill can be selected by:

- user/admin
- low performance signal
- frequent failures
- high usage volume
- scheduled optimization cycle
- ALE benchmark result
- OpenClaw College improvement pipeline

Default: manual selection.

---

### 12.2 Step 2 — Collect Trajectories

Collect recent trajectories where the skill was used.

Filter by:

- skill ID
- skill version
- task type
- model profile
- posture
- success/failure
- date range
- environment

Recommended minimum:

```text
At least 10 usable trajectories before optimization.
```

For early testing, allow smaller sets.

---

### 12.3 Step 3 — Build Training and Validation Sets

Split tasks into:

- training trajectories
- validation tasks
- optional regression tasks

Important:

> Do not validate only on the same tasks used to propose the edit.

---

### 12.4 Step 4 — Generate Reflection

The optimizer model analyzes trajectories.

Reflection should identify:

- repeated failure patterns
- missing procedural instructions
- bad tool-use conventions
- weak verification behavior
- ambiguity in skill text
- overlong or irrelevant instructions
- missing recovery rules

---

### 12.5 Step 5 — Generate Candidate Edit

The optimizer proposes a bounded diff.

The output must be a patch, not a full uncontrolled rewrite.

Example:

```diff
+ Before submitting a browser research result, verify at least two independent sources when the task asks for current facts.
+ If a page fails to load, retry once, then search for the same source through another route instead of declaring failure immediately.
```

---

### 12.6 Step 6 — Static Validation

Run static safety checks.

Reject immediately if candidate violates safety constraints.

---

### 12.7 Step 7 — Held-Out Validation

Run baseline version and candidate version against validation tasks.

Compare:

- success rate
- verification pass rate
- average retries
- tool errors
- safety violations
- runtime
- token/cost usage
- human interventions

---

### 12.8 Step 8 — Promotion Decision

Accept candidate only if it beats baseline under the configured gate.

Recommended default gate:

```text
Candidate must improve final score by at least 5 percentage points
OR improve success on at least 2 additional validation tasks
AND must not introduce safety regressions.
```

For small validation sets, require human approval.

---

### 12.9 Step 9 — Promote or Reject

If accepted:

- create new immutable skill version
- mark as candidate-promoted or active
- update Skill Registry
- log promotion event
- make rollback available

If rejected:

- store candidate in rejected buffer
- log reason
- keep active version unchanged

---

## 13. Scoring Model

Create a normalized score per evaluation run.

Suggested score components:

| Metric | Weight |
|---|---:|
| Task success | 40% |
| Self-verification passed | 20% |
| Safety compliance | 20% |
| Tool reliability | 10% |
| Efficiency / cost | 10% |

Default formula:

```text
final_score =
  0.40 * task_success
+ 0.20 * verification_score
+ 0.20 * safety_score
+ 0.10 * tool_reliability
+ 0.10 * efficiency_score
```

Safety violations should hard-fail promotion regardless of score.

---

## 14. Data Model

### 14.1 Skills

```sql
CREATE TABLE skills (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT,
  active_version_id TEXT,
  trust_level TEXT,
  source TEXT,
  created_at TEXT,
  updated_at TEXT,
  metadata_json TEXT
);
```

### 14.2 Skill Versions

```sql
CREATE TABLE skill_versions (
  id TEXT PRIMARY KEY,
  skill_id TEXT NOT NULL,
  version_number INTEGER NOT NULL,
  status TEXT NOT NULL,
  content_path TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  parent_version_id TEXT,
  created_by TEXT,
  created_at TEXT,
  validation_score REAL,
  metadata_json TEXT
);
```

### 14.3 Skill Usage Events

```sql
CREATE TABLE skill_usage_events (
  id TEXT PRIMARY KEY,
  skill_id TEXT NOT NULL,
  skill_version_id TEXT NOT NULL,
  run_id TEXT,
  stack_run_id TEXT,
  agent_id TEXT,
  model_used TEXT,
  posture TEXT,
  task_type TEXT,
  started_at TEXT,
  completed_at TEXT,
  outcome TEXT,
  score REAL,
  metadata_json TEXT
);
```

### 14.4 Skill Trajectories

```sql
CREATE TABLE skill_trajectories (
  id TEXT PRIMARY KEY,
  skill_usage_event_id TEXT NOT NULL,
  run_id TEXT,
  stack_run_id TEXT,
  trajectory_path TEXT,
  summary TEXT,
  verification_json TEXT,
  score REAL,
  created_at TEXT,
  metadata_json TEXT
);
```

### 14.5 SkillOpt Training Runs

```sql
CREATE TABLE skillopt_training_runs (
  id TEXT PRIMARY KEY,
  skill_id TEXT NOT NULL,
  base_version_id TEXT NOT NULL,
  status TEXT NOT NULL,
  optimizer_model TEXT,
  target_model_profile TEXT,
  started_at TEXT,
  completed_at TEXT,
  training_set_json TEXT,
  validation_set_json TEXT,
  result_json TEXT,
  metadata_json TEXT
);
```

### 14.6 SkillOpt Candidates

```sql
CREATE TABLE skillopt_candidates (
  id TEXT PRIMARY KEY,
  training_run_id TEXT NOT NULL,
  skill_id TEXT NOT NULL,
  base_version_id TEXT NOT NULL,
  candidate_content_path TEXT NOT NULL,
  candidate_diff_path TEXT NOT NULL,
  status TEXT NOT NULL,
  static_validation_status TEXT,
  validation_score REAL,
  rejection_reason TEXT,
  created_at TEXT,
  metadata_json TEXT
);
```

### 14.7 SkillOpt Evaluation Results

```sql
CREATE TABLE skillopt_eval_results (
  id TEXT PRIMARY KEY,
  candidate_id TEXT,
  skill_version_id TEXT,
  eval_task_id TEXT,
  model_used TEXT,
  posture TEXT,
  status TEXT,
  baseline_score REAL,
  candidate_score REAL,
  verification_status TEXT,
  safety_status TEXT,
  runtime_seconds REAL,
  cost_estimate REAL,
  created_at TEXT,
  metadata_json TEXT
);
```

---

## 15. Backend Services

Create or extend the following services:

```text
SkillRegistryService
SkillVersionService
SkillUsageTrackingService
SkillTrajectoryService
SkillOptService
SkillReflectionService
SkillCandidateEditService
SkillStaticValidationService
SkillEvaluationService
SkillPromotionService
SkillRollbackService
RejectedEditBufferService
```

---

## 16. API Endpoints

### 16.1 Skills

```http
GET /api/v1/skills
GET /api/v1/skills/{skill_id}
GET /api/v1/skills/{skill_id}/versions
GET /api/v1/skills/{skill_id}/performance
```

### 16.2 SkillOpt Runs

```http
POST /api/v1/skillopt/runs/create
POST /api/v1/skillopt/runs/{run_id}/start
POST /api/v1/skillopt/runs/{run_id}/pause
POST /api/v1/skillopt/runs/{run_id}/cancel
GET /api/v1/skillopt/runs/{run_id}
GET /api/v1/skillopt/runs/{run_id}/candidates
```

### 16.3 Candidates

```http
GET /api/v1/skillopt/candidates/{candidate_id}
GET /api/v1/skillopt/candidates/{candidate_id}/diff
POST /api/v1/skillopt/candidates/{candidate_id}/validate
POST /api/v1/skillopt/candidates/{candidate_id}/promote
POST /api/v1/skillopt/candidates/{candidate_id}/reject
```

### 16.4 Rollback

```http
POST /api/v1/skills/{skill_id}/rollback
```

---

## 17. Configuration in `setup.json`

Add:

```json
{
  "skillopt": {
    "enabled": false,
    "default_optimizer_model": "glm-5.2",
    "default_target_model_profile": "balanced",
    "minimum_trajectories": 10,
    "validation_split": 0.3,
    "max_candidate_edits": 5,
    "max_candidates_per_run": 3,
    "promotion_mode": "manual_approval",
    "minimum_score_improvement": 0.05,
    "block_on_safety_regression": true,
    "store_rejected_edits": true,
    "allow_auto_promotion_in_ronin": false,
    "require_human_approval_for_openclaw_publish": true
  }
}
```

Default should be disabled until configured.

---

## 18. UI Requirements

Add a SkillOpt area in Katana / Kaizen.

### 18.1 Skills Dashboard

Show:

- installed skills
- active version
- trust level
- usage count
- success rate
- recent failures
- optimization status
- last optimized date

### 18.2 Skill Detail View

Show:

- skill content
- version history
- performance by version
- tasks where used
- failure patterns
- allowed tools
- validation results
- rollback button

### 18.3 SkillOpt Run View

Show:

- selected skill
- base version
- optimizer model
- target model profile
- training trajectories
- validation tasks
- generated reflection
- candidate diffs
- static validation status
- evaluation results
- promotion decision

### 18.4 Candidate Diff View

Show before/after markdown.

Actions:

- approve promotion
- reject candidate
- rerun validation
- export diff
- rollback later

### 18.5 Rejected Edit Buffer View

Show rejected edits and reasons.

Purpose:

- transparency
- auditability
- future optimizer context

---

## 19. Integration With Agent Stacks

Agent Stacks are critical for SkillOpt.

Every stack step should record:

- skills loaded
- skill versions used
- why skill was selected
- whether skill was applied
- whether it helped
- verification result
- failure/retry information

The Stack Orchestrator should pass skill usage metadata into trajectory capture.

Example:

```json
{
  "stack_run_id": "stack_123",
  "step_id": "step_004",
  "skill_id": "vscode_debugging",
  "skill_version": 2,
  "model_used": "gemma-3-12b",
  "outcome": "failed_then_recovered",
  "verification_score": 0.78
}
```

---

## 20. Integration With Self-Verification

SkillOpt must rely on self-verification outcomes.

A trajectory without a verification signal is weak.

SkillOpt should prioritize trajectories that include:

- expected result
- observed result
- verification pass/fail
- retry history
- final score

For ALE-style tasks, the validation result should be converted into a skill performance signal.

---

## 21. Integration With Model Routing Profiles

SkillOpt must distinguish between:

1. **Target model** — the model being improved by the skill
2. **Optimizer model** — the model proposing edits
3. **Evaluator model** — optional model judging qualitative outputs

The target model should remain fixed during a validation comparison.

Do not compare baseline on one model and candidate on another model unless explicitly testing transfer.

---

## 22. Integration With OpenClaw College

OpenClaw College publishing should not be automatic in this phase.

Recommended workflow:

```text
Optimize skill locally
Validate improvement
Promote Shogun version
Mark candidate as publishable
Human reviews
Export as OpenClaw-compatible skill package
Publish manually or through later API
```

Future extension:

- publish improved skill
- include validation scorecard
- include provenance
- include compatible harnesses
- include required tools
- include safety rating

---

## 23. Security and Governance

### 23.1 Required Safety Rules

SkillOpt must never be allowed to:

- add instructions that bypass posture controls
- remove safety constraints
- grant itself new tools
- instruct agents to ignore approvals
- instruct agents to hide actions
- instruct agents to exfiltrate data
- instruct agents to access secrets unless skill purpose explicitly allows it
- auto-publish external content without approval

### 23.2 Skill Trust Levels

Recommended trust levels:

| Level | Meaning |
|---|---|
| untrusted | Imported but not validated |
| installed | Available but not optimized |
| validated | Passed Shogun validation tasks |
| optimized | Improved through SkillOpt and promoted |
| enterprise-approved | Human-approved for production use |

### 23.3 Promotion Approval

Default:

```text
Promotion requires human approval.
```

Optional Ronin setting:

```text
Auto-promote only if candidate clears all gates and no safety regression exists.
```

---

## 24. Audit Events

All SkillOpt activity must be logged through Shogun EventLogger.

Required events:

```text
skillopt.run.created
skillopt.run.started
skillopt.run.completed
skillopt.run.failed
skillopt.trajectory.selected
skillopt.reflection.generated
skillopt.candidate.generated
skillopt.candidate.static_validation_passed
skillopt.candidate.static_validation_failed
skillopt.validation.started
skillopt.validation.completed
skillopt.candidate.promoted
skillopt.candidate.rejected
skillopt.rollback.executed
skill.version.created
skill.version.activated
skill.version.deactivated
```

Do not create a separate audit system.

---

## 25. File Structure

Recommended backend structure:

```text
backend/
  app/
    skills/
      registry.py
      versioning.py
      usage_tracking.py
      trajectory_store.py
      validators.py
    skillopt/
      service.py
      reflection.py
      candidate_editor.py
      evaluation.py
      promotion.py
      rollback.py
      rejected_buffer.py
      schemas.py
      routes.py
```

Recommended storage:

```text
workspace/
  skills/
    {skill_id}/
      versions/
        v1/SKILL.md
        v2/SKILL.md
      candidates/
        {candidate_id}/SKILL.md
        {candidate_id}/diff.patch
      evaluations/
        {run_id}/results.json
      rejected/
        {candidate_id}/reason.json
```

---

## 26. Runtime Pseudocode

```python
class SkillOptService:
    async def optimize_skill(self, skill_id: str, config: SkillOptConfig):
        skill = await self.registry.get_skill(skill_id)
        base_version = await self.versions.get_active_version(skill_id)

        trajectories = await self.trajectories.select_for_skill(
            skill_id=skill_id,
            version_id=base_version.id,
            minimum=config.minimum_trajectories,
        )

        train_set, validation_set = self.dataset_builder.split(trajectories)

        reflection = await self.reflection.generate(
            skill=base_version,
            trajectories=train_set,
            optimizer_model=config.optimizer_model,
        )

        candidates = await self.editor.generate_candidates(
            base_skill=base_version,
            reflection=reflection,
            max_candidates=config.max_candidates_per_run,
            max_edits=config.max_candidate_edits,
        )

        best_candidate = None

        for candidate in candidates:
            static_result = await self.static_validator.validate(candidate)
            if not static_result.passed:
                await self.rejected.store(candidate, static_result.reason)
                continue

            eval_result = await self.evaluator.compare(
                baseline_skill=base_version,
                candidate_skill=candidate,
                validation_tasks=validation_set,
                target_model_profile=config.target_model_profile,
            )

            if self.promotion_gate.passes(eval_result):
                best_candidate = candidate
                break

            await self.rejected.store(candidate, eval_result.rejection_reason)

        if best_candidate:
            promoted_version = await self.promotion.promote(
                skill_id=skill_id,
                candidate=best_candidate,
                approval_required=config.promotion_mode == "manual_approval",
            )
            return promoted_version

        return None
```

---

## 27. Testing Requirements

### 27.1 Unit Tests

Test:

- skill version creation
- immutable versions
- trajectory selection
- training/validation split
- candidate patch application
- static validation
- promotion gate
- rejection storage
- rollback
- audit events

### 27.2 Integration Tests

Test:

- one skill optimized from mock trajectories
- candidate rejected for safety regression
- candidate rejected for worse score
- candidate promoted for better validation score
- rollback to previous skill version
- UI diff loads correctly
- EventLogger receives all events

### 27.3 End-to-End Demo Test

Use a small skill such as:

```text
vscode_debugging
```

Run:

1. execute 10 coding tasks using v1
2. capture failures and verification scores
3. run SkillOpt
4. generate v2 candidate
5. validate on held-out coding tasks
6. promote v2 if better
7. rerun selected tasks and compare

---

## 28. Acceptance Criteria

SkillOpt Integration is complete when:

1. Skills are versioned.
2. Skill usage is tracked by skill ID and version.
3. Skill trajectories are captured from real Shogun runs.
4. A SkillOpt run can be created from the UI/API.
5. Training and validation trajectories can be selected.
6. An optimizer model can generate a bounded candidate diff.
7. Candidate skills pass static validation before evaluation.
8. Candidate skills are evaluated against held-out tasks.
9. Candidate promotion requires improvement over baseline.
10. Safety regression blocks promotion.
11. Rejected edits are stored with reasons.
12. Promoted skills become new immutable versions.
13. Active skill version can be changed.
14. Rollback to previous version works.
15. UI shows skill versions, diffs, scores, and promotion status.
16. All SkillOpt events are logged through EventLogger.
17. Stack Orchestrator trajectories can feed SkillOpt.
18. SkillOpt does not bypass posture or tool permissions.
19. OpenClaw College publishing remains manual/approval-gated.
20. A demo skill can be improved and validated end-to-end.

---

## 29. Recommended First Demo

Demo name:

```text
Order 14 Demo — Optimize VS Code Debugging Skill
```

Goal:

```text
Improve the VS Code debugging skill using real failed coding trajectories from Shogun IDE Mode.
```

Flow:

```text
1. Run several coding tasks with vscode_debugging v1
2. Capture trajectories and verification outcomes
3. Start SkillOpt run
4. Optimizer proposes a small SKILL.md diff
5. Shogun validates candidate on held-out tasks
6. Candidate beats baseline
7. User approves promotion
8. v2 becomes active
9. Shogun reruns selected tasks with improved behavior
```

Expected proof:

```text
The improved skill reduces repeated debugging errors, improves verification pass rate, and gives Shogun a better coding procedure without changing the model.
```

---

## 30. Build Order

### Phase 1 — Skill Versioning Foundation

- immutable skill versions
- skill registry extension
- active version pointer
- rollback support

### Phase 2 — Skill Usage and Trajectory Capture

- record skill usage
- link skill usage to stack runs
- store trajectory summaries
- store verification scores

### Phase 3 — SkillOpt Run Service

- create/start/cancel SkillOpt runs
- select trajectories
- split train/validation sets
- store run state

### Phase 4 — Candidate Edit Generation

- reflection prompt
- bounded diff generation
- candidate artifact storage
- candidate diff view

### Phase 5 — Static Validation

- markdown validation
- frontmatter validation
- safety constraints
- forbidden instruction checks

### Phase 6 — Evaluation Runner

- run baseline vs candidate
- collect scores
- compare metrics
- store results

### Phase 7 — Promotion Gate

- improvement threshold
- safety regression check
- approval workflow
- promote/reject logic

### Phase 8 — UI

- skills dashboard
- skill detail view
- SkillOpt run view
- candidate diff view
- rejected edit buffer

### Phase 9 — Demo and Tests

- create demo skill
- run trajectories
- optimize
- validate
- promote
- rollback

---

## 31. Critical Constraints for Coding Agent

The coding agent must follow these constraints:

1. Do not modify model weights.
2. Do not overwrite active skills directly.
3. Always create a new skill version for candidate changes.
4. Do not promote candidates without validation.
5. Do not validate on the same trajectories used to generate the candidate unless explicitly marked as training-only.
6. Do not remove Safety Constraints from skill documents.
7. Do not allow skill edits to expand tool permissions automatically.
8. Do not allow skills to bypass Shogun posture controls.
9. Do not auto-publish to OpenClaw College.
10. Do not create a separate audit system.
11. Do not run SkillOpt without trajectory data.
12. Do not let optimizer model decide promotion alone.
13. Store rejected edits.
14. Preserve rollback.
15. Keep the target model fixed during baseline vs candidate validation.

---

## 32. References

- Microsoft Research: “SkillOpt: Agent skills as trainable parameters”
- Microsoft Research publication page: “SkillOpt: Executive Strategy for Self-Evolving Agent Skills”
- SkillOpt project page: “Executive Strategy for Self-Evolving Agent Skills”
- SkillOpt GitHub repository: `microsoft/SkillOpt`

---

## 33. Final Design Sentence

> **Order 14: SkillOpt Integration turns Shogun skills into trainable, versioned, validation-gated artifacts that improve from real trajectories while remaining governed, auditable, rollbackable, and safe.**

---
