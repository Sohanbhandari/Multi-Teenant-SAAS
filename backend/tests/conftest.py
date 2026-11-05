"""
Pytest configuration and shared fixtures.

Sets up:
- Environment variable overrides for testing
- AsyncClient fixture for FastAPI endpoint testing
"""

import os
from typing import AsyncGenerator
import pytest
from httpx import AsyncClient

# Enforce test environment variables before importing app
os.environ["ENVIRONMENT"] = "development"
os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres:postgres@localhost:5432/lms_test"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["JWT_SECRET_KEY"] = "super-secret-key-that-is-at-least-32-chars-long"
os.environ["FRONTEND_URL"] = "http://localhost:3000"
os.environ["COOKIE_SECURE"] = "false"

from app.main import app
from app.db.session import get_db


class MockAsyncSession:
    """Mock session used for basic health probe when no live DB is active."""
    async def execute(self, statement):
        return None


async def override_get_db():
    yield MockAsyncSession()


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Yields an httpx AsyncClient pointing to the FastAPI test application."""
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(app=app, base_url="http://testserver") as client:
        yield client
    app.dependency_overrides.clear()

