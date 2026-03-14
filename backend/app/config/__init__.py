"""Centralized configuration loading.

Uses pydantic-settings for validated configuration with environment variable support.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Loads from ~/.env.local by default.
    """

    model_config = SettingsConfigDict(
        env_file=str(Path.home() / ".env.local"),
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
    redis_url: str = "redis://localhost:6379"

    # Frontend / CORS
    frontend_host: str | None = None
    frontend_extra_origins: str = ""

    # Cache configuration
    cache_enabled: bool = True
    cache_max_size: int = 1000
    cache_default_ttl: int = 300

    # Agent Hub integration
    agent_hub_url: str = "http://localhost:8003"
    agent_hub_enabled: bool | None = None
    portfolio_client_id: str = ""
    portfolio_client_secret: str = ""
    portfolio_request_source: str = "portfolio-ai"

    # Self-referencing URLs (for internal service calls)
    backend_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:3000"

    # Filesystem paths
    artifacts_dir: Path = Path(__file__).resolve().parents[3] / "data" / "artifacts"

    @model_validator(mode="after")
    def resolve_agent_hub_enabled(self) -> Settings:
        """Enable Agent Hub automatically when credentials are configured."""
        if self.agent_hub_enabled is None:
            self.agent_hub_enabled = bool(
                self.portfolio_client_id and self.portfolio_client_secret
            )
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


def sqlalchemy_database_url(database_url: str) -> str:
    """Normalize PostgreSQL URLs for SQLAlchemy's psycopg dialect."""
    if database_url.startswith("postgresql+psycopg://"):
        return database_url
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg://", 1)
    return database_url
