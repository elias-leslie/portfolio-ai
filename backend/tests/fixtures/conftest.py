"""Shared test fixtures and configuration for all tests.

This module provides centralized test fixtures to ensure test isolation
and proper database cleanup between tests.

CRITICAL: Tests NEVER touch production database. All tests run against
portfolio_ai_test database automatically.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load env vars from ~/.env.local FIRST
_env_file = Path.home() / ".env.local"
if _env_file.exists():
    load_dotenv(_env_file)

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

# Configure test database
# Tests use a separate database to avoid cleaning production data
# Derive test DB URL from production DB URL (same user, different database)
_prod_db_url = os.environ.get("PORTFOLIO_DB_URL")
if not _prod_db_url:
    raise RuntimeError(
        "PORTFOLIO_DB_URL environment variable is required. "
        "Create ~/.env.local with PORTFOLIO_DB_URL=postgresql://..."
    )

# PRODUCTION GUARD - refuse to run if URL doesn't contain portfolio_ai
if "/portfolio_ai" not in _prod_db_url:
    print("\n" + "=" * 70, file=sys.stderr)
    print(
        "FATAL: PORTFOLIO_DB_URL does not appear to be a valid portfolio database", file=sys.stderr
    )
    print("=" * 70, file=sys.stderr)
    print(f"\nPORTFOLIO_DB_URL: {_prod_db_url}", file=sys.stderr)
    print("\nExpected format: postgresql://...@localhost:5432/portfolio_ai", file=sys.stderr)
    print("=" * 70 + "\n", file=sys.stderr)
    raise RuntimeError("Invalid PORTFOLIO_DB_URL configuration")

# Replace database name with test database
TEST_DB_URL = _prod_db_url.replace("/portfolio_ai", "/portfolio_ai_test")

# Final safety check - refuse if somehow still pointing at production
if "/portfolio_ai_test" not in TEST_DB_URL:
    print("\n" + "=" * 70, file=sys.stderr)
    print("FATAL: TEST_DB_URL derivation failed - would still hit production!", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    print(f"\nDerived TEST_DB_URL: {TEST_DB_URL}", file=sys.stderr)
    print("=" * 70 + "\n", file=sys.stderr)
    raise RuntimeError("Test database URL derivation failed")

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
    # Agent workflow tables (agent_messages references agent_workflows)
    "agent_messages",
    "agent_workflows",
    # Agent tables (no FK dependencies)
    "agent_tool_calls",
    "agent_ideas",
    "agent_runs",
    # Idea outcomes (references agent_ideas)
    "idea_outcomes",
    # Portfolio positions (references portfolio_accounts)
    "portfolio_positions",
    "portfolio_accounts",
    # Watchlist tables
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
    # Celery task metadata (for Celery testing)
    "celery_taskmeta",
]


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
        - Does NOT clean Celery tables (celery_taskmeta, celery_tasksetmeta)
          as they're managed by Celery itself
    """
    # Create connection manager and clean tables
    cm = ConnectionManager()

    with cm.connection() as conn:
        # Build single TRUNCATE statement with CASCADE for efficiency
        table_list = ", ".join(TABLES_TO_CLEAN)
        try:
            conn.execute(f"TRUNCATE TABLE {table_list} CASCADE")
            conn.commit()
            logger.debug(f"Cleaned {len(TABLES_TO_CLEAN)} tables for test isolation")
        except Exception as e:
            # Log but don't fail if tables don't exist yet
            logger.warning(f"Database cleanup failed (may be expected on first run): {e}")
            conn.rollback()


@pytest.fixture(autouse=True)
def clear_hatchet_cache() -> None:
    """Clear the cached Hatchet client between tests.

    Prevents test pollution from a real Hatchet connection leaking
    into subsequent tests.
    """
    get_hatchet.cache_clear()
