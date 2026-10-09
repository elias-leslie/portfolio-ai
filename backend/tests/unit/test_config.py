"""Unit tests for application settings."""

from __future__ import annotations

from pydantic import SecretStr

from app.config import Settings, sqlalchemy_database_url


def test_agent_hub_enabled_defaults_true_when_client_id_present() -> None:
    """Agent Hub should auto-enable when a portfolio client id exists."""
    settings = Settings(
        portfolio_db_url="postgresql://test",
        portfolio_client_id="client-id",
        agent_hub_enabled=None,
    )

    assert settings.agent_hub_enabled is True


def test_agent_hub_enabled_respects_explicit_false() -> None:
    """Explicit config should still be able to disable Agent Hub."""
    settings = Settings(
        portfolio_db_url="postgresql://test",
        portfolio_client_id="client-id",
        agent_hub_enabled=False,
    )

    assert settings.agent_hub_enabled is False


def test_sqlalchemy_database_url_uses_psycopg_driver() -> None:
    """SQLAlchemy URLs should be normalized to psycopg3."""
    assert sqlalchemy_database_url("postgresql://test") == "postgresql+psycopg://test"


def test_sqlalchemy_database_url_handles_postgres_shorthand() -> None:
    assert sqlalchemy_database_url("postgres://test") == "postgresql+psycopg://test"


def test_sqlalchemy_database_url_preserves_existing_psycopg() -> None:
    url = "postgresql+psycopg://user:pass@host/db"
    assert sqlalchemy_database_url(url) == url


def test_sqlalchemy_database_url_ignores_non_postgresql() -> None:
    assert sqlalchemy_database_url("sqlite:///test.db") == "sqlite:///test.db"


def test_portfolio_secret_key_is_masked_secret(monkeypatch) -> None:
    settings = Settings(portfolio_db_url="postgresql://test", portfolio_secret_key="super-secret")

    assert isinstance(settings.portfolio_secret_key, SecretStr)
    assert settings.portfolio_secret_key.get_secret_value() == "super-secret"
    assert "super-secret" not in repr(settings)

    from app.services import credential_crypto

    monkeypatch.setattr(credential_crypto, "settings", settings)
    cipher = credential_crypto.CredentialCipher()
    assert cipher.available
    assert cipher.decrypt(cipher.encrypt("value")) == "value"
