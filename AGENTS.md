# AGENTS.md

## Purpose

This file defines the general engineering standards that all coding agents must follow when working in this repository.

The objective is to produce code that is:

* Correct
* Maintainable
* Understandable
* Secure
* Testable
* Consistent with the existing architecture
* Easy for future developers and coding agents to extend

These rules apply unless a more specific instruction in the repository explicitly overrides them.

---

# 1. General Engineering Principles

Follow established software engineering principles, including:

* SOLID
* DRY — Don't Repeat Yourself
* KISS — Keep It Simple
* YAGNI — You Aren't Gonna Need It
* Separation of Concerns
* Composition over unnecessary inheritance
* Explicit behavior over hidden behavior
* Maintainability over cleverness

Do not over-engineer solutions.

Prefer the simplest solution that correctly solves the problem and fits the existing architecture.

---

# 2. Respect the Existing Codebase

Before implementing changes:

1. Inspect the relevant existing code.
2. Understand the existing architecture and conventions.
3. Identify reusable components, functions, services, utilities, and patterns.
4. Prefer extending existing systems rather than creating parallel implementations.

Do not redesign working systems unless the task explicitly requires architectural changes.

Do not refactor unrelated code simply because another implementation appears cleaner.

Keep changes scoped to the requested task.

---

# 3. Preserve Existing Functionality

Existing working functionality must be preserved unless explicitly instructed otherwise.

Do not:

* Remove features without explicit authorization.
* Change public APIs unnecessarily.
* Rename externally used interfaces without considering compatibility.
* Change configuration structures without considering existing users.
* Modify database structures without considering migrations.
* Introduce breaking changes without clearly identifying them.

When modifying existing functionality, consider downstream dependencies and regression risk.

---

# 4. Modularity

Code should be organized into focused modules with clear responsibilities.

Avoid:

* Very large files.
* God classes.
* God services.
* Functions with many unrelated responsibilities.
* Business logic embedded directly into presentation layers.
* Circular dependencies.
* Unnecessary coupling between subsystems.

If a module becomes difficult to understand because it contains multiple responsibilities, consider separating it.

Do not split code merely to create more files. Modularity must improve clarity.

---

# 5. Reuse Before Creation

Before creating a new:

* Component
* Utility
* Function
* Service
* API
* Data model
* Configuration mechanism
* Abstraction

check whether an equivalent or sufficiently similar implementation already exists.

Reuse or extend existing functionality where practical.

Avoid duplicate implementations of the same business logic.

---

# 6. Abstractions

Create abstractions when they solve a real architectural or reuse problem.

Do not create abstractions solely because they might become useful later.

Avoid premature abstraction.

Prefer concrete, understandable implementations until abstraction provides measurable value.

---

# 7. Functions and Methods

Functions should:

* Have a clear responsibility.
* Have descriptive names.
* Be reasonably small.
* Minimize side effects.
* Have predictable behavior.
* Validate inputs where appropriate.
* Return consistent data structures.

Avoid deeply nested control flow when simpler alternatives exist.

Prefer early returns where they improve readability.

---

# 8. Naming

Names must clearly communicate intent.

Avoid vague names such as:

* data
* temp
* stuff
* thing
* manager
* helper
* misc

unless the context makes their meaning unambiguous.

Prefer descriptive names reflecting business or technical responsibility.

Use terminology consistently throughout the codebase.

---

# 9. Error Handling

Errors must never disappear silently.

Do not:

* Swallow exceptions without reason.
* Catch generic exceptions unnecessarily.
* Return success when an operation failed.
* Hide important failures only in debug logs.

Errors should be:

* Detected appropriately.
* Logged when operationally relevant.
* Returned or propagated at the correct abstraction level.
* Presented to users safely when required.

Avoid exposing sensitive implementation details to end users.

---

# 10. Logging

Use structured and meaningful logging.

Logs should help diagnose:

* Failures
* State transitions
* External integrations
* Important system actions
* Unexpected behavior

Do not log:

* Passwords
* API keys
* Authentication tokens
* Secrets
* Sensitive personal information
* Entire payloads containing confidential data unless specifically required and protected

Avoid excessive logging that creates noise.

---

# 11. Security

Treat security as a default engineering requirement.

Never:

* Hardcode credentials.
* Commit secrets.
* Disable authentication to solve implementation problems.
* Weaken authorization checks without explicit instruction.
* Trust user-controlled input without validation.
* Construct unsafe queries from raw input.
* Expose internal system information unnecessarily.

Follow least-privilege principles.

Validate data crossing trust boundaries.

---

# 12. Dependencies

Prefer existing dependencies when they adequately solve the problem.

Do not introduce new libraries without a clear reason.

Before adding a dependency, consider:

* Maintenance status
* Security
* Licensing
* Package size
* Complexity
* Existing alternatives already present in the project

Avoid adding large frameworks to solve small problems.

---

# 13. Configuration

Do not hardcode environment-specific values.

Use appropriate configuration mechanisms for:

* URLs
* Ports
* Paths
* Credentials
* Feature flags
* Model names
* Service endpoints
* Environment differences

Provide sensible defaults where appropriate.

Configuration should fail clearly when required values are missing.

---

# 14. Data and Persistence

Changes involving persistent data must consider backward compatibility.

