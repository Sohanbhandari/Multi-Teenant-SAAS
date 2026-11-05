"""
Integration test for the health check endpoint.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check_returns_200(async_client: AsyncClient):
    """
    Verifies GET /api/v1/health returns HTTP 200 with standard status payload.
    """
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.1.0"
    assert "database" in data
    assert "environment" in data

    # Verify X-Request-ID header attached by middleware
    assert "X-Request-ID" in response.headers

