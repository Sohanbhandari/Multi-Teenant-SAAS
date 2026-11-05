"""
FastAPI application factory.

This module creates and configures the FastAPI application instance.
Responsibility: wire components together only. No business logic lives here.

What this file does:
  1. Creates the FastAPI app with metadata (title, version, docs config).
  2. Registers the CORS middleware (must be first — outermost layer).
  3. Registers the RequestID middleware (attaches a UUID to every request).
  4. Includes the API v1 router at the /api/v1 prefix.
  5. Registers global exception handlers.
  6. Manages the async DB connection pool via the lifespan context.

Starting the server:
  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestIDMiddleware
from app.db.session import close_db_connection, init_db_connection

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.

    Code BEFORE `yield` runs at startup (before the first request).
    Code AFTER `yield` runs at shutdown (after the last request is handled).

    Startup order:
      1. Configure logging so all subsequent messages are formatted correctly.
      2. Initialize the async DB connection pool — verify DB is reachable.

    Shutdown order:
      1. Dispose the DB connection pool — close all open connections cleanly.
    """
    # --- Startup ---
    configure_logging()
    logger.info(
        "Application starting",
        extra={"environment": settings.ENVIRONMENT, "version": "0.1.0"},
    )
    await init_db_connection()

    yield  # Application is now serving requests

    # --- Shutdown ---
    await close_db_connection()
    logger.info("Application shutdown complete")


def create_app() -> FastAPI:
    """
    Application factory.

    Returns a fully configured FastAPI application instance.
    This function is called once at module import time (see `app = create_app()` below).

    Why a factory instead of a module-level app?
    - Testability: tests can call create_app() to get a fresh instance.
    - Future: makes it easier to run multiple ASGI apps in one process if needed.
    """
    app = FastAPI(
        title="Multi-Tenant LMS & Coaching SaaS",
        description=(
            "REST API for the multi-tenant learning and coaching management platform. "
            "Every endpoint is tenant-scoped via organization_id from the JWT."
        ),
        version="0.1.0",
        # Disable interactive docs in production to reduce attack surface
        docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
        redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
        lifespan=lifespan,
    )

    # -------------------------------------------------------------------------
    # Middleware (registered in reverse execution order — last added = first run)
    # -------------------------------------------------------------------------

    # 1. CORS — must be the outermost layer so preflight OPTIONS requests are
    #    handled before any other middleware or route logic.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(settings.FRONTEND_URL)],
        allow_credentials=True,  # Required: cookies are sent with requests
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 2. Request ID — attaches a UUID to request.state and response headers.
    #    Runs after CORS (inner layer).
    app.add_middleware(RequestIDMiddleware)

    # -------------------------------------------------------------------------
    # Routers
    # -------------------------------------------------------------------------
    app.include_router(api_v1_router, prefix="/api/v1")

    # -------------------------------------------------------------------------
    # Exception handlers
    # -------------------------------------------------------------------------
    register_exception_handlers(app)

    return app


# The application instance used by uvicorn:
#   uvicorn app.main:app --reload
app = create_app()

