"""Centralized configuration loading.

Uses pydantic-settings for validated configuration with environment variable support.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from ..utils.project_paths import resolve_project_root

# Ensure HOME is set before any library tries to create cache directories.
# Libraries like yfinance, transformers, and edgartools fail without it.
if not os.environ.get("HOME"):
    os.environ["HOME"] = "/var/cache/portfolio-ai"

# ---------------------------------------------------------------------------
# Port allocation — single source of truth for Portfolio AI.
# ---------------------------------------------------------------------------
PORTFOLIO_BACKEND_PORT = 8000
PORTFOLIO_FRONTEND_PORT = 3000
AGENT_HUB_BACKEND_PORT = 8003
REDIS_PORT = 6379
HATCHET_GRPC_PORT = 7070
PROJECT_ROOT = resolve_project_root(Path(__file__).resolve())
ENV_FILES = (
    Path.home() / ".env.local",
    PROJECT_ROOT / ".env",
    PROJECT_ROOT / ".env.local",
)


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Loads from repo-local env files first, with ~/.env.local kept as a fallback
    for the current internal runtime.
    """

    model_config = SettingsConfigDict(
        env_file=tuple(str(path) for path in ENV_FILES),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    portfolio_db_url: str = ""

    @field_validator("portfolio_db_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Ensure portfolio_db_url is provided."""
        if not v:
            raise ValueError("PORTFOLIO_DB_URL environment variable is required")
        return v

    # Redis
    redis_url: str = f"redis://localhost:{REDIS_PORT}"

    # Hatchet
    hatchet_client_token: str = ""
    hatchet_client_host_port: str = f"127.0.0.1:{HATCHET_GRPC_PORT}"
    hatchet_client_tls_strategy: str = "none"

    # Frontend / CORS
    frontend_host: str | None = None
    frontend_extra_origins: str = ""

    # Cache configuration
    cache_enabled: bool = True
    cache_max_size: int = 1000
    cache_default_ttl: int = 300

    # Agent Hub integration
    agent_hub_url: str = f"http://localhost:{AGENT_HUB_BACKEND_PORT}"
    agent_hub_enabled: bool | None = None
    portfolio_client_id: str = ""
    portfolio_request_source: str = "portfolio-ai"
    sec_user_agent: str = ""
    portfolio_secret_key: str = ""

    # Self-referencing URLs (for internal service calls)
    backend_url: str = f"http://localhost:{PORTFOLIO_BACKEND_PORT}"
    frontend_url: str = f"http://localhost:{PORTFOLIO_FRONTEND_PORT}"

    # Filesystem paths
    artifacts_dir: Path = PROJECT_ROOT / "data" / "artifacts"

    @field_validator("agent_hub_url", mode="before")
    @classmethod
    def normalize_agent_hub_url(cls, v: str | None) -> str:
        """Treat blank env overrides as unset and fall back to local default."""
        if v is None:
            return f"http://localhost:{AGENT_HUB_BACKEND_PORT}"
        text = str(v).strip()
        return text or f"http://localhost:{AGENT_HUB_BACKEND_PORT}"

    @model_validator(mode="after")
    def resolve_agent_hub_enabled(self) -> Settings:
        """Enable Agent Hub automatically when a client id is configured."""
        if self.agent_hub_enabled is None:
            self.agent_hub_enabled = bool(self.portfolio_client_id)
        return self


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    Returns:
        Settings instance (cached for performance)
    """
    return Settings()


# Pre-loaded for modules that need them at import time
# These provide backward compatibility with existing code
settings = get_settings()
DATABASE_URL = settings.portfolio_db_url
REDIS_URL = settings.redis_url

# Some libraries read their configuration directly from process env instead of
# the shared settings object. Bridge repo-local env files into that contract.
if settings.hatchet_client_token:
    os.environ.setdefault("HATCHET_CLIENT_TOKEN", settings.hatchet_client_token)
if settings.hatchet_client_host_port:
    os.environ.setdefault("HATCHET_CLIENT_HOST_PORT", settings.hatchet_client_host_port)
if settings.hatchet_client_tls_strategy:
    os.environ.setdefault("HATCHET_CLIENT_TLS_STRATEGY", settings.hatchet_client_tls_strategy)
if settings.sec_user_agent:
    os.environ.setdefault("SEC_USER_AGENT", settings.sec_user_agent)


def sqlalchemy_database_url(database_url: str) -> str:
    """Normalize PostgreSQL URLs for SQLAlchemy's psycopg dialect."""
    if database_url.startswith("postgresql+psycopg://"):
        return database_url
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg://", 1)
    return database_url
