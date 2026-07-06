"""Flow Execution Engine — DAG-walking runtime for Agent Flow workflows.

Walks a flow's node graph in topological order, executing each node type:
- Input: provides initial context
- Samurai: delegates to LLM via agent's routing profile
- Shogun Approval: gate that checks approval policy
- Logic/Decision: evaluates condition to select branches
- Output: formats and stores final result

Supports parallel execution of independent sibling nodes.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from shogun.db.engine import async_session_factory
from shogun.db.models.agent import Agent
from shogun.db.models.agent_flow import AgentFlow, AgentFlowEdge, AgentFlowNode
from shogun.db.models.agent_flow_run import AgentFlowRun
from shogun.db.models.model_definition import ModelDefinition
from shogun.db.models.model_provider import ModelProvider
from shogun.db.models.model_routing import ModelRoutingProfile

log = logging.getLogger("shogun.flow_engine")

# ── Active runs registry (for cancellation) ─────────────────
_active_runs: dict[str, asyncio.Task] = {}


# ═══════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════


async def start_flow_run(
    flow_id: uuid.UUID,
    trigger_type: str = "manual",
) -> uuid.UUID:
    """Create a FlowRun record and launch execution as a background task.

    Returns the run ID immediately. Execution proceeds asynchronously.
    """
    run_id = uuid.uuid4()

    async with async_session_factory() as session:
        # Verify flow exists and is not deleted
        result = await session.execute(
            select(AgentFlow).where(
                AgentFlow.id == flow_id,
                AgentFlow.is_deleted == False,
            )
        )
        flow = result.scalar_one_or_none()
        if not flow:
            raise ValueError(f"Agent Flow {flow_id} not found or deleted")

        run = AgentFlowRun(
            id=run_id,
            flow_id=flow_id,
            status="pending",
            trigger_type=trigger_type,
            node_states={},
            result_summary={},
        )
        session.add(run)
        await session.commit()

    # Launch as background task
    task = asyncio.create_task(_execute_flow(run_id, flow_id))
    _active_runs[str(run_id)] = task

    # Auto-cleanup when done
    def _cleanup(t: asyncio.Task):
        _active_runs.pop(str(run_id), None)

    task.add_done_callback(_cleanup)

    log.info("Flow run %s started for flow %s (trigger=%s)", run_id, flow_id, trigger_type)
    return run_id


async def cancel_flow_run(run_id: uuid.UUID) -> bool:
    """Cancel a running flow execution."""
    task = _active_runs.get(str(run_id))
    if task and not task.done():
        task.cancel()
        # Update DB status
        async with async_session_factory() as session:
            result = await session.execute(
                select(AgentFlowRun).where(AgentFlowRun.id == run_id)
            )
            run = result.scalar_one_or_none()
            if run:
                run.status = "cancelled"
                run.completed_at = datetime.now(timezone.utc)
                run.error_message = "Cancelled by user"
                await session.commit()
        log.info("Flow run %s cancelled", run_id)
        return True
    return False


# ═══════════════════════════════════════════════════════════════
# CORE EXECUTION LOOP
# ═══════════════════════════════════════════════════════════════


async def _execute_flow(run_id: uuid.UUID, flow_id: uuid.UUID) -> None:
    """Main execution loop — loads flow, walks DAG, executes nodes."""
    try:
        async with async_session_factory() as session:
            # ── 1. Load flow with nodes and edges ──────────────────
            result = await session.execute(
                select(AgentFlow)
                .where(AgentFlow.id == flow_id)
                .options(
                    selectinload(AgentFlow.nodes),
                    selectinload(AgentFlow.edges),
                )
            )
            flow = result.scalar_one_or_none()
            if not flow:
                await _fail_run(run_id, "Flow not found")
                return

            nodes = list(flow.nodes)
            edges = list(flow.edges)

            if not nodes:
                await _fail_run(run_id, "Flow has no nodes")
                return

            # ── 2. Mark run as running ─────────────────────────────
            run_result = await session.execute(
                select(AgentFlowRun).where(AgentFlowRun.id == run_id)
            )
            run = run_result.scalar_one()
            run.status = "running"
            run.started_at = datetime.now(timezone.utc)

            # Initialize node states
            node_states: dict[str, dict[str, Any]] = {}
            for node in nodes:
                node_states[str(node.id)] = {
                    "status": "pending",
                    "output": None,
                    "error": None,
                    "started_at": None,
                    "completed_at": None,
                }
            run.node_states = node_states
            await session.commit()

        # ── 3. Topological sort ────────────────────────────────
        try:
            execution_layers = _topological_sort(nodes, edges)
        except ValueError as e:
            await _fail_run(run_id, str(e))
            return

        # ── 4. Build lookup maps ───────────────────────────────
        node_map: dict[str, AgentFlowNode] = {str(n.id): n for n in nodes}
        edge_list = edges

        # Build predecessor map: node_id → [source_node_ids]
        predecessors: dict[str, list[str]] = defaultdict(list)
        for edge in edge_list:
            predecessors[str(edge.target_node_id)].append(str(edge.source_node_id))

        # Build edge map for logic nodes: source_node_id → [(target_node_id, source_handle)]
        edge_by_source: dict[str, list[tuple[str, str | None]]] = defaultdict(list)
        for edge in edge_list:
            edge_by_source[str(edge.source_node_id)].append(
                (str(edge.target_node_id), edge.source_handle)
            )

        # ── 5. Walk layers ─────────────────────────────────────
        # node_outputs stores the output of each completed node
        node_outputs: dict[str, Any] = {}
        # skipped_nodes tracks nodes that should be skipped (logic branch pruning)
        skipped_nodes: set[str] = set()

        for layer in execution_layers:
            # Filter out skipped nodes
            active_nodes = [nid for nid in layer if nid not in skipped_nodes]

            if not active_nodes:
                continue

            # Execute all nodes in this layer in parallel
            tasks = []
            for node_id in active_nodes:
                node = node_map[node_id]
                # Gather predecessor outputs as context
                pred_outputs = {}
                for pred_id in predecessors.get(node_id, []):
                    if pred_id in node_outputs:
                        pred_outputs[pred_id] = node_outputs[pred_id]

                tasks.append(
                    _execute_single_node(
                        run_id=run_id,
                        node=node,
                        predecessor_outputs=pred_outputs,
                        node_map=node_map,
                    )
                )

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for node_id, result in zip(active_nodes, results):
                node = node_map[node_id]
                if isinstance(result, Exception):
                    node_outputs[node_id] = None
                    await _update_node_state(
                        run_id, node_id, "failed", error=str(result)
                    )
                    # Check failure action
                    config = node.config or {}
                    failure_action = config.get("failure_action", "stop")
                    if failure_action == "stop":
                        await _fail_run(
                            run_id,
                            f"Node '{node.label}' failed: {result}",
                            node_states_override=True,
                        )
                        return
                    elif failure_action == "skip":
                        # Mark downstream nodes as skipped
                        _mark_downstream_skipped(
                            node_id, edge_by_source, skipped_nodes
                        )
                    # "retry" and "escalate" fall through (retry handled inside _execute_single_node)
                else:
                    node_outputs[node_id] = result
                    await _update_node_state(
                        run_id, node_id, "completed", output=result
                    )

                    # ── Logic/Decision branch pruning ──────────
                    if node.node_type == "logic":
                        # result is True/False — prune the non-taken branch
                        taken_handle = None if result else "false"
                        for target_id, handle in edge_by_source.get(node_id, []):
                            if handle != taken_handle:
                                # This branch was NOT taken — skip all downstream
                                skipped_nodes.add(target_id)
                                _mark_downstream_skipped(
                                    target_id, edge_by_source, skipped_nodes
                                )
                            else:
                                # Ensure the taken branch is NOT skipped
                                skipped_nodes.discard(target_id)

        # ── 6. Mark skipped nodes ──────────────────────────────
        for nid in skipped_nodes:
            await _update_node_state(run_id, nid, "skipped")

        # ── 7. Build result summary ────────────────────────────
        # Collect output node results
        output_results = {}
        for node in nodes:
            if node.node_type == "output" and str(node.id) in node_outputs:
                output_results[node.label] = node_outputs[str(node.id)]

        await _complete_run(run_id, output_results or node_outputs)

    except asyncio.CancelledError:
        log.info("Flow run %s was cancelled", run_id)
        raise
    except Exception as exc:
        log.exception("Flow run %s failed with unexpected error", run_id)
        await _fail_run(run_id, f"Unexpected error: {str(exc)[:500]}")


# ═══════════════════════════════════════════════════════════════
# NODE EXECUTORS
# ═══════════════════════════════════════════════════════════════


async def _execute_single_node(
    run_id: uuid.UUID,
    node: AgentFlowNode,
    predecessor_outputs: dict[str, Any],
    node_map: dict[str, AgentFlowNode],
) -> Any:
    """Execute a single node and return its output."""
    node_id = str(node.id)
    await _update_node_state(run_id, node_id, "running")

    config = node.config or {}
    node_type = node.node_type

    # Build context string from predecessor outputs
    context_parts = []
    for pred_id, output in predecessor_outputs.items():
        pred_node = node_map.get(pred_id)
        pred_label = pred_node.label if pred_node else pred_id
        if output is not None:
            output_text = str(output)
            # Final output nodes must receive the complete predecessor result.
            # Other executable nodes retain a context guard for model calls.
            if node_type != "output":
                output_text = _truncate(output_text, 4000)
            context_parts.append(f"[Output from '{pred_label}']:\n{output_text}")
    context_str = "\n\n".join(context_parts) if context_parts else ""

    # Additional context injection from config
    if config.get("context_injection"):
        context_str += f"\n\n[Additional Context]:\n{config['context_injection']}"

    if node_type == "input":
        return await _exec_input(config, context_str)
    elif node_type == "samurai":
        return await _exec_samurai(config, context_str)
    elif node_type == "shogun_approval":
        return await _exec_approval(config, predecessor_outputs)
    elif node_type == "logic":
        return await _exec_logic(config, predecessor_outputs)
    elif node_type == "output":
        return await _exec_output(
            config,
            context_str,
            predecessor_outputs,
            run_id,
            node.label,
            node_id,
        )
    elif node_type == "mado_browser":
        return await _exec_mado_browser(config, context_str)
    elif node_type == "email_send":
        return await _exec_email_send(config, context_str)
    elif node_type == "channel_send":
        return await _exec_channel_send(config, context_str)
    elif node_type == "workspace":
        return await _exec_workspace(config, context_str)
    elif node_type == "office":
        return await _exec_office(config, context_str)
    else:
        raise ValueError(f"Unknown node type: {node_type}")


async def _exec_input(config: dict, context_str: str) -> str:
    """Input node — returns its configuration as initial context.

    Handles multiple input types:
    - manual: uses manual_input text or description
    - document: reads uploaded file content from disk
    - scheduled/api/event/nexus: uses description as context
    """
    from pathlib import Path
    import logging

    log = logging.getLogger("shogun.flow")
    description = config.get("description", "")
    input_type = config.get("input_type", "manual")

    output_parts = []

    # Always include description if present
    if description:
        output_parts.append(description)

    # Type-specific context
    if input_type == "manual":
        manual_input = config.get("manual_input", "")
        if manual_input:
            output_parts.append(manual_input)

    elif input_type == "document":
        uploaded = config.get("uploaded_file")
        if uploaded and uploaded.get("path"):
            file_path = Path(uploaded["path"])
            if file_path.exists():
                try:
                    content = file_path.read_text(encoding="utf-8", errors="replace")
                    output_parts.append(f"[Document: {uploaded.get('filename', 'unknown')}]\n{content}")
                    log.info("[Flow] Input: read document %s (%d chars)", uploaded["filename"], len(content))
                except Exception as exc:
                    output_parts.append(f"[ERROR reading document: {exc}]")
            else:
                output_parts.append(f"[Document not found: {uploaded.get('filename', 'unknown')}]")
        else:
            output_parts.append("[No document uploaded yet]")

    # Add any context from upstream nodes
    if context_str:
        output_parts.append(context_str)

    if not output_parts:
        output_parts.append(f"Workflow triggered ({input_type})")

    return "\n\n".join(output_parts)


async def _exec_samurai(config: dict, context_str: str) -> str:
    """Samurai node — delegates task to LLM using agent's routing profile."""
    task_description = config.get("task_description", "")
    expected_output = config.get("expected_output", "")
    agent_id = config.get("agent_id")
    routing_profile_id = config.get("routing_profile_id")
    timeout = config.get("timeout", 300)
    retry_count = config.get("retry_count", 0)

    if not task_description:
        raise ValueError("Samurai node has no task description")

    # Build the prompt
    user_message = task_description
    if context_str:
        user_message = f"{task_description}\n\n--- CONTEXT FROM PREVIOUS STEPS ---\n{context_str}"
    if expected_output:
        user_message += f"\n\n--- EXPECTED OUTPUT FORMAT ---\n{expected_output}"

    # Resolve agent persona
    agent_persona = "You are a Samurai agent executing a task in an automated workflow."
    async with async_session_factory() as session:
        if agent_id:
            agent_result = await session.execute(
                select(Agent).where(Agent.id == uuid.UUID(agent_id))
            )
            agent = agent_result.scalar_one_or_none()
            if agent:
                agent_persona = (
                    f"You are {agent.name}, a Samurai agent. "
                    f"{agent.description or ''}\n"
                    "You are executing a task as part of an automated Agent Flow workflow. "
                    "Respond with the requested output directly. Do not ask clarifying questions."
                )
                # Use agent's routing profile if not overridden
                if not routing_profile_id and agent.model_routing_profile_id:
                    routing_profile_id = str(agent.model_routing_profile_id)

        # Resolve the ordered primary + fallback chain.
        model_chain = await _resolve_llm_chain(
            session, routing_profile_id
        )

    if not model_chain:
        raise ValueError("No active LLM provider available for Samurai execution")

    messages = [
        {"role": "system", "content": agent_persona},
        {"role": "user", "content": user_message},
    ]

    return await _call_llm_chain(
        messages,
        model_chain,
        timeout=timeout,
        retry_count=retry_count,
        context="AgentFlow Samurai node",
    )


