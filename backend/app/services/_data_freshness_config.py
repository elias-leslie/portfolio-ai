"""Static configuration for data freshness monitoring.

Defines per-table freshness thresholds and remediation task mappings.
"""

from __future__ import annotations

from typing import NotRequired, TypedDict


class TableFreshnessConfig(TypedDict):
    """Configuration for a single table's freshness monitoring."""

    table_name: str
    date_column: str
    expected_hours: float  # How often data should refresh
    critical_hours: float  # When to create alert
    market_data: bool  # Whether to skip alerts on weekends/holidays
    availability_delay_hours: NotRequired[float]  # Post-close processing window before data is expected
    where_clause: NotRequired[str]  # Optional filter for freshness checks on shared tables
    required_symbols_query: NotRequired[str]  # Optional SQL returning required symbol coverage rows
    intraday: NotRequired[bool]  # Age against wall-clock during market hours (live quotes), not the trading day


REQUIRED_PORTFOLIO_SYMBOLS_QUERY = """
    SELECT DISTINCT symbol FROM watchlist_items
    UNION
    SELECT DISTINCT symbol FROM portfolio_positions
"""


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
    "cash_flow_metrics": "portfolio-ingest-fundamentals",
    "financial_health_scores": "portfolio-financial-health",
    "symbol_risk_metrics": "portfolio-risk-metrics",
    "watchlist_snapshots": "portfolio-refresh-watchlist-scores",
    "snaptrade_accounts": "portfolio-sync-accounts",
    "plaid_accounts": "portfolio-sync-accounts",
    # Re-running the gate refreshes the live ^VIX quote and recomputes the snapshot.
    "price_cache": "portfolio-macro-gate",
    # Open-UI top-up for the scanner's "Today" intraday trendline. The hourly
    # cron is the closed-PWA baseline; this lets the Data Feed refresh pull fresh
    # bars on demand when the UI is open and intraday_bars has aged past expected.
    "intraday_bars": "portfolio-refresh-watchlist-intraday",
}

# Freshness thresholds for all critical tables
TABLE_FRESHNESS_CONFIG: list[TableFreshnessConfig] = [
    {
        "table_name": "day_bars",
        "date_column": "date",
        "expected_hours": 24,
        "critical_hours": 48,
        "market_data": True,
        "required_symbols_query": REQUIRED_PORTFOLIO_SYMBOLS_QUERY,
    },
    {
        "table_name": "technical_indicators",
        "date_column": "date",
        "expected_hours": 24,
        "critical_hours": 48,
        "market_data": True,
        "availability_delay_hours": 6.5,
        "required_symbols_query": REQUIRED_PORTFOLIO_SYMBOLS_QUERY,
    },
    {
        "table_name": "fear_greed_inputs",
        "date_column": "as_of_date",
        "expected_hours": 24,
        "critical_hours": 48,
        "market_data": True,
        "availability_delay_hours": 6.5,
        # HY OAS is a T+1 FRED series. The macro gate validates its own carried
        # credit as-of separately, so this table-level check should not mark the
        # whole feed overdue just because the newest price/put-call row is waiting
        # on the next HY print.
        "where_clause": (
            "vix_close IS NOT NULL AND spy_close IS NOT NULL AND spy_sma_200 IS NOT NULL "
            "AND rsi_14 IS NOT NULL"
        ),
    },
    {
        "table_name": "fear_greed_daily",
        "date_column": "as_of_date",
        "expected_hours": 24,
        "critical_hours": 48,
        "market_data": True,
        "availability_delay_hours": 6.5,
    },
    {
        "table_name": "fear_greed_components",
        "date_column": "as_of_date",
        "expected_hours": 24,
        "critical_hours": 48,
        "market_data": True,
        "availability_delay_hours": 6.5,
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
        "date_column": "fetched_at",
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
    {
        "table_name": "cash_flow_metrics",
        "date_column": "updated_at",
        "expected_hours": 168,
        "critical_hours": 240,
        "market_data": False,
    },
    {
        "table_name": "financial_health_scores",
        "date_column": "updated_at",
        "expected_hours": 168,
        "critical_hours": 240,
        "market_data": False,
    },
    {
        "table_name": "symbol_risk_metrics",
        "date_column": "as_of_date",
        "expected_hours": 24,
        "critical_hours": 72,
        "market_data": False,
    },
    # Data-services account aggregators. Synced 3x on weekdays
    # (ACCOUNT_SYNC_CRONS); the longest weekday gap is overnight (~13.5h).
    # market_data=True so weekend/holiday staleness (when no sync runs) is not
    # flagged. Both remediate via portfolio-sync-accounts.
    {
        "table_name": "snaptrade_accounts",
        "date_column": "last_synced_at",
        "expected_hours": 24,
        "critical_hours": 72,
        "market_data": True,
    },
    {
        "table_name": "plaid_accounts",
        "date_column": "last_synced_at",
        "expected_hours": 24,
        "critical_hours": 72,
        "market_data": True,
    },
    # Canonical live-quote table. The macro gate's only intraday input is ^VIX,
    # so the "Live (Data Feed)" badge must watch its vendor quote_time at an
    # intraday cadence — otherwise a frozen VIX feed reads "Live" while the gate
    # runs on a stale value. CBOE is ~15min delayed, so expected/critical leave
    # headroom above that; market_data + intraday freeze aging outside the
    # session so the last close is not flagged when the market is simply shut.
    {
        "table_name": "price_cache",
        "date_column": "quote_time",
        "expected_hours": 0.5,
        "critical_hours": 1.0,
        "market_data": True,
        "intraday": True,
        "where_clause": "UPPER(symbol) = '^VIX' AND quote_time IS NOT NULL",
    },
    # Current-session intraday bars behind the scanner's "Today" trendline. The
    # background cron refreshes hourly, so expected_hours 1.0 means the open Data
    # Feed reads "Current" right after a pull and tips to stale ~an hour later,
    # driving a foreground top-up while the PWA is open. market_data + intraday
    # age it against wall-clock during the session and freeze aging once the
    # market closes, so the last session's bars are not flagged overnight.
    {
        "table_name": "intraday_bars",
        "date_column": "ts",
        "expected_hours": 1.0,
        "critical_hours": 3.0,
        "market_data": True,
        "intraday": True,
    },
]
