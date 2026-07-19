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