async def _exec_channel_send(config: dict, context_str: str) -> str:
    """Send an AgentFlow message to Telegram, Teams, or both."""
    from shogun.services.notification_service import send_channel_message

    channel = config.get("channel", "both")
    template = config.get("message_template") or "{{context}}"
    message = template.replace("{{context}}", context_str).strip()
    if not message:
        raise ValueError("Channel Send node produced an empty message")

    results = await send_channel_message(
        message,
        channel=channel,
        telegram_chat_ids=config.get("telegram_chat_ids") or None,
        teams_conversation_ids=config.get("teams_conversation_ids") or None,
    )
    selected = [channel] if channel != "both" else ["telegram", "teams"]
    failures = [name for name in selected if not results.get(name, {}).get("ok")]
    if failures:
        detail = "; ".join(
            f"{name}: {results.get(name, {}).get('error') or results.get(name, {}).get('errors')}"
            for name in failures
        )
        raise ValueError(f"Channel delivery failed ({detail})")
    return f"Message delivered via {', '.join(selected)}"


async def _exec_approval(
    config: dict, predecessor_outputs: dict[str, Any]
) -> str:
    """Shogun Approval node — gate that checks approval policy."""
    approval_mode = config.get("approval_mode", "manual")
    confidence_threshold = config.get("confidence_threshold", 85)

    # Aggregate predecessor output for review
    review_content = "\n\n".join(
        str(v) for v in predecessor_outputs.values() if v is not None
    )

    if approval_mode == "manual":
        # In Phase 2, manual approval auto-approves with a note
        # Full human-in-the-loop requires WebSocket (future phase)
        return f"[AUTO-APPROVED — manual approval mode]\n{review_content}"

    elif approval_mode == "ai_assisted":
        # Use LLM to evaluate if the output is acceptable
        async with async_session_factory() as session:
            model_chain = await _resolve_llm_chain(session)

        if model_chain:
            judge_messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a quality assurance judge reviewing the output of an AI agent. "
                        "Evaluate the following output and respond with APPROVED if it meets quality standards, "
                        "or REJECTED with a brief reason if it does not."
                    ),
                },
                {"role": "user", "content": f"Review this output:\n\n{review_content[:3000]}"},
            ]
            verdict = await _call_llm_chain(
                judge_messages,
                model_chain,
                timeout=60,
                retry_count=0,
                context="AgentFlow approval node",
            )
            if "REJECTED" in verdict.upper():
                raise ValueError(f"AI review rejected: {verdict[:500]}")
            return f"[AI-APPROVED]\n{review_content}"

        return f"[AUTO-APPROVED — no LLM available for AI review]\n{review_content}"

    elif approval_mode == "confidence_threshold":
        # Auto-approve — threshold is informational in Phase 2
        return f"[AUTO-APPROVED — confidence threshold {confidence_threshold}%]\n{review_content}"

    elif approval_mode == "policy_based":
        # Check Torii posture for agentflow_execute permission
        try:
            from shogun.services.posture_guard import get_posture_permissions
            perms = await get_posture_permissions()
            if not perms.get("agentflow_execute", False):
                raise ValueError(
                    "Policy-based approval denied: agentflow_execute not permitted at current tier"
                )
        except ImportError:
            pass
        return f"[POLICY-APPROVED]\n{review_content}"

    return f"[APPROVED]\n{review_content}"


