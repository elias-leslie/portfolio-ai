"""optimize maintenance indexes

Revision ID: b2f9c40d0d5a
Revises: 10b1de025fa4
Create Date: 2026-03-11 10:05:00.000000

"""

import re
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2f9c40d0d5a"
down_revision: str | Sequence[str] | None = "10b1de025fa4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


REDUNDANT_INDEXES = [
    "idx_agent_conversation_messages_run_seq",
    "idx_agent_messages_from_run",
    "idx_celery_feature_feature",
    "idx_celery_feature_mappings_task_name",
    "idx_day_bars_symbol_date",
    "idx_earnings_surprises_ticker_date",
    "idx_feature_capabilities_feature_id",
    "idx_file_audit_path",
    "idx_indicators_ticker",
    "idx_ml_training_progress_session",
    "idx_news_cache_ticker_hash",
    "idx_portfolio_snapshots_account_date",
    "idx_price_cache_symbol",
    "idx_sec_cik_cache_symbol",
    "idx_snapshots_core_item_desc",
    "idx_strategy_signals_strategy_date",
    "idx_thesis_versions_thesis_id",
    "idx_watchlist_snapshots_item",
    "idx_watchlist_snapshots_item_fetched",
    "idx_watchlist_thesis_symbol",
]


_SAFE_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _drop_index_if_permitted(index_name: str) -> None:
    """Drop an index when the migration role owns it; otherwise skip cleanly."""
    if not _SAFE_IDENTIFIER_RE.match(index_name):
        raise ValueError(f"Unsafe index name rejected: {index_name!r}")
    op.execute(
        f"""
        DO $$
        BEGIN
            EXECUTE 'DROP INDEX IF EXISTS {index_name}';
        EXCEPTION
            WHEN insufficient_privilege THEN
                RAISE NOTICE 'Skipping index cleanup for {index_name}; insufficient privilege';
        END $$;
        """
    )


def _create_index_if_permitted(sql: str, *, object_name: str) -> None:
    """Create an index when the migration role owns the target table."""
    escaped_sql = sql.replace("'", "''")
    op.execute(
        f"""
        DO $$
        BEGIN
            EXECUTE '{escaped_sql}';
        EXCEPTION
            WHEN insufficient_privilege THEN
                RAISE NOTICE 'Skipping index create for {object_name}; insufficient privilege';
        END $$;
        """
    )


def upgrade() -> None:
    """Upgrade schema."""
    for index_name in REDUNDANT_INDEXES:
        _drop_index_if_permitted(index_name)

    _create_index_if_permitted(
        "CREATE INDEX IF NOT EXISTS idx_news_cache_fetched_at ON news_cache (fetched_at)",
        object_name="idx_news_cache_fetched_at",
    )
    _create_index_if_permitted(
        "CREATE INDEX IF NOT EXISTS idx_news_cache_vendor_fetched_at "
        "ON news_cache ((raw_payload->'raw'->>'vendor'), fetched_at DESC)",
        object_name="idx_news_cache_vendor_fetched_at",
    )


def downgrade() -> None:
    """Downgrade schema."""
    _drop_index_if_permitted("idx_news_cache_vendor_fetched_at")
    _drop_index_if_permitted("idx_news_cache_fetched_at")

    _create_index_if_permitted(
        "CREATE INDEX IF NOT EXISTS idx_agent_conversation_messages_run_seq "
        "ON agent_conversation_messages (agent_run_id, sequence_num)",
        object_name="idx_agent_conversation_messages_run_seq",
    )
    _create_index_if_permitted(
        "CREATE INDEX IF NOT EXISTS idx_agent_messages_from_run ON agent_messages (from_agent_run_id)",
        object_name="idx_agent_messages_from_run",
    )
    _create_index_if_permitted(
        "CREATE INDEX IF NOT EXISTS idx_celery_feature_feature ON celery_feature_mappings (feature_id)",
        object_name="idx_celery_feature_feature",
    )
    _create_index_if_permitted(
        "CREATE INDEX IF NOT EXISTS idx_celery_feature_mappings_task_name "
        "ON celery_feature_mappings (task_name)",
        object_name="idx_celery_feature_mappings_task_name",
    )
    _create_index_if_permitted(
        "CREATE INDEX IF NOT EXISTS idx_day_bars_symbol_date ON day_bars (symbol, date)",
        object_name="idx_day_bars_symbol_date",
    )
    _create_index_if_permitted(
        "CREATE INDEX IF NOT EXISTS idx_earnings_surprises_ticker_date "
        "ON earnings_surprises (symbol, earnings_date)",
        object_name="idx_earnings_surprises_ticker_date",
    )
    _create_index_if_permitted(
        "CREATE INDEX IF NOT EXISTS idx_feature_capabilities_feature_id "
        "ON feature_capabilities (feature_id)",
        object_name="idx_feature_capabilities_feature_id",
    )
    _create_index_if_permitted(
        "CREATE INDEX IF NOT EXISTS idx_file_audit_path ON file_audit (path)",
        object_name="idx_file_audit_path",
    )
    _create_index_if_permitted(
        "CREATE INDEX IF NOT EXISTS idx_indicators_ticker ON technical_indicators (symbol, date)",
        object_name="idx_indicators_ticker",
    )
    _create_index_if_permitted(
        "CREATE INDEX IF NOT EXISTS idx_ml_training_progress_session "
        "ON ml_training_progress (session_id)",
        object_name="idx_ml_training_progress_session",
    )
    _create_index_if_permitted(
        "CREATE INDEX IF NOT EXISTS idx_news_cache_ticker_hash ON news_cache (symbol, content_hash)",
        object_name="idx_news_cache_ticker_hash",
    )
    _create_index_if_permitted(
        "CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_account_date "
        "ON portfolio_snapshots (account_id, snapshot_date)",
        object_name="idx_portfolio_snapshots_account_date",
    )
    _create_index_if_permitted(
        "CREATE INDEX IF NOT EXISTS idx_price_cache_symbol ON price_cache (symbol, cached_at)",
        object_name="idx_price_cache_symbol",
    )
    _create_index_if_permitted(
        "CREATE INDEX IF NOT EXISTS idx_sec_cik_cache_symbol ON sec_cik_cache (symbol)",
        object_name="idx_sec_cik_cache_symbol",
    )
    _create_index_if_permitted(
        "CREATE INDEX IF NOT EXISTS idx_snapshots_core_item_desc "
        "ON watchlist_snapshots_core (item_id, fetched_at)",
        object_name="idx_snapshots_core_item_desc",
    )
    _create_index_if_permitted(
        "CREATE INDEX IF NOT EXISTS idx_strategy_signals_strategy_date "
        "ON strategy_signals (strategy_id, signal_date)",
        object_name="idx_strategy_signals_strategy_date",
    )
    _create_index_if_permitted(
        "CREATE INDEX IF NOT EXISTS idx_thesis_versions_thesis_id "
        "ON thesis_versions (thesis_id, version)",
        object_name="idx_thesis_versions_thesis_id",
    )
    _create_index_if_permitted(
        "CREATE INDEX IF NOT EXISTS idx_watchlist_snapshots_item "
        "ON watchlist_snapshots (item_id, fetched_at)",
        object_name="idx_watchlist_snapshots_item",
    )
    _create_index_if_permitted(
        "CREATE INDEX IF NOT EXISTS idx_watchlist_thesis_symbol ON watchlist_thesis (symbol)",
        object_name="idx_watchlist_thesis_symbol",
    )
