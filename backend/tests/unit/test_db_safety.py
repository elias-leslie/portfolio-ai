"""Unit tests for pytest database safety helpers."""

from __future__ import annotations

import pytest

from app.storage.connection import ConnectionManager
from tests.fixtures.db_safety import (
    OWNERSHIP_REPAIR_COMMAND,
    TEST_DB_NAME,
    assert_connected_to_test_database,
    assert_test_database_ownership,
    assert_test_database_writable,
    derive_test_db_url,
)


def test_derive_test_db_url_prefers_explicit_override() -> None:
    """An explicit test URL should take precedence over derivation."""
    result = derive_test_db_url(
        "postgresql://portfolio_app:secret@localhost:5432/portfolio_ai",
        "postgresql://portfolio_app:secret@localhost:5432/custom_test_db",
    )

    assert result == "postgresql://portfolio_app:secret@localhost:5432/custom_test_db"


def test_derive_test_db_url_rewrites_standard_portfolio_database() -> None:
    """The default production database should map to the standard test database."""
    result = derive_test_db_url(
        "postgresql://portfolio_app:secret@localhost:5432/portfolio_ai"
    )

    assert result.endswith(f"/{TEST_DB_NAME}")


def test_assert_connected_to_test_database_rejects_production_database() -> None:
    """Destructive cleanup must never proceed against the live portfolio database."""
    with pytest.raises(RuntimeError, match="Refusing destructive test cleanup"):
        assert_connected_to_test_database("portfolio_ai")


def test_connection_manager_prefers_runtime_portfolio_db_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """Runtime test overrides should beat the import-time database URL snapshot."""
    monkeypatch.setenv(
        "PORTFOLIO_DB_URL",
        "postgresql://portfolio_app:secret@localhost:5432/portfolio_ai_test_runtime",
    )

    manager = ConnectionManager()

    assert manager.database_url.endswith("/portfolio_ai_test_runtime")


def test_assert_test_database_writable_rejects_missing_permissions() -> None:
    """Mis-granted test databases should fail immediately with a clear error."""
    with pytest.raises(RuntimeError, match="permissions are incomplete"):
        assert_test_database_writable(
            current_user="portfolio_app",
            symbols_writable=False,
            reference_cache_writable=True,
        )


def test_assert_test_database_ownership_rejects_owner_drift() -> None:
    """Legacy objects owned by the wrong role should fail with a repair command."""
    with pytest.raises(RuntimeError, match="ownership drift detected") as exc_info:
        assert_test_database_ownership(
            current_user="portfolio_app",
            owner_mismatches=[("feature_capabilities", "portfolio_ai_user")],
        )

    assert OWNERSHIP_REPAIR_COMMAND in str(exc_info.value)