async def _exec_logic(
    config: dict, predecessor_outputs: dict[str, Any]
) -> bool:
    """Logic/Decision node — evaluates condition and returns True (right) or False (bottom)."""
    condition = config.get("condition_expression", "")

    if not condition:
        # No condition — always take the TRUE branch
        return True

    # Build context for evaluation
    context = "\n\n".join(
        str(v) for v in predecessor_outputs.values() if v is not None
    )

    # Use LLM to evaluate the condition
    async with async_session_factory() as session:
        model_chain = await _resolve_llm_chain(session)

    if not model_chain:
        # No LLM — default to True
        log.warning("Logic node: no LLM available, defaulting to TRUE branch")
        return True

    eval_messages = [
        {
            "role": "system",
            "content": (
                "You are a logic evaluator. Given a condition and context, "
                "evaluate whether the condition is TRUE or FALSE. "
                "Respond with exactly one word: TRUE or FALSE."
            ),
        },
        {
            "role": "user",
            "content": f"Condition: {condition}\n\nContext:\n{context[:3000]}",
        },
    ]

    try:
        result = await _call_llm_chain(
            eval_messages,
            model_chain,
            timeout=30,
            retry_count=0,
            context="AgentFlow logic node",
        )
        return "TRUE" in result.upper()
    except Exception:
        log.warning("Logic node evaluation failed, defaulting to TRUE")
        return True


