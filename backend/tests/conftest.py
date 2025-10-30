"""Shared test fixtures and configuration for all tests.

This module provides centralized test fixtures to ensure test isolation
and proper database cleanup between tests.
"""

from __future__ import annotations

import logging
import os

import pytest

from app.storage.connection import ConnectionManager

# Configure test database
# Tests use a separate database to avoid cleaning production data
TEST_DB_URL = (
    "postgresql://portfolio_ai_user:REDACTED_PASSWORD@localhost:5432/portfolio_ai_test"
)
os.environ["DATABASE_URL"] = TEST_DB_URL

logger = logging.getLogger(__name__)

# List of tables to clean between tests (ordered to respect foreign key constraints)
# Tables are listed in deletion order (children before parents)
TABLES_TO_CLEAN = [
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
    "minute_bars",
    "day_bars",
    "technical_indicators",
    "price_cache",
    "reference_cache",
    # Source metadata
    "source_performance",
    "validation_results",
    # User preferences
    "user_preferences",
]


@pytest.fixture(autouse=True)
def clean_database() -> None:
    """Clean all test data from database tables between tests.

    This fixture runs automatically before each test to ensure test isolation.
    It truncates all application tables (but preserves schema/metadata tables).

    Note:
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
