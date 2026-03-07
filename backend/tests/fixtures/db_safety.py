"""Shared test-database safety helpers."""

from __future__ import annotations

TEST_DB_NAME = "portfolio_ai_test"
PROD_DB_NAME = "portfolio_ai"


def derive_test_db_url(prod_db_url: str, explicit_test_db_url: str | None = None) -> str:
    """Return the database URL tests should use.

    Prefers an explicit test URL when provided. Otherwise derives the test database
    from the standard production database name.
    """
    if explicit_test_db_url:
        return explicit_test_db_url

    if not prod_db_url:
        raise RuntimeError(
            "PORTFOLIO_DB_URL environment variable is required. "
            "Create ~/.env.local with PORTFOLIO_DB_URL=postgresql://..."
        )

    if f"/{TEST_DB_NAME}" in prod_db_url:
        return prod_db_url

    if f"/{PROD_DB_NAME}" not in prod_db_url:
        raise RuntimeError(
            f"PORTFOLIO_DB_URL must point to /{PROD_DB_NAME} or /{TEST_DB_NAME}; "
            f"got {prod_db_url}"
        )

    return prod_db_url.replace(f"/{PROD_DB_NAME}", f"/{TEST_DB_NAME}")


def assert_connected_to_test_database(current_database: str) -> None:
    """Refuse destructive test cleanup unless the active database is the test DB."""
    if current_database != TEST_DB_NAME:
        raise RuntimeError(
            f"Refusing destructive test cleanup against database {current_database!r}. "
            f"Expected {TEST_DB_NAME!r}."
        )


def assert_test_database_writable(
    *,
    current_user: str,
    symbols_writable: bool,
    reference_cache_writable: bool,
) -> None:
    """Require the test role to have write access to core test tables."""
    if symbols_writable and reference_cache_writable:
        return

    raise RuntimeError(
        "Test database role permissions are incomplete. "
        f"Current user {current_user!r} must be able to write to 'symbols' and "
        "'reference_cache' in portfolio_ai_test."
    )
