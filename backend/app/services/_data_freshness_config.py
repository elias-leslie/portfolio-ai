"""Static configuration for data freshness monitoring.

Defines per-table freshness thresholds and remediation task mappings.
"""

from __future__ import annotations

from typing import NotRequired, TypedDict


class TableFreshnessConfig(TypedDict):
    """Configuration for a single table's freshness monitoring."""

    table_name: str
    date_column: str
    expected_hours: int  # How often data should refresh
    critical_hours: int  # When to create alert
    market_data: bool  # Whether to skip alerts on weekends/holidays
    availability_delay_hours: NotRequired[float]  # Post-close processing window before data is expected
    where_clause: NotRequired[str]  # Optional filter for freshness checks on shared tables


# Map tables to their refresh tasks for auto-remediation
# Note: For fear_greed_daily/components, we trigger populate_fear_greed_inputs
# because it fetches new data AND triggers calculate_fear_greed afterwards.
# Triggering just calculate_fear_greed would only recalculate from existing inputs.
REMEDIATION_TASKS: dict[str, str] = {
    "day_bars": "portfolio-maintain-historical",
    "technical_indicators": "portfolio-backfill-indicators",
    "fear_greed_inputs": "portfolio-fg-inputs",
    "fear_greed_daily": "portfolio-fg-inputs",
    "fear_greed_components": "portfolio-fg-inputs",
    "options_market_metrics": "portfolio-options-activity",
    "news_cache": "portfolio-refresh-news-sentiment",
    "reference_cache": "portfolio-yfinance-ref",
    "watchlist_snapshots": "portfolio-refresh-watchlist-scores",
}

# Freshness thresholds for all critical tables
TABLE_FRESHNESS_CONFIG: list[TableFreshnessConfig] = [
    {
        "table_name": "day_bars",
        "date_column": "date",
        "expected_hours": 24,
        "critical_hours": 48,
        "market_data": True,
    },
    {
        "table_name": "technical_indicators",
        "date_column": "calculated_at",
        "expected_hours": 24,
        "critical_hours": 48,
        "market_data": True,
        "availability_delay_hours": 6.5,
    },
    {
        "table_name": "fear_greed_inputs",
        "date_column": "as_of_date",
        "expected_hours": 24,
        "critical_hours": 48,
        "market_data": True,
    },
    {
        "table_name": "fear_greed_daily",
        "date_column": "as_of_date",
        "expected_hours": 24,
        "critical_hours": 48,
        "market_data": True,
    },
    {
        "table_name": "fear_greed_components",
        "date_column": "as_of_date",
        "expected_hours": 24,
        "critical_hours": 48,
        "market_data": True,
    },
    {
        "table_name": "watchlist_snapshots",
        "date_column": "fetched_at",
        "expected_hours": 2,
        "critical_hours": 24,
        "market_data": False,  # Watchlist scores refresh continuously
    },
    {
        "table_name": "options_market_metrics",
        "date_column": "source_timestamp",
        "expected_hours": 24,
        "critical_hours": 72,
        "market_data": True,
    },
    {
        "table_name": "news_cache",
        "date_column": "published_at",
        "expected_hours": 2,
        "critical_hours": 6,
        "market_data": False,
    },
    {
        "table_name": "reference_cache",
        "date_column": "created_at",
        "expected_hours": 24,
        "critical_hours": 72,
        "market_data": False,
        "where_clause": "source = 'yfinance'",
    },
]
