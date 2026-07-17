"""Stack Orchestrator: persistent runtime control above the Agent Flow engine.

The service deliberately delegates concrete work to ``start_flow_run``.  It
owns long-horizon concerns only: posture gates, planning, checkpoints, pause /
resume, retries, verification, artifacts, state and final packaging.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.config import PROJECT_ROOT, settings
from shogun.db.engine import async_session_factory
from shogun.db.models.agent_flow import AgentFlow
from shogun.db.models.agent_flow_run import AgentFlowRun
from shogun.db.models.stack_orchestrator import (
    StackArtifact,
    StackCheckpoint,
    StackRun,
    StackStepRun,
    StackVerification,
)
from shogun.schemas.stack_orchestrator import StackOrchestratorCreate, StackPlanDecision
from shogun.services.agent_flow_service import AgentFlowService
from shogun.services.event_logger import EventLogger

log = logging.getLogger(__name__)
_active_stack_runs: dict[str, asyncio.Task] = {}
_TERMINAL = {"completed", "completed_with_errors", "failed", "cancelled"}


async def _audit(event_type: str, action: str, stack_run_id: uuid.UUID, **kwargs: Any) -> None:
    await EventLogger.emit(
        category="governance",
        event_type=event_type,
        action=action,
        session_id=str(stack_run_id),
        trace_id=str(stack_run_id),
        detail={"stack_run_id": str(stack_run_id), **kwargs.pop("detail", {})},
        **kwargs,
    )


class StackPlannerService:
    """Build persisted execution plans without executing generated work."""

    @staticmethod
    def goal_plan(objective: str, success_criteria: list[str]) -> list[dict[str, Any]]:
        criteria = "; ".join(success_criteria) or "Objective-specific acceptance criteria"
        return [
            {
                "name": "Inspect current state and constraints",
                "step_type": "planning",
                "expected_output": "Relevant architecture, permissions and risks identified",
                "risk_level": "low",
                "required_tools": [],
                "model_hint": "reasoning",
            },
            {
                "name": "Propose reusable Agent Stack",
                "step_type": "planning",
                "expected_output": f"Reviewable stack plan for: {objective}",
                "risk_level": "medium",
                "required_tools": [],
                "model_hint": "strong_reasoning",
            },
            {
                "name": "Execute approved Agent Stack",
                "step_type": "flow",
                "expected_output": "Approved stack completes its concrete work",
                "risk_level": "medium",
                "required_tools": [],
                "model_hint": "balanced",
            },
            {
                "name": "Verify success criteria",
                "step_type": "verification",
                "expected_output": criteria,
                "risk_level": "low",
                "required_tools": [],
                "model_hint": "strong_reasoning",
            },
            {
                "name": "Package final summary and artifacts",
                "step_type": "summary",
                "expected_output": "Final status, artifacts, verifications, issues and next steps",
                "risk_level": "low",
                "required_tools": [],
                "model_hint": "balanced",
            },
        ]

    @staticmethod
    async def flow_plan(
        session: AsyncSession,
        flow: AgentFlow,
        max_retries: int,
    ) -> list[dict[str, Any]]:
        nodes = list(flow.nodes)
        node_map = {node.id: node for node in nodes}
        indegree = {node.id: 0 for node in nodes}
        outgoing: dict[uuid.UUID, list[uuid.UUID]] = {node.id: [] for node in nodes}
        for edge in flow.edges:
            if edge.source_node_id in outgoing and edge.target_node_id in indegree:
                outgoing[edge.source_node_id].append(edge.target_node_id)
                indegree[edge.target_node_id] += 1
        queue = sorted(
            (node for node in nodes if indegree[node.id] == 0),
            key=lambda node: (node.position_x, node.position_y),
        )
        ordered = []
        while queue:
            node = queue.pop(0)
            ordered.append(node)
            for target in outgoing[node.id]:
                indegree[target] -= 1
                if indegree[target] == 0:
                    queue.append(node_map[target])
                    queue.sort(key=lambda item: (item.position_x, item.position_y))

        subflows = [node for node in ordered if node.node_type == "subflow"]
        if not subflows:
            return [
                {
                    "name": flow.name,
                    "step_type": "flow",
                    "flow_id": flow.id,
                    "expected_output": f"Agent Flow '{flow.name}' completes successfully",
                    "risk_level": flow.risk_tier,
                    "required_tools": flow.required_tools or [],
                    "max_retries": max_retries,
                    "model_hint": "balanced",
                }
            ]

        plan: list[dict[str, Any]] = []
        for node in subflows:
            config = node.config or {}
            try:
                child_id = uuid.UUID(str(config.get("child_flow_id")))
            except (TypeError, ValueError):
                continue
            child = await session.get(AgentFlow, child_id)
            plan.append(
                {
                    "name": node.label or (child.name if child else "Subflow"),
                    "step_type": "subflow",
                    "flow_id": child_id,
                    "expected_output": f"Subflow '{node.label}' completes successfully",
                    "risk_level": child.risk_tier if child else "medium",
                    "required_tools": child.required_tools if child else [],
                    "max_retries": int(config.get("max_retries", max_retries)),
                    "model_hint": config.get("model_profile", "balanced"),
                    "source_node_id": str(node.id),
                }
            )
        return plan


class StackCompactionService:
    """Build a bounded, durable hand-off for the next execution horizon."""

    @staticmethod
    def _bounded(value: Any, *, depth: int = 0) -> Any:
        if depth >= 5:
            return "[nested content compacted]"
        if isinstance(value, str):
            return value if len(value) <= 2000 else f"{value[:1800]}\n...[{len(value) - 1800} chars compacted]"
        if isinstance(value, dict):
            items = list(value.items())
            result = {str(key): StackCompactionService._bounded(item, depth=depth + 1) for key, item in items[:30]}
            if len(items) > 30:
                result["_compacted_keys"] = len(items) - 30
            return result
        if isinstance(value, list):
            result = [StackCompactionService._bounded(item, depth=depth + 1) for item in value[-20:]]
            if len(value) > 20:
                result.insert(0, f"[{len(value) - 20} earlier items compacted]")
            return result
        return value

    @staticmethod
    def _fit_budget(payload: dict[str, Any]) -> str:
        budget = max(2000, settings.stack_orchestrator_context_budget_chars)
        encoded = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        if len(encoded) <= budget:
            return encoded
        completed = payload.get("completed_steps", [])
        while len(encoded) > budget and len(completed) > 1:
            completed.pop(0)
            payload["earlier_completed_steps_compacted"] = payload.get("earlier_completed_steps_compacted", 0) + 1
            encoded = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        if len(encoded) > budget:
            payload["completed_steps"] = [
                {"name": item.get("name"), "status": item.get("status"), "verification": item.get("verification")}
                for item in completed
            ]
            encoded = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        if len(encoded) > budget:
            payload["goal"] = str(payload.get("goal", ""))[:800]
            payload["success_criteria"] = [str(item)[:300] for item in payload.get("success_criteria", [])[:10]]
            payload["important_decisions"] = [str(item)[:300] for item in payload.get("important_decisions", [])[-10:]]
            encoded = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        if len(encoded) > budget:
            payload = {
                "continuity_version": 2,
                "goal": str(payload.get("goal", ""))[:500],
                "stack_status": payload.get("stack_status"),
                "completed_step_count": len(completed),
                "failures": payload.get("failures", [])[-3:],
                "next_action": payload.get("next_action"),
                "active_skills": payload.get("active_skills", [])[-10:],
                "active_skill_constraints": payload.get("active_skill_constraints", [])[-20:],
                "compaction_notice": "Context exceeded the budget; full evidence remains in durable checkpoints.",
            }
            encoded = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        return encoded

    @staticmethod
    def compact(stack: StackRun, steps: list[StackStepRun], next_step: StackStepRun | None) -> str:
        completed = [
            {
                "step_id": step.step_id,
                "name": step.name,
                "status": step.status,
                "verification": step.verification_status,
                "output": StackCompactionService._bounded((step.output_json or {}).get("output", step.output_json)),
            }
            for step in steps
            if step.status == "completed"
        ]
        failed = [
            {"step_id": step.step_id, "name": step.name, "error": StackCompactionService._bounded(step.error_json)}
            for step in steps
            if step.status in {"failed", "blocked"}
        ]
        pending = [
            {"step_id": step.step_id, "name": step.name, "status": step.status}
            for step in steps
            if step.status in {"pending", "paused", "waiting_approval"}
        ]
        payload = {
            "continuity_version": 2,
            "goal": stack.objective,
            "success_criteria": stack.success_criteria or [],
            "stack_status": stack.status,
            "completed_steps": completed,
            "pending_steps": pending,
            "failures": failed,
            "important_decisions": (stack.metadata_json or {}).get("decisions", []),
            "active_skills": (stack.metadata_json or {}).get("active_skills", []),
            "active_skill_constraints": (stack.metadata_json or {}).get("active_skill_constraints", []),
            "next_action": {
                "step_id": next_step.step_id if next_step else None,
                "name": next_step.name if next_step else "produce final summary",
                "expected_output": next_step.expected_output if next_step else None,
            },
        }
        return StackCompactionService._fit_budget(payload)


class StackCheckpointService:
    @staticmethod
    async def create(
        session: AsyncSession, stack: StackRun, step: StackStepRun, steps: list[StackStepRun]
    ) -> StackCheckpoint:
        next_step = next((item for item in steps if item.sequence > step.sequence and item.status == "pending"), None)
        artifacts = list((step.output_json or {}).get("artifacts", []))
        checkpoint = StackCheckpoint(
            stack_run_id=stack.id,
            step_run_id=step.id,
            summary=f"{step.name} completed and verified={step.verification_status}.",
            context_summary=StackCompactionService.compact(stack, steps, next_step),
            resume_instruction=(f"Continue with '{next_step.name}'." if next_step else "Finalize the stack run."),
            artifacts_json=artifacts,
            state_json={
                "continuity_version": 2,
                "current_step_id": step.step_id,
                "completed_steps": [item.step_id for item in steps if item.status == "completed"],
                "pending_steps": [item.step_id for item in steps if item.status == "pending"],
                "failed_steps": [item.step_id for item in steps if item.status == "failed"],
                "last_output": step.output_json,
                "model_usage": stack.model_usage or [],
                "success_criteria": stack.success_criteria or [],
            },
        )
        session.add(checkpoint)
        await session.flush()
        return checkpoint


class StackArtifactService:
    @staticmethod
    async def capture(
        session: AsyncSession, stack: StackRun, step: StackStepRun, flow_run: AgentFlowRun
    ) -> list[StackArtifact]:
        captured = []
        for raw in flow_run.artifacts or []:
            data = raw if isinstance(raw, dict) else {"summary": str(raw)}
            if stack.artifact_policy == "retain_selected" and not data.get("retain", False):
                continue
            artifact = StackArtifact(
                stack_run_id=stack.id,
                step_run_id=step.id,
                artifact_type=str(data.get("type", "flow_artifact")),
                path=data.get("path"),
                summary=str(data.get("summary") or data.get("name") or "Agent Flow artifact"),
                metadata_json={**data, "flow_run_id": str(flow_run.id)},
            )
            session.add(artifact)
            captured.append(artifact)
        if not captured and stack.artifact_policy != "retain_selected":
            artifact = StackArtifact(
                stack_run_id=stack.id,
                step_run_id=step.id,
                artifact_type="flow_result",
                path=None,
                summary=f"Structured result for {step.name}",
                metadata_json={"flow_run_id": str(flow_run.id), "output": flow_run.output_payload or {}},
            )
            session.add(artifact)
            captured.append(artifact)
        await session.flush()
        return captured


class StackVerificationService:
    @staticmethod
    def _explicit_checks(output: Any) -> list[dict[str, Any]]:
        checks: list[dict[str, Any]] = []
        if not isinstance(output, dict):
            return checks
        candidates = []
        for key in ("verification", "quality_gate", "success_criteria", "checks", "tests"):
            if key in output:
                candidates.append((key, output[key]))
        for group, value in candidates:
            if isinstance(value, dict):
                for name, result in value.items():
                    status = result.get("status") if isinstance(result, dict) else result
                    passed = result.get("passed") if isinstance(result, dict) else None
                    if passed is None:
                        passed = str(status).lower() in {"true", "passed", "pass", "approved", "success", "completed"}
                    checks.append({"name": f"{group}.{name}", "passed": bool(passed), "observed": str(status)})
            elif isinstance(value, list):
                for index, result in enumerate(value):
                    if isinstance(result, dict):
                        status = result.get("status", result.get("passed"))
                        name = result.get("name", f"{group}[{index}]")
                    else:
                        status, name = result, f"{group}[{index}]"
                    checks.append(
                        {
                            "name": str(name),
                            "passed": status is True
                            or str(status).lower() in {"passed", "pass", "approved", "success"},
                            "observed": str(status),
                        }
                    )
            elif isinstance(value, (bool, str)):
                checks.append(
                    {
                        "name": group,
                        "passed": value is True or str(value).lower() in {"passed", "pass", "approved", "success"},
                        "observed": str(value),
                    }
                )
        return checks

    @staticmethod
    async def _semantic_judgement(
        session: AsyncSession,
        stack: StackRun,
        step: StackStepRun,
        output: Any,
    ) -> dict[str, Any] | None:
        """Use an independently-routed judge when a model is configured."""
        try:
            from shogun.engine.flow_engine import _call_llm_chain, _resolve_task_llm_chain

            chain, _routing = await _resolve_task_llm_chain(
                session,
                prompt=f"Verify step {step.name}: {StackCompactionService._bounded(output)}",
                task_type="self_verification",
                required_capabilities=["chat", "reasoning", "json_mode"],
                routing_profile_id=stack.model_profile,
                stack_run_id=stack.id,
                step_id=step.step_id,
                verification_status=step.verification_status,
                risk_level=step.risk_level,
                exclude_model_ids=[step.model_used] if step.model_used else [],
            )
            if not chain:
                return None
            prompt = {
                "objective": stack.objective,
                "stack_success_criteria": stack.success_criteria or [],
                "step": step.name,
                "expected_result": step.expected_output,
                "observed_output": StackCompactionService._bounded(output),
                "active_skill_verification_checklist": (step.metadata_json or {}).get(
                    "active_skill_verification_checklist", []
                ),
            }
            response = await _call_llm_chain(
                [
                    {
                        "role": "system",
                        "content": (
                            "You are an independent execution verifier. Judge evidence, not task completion. "
                            "Return JSON only with passed (boolean), score (0-100), reasons (array), and checks (array). "
                            "Fail missing, contradictory, placeholder, or unsupported results."
                        ),
                    },
                    {"role": "user", "content": json.dumps(prompt, ensure_ascii=False, default=str)},
                ],
                chain,
                timeout=settings.stack_orchestrator_verifier_timeout_seconds,
                retry_count=0,
                context="Stack independent verifier",
                routing_context=_routing,
                usage_session=session,
            )
            cleaned = response.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            result = json.loads(cleaned)
            if not isinstance(result.get("passed"), bool):
                return None
            return result
        except Exception as exc:
            log.info("Independent model verifier unavailable; using deterministic evidence gate: %s", exc)
            return None

    @staticmethod
    async def verify(
        session: AsyncSession, stack: StackRun, step: StackStepRun, flow_run: AgentFlowRun
    ) -> StackVerification:
        output = flow_run.output_payload or flow_run.result_summary or {}
        base_checks = [
            {"name": "flow_completed", "passed": flow_run.status == "completed", "observed": flow_run.status},
            {
                "name": "no_runtime_error",
                "passed": not bool(flow_run.error_message),
                "observed": flow_run.error_message or "none",
            },
            {
                "name": "non_empty_output",
                "passed": bool(output),
                "observed": f"{len(json.dumps(output, default=str))} chars",
            },
        ]
        explicit_checks = StackVerificationService._explicit_checks(output)
        semantic = await StackVerificationService._semantic_judgement(session, stack, step, output)
        checks = [*base_checks, *explicit_checks]
        later_step = await session.scalar(
            select(StackStepRun.id)
            .where(StackStepRun.stack_run_id == stack.id, StackStepRun.sequence > step.sequence)
            .limit(1)
        )
        if not later_step and stack.success_criteria and semantic is None:
            checks.append(
                {
                    "name": "success_criteria_evidence_present",
                    "passed": bool(explicit_checks),
                    "observed": (
                        "machine-readable success-criteria evidence found"
                        if explicit_checks
                        else "no independent model or machine-readable acceptance evidence available"
                    ),
                }
            )
        if semantic:
            checks.append(
                {
                    "name": "independent_semantic_judge",
                    "passed": semantic["passed"],
                    "observed": "; ".join(str(item) for item in semantic.get("reasons", []))
                    or str(semantic.get("score")),
                }
            )
        passed = all(item["passed"] for item in checks)
        mode = "model_and_evidence" if semantic else "deterministic_evidence"
        failures = [item for item in checks if not item["passed"]]
        verification = StackVerification(
            stack_run_id=stack.id,
            step_run_id=step.id,
            verification_type="independent_quality_gate",
            expected_result=step.expected_output or "Step completes successfully",
            observed_result=(
                f"{mode} passed {len(checks)} independent checks"
                if passed
                else "; ".join(f"{item['name']}: {item['observed']}" for item in failures)
            ),
            status="passed" if passed else "failed",
            metadata_json={
                "flow_run_id": str(flow_run.id),
                "flow_status": flow_run.status,
                "verifier_mode": mode,
                "checks": checks,
                "score": semantic.get("score")
                if semantic
                else round(100 * sum(item["passed"] for item in checks) / len(checks)),
                "reasons": semantic.get("reasons", []) if semantic else [item["observed"] for item in failures],
            },
        )
        session.add(verification)
        step.verification_status = verification.status
        await session.flush()
        return verification


class StackRetryService:
    @staticmethod
    def failure_category(flow_run: AgentFlowRun) -> str:
        message = (flow_run.error_message or "").lower()
        if "permission" in message or "blocked" in message:
            return "permission_failure"
        if "timeout" in message:
            return "runtime_failure"
        if "verify" in message:
            return "verification_failure"
        return "tool_or_flow_failure"


async def _audit_step_evidence(
    stack: StackRun,
    step: StackStepRun,
    artifacts: list[StackArtifact],
    verification: StackVerification,
    checkpoint: StackCheckpoint | None = None,
) -> None:
    for artifact in artifacts:
        await _audit(
            "stack.artifact.created",
            artifact.summary,
            stack.id,
            detail={"artifact_id": str(artifact.id), "step_id": step.step_id},
        )
    await _audit(
        f"stack.verification.{verification.status}",
        f"Verification {verification.status} for '{step.name}'",
        stack.id,
        result="success" if verification.status == "passed" else "failure",
        severity="info" if verification.status == "passed" else "warn",
        detail={"step_id": step.step_id, "verification_id": str(verification.id)},
    )
    if checkpoint:
        await _audit(
            "stack.checkpoint.created",
            f"Checkpoint created after '{step.name}'",
            stack.id,
            detail={"checkpoint_id": str(checkpoint.id), "step_id": step.step_id},
        )


class StackApprovalService:
    @staticmethod
    def add_event(stack: StackRun, action: str, status: str, reason: str | None = None) -> None:
        events = list(stack.approval_events or [])
        events.append(
            {
                "id": str(uuid.uuid4()),
                "action": action,
                "status": status,
                "reason": reason,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        stack.approval_events = events


class StackExecutionTreeService:
    @staticmethod
    def build(stack: StackRun, steps: list[StackStepRun]) -> dict[str, Any]:
        return {
            "id": str(stack.id),
            "name": stack.objective,
            "status": stack.status,
            "type": "stack_run",
            "children": [
                {
                    "id": step.step_id,
                    "step_run_id": str(step.id),
                    "name": step.name,
                    "status": step.status,
                    "model_used": step.model_used,
                    "retries": step.retry_count,
                    "verification_status": step.verification_status,
                    "approval_state": "waiting" if step.status == "waiting_approval" else "not_required",
                    "flow_run_id": str(step.flow_run_id) if step.flow_run_id else None,
                }
                for step in steps
            ],
        }


class StackStateService:
    @staticmethod
    async def steps(session: AsyncSession, stack_run_id: uuid.UUID) -> list[StackStepRun]:
        result = await session.execute(
            select(StackStepRun).where(StackStepRun.stack_run_id == stack_run_id).order_by(StackStepRun.sequence)
        )
        return list(result.scalars().all())

    @staticmethod
    def refresh_lists(stack: StackRun, steps: list[StackStepRun]) -> None:
        stack.completed_steps = [step.step_id for step in steps if step.status == "completed"]
        stack.pending_steps = [
            step.step_id for step in steps if step.status in {"pending", "paused", "waiting_approval"}
        ]
        stack.failed_steps = [step.step_id for step in steps if step.status == "failed"]


class StackOrchestratorService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, body: StackOrchestratorCreate) -> StackRun:
        if not settings.stack_orchestrator_enabled:
            raise ValueError("Stack Orchestrator is disabled.")
        if body.mode == "template" and body.stack_template_id:
            from shogun.api.agent_flow import _flow_stack_templates

            recipe = next(
                (item for item in _flow_stack_templates() if item["id"] == body.stack_template_id),
                None,
            )
            if recipe:
                config = recipe["orchestrator_config"]
                body = body.model_copy(
                    update={
                        "success_criteria": config["success_criteria"],
                        "model_routing_profile": config["model_routing_profile"],
                        "max_runtime_minutes": config["max_runtime_minutes"],
                        "max_iterations": config["max_iterations"],
                        "max_retry_attempts_per_step": config["max_retry_attempts_per_step"],
                        "checkpoint_frequency": config["checkpoint_frequency"],
                        "context_compaction": config["context_compaction"],
                        "verification_required": config["verification_required"],
                        "approval_policy": config["approval_policy"],
                        "artifact_policy": config["artifact_policy"],
                        "failure_policy": config["failure_policy"],
                    }
                )
        posture = await self._posture_gate(body)
        flow = None
        if body.mode == "selected_stack":
            flow = await AgentFlowService(self.session).get_flow_full(body.selected_stack_id)
            if not flow:
                raise ValueError("Selected Agent Stack does not exist.")
        elif body.mode == "template":
            flow = await self._instantiate_template(body.stack_template_id, body.objective)

        needs_review = body.mode == "goal_driven" or posture == "tactical"
        stack = StackRun(
            stack_id=flow.id if flow else None,
            mode=body.mode,
            status="waiting_approval" if needs_review else "created",
            objective=body.objective,
            posture=posture,
            model_profile=body.model_routing_profile,
            max_runtime_minutes=body.max_runtime_minutes,
            max_iterations=body.max_iterations,
            max_retry_attempts_per_step=body.max_retry_attempts_per_step,
            checkpoint_frequency=body.checkpoint_frequency,
            context_compaction=body.context_compaction == "enabled",
            verification_required=body.verification_required,
            approval_policy=body.approval_policy,
            artifact_policy=body.artifact_policy,
            failure_policy=body.failure_policy,
            success_criteria=body.success_criteria,
            allowed_tools=body.allowed_tools,
            metadata_json={
                "input_payload": body.input_payload,
                "stack_template_id": body.stack_template_id,
                "plan_review_required": needs_review,
                "generated_plan": body.mode == "goal_driven",
            },
        )
        if needs_review:
            StackApprovalService.add_event(stack, "Review generated or supervised stack plan", "requested")
        self.session.add(stack)
        await self.session.flush()

        # Activate stack-level skills before constructing the execution plan.
        try:
            from shogun.schemas.skills import SkillActivationRequest
            from shogun.services.active_skill_service import SkillActivationService

            skill_activation = await SkillActivationService(self.session).activate(SkillActivationRequest(
                run_id=str(stack.id), stack_run_id=stack.id, objective=stack.objective,
                context="Plan a governed long-running Agent Stack. " + " ".join(stack.success_criteria or []),
                posture=stack.posture, available_tools=stack.allowed_tools or [],
                max_skills=settings.active_skill_max_per_run, usage_location="stack_planning",
                ide_enabled=any(str(tool).startswith("ide") for tool in (stack.allowed_tools or [])),
                activation_phase="planning",
            ))
            stack_meta = dict(stack.metadata_json or {})
            stack_meta["active_skills"] = [
                {"skill_id": str(item["skill_id"]), "name": item["name"],
                 "reason": item["activation_reason"], "phase": "planning"}
                for item in skill_activation["active_skills"]
            ]
            stack_meta["active_skill_constraints"] = [
                check for item in skill_activation["active_skills"]
                for check in item.get("verification_checklist", [])
            ]
            stack_meta["skill_context"] = skill_activation["context_block"]
            stack.metadata_json = stack_meta
        except Exception as exc:
            log.warning("Stack planning skill activation skipped: %s", exc)

        plan = (
            await StackPlannerService.flow_plan(self.session, flow, body.max_retry_attempts_per_step)
            if flow
            else StackPlannerService.goal_plan(body.objective, body.success_criteria)
        )
        if len(plan) > settings.stack_orchestrator_max_steps:
            raise ValueError("Stack plan exceeds the configured maximum step count.")
        await self._replace_steps(stack, plan)
        await self.session.commit()
        await self.session.refresh(stack)
        await _audit(
            "stack.orchestrator.created",
            f"Stack Orchestrator run created for '{stack.objective}'",
            stack.id,
            detail={
                "mode": stack.mode,
                "posture": stack.posture,
                "stack_id": str(stack.stack_id) if stack.stack_id else None,
            },
        )
        if body.mode == "goal_driven":
            await _audit("stack.plan.generated", "Goal-driven stack plan generated for review", stack.id)
        return stack

    async def approve_plan(self, stack_run_id: uuid.UUID, decision: StackPlanDecision) -> StackRun:
        stack = await self._get(stack_run_id)
        if stack.status not in {"waiting_approval", "paused", "created"}:
            raise ValueError("This stack plan is not awaiting a decision.")
        if not decision.approved:
            stack.status = "cancelled"
            stack.completed_at = datetime.now(timezone.utc)
            StackApprovalService.add_event(stack, "Stack plan", "rejected", decision.reason)
            await self.session.commit()
            await _audit("stack.plan.rejected", "Stack plan rejected", stack.id, result="failure")
            return stack

        if decision.selected_stack_id:
            flow = await AgentFlowService(self.session).get_flow_full(decision.selected_stack_id)
            if not flow:
                raise ValueError("Approved Agent Stack does not exist.")
            stack.stack_id = flow.id
            plan = await StackPlannerService.flow_plan(
                self.session,
                flow,
                stack.max_retry_attempts_per_step,
            )
            await self._replace_steps(stack, plan)
        if not stack.stack_id:
            raise ValueError("Goal-driven plans must be attached to a reviewed Agent Stack before approval.")
        stack.status = "created"
        StackApprovalService.add_event(stack, "Stack plan", "approved", decision.reason)
        await self.session.commit()
        await _audit("stack.plan.approved", "Stack plan approved", stack.id)
        return stack

    async def approve_step(self, stack_run_id: uuid.UUID, step_id: str, approved: bool, reason: str | None) -> StackRun:
        stack = await self._get(stack_run_id)
        result = await self.session.execute(
            select(StackStepRun).where(
                StackStepRun.stack_run_id == stack.id,
                StackStepRun.step_id == step_id,
            )
        )
        step = result.scalar_one_or_none()
        if not step or step.status != "waiting_approval":
            raise ValueError("Step is not waiting for approval.")
        StackApprovalService.add_event(stack, step.name, "granted" if approved else "rejected", reason)
        if approved:
            step.requires_approval = False
            step.status = "pending"
            stack.status = "paused"
        else:
            step.status = "blocked"
            stack.status = "failed"
            stack.completed_at = datetime.now(timezone.utc)
        await self.session.commit()
        await _audit(
            "stack.approval.granted" if approved else "stack.approval.rejected",
            f"Approval {'granted' if approved else 'rejected'} for '{step.name}'",
            stack.id,
            detail={"step_id": step.step_id, "reason": reason},
        )
        return stack

    async def start(self, stack_run_id: uuid.UUID) -> StackRun:
        stack = await self._get(stack_run_id)
        await self._assert_live_posture(stack)
        if stack.status == "waiting_approval":
            raise ValueError("Stack plan approval is required before execution.")
        if stack.status not in {"created", "paused", "failed"}:
            raise ValueError(f"Stack cannot start from status '{stack.status}'.")
        steps = await StackStateService.steps(self.session, stack.id)
        if not any(step.flow_id for step in steps):
            raise ValueError("The reviewed plan has no executable Agent Stack attached.")
        failed_restart = stack.status == "failed"
        for step in steps:
            if step.status in {"paused", "running", "retrying"}:
                step.status = "pending"
                step.flow_run_id = None
            elif failed_restart and step.status == "failed":
                step.status = "pending"
                step.flow_run_id = None
                step.completed_at = None
        stack.status = "running"
        stack.started_at = stack.started_at or datetime.now(timezone.utc)
        stack.completed_at = None
        await self.session.commit()
        self._launch(stack.id)
        await _audit("stack.orchestrator.started", "Stack Orchestrator execution started", stack.id)
        return stack

    async def pause(self, stack_run_id: uuid.UUID) -> StackRun:
        stack = await self._get(stack_run_id)
        if stack.status != "running":
            raise ValueError("Only a running stack can be paused.")
        stack.status = "paused"
        steps = await StackStateService.steps(self.session, stack.id)
        current = next((step for step in steps if step.status in {"running", "retrying"}), None)
        if current:
            current.status = "paused"
            if current.flow_run_id:
                from shogun.engine.flow_engine import cancel_flow_run

                await cancel_flow_run(current.flow_run_id)
            current.flow_run_id = None
        await self.session.commit()
        task = _active_stack_runs.pop(str(stack.id), None)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        await _audit("stack.orchestrator.paused", "Stack Orchestrator execution paused", stack.id)
        return stack

    async def resume(self, stack_run_id: uuid.UUID) -> StackRun:
        stack = await self._get(stack_run_id)
        if stack.status != "paused":
            raise ValueError("Only a paused stack can be resumed.")
        checkpoints = await self.session.execute(
            select(StackCheckpoint)
            .where(StackCheckpoint.stack_run_id == stack.id)
            .order_by(StackCheckpoint.created_at.desc())
        )
        latest = checkpoints.scalars().first()
        stack.status = "running"
        steps = await StackStateService.steps(self.session, stack.id)
        for step in steps:
            if step.status == "paused":
                step.status = "pending"
        await self.session.commit()
        self._launch(stack.id)
        await _audit(
            "stack.orchestrator.resumed",
            "Stack Orchestrator resumed from latest valid checkpoint",
            stack.id,
            detail={"checkpoint_id": str(latest.id) if latest else None},
        )
        if latest:
            await _audit("stack.checkpoint.loaded", "Latest checkpoint loaded for resume", stack.id)
        return stack

    async def recover(self, stack_run_id: uuid.UUID) -> StackRun:
        """Recover a run whose in-process worker disappeared unexpectedly."""
        stack = await self._get(stack_run_id)
        await self._assert_live_posture(stack)
        if stack.status not in {"running", "paused"}:
            raise ValueError("Only running or paused stacks can be recovered.")
        await self._prepare_recovery(stack)
        stack.status = "running"
        await self.session.commit()
        self._launch(stack.id)
        await _audit("stack.orchestrator.recovered", "Interrupted Stack Orchestrator run recovered", stack.id)
        return stack

    async def cancel(self, stack_run_id: uuid.UUID) -> StackRun:
        stack = await self._get(stack_run_id)
        if stack.status in _TERMINAL:
            return stack
        stack.status = "cancelled"
        stack.completed_at = datetime.now(timezone.utc)
        steps = await StackStateService.steps(self.session, stack.id)
        current = next((step for step in steps if step.status in {"running", "retrying", "paused"}), None)
        if current:
            current.status = "cancelled"
            if current.flow_run_id:
                from shogun.engine.flow_engine import cancel_flow_run

                await cancel_flow_run(current.flow_run_id)
        await self.session.commit()
        task = _active_stack_runs.pop(str(stack.id), None)
        if task and not task.done():
            task.cancel()
        await _audit("stack.orchestrator.cancelled", "Stack Orchestrator execution cancelled", stack.id)
        return stack

    async def get(self, stack_run_id: uuid.UUID) -> tuple[StackRun, list[StackStepRun]]:
        stack = await self._get(stack_run_id)
        return stack, await StackStateService.steps(self.session, stack.id)

    async def list_runs(self, limit: int = 50) -> list[StackRun]:
        result = await self.session.execute(select(StackRun).order_by(StackRun.created_at.desc()).limit(limit))
        return list(result.scalars().all())

    async def checkpoints(self, stack_run_id: uuid.UUID) -> list[StackCheckpoint]:
        await self._get(stack_run_id)
        result = await self.session.execute(
            select(StackCheckpoint)
            .where(StackCheckpoint.stack_run_id == stack_run_id)
            .order_by(StackCheckpoint.created_at.desc())
        )
        return list(result.scalars().all())

    async def artifacts(self, stack_run_id: uuid.UUID) -> list[StackArtifact]:
        await self._get(stack_run_id)
        result = await self.session.execute(
            select(StackArtifact).where(StackArtifact.stack_run_id == stack_run_id).order_by(StackArtifact.created_at)
        )
        return list(result.scalars().all())

    async def verifications(self, stack_run_id: uuid.UUID) -> list[StackVerification]:
        await self._get(stack_run_id)
        result = await self.session.execute(
            select(StackVerification)
            .where(StackVerification.stack_run_id == stack_run_id)
            .order_by(StackVerification.created_at)
        )
        return list(result.scalars().all())

    async def tree(self, stack_run_id: uuid.UUID) -> dict[str, Any]:
        stack, steps = await self.get(stack_run_id)
        return StackExecutionTreeService.build(stack, steps)

    async def _get(self, stack_run_id: uuid.UUID) -> StackRun:
        stack = await self.session.get(StackRun, stack_run_id)
        if not stack:
            raise ValueError("Stack Orchestrator run not found.")
        return stack

    async def _prepare_recovery(self, stack: StackRun) -> None:
        steps = await StackStateService.steps(self.session, stack.id)
        now = datetime.now(timezone.utc).isoformat()
        recovered_steps = []
        for step in steps:
            if step.status in {"running", "retrying", "paused"}:
                recovered_steps.append(step.step_id)
                if step.flow_run_id:
                    flow_run = await self.session.get(AgentFlowRun, step.flow_run_id)
                    if flow_run and flow_run.status not in _TERMINAL:
                        flow_run.status = "cancelled"
                        flow_run.completed_at = datetime.now(timezone.utc)
                        flow_run.error_message = "Interrupted by process restart; recovered from durable checkpoint."
                step.status = "pending"
                step.flow_run_id = None
        metadata = dict(stack.metadata_json or {})
        recoveries = list(metadata.get("recovery_events", []))
        recoveries.append({"recovered_at": now, "steps": recovered_steps})
        metadata["recovery_events"] = recoveries[-20:]
        stack.metadata_json = metadata
        stack.completed_at = None

    async def _replace_steps(self, stack: StackRun, plan: list[dict[str, Any]]) -> None:
        await self.session.execute(delete(StackStepRun).where(StackStepRun.stack_run_id == stack.id))
        step_ids = []
        for index, item in enumerate(plan, start=1):
            step_id = f"step_{index:03d}"
            step_ids.append(step_id)
            risk = item.get("risk_level", "low")
            requires_approval = risk in {"high", "critical"} and stack.approval_policy in {
                "step_based",
                "always_required_for_high_risk",
            }
            self.session.add(
                StackStepRun(
                    stack_run_id=stack.id,
                    step_id=step_id,
                    parent_step_id=None,
                    sequence=index,
                    name=item["name"],
                    status="pending",
                    step_type=item.get("step_type", "flow"),
                    flow_id=item.get("flow_id"),
                    max_retries=int(item.get("max_retries", stack.max_retry_attempts_per_step)),
                    expected_output=item.get("expected_output"),
                    requires_verification=stack.verification_required,
                    requires_approval=requires_approval,
                    risk_level=risk,
                    required_tools=item.get("required_tools", []),
                    metadata_json={
                        "model_hint": item.get("model_hint", stack.model_profile),
                        "source_node_id": item.get("source_node_id"),
                    },
                )
            )
        stack.pending_steps = step_ids
        stack.completed_steps = []
        stack.failed_steps = []
        await self.session.flush()

    async def _instantiate_template(self, template_id: str, objective: str) -> AgentFlow:
        from shogun.api.agent_flow import _flow_stack_templates, compose_flow_stack
        from shogun.schemas.agent_flow import FlowStackComposeEdge, FlowStackComposeNode, FlowStackComposeRequest

        recipe = next((item for item in _flow_stack_templates() if item["id"] == template_id), None)
        if recipe:
            config = dict(recipe["orchestrator_config"])
            config["objective"] = objective or config["objective"]
            response = await compose_flow_stack(
                FlowStackComposeRequest(
                    name=recipe["name"],
                    description=recipe["description"],
                    category=recipe["category"],
                    nodes=[
                        FlowStackComposeNode(
                            id=item["id"],
                            template_id=item["template_id"],
                            label=item["label"],
                            position_x=item["position_x"],
                            position_y=item["position_y"],
                        )
                        for item in recipe["builder_nodes"]
                    ],
                    edges=[
                        FlowStackComposeEdge(source=item["source"], target=item["target"])
                        for item in recipe["builder_edges"]
                    ],
                    orchestrator_config=config,
                ),
                AgentFlowService(self.session),
            )
            return await AgentFlowService(self.session).get_flow_full(response.data.id)

        # Backward compatibility for callers that still reference a single
        # AgentFlow catalog template rather than a long-running stack program.
        catalog_path = Path(PROJECT_ROOT) / "shogun" / "resources" / "flow_templates.json"
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        template = next((item for item in catalog.get("templates", []) if item.get("id") == template_id), None)
        if not template:
            raise ValueError(f"Stack template '{template_id}' was not found.")
        svc = AgentFlowService(self.session)
        flow = await svc.create(
            name=f"{template.get('name', template_id)} · Orchestrated",
            description=objective or template.get("description", ""),
            trigger_type="manual",
            schedule_config={},
            flow_type="stack",
            allow_as_subflow=True,
        )
        saved = await svc.save_flow_graph(
            flow.id,
            template.get("nodes", []),
            template.get("edges", []),
            {"x": 50, "y": 100, "zoom": 0.85},
        )
        return saved or flow

    async def _posture_gate(self, body: StackOrchestratorCreate) -> str:
        from shogun.services.posture_guard import get_posture_tool_filter

        posture = await get_posture_tool_filter()
        tier = str(posture.get("active_tier", "guarded")).lower()
        if posture.get("kill_switch_active"):
            raise ValueError("Stack Orchestrator is blocked while HARAKIRI is active.")
        if tier not in {"tactical", "campaign", "ronin"}:
            raise ValueError(f"Stack Orchestrator is unavailable at {tier.upper()} posture.")
        if tier == "tactical" and not settings.stack_orchestrator_allow_supervised:
            raise ValueError("Supervised Stack Orchestrator execution is disabled.")
        if tier == "tactical" and body.mode == "goal_driven":
            raise ValueError("Goal-driven orchestration requires Campaign or Ronin posture.")
        self._validate_tools(body.allowed_tools, posture, tier)
        return tier

    async def _assert_live_posture(self, stack: StackRun) -> None:
        from shogun.services.posture_guard import get_posture_tool_filter

        posture = await get_posture_tool_filter()
        tier = str(posture.get("active_tier", "guarded")).lower()
        if tier not in {"tactical", "campaign", "ronin"}:
            raise ValueError(f"Stack execution is blocked at {tier.upper()} posture.")
        self._validate_tools(stack.allowed_tools or [], posture, tier)

    @staticmethod
    def _validate_tools(tools: list[str], posture: dict[str, Any], tier: str) -> None:
        normalized = {str(tool).lower() for tool in tools}
        if normalized & {"ide", "ide_mode", "vscode"}:
            if tier not in {"campaign", "ronin"} or not posture.get("ide_enabled", False):
                raise ValueError("IDE Mode tools require Campaign/Ronin posture and IDE Mode enabled.")
        if normalized & {"ronin", "desktop", "desktop_control"}:
            if tier != "ronin" or not posture.get("ronin_enabled", False):
                raise ValueError("Ronin desktop tools require Ronin posture and desktop control enabled.")
        if normalized & {"mado", "browser"} and not posture.get("mado_enabled", False):
            raise ValueError("Mado tools are disabled by the current posture.")
        if normalized & {"office", "productivity"} and not posture.get("office_enabled", False):
            raise ValueError("Productivity tools are disabled by the current posture.")

    @staticmethod
    def _launch(stack_run_id: uuid.UUID) -> None:
        existing = _active_stack_runs.get(str(stack_run_id))
        if existing and not existing.done():
            return
        task = asyncio.create_task(_run_stack(stack_run_id))
        _active_stack_runs[str(stack_run_id)] = task

        def clear_if_current(done: asyncio.Task) -> None:
            if _active_stack_runs.get(str(stack_run_id)) is done:
                _active_stack_runs.pop(str(stack_run_id), None)

        task.add_done_callback(clear_if_current)


async def _run_stack(stack_run_id: uuid.UUID) -> None:
    from shogun.engine.flow_engine import start_flow_run

    try:
        iterations = 0
        previous_output: dict[str, Any] = {}
        async with async_session_factory() as session:
            latest = (
                (
                    await session.execute(
                        select(StackCheckpoint)
                        .where(StackCheckpoint.stack_run_id == stack_run_id)
                        .order_by(StackCheckpoint.created_at.desc())
                        .limit(1)
                    )
                )
                .scalars()
                .first()
            )
            if latest:
                last_output = (latest.state_json or {}).get("last_output", {})
                previous_output = last_output.get("output", last_output) if isinstance(last_output, dict) else {}
        while True:
            async with async_session_factory() as session:
                stack = await session.get(StackRun, stack_run_id)
                if not stack or stack.status != "running":
                    return
                if stack.started_at:
                    started_at = stack.started_at
                    if started_at.tzinfo is None:
                        started_at = started_at.replace(tzinfo=timezone.utc)
                    elapsed_minutes = (datetime.now(timezone.utc) - started_at).total_seconds() / 60
                    if elapsed_minutes >= stack.max_runtime_minutes:
                        await _fail_stack(session, stack, "Maximum Stack Orchestrator runtime exceeded.")
                        return
                steps = await StackStateService.steps(session, stack.id)
                step = next((item for item in steps if item.status in {"pending", "paused"}), None)
                if not step:
                    await _finalize(session, stack, steps)
                    return
                iterations += 1
                if iterations > stack.max_iterations:
                    await _fail_stack(session, stack, "Maximum stack iterations exceeded.")
                    return
                if step.requires_approval:
                    step.status = "waiting_approval"
                    stack.status = "waiting_approval"
                    StackApprovalService.add_event(stack, step.name, "requested", "High-risk step")
                    await session.commit()
                    await _audit(
                        "stack.step.waiting_approval",
                        f"'{step.name}' is waiting for approval",
                        stack.id,
                        detail={"step_id": step.step_id, "risk_level": step.risk_level},
                    )
                    return
                if not step.flow_id:
                    await _fail_stack(session, stack, f"Step '{step.name}' has no approved Agent Flow.")
                    return

                step.status = "running" if step.retry_count == 0 else "retrying"
                step.started_at = step.started_at or datetime.now(timezone.utc)
                stack.current_step_id = step.step_id
                context = StackCompactionService.compact(stack, steps, step) if stack.context_compaction else ""
                try:
                    from shogun.schemas.skills import SkillActivationRequest
                    from shogun.services.active_skill_service import SkillActivationService

                    available_skill_tools = list(set((stack.allowed_tools or []) + (step.required_tools or [])))
                    skill_activation = await SkillActivationService(session).activate(SkillActivationRequest(
                        run_id=str(stack.id), stack_run_id=stack.id, step_run_id=step.id,
                        objective=f"{stack.objective}\nStep: {step.name}\nExpected: {step.expected_output or ''}",
                        context=context, posture=stack.posture, available_tools=available_skill_tools,
                        max_skills=settings.active_skill_max_per_step, usage_location="stack_step",
                        ide_enabled=any(
                            str(tool).startswith("ide") or str(tool) in {"ide", "vscode"}
                            for tool in available_skill_tools
                        ),
                        activation_phase="retry" if step.retry_count else "execution",
                    ))
                    if skill_activation["context_block"]:
                        context += "\n\n" + skill_activation["context_block"]
                    step_meta = dict(step.metadata_json or {})
                    step_meta["active_skills"] = [
                        {"skill_id": str(item["skill_id"]), "name": item["name"],
                         "reason": item["activation_reason"], "score": item["relevance_score"]}
                        for item in skill_activation["active_skills"]
                    ]
                    step_meta["active_skill_run_ids"] = [
                        str(item["active_skill_run_id"]) for item in skill_activation["active_skills"]
                    ]
                    step_meta["active_skill_verification_checklist"] = [
                        check for item in skill_activation["active_skills"]
                        for check in item.get("verification_checklist", [])
                    ]
                    step.metadata_json = step_meta
                    stack_meta = dict(stack.metadata_json or {})
                    active_history = list(stack_meta.get("active_skills", []))
                    active_history.extend(
                        {"skill_id": str(item["skill_id"]), "name": item["name"],
                         "reason": item["activation_reason"], "phase": f"step:{step.step_id}"}
                        for item in skill_activation["active_skills"]
                    )
                    stack_meta["active_skills"] = active_history[-50:]
                    stack.metadata_json = stack_meta
                except Exception as exc:
                    log.warning("Stack step skill activation skipped: %s", exc)
                from shogun.schemas.model_router import ModelRouteRequest
                from shogun.services.model_router import ModelRoutingService

                coding_step = any(tool in {"ide", "vscode", "workspace"} for tool in (step.required_tools or []))
                task_type = (
                    "test_failure_analysis"
                    if step.retry_count or step.verification_status == "failed"
                    else "coding_edit"
                    if coding_step
                    else "stack_step_execution"
                )
                required_capabilities = ["chat"]
                if step.required_tools:
                    required_capabilities.append("tool_use")
                step_db_id = step.id
                routing = None
                try:
                    routing = await ModelRoutingService(session).route(
                        ModelRouteRequest(
                            prompt=f"{stack.objective}\n\nStep: {step.name}\nExpected: {step.expected_output or ''}",
                            task_type=task_type,
                            required_capabilities=required_capabilities,
                            risk_level=step.risk_level
                            if step.risk_level in {"low", "medium", "high", "critical"}
                            else "low",
                            retry_count=step.retry_count,
                            verification_status=step.verification_status,
                            profile_override=stack.model_profile,
                            stack_run_id=stack.id,
                            step_id=step.step_id,
                            escalation_level=min(step.retry_count, 2),
                            metadata={"required_tools": step.required_tools or []},
                        )
                    )
                except Exception as exc:
                    log.info("Task-aware stack routing unavailable; using configured profile: %s", exc)
                    await session.rollback()
                    stack = await session.get(StackRun, stack_run_id)
                    step = await session.get(StackStepRun, step_db_id)
                    if not stack or not step:
                        return
                    step.status = "running" if step.retry_count == 0 else "retrying"
                    step.started_at = step.started_at or datetime.now(timezone.utc)
                    stack.current_step_id = step.step_id
                if routing:
                    model = routing.selected.model_id
                    route_payload = routing.payload
                    decision_id = str(routing.decision.id) if routing.decision else None
                else:
                    model = str((step.metadata_json or {}).get("model_hint") or stack.model_profile)
                    route_payload = {
                        "active_profile": stack.model_profile,
                        "selected_provider": "legacy",
                        "reason": "Legacy configured profile used because the model registry is unavailable.",
                    }
                    decision_id = None
                step.model_used = model
                step_metadata = dict(step.metadata_json or {})
                step_metadata["routing_decision"] = route_payload
                step.metadata_json = step_metadata
                usage = list(stack.model_usage or [])
                usage.append(
                    {
                        "step_id": step.step_id,
                        "model_profile": route_payload["active_profile"],
                        "model": model,
                        "provider": route_payload["selected_provider"],
                        "reason": route_payload["reason"],
                        "routing_decision_id": decision_id,
                        "selected_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
                stack.model_usage = usage
                step.input_json = previous_output or (stack.metadata_json or {}).get("input_payload", {})
                await session.commit()
                await _audit(
                    "stack.step.started" if step.retry_count == 0 else "stack.step.retrying",
                    f"Stack step '{step.name}' started",
                    stack.id,
                    detail={"step_id": step.step_id, "retry_count": step.retry_count},
                )
                await _audit(
                    "stack.context.compacted",
                    f"Operational context prepared for '{step.name}'",
                    stack.id,
                    detail={"step_id": step.step_id, "context": context},
                )
                await _audit(
                    "stack.model.selected",
                    f"Model '{model}' selected for '{step.name}'",
                    stack.id,
                    model_used=model,
                    detail={"step_id": step.step_id, **route_payload},
                )
                flow_id = step.flow_id
                step_id = step.id
                governance = {
                    "posture_level": stack.posture,
                    "allowed_tools": stack.allowed_tools,
                    "model_profile": route_payload["active_profile"],
                    "selected_model": model,
                    "routing_decision_id": decision_id,
                    "stack_run_id": str(stack.id),
                    "stack_step_id": step.step_id,
                }
                input_payload = {"input": step.input_json, "objective": stack.objective, "context": context}

            flow_run_id = await start_flow_run(
                flow_id,
                trigger_type="stack_orchestrator",
                input_payload=input_payload,
                governance_context=governance,
            )
            async with async_session_factory() as session:
                step = await session.get(StackStepRun, step_id)
                stack = await session.get(StackRun, stack_run_id)
                if not step or not stack or stack.status != "running":
                    return
                step.flow_run_id = flow_run_id
                stack.root_run_id = stack.root_run_id or flow_run_id
                await session.commit()

            flow_run = await _wait_for_flow(flow_run_id, stack_run_id)
            if flow_run is None:
                return

            async with async_session_factory() as session:
                stack = await session.get(StackRun, stack_run_id)
                step = await session.get(StackStepRun, step_id)
                if not stack or not step or stack.status != "running":
                    return
                flow_run = await session.get(AgentFlowRun, flow_run_id)
                if not flow_run:
                    await _fail_stack(session, stack, "Agent Flow result disappeared.")
                    return
                artifacts = await StackArtifactService.capture(session, stack, step, flow_run)
                verification = await StackVerificationService.verify(session, stack, step, flow_run)
                passed = flow_run.status == "completed" and (
                    not step.requires_verification or verification.status == "passed"
                )
                try:
                    from shogun.services.active_skill_service import SkillActivationService

                    outcome_service = SkillActivationService(session)
                    for active_id in (step.metadata_json or {}).get("active_skill_run_ids", []):
                        await outcome_service.outcome(
                            uuid.UUID(active_id), "success" if passed else "failed",
                            verification.observed_result,
                        )
                except Exception as exc:
                    log.warning("Stack skill outcome recording skipped: %s", exc)
                if passed:
                    checkpoint = None
                    step.status = "completed"
                    step.completed_at = datetime.now(timezone.utc)
                    step.output_json = {
                        "output": flow_run.output_payload or flow_run.result_summary or {},
                        "artifacts": [str(item.id) for item in artifacts],
                        "flow_run_id": str(flow_run.id),
                    }
                    previous_output = step.output_json["output"]
                    StackStateService.refresh_lists(stack, await StackStateService.steps(session, stack.id))
                    if stack.checkpoint_frequency in {"after_each_step", "after_each_subflow"}:
                        steps = await StackStateService.steps(session, stack.id)
                        checkpoint = await StackCheckpointService.create(session, stack, step, steps)
                    await session.commit()
                    await _audit_step_evidence(stack, step, artifacts, verification, checkpoint)
                    await _audit(
                        "stack.step.completed",
                        f"Stack step '{step.name}' completed",
                        stack.id,
                        detail={"step_id": step.step_id, "flow_run_id": str(flow_run.id)},
                    )
                    continue

                category = (
                    "verification_failure"
                    if flow_run.status == "completed" and verification.status == "failed"
                    else StackRetryService.failure_category(flow_run)
                )
                step.error_json = {
                    "message": flow_run.error_message or verification.observed_result or "Step verification failed",
                    "category": category,
                    "verification_id": str(verification.id),
                }
                if step.retry_count < step.max_retries and stack.failure_policy in {"retry", "pause"}:
                    step.retry_count += 1
                    step.status = "pending"
                    step.flow_run_id = None
                    await session.commit()
                    await _audit_step_evidence(stack, step, artifacts, verification)
                    await _audit(
                        "stack.step.retrying",
                        f"Retrying '{step.name}' after {category}",
                        stack.id,
                        result="failure",
                        severity="warn",
                        detail={"step_id": step.step_id, "retry_count": step.retry_count, "category": category},
                    )
                    continue

                step.status = "failed"
                step.completed_at = datetime.now(timezone.utc)
                steps = await StackStateService.steps(session, stack.id)
                StackStateService.refresh_lists(stack, steps)
                if stack.failure_policy == "continue_with_error":
                    checkpoint = await StackCheckpointService.create(session, stack, step, steps)
                    await session.commit()
                    await _audit_step_evidence(stack, step, artifacts, verification, checkpoint)
                    continue
                stack.status = "paused" if stack.failure_policy == "pause" else "failed"
                if stack.status == "failed":
                    stack.completed_at = datetime.now(timezone.utc)
                await session.commit()
                await _audit_step_evidence(stack, step, artifacts, verification)
                await _audit(
                    "stack.step.failed",
                    f"Stack step '{step.name}' failed",
                    stack.id,
                    result="failure",
                    severity="error",
                    detail={"step_id": step.step_id, "category": category},
                )
                await _audit(
                    "stack.orchestrator.paused" if stack.status == "paused" else "stack.orchestrator.failed",
                    f"Stack {stack.status} after step failure",
                    stack.id,
                    result="failure",
                    severity="warn" if stack.status == "paused" else "error",
                )
                return
    except asyncio.CancelledError:
        return
    except Exception as exc:
        log.exception("Stack Orchestrator run %s failed", stack_run_id)
        async with async_session_factory() as session:
            stack = await session.get(StackRun, stack_run_id)
            if stack and stack.status == "running":
                await _fail_stack(session, stack, str(exc))


async def _wait_for_flow(flow_run_id: uuid.UUID, stack_run_id: uuid.UUID) -> AgentFlowRun | None:
    while True:
        await asyncio.sleep(settings.stack_orchestrator_poll_interval_seconds)
        async with async_session_factory() as session:
            stack = await session.get(StackRun, stack_run_id)
            if not stack or stack.status != "running":
                return None
            run = await session.get(AgentFlowRun, flow_run_id)
            if run and run.status in _TERMINAL:
                return run


async def _finalize(session: AsyncSession, stack: StackRun, steps: list[StackStepRun]) -> None:
    if stack.artifact_policy == "retain_final_only":
        final_step = next((step for step in reversed(steps) if step.status == "completed"), None)
        if final_step:
            await session.execute(
                delete(StackArtifact).where(
                    StackArtifact.stack_run_id == stack.id,
                    StackArtifact.step_run_id != final_step.id,
                )
            )
    artifacts = await session.execute(select(StackArtifact).where(StackArtifact.stack_run_id == stack.id))
    verifications = await session.execute(select(StackVerification).where(StackVerification.stack_run_id == stack.id))
    artifact_rows = list(artifacts.scalars().all())
    verification_rows = list(verifications.scalars().all())
    failed = [step for step in steps if step.status in {"failed", "blocked", "cancelled"}]
    required_unverified = [
        step for step in steps if step.requires_verification and step.verification_status != "passed"
    ]
    if failed and stack.failure_policy == "continue_with_error":
        stack.status = "completed_with_errors"
    elif failed or required_unverified:
        stack.status = "failed"
    else:
        stack.status = "completed"
    stack.completed_at = datetime.now(timezone.utc)
    stack.current_step_id = None
    StackStateService.refresh_lists(stack, steps)
    stack.final_summary = {
        "objective": stack.objective,
        "final_status": stack.status,
        "steps_completed": [step.name for step in steps if step.status == "completed"],
        "steps_failed": [{"name": step.name, "error": step.error_json} for step in failed],
        "unverified_steps": [step.name for step in required_unverified],
        "files_changed": [item.path for item in artifact_rows if item.path],
        "artifacts_created": [
            {"id": str(item.id), "type": item.artifact_type, "summary": item.summary} for item in artifact_rows
        ],
        "tests_and_verifications": [
            {"step_run_id": str(item.step_run_id), "status": item.status, "observed": item.observed_result}
            for item in verification_rows
        ],
        "approvals_requested": stack.approval_events or [],
        "models_used": stack.model_usage or [],
        "known_issues": [step.error_json for step in failed]
        + [
            {"step": step.name, "issue": "required independent verification did not pass"}
            for step in required_unverified
        ],
        "recommended_next_steps": ["Review artifacts and verification evidence before publishing changes."],
        "commit_message_suggestion": f"feat: complete {stack.objective[:72]}",
        "pr_summary": f"Stack Orchestrator completed {len(stack.completed_steps)} governed steps.",
        "risk_notes": f"Executed under {stack.posture.upper()} posture with inherited tool permissions.",
    }
    await session.commit()
    await _audit(
        "stack.orchestrator.completed" if stack.status == "completed" else "stack.orchestrator.failed",
        f"Stack Orchestrator run {stack.status}",
        stack.id,
        result="success" if stack.status == "completed" else "failure",
        severity="info" if stack.status == "completed" else "error",
    )


async def _fail_stack(session: AsyncSession, stack: StackRun, message: str) -> None:
    stack.status = "failed"
    stack.completed_at = datetime.now(timezone.utc)
    metadata = dict(stack.metadata_json or {})
    metadata["last_error"] = message
    stack.metadata_json = metadata
    await session.commit()
    await _audit(
        "stack.orchestrator.failed",
        "Stack Orchestrator execution failed",
        stack.id,
        result="failure",
        severity="error",
        detail={"error": message},
    )


async def recover_interrupted_stack_runs() -> int:
    """Rehydrate durable running stacks after an application restart."""
    recovered: list[uuid.UUID] = []
    async with async_session_factory() as session:
        rows = await session.execute(select(StackRun).where(StackRun.status == "running"))
        service = StackOrchestratorService(session)
        for stack in rows.scalars().all():
            if str(stack.id) in _active_stack_runs:
                continue
            await service._prepare_recovery(stack)
            recovered.append(stack.id)
        await session.commit()
    for stack_id in recovered:
        StackOrchestratorService._launch(stack_id)
        await _audit("stack.orchestrator.recovered", "Stack run rehydrated after application restart", stack_id)
    return len(recovered)