Do not casually modify:

* Database schemas
* Stored JSON structures
* Persistent configuration
* Cache formats
* Saved application state

Schema changes should use appropriate migration mechanisms where applicable.

Never destroy user data unless explicitly required.

---

# 15. APIs and Interfaces

Interfaces should be:

* Explicit
* Stable
* Predictable
* Documented where necessary

Avoid changing API contracts unnecessarily.

Use consistent:

* Request structures
* Response structures
* Error formats
* Naming conventions
* Status semantics

Validate inputs at system boundaries.

---

# 16. Frontend and User Experience

When modifying user-facing functionality:

* Preserve established design patterns.
* Reuse existing UI components.
* Maintain accessibility.
* Handle loading, empty, success, and error states.
* Avoid unnecessary interface complexity.
* Do not change unrelated UI elements.

User-facing errors should be understandable and actionable.

---

# 17. Backend and Business Logic

Business rules should live in appropriate domain or service layers rather than being scattered throughout transport, UI, or persistence code.

Keep boundaries clear between:

* Presentation
* Application logic
* Business logic
* Persistence
* External integrations

Avoid embedding important business logic directly inside API endpoints, controllers, handlers, or UI components when a dedicated service/domain layer is more appropriate.

---

# 18. External Integrations

External services should be treated as unreliable dependencies.

Handle:

* Timeouts
* Invalid responses
* Authentication failures
* Rate limits
* Temporary outages
* Partial failures

Do not assume external services always return valid data.

Where appropriate, isolate external integrations behind adapters or service boundaries.

---

# 19. Concurrency and Background Work

When working with:

* Threads
* Async operations
* Queues
* Workers
* Background jobs
* Parallel agents

consider:

* Race conditions
* Duplicate execution
* Idempotency
* Locking
* Retry behavior
* Failure recovery
* Cancellation
* Resource cleanup

Do not introduce concurrency unless it provides a clear benefit.

---

# 20. Testing

Changes should be validated at the appropriate level.

Where practical, add or update tests for:

* New business logic
* Bug fixes
* Critical workflows
* Edge cases
* Security-sensitive behavior

Prefer tests that validate observable behavior rather than implementation details.

Do not modify tests merely to make incorrect code pass.

---

# 21. Bug Fixes

When fixing a bug:

1. Identify the underlying cause.
2. Avoid merely hiding the symptom.
3. Check whether the same issue exists elsewhere.
4. Preserve unrelated behavior.
5. Add regression coverage where practical.

Do not use broad workarounds when a targeted fix is available.

---

# 22. Refactoring

Refactoring should improve the codebase without changing intended behavior.

Avoid large unsolicited refactors.

Separate substantial architectural refactoring from functional feature work whenever practical.

If a significant refactor is necessary to complete the task, explain why.

---

# 23. Performance

Do not prematurely optimize.

However, avoid obviously inefficient implementations such as:

* Repeated expensive operations inside loops.
* Unnecessary network calls.
* Excessive database queries.
* Loading large datasets when only small subsets are required.
* Repeated parsing or serialization.
* Blocking operations in asynchronous execution paths.

Optimize when there is a meaningful reason.

---

# 24. Comments and Documentation

Code should primarily explain itself through good structure and naming.

Comments should explain:

* Why something exists.
* Non-obvious architectural decisions.
* Important constraints.
* Workarounds.
* Security considerations.
* Complex algorithms.

Avoid comments that simply restate the code.

Update documentation when behavior, architecture, configuration, or operating procedures materially change.

---

# 25. Avoid Unnecessary Scope Expansion

Implement the requested task.

Do not independently:

* Add unrelated features.
* Redesign unrelated interfaces.
* Replace existing technologies.
* Introduce new architectural layers.
* Rename large parts of the codebase.
* Perform cosmetic rewrites across unrelated files.

If another issue is discovered during implementation, mention it separately rather than automatically expanding scope.

---

# 26. Inspect Before Editing

Never assume how a system works based only on filenames or conventional architecture.

Inspect the relevant implementation first.

Trace important code paths when necessary.

Understand dependencies before modifying shared functionality.

---

# 27. Definition of Done

Before considering a task complete:

1. Confirm the requested functionality is implemented.
2. Check relevant existing functionality for regressions.
3. Run applicable tests.
4. Run available linting, type checking, or validation tools where appropriate.
5. Check for obvious security issues.
6. Confirm no secrets or debugging artifacts were introduced.
7. Review the final diff for unnecessary changes.
8. Ensure documentation is updated when required.

---

# 28. Communicating Changes

When completing a development task, provide a concise summary of:

* What changed.
* Why it changed.
* Important files affected.
* Tests or validation performed.
* Any known limitations.
* Any migrations, configuration changes, or manual steps required.

Do not claim that something was tested unless it was actually tested.

---

# 29. Decision Priority

When engineering principles conflict, prioritize approximately in this order:

1. Correctness
2. Security
3. Data integrity
4. Existing functionality
5. Maintainability
6. Simplicity
7. Consistency
8. Performance
9. Elegance

Use engineering judgment rather than applying rules mechanically.

---

# 30. Core Rule

Make the smallest clean change that correctly solves the problem while leaving the codebase better — or at minimum no worse — than before.
