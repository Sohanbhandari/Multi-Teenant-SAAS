"""
Application configuration and environment variable loading.

This module is the SINGLE SOURCE OF TRUTH for all configuration.
Per AGENTS.md: Never call os.getenv() or os.environ outside of this file.

Uses Pydantic BaseSettings to read and validate environment variables at startup.
If any required variable is missing, FastAPI will fail to start immediately with
a clear error message explaining which variable was omitted.
"""

from typing import Literal
from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Validated application settings loaded from environment variables.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Environment
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"

    # Database (PostgreSQL via Supabase or local docker-compose)
    DATABASE_URL: str = Field(
        ...,
        description="Async PostgreSQL connection string, e.g. postgresql+asyncpg://..."
    )

    # Redis
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL for token blocklist and caching"
    )

    # JWT Authentication
    JWT_SECRET_KEY: str = Field(
        ...,
        min_length=32,
        description="HMAC secret key for signing JWTs (minimum 32 characters)"
    )
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Supabase (Backend only)
    SUPABASE_URL: str = Field(
        default="http://localhost:54321",
        description="Supabase project base URL"
    )
    SUPABASE_SERVICE_ROLE_KEY: str = Field(
        default="",
        description="Supabase service role key (backend only, never expose to client)"
    )
    SUPABASE_STORAGE_BUCKET: str = Field(
        default="lms-dev",
        description="Default storage bucket name"
    )

    # CORS
    FRONTEND_URL: AnyHttpUrl = Field(
        default="http://localhost:3000",
        description="Allowed frontend origin for CORS"
    )

    # Cookie security
    COOKIE_SECURE: bool = Field(
        default=False,
        description="Set to true in production (requires HTTPS)"
    )
    COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"


# Instantiate settings singleton
settings = Settings()

