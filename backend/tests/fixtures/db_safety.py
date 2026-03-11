"""Shared test-database safety helpers."""

from __future__ import annotations

from collections.abc import Sequence

from app.storage.connection import PostgreSQLConnectionWrapper

TEST_DB_NAME = "portfolio_ai_test"
PROD_DB_NAME = "portfolio_ai"
OWNERSHIP_REPAIR_COMMAND = "sudo bash backend/scripts/setup-test-db.sh"
# Legacy capability tables were dropped in migration 5f4a1c6d9e72.
# Keep the tuple empty — ownership checks remain wired for future drift-prone objects.
LEGACY_TEST_OBJECTS_WITH_OWNER_DRIFT: tuple[str, ...] = ()


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


def find_test_database_owner_mismatches(conn: PostgreSQLConnectionWrapper, *, current_user: str) -> list[tuple[str, str]]:
    """Return legacy test objects not owned by the active test role."""
    conn.execute(
        """
        SELECT c.relname, pg_get_userbyid(c.relowner) AS owner
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = %s
          AND c.relname = ANY(%s)
          AND pg_get_userbyid(c.relowner) <> %s
        ORDER BY c.relname
        """,
        ("public", list(LEGACY_TEST_OBJECTS_WITH_OWNER_DRIFT), current_user),
    )
    return [(str(name), str(owner)) for name, owner in conn.fetchall()]


def assert_test_database_ownership(
    *,
    current_user: str,
    owner_mismatches: Sequence[tuple[str, str]],
) -> None:
    """Require drift-prone legacy objects to be owned by the active test role."""
    if not owner_mismatches:
        return

    mismatch_text = ", ".join(
        f"{name} (owner {owner})" for name, owner in owner_mismatches
    )
    raise RuntimeError(
        "Test database ownership drift detected. "
        f"Current user {current_user!r} cannot run migrations against: {mismatch_text}. "
        f"Repair the test database ownership first with `{OWNERSHIP_REPAIR_COMMAND}`."
    )