async def _exec_output(
    config: dict,
    context_str: str,
    predecessor_outputs: dict[str, Any],
    run_id: uuid.UUID | None = None,
    node_label: str = "output",
    node_id: str | None = None,
) -> str:
    """Output node — formats and returns the final result, saving it to workspace."""
    output_type = config.get("output_type", "artifact")
    fmt = config.get("format", "markdown")

    # Collect all predecessor outputs
    content = context_str or "\n\n".join(
        str(v) for v in predecessor_outputs.values() if v is not None
    )

    final_content = content
    if fmt == "json":
        import json
        try:
            # Try to parse as JSON, otherwise wrap as JSON
            result = json.loads(content)
            final_content = json.dumps(result, indent=2)
        except (json.JSONDecodeError, TypeError):
            final_content = json.dumps({
                "output_type": output_type,
                "content": content,
            }, indent=2)
    elif fmt == "plain":
        # Strip markdown formatting
        import re
        final_content = re.sub(r'[#*_`~\[\]]', '', content)

    # Never create a misleading zero-byte "successful" report. An empty
    # predecessor result is still a result that the user needs to understand.
    if not final_content or not str(final_content).strip():
        final_content = (
            "No output was produced by the preceding node. "
            "Open the run details to check that node's response and configuration."
        )

    # Save to workspace automatically
    if run_id:
        from shogun.config import settings
        from datetime import datetime
        import logging
        
        log = logging.getLogger("shogun.flow")
        workspace_dir = settings.workspace_path.resolve() / "output"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_ext = "md" if fmt == "markdown" else "json" if fmt == "json" else "html" if fmt == "html" else "txt"
        
        # Sanitize node label for filename
        import re
        safe_label = re.sub(r'[^a-zA-Z0-9_-]', '_', node_label).strip('_').lower()
        if not safe_label:
            safe_label = "output"
            
        short_run_id = str(run_id)[:8]
        filename = f"report_{safe_label}_{timestamp}_{short_run_id}.{file_ext}"
        
        try:
            target_path = workspace_dir / filename
            temporary_path = target_path.with_suffix(f"{target_path.suffix}.tmp")
            temporary_path.write_text(final_content, encoding="utf-8")
            temporary_path.replace(target_path)
            if node_id:
                artifact_path = str(
                    target_path.relative_to(settings.workspace_path.resolve())
                ).replace("\\", "/")
                await _record_node_artifact(run_id, node_id, artifact_path)
            log.info("Saved flow output report to workspace: %s", target_path)
        except Exception as e:
            log.error("Failed to save flow output report to workspace: %s", e)

    return final_content


async def _exec_mado_browser(config: dict, context_str: str) -> str:
    """Mado Browser node — executes browser automation actions.

    Supports: navigate, extract_content, screenshot, fill_form,
              click, execute_js, wait_for
    """
    from fastapi import HTTPException

    from shogun.services import mado_service
    from shogun.services.posture_guard import (
        check_mado_access,
        check_mado_browser_mode,
        check_mado_session_limit,
        get_posture_tool_filter,
    )

    action = config.get("action", "navigate")
    url = config.get("url", "")
    selector = config.get("selector")
    session_name = config.get("session_name", "flow_browser")
    browser_mode = config.get("browser_mode", "headless")

    # Use a deterministic session ID for the flow to allow session reuse
    flow_session_id = f"flow_{session_name}"

    # Enforce the same local Torii, Harakiri, Gensui, browser-mode, and
    # session-limit rules used by chat and the Mado API.
    try:
        await check_mado_access()
        posture = await get_posture_tool_filter()
        check_mado_browser_mode(browser_mode, posture)
        if flow_session_id not in mado_service._active_contexts:
            await check_mado_session_limit()
    except HTTPException as exc:
        return f"[BLOCKED] {exc.detail}"

    # Ensure browser is launched
    launch_result = await mado_service.launch_browser(
        session_id=flow_session_id,
        profile_name=f"flow_{session_name}",
        mode=browser_mode,
    )

    if launch_result.get("status") == "error":
        return f"[ERROR] Failed to launch browser: {launch_result.get('error', 'Unknown')}"

    try:
        if action == "navigate":
            # Use URL from config first; fall back to context string
            target_url = url or (context_str.strip().split("\n")[0] if context_str else "")
            if not target_url:
                return "[ERROR] No URL specified for navigation"

            log.info("[Mado/Flow] navigate → %s (session=%s)", target_url, flow_session_id)
            result = await mado_service.navigate(
                session_id=flow_session_id,
                url=target_url,
            )
            if result.get("status") == "error":
                log.error("[Mado/Flow] navigate FAILED: %s", result.get('error'))
                return f"[ERROR] Navigation failed: {result.get('error', 'Unknown')}"
            if result.get("status") == "blocked":
                return f"[BLOCKED] {result.get('reason', 'Domain not allowed')}"
            log.info("[Mado/Flow] navigate OK → %s", result.get('title', 'N/A'))
            return f"Navigated to: {result.get('url', target_url)}\nTitle: {result.get('title', 'N/A')}"

        elif action == "extract_content":
            extract_type = config.get("extract_type", "text")
            log.info("[Mado/Flow] extract '%s' (type=%s, session=%s)", selector, extract_type, flow_session_id)
            result = await mado_service.extract_content(
                session_id=flow_session_id,
                selector=selector,
                extract_type=extract_type,
            )
            content = result.get("content", "")
            status = result.get("status", "unknown")
            log.info("[Mado/Flow] extract result: status=%s, length=%d chars", status, len(content))
            if not content:
                return "[No content extracted — the page may not have matching elements]"
            return content

        elif action == "screenshot":
            full_page = config.get("full_page", False)
            result = await mado_service.screenshot(
                session_id=flow_session_id,
                full_page=full_page,
                selector=selector,
            )
            return f"Screenshot saved: {result.get('filename', 'unknown')}\nPath: {result.get('path', 'N/A')}"

        elif action == "fill_form":
            fields = config.get("fields", [])
            if not fields:
                return "[ERROR] No form fields specified"
            result = await mado_service.fill_form(
                session_id=flow_session_id,
                fields=fields,
            )
            return f"Filled {result.get('filled', 0)}/{result.get('total', 0)} fields"

        elif action == "click":
            if not selector:
                return "[ERROR] No selector specified for click"
            result = await mado_service.click_element(
                session_id=flow_session_id,
                selector=selector,
            )
            return f"Clicked: {selector}\nURL after click: {result.get('url', 'N/A')}"

        elif action == "execute_js":
            script = config.get("script", "")
            if not script:
                return "[ERROR] No JavaScript specified"
            result = await mado_service.execute_js(
                session_id=flow_session_id,
                script=script,
            )
            return f"JS result: {result.get('result', 'undefined')}"

        elif action == "wait_for":
            if not selector:
                return "[ERROR] No selector specified for wait"
            timeout = config.get("timeout", 10000)
            result = await mado_service.wait_for_selector(
                session_id=flow_session_id,
                selector=selector,
                timeout=timeout,
            )
            if result.get("status") == "timeout":
                return f"[TIMEOUT] Selector '{selector}' not found within {timeout}ms"
            return f"Element found: {selector}"

        else:
            return f"[ERROR] Unknown Mado action: {action}"

    except Exception as exc:
        return f"[ERROR] Browser action '{action}' failed: {str(exc)[:500]}"


