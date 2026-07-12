"""Shared test fixtures and configuration for all tests.

This module provides centralized test fixtures to ensure test isolation
and proper database cleanup between tests.

CRITICAL: Tests NEVER touch production database. All tests run against
portfolio_ai_test database automatically.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load env vars from ~/.env.local FIRST
_env_file = Path.home() / ".env.local"
if _env_file.exists():
    load_dotenv(_env_file, override=True)

# Mark test environment FIRST - before any app imports
# This prevents app/main.py from configuring production logging
os.environ["PYTEST_RUNNING"] = "1"

# Hatchet test configuration - prevent real connections during tests
os.environ.setdefault(
    "HATCHET_CLIENT_TOKEN",
    "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0."
    "eyJzdWIiOiJ0ZXN0LXRlbmFudCIsInNlcnZlcl91cmwiOiJodHRwOi8vbG9jYWxob3N0OjgwODAiLCJncnBjX2Jyb2FkY2FzdF9hZGRyZXNzIjoiMTI3LjAuMC4xOjcwNzAifQ."
    "test",
)
os.environ.setdefault("HATCHET_CLIENT_TLS_STRATEGY", "none")

import pytest  # noqa: E402

from app.hatchet_app import get_hatchet  # noqa: E402
from app.logging_config import configure_logging  # noqa: E402
from app.middleware.cache import clear_cache  # noqa: E402
from app.storage.connection import ConnectionManager  # noqa: E402
from tests.fixtures.db_safety import (  # noqa: E402
    TEST_DB_NAME,
    assert_connected_to_test_database,
    assert_test_database_ownership,
    assert_test_database_writable,
    derive_test_db_url,
    find_test_database_owner_mismatches,
)

# Configure test database
_prod_db_url = os.environ.get("PORTFOLIO_DB_URL", "")
_explicit_test_db_url = os.environ.get("TEST_PORTFOLIO_DB_URL")

try:
    TEST_DB_URL = derive_test_db_url(_prod_db_url, _explicit_test_db_url)
except RuntimeError as exc:
    print("\n" + "=" * 70, file=sys.stderr)
    print("FATAL: TEST DATABASE CONFIGURATION INVALID", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    print(f"\n{exc}", file=sys.stderr)
    print("=" * 70 + "\n", file=sys.stderr)
    raise

if f"/{TEST_DB_NAME}" not in TEST_DB_URL:
    raise RuntimeError(f"Expected test database URL to point to {TEST_DB_NAME}, got {TEST_DB_URL}")

os.environ["PORTFOLIO_DB_URL"] = TEST_DB_URL

# Configure minimal connection pool for tests
# PostgreSQL has max_connections=100, and production services have priority
# Tests use minimal pools (1+1=2 connections) to avoid exhausting the connection limit
os.environ["DB_POOL_SIZE"] = "1"
os.environ["DB_MAX_OVERFLOW"] = "1"

# Configure test logging (separate from production logs)
# Tests write to backend/logs/test.log (user-writable, auto-cleaned)
# This avoids permission issues with /var/log/portfolio-ai/ (systemd-owned)
TEST_LOG_DIR = Path(__file__).parent.parent.parent / "logs"
TEST_LOG_DIR.mkdir(exist_ok=True)
configure_logging(log_dir=str(TEST_LOG_DIR), log_file="test.log")

logger = logging.getLogger(__name__)

# Migration bookkeeping and reference catalogs are shared fixtures. Every other
# public table is test-owned data and must be reset, including tables introduced
# by future migrations. A hard-coded cleanup list had silently missed dozens of
# newer household/portfolio tables and made the integration suite order-dependent.
TABLES_TO_PRESERVE = frozenset(
    {
        "alembic_version",
        "endpoint_catalog",
        "schema_migrations",
        "source_registry",
        "symbols",
        "table_registry",
    }
)


def _get_existing_tables(conn: ConnectionManager) -> set[str]:
    """Return the subset of cleanup tables that exist in the current test schema."""
    rows = conn.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_type = 'BASE TABLE'
        """
    ).fetchall()
    return {str(row[0]) for row in rows}


def _quote_identifier(identifier: str) -> str:
    """Quote one PostgreSQL identifier obtained from the system catalog."""
    return '"' + identifier.replace('"', '""') + '"'


