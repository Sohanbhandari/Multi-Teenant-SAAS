"""
Health check and diagnostic endpoints.

Provides:
- GET /api/v1/health: Verifies backend is live, reports environment, checks DB connectivity.
"""

import logging
from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.schemas.common import HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health check",
    description="Returns service status and checks database reachability.",
)
async def check_health(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    """
    Performs live checks on application dependencies (database).
    Returns 200 OK with connectivity diagnostic info.
    """
    db_status = "connected"
    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:
        logger.error("Health check DB probe failed: %s", exc)
        db_status = "disconnected"

    return HealthResponse(
        status="ok",
        environment=settings.ENVIRONMENT,
        version="0.1.0",
        database=db_status,
    )

