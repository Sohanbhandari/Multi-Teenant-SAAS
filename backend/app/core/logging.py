"""
Structured logging configuration.

Sets up standard Python logging with structured formatting and correlation ID support.
"""

import logging
import sys
from app.core.config import settings


def configure_logging() -> None:
    """
    Configures standard stream logging with formatting appropriate for the environment.
    """
    log_level = logging.DEBUG if settings.ENVIRONMENT == "development" else logging.INFO

    log_format = "%(asctime)s | %(levelname)-7s | [%(name)s] %(message)s"
    if settings.ENVIRONMENT == "production":
        # In production, structured format with JSON or clear timestamp is preferred
        log_format = '{"timestamp":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}'

    logging.basicConfig(
        level=log_level,
        format=log_format,
        datefmt="%Y-%m-%dT%H:%M:%S%z",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )

    # Reduce chatter from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