async def _exec_email_send(config: dict, context_str: str) -> str:
    """Email Send node — sends an email via the configured SMTP account.

    Uses the existing EmailService infrastructure.  If no body_template is
    provided the full predecessor output is used as the email body.
    """
    from shogun.services.email_service import EmailService
    from shogun.schemas.channels import EmailComposeRequest

    to_address = config.get("to_address", "")
    if not to_address:
        raise ValueError("Email Send node has no recipient (to_address)")

    subject = config.get("subject", "Shogun Agent Flow — Email")
    body_template = config.get("body_template", "")
    cc_address = config.get("cc_address") or None
    bcc_address = config.get("bcc_address") or None

    # Build the email body
    if body_template:
        # Allow a simple {{context}} placeholder for predecessor output
        body = body_template.replace("{{context}}", context_str)
    else:
        # No template — use the raw predecessor output as the body
        body = context_str or "(No content from previous steps)"

    # Send via EmailService
    async with async_session_factory() as session:
        svc = EmailService(session)
        acc = await svc.get_account()
        if not acc:
            raise ValueError(
                "No email account configured. Set up an account in the Mail page first."
            )
        if not acc.perm_send_mail:
            raise ValueError(
                "Email sending permission is disabled. Enable perm_send_mail in the Mail settings."
            )

        compose = EmailComposeRequest(
            to_address=to_address,
            cc_address=cc_address,
            bcc_address=bcc_address,
            subject=subject,
            body=body,
        )
        result = await svc.send_email(compose)

    status = result.get("message", "Sent")
    log.info("Email sent to %s — %s", to_address, status)
    return f"Email sent to {to_address}\nSubject: {subject}\nStatus: {status}"


