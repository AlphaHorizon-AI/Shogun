---
name: agentflow-operator
description: Canonical operating guide for inspecting, creating, editing, activating, deactivating, running, and troubleshooting Shogun AgentFlows and Flow Stacks. Use for every request involving AgentFlow nodes, graphs, schedules, Telegram or Teams delivery, reusable subflows, stack orchestration, or workflow lifecycle changes.
---

# AgentFlow Operator

Treat this guide as authoritative. Read it before designing or changing any AgentFlow or Flow Stack. Use native workflow tools and their returned IDs; never invent objects, node types, configurations, or results.

## Truth and execution contract

- Call `list_agent_flows` before working on stored flows. An empty successful query is not a ToolGate block; read its diagnostic.
- Call `get_agent_flow` or `get_flow_stack` before editing, deleting, or changing lifecycle state.
- Never claim that a flow was found, created, edited, activated, paused, run, or deleted unless the matching tool returned success in this turn.
- Prefer `patch_agent_flow` for targeted graph changes. Use full replacement only when intentionally replacing the entire graph.
- After every mutation, inspect the object again and verify names, node types, configuration, edges, trigger, and status.
- Do not tell a Telegram or Teams operator to approve a ToolGate card in Dojo. Channel chats cannot operate Dojo confirmation cards. Report the exact permission or posture requirement instead.
- If `list_agent_flows` reports zero visible flows while the UI shows flows, stop. The channels use different databases or instances. A UUID cannot bypass that mismatch, and creating a replacement would write to the wrong database.

## Lifecycle

- `draft`: saved but not scheduled or autonomously active.
- `active`: enabled. Scheduled flows are registered with the scheduler.
- `paused`: disabled without deleting the graph.
- Create and edit as draft unless activation was requested or Campaign/Ronin autonomy is intentionally being used.
- Use `set_agent_flow_status` with the exact flow ID to activate or pause an existing flow.
- Campaign and Ronin posture may activate or pause AgentFlows autonomously. Lower postures still require the persistent activation permission or one-time approval.
- Activation is not execution. `active` enables scheduling; a manual run is a separate operation.

## Graph construction rules

1. Give every node a unique ID and every edge valid source and target node IDs.
2. Start normal flows with one `input` node.
3. Connect parallel work directly from the input. Connect every parallel result into the compiler/aggregator node.
4. Use a `channel_send` node for Telegram or Teams. An `output` node creates a result/artifact; it does not deliver to Telegram or Teams.
5. Keep secrets out of node configuration. Use configured channels, providers, vault references, and workspace boundaries.
6. Keep flows acyclic. Use `logic` handles for branches and `subflow` for reusable child flows.
7. Validate before activation. Test manually, inspect run details, and verify the actual downstream delivery.

## Node reference

### `input`

Start the flow and produce its initial context.

- `input_type`: `manual`, `document`, `api`, `scheduled`, `event`, or `nexus`.
- Manual: set `manual_input` and optional `description`.
- Document: use the UI-managed `uploaded_file`; never invent a local path.
- Scheduled: use `schedule_frequency` (`hourly`, `nightly`, `weekly`, `monthly`), `schedule_time`, `schedule_minute_offset`, `schedule_days`, or `schedule_day` as applicable. Do not place a raw cron expression in node config.
- API/event/Nexus: set the relevant configured tool, event source/filter, or workspace/message type.

### `samurai`

Delegate a bounded task to an LLM worker and consume all predecessor context.

- Required: `task_description`.
- Useful: `expected_output`, `agent_id`, `routing_profile_id`, `timeout`, `retry_count`, `failure_action`, `context_injection`.
- Use one compiler Samurai after parallel research nodes. Specify a strict output format and ask it to deduplicate sources.

### `shogun_approval`

Apply a workflow quality/policy gate.

- `approval_mode`: `manual`, `ai_assisted`, `policy_based`, or `confidence_threshold`.
- `confidence_threshold` and `escalation_action` refine the decision.
- Current `manual` mode is not a live Dojo confirmation prompt; it records an auto-approved marker. Never confuse this node with ToolGate confirmation.

### `logic`

Evaluate `condition_expression` against predecessor output and choose a branch.

- The normal source handle is the true branch.
- The `false` source handle is the false branch.
- Make conditions explicit and test both paths.

### `output`

Format the final predecessor result and save it as a workspace artifact/result.

- `output_type`: `artifact`, `export`, `api`, `notification`, or `memory`.
- `format`: `markdown`, `json`, `html`, or `plain`.
- Optional `memory_infusion` stores verified output in memory with type, decay, importance, fields, tags, limits, and deduplication.
- This node does not send Telegram or Teams messages. Add `channel_send` for delivery.

