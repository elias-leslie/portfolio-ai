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
os.environ.setdefault("HATCHET_CLIENT_TOKEN", "test-token-not-real")
os.environ.setdefault("HATCHET_CLIENT_TLS_STRATEGY", "none")

import pytest  # noqa: E402

from app.hatchet_app import get_hatchet  # noqa: E402
from app.logging_config import configure_logging  # noqa: E402
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

# List of tables to clean between tests (ordered to respect foreign key constraints)
# Tables are listed in deletion order (children before parents)
TABLES_TO_CLEAN = [
    "automation_preferences",
    "symbol_workflow_events",
    "symbol_workflows",
    "household_questions",
    "household_inferred_values",
    "household_document_reviews",
    "household_document_requirements",
    "household_planned_expenses",
    "household_retirement_income_sources",
    "household_insurance_policies",
    "household_housing_costs",
    "household_debt_obligations",
    "household_income_sources",
    "household_members",
    "household_transactions",
    "household_import_rows",
    "household_merchants",
    "household_document_signatures",
    "household_documents",
    "household_profiles",
    # Agent workflow tables (agent_messages references agent_workflows)
    "agent_messages",
    "agent_workflows",
    # Agent tables (strategy_seeds references agent_runs and symbols)
    "strategy_seeds",
    "agent_tool_calls",
    "agent_conversation_messages",
    "agent_runs",
    # Idea outcomes
    "idea_outcomes",
    # SnapTrade brokerage sync (children before parents; reference
    # portfolio_accounts, so clean before it)
    "snaptrade_activities",
    "snaptrade_positions",
    "snaptrade_accounts",
    "snaptrade_connections",
    "snaptrade_users",
    # Portfolio ledger (references portfolio_accounts and portfolio_transactions)
    "portfolio_tax_lots",
    "portfolio_transactions",
    # Portfolio positions (references portfolio_accounts)
    "portfolio_positions",
    "portfolio_accounts",
    # Watchlist tables (split schema: narrative/news/technical reference core)
    "watchlist_narrative",
    "watchlist_news_summary",
    "watchlist_technical_metrics",
    "watchlist_snapshots_core",
    "watchlist_snapshots",
    "watchlist_items",
    # Price and market data
    "day_bars",
    "technical_indicators",
    "price_cache",
    "reference_cache",
    "news_cache",
    "news_summary_log",
    # Source metadata
    "source_performance",
    "validation_results",
    # User preferences
    "user_preferences",
]


def _get_existing_tables(conn: ConnectionManager) -> set[str]:
    """Return the subset of cleanup tables that exist in the current test schema."""
    rows = conn.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        """
    ).fetchall()
    return {str(row[0]) for row in rows}


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


@pytest.fixture(autouse=False)
def clean_database() -> None:
    """Clean all test data from database tables between tests.

    This fixture provides database cleanup for integration tests that need
    test isolation. It truncates all application tables (but preserves
    schema/metadata tables).

    Note:
        - Applied automatically to integration/watchlist tests only
        - Unit tests do NOT use this fixture (they should mock database access)
        - Uses CASCADE to handle foreign key dependencies
        - Preserves schema_migrations, source_registry, source_credentials,
          endpoint_catalog, and table_registry (these are configuration data)
    """
    # Create connection manager and clean tables
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

        existing_tables = [table for table in TABLES_TO_CLEAN if table in _get_existing_tables(conn)]
        if not existing_tables:
            return

        try:
            for table in existing_tables:
                conn.execute(f"DELETE FROM {table}")
            conn.commit()
            logger.debug(f"Cleaned {len(existing_tables)} tables for test isolation")
        except Exception:
            conn.rollback()
            raise


@pytest.fixture(autouse=True)
def clear_hatchet_cache() -> None:
    """Clear the cached Hatchet client between tests.

    Prevents test pollution from a real Hatchet connection leaking
    into subsequent tests.
    """
    get_hatchet.cache_clear()