async def _exec_workspace(config: dict, context_str: str) -> str:
    """Workspace node — performs file operations inside the agent workspace.

    Actions: read_file, write_file, list_files, mkdir, delete, copy
    """
    from pathlib import Path
    import shutil
    from shogun.config import settings
    from shogun.services.posture_guard import get_posture_permissions

    action = config.get("action", "read_file")
    file_path = config.get("path", "").strip()
    content_template = config.get("content_template", "")

    # Check posture
    perms = await get_posture_permissions()
    if not perms.get("workspace_enabled", True):
        return "[BLOCKED] Workspace access is disabled at current security posture"

    root = settings.workspace_path.resolve()
    root.mkdir(parents=True, exist_ok=True)

    def _safe(rel: str) -> Path:
        """Resolve and validate a relative path within workspace."""
        if not rel:
            return root
        if ".." in rel:
            raise ValueError(f"Path traversal blocked: {rel}")
        target = (root / rel).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            raise ValueError(f"Path escape blocked: {rel}")
        return target

    try:
        if action == "read_file":
            if not file_path:
                return "[ERROR] No path specified for read_file"
            target = _safe(file_path)
            if not target.is_file():
                return f"[ERROR] File not found: {file_path}"
            try:
                content = target.read_text(encoding="utf-8", errors="replace")
            except UnicodeDecodeError:
                return f"[Binary file — {target.stat().st_size} bytes] Cannot read as text: {file_path}"
            log.info("[Flow/Workspace] read_file: %s (%d chars)", file_path, len(content))
            return content

        elif action == "write_file":
            if not file_path:
                return "[ERROR] No path specified for write_file"
            target = _safe(file_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            # Content: template with {{context}} or raw predecessor output
            if content_template:
                body = content_template.replace("{{context}}", context_str)
            else:
                body = context_str or ""
            target.write_text(body, encoding="utf-8")
            log.info("[Flow/Workspace] write_file: %s (%d chars)", file_path, len(body))
            return f"Written {len(body)} characters to: {file_path}"

        elif action == "list_files":
            target = _safe(file_path) if file_path else root
            if not target.is_dir():
                return f"[ERROR] Not a directory: {file_path}"
            entries = []
            for item in sorted(target.iterdir()):
                rel = str(item.relative_to(root)).replace("\\", "/")
                if item.is_dir():
                    entries.append(f"📁 {rel}/")
                else:
                    size = item.stat().st_size
                    entries.append(f"📄 {rel} ({size:,} bytes)")
            log.info("[Flow/Workspace] list_files: %s (%d entries)", file_path or ".", len(entries))
            return "\n".join(entries) if entries else "(empty directory)"

        elif action == "mkdir":
            if not file_path:
                return "[ERROR] No path specified for mkdir"
            target = _safe(file_path)
            target.mkdir(parents=True, exist_ok=True)
            log.info("[Flow/Workspace] mkdir: %s", file_path)
            return f"Directory created: {file_path}"

        elif action == "delete":
            if not file_path:
                return "[ERROR] No path specified for delete"
            target = _safe(file_path)
            if not target.exists():
                return f"[ERROR] Not found: {file_path}"
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
            log.info("[Flow/Workspace] delete: %s", file_path)
            return f"Deleted: {file_path}"

        elif action == "copy":
            source_path = config.get("source_path", "").strip()
            dest_path = config.get("dest_path", "").strip()
            if not source_path or not dest_path:
                return "[ERROR] Both source_path and dest_path are required for copy"
            src = _safe(source_path)
            dst = _safe(dest_path)
            if not src.exists():
                return f"[ERROR] Source not found: {source_path}"
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
            log.info("[Flow/Workspace] copy: %s → %s", source_path, dest_path)
            return f"Copied: {source_path} → {dest_path}"

        else:
            return f"[ERROR] Unknown workspace action: {action}"

    except Exception as exc:
        return f"[ERROR] Workspace '{action}' failed: {str(exc)[:500]}"


async def _exec_office(config: dict, context_str: str) -> str:
    """Office node — performs Office document operations using adapters.

    Actions: excel_read, excel_write, excel_create, word_read, word_replace,
             word_create, pptx_read, pptx_replace
    """
    from pathlib import Path
    from shogun.config import settings
    from shogun.office.config import load_office_config

    action = config.get("action", "word_read")
    input_path = config.get("input_path", "").strip()
    output_path = config.get("output_path", "").strip()
    sheet_name = config.get("sheet_name", "Sheet1")

    # Check office is enabled
    office_cfg = load_office_config()
    if not office_cfg.enabled:
        return "[BLOCKED] Office App Mode is disabled. Enable it in the Katana settings."

    root = settings.workspace_path.resolve()
    root.mkdir(parents=True, exist_ok=True)

    def _resolve(rel: str) -> str:
        """Resolve relative workspace path to absolute string."""
        if not rel:
            raise ValueError("Path is required")
        if ".." in rel:
            raise ValueError(f"Path traversal blocked: {rel}")
        target = (root / rel).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            raise ValueError(f"Path escape blocked: {rel}")
        return str(target)

    try:
        # ── Excel Operations ──
        if action == "excel_read":
            from shogun.office.adapters.excel_adapter import (
                open_workbook, read_used_range, list_sheets, close_workbook,
            )
            abs_path = _resolve(input_path)
            handle = open_workbook(abs_path)
            try:
                target_sheet = sheet_name or list_sheets(handle)[0]
                data = read_used_range(handle, target_sheet)
                # Format as CSV-like text
                lines = []
                for row in data:
                    lines.append("\t".join(str(c) if c is not None else "" for c in row))
                result = f"[Sheet: {target_sheet}] ({len(data)} rows)\n" + "\n".join(lines)
                log.info("[Flow/Office] excel_read: %s, sheet=%s, rows=%d", input_path, target_sheet, len(data))
                return result
            finally:
                close_workbook(handle)

        elif action == "excel_create":
            from shogun.office.adapters.excel_adapter import (
                open_workbook, write_range, save_as, close_workbook, create_sheet,
            )
            import openpyxl
            abs_out = _resolve(output_path)
            # Create new workbook
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = sheet_name or "Sheet1"
            # Parse context as tab-separated data
            lines = context_str.strip().split("\n") if context_str.strip() else []
            for r_idx, line in enumerate(lines, 1):
                cells = line.split("\t")
                for c_idx, val in enumerate(cells, 1):
                    ws.cell(row=r_idx, column=c_idx, value=val.strip())
            Path(abs_out).parent.mkdir(parents=True, exist_ok=True)
            wb.save(abs_out)
            wb.close()
            log.info("[Flow/Office] excel_create: %s (%d rows)", output_path, len(lines))
            return f"Excel workbook created: {output_path} ({len(lines)} rows)"

        elif action == "excel_write":
            from shogun.office.adapters.excel_adapter import (
                open_workbook, write_range, save_as, close_workbook,
            )
            abs_in = _resolve(input_path)
            abs_out = _resolve(output_path) if output_path else abs_in
            handle = open_workbook(abs_in)
            try:
                # Parse context as 2D data
                lines = context_str.strip().split("\n") if context_str.strip() else []
                data = []
                for line in lines:
                    data.append(line.split("\t"))
                if data:
                    target_sheet = sheet_name or handle.workbook.sheetnames[0]
                    write_range(handle, target_sheet, 1, 1, data)
                Path(abs_out).parent.mkdir(parents=True, exist_ok=True)
                save_as(handle, abs_out)
                log.info("[Flow/Office] excel_write: %s → %s (%d rows)", input_path, output_path or input_path, len(data))
                return f"Excel updated: {output_path or input_path} ({len(data)} rows written)"
            finally:
                close_workbook(handle)

        # ── Word Operations ──
        elif action == "word_read":
            from shogun.office.adapters.word_adapter import (
                open_document, read_text, close_document,
            )
            abs_path = _resolve(input_path)
            handle = open_document(abs_path)
            try:
                text = read_text(handle)
                log.info("[Flow/Office] word_read: %s (%d chars)", input_path, len(text))
                return text
            finally:
                close_document(handle)

        elif action == "word_create":
            from docx import Document
            abs_out = _resolve(output_path)
            doc = Document()
            # Use template or context as content
            content = config.get("content_template", "") or context_str or ""
            if config.get("content_template"):
                content = content.replace("{{context}}", context_str)
            for para in content.split("\n"):
                doc.add_paragraph(para)
            Path(abs_out).parent.mkdir(parents=True, exist_ok=True)
            doc.save(abs_out)
            log.info("[Flow/Office] word_create: %s", output_path)
            return f"Word document created: {output_path}"

        elif action == "word_replace":
            from shogun.office.adapters.word_adapter import (
                open_document, replace_placeholders, save_as, close_document,
            )
            abs_in = _resolve(input_path)
            abs_out = _resolve(output_path) if output_path else abs_in
            handle = open_document(abs_in)
            try:
                replacements = config.get("replacements", {})
                if not replacements:
                    return "[ERROR] No replacements specified for word_replace"
                count = replace_placeholders(handle, replacements)
                Path(abs_out).parent.mkdir(parents=True, exist_ok=True)
                save_as(handle, abs_out)
                log.info("[Flow/Office] word_replace: %s → %s (%d replacements)", input_path, output_path or input_path, count)
                return f"Word document updated: {output_path or input_path} ({count} replacements)"
            finally:
                close_document(handle)

        # ── PowerPoint Operations ──
        elif action == "pptx_read":
            from shogun.office.adapters.pptx_adapter import (
                open_presentation, list_slides, read_slide_text, close_presentation,
            )
            abs_path = _resolve(input_path)
            handle = open_presentation(abs_path)
            try:
                slides = list_slides(handle)
                texts = []
                for i, s in enumerate(slides):
                    text = read_slide_text(handle, i)
                    texts.append(f"[Slide {i+1}: {s.get('title', 'Untitled')}]\n{text}")
                result = "\n\n".join(texts)
                log.info("[Flow/Office] pptx_read: %s (%d slides)", input_path, len(slides))
                return result
            finally:
                close_presentation(handle)

        elif action == "pptx_replace":
            from shogun.office.adapters.pptx_adapter import (
                open_presentation, replace_placeholders, save_as, close_presentation,
            )
            abs_in = _resolve(input_path)
            abs_out = _resolve(output_path) if output_path else abs_in
            handle = open_presentation(abs_in)
            try:
                replacements = config.get("replacements", {})
                if not replacements:
                    return "[ERROR] No replacements specified for pptx_replace"
                count = replace_placeholders(handle, replacements)
                Path(abs_out).parent.mkdir(parents=True, exist_ok=True)
                save_as(handle, abs_out)
                log.info("[Flow/Office] pptx_replace: %s → %s", input_path, output_path or input_path)
                return f"Presentation updated: {output_path or input_path} ({count} replacements)"
            finally:
                close_presentation(handle)

        else:
            return f"[ERROR] Unknown office action: {action}"

    except ImportError as exc:
        return f"[ERROR] Missing dependency for '{action}': {exc}"
    except Exception as exc:
        return f"[ERROR] Office '{action}' failed: {str(exc)[:500]}"


# ═══════════════════════════════════════════════════════════════
# LLM RESOLUTION & CALLING
# ═══════════════════════════════════════════════════════════════


PROVIDER_URLS = {
    "ollama": "http://127.0.0.1:11434",
    "lmstudio": "http://localhost:1234/v1",
    "local": "http://localhost:1234/v1",
    "openai": "https://api.openai.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "google": "https://generativelanguage.googleapis.com/v1beta/openai",
    "custom": "https://api.openai.com/v1",
}


async def _resolve_llm(
    session: AsyncSession,
    routing_profile_id: str | None = None,
) -> tuple[ModelProvider | None, str, str, dict]:
    """Resolve the LLM provider, model name, base URL, and headers.

    Returns (provider, model_name, base_url, headers) or (None, "", "", {}).
    """
    chain = await _resolve_llm_chain(session, routing_profile_id)
    if not chain:
        return None, "", "", {}
    return chain[0]


def _provider_connection(
    provider: ModelProvider,
    model_name: str | None = None,
) -> tuple[ModelProvider, str, str, dict]:
    """Build an API target tuple for one provider/model."""
    resolved_model = (
        model_name
        or provider.config.get("model_id")
        or provider.config.get("model")
        or (provider.config.get("models") or [None])[0]
        or provider.name
    )
    # Resolve base URL
    base_url = provider.base_url or PROVIDER_URLS.get(
        provider.provider_type, "https://api.openai.com/v1"
    )
    if provider.provider_type == "ollama" and not base_url.rstrip("/").endswith("/v1"):
        base_url = base_url.rstrip("/") + "/v1"

    # Build headers
    api_key = provider.config.get("api_key") or provider.config.get("api-key")
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    if provider.provider_type == "openrouter":
        headers["HTTP-Referer"] = "https://shogun.ai"
        headers["X-Title"] = "Shogun AgentFlow"

    return provider, resolved_model, base_url, headers


async def _resolve_model_target(
    session: AsyncSession, target_id: str | uuid.UUID
) -> tuple[ModelProvider, str, str, dict] | None:
    """Resolve routing IDs that refer to either providers or model definitions."""
    try:
        parsed_id = target_id if isinstance(target_id, uuid.UUID) else uuid.UUID(str(target_id))
    except (TypeError, ValueError):
        return None

    provider = await session.scalar(
        select(ModelProvider).where(
            ModelProvider.id == parsed_id,
            ModelProvider.status == "connected",
        )
    )
    if provider:
        return _provider_connection(provider)

    definition = await session.scalar(select(ModelDefinition).where(ModelDefinition.id == parsed_id))
    if definition and definition.provider and definition.provider.status == "connected":
        return _provider_connection(definition.provider, definition.model_key)
    return None


async def _resolve_llm_chain(
    session: AsyncSession,
    routing_profile_id: str | None = None,
) -> list[tuple[ModelProvider, str, str, dict]]:
    """Resolve a primary model and every configured fallback in exact order."""
    profile: ModelRoutingProfile | None = None
    try:
        if routing_profile_id:
            profile = await session.scalar(
                select(ModelRoutingProfile).where(
                    ModelRoutingProfile.id == uuid.UUID(routing_profile_id)
                )
            )
        else:
            profile = await session.scalar(
                select(ModelRoutingProfile)
                .where(ModelRoutingProfile.is_default.is_(True))
                .order_by(ModelRoutingProfile.updated_at.desc())
                .limit(1)
            )
    except Exception as exc:
        log.warning("Failed to resolve routing profile %s: %s", routing_profile_id, exc)

    chain: list[tuple[ModelProvider, str, str, dict]] = []
    seen: set[tuple[str, str]] = set()
    if profile:
        rule = next((r for r in profile.rules if r.get("task_type") == "*"), None)
        if not rule and profile.rules:
            rule = profile.rules[0]
        if rule:
            target_ids = [rule.get("primary_model_id"), *(rule.get("fallback_model_ids") or [])]
            for target_id in target_ids:
                if not target_id:
                    continue
                target = await _resolve_model_target(session, target_id)
                if target:
                    key = (str(target[0].id), target[1])
                    if key not in seen:
                        seen.add(key)
                        chain.append(target)
                else:
                    log.warning("Configured routing target %s is unavailable; skipping it", target_id)

    if not chain:
        provider = await session.scalar(
            select(ModelProvider)
            .where(ModelProvider.status == "connected")
            .order_by(ModelProvider.created_at)
            .limit(1)
        )
        if provider:
            chain.append(_provider_connection(provider))
    return chain


async def _call_llm(
    messages: list[dict],
    model_name: str,
    base_url: str,
    headers: dict,
    timeout: int = 120,
) -> str:
    """Make a non-streaming chat completion call and return the response text."""
    url = f"{base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model_name,
        "messages": messages,
        "stream": False,
        "temperature": 0.3,  # Low temperature for task execution
    }

    async with httpx.AsyncClient(timeout=float(timeout)) as client:
        resp = await client.post(url, headers=headers, json=payload)

        if resp.status_code >= 400:
            body = resp.text[:500]
            raise ValueError(f"LLM API error {resp.status_code}: {body}")

        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            raise ValueError("LLM returned no choices")

        content = choices[0].get("message", {}).get("content", "")
        if not content:
            raise ValueError("LLM returned empty content")

        return content


