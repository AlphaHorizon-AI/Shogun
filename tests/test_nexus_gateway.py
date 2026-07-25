"""Integration tests for the Nexus External Gateway."""

from __future__ import annotations

import uuid
import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient

from shogun.db.base import Base
from shogun.db.engine import engine
from shogun.db.models.agent import Agent
from shogun.services.event_logger import EventLogger


@pytest.fixture(autouse=True)
async def setup_db():
    """Ensure database tables are fully created for testing."""
    import shogun.db.models  # Ensure models are loaded
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Cleanup after test if desired, but sqlite in-memory or file runs cleanly


@pytest.fixture
async def seed_agents():
    """Seed a primary Shogun agent and a Samurai research agent."""
    from shogun.db.engine import async_session_factory
    async with async_session_factory() as session:
        # Check if primary shogun already exists
        from sqlalchemy import select
        res = await session.execute(select(Agent).where(Agent.agent_type == "shogun", Agent.is_primary == True))
        shogun_agent = res.scalar_one_or_none()
        
        if not shogun_agent:
            shogun_agent = Agent(
                name="Primary Shogun Agent",
                slug="primary-shogun-agent",
                agent_type="shogun",
                is_primary=True,
                status="active",
                description="Primary Shogun execution hub"
            )
            session.add(shogun_agent)

        res = await session.execute(select(Agent).where(Agent.slug == "research-samurai"))
        research_samurai = res.scalar_one_or_none()
        if not research_samurai:
            research_samurai = Agent(
                name="Research Samurai",
                slug="research-samurai",
                agent_type="samurai",
                status="active",
                description="Specialized in browser research",
                tags=["browser"]
            )
            session.add(research_samurai)

        await session.commit()


@pytest.mark.asyncio
async def test_register_and_list_agents(client: AsyncClient):
    """Test registering a new external agent and listing registered agents."""
    payload = {
        "name": "M365 Integration Agent",
        "platform": "microsoft_365"
    }
    
    # 1. Register agent
    resp = await client.post("/api/v1/nexus/external/register-agent", json=payload)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["name"] == payload["name"]
    assert data["platform"] == payload["platform"]
    assert "token" in data
    
    agent_token = data["token"]
    
    # 2. List agents
    list_resp = await client.get("/api/v1/nexus/external/agents")
    assert list_resp.status_code == 200
    agents = list_resp.json()["data"]
    assert any(a["name"] == payload["name"] and a["token"] == "********" for a in agents)
    assert all(a["token"] != agent_token for a in agents)


@pytest.mark.asyncio
async def test_list_capabilities(client: AsyncClient):
    """Test capability listing and default capability seeding."""
    resp = await client.get("/api/v1/nexus/capabilities")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) >= 9
    assert any(c["name"] == "document.summarize" for c in data)
    assert any(c["name"] == "spreadsheet.analyze" for c in data)


@pytest.mark.asyncio
@patch("shogun.nexus.protocols.internal_shogun_adapter.InternalShogunAdapter.execute_on_agent")
async def test_a2a_task_execution_flow(mock_execute, client: AsyncClient, seed_agents):
    """Test complete successful A2A task lifecycle: registration, auth, policy, execution, and logs."""
    mock_execute.return_value = {
        "status": "success",
        "output": "Mocked summary: Supplier risk is low.",
    }

    # 1. Register external agent to get token
    reg_payload = {"name": "Test M365", "platform": "microsoft_365"}
    reg_resp = await client.post("/api/v1/nexus/external/register-agent", json=reg_payload)
    registration = reg_resp.json()["data"]
    token = registration["token"]
    
    # 2. Submit allowed A2A task
    task_payload = {
        "from_agent_id": "m365_source_007",
        "from_platform": "microsoft_365",
        "capability": "document.summarize",
        "task_description": "Summarize supplier risk assess",
        "context": {"file_path": "data/risk.pdf"},
        "sensitivity": "internal"
    }
    
    headers = {"Authorization": f"Bearer {token}"}
    task_resp = await client.post("/api/v1/nexus/external/a2a/task", json=task_payload, headers=headers)
    assert task_resp.status_code == 200
    task_data = task_resp.json()
    
    assert task_data["status"] == "completed"
    assert task_data["error"] is None
    assert "Mocked summary: Supplier risk is low." in task_data["result"]["output"]
    assert task_data["audit_event_id"] is not None

    # 3. Check status query endpoint
    task_id = task_data["task_id"]
    status_resp = await client.get(f"/api/v1/nexus/external/task/{task_id}", headers=headers)
    assert status_resp.status_code == 200
    status_data = status_resp.json()["data"]
    assert status_data["status"] == "completed"
    assert status_data["requested_action"] == "document.summarize"


