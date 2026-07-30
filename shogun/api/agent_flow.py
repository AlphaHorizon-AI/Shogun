"""Agent Flow API routes — CRUD, graph operations, and execution for visual workflows."""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path as _Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.api.deps import get_agent_flow_service, get_db
from shogun.schemas.agent_flow import (
    AgentFlowBulkDeleteRequest,
    AgentFlowCreate,
    AgentFlowGraphSave,
    AgentFlowListItem,
    AgentFlowResponse,
    AgentFlowRunCreate,
    AgentFlowRunListItem,
    AgentFlowRunResponse,
    AgentFlowUpdate,
    FlowStackCreate,
    FlowStackComposeEdge,
    FlowStackComposeNode,
    FlowStackComposeRequest,
    FlowStackTemplateInstantiate,
    SaveFlowTemplateRequest,
    SubflowValidationRequest,
)
from shogun.schemas.common import ApiResponse
from shogun.services.agent_flow_service import AgentFlowService

router = APIRouter(prefix="/agent-flows", tags=["Agent Flows"])

# ── List all flows ───────────────────────────────────────────


@router.get("", response_model=ApiResponse)
async def list_flows(
    status: str | None = None,
    search: str | None = None,
    page: int = 1,
    per_page: int = 50,
    svc: AgentFlowService = Depends(get_agent_flow_service),
):
    """List all Agent Flows (lightweight, without nodes/edges)."""
    offset = max(0, (page - 1) * per_page)
    records, total = await svc.list_flows(
        status=status,
        search=search,
        offset=offset,
        limit=per_page,
    )
    return ApiResponse(
        data=[AgentFlowListItem.model_validate(r) for r in records],
        meta={"total": total, "page": page, "per_page": per_page},
    )


# ── Create a new flow ───────────────────────────────────────


@router.post("", response_model=ApiResponse, status_code=201)
async def create_flow(
    body: AgentFlowCreate,
    svc: AgentFlowService = Depends(get_agent_flow_service),
):
    """Create a new Agent Flow."""
    data = body.model_dump()
    if data.get("trigger_type") == "scheduled":
        data["schedule_config"] = _normalized_schedule_config(data.get("schedule_config") or {})
        data["status"] = "active"
    record = await svc.create(**data)
    try:
        await _sync_live_flow_schedule(record)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"AgentFlow schedule could not be synchronized: {exc}",
        ) from exc
    return ApiResponse(data=AgentFlowResponse.model_validate(record))


@router.post("/flow-stacks", response_model=ApiResponse, status_code=201)
async def create_flow_stack(
    body: FlowStackCreate,
    svc: AgentFlowService = Depends(get_agent_flow_service),
    db: AsyncSession = Depends(get_db),
):
    """Generate a normal AgentFlow containing sequential Subflow nodes."""
    from shogun.db.models.agent_flow import AgentFlow

    result = await db.execute(
        select(AgentFlow).where(
            AgentFlow.id.in_(body.flow_ids),
            AgentFlow.is_deleted.is_(False),
        )
    )
    selected = {flow.id: flow for flow in result.scalars().all()}
    missing = [str(flow_id) for flow_id in body.flow_ids if flow_id not in selected]
    blocked = [
        selected[flow_id].name
        for flow_id in body.flow_ids
        if flow_id in selected and not selected[flow_id].allow_as_subflow
    ]
    if missing:
        raise HTTPException(404, detail=f"Flow Stack contains missing flows: {', '.join(missing)}")
    if blocked:
        raise HTTPException(422, detail=f"These flows cannot be used as subflows: {', '.join(blocked)}")
    from shogun.config import settings
    if body.version_mode == "latest" and not settings.flow_stacking_allow_latest_version:
        raise HTTPException(422, detail="Latest-version Flow Stack references are disabled")

    stack = await svc.create(
        name=body.name,
        description=body.description or "Flow Stack generated from reusable Shogun flows.",
        trigger_type="manual",
        schedule_config={},
        flow_type="stack",
        input_contract={},
        output_contract={},
        risk_tier=max(
            (selected[fid].risk_tier for fid in body.flow_ids),
            key=lambda risk: {"low": 0, "medium": 1, "high": 2}.get(risk, 0),
        ),
        default_timeout_seconds=body.timeout_seconds,
        allow_as_subflow=True,
        required_tools=sorted({tool for fid in body.flow_ids for tool in (selected[fid].required_tools or [])}),
    )
    nodes: list[dict] = []
    edges: list[dict] = []
    input_id = str(uuid.uuid4())
    nodes.append({
        "id": input_id,
        "node_type": "input",
        "label": "Stack Input",
        "position_x": 0,
        "position_y": 120,
        "config": {"input_type": "subflow", "description": "Input passed into the Flow Stack"},
    })
    previous_id = input_id
    for index, flow_id in enumerate(body.flow_ids, start=1):
        child = selected[flow_id]
        node_id = str(uuid.uuid4())
        nodes.append({
            "id": node_id,
            "node_type": "subflow",
            "label": child.name,
            "position_x": index * 280,
            "position_y": 120,
            "config": {
                "child_flow_id": str(child.id),
                "child_flow_version_mode": body.version_mode,
                "child_flow_version": child.version if body.version_mode == "locked" else None,
                "execution_mode": "sequential",
                "timeout_seconds": body.timeout_seconds,
                "on_failure": "fail_parent",
                "input_mapping": {},
                "output_mapping": {},
            },
        })
        edges.append({"source_node_id": previous_id, "target_node_id": node_id})
        previous_id = node_id
    output_id = str(uuid.uuid4())
    nodes.append({
        "id": output_id,
        "node_type": "output",
        "label": "Stack Output",
        "position_x": (len(body.flow_ids) + 1) * 280,
        "position_y": 120,
        "config": {"output_type": "artifact", "format": "json"},
    })
    edges.append({"source_node_id": previous_id, "target_node_id": output_id})
    saved = await svc.save_flow_graph(stack.id, nodes, edges, {"x": 20, "y": 80, "zoom": 0.8})
    return ApiResponse(data=AgentFlowResponse.model_validate(saved), meta={"message": "Flow Stack created"})


# ═══════════════════════════════════════════════════════════════
# TEMPLATE GALLERY ENDPOINTS (must be before /{flow_id} routes)
# ═══════════════════════════════════════════════════════════════

_TEMPLATE_CACHE: dict | None = None
_log = logging.getLogger(__name__)


async def _sync_live_flow_schedule(flow) -> dict:
    """Keep one APScheduler job aligned with the persisted AgentFlow state."""
    from shogun.scheduler import (
        _make_flow_job_id,
        deregister_flow_schedule,
        register_flow_schedule,
        scheduler_job_snapshot,
    )

    if flow.trigger_type == "scheduled" and flow.status == "active" and not flow.is_deleted:
        snapshot = await register_flow_schedule(flow)
        if not snapshot["scheduler_registered"]:
            raise RuntimeError(
                f"AgentFlow schedule {_make_flow_job_id(flow.id)} was not registered"
            )
        return snapshot
    else:
        await deregister_flow_schedule(flow.id)
        return scheduler_job_snapshot(_make_flow_job_id(flow.id))


def _normalized_schedule_config(config: dict | None) -> dict:
    """Return a complete schedule_config for Agent Flow cron registration."""
    normalized = dict(config or {})
    frequency = normalized.get("frequency") or normalized.get("schedule_frequency") or "nightly"
    normalized["frequency"] = frequency
    if frequency == "hourly":
        normalized["minute_offset"] = int(normalized.get("minute_offset") or normalized.get("schedule_minute_offset") or 0)
    else:
        normalized["schedule_time"] = normalized.get("schedule_time") or "07:00"
    if frequency == "weekly":
        normalized["schedule_days"] = normalized.get("schedule_days") or ["mon", "tue", "wed", "thu", "fri"]
    if frequency == "monthly":
        normalized["schedule_day"] = int(normalized.get("schedule_day") or 1)
    return normalized