async def _call_llm_chain(
    messages: list[dict],
    model_chain: list[tuple[ModelProvider, str, str, dict]],
    *,
    timeout: int,
    retry_count: int,
    context: str,
) -> str:
    """Call each model in order, transparently notifying on every transition."""
    last_error: Exception | None = None
    for model_index, (_provider, model_name, base_url, headers) in enumerate(model_chain):
        for attempt in range(1 + retry_count):
            try:
                return await _call_llm(messages, model_name, base_url, headers, timeout)
            except Exception as exc:
                last_error = exc
                log.warning(
                    "%s model '%s' failed (attempt %d/%d, timeout=%ss): %s",
                    context,
                    model_name,
                    attempt + 1,
                    1 + retry_count,
                    timeout,
                    exc,
                )
                if attempt < retry_count:
                    await asyncio.sleep(2 ** attempt)

        if model_index + 1 < len(model_chain):
            next_model = model_chain[model_index + 1][1]
            reason = (
                f"timeout after {timeout}s"
                if isinstance(last_error, (httpx.TimeoutException, asyncio.TimeoutError))
                else str(last_error)[:300]
            )
            from shogun.services.notification_service import notify_model_fallback

            await notify_model_fallback(
                from_model=model_name,
                to_model=next_model,
                reason=reason,
                context=context,
                timeout_seconds=timeout,
            )

    raise last_error or ValueError(f"{context} failed without a model response")