@pytest.mark.asyncio
async def test_a2a_task_policy_blocked(client: AsyncClient, seed_agents):
    """Test that unauthorized/restricted tasks (like desktop.execute) are blocked by policies."""
    # 1. Register external agent
    reg_payload = {"name": "Test Salesforce", "platform": "salesforce"}
    reg_resp = await client.post("/api/v1/nexus/external/register-agent", json=reg_payload)
    token = reg_resp.json()["data"]["token"]
    
    # 2. Submit desktop task (which is blocked by policy hooks)
    task_payload = {
        "from_agent_id": "sf_source_abc",
        "from_platform": "salesforce",
        "capability": "desktop.execute",
        "task_description": "Attempt desktop execution",
        "context": {"command": "rm -rf /"},
        "sensitivity": "restricted"
    }
    
    headers = {"Authorization": f"Bearer {token}"}
    task_resp = await client.post("/api/v1/nexus/external/a2a/task", json=task_payload, headers=headers)
    assert task_resp.status_code == 200  # The endpoint responds successfully, but task status is "blocked"
    task_data = task_resp.json()
    
    assert task_data["status"] == "blocked"
    assert "strictly blocked" in task_data["error"]
    assert task_data["result"] == {}


@pytest.mark.asyncio
async def test_invalid_auth_token(client: AsyncClient):
    """Test that requests with invalid bearer token are rejected with 401."""
    task_payload = {
        "from_agent_id": "m365_source_007",
        "from_platform": "microsoft_365",
        "capability": "document.summarize"
    }
    headers = {"Authorization": "Bearer bad_token_12345"}
    resp = await client.post("/api/v1/nexus/external/a2a/task", json=task_payload, headers=headers)
    assert resp.status_code == 401
    assert "Invalid" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_task_callback_update(client: AsyncClient, seed_agents):
    """Test that remote callbacks can update a task status."""
    # 1. Register agent
    reg_payload = {"name": "Test M365 Callback", "platform": "microsoft_365"}
    reg_resp = await client.post("/api/v1/nexus/external/register-agent", json=reg_payload)
    registration = reg_resp.json()["data"]
    token = registration["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Add a dummy task record first
    from shogun.db.engine import async_session_factory
    from shogun.db.models.nexus import NexusTaskModel
    async with async_session_factory() as session:
        dummy_task = NexusTaskModel(
            source_agent_id=registration["id"],
            source_platform="microsoft_365",
            source_protocol="a2a",
            requested_action="document.summarize",
            status="pending"
        )
        session.add(dummy_task)
        await session.commit()
        task_id = dummy_task.id

    # 3. Call the callback update endpoint
    callback_payload = {
        "status": "completed",
        "result": {"output": "Manually completed via callback"},
        "error": None
    }
    callback_resp = await client.post(
        f"/api/v1/nexus/external/task/{task_id}/callback",
        json=callback_payload,
        headers=headers
    )
    assert callback_resp.status_code == 200
    callback_data = callback_resp.json()["data"]
    assert callback_data["status"] == "completed"
    assert callback_data["result"]["output"] == "Manually completed via callback"
