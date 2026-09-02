import json

import httpx
import pytest

from shogun.integrations.openclaw_client import OPENCLAW_API_KEY, OpenClawClient


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("operation", "expected_path"),
    [
        ("enroll", "/api/v1/specializations/spec%2Fadvanced/enroll"),
        ("evaluate", "/api/v1/agents/ag%2Fprimary/evaluate-badges"),
    ],
)
async def test_agent_writes_retry_with_platform_key(operation, expected_path):
    attempts: list[str | None] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request.headers.get("x-api-key"))
        if request.headers.get("x-api-key") != OPENCLAW_API_KEY:
            return httpx.Response(401, json={"error": "Invalid or missing API key"})
        return httpx.Response(200, json={
            "ok": True,
            "path": request.url.raw_path.decode("ascii"),
        })

    transport_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = OpenClawClient(
        base_url="https://college.test/api",
        actor_id="ag-primary",
        api_key="stale-agent-key",
    )
    client._client = transport_client
    try:
        if operation == "enroll":
            result = await client.enroll_specialization("spec/advanced", "ag-primary")
        else:
            result = await client.evaluate_achievements("ag/primary")
    finally:
        await transport_client.aclose()

    assert result == {"ok": True, "path": expected_path}
    assert attempts == ["stale-agent-key", OPENCLAW_API_KEY]


@pytest.mark.asyncio
async def test_agent_write_uses_platform_key_when_profile_has_no_key():
    attempts: list[str | None] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request.headers.get("x-api-key"))
        status = 200 if request.headers.get("x-api-key") == OPENCLAW_API_KEY else 401
        return httpx.Response(status, json={"ok": status == 200})

    transport_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = OpenClawClient(
        base_url="https://college.test/api",
        actor_id="ag-primary",
        api_key=None,
    )
    client._client = transport_client
    try:
        result = await client.evaluate_achievements("ag-primary")
    finally:
        await transport_client.aclose()

    assert result == {"ok": True}
    assert attempts == [None, OPENCLAW_API_KEY]


@pytest.mark.asyncio
async def test_private_agent_read_retries_with_platform_key():
    attempts: list[str | None] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request.headers.get("x-api-key"))
        if request.headers.get("x-api-key") != OPENCLAW_API_KEY:
            return httpx.Response(401, json={"error": "Unauthorized"})
        return httpx.Response(200, json={"id": "ag-primary", "badges": []})

    transport_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = OpenClawClient(
        base_url="https://college.test/api",
        actor_id="ag-primary",
        api_key="stale-agent-key",
    )
    client._client = transport_client
    try:
        result = await client.get_agent_by_id("ag-primary")
    finally:
        await transport_client.aclose()

    assert result == {"id": "ag-primary", "badges": []}
    assert attempts == ["stale-agent-key", OPENCLAW_API_KEY]


@pytest.mark.asyncio
async def test_transcript_uses_private_self_endpoint():
    requested_paths: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.raw_path.decode("ascii"))
        return httpx.Response(200, json={
            "id": "ag/primary",
            "testResults": [{"skillId": "skill-1", "score": 100}],
        })

    transport_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = OpenClawClient(
        base_url="https://college.test/api",
        actor_id="ag/primary",
        api_key=OPENCLAW_API_KEY,
    )
    client._client = transport_client
    try:
        result = await client.get_agent_transcript("ag/primary")
    finally:
        await transport_client.aclose()

    assert result["testResults"][0]["skillId"] == "skill-1"
    assert requested_paths == ["/api/v1/agents/ag%2Fprimary/self"]


@pytest.mark.asyncio
async def test_exam_submission_includes_genuine_review():
    captured: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(201, json={"ok": True})

    transport_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = OpenClawClient(
        base_url="https://college.test/api",
        actor_id="ag-primary",
        api_key=OPENCLAW_API_KEY,
    )
    client._client = transport_client
    review = {
        "rating": 4,
        "strengths": "The workflow required concrete evidence and verification.",
        "improvements": "The failure cases could include more recovery tradeoffs.",
        "comment": "A relevant and demanding assessment.",
    }
    try:
        await client.submit_test_result(
            "test-1", "ag-primary", 92, model_id="provider/model", review=review
        )
    finally:
        await transport_client.aclose()

    assert captured["review"] == review
    assert captured["agentId"] == "ag-primary"


@pytest.mark.asyncio
async def test_public_catalog_retries_transient_upstream_failure(monkeypatch):
    attempts = 0

    async def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(503, json={"error": "temporarily unavailable"})
        return httpx.Response(200, json=[{
            "id": "skill-1",
            "slug": "reliable-catalog",
            "name": "Reliable Catalog",
            "currentVersion": {"versionLabel": "1.0.0"},
        }])

    async def no_wait(_delay: float) -> None:
        return None

    monkeypatch.setattr("shogun.integrations.openclaw_client.asyncio.sleep", no_wait)
    transport_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = OpenClawClient(base_url="https://college.test/api")
    client._client = transport_client
    try:
        skills = await client.get_skills(limit=1)
    finally:
        await transport_client.aclose()

    assert [skill.id for skill in skills] == ["skill-1"]
    assert attempts == 2


@pytest.mark.asyncio
async def test_public_skill_detail_preserves_not_found_result():
    requested_paths: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.raw_path.decode("ascii"))
        return httpx.Response(404, json={"error": "not found"})

    transport_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = OpenClawClient(base_url="https://college.test/api")
    client._client = transport_client
    try:
        skill = await client.get_skill_by_id("missing/skill")
    finally:
        await transport_client.aclose()

    assert skill is None
    assert requested_paths == ["/api/skills/missing%2Fskill"]


@pytest.mark.asyncio
async def test_dojo_catalog_reports_upstream_failure_without_losing_registration(monkeypatch):
    from fastapi import HTTPException

    from shogun.api import dojo

    request = httpx.Request("GET", "https://college.test/api/skills")
    response = httpx.Response(503, request=request)

    class FailingCollegeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get_skills(self, **_kwargs):
            raise httpx.HTTPStatusError(
                "Service Unavailable",
                request=request,
                response=response,
            )

    monkeypatch.setattr(dojo, "get_openclaw_client", FailingCollegeClient)

    with pytest.raises(HTTPException) as exc_info:
        await dojo.openclaw_skills(limit=200)

    assert exc_info.value.status_code == 502
    assert "registration is still saved" in exc_info.value.detail