def _load_templates() -> dict:
    """Load and cache the template catalog from JSON."""
    global _TEMPLATE_CACHE
    if _TEMPLATE_CACHE is not None:
        return _TEMPLATE_CACHE
    package_root = _Path(__file__).resolve().parent.parent
    candidates = (
        package_root / "resources" / "flow_templates.json",
        # Compatibility with installations made before build 38.
        package_root / "data" / "flow_templates.json",
    )
    tpl_path = next((path for path in candidates if path.is_file()), None)
    if tpl_path is None:
        searched = ", ".join(str(path) for path in candidates)
        _log.error("AgentFlow template catalog is missing; searched: %s", searched)
        raise RuntimeError(
            "The built-in AgentFlow template catalog is missing. "
            "Run Shogun Repair/Update, then restart Shogun."
        )

    try:
        _TEMPLATE_CACHE = json.loads(tpl_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _log.exception("Could not load AgentFlow templates from %s", tpl_path)
        raise RuntimeError(
            "The built-in AgentFlow template catalog could not be loaded. "
            "Run Shogun Repair/Update, then restart Shogun."
        ) from exc
    return _TEMPLATE_CACHE


def _built_in_template(template_id: str) -> dict | None:
    return next(
        (item for item in _load_templates().get("templates", []) if item["id"] == template_id),
        None,
    )


def _flow_stack_templates() -> list[dict]:
    """Build 208 long-horizon programs, including 33 purpose-built coding stacks."""
    by_id = {item["id"]: item for item in _load_templates().get("templates", [])}
    role_pools = {
        "intake": ["project-status", "campaign-brief", "meeting-minutes", "risk-assessment", "process-docs", "customer-persona"],
        "intelligence": ["competitor-analysis", "market-research", "regulatory-monitor", "supplier-research", "tech-trends", "brand-monitor"],
        "analysis": ["adv-anomaly-detect", "adv-quarterly-forecast", "sales-kpi", "data-quality", "adv-pricing-intel", "survey-analysis"],
        "governance": ["adv-compliance-check", "adv-risk-register", "contract-review", "gdpr-checklist", "adv-audit-prep", "quality-audit"],
        "planning": ["adv-strategic-plan", "adv-gtm-plan", "adv-workforce-plan", "onboarding-plan", "adv-business-case", "content-calendar"],
        "production": ["whitepaper", "adv-content-suite", "training-material", "process-docs", "adv-localization", "adv-ops-dashboard"],
        "verification": ["quality-audit", "data-quality", "doc-compare", "adv-audit-prep", "adv-compliance-check", "adv-training-eval"],
        "communication": ["adv-report-distribution", "internal-announcement", "newsletter", "ops-brief-channel-broadcast", "weekly-status", "press-release"],
    }
    archetypes = [
        ("Continuous Intelligence", "Competitive Signal Watchtower", "maintain a continuously refreshed view of competitors, market shifts, and response options"),
        ("Continuous Intelligence", "Regulatory Radar", "detect regulatory change early, assess exposure, and keep an evidence-backed response plan current"),
        ("Continuous Intelligence", "Technology Horizon Scan", "track emerging technology, evaluate relevance, and turn signals into governed experiments"),
        ("Strategy & Transformation", "Market Entry Program", "take a market opportunity from evidence gathering through entry plan, controls, and executive decision"),
        ("Strategy & Transformation", "Operating Model Transformation", "diagnose operational friction, design the target model, and govern a phased transformation"),
        ("Strategy & Transformation", "Strategic Portfolio Review", "continuously evaluate initiatives, dependencies, risk, value, and funding recommendations"),
        ("Product & Innovation", "Product Discovery Program", "move from customer evidence and market intelligence to a verified product opportunity brief"),
        ("Product & Innovation", "Launch Readiness Command", "coordinate launch workstreams, surface readiness gaps, verify assets, and package the go-live decision"),
        ("Product & Innovation", "Innovation Pipeline", "collect ideas, evaluate strategic fit, govern experiments, and publish investment recommendations"),
        ("Growth & Brand", "Integrated Go-to-Market Program", "coordinate research, positioning, content, channels, measurement, and optimization as one program"),
        ("Growth & Brand", "Brand Health Command", "monitor brand signals, investigate changes, plan interventions, and verify market-facing consistency"),
        ("Growth & Brand", "Content Growth Engine", "operate a research-led content system with parallel production, compliance, localization, and distribution"),
        ("Customer Operations", "Customer Onboarding Journey", "coordinate onboarding knowledge, communications, success signals, risk checks, and follow-through"),
        ("Customer Operations", "Retention Recovery Program", "identify churn signals, investigate causes, design interventions, and track verified recovery actions"),
        ("Customer Operations", "Voice of Customer Council", "turn customer feedback into recurring analysis, governed priorities, action plans, and executive reporting"),
        ("Data & Executive Operations", "Executive Performance Cycle", "run a recurring evidence-to-decision cycle across KPIs, anomalies, risks, and executive actions"),
        ("Data & Executive Operations", "Forecast and Scenario Program", "maintain forecasts, challenge assumptions, model scenarios, and package decision-ready options"),
        ("Data & Executive Operations", "Data Quality Remediation", "discover quality failures, assess impact, coordinate remediation, verify fixes, and report controls"),
        ("Risk & Compliance", "Enterprise Risk Assurance", "maintain a living risk picture with evidence, mitigation ownership, verification, and escalation"),
        ("Risk & Compliance", "Contract Lifecycle Command", "coordinate drafting, review, obligation tracking, compliance verification, and stakeholder communication"),
        ("Risk & Compliance", "Audit Readiness Program", "continuously assemble evidence, test controls, close gaps, and maintain an audit-ready package"),
        ("People & Capability", "Workforce Planning Cycle", "connect workforce evidence, skills gaps, operating priorities, risk, and an approved capability plan"),
        ("People & Capability", "Talent Acquisition Program", "run a governed hiring pipeline from role design through screening, interviews, and onboarding readiness"),
        ("People & Capability", "Learning Academy Operation", "design, produce, validate, distribute, and evaluate an evolving learning program"),
        ("Incident & Resilience", "Incident Command System", "coordinate triage, investigation, stakeholder updates, recovery, verification, and final incident reporting"),
        ("Incident & Resilience", "Root Cause and Prevention Program", "move from evidence collection to root cause, corrective actions, verification, and organizational learning"),
        ("Incident & Resilience", "Supplier Continuity Watch", "monitor supplier risk, test alternatives, maintain mitigations, and escalate continuity decisions"),
        ("Knowledge & Publishing", "Policy Publishing System", "research, draft, review, localize, publish, and maintain governed organizational policy"),
        ("Knowledge & Publishing", "Research-to-Whitepaper Program", "turn broad research into a verified, compliant, multi-format publication and distribution plan"),
        ("Knowledge & Publishing", "Multilingual Knowledge Hub", "maintain source knowledge, translations, quality controls, updates, and audience distribution"),
    ]
    contexts = [
        ("Enterprise", 1440, 120), ("Regional", 960, 100), ("Product", 720, 80),
        ("Customer", 720, 80), ("Regulated", 1440, 150), ("Transformation", 1440, 150),
    ]
    phase_names = [
        "Frame objective and operating context", "Run intelligence workstream", "Run evidence and analysis workstream",
        "Run governance and risk workstream", "Synthesize the program plan", "Produce operational artifacts",
        "Verify outcomes and controls", "Publish decision package and next checkpoint",
    ]
    positions = [(340, 220), (650, 20), (650, 220), (650, 420), (970, 220), (1290, 80), (1290, 360), (1610, 220)]
    topology = [(0, 1), (0, 2), (0, 3), (1, 4), (2, 4), (3, 4), (4, 5), (4, 6), (5, 7), (6, 7)]
    recipes: list[dict] = []
    role_names = list(role_pools)
    for archetype_index, (category, program_name, purpose) in enumerate(archetypes):
        for context_index, (context, runtime_minutes, iterations) in enumerate(contexts):
            members = []
            for role_index, role in enumerate(role_names):
                pool = [item for item in role_pools[role] if item in by_id]
                members.append(pool[(archetype_index * 2 + context_index + role_index) % len(pool)])
            node_ids = [f"phase-{index + 1}" for index in range(len(members))]
            objective = f"Operate the {context.lower()} {program_name.lower()} to {purpose}."
            recipes.append({
                "id": f"stack-program-{archetype_index + 1:02d}-{context.lower()}",
                "name": f"{context} {program_name}",
                "description": f"A long-running operating program that {purpose}. Three parallel workstreams converge into planning, production, independent verification, and a checkpointed decision package.",
                "category": category, "icon": "layers", "difficulty": "long-running",
                "duration_label": "8–24 hours, resumable", "flow_template_ids": members,
                "flow_count": len(members), "source": "built-in",
                "builder_nodes": [{
                    "id": node_ids[index], "label": phase_names[index], "template_id": template_id,
                    "position_x": positions[index][0], "position_y": positions[index][1],
                } for index, template_id in enumerate(members)],
                "builder_edges": [{"source": node_ids[source], "target": node_ids[target]} for source, target in topology],
                "orchestrator_config": {
                    "mode": "template", "objective": objective,
                    "success_criteria": [
                        "All parallel workstreams complete with traceable artifacts",
                        "Verification passes before the decision package is published",
                        "The final package identifies owners, risks, decisions, and the next checkpoint",
                    ],
                    "model_routing_profile": "balanced", "max_runtime_minutes": runtime_minutes,
                    "max_iterations": iterations, "max_retry_attempts_per_step": 3,
                    "timeout_seconds": 7200,
                    "checkpoint_frequency": "after_each_subflow", "context_compaction": "enabled",
                    "verification_required": True, "approval_policy": "step_based",
                    "artifact_policy": "retain_all", "failure_policy": "retry",
                },
            })
            if len(recipes) == 175:
                break
        if len(recipes) == 175:
            break
    # One original coding stack per Coding AgentFlow. Each program composes eight
    # distinct coding flows so the stack is executable from the same built-in catalog.
    coding_programs = [item for item in by_id.values() if item.get("category") == "Coding"]
    coding_ids = [item["id"] for item in coding_programs]
    coding_labels = ["Frame requirement and repository scope", "Inspect architecture and dependencies", "Analyze implementation risks",
                     "Confirm governance and change boundaries", "Create implementation plan", "Apply reversible code patches",
                     "Run tests, build, and diagnostics", "Produce verified review package"]
    for index, template in enumerate(coding_programs):
        slug = template["id"].removeprefix("coding-")
        name = f"{template['name']} Stack"
        objective = template["description"].rstrip(".").lower()
        coding_members = [coding_ids[(index + offset) % len(coding_ids)] for offset in range(8)]
        node_ids = [f"ide-{slug}-{i+1}" for i in range(len(coding_members))]
        recipes.append({
            "id": template["id"], "name": name,
            "description": f"A governed, resumable coding Agent Stack to {objective}.",
            "category": "Coding Agent Stacks", "icon": "code", "difficulty": "long-running",
            "duration_label": "1–12 hours, resumable", "flow_template_ids": coding_members,
            "flow_count": len(coding_members), "source": "built-in",
            "builder_nodes": [{"id": node_id, "label": coding_labels[i],
                               "template_id": template_id, "position_x": positions[i][0], "position_y": positions[i][1]}
                              for i, (node_id, template_id) in enumerate(zip(node_ids, coding_members))],
            "builder_edges": [{"source": node_ids[source], "target": node_ids[target]} for source, target in topology],
            "orchestrator_config": {"mode": "template", "objective": objective,
                "success_criteria": ["Required implementation exists", "Tests/build complete successfully", "Diagnostics are clear or explained", "Final diff and review package are produced"],
                "required_tools": ["ide_list_workspaces", "ide_list_files", "ide_read_file", "ide_search", "ide_apply_patch", "ide_run_task", "ide_memory_search", "ide_memory_store", "ide_memory_reinforce"],
                "model_routing_profile": "balanced", "max_runtime_minutes": 720, "max_iterations": 100,
                "max_retry_attempts_per_step": 3, "timeout_seconds": 7200, "checkpoint_frequency": "after_each_subflow",
                "context_compaction": "enabled", "verification_required": True, "approval_policy": "step_based",
                "artifact_policy": "retain_all", "failure_policy": "retry"},
        })
    return recipes


async def _instantiate_flow_template(
    template_id: str, svc: AgentFlowService, name: str | None = None,
):
    """Instantiate either a built-in catalog template or a saved custom template."""
    if template_id.startswith("custom:"):
        try:
            source_id = uuid.UUID(template_id.split(":", 1)[1])
        except ValueError as exc:
            raise HTTPException(404, f"Template not found: {template_id}") from exc
        source = await svc.get_flow_full(source_id)
        if not source or not source.is_template:
            raise HTTPException(404, f"Template not found: {template_id}")
        flow = await svc.duplicate_flow(source_id)
        if not flow:
            raise HTTPException(404, f"Template not found: {template_id}")
        flow.name = name or flow.name.removesuffix(" (Copy)")
        flow.is_template = False
        flow.template_category = None
        flow.template_source = None
        flow.template_config = {}
        await svc.session.flush()
        return await svc.get_flow_full(flow.id)

    template = _built_in_template(template_id)
    if not template:
        raise HTTPException(404, f"Template not found: {template_id}")
    trigger_type = template.get("trigger_type", "manual")
    is_coding_template = template.get("category") == "Coding"
    flow = await svc.create(
        name=name or template["name"],
        description=template.get("description", ""),
        trigger_type=trigger_type,
        schedule_config=_normalized_schedule_config(template.get("schedule_config", {}))
            if trigger_type == "scheduled" else template.get("schedule_config", {}),
        status="active" if trigger_type == "scheduled" else "draft",
        risk_tier="high" if is_coding_template else "low",
        required_tools=(
            [
                "ide_list_workspaces", "ide_list_files", "ide_read_file", "ide_search",
                "ide_apply_patch", "ide_run_task", "ide_memory_search", "ide_memory_store",
            ]
            if is_coding_template else []
        ),
    )
    saved = await svc.save_flow_graph(
        flow.id, template.get("nodes", []), template.get("edges", []),
        {"x": 50, "y": 100, "zoom": 0.85},
    )
    return saved or flow


@router.get("/templates", response_model=ApiResponse)
async def list_templates(svc: AgentFlowService = Depends(get_agent_flow_service)):
    """Return the full template catalog (categories + lightweight template list)."""
    try:
        catalog = _load_templates()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    # Return lightweight version (without full node/edge data)
    lightweight = []
    for t in catalog.get("templates", []):
        lightweight.append({
            "id": t["id"],
            "name": t["name"],
            "description": t["description"],
            "category": t["category"],
            "icon": t["icon"],
            "difficulty": t["difficulty"],
            "trigger_type": t["trigger_type"],
            "node_count": t.get("node_count", len(t.get("nodes", []))),
        })
    custom = await svc.list_saved_templates(flow_type="standard")
    for item in custom:
        lightweight.append({
            "id": f"custom:{item.id}", "name": item.name,
            "description": item.description or "Saved custom AgentFlow template",
            "category": item.template_category or "My Templates", "icon": "bookmark",
            "difficulty": "custom", "trigger_type": item.trigger_type,
            "node_count": len(item.nodes), "source": "custom",
        })
    categories = list(catalog.get("categories", []))
    if custom:
        categories.append({"name": "My Templates", "count": len(custom)})
    return ApiResponse(data={
        "total": len(lightweight),
        "categories": categories,
        "templates": lightweight,
    })


@router.get("/flow-stack-templates", response_model=ApiResponse)
async def list_flow_stack_templates(svc: AgentFlowService = Depends(get_agent_flow_service)):
    built_in = _flow_stack_templates()
    custom = await svc.list_saved_templates(flow_type="stack")
    custom_items = []
    for item in custom:
        subflow_nodes = [node for node in item.nodes if node.node_type == "subflow"]
        subflow_ids = {str(node.id) for node in subflow_nodes}
        custom_items.append({
            "id": f"custom:{item.id}", "name": item.name,
            "description": item.description or "Saved custom Flow Stack template",
            "category": item.template_category or "My Templates", "icon": "bookmark",
            "difficulty": "custom", "flow_count": len(subflow_nodes), "source": "custom",
            "builder_nodes": [{
                "id": str(node.id), "label": node.label,
                "flow_id": str((node.config or {}).get("child_flow_id")),
                "position_x": node.position_x, "position_y": node.position_y,
            } for node in subflow_nodes],
            "builder_edges": [{
                "source": str(edge.source_node_id), "target": str(edge.target_node_id),
            } for edge in item.edges
                if str(edge.source_node_id) in subflow_ids and str(edge.target_node_id) in subflow_ids],
        })
    categories = sorted({item["category"] for item in [*built_in, *custom_items]})
    return ApiResponse(data={
        "total": len(built_in) + len(custom_items), "built_in_total": 208,
        "categories": [{"name": name, "count": sum(i["category"] == name for i in [*built_in, *custom_items])} for name in categories],
        "templates": [*built_in, *custom_items],
    })


@router.get("/templates/{template_id}", response_model=ApiResponse)
async def get_template_detail(
    template_id: str,
    svc: AgentFlowService = Depends(get_agent_flow_service),
):
    """Return the complete graph behind a built-in or user-saved AgentFlow template."""
    if template_id.startswith("custom:"):
        try:
            flow_id = uuid.UUID(template_id.split(":", 1)[1])
        except ValueError as exc:
            raise HTTPException(404, f"Template not found: {template_id}") from exc
        flow = await svc.get_flow_full(flow_id)
        if not flow or not flow.is_template:
            raise HTTPException(404, f"Template not found: {template_id}")
        return ApiResponse(data={
            "id": template_id,
            "name": flow.name,
            "description": flow.description or "Saved custom AgentFlow template",
            "category": flow.template_category or "My Templates",
            "trigger_type": flow.trigger_type,
            "nodes": [{
                "id": str(node.id), "node_type": node.node_type, "label": node.label,
                "position_x": node.position_x, "position_y": node.position_y,
                "config": node.config or {},
            } for node in flow.nodes],
            "edges": [{
                "id": str(edge.id), "source_node_id": str(edge.source_node_id),
                "target_node_id": str(edge.target_node_id), "label": edge.label,
                "edge_type": edge.edge_type, "config": edge.config or {},
            } for edge in flow.edges],
            "source": "custom",
        })
    template = _built_in_template(template_id)
    if not template:
        raise HTTPException(404, f"Template not found: {template_id}")
    return ApiResponse(data=template)


@router.post("/flow-stacks/from-template", response_model=ApiResponse, status_code=201)
async def create_stack_from_template(
    body: FlowStackTemplateInstantiate,
    svc: AgentFlowService = Depends(get_agent_flow_service),
):
    if body.template_id.startswith("custom:"):
        stack = await _instantiate_flow_template(body.template_id, svc, body.name)
        return ApiResponse(data=AgentFlowResponse.model_validate(stack))
    recipe = next((item for item in _flow_stack_templates() if item["id"] == body.template_id), None)
    if not recipe:
        raise HTTPException(404, f"Flow Stack template not found: {body.template_id}")
    stack_body = FlowStackComposeRequest(
        name=body.name or recipe["name"], description=recipe["description"],
        category=recipe["category"],
        nodes=[FlowStackComposeNode(
            id=item["id"], template_id=item["template_id"], label=item["label"],
            position_x=item["position_x"], position_y=item["position_y"],
        ) for item in recipe["builder_nodes"]],
        edges=[FlowStackComposeEdge(source=item["source"], target=item["target"])
               for item in recipe["builder_edges"]],
        orchestrator_config=recipe["orchestrator_config"],
    )
    return await compose_flow_stack(stack_body, svc)


@router.post("/flow-stacks/compose", response_model=ApiResponse, status_code=201)
async def compose_flow_stack(
    body: FlowStackComposeRequest,
    svc: AgentFlowService = Depends(get_agent_flow_service),
):
    """Persist the connected canvas as an executable stack with embedded orchestrator policy."""
    ids = {item.id for item in body.nodes}
    if len(ids) != len(body.nodes):
        raise HTTPException(422, "Every canvas node must have a unique id")
    outgoing = {item.id: [] for item in body.nodes}
    incoming = {item.id: 0 for item in body.nodes}
    for edge in body.edges:
        if edge.source not in ids or edge.target not in ids:
            raise HTTPException(422, "A connection references a missing canvas node")
        if edge.source == edge.target:
            raise HTTPException(422, "A Flow Stack cannot connect a node to itself")
        outgoing[edge.source].append(edge.target)
        incoming[edge.target] += 1
    if len(body.nodes) > 1 and not body.edges:
        raise HTTPException(422, "Connect the AgentFlow templates before saving the stack")
    pending = [item for item, count in incoming.items() if count == 0]
    visited = 0
    indegree = dict(incoming)
    while pending:
        current = pending.pop()
        visited += 1
        for target in outgoing[current]:
            indegree[target] -= 1
            if indegree[target] == 0:
                pending.append(target)
    if visited != len(body.nodes):
        raise HTTPException(422, "Flow Stack connections must not contain a cycle")

    children = {}
    for item in body.nodes:
        if bool(item.template_id) == bool(item.flow_id):
            raise HTTPException(422, f"Canvas node '{item.id}' must reference one template or one saved flow")
        if item.template_id:
            children[item.id] = await _instantiate_flow_template(item.template_id, svc, item.label)
        else:
            child = await svc.get_flow_full(item.flow_id)
            if not child or child.is_template or not child.allow_as_subflow:
                raise HTTPException(422, f"Canvas node '{item.id}' references an unavailable flow")
            children[item.id] = child

    stack = await svc.create(
        name=body.name, description=body.description or "Connected Flow Stack",
        trigger_type="manual",
        schedule_config={"stack_orchestrator": body.orchestrator_config},
        flow_type="stack", risk_tier="low", allow_as_subflow=True,
        default_timeout_seconds=int(body.orchestrator_config.get("timeout_seconds", 600)),
        required_tools=sorted({tool for flow in children.values() for tool in (flow.required_tools or [])}),
    )
    input_id, output_id = str(uuid.uuid4()), str(uuid.uuid4())
    graph_nodes = [{
        "id": input_id, "node_type": "input", "label": "Orchestrator Input",
        "position_x": -320, "position_y": 80,
        "config": {"input_type": "orchestrated", "orchestrator": body.orchestrator_config},
    }]
    graph_edges = []
    for item in body.nodes:
        child = children[item.id]
        graph_nodes.append({
            "id": item.id, "node_type": "subflow", "label": item.label or child.name,
            "position_x": item.position_x, "position_y": item.position_y,
            "config": {
                "child_flow_id": str(child.id), "child_flow_version_mode": "locked",
                "child_flow_version": child.version, "execution_mode": "orchestrated",
                "timeout_seconds": stack.default_timeout_seconds, "on_failure": "fail_parent",
                "input_mapping": {}, "output_mapping": {},
            },
        })
    for edge in body.edges:
        graph_edges.append({
            "id": edge.id, "source_node_id": edge.source, "target_node_id": edge.target,
        })
    for source in (item for item, count in incoming.items() if count == 0):
        graph_edges.append({"source_node_id": input_id, "target_node_id": source})
    graph_nodes.append({
        "id": output_id, "node_type": "output", "label": "Stack Output",
        "position_x": max((item.position_x for item in body.nodes), default=0) + 360,
        "position_y": 80, "config": {"output_type": "artifact", "format": "json"},
    })
    for source, targets in outgoing.items():
        if not targets:
            graph_edges.append({"source_node_id": source, "target_node_id": output_id})
    saved = await svc.save_flow_graph(stack.id, graph_nodes, graph_edges, {"x": 40, "y": 80, "zoom": 0.8})
    meta = {"message": "Flow Stack saved"}
    if body.save_as_template:
        template = await svc.duplicate_flow(saved.id)
        template.name = saved.name
        template.is_template = True
        template.template_category = body.category
        template.template_source = "custom"
        template.template_config = {"source_flow_id": str(saved.id), "orchestrator": body.orchestrator_config}
        await svc.session.flush()
        meta["template_id"] = f"custom:{template.id}"
    return ApiResponse(data=AgentFlowResponse.model_validate(saved), meta=meta)


@router.post("/{flow_id}/save-as-template", response_model=ApiResponse, status_code=201)
async def save_flow_as_template(
    flow_id: uuid.UUID,
    body: SaveFlowTemplateRequest,
    svc: AgentFlowService = Depends(get_agent_flow_service),
):
    source = await svc.get_flow_full(flow_id)
    if not source:
        raise HTTPException(404, "Agent Flow not found")
    template = await svc.duplicate_flow(flow_id)
    template.name = body.name or source.name
    template.description = body.description if body.description is not None else source.description
    template.is_template = True
    template.template_category = body.category
    template.template_source = "custom"
    template.template_config = {"source_flow_id": str(source.id), "source_version": source.version}
    await svc.session.flush()
    template = await svc.get_flow_full(template.id)
    return ApiResponse(data=AgentFlowResponse.model_validate(template), meta={"message": "Reusable template saved"})


@router.post("/from-template", response_model=ApiResponse, status_code=201)
async def create_from_template(
    body: dict,
    svc: AgentFlowService = Depends(get_agent_flow_service),
):
    """Create a new Agent Flow from a template ID.

    Body: ``{ "template_id": "translate-en-da", "name": "Optional override" }``
    """
    template_id = body.get("template_id")
    if not template_id:
        raise HTTPException(400, "template_id is required")

    flow = await _instantiate_flow_template(template_id, svc, body.get("name"))

    try:
        await _sync_live_flow_schedule(flow)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"AgentFlow schedule could not be synchronized: {exc}",
        ) from exc

    return ApiResponse(data=AgentFlowResponse.model_validate(flow))