def _get_cleanup_roots(
    conn: ConnectionManager, cleanup_tables: set[str]
) -> list[str]:
    """Return the smallest FK-root set whose CASCADE covers cleanup tables."""
    rows = conn.execute(
        """
        SELECT child.relname, parent.relname
        FROM pg_constraint AS constraint_row
        JOIN pg_class AS child ON child.oid = constraint_row.conrelid
        JOIN pg_namespace AS child_namespace ON child_namespace.oid = child.relnamespace
        JOIN pg_class AS parent ON parent.oid = constraint_row.confrelid
        WHERE constraint_row.contype = 'f'
          AND child_namespace.nspname = 'public'
        """
    ).fetchall()
    edges = {
        (str(child), str(parent))
        for child, parent in rows
        if str(child) in cleanup_tables and str(parent) in cleanup_tables
    }
    children_with_cleanup_parent = {child for child, _parent in edges}
    roots = cleanup_tables - children_with_cleanup_parent
    covered = set(roots)
    while True:
        descendants = {child for child, parent in edges if parent in covered}
        expanded = covered | descendants
        if expanded == covered:
            break
        covered = expanded

    # A self-reference or FK cycle has no graph root. Include any uncovered
    # members explicitly; CASCADE then handles the rest of that component.
    return sorted(roots | (cleanup_tables - covered))


@pytest.fixture(scope="session", autouse=True)
def ensure_test_schema_up_to_date() -> None:
    """Apply Alembic migrations to the test database before any tests run."""
    cm = ConnectionManager(TEST_DB_URL)
    with cm.connection() as conn:
        current_database_row = conn.execute("SELECT current_database(), current_user").fetchone()
        current_database = str(current_database_row[0]) if current_database_row else ""
        current_user = str(current_database_row[1]) if current_database_row else ""
        assert_connected_to_test_database(current_database)
        assert_test_database_ownership(
            current_user=current_user,
            owner_mismatches=find_test_database_owner_mismatches(
                conn, current_user=current_user
            ),
        )

    backend_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["PORTFOLIO_DB_URL"] = TEST_DB_URL
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(backend_root / "alembic.ini"), "upgrade", "head"],
        cwd=backend_root,
        env=env,
        check=True,
    )


def _truncate_test_database() -> None:
    """Clean all mutable application tables in the configured test database."""
    clear_cache()
    cm = ConnectionManager(TEST_DB_URL)

    with cm.connection() as conn:
        current_database_row = conn.execute("SELECT current_database()").fetchone()
        current_database = str(current_database_row[0]) if current_database_row else ""
        assert_connected_to_test_database(current_database)
        privilege_row = conn.execute(
            """
            SELECT
                current_user,
                has_table_privilege(current_user, 'public.symbols', 'INSERT,UPDATE,DELETE'),
                has_table_privilege(
                    current_user,
                    'public.reference_cache',
                    'INSERT,UPDATE,DELETE'
                )
            """
        ).fetchone()
        current_user = str(privilege_row[0]) if privilege_row else ""
        symbols_writable = bool(privilege_row[1]) if privilege_row else False
        reference_cache_writable = bool(privilege_row[2]) if privilege_row else False
        assert_test_database_writable(
            current_user=current_user,
            symbols_writable=symbols_writable,
            reference_cache_writable=reference_cache_writable,
        )

        cleanup_tables = _get_existing_tables(conn) - TABLES_TO_PRESERVE
        if not cleanup_tables:
            return

        try:
            # Names originate from information_schema, not user input. Quote
            # them defensively and truncate in one statement so PostgreSQL can
            # resolve the complete foreign-key graph with CASCADE.
            cleanup_roots = _get_cleanup_roots(conn, cleanup_tables)
            quoted_tables = ", ".join(_quote_identifier(table) for table in cleanup_roots)
            conn.execute(f"TRUNCATE TABLE {quoted_tables} RESTART IDENTITY CASCADE")
            conn.commit()
            logger.debug(
                "Cleaned %d tables from %d FK roots for test isolation",
                len(cleanup_tables),
                len(cleanup_roots),
            )
        except Exception:
            conn.rollback()
            raise


@pytest.fixture
def clean_database() -> None:
    """Provide explicit database isolation to the few DB-backed unit tests.

    Unit tests should normally mock storage. Tests that intentionally exercise
    PostgreSQL can request this fixture and receive the same guarded cleanup as
    the integration lane.
    """
    _truncate_test_database()


@pytest.fixture(autouse=True)
def isolate_integration_database(request: pytest.FixtureRequest) -> None:
    """Run database cleanup before any integration/watchlist data builders.

    Resolve ``clean_database`` from this autouse fixture rather than adding it
    during collection. That keeps cleanup ahead of explicit data-building
    fixtures while avoiding a database truncate for ordinary unit tests.
    """
    if "integration" not in request.node.keywords:
        return
    request.getfixturevalue("clean_database")


@pytest.fixture(autouse=True)
def clear_hatchet_cache() -> None:
    """Clear the cached Hatchet client between tests.

    Prevents test pollution from a real Hatchet connection leaking
    into subsequent tests.
    """
    get_hatchet.cache_clear()
