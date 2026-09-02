---
name: agentflow-operator
description: Canonical operating guide for inspecting, creating, editing, activating, deactivating, running, and troubleshooting Yellow Label AgentFlows, including schedules, Telegram delivery, browser work, coding, and document templates.
---

# AgentFlow Operator

Treat this guide as authoritative for Yellow Label AgentFlows. Use native workflow tools and their returned IDs; never invent objects, node types, configurations, or results.

## Truth and execution contract

- Call `list_agent_flows` before working on stored flows.
- Call `get_agent_flow` before editing, deleting, or changing lifecycle state.
- Never claim that a flow was found, created, edited, activated, paused, run, or deleted unless the matching tool returned success in this turn.
- Prefer `patch_agent_flow` for targeted graph changes. Use full replacement only when intentionally replacing the entire graph.
- After every mutation, inspect the flow again and verify its name, nodes, configuration, edges, trigger, and status.
- If native tools report zero visible flows while the UI shows flows, stop. The channels may use different databases or instances; do not create a replacement in the wrong database.

## Lifecycle

- `draft`: saved but not scheduled or autonomously active.
- `active`: enabled; scheduled flows are registered with the scheduler.
- `paused`: disabled without deleting the graph.
- Create and edit as draft unless activation was requested.
- Activation is not execution. A manual run is a separate operation.

## Graph rules

1. Give every node a unique ID and every edge valid source and target node IDs.
2. Start flows with one `input` node.
3. Connect parallel work directly from the input and connect every result to a compiler or aggregator node.
4. Use `channel_send` for Telegram delivery. An `output` node creates a result or artifact; it does not deliver to Telegram.
5. Keep secrets out of node configuration. Use configured channels, providers, vault references, and workspace boundaries.
6. Keep flows acyclic. Yellow Label does not support child-flow or stack-orchestrator nodes.
7. Validate before activation. Test manually and inspect the actual run result.
8. For an exact document template, connect `file_template` upstream of the generating `samurai`, then connect that Samurai to an `office` create action.

## Supported node reference

### `input`

Starts the flow. Supported input types are `manual`, `document`, `api`, `scheduled`, and `event`.

- Manual input uses `manual_input` and optional `description`.
- Document input can use a UI upload, a verified workspace-relative path, or a server-verified attachment file ID.
- Scheduled input uses structured frequency, time, day, and minute-offset fields; do not place a raw cron expression in node configuration.

### `samurai`

Delegates a bounded task to an LLM worker and consumes predecessor context. Set `task_description`; optionally set expected output, agent, routing profile, timeout, retry, failure action, and context injection.

### `coding`

Performs a governed IDE operation. Supported actions include analysis, file listing/search/read, patch application, and allowlisted tasks. IDE actions require an approved workspace and remain subject to posture, ToolGate, protected-file, and command restrictions.

### `shogun_approval`

Applies a workflow quality or policy gate. A manual workflow gate is not the same as a live ToolGate confirmation card.

### `logic`

Evaluates an explicit condition and chooses the true or false branch. Test both paths.

### `output`

Formats and stores the predecessor result as an artifact, export, API result, notification, or memory entry. Add `channel_send` when Telegram delivery is required.

### `mado_browser`

Performs a governed browser operation such as navigation, extraction, screenshot, form fill, click, script execution, or wait. Respect configured domains, posture, and browser permissions.

### `email_send`

Sends mail through the configured provider. Use `{{context}}` in templates and treat sending as an external side effect.

### `channel_send`

Sends predecessor output to Telegram.

- Set `channel` to `telegram`.
- Optionally provide `telegram_chat_ids` and a numeric `message_thread_id`.
- Use `{{context}}` in `message_template`, or omit the template to send predecessor context directly.
- Treat delivery as verified only when the run result confirms it.

### `workspace`

Operates within the configured workspace using read, write, list, directory creation, delete, or copy actions. Never target a path outside the workspace.

### `file_template`

Provides a Word or Excel structure to a Samurai and a downstream Office create action.

- `template_path` must be workspace-relative and use `.docx` or `.xlsx`.
- Prefer `structure_only`; `one_shot` can expose bounded example content to the chosen model provider.
- Rendering must write a new output file and never overwrite the source template.

### `office`

Creates or transforms supported Office documents. Use the action matching the document type, keep operations within configured folders, and connect exactly one compatible upstream template for template-driven creation.

## Reliable patterns

### Scheduled Telegram brief

```text
scheduled input
  -> parallel mado_browser source nodes
  -> compiler samurai
  -> channel_send (Telegram)
```

Test manually before activation. Add an `output` branch when an archived result is also required.

### Safe edit

1. Locate the exact flow.
2. Inspect its full graph.
3. Patch only the requested nodes or edges.
4. Inspect again.
5. Preserve lifecycle status unless the operator requested a change.

## Failure handling

- Report the exact returned status and message.
- Do not retry the same denied or invalid mutation repeatedly.
- Distinguish ToolGate denial, posture denial, permission denial, database mismatch, validation failure, and delivery failure.
- Do not delete a working flow merely because a new configuration is required.

## Completion checklist

- Confirm the intended flow ID and name.
- Confirm every node type is supported by Yellow Label.
- Confirm every edge endpoint exists.
- Confirm Telegram delivery uses `channel_send`.
- Confirm schedule fields use the structured schedule model.
- Confirm template output does not overwrite its source.
- Confirm lifecycle status and scheduler synchronization.
- Confirm final inspection reflects the requested change.