# ── Get a single flow (with nodes and edges) ────────────────
@router.get("/active-runs", response_model=ApiResponse)
async def get_active_runs(db: AsyncSession = Depends(get_db)):
    """Get the count of currently active runs globally."""
    from shogun.db.models.agent_flow_run import AgentFlowRun
    from sqlalchemy import select, func

    result = await db.execute(
        select(func.count(AgentFlowRun.id))
        .where(AgentFlowRun.status.in_(["pending", "running"]))
    )
    count = result.scalar() or 0
    return ApiResponse(data={"active_runs": count})


@router.get("/{flow_id}", response_model=ApiResponse)
async def get_flow(
    flow_id: uuid.UUID,
    svc: AgentFlowService = Depends(get_agent_flow_service),
):
    """Get a single Agent Flow with all nodes and edges."""
    record = await svc.get_flow_full(flow_id)
    if not record:
        raise HTTPException(status_code=404, detail="Agent Flow not found")
    return ApiResponse(data=AgentFlowResponse.model_validate(record))


# ── Update flow metadata ────────────────────────────────────


@router.patch("/{flow_id}", response_model=ApiResponse)
async def update_flow(
    flow_id: uuid.UUID,
    body: AgentFlowUpdate,
    svc: AgentFlowService = Depends(get_agent_flow_service),
):
    """Update Agent Flow metadata (name, description, trigger, status)."""
    current = await svc.get_by_id(flow_id)
    if not current or current.is_deleted:
        raise HTTPException(status_code=404, detail="Agent Flow not found")

    update_data = body.model_dump(exclude_unset=True)
    next_trigger = update_data.get("trigger_type", current.trigger_type)
    if next_trigger == "scheduled":
        update_data["schedule_config"] = _normalized_schedule_config(
            update_data.get("schedule_config") or current.schedule_config or {}
        )
        update_data.setdefault("status", "active")

    record = await svc.update(flow_id, **update_data)
    try:
        await _sync_live_flow_schedule(record)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"AgentFlow schedule could not be synchronized: {exc}",
        ) from exc
    # Reload full flow with nodes/edges
    full = await svc.get_flow_full(flow_id)
    return ApiResponse(data=AgentFlowResponse.model_validate(full))


