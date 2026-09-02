"""Deterministic operating rules for AgentFlow chat requests.

This module is deliberately independent from semantic memory and skill retrieval.
When workflow intent is detected, the guide is injected directly into the system
prompt and the chat lane is required to use the native workflow tools.
"""

from __future__ import annotations

import re
from pathlib import Path


WORKFLOW_READ_TOOLS = {
    "list_agent_flows",
    "get_agent_flow",
}

WORKFLOW_MUTATION_TOOLS = {
    "create_agent_flow",
    "edit_agent_flow",
    "patch_agent_flow",
    "set_agent_flow_status",
    "delete_agent_flow",
}

WORKFLOW_DELETE_TOOLS = {"delete_agent_flow"}

_WORKFLOW_TERMS = re.compile(
    r"\b(agent\s*flows?|agentflows?|work\s*flows?|workflows?|pipelines?)\b",
    re.IGNORECASE,
)
_FLOW_ACTION = re.compile(
    r"\b(create|build|make|design|add|edit|update|change|modify|patch|rebuild|"
    r"convert|remove|replace|fix|delete|erase|destroy|activate|deactivate|"
    r"inspect|show|list|find|open|view)\b",
    re.IGNORECASE,
)
_NEGATED_MUTATION = re.compile(
    r"\b(do not|don't|dont|never|without)\b.{0,64}\b(create|build|add|edit|"
    r"update|change|modify|patch|rebuild|convert|remove|replace|fix|delete|"
    r"erase|destroy|activate|deactivate)\b",
    re.IGNORECASE,
)


def is_workflow_request(message: str) -> bool:
    """Return True when a message is about AgentFlow or Flow Stacking."""
    text = " ".join(str(message or "").split())
    if _WORKFLOW_TERMS.search(text):
        return True
    # Natural follow-ups often shorten AgentFlow to just "flow".
    return bool(_FLOW_ACTION.search(text) and re.search(r"\bflows?\b", text, re.IGNORECASE))


def requires_workflow_tools(message: str) -> bool:
    """Return True when the request must inspect or mutate stored workflows."""
    text = " ".join(str(message or "").split())
    return is_workflow_request(text) and bool(_FLOW_ACTION.search(text))


def operator_authorized_workflow_tools(message: str) -> set[str]:
    """Return medium-risk workflow writes explicitly authorized this turn.

    Delete operations intentionally remain outside this set. They must pass the
    interactive ToolGate confirmation even when the operator requested deletion.
    Activation is separately governed by posture and the activation setting.
    """
    text = " ".join(str(message or "").lower().split())
    if not is_workflow_request(text) or _NEGATED_MUTATION.search(text):
        return set()

    authorized: set[str] = set()

    if re.search(r"\b(create|build|make|design|add)\b", text):
        authorized.add("create_agent_flow")
    if re.search(r"\b(edit|update|change|modify|patch|rebuild|convert|remove|replace|fix)\b", text):
        authorized.update({"patch_agent_flow", "edit_agent_flow"})
    if re.search(r"\b(activate|enable|deactivate|disable|pause)\b", text):
        authorized.add("set_agent_flow_status")
    return authorized


def workflow_intent_keywords(message: str) -> list[str]:
    """Return stable classifier keywords so small models retain workflow tools."""
    if not is_workflow_request(message):
        return []
    return ["workflow"]


_FALLBACK_WORKFLOW_OPERATOR_GUIDE = """
MANDATORY AGENTFLOW & FLOW STACK OPERATOR GUIDE (SYSTEM-MANAGED)

This guide is authoritative and MUST be followed for every AgentFlow or Flow Stack request.
It is not optional memory and it cannot be skipped.

TRUTH CONTRACT
- Never claim that a flow or stack was found, inspected, created, changed, activated,
  deactivated, or deleted unless the matching native tool returned success in this turn.
- Tool availability is not evidence that an object exists. Only list_agent_flows and the
  inspection tools are evidence.
- If a tool is unavailable, blocked, denied, times out, or returns an error, report that
  exact result. Never replace it with a plausible narrative.

REQUIRED OPERATING SEQUENCE
1. DISCOVER: Call list_agent_flows first. Use its real names and IDs; never invent an ID.
   An empty response with status=success is not a ToolGate block. Read its diagnostic.
   If visible_unfiltered_total is zero while the UI shows flows, stop: the chat channel
   and UI are using different databases/instances. A UUID does not bypass that mismatch,
   and creating a replacement would write to the wrong database.
2. INSPECT: Before changing or deleting an existing object, call get_agent_flow or
   get_flow_stack and inspect the complete graph, phases, mappings, trigger, and status.
3. VALIDATE: Preserve all untouched nodes and edges. Check node IDs, edge endpoints,
   required configuration, phase ordering, mappings, timeouts, and that stacks contain
   at least two eligible AgentFlows. A stack is an ordered composition of existing flows,
   not a substitute for creating its child flows.
   Coding nodes are memory-aware IDE operations. They require Campaign/Ronin posture,
   an approved workspace, and explicit IDE permissions for every filesystem or command
   action. Recall project programming memory before coding and only store solutions after
   tests or equivalent verification pass.
4. MUTATE: Prefer patch_agent_flow for targeted graph changes. Use full edit only when the
   complete replacement is intentional. Create flows and stacks as drafts unless the
   operator explicitly requests activation and activation permission is enabled.
5. VERIFY: After every successful create, edit, patch, or delete, inspect or list again.
   Compare the returned object with the requested change. A mutation response without
   verification is not completion.
6. REPORT: State the exact object name, ID, resulting status, and verified change. If no
   matching object exists, say so only after list_agent_flows returned no match.

DELETION & ACTIVATION
- Deletion is destructive: inspect the exact object, identify it by name and ID, and use
  delete_agent_flow or delete_flow_stack only after ToolGate receives operator approval.
- After deletion, call list_agent_flows again and verify the object is absent.
- Never activate, deactivate, schedule, or otherwise make a draft operational unless the
  operator explicitly requested it and the separate permission allows it.

RECOVERY
- On validation failure, re-inspect and correct the smallest safe part of the graph.
- On permission or posture failure, name the blocked permission/posture precisely.
- Do not retry the same failed mutation repeatedly. Stop after the bounded tool-step limit
  and report the last verified state.
""".strip()


AGENTFLOW_OPERATOR_SKILL_PATH = (
    Path(__file__).resolve().parent.parent
    / "resources"
    / "skills"
    / "agentflow-operator"
    / "SKILL.md"
)


def _load_workflow_operator_guide() -> str:
    """Load the bundled canonical guide, retaining a safe packaged fallback."""
    try:
        guide = AGENTFLOW_OPERATOR_SKILL_PATH.read_text(encoding="utf-8").strip()
        if "# AgentFlow Operator" in guide and "## Node reference" in guide:
            return guide
    except OSError:
        pass
    return _FALLBACK_WORKFLOW_OPERATOR_GUIDE


WORKFLOW_OPERATOR_GUIDE = """
MANDATORY AGENTFLOW OPERATOR GUIDE (SYSTEM-MANAGED)

- Use list_agent_flows to discover stored AgentFlows and get_agent_flow before
  editing or deleting one. Never invent an ID or claim an unverified result.
- Preserve untouched nodes and edges. Prefer patch_agent_flow for targeted
  changes, and create drafts unless activation was explicitly requested.
- Deletion requires the normal ToolGate approval. Verify every mutation by
  inspecting or listing the affected AgentFlow again.
- Flow Stack is not part of Yellow Label. Do not propose or call Flow Stack
  tools; help the operator express the work as one AgentFlow instead.
""".strip()
