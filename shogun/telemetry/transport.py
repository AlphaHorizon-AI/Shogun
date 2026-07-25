"""Fail-safe HTTPS transport isolated from Shogun's operational runtime."""

from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import urlparse

import httpx

from shogun.telemetry.config import MAX_BATCH_BYTES


class TelemetryTransport:
    def __init__(self, endpoint: str) -> None:
        parsed = urlparse(endpoint)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("Telemetry endpoint must be an absolute HTTPS URL")
        self.endpoint = endpoint.rstrip("/")

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        encoded = kwargs.get("content")
        if encoded is not None and len(encoded) > MAX_BATCH_BYTES:
            raise ValueError("Telemetry request exceeds the 32 KB limit")
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                timeout = httpx.Timeout(8.0, connect=3.0, read=5.0)
                async with httpx.AsyncClient(
                    timeout=timeout,
                    follow_redirects=False,
                    trust_env=False,
                ) as client:
                    response = await client.request(method, f"{self.endpoint}{path}", **kwargs)
                if 300 <= response.status_code < 400:
                    raise RuntimeError("Telemetry redirects are refused")
                return response
            except (httpx.HTTPError, RuntimeError) as exc:
                last_error = exc
                if attempt == 0:
                    await asyncio.sleep(0.25)
        raise RuntimeError("Telemetry service unavailable") from last_error

    async def post_json(
        self, path: str, payload: dict, token: str | None = None
    ) -> dict:
        import json

        content = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        response = await self._request("POST", path, content=content, headers=headers)
        response.raise_for_status()
        return response.json()

    async def delete(self, path: str, token: str) -> dict:
        response = await self._request(
            "DELETE",
            path,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        )
        response.raise_for_status()
        return response.json()
