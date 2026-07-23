from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from shogun.api.agent_flow import (
    _flow_stack_templates,
    _instantiate_flow_template,
    _load_templates,
    compose_flow_stack,
    create_stack_from_template,
    get_template_detail,
    save_flow_as_template,
)
from shogun.db.models.agent_flow import AgentFlow, AgentFlowEdge, AgentFlowNode
from shogun.schemas.agent_flow import (
    FlowStackComposeEdge,
    FlowStackComposeNode,
    FlowStackComposeRequest,
    FlowStackTemplateInstantiate,
    SaveFlowTemplateRequest,
)
from shogun.services.agent_flow_service import AgentFlowService


@pytest.fixture
async def template_sessions():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(AgentFlow.__table__.create)
        await connection.run_sync(AgentFlowNode.__table__.create)
        await connection.run_sync(AgentFlowEdge.__table__.create)
    yield sessions
    await engine.dispose()


def test_stack_catalog_has_208_valid_categorized_recipes_including_required_build_stacks():
    recipes = _flow_stack_templates()
    flow_template_ids = {item["id"] for item in _load_templates()["templates"]}

    assert len(recipes) == 208
    assert len({item["id"] for item in recipes}) == 208
    coding = [item for item in recipes if item["category"] == "Coding Agent Stacks"]
    assert len(coding) == 33
    assert {
        "coding-complex-game-build",
        "coding-website-build",
        "coding-business-app-build",
    } <= {item["id"] for item in coding}
    assert len({item["category"] for item in recipes}) >= 10
    assert all(item["flow_template_ids"] for item in recipes)
    assert all(set(item["flow_template_ids"]) <= flow_template_ids for item in recipes)
    assert all(item["flow_count"] == 8 for item in recipes)
    assert all(len(item["builder_edges"]) == 10 for item in recipes)
    assert all(item["orchestrator_config"]["max_runtime_minutes"] >= 720 for item in recipes)
    assert all(item["orchestrator_config"]["checkpoint_frequency"] == "after_each_subflow" for item in recipes)
    assert all(item["orchestrator_config"]["verification_required"] is True for item in recipes)
    assert {item["category"] for item in recipes} == {
        "Continuous Intelligence", "Strategy & Transformation", "Product & Innovation",
        "Growth & Brand", "Customer Operations", "Data & Executive Operations",
        "Risk & Compliance", "People & Capability", "Incident & Resilience",
        "Knowledge & Publishing",
        "Coding Agent Stacks",
    }


@pytest.mark.asyncio
async def test_template_detail_exposes_internal_nodes_and_connections(template_sessions):
    async with template_sessions() as session:
        response = await get_template_detail("translate-en-da", AgentFlowService(session))

    assert response.data["name"]
    assert len(response.data["nodes"]) == 5
    assert len(response.data["edges"]) == 4
    assert {node["node_type"] for node in response.data["nodes"]} >= {"input", "samurai", "output"}


@pytest.mark.asyncio
async def test_coding_template_instantiation_declares_ide_governance(template_sessions):
    async with template_sessions() as session:
        flow = await _instantiate_flow_template(
            "coding-feature-build",
            AgentFlowService(session),
            "Governed Feature Build",
        )

    assert flow.risk_tier == "high"
    assert "ide_memory_search" in flow.required_tools
    assert "ide_apply_patch" in flow.required_tools
    assert any(node.node_type == "coding" for node in flow.nodes)


@pytest.mark.asyncio
async def test_agentflow_can_be_saved_as_reusable_template(template_sessions):
    async with template_sessions() as session:
        service = AgentFlowService(session)
        source = await service.create(name="Research Flow", schedule_config={}, viewport={})
        await service.save_flow_graph(source.id, [{
            "id": str(uuid.uuid4()), "node_type": "samurai", "label": "Research",
            "position_x": 10, "position_y": 20, "config": {},
        }], [])
        response = await save_flow_as_template(
            source.id,
            SaveFlowTemplateRequest(name="Reusable Research", category="Research"),
            service,
        )
        templates = await service.list_saved_templates(flow_type="standard")
        instance = await _instantiate_flow_template(f"custom:{templates[0].id}", service, "Research Instance")

    assert response.data.name == "Reusable Research"
    assert len(templates) == 1
    assert templates[0].is_template is True
    assert templates[0].template_category == "Research"
    assert instance.name == "Research Instance"
    assert instance.is_template is False


@pytest.mark.asyncio
async def test_canvas_compose_saves_connections_orchestrator_and_custom_template(template_sessions):
    first_id, second_id = str(uuid.uuid4()), str(uuid.uuid4())
    async with template_sessions() as session:
        service = AgentFlowService(session)
        response = await compose_flow_stack(
            FlowStackComposeRequest(
                name="Connected Stack",
                category="Operations",
                nodes=[
                    FlowStackComposeNode(id=first_id, template_id="translate-en-da", position_x=100, position_y=80),
                    FlowStackComposeNode(id=second_id, template_id="summarize-doc", position_x=450, position_y=80),
                ],
                edges=[FlowStackComposeEdge(source=first_id, target=second_id)],
                orchestrator_config={"objective": "Translate then summarize", "failure_policy": "pause"},
                save_as_template=True,
            ),
            service,
        )
        saved = await service.get_flow_full(response.data.id)
        templates = await service.list_saved_templates(flow_type="stack")

    subflows = [node for node in saved.nodes if node.node_type == "subflow"]
    assert saved.flow_type == "stack"
    assert saved.schedule_config["stack_orchestrator"]["objective"] == "Translate then summarize"
    assert len(subflows) == 2
    assert len(saved.edges) == 3  # orchestrator input -> first -> second -> output
    assert len(templates) == 1
    assert response.meta["template_id"].startswith("custom:")


@pytest.mark.asyncio
async def test_original_stack_template_instantiates_branching_long_running_program(template_sessions):
    recipe = _flow_stack_templates()[0]
    async with template_sessions() as session:
        service = AgentFlowService(session)
        response = await create_stack_from_template(
            FlowStackTemplateInstantiate(template_id=recipe["id"]), service,
        )
        saved = await service.get_flow_full(response.data.id)

    assert len([node for node in saved.nodes if node.node_type == "subflow"]) == 8
    assert len(saved.edges) == 12  # 10 program edges + orchestrator input + final output
    assert saved.schedule_config["stack_orchestrator"]["max_runtime_minutes"] >= 720
    assert saved.schedule_config["stack_orchestrator"]["verification_required"] is True


@pytest.mark.parametrize("template_id", [
    "coding-complex-game-build",
    "coding-website-build",
    "coding-business-app-build",
])
@pytest.mark.asyncio
async def test_specialized_build_stacks_instantiate_with_visible_canvas_graph(
    template_sessions,
    template_id,
):
    async with template_sessions() as session:
        service = AgentFlowService(session)
        response = await create_stack_from_template(
            FlowStackTemplateInstantiate(template_id=template_id),
            service,
        )
        saved = await service.get_flow_full(response.data.id)

    subflows = [node for node in saved.nodes if node.node_type == "subflow"]
    assert len(subflows) == 8
    assert len(saved.edges) == 12
    assert all(node.position_x >= 0 and node.position_y >= 0 for node in subflows)
    assert all(node.config.get("child_flow_id") for node in subflows)