### `mado_browser`

Perform one governed browser operation.

- `action`: `navigate`, `extract_content`, `screenshot`, `fill_form`, `click`, `execute_js`, or `wait_for`.
- Configure `url`, `extract_hint` or `selector`, `session_name`, `browser_mode`, `extract_type`, `script`, and `timeout` as required by the action.
- Use `headless` unless visible interaction is genuinely needed. Respect posture, allowed domains, and browser permissions.
- For multiple sources, use one browser node per source in parallel, then aggregate downstream.

### `email_send`

Send an email through the configured mail provider.

- Configure `to_address`, optional `cc_address`/`bcc_address`, `subject`, and `body_template`.
- Use `{{context}}` in templates to insert predecessor output.
- Sending remains governed as an external side effect.

### `channel_send`

Send the predecessor output to Telegram, Microsoft Teams, or both.

- `channel`: `telegram`, `teams`, or `both`.
- `message_template`: use `{{context}}` where compiled content belongs; omit it to send predecessor context directly.
- Telegram: optional `telegram_chat_ids` list and `message_thread_id` for a forum topic. Use the numeric topic thread ID, not a topic name.
- Teams: optional `teams_conversation_ids` list.
- If destination IDs are omitted, configured channel defaults are used.
- Treat delivery success as verified only when the tool/run result confirms it.

Example Telegram node:

```json
{
  "id": "deliver-news",
  "node_type": "channel_send",
  "label": "Send to Telegram News",
  "config": {
    "channel": "telegram",
    "telegram_chat_ids": ["-1004426378095"],
    "message_thread_id": 22,
    "message_template": "{{context}}"
  }
}
```

### `workspace`

Operate inside the configured workspace boundary.

- `action`: `read_file`, `write_file`, `list_files`, `mkdir`, `delete`, or `copy`.
- Configure `path`, or `source_path` and `dest_path`; use `content_template` for writes.
- Never target paths outside the allowed workspace. Destructive actions remain governed.

### `office`

Create or transform supported Office documents through the configured Office adapter.

- Select the application/action in the UI and provide its required input/output paths and options.
- Keep operations within configured folders. Outlook sending remains separately governed.

### `subflow`

Run a reusable child AgentFlow inside the parent DAG.

- Required: `child_flow_id` referencing an existing flow with `allow_as_subflow=true`.
- `child_flow_version_mode`: `locked` or `latest`; prefer `locked` for reproducibility.
- Configure `timeout_seconds`, `on_failure`, `input_mapping`, and `output_mapping`.
- Mapping tokens use `{{path.to.value}}`. Avoid cycles and respect configured depth/run limits.

### `stack_orchestrator`

Supervise a long-running Agent Stack control process.

- `mode`: `selected_stack`, `template`, or `goal_driven`.
- Configure the selected stack/template, `objective`, `success_criteria`, `allowed_tools`, model routing, runtime/iteration/retry limits, checkpointing, verification, approval, artifact, and failure policies.
- Use this for governed long-horizon control, not as a substitute for ordinary DAG nodes.

## Reliable patterns

### Scheduled Telegram news brief

Build:

```text
scheduled input
  -> parallel mado_browser source nodes
  -> compiler samurai
  -> channel_send (Telegram + topic ID)
```

Optionally branch the compiler output to an `output` node as well when an archived Markdown report is wanted. Test the flow manually before activation, then activate it.

### Safe edit

1. List and locate the exact flow.
2. Inspect its complete graph.
3. Patch only requested nodes/edges.
4. Inspect again and compare.
5. Preserve status unless the operator requested a lifecycle change.

### Flow Stack

Create and test each child AgentFlow first. Mark children reusable, compose at least two child flows in order, lock versions unless the operator accepts latest-version drift, validate mappings, then test the parent execution tree.

## Failure handling

- Report exact tool status and message. Do not translate permission errors into invented database or ToolGate failures.
- Do not retry the same denied or invalid mutation repeatedly.
- A ToolGate denial, posture denial, persistent permission denial, database mismatch, validation error, and delivery failure are different conditions; name the one actually returned.
- Never instruct a Telegram/Teams user to look for a Dojo confirmation unless the channel supports that exact confirmation mechanism.
- Do not delete a working flow merely because a new configuration is needed; inspect and patch it.

## Completion checklist

- Confirm the intended flow ID and name.
- Confirm every node type exists in this reference.
- Confirm every edge endpoint exists.
- Confirm delivery uses `channel_send`, not `output`.
- Confirm schedule fields use the supported schedule model.
- Confirm lifecycle status and scheduler synchronization.
- Confirm the final inspection reflects the requested change.
