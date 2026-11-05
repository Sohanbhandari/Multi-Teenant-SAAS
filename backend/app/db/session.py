"""
Async database session management using SQLAlchemy 2.0 and asyncpg.

Provides:
- init_db_connection: Called on app startup to verify connectivity
- close_db_connection: Called on app shutdown to dispose the engine pool
- get_db: FastAPI dependency yielding an AsyncSession per request
"""

import logging
from typing import AsyncGenerator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from app.core.config import settings

logger = logging.getLogger(__name__)

# Create the async engine with sensible pool defaults
engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=(settings.ENVIRONMENT == "development"),
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def init_db_connection() -> None:
    """Tests connectivity to the database at application startup."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Database connection established successfully.")
    except Exception as exc:
        logger.warning(
            "Could not connect to database on startup (this is expected if DB is offline): %s",
            exc,
        )


async def close_db_connection() -> None:
    """Disposes all pooled connections at application shutdown."""
    await engine.dispose()
    logger.info("Database connection pool disposed.")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an async database session per request.
    Automatically commits or rolls back on exception.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