# ── Delete a flow ────────────────────────────────────────────


@router.delete("/bulk", response_model=ApiResponse)
async def delete_flows_bulk(
    body: AgentFlowBulkDeleteRequest,
    svc: AgentFlowService = Depends(get_agent_flow_service),
):
    """Soft-delete a validated selection of Agent Flows in one request."""
    flow_ids = list(dict.fromkeys(body.flow_ids))
    records = []
    missing: list[str] = []
    for flow_id in flow_ids:
        record = await svc.get_by_id(flow_id)
        if not record or record.is_deleted:
            missing.append(str(flow_id))
        else:
            records.append(record)
    if missing:
        raise HTTPException(
            status_code=404,
            detail={"message": "One or more Agent Flows were not found.", "missing_flow_ids": missing},
        )

    deleted_ids: list[str] = []
    for record in records:
        await svc.delete(record.id)
        await _sync_live_flow_schedule(record)
        deleted_ids.append(str(record.id))
    return ApiResponse(data={"deleted": True, "deleted_count": len(deleted_ids), "deleted_flow_ids": deleted_ids})


@router.delete("/{flow_id}", response_model=ApiResponse)
async def delete_flow(
    flow_id: uuid.UUID,
    svc: AgentFlowService = Depends(get_agent_flow_service),
):
    """Soft-delete an Agent Flow."""
    record = await svc.get_by_id(flow_id)
    success = await svc.delete(flow_id)
    if not success:
        raise HTTPException(status_code=404, detail="Agent Flow not found")
    if record:
        await _sync_live_flow_schedule(record)
    return ApiResponse(data={"deleted": True})


