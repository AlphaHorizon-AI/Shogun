"""Pytest fixtures for Shogun tests."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from shogun.app import create_app


@pytest.fixture
def api_app():
    """Create a test FastAPI application."""
    return create_app()


@pytest.fixture
async def client(api_app):
    """Create an async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=api_app),
        base_url="http://test",
    ) as ac:
        yield ac
