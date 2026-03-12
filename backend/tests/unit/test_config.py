"""Unit tests for application settings."""

from __future__ import annotations

from app.config import Settings, sqlalchemy_database_url


def test_agent_hub_enabled_defaults_true_when_credentials_present() -> None:
    """Agent Hub should auto-enable when portfolio credentials exist."""
    settings = Settings(
        portfolio_db_url="postgresql://test",
        portfolio_client_id="client-id",
        portfolio_client_secret="client-secret",
        agent_hub_enabled=None,
    )

    assert settings.agent_hub_enabled is True


def test_agent_hub_enabled_respects_explicit_false() -> None:
    """Explicit config should still be able to disable Agent Hub."""
    settings = Settings(
        portfolio_db_url="postgresql://test",
        portfolio_client_id="client-id",
        portfolio_client_secret="client-secret",
        agent_hub_enabled=False,
    )

    assert settings.agent_hub_enabled is False


def test_sqlalchemy_database_url_uses_psycopg_driver() -> None:
    """SQLAlchemy URLs should be normalized to psycopg3."""
    assert sqlalchemy_database_url("postgresql://test") == "postgresql+psycopg://test"