async def _validate_subflow_graph(
    db: AsyncSession,
    parent_flow_id: uuid.UUID,
    proposed_nodes: list[dict] | None = None,
) -> list[str]:
    """Validate references, version locks, static cycles, and configured depth."""
    from shogun.config import settings
    from shogun.db.models.agent_flow import AgentFlow, AgentFlowNode

    flow_result = await db.execute(select(AgentFlow).where(AgentFlow.is_deleted.is_(False)))
    flows = {flow.id: flow for flow in flow_result.scalars().all()}
    node_result = await db.execute(select(AgentFlowNode).where(AgentFlowNode.node_type == "subflow"))
    adjacency: dict[uuid.UUID, list[uuid.UUID]] = {}
    configs: dict[tuple[uuid.UUID, uuid.UUID], dict] = {}
    for node in node_result.scalars().all():
        try:
            child_id = uuid.UUID(str((node.config or {}).get("child_flow_id")))
        except (ValueError, TypeError):
            continue
        adjacency.setdefault(node.flow_id, []).append(child_id)
        configs[(node.flow_id, child_id)] = node.config or {}
    if proposed_nodes is not None:
        adjacency[parent_flow_id] = []
        for node in proposed_nodes:
            if node.get("node_type") != "subflow":
                continue
            config = node.get("config") or {}
            try:
                child_id = uuid.UUID(str(config.get("child_flow_id")))
            except (ValueError, TypeError):
                raise ValueError("Subflow node has an invalid or missing child_flow_id.")
            adjacency[parent_flow_id].append(child_id)
            configs[(parent_flow_id, child_id)] = config

    warnings: list[str] = []
    hard_limit = min(settings.flow_stacking_max_depth, settings.flow_stacking_hard_max_depth)

    def walk(flow_id: uuid.UUID, path: list[uuid.UUID]) -> None:
        if len(path) - 1 > hard_limit:
            raise ValueError(f"Subflow hierarchy exceeds the maximum depth of {hard_limit}.")
        for child_id in adjacency.get(flow_id, []):
            child = flows.get(child_id)
            if not child:
                raise ValueError(f"Subflow reference {child_id} does not exist.")
            if not child.allow_as_subflow:
                raise ValueError(f"Flow '{child.name}' is not allowed to run as a subflow.")
            config = configs.get((flow_id, child_id), {})
            mode = config.get("child_flow_version_mode", "locked")
            locked = config.get("child_flow_version")
            if mode not in {"locked", "latest"}:
                raise ValueError(
                    f"Flow '{child.name}' has invalid version mode '{mode}'; "
                    "expected 'locked' or 'latest'."
                )
            if mode == "latest" and not settings.flow_stacking_allow_latest_version:
                raise ValueError("Latest-version subflow references are disabled.")
            if mode == "latest":
                warnings.append(f"'{child.name}' will use its latest saved version at execution time.")
            if mode == "locked" and locked is not None and int(locked) != child.version:
                raise ValueError(
                    f"Flow '{child.name}' is locked to unavailable version {locked}; "
                    f"current version is {child.version}."
                )
            if child_id in path:
                names = [flows[item].name if item in flows else str(item) for item in [*path, child_id]]
                raise ValueError(f"Subflow cycle detected: {' -> '.join(names)}")
            walk(child_id, [*path, child_id])

    walk(parent_flow_id, [parent_flow_id])
    return list(dict.fromkeys(warnings))


