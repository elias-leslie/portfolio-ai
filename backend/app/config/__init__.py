"""Centralized configuration loading.

Uses pydantic-settings for validated configuration with environment variable support.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
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

    # CORS (defaults in main.py are host-specific, not managed here)

    # Cache configuration
    cache_enabled: bool = True
    cache_max_size: int = 1000
    cache_default_ttl: int = 300

    # Agent Hub integration
    agent_hub_enabled: bool = False
    portfolio_client_id: str = ""
    portfolio_client_secret: str = ""
    portfolio_request_source: str = "portfolio-ai"


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