# ═══════════════════════════════════════════════════════════════
# GRAPH UTILITIES
# ═══════════════════════════════════════════════════════════════


def _topological_sort(
    nodes: list[AgentFlowNode],
    edges: list[AgentFlowEdge],
) -> list[list[str]]:
    """Sort nodes into execution layers (Kahn's algorithm).

    Returns a list of layers, where each layer contains node IDs that can
    be executed in parallel.

    Raises ValueError if the graph contains a cycle.
    """
    node_ids = {str(n.id) for n in nodes}

    # Build adjacency and in-degree
    in_degree: dict[str, int] = {nid: 0 for nid in node_ids}
    adjacency: dict[str, list[str]] = {nid: [] for nid in node_ids}

    for edge in edges:
        src = str(edge.source_node_id)
        tgt = str(edge.target_node_id)
        if src in node_ids and tgt in node_ids:
            adjacency[src].append(tgt)
            in_degree[tgt] += 1

    # Kahn's algorithm with layer tracking
    queue: deque[str] = deque()
    for nid, deg in in_degree.items():
        if deg == 0:
            queue.append(nid)

    layers: list[list[str]] = []
    visited = 0

    while queue:
        # All nodes currently in the queue form one parallel layer
        layer = list(queue)
        queue.clear()
        layers.append(layer)
        visited += len(layer)

        for nid in layer:
            for neighbor in adjacency[nid]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

    if visited != len(node_ids):
        raise ValueError(
            "Agent Flow contains a cycle — cannot execute. "
            "Remove circular dependencies and try again."
        )

    return layers


def _mark_downstream_skipped(
    node_id: str,
    edge_by_source: dict[str, list[tuple[str, str | None]]],
    skipped: set[str],
) -> None:
    """Recursively mark all downstream nodes as skipped."""
    for target_id, _ in edge_by_source.get(node_id, []):
        if target_id not in skipped:
            skipped.add(target_id)
            _mark_downstream_skipped(target_id, edge_by_source, skipped)


# ═══════════════════════════════════════════════════════════════
# STATE MANAGEMENT HELPERS
# ═══════════════════════════════════════════════════════════════


async def _record_node_artifact(
    run_id: uuid.UUID,
    node_id: str,
    artifact_path: str,
) -> None:
    """Associate a generated workspace artifact with its run node."""
    async with async_session_factory() as session:
        result = await session.execute(
            select(AgentFlowRun).where(AgentFlowRun.id == run_id)
        )
        run = result.scalar_one_or_none()
        if not run:
            return

        states = dict(run.node_states or {})
        node_state = dict(states.get(node_id, {}))
        node_state["artifact_path"] = artifact_path
        states[node_id] = node_state
        run.node_states = states
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(run, "node_states")
        await session.commit()


async def _update_node_state(
    run_id: uuid.UUID,
    node_id: str,
    status: str,
    output: Any = None,
    error: str | None = None,
) -> None:
    """Update a single node's execution state in the run record."""
    async with async_session_factory() as session:
        result = await session.execute(
            select(AgentFlowRun).where(AgentFlowRun.id == run_id)
        )
        run = result.scalar_one_or_none()
        if not run:
            return

        states = dict(run.node_states or {})
        now = datetime.now(timezone.utc).isoformat()

        node_state = states.get(node_id, {})
        node_state["status"] = status

        if status == "running":
            node_state["started_at"] = now
        elif status in ("completed", "failed", "skipped"):
            node_state["completed_at"] = now

        if output is not None:
            # Preserve the complete result so View Result and run history match
            # the generated artifact exactly.
            node_state["output"] = str(output)
        if error:
            node_state["error"] = error[:2000]

        states[node_id] = node_state
        run.node_states = states
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(run, "node_states")
        await session.commit()


async def _fail_run(
    run_id: uuid.UUID,
    error_message: str,
    node_states_override: bool = False,
) -> None:
    """Mark a run as failed."""
    async with async_session_factory() as session:
        result = await session.execute(
            select(AgentFlowRun).where(AgentFlowRun.id == run_id)
        )
        run = result.scalar_one_or_none()
        if not run:
            return

        run.status = "failed"
        run.completed_at = datetime.now(timezone.utc)
        run.error_message = error_message[:2000]
        await session.commit()

    log.error("Flow run %s FAILED: %s", run_id, error_message)


async def _complete_run(
    run_id: uuid.UUID,
    result_summary: dict[str, Any],
) -> None:
    """Mark a run as completed with results."""
    async with async_session_factory() as session:
        result = await session.execute(
            select(AgentFlowRun).where(AgentFlowRun.id == run_id)
        )
        run = result.scalar_one_or_none()
        if not run:
            return

        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)

        # Preserve final reports in full. This is the authoritative content
        # shown by View Result and must not differ from the workspace artifact.
        complete_summary = {}
        for k, v in result_summary.items():
            complete_summary[k] = str(v)
        run.result_summary = complete_summary
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(run, "result_summary")
        await session.commit()

    log.info("Flow run %s COMPLETED", run_id)


def _truncate(text: str, max_len: int) -> str:
    """Truncate text with an ellipsis marker."""
    if len(text) <= max_len:
        return text
    return text[:max_len - 20] + "\n\n[...truncated...]"