@router.post("/{flow_id}/validate-subflow", response_model=ApiResponse)
async def validate_subflow(
    flow_id: uuid.UUID,
    body: SubflowValidationRequest,
    db: AsyncSession = Depends(get_db),
):
    config = {
        "child_flow_id": str(body.child_flow_id),
        "child_flow_version_mode": body.child_flow_version_mode,
        "child_flow_version": body.child_flow_version,
    }
    try:
        warnings = await _validate_subflow_graph(
            db,
            flow_id,
            [{"node_type": "subflow", "config": config}],
        )
    except ValueError as exc:
        return ApiResponse(data={"valid": False, "warnings": [], "errors": [str(exc)]})
    return ApiResponse(data={"valid": True, "warnings": warnings, "errors": []})


# ── Bulk save graph (nodes + edges) ──────────────────────────


@router.put("/{flow_id}/graph", response_model=ApiResponse)
async def save_graph(
    flow_id: uuid.UUID,
    body: AgentFlowGraphSave,
    svc: AgentFlowService = Depends(get_agent_flow_service),
):
    """Atomically save the full canvas graph (all nodes and edges)."""
    proposed = [n.model_dump() for n in body.nodes]
    try:
        await _validate_subflow_graph(svc.session, flow_id, proposed)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    record = await svc.save_flow_graph(
        flow_id=flow_id,
        nodes_data=proposed,
        edges_data=[e.model_dump() for e in body.edges],
        viewport=body.viewport,
    )
    if not record:
        raise HTTPException(status_code=404, detail="Agent Flow not found")
    try:
        scheduler_state = await _sync_live_flow_schedule(record)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"AgentFlow graph was not saved because its schedule could not be registered: {exc}",
        ) from exc
    if scheduler_state["next_run_at"]:
        scheduler_state["next_run_at"] = scheduler_state["next_run_at"].isoformat()
    return ApiResponse(
        data=AgentFlowResponse.model_validate(record),
        meta=scheduler_state,
    )


# ── Duplicate a flow ─────────────────────────────────────────


@router.post("/{flow_id}/duplicate", response_model=ApiResponse, status_code=201)
async def duplicate_flow(
    flow_id: uuid.UUID,
    svc: AgentFlowService = Depends(get_agent_flow_service),
):
    """Deep-copy an Agent Flow including all nodes and edges."""
    record = await svc.duplicate_flow(flow_id)
    if not record:
        raise HTTPException(status_code=404, detail="Agent Flow not found")
    return ApiResponse(data=AgentFlowResponse.model_validate(record))


# ── Activate / Pause ─────────────────────────────────────────


@router.post("/{flow_id}/activate", response_model=ApiResponse)
async def activate_flow(
    flow_id: uuid.UUID,
    svc: AgentFlowService = Depends(get_agent_flow_service),
):
    """Set flow status to active."""
    record = await svc.update_status(flow_id, "active")
    if not record:
        raise HTTPException(status_code=404, detail="Agent Flow not found")
    try:
        await _sync_live_flow_schedule(record)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"AgentFlow could not be activated in the scheduler: {exc}",
        ) from exc
    return ApiResponse(data=AgentFlowListItem.model_validate(record))


@router.post("/{flow_id}/pause", response_model=ApiResponse)
async def pause_flow(
    flow_id: uuid.UUID,
    svc: AgentFlowService = Depends(get_agent_flow_service),
):
    """Set flow status to paused."""
    record = await svc.update_status(flow_id, "paused")
    if not record:
        raise HTTPException(status_code=404, detail="Agent Flow not found")
    await _sync_live_flow_schedule(record)
    return ApiResponse(data=AgentFlowListItem.model_validate(record))


# ═══════════════════════════════════════════════════════════════
# EXECUTION RUN ENDPOINTS
# ═══════════════════════════════════════════════════════════════


def _run_artifact_files(run) -> list[_Path]:
    """Return safe workspace artifact paths associated with a run."""
    from shogun.config import settings

    root = settings.workspace_path.resolve()
    files: set[_Path] = set()

    for state in (run.node_states or {}).values():
        relative = state.get("artifact_path") if isinstance(state, dict) else None
        if not relative:
            continue
        target = (root / relative).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            continue
        files.add(target)

    # Backward compatibility for runs created before artifact paths were stored.
    legacy_pattern = f"report_*_{str(run.id)[:8]}.*"
    for folder_name in ("Output", "output"):
        output_dir = (root / folder_name).resolve()
        if output_dir.is_dir():
            files.update(path.resolve() for path in output_dir.glob(legacy_pattern))

    return list(files)


def _run_artifact_exists(run) -> bool:
    return any(path.is_file() for path in _run_artifact_files(run))


def _run_has_recorded_artifact(run) -> bool:
    """Whether this run explicitly recorded an artifact it successfully created."""
    return any(
        isinstance(state, dict) and bool(state.get("artifact_path"))
        for state in (run.node_states or {}).values()
    )


@router.post("/{flow_id}/run", response_model=ApiResponse, status_code=202)
async def run_flow(
    flow_id: uuid.UUID,
    body: AgentFlowRunCreate | None = None,
):
    """Trigger execution of an Agent Flow. Returns the run ID immediately.

    The flow executes asynchronously in the background.
    Poll GET /agent-flows/runs/{run_id} for status.
    """
    from shogun.engine.flow_engine import start_flow_run

    trigger = body.trigger_type if body else "manual"
    try:
        run_id = await start_flow_run(
            flow_id,
            trigger_type=trigger,
            input_payload=body.input_payload if body else {},
            governance_context=body.governance_context if body else {},
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return ApiResponse(
        data={"run_id": str(run_id), "status": "pending"},
        meta={"message": "Flow execution started"},
    )


@router.get("/{flow_id}/runs", response_model=ApiResponse)
async def list_flow_runs(
    flow_id: uuid.UUID,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """List execution history for a specific flow."""
    from shogun.db.models.agent_flow_run import AgentFlowRun

    result = await db.execute(
        select(AgentFlowRun)
        .where(AgentFlowRun.flow_id == flow_id)
        .order_by(AgentFlowRun.created_at.desc())
        .limit(limit)
    )
    runs = list(result.scalars().all())

    # Keep completed output-backed history synchronized with the workspace.
    from shogun.db.models.agent_flow import AgentFlowNode
    output_node_result = await db.execute(
        select(AgentFlowNode.id)
        .where(
            AgentFlowNode.flow_id == flow_id,
            AgentFlowNode.node_type == "output",
        )
        .limit(1)
    )
    has_output_node = output_node_result.scalar_one_or_none() is not None
    stale_runs = [
        run for run in runs
        if has_output_node
        and run.status == "completed"
        # Only synchronize runs that previously recorded a successful artifact.
        # A report-write failure must remain visible in History for diagnosis.
        and _run_has_recorded_artifact(run)
        and not _run_artifact_exists(run)
    ]
    if stale_runs:
        for stale_run in stale_runs:
            await db.delete(stale_run)
        await db.commit()
        result = await db.execute(
            select(AgentFlowRun)
            .where(AgentFlowRun.flow_id == flow_id)
            .order_by(AgentFlowRun.created_at.desc())
            .limit(limit)
        )
        runs = list(result.scalars().all())

    return ApiResponse(
        data=[AgentFlowRunListItem.model_validate(r) for r in runs],
        meta={"total": len(runs)},
    )


@router.get("/runs/{run_id}", response_model=ApiResponse)
async def get_flow_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get full execution run details including per-node states."""
    from shogun.db.models.agent_flow_run import AgentFlowRun

    result = await db.execute(
        select(AgentFlowRun).where(AgentFlowRun.id == run_id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Flow run not found")
    return ApiResponse(data=AgentFlowRunResponse.model_validate(run))


def _run_tree_node(run, flow_name: str) -> dict:
    return {
        "run_id": str(run.id),
        "flow_id": str(run.flow_id),
        "flow_name": flow_name,
        "flow_version": run.flow_version,
        "status": run.status,
        "root_run_id": str(run.root_run_id or run.id),
        "parent_run_id": str(run.parent_run_id) if run.parent_run_id else None,
        "parent_node_id": str(run.parent_node_id) if run.parent_node_id else None,
        "run_depth": run.run_depth,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "error_message": run.error_message,
        "governance_context": run.governance_context or {},
        "children": [],
    }


@router.get("/runs/{run_id}/tree", response_model=ApiResponse)
async def get_run_tree(run_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Return the requested run and every nested descendant as a tree."""
    from shogun.db.models.agent_flow import AgentFlow
    from shogun.db.models.agent_flow_run import AgentFlowRun

    requested = await db.get(AgentFlowRun, run_id)
    if not requested:
        raise HTTPException(404, detail="Flow run not found")
    result = await db.execute(
        select(AgentFlowRun, AgentFlow.name)
        .join(AgentFlow, AgentFlow.id == AgentFlowRun.flow_id)
        .where(AgentFlowRun.root_run_id == (requested.root_run_id or requested.id))
        .order_by(AgentFlowRun.run_depth, AgentFlowRun.created_at)
    )
    nodes = {str(run.id): _run_tree_node(run, name) for run, name in result.all()}
    for node in nodes.values():
        parent_id = node["parent_run_id"]
        if parent_id in nodes:
            nodes[parent_id]["children"].append(node)
    return ApiResponse(data=nodes.get(str(run_id)))


@router.get("/runs/{run_id}/children", response_model=ApiResponse)
async def get_run_children(run_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    from shogun.db.models.agent_flow import AgentFlow
    from shogun.db.models.agent_flow_run import AgentFlowRun

    result = await db.execute(
        select(AgentFlowRun, AgentFlow.name)
        .join(AgentFlow, AgentFlow.id == AgentFlowRun.flow_id)
        .where(AgentFlowRun.parent_run_id == run_id)
        .order_by(AgentFlowRun.created_at)
    )
    rows = result.all()
    return ApiResponse(data=[_run_tree_node(run, name) for run, name in rows], meta={"total": len(rows)})


@router.get("/runs/{run_id}/parent", response_model=ApiResponse)
async def get_run_parent(run_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    from shogun.db.models.agent_flow import AgentFlow
    from shogun.db.models.agent_flow_run import AgentFlowRun

    run = await db.get(AgentFlowRun, run_id)
    if not run:
        raise HTTPException(404, detail="Flow run not found")
    if not run.parent_run_id:
        return ApiResponse(data=None)
    result = await db.execute(
        select(AgentFlowRun, AgentFlow.name)
        .join(AgentFlow, AgentFlow.id == AgentFlowRun.flow_id)
        .where(AgentFlowRun.id == run.parent_run_id)
    )
    parent = result.first()
    return ApiResponse(data=_run_tree_node(*parent) if parent else None)


@router.delete("/runs/{run_id}", response_model=ApiResponse)
async def delete_flow_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a historical run and its generated workspace artifacts."""
    from shogun.config import settings
    from shogun.db.models.agent_flow_run import AgentFlowRun

    result = await db.execute(
        select(AgentFlowRun).where(AgentFlowRun.id == run_id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Flow run not found")
    if run.status in {"pending", "running"}:
        raise HTTPException(status_code=409, detail="Active runs cannot be deleted")

    root = settings.workspace_path.resolve()
    deleted_files: list[str] = []
    for artifact in _run_artifact_files(run):
        if not artifact.is_file():
            continue
        try:
            relative = str(artifact.relative_to(root)).replace("\\", "/")
        except ValueError:
            continue
        artifact.unlink()
        deleted_files.append(relative)

    await db.delete(run)
    await db.commit()
    return ApiResponse(data={
        "deleted": True,
        "run_id": str(run_id),
        "deleted_files": deleted_files,
    })


@router.post("/runs/{run_id}/cancel", response_model=ApiResponse)
async def cancel_run(
    run_id: uuid.UUID,
):
    """Cancel a running flow execution."""
    from shogun.engine.flow_engine import cancel_flow_run

    cancelled = await cancel_flow_run(run_id)
    if not cancelled:
        raise HTTPException(
            status_code=404,
            detail="Run not found or already completed",
        )
    return ApiResponse(data={"cancelled": True})


# ── Document Upload for Input Nodes ──────────────────────────


@router.post("/{flow_id}/upload", response_model=ApiResponse)
async def upload_flow_document(
    flow_id: uuid.UUID,
    file: UploadFile = File(...),
    svc: AgentFlowService = Depends(get_agent_flow_service),
):
    """Upload a document file for a Document Upload input node.

    The file is stored under ``{shogun_data}/flows/{flow_id}/uploads/``
    and can be read by the flow engine at execution time.
    """
    from pathlib import Path
    from shogun.config import settings

    # Verify flow exists
    flow = await svc.get_by_id(flow_id)
    if not flow:
        raise HTTPException(status_code=404, detail="Agent Flow not found")

    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    allowed_extensions = {".pdf", ".txt", ".csv", ".json", ".md", ".docx", ".xlsx"}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext}' not allowed. Accepted: {', '.join(sorted(allowed_extensions))}",
        )

    # Save file
    upload_dir = Path(settings.data_dir) / "flows" / str(flow_id) / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Use a safe filename
    safe_name = file.filename.replace("..", "_").replace("/", "_").replace("\\", "_")
    dest_path = upload_dir / safe_name

    content = await file.read()
    dest_path.write_bytes(content)

    return ApiResponse(data={
        "filename": safe_name,
        "size": len(content),
        "path": str(dest_path),
    })





# ═══════════════════════════════════════════════════════════════
# EXAMPLE FLOW SEEDING
# ═══════════════════════════════════════════════════════════════


@router.post("/seed-examples", response_model=ApiResponse, status_code=201)
async def seed_example_flows(
    svc: AgentFlowService = Depends(get_agent_flow_service),
    db: AsyncSession = Depends(get_db),
):
    """Create pre-built example flows to showcase Shogun capabilities.

    Currently seeds:
      - **AI News Digest** — Mado browses AI news sites, Samurai compiles
        a newsletter, and the result is emailed to Michael@alphahorizon.io.
      - Also creates the "News Editor" Samurai agent used by the flow.
    """
    from shogun.services.agent_service import AgentService

    created = []

    # ── 1. Create or find the "News Editor" Samurai agent ───────
    from shogun.db.models.agent import Agent as AgentModel

    agent_svc = AgentService(db)

    # Check if agent already exists (including soft-deleted — slug has unique constraint)
    existing = await db.execute(
        select(AgentModel).where(AgentModel.slug == "news-editor").limit(1)
    )
    editor_agent = existing.scalar_one_or_none()

    if editor_agent:
        # Reactivate if soft-deleted
        if editor_agent.is_deleted:
            editor_agent.is_deleted = False
            editor_agent.deleted_at = None
            editor_agent.status = "draft"
            await db.flush()
    else:
        editor_agent = await agent_svc.create(
            agent_type="samurai",
            name="News Editor",
            slug="news-editor",
            description=(
                "A specialist Samurai agent that compiles raw news data into "
                "polished, well-structured newsletter digests. Expert at "
                "summarising articles, categorising by source, and writing "
                "professional yet approachable email copy."
            ),
            memory_scope={
                "episodic": True,
                "semantic": True,
                "procedural": True,
                "persona": True,
                "skills": True,
            },
            spawn_policy="manual",
            avatar_url="/shogun-avatar.png",
            tags=["news", "editor", "newsletter", "ai-digest"],
        )

    editor_agent_id = str(editor_agent.id)

    # ── 2. AI News Digest Flow ─────────────────────────────────
    flow = await svc.create(
        name="AI News Digest",
        description=(
            "Automated AI news pipeline: Mado scans TechCrunch and The Verge "
            "for the latest AI stories, a Samurai agent compiles the findings "
            "into a polished newsletter, and sends it to Michael@alphahorizon.io."
        ),
        trigger_type="scheduled",
        status="draft",
    )

    # Node IDs (client-side, will be remapped by save_flow_graph)
    n_trigger   = "node-trigger"
    n_nav_gn    = "node-nav-google-news"
    n_nav_ai    = "node-nav-ai-news"
    n_ext_gn    = "node-extract-google-news"
    n_ext_ai    = "node-extract-ai-news"
    n_compiler  = "node-compiler"
    n_email     = "node-email"
    n_output    = "node-output"

    nodes_data = [
        {
            "id": n_trigger,
            "node_type": "input",
            "label": "Daily Trigger",
            "position_x": 0,
            "position_y": 200,
            "config": {
                "input_type": "scheduled",
                "description": "Daily AI news scan — triggers the Mado browser agents to scrape the latest AI articles from top tech publications.",
            },
        },
        {
            "id": n_nav_gn,
            "node_type": "mado_browser",
            "label": "Browse Google News AI",
            "position_x": 320,
            "position_y": 80,
            "config": {
                "action": "navigate",
                "url": "https://news.google.com/search?q=artificial+intelligence&hl=en-US&gl=US&ceid=US:en",
                "session_name": "news_google",
                "browser_mode": "headless",
            },
        },
        {
            "id": n_nav_ai,
            "node_type": "mado_browser",
            "label": "Browse AI News",
            "position_x": 320,
            "position_y": 320,
            "config": {
                "action": "navigate",
                "url": "https://www.artificialintelligence-news.com/",
                "session_name": "news_ainews",
                "browser_mode": "headless",
            },
        },
        {
            "id": n_ext_gn,
            "node_type": "mado_browser",
            "label": "Extract Google News Headlines",
            "position_x": 620,
            "position_y": 80,
            "config": {
                "action": "extract_content",
                "selector": "article a, [data-n-tid] a, c-wiz article, [jslog] h3, [jslog] h4",
                "extract_type": "text",
                "session_name": "news_google",
            },
        },
        {
            "id": n_ext_ai,
            "node_type": "mado_browser",
            "label": "Extract AI News Articles",
            "position_x": 620,
            "position_y": 320,
            "config": {
                "action": "extract_content",
                "selector": "h2 a, h3 a, .post-title a, .entry-title a, article h2, article h3",
                "extract_type": "text",
                "session_name": "news_ainews",
            },
        },
        {
            "id": n_compiler,
            "node_type": "samurai",
            "label": "Compile Newsletter",
            "position_x": 940,
            "position_y": 200,
            "config": {
                "agent_id": editor_agent_id,
                "task_description": (
                    "You are an AI news editor. From the scraped article headlines and "
                    "summaries provided by the previous steps, compile a professional, "
                    "concise AI news digest email.\n\n"
                    "Format the email with:\n"
                    "- A friendly greeting to Michael\n"
                    "- Sections for each source (Google News, AI News)\n"
                    "- Bullet points with brief 1-2 sentence summaries per story\n"
                    "- A closing note from the Shogun AI team\n\n"
                    "Keep it scannable and informative. Use markdown formatting."
                ),
                "expected_output": "A formatted newsletter-style email body in markdown",
                "timeout": 120,
                "retry_count": 1,
                "failure_action": "retry",
            },
        },
        {
            "id": n_email,
            "node_type": "email_send",
            "label": "Send to Michael",
            "position_x": 1260,
            "position_y": 200,
            "config": {
                "to_address": "Michael@alphahorizon.io",
                "subject": "🤖 Your Daily AI News Digest — Shogun",
                "body_template": "",
            },
        },
        {
            "id": n_output,
            "node_type": "output",
            "label": "Delivery Log",
            "position_x": 1540,
            "position_y": 200,
            "config": {
                "output_type": "artifact",
                "format": "markdown",
            },
        },
    ]

    edges_data = [
        # Trigger → both navigation nodes (parallel)
        {
            "source_node_id": n_trigger,
            "target_node_id": n_nav_gn,
            "edge_type": "default",
            "label": None,
            "config": {},
        },
        {
            "source_node_id": n_trigger,
            "target_node_id": n_nav_ai,
            "edge_type": "default",
            "label": None,
            "config": {},
        },
        # Navigate → Extract (each branch)
        {
            "source_node_id": n_nav_gn,
            "target_node_id": n_ext_gn,
            "edge_type": "default",
            "label": None,
            "config": {},
        },
        {
            "source_node_id": n_nav_ai,
            "target_node_id": n_ext_ai,
            "edge_type": "default",
            "label": None,
            "config": {},
        },
        # Both extractions → Compiler (merge)
        {
            "source_node_id": n_ext_gn,
            "target_node_id": n_compiler,
            "edge_type": "default",
            "label": None,
            "config": {},
        },
        {
            "source_node_id": n_ext_ai,
            "target_node_id": n_compiler,
            "edge_type": "default",
            "label": None,
            "config": {},
        },
        # Compiler → Email
        {
            "source_node_id": n_compiler,
            "target_node_id": n_email,
            "edge_type": "default",
            "label": None,
            "config": {},
        },
        # Email → Output
        {
            "source_node_id": n_email,
            "target_node_id": n_output,
            "edge_type": "default",
            "label": None,
            "config": {},
        },
    ]

    saved = await svc.save_flow_graph(
        flow_id=flow.id,
        nodes_data=nodes_data,
        edges_data=edges_data,
        viewport={"x": 50, "y": 50, "zoom": 0.75},
    )
    created.append(AgentFlowListItem.model_validate(saved))

    return ApiResponse(
        data=created,
        meta={"message": f"Seeded {len(created)} example flow(s)"},
    )
