"""Celery Beat periodic task schedules.

This module contains all periodic task definitions for Celery Beat.
Extracted from celery_app.py to improve maintainability and readability.

REFRESH ARCHITECTURE:
---------------------
Backend refresh (expensive API calls): Controlled by user preferences
  - Global default: default_refresh_minutes (15 min default)
  - Per-feature overrides: watchlist_refresh_override, portfolio_refresh_override, news_refresh_override
  - Tasks check preference hierarchy: override → default → hardcoded fallback

Frontend polling (cheap DB reads): Fixed at 30 seconds for responsiveness
  - Controlled by frontend_poll_interval in user_preferences (default: 30s)
  - Independent of backend refresh schedule

PERIODIC TASK TYPES:
--------------------
1. User-Configurable Backend Refresh (respects preferences)
   - Watchlist scores: polls every 60s, honors user's refresh_interval
   - Portfolio analytics: (future) polls every 60s, honors user's refresh_interval
   - News sentiment: (future) polls every 60s, honors user's refresh_interval

2. Static Schedules (not configurable)
   - Paper trades update: Daily at 4:30 PM ET (market close + 30 min)
   - Data cleanup: Weekly on Sunday 2:00 AM

DESIGN RATIONALE:
-----------------
Why separate polling (60s) from execution (15+ min)?
  - Beat is cheap (schedule check only)
  - Task execution is expensive (DB queries, API calls)
  - Decoupling allows dynamic adjustment without Beat restart
  - Task can decide to skip execution based on runtime conditions

PREVIOUSLY DISABLED TASKS (now fixed):
--------------------------------------
  - fetch-putcall-ratio: Was disabled due to CBOE HTTP 403 blocks.
    Fixed 2025-12-01: Now uses yfinance options chains (SPY+QQQ+IWM aggregate).
    See backend/app/tasks/market_data/options_pipeline.py for implementation.

MARKET HOURS AWARENESS:
-----------------------
The system is market-hours aware to prevent thrashing on weekends/holidays:

1. Data Freshness Monitoring (data_freshness_service.py):
   - Uses market-aware age calculation for market_data tables
   - On weekends, data from Friday is considered "fresh" (not stale)
   - Skips remediation alerts for market data when market is closed

2. Remediation Thrashing Protection:
   - Cooldown period: 30 minutes between remediation attempts per table
   - Market check: Won't trigger market data remediation when market closed
   - Cooldowns clear on successful data refresh

3. Holiday Calendar:
   - Full NYSE/NASDAQ holiday support (2024-2026)
   - Early close days (1 PM close) handled separately
   - See app/utils/market_hours.py for complete calendar

4. API Endpoint:
   - GET /api/market/status - Returns current market status, last/next trading days
   - Used by frontend MarketStatusBadge component in navigation
"""

from typing import Any

from celery.schedules import crontab

from app.constants import ALL_MARKET_SYMBOLS

# Schedule intervals (seconds)
POLL_INTERVAL_60_SEC = 60.0  # Standard polling interval for user-configurable tasks
POLL_INTERVAL_30_MIN = 1800.0  # 30 minutes - reduced polling for API-heavy tasks
POLL_INTERVAL_12_HOURS = 43200.0  # 12 hours - for daily-ish tasks

# Task expiry times (seconds)
EXPIRY_2_MIN = 120  # Quick tasks that should be dropped if delayed
EXPIRY_10_MIN = 600  # 10-minute expiry for quick monitoring tasks
EXPIRY_28_MIN = 1700  # Slightly less than 30-min schedule
EXPIRY_30_MIN = 1800  # 30-minute expiry for moderate tasks
EXPIRY_50_MIN = 3000  # 50-minute expiry for longer tasks
EXPIRY_1_HOUR = 3600  # Longer-running tasks
EXPIRY_2_HOURS = 7200  # 2-hour expiry for daily cleanup tasks

# Fear & Greed lookback period (days)
FEAR_GREED_LOOKBACK_DAYS = 7

# Cleanup task retention periods
CLEANUP_LOGS_RETENTION_DAYS = 7
CLEANUP_TEMP_FILES_RETENTION_HOURS = 24
CLEANUP_NEWS_RETENTION_DAYS = 90
CLEANUP_AGENT_RUNS_RETENTION_DAYS = 30
CLEANUP_BACKUPS_KEEP_COUNT = 5
CLEANUP_MODELS_KEEP_COUNT = 3
CLEANUP_SOLUTION_STATE_RETENTION_DAYS = 14


def _create_intraday_refresh_tasks(
    time_label: str, hour: int, minute_offset: int = 0
) -> dict[str, dict[str, Any]]:
    """Generate intraday OHLCV → Fear/Greed inputs → F&G calculation task chain.

    Creates a 3-task pattern with 15-minute spacing:
    - :00 refresh_daily_ohlcv (OHLCV data)
    - :15 populate_fear_greed_inputs (F&G inputs)
    - :30 calculate_fear_greed (F&G calculation)

    Args:
        time_label: Identifier for the refresh period (e.g., "morning", "midday")
        hour: UTC hour to start the refresh chain
        minute_offset: Additional minutes to add to the base schedule (default 0)

    Returns:
        Dict of 3 Celery Beat task definitions
    """
    return {
        f"refresh-market-ohlcv-{time_label}": {
            "task": "refresh_daily_ohlcv",
            "schedule": crontab(hour=hour, minute=minute_offset),
            "args": [ALL_MARKET_SYMBOLS],
            "options": {"expires": EXPIRY_1_HOUR},
        },
        f"refresh-fear-greed-{time_label}": {
            "task": "populate_fear_greed_inputs",
            "schedule": crontab(hour=hour, minute=minute_offset + 15),
            "args": [FEAR_GREED_LOOKBACK_DAYS],
            "options": {"expires": EXPIRY_1_HOUR},
        },
        f"calculate-fear-greed-{time_label}": {
            "task": "calculate_fear_greed",
            "schedule": crontab(hour=hour, minute=minute_offset + 30),
            "args": [None],
            "options": {"expires": EXPIRY_1_HOUR},
        },
    }


def _maintenance_tasks() -> dict[str, dict[str, Any]]:
    """Automated maintenance tasks for system health.

    These tasks maintain system health through automated cleanup and monitoring.
    Includes log cleanup, temp file cleanup, database vacuum, news cleanup,
    agent run cleanup, orphaned data cleanup, backup cleanup, model cleanup,
    solution state cleanup, disk space checks, data source health, and database size tracking.

    Returns:
        Dict of Celery Beat task definitions for maintenance tasks
    """
    return {
        "maintain-data-freshness": {
            "task": "maintain_data_freshness",
            "schedule": crontab(hour="*/2"),  # Every 2 hours
            "options": {"expires": EXPIRY_1_HOUR},  # 1-hour expiry
        },
        "check-all-data-freshness": {
            "task": "check_all_data_freshness",
            "schedule": crontab(minute=0, hour="*/2"),  # Every 2 hours
            "options": {"expires": EXPIRY_1_HOUR},
        },
        "cleanup-old-logs-daily": {
            "task": "cleanup_old_logs_task",
            "schedule": crontab(hour=2, minute=0),  # Daily at 02:00 UTC
            "args": [CLEANUP_LOGS_RETENTION_DAYS],
            "options": {"expires": EXPIRY_1_HOUR},
        },
        "cleanup-temp-files-daily": {
            "task": "cleanup_temp_files_task",
            "schedule": crontab(hour=2, minute=15),  # Daily at 02:15 UTC
            "args": [CLEANUP_TEMP_FILES_RETENTION_HOURS],
            "options": {"expires": EXPIRY_1_HOUR},
        },
        "vacuum-database-weekly": {
            "task": "vacuum_database_task",
            "schedule": crontab(day_of_week=0, hour=3, minute=30),  # Sunday 03:30 UTC
            "args": [None],
            "options": {"expires": EXPIRY_2_HOURS},
        },
        "cleanup-old-news-weekly": {
            "task": "cleanup_old_news_task",
            "schedule": crontab(day_of_week=0, hour=4, minute=0),  # Sunday 04:00 UTC
            "args": [CLEANUP_NEWS_RETENTION_DAYS],
            "options": {"expires": EXPIRY_1_HOUR},
        },
        "cleanup-old-agent-runs-weekly": {
            "task": "cleanup_old_agent_runs_task",
            "schedule": crontab(day_of_week=0, hour=4, minute=15),  # Sunday 04:15 UTC
            "args": [CLEANUP_AGENT_RUNS_RETENTION_DAYS],
            "options": {"expires": EXPIRY_1_HOUR},
        },
        "cleanup-orphaned-data-weekly": {
            "task": "cleanup_orphaned_data_task",
            "schedule": crontab(day_of_week=0, hour=4, minute=30),  # Sunday 04:30 UTC
            "options": {"expires": EXPIRY_1_HOUR},
        },
        "cleanup-old-backups-weekly": {
            "task": "cleanup_old_backups_task",
            "schedule": crontab(day_of_week=0, hour=4, minute=45),  # Sunday 04:45 UTC
            "args": [CLEANUP_BACKUPS_KEEP_COUNT],
            "options": {"expires": EXPIRY_1_HOUR},
        },
        "cleanup-old-models-weekly": {
            "task": "cleanup_old_models_task",
            "schedule": crontab(day_of_week=0, hour=5, minute=0),  # Sunday 05:00 UTC
            "args": [CLEANUP_MODELS_KEEP_COUNT],
            "options": {"expires": EXPIRY_1_HOUR},
        },
        "cleanup-solution-state-weekly": {
            "task": "cleanup_solution_state_task",
            "schedule": crontab(day_of_week=0, hour=5, minute=15),  # Sunday 05:15 UTC
            "args": [CLEANUP_SOLUTION_STATE_RETENTION_DAYS],
            "options": {"expires": EXPIRY_1_HOUR},
        },
        "check-disk-space-periodic": {
            "task": "check_disk_space_task",
            "schedule": crontab(hour="*/6"),  # Every 6 hours
            "options": {"expires": EXPIRY_10_MIN},
        },
        "check-data-source-health-periodic": {
            "task": "check_data_source_health",
            "schedule": crontab(minute=30, hour="*/6"),  # Every 6 hours at :30
            "options": {"expires": EXPIRY_10_MIN},
        },
        "get-database-size-daily": {
            "task": "get_database_size_task",
            "schedule": crontab(hour=5, minute=30),  # Daily at 05:30 UTC
            "options": {"expires": EXPIRY_10_MIN},
        },
        "refresh-sec-cik-cache-weekly": {
            "task": "refresh_sec_cik_cache",
            "schedule": crontab(hour=6, minute=0, day_of_week=0),  # Weekly on Sunday at 06:00 UTC
            "options": {"expires": EXPIRY_1_HOUR},
        },
    }


def _agent_tasks() -> dict[str, dict[str, Any]]:
    """Autonomous AI agent tasks.

    Discovery Agent and Portfolio Analyzer generate investment ideas daily
    at 03:30 UTC to fulfill VISION.md requirement for autonomous scheduling.

    Returns:
        Dict of Celery Beat task definitions for AI agent tasks
    """
    return {
        "run-discovery-agent-daily": {
            "task": "run_discovery_agent",
            "schedule": crontab(hour=3, minute=30),  # Daily at 03:30 UTC
            "options": {"expires": EXPIRY_30_MIN},  # 30-minute expiry
        },
        "run-portfolio-analyzer-daily": {
            "task": "run_portfolio_analyzer",
            "schedule": crontab(hour=3, minute=30),  # Daily at 03:30 UTC
            "options": {"expires": EXPIRY_30_MIN},  # 30-minute expiry
        },
    }


def _user_configurable_tasks() -> dict[str, dict[str, Any]]:
    """User-configurable backend refresh tasks.

    These tasks poll frequently (60s) but honor user preference intervals.
    Task logic checks: last_refresh_time + user_interval < now → execute

    Returns:
        Dict of Celery Beat task definitions for user-configurable refreshes
    """
    return {
        "refresh-watchlist-scores": {
            "task": "refresh_watchlist_scores",
            "schedule": POLL_INTERVAL_60_SEC,
            "args": ["default"],  # account_id
            "options": {"expires": EXPIRY_2_MIN},
            # Notes:
            # - Task checks: watchlist_refresh_override → default_refresh_minutes → 15 min
            # - Skips execution if not enough time elapsed since last refresh
            # - Runs 24/7 to capture after-hours and weekend data
            # - Issue #4 fix: Uses Redis cache for watchlist symbols (60s TTL)
        },
        # Future: Portfolio analytics refresh
        # Note: Commented example for future implementation
        "refresh-news-sentiment": {
            "task": "refresh_news_sentiment",
            "schedule": POLL_INTERVAL_30_MIN,  # Was 65s - too aggressive, caused CPU spikes
            "args": ["default"],
            "options": {"expires": EXPIRY_28_MIN},  # Slightly less than schedule interval
            # Notes:
            # - Changed from 65s to 30min to reduce Gemini API load and CPU usage
            # - Task checks: news_refresh_override → default_refresh_minutes → 15 min
            # - Uses optimized JOIN query from Issue #5 fix
        },
    }


def get_beat_schedule() -> dict[str, dict[str, Any]]:
    """Get Celery Beat schedule configuration.

    Returns:
        dict: Beat schedule with all periodic tasks
    """
    return {
        # Merge user-configurable tasks
        **_user_configurable_tasks(),
        # ============================================================================
        # STATIC SCHEDULE TASKS (NOT CONFIGURABLE)
        # ============================================================================
        # These tasks run on fixed schedules regardless of user preferences
        # ============================================================================
        "update-paper-trades-daily": {
            "task": "update_paper_trades_task",
            "schedule": crontab(hour=21, minute=30),  # Daily at 21:30 UTC (4:30 PM ET)
            "options": {"expires": EXPIRY_1_HOUR},
            # Notes:
            # - Runs daily at 21:30 UTC (4:30 PM ET, market close + 30 min)
            # - Not configurable by user (business logic requirement)
        },
        "profile-news-sources": {
            "task": "profile_news_sources",
            "schedule": POLL_INTERVAL_12_HOURS,  # Configurable via user preferences
            "args": ["default"],  # user_id
            "options": {"expires": EXPIRY_1_HOUR},
            # Notes:
            # - Task checks: news_profiling_interval_hours preference (default 12h)
            # - Calculates 6 quality metrics per vendor (duplicate, diversity, confidence, freshness, user_feedback, quality)
            # - Stores results in source_metrics table
            # - Skips execution if not enough time elapsed since last profiling
        },
        "refresh-daily-ohlcv": {
            "task": "refresh_daily_ohlcv",
            "schedule": crontab(hour=2, minute=0),  # Daily at 02:00 UTC
            "args": [ALL_MARKET_SYMBOLS],  # From app.constants - SPY + indices + sector ETFs
            "options": {"expires": EXPIRY_1_HOUR},
            # Notes:
            # - Runs daily at 02:00 UTC
            # - Ensures SPY + market indicators + sector ETFs fresh for market intelligence
            # - Fetches last 5 days to account for holidays/weekends
            # - Symbol list: app.constants.ALL_MARKET_SYMBOLS (DRY principle)
        },
        "refresh-watchlist-ohlcv": {
            "task": "refresh_watchlist_ohlcv",
            "schedule": crontab(hour=2, minute=15),  # Daily at 02:15 UTC (after market indicators)
            "options": {"expires": EXPIRY_1_HOUR},
            # Notes:
            # - Runs daily at 02:15 UTC (15 min after refresh-daily-ohlcv)
            # - Automatically fetches all symbols from watchlist_items table
            # - Fetches last 5 days to account for holidays/weekends
            # - Ensures watchlist OHLCV data stays fresh daily
            # - Idempotent: Safe to run multiple times
            # - Self-healing: Replaces stale data with fresh data
        },
        "retrain-article-quality-model": {
            "task": "retrain_article_quality_model",
            "schedule": crontab(hour=5, minute=0),  # Daily at 05:00 UTC
            "options": {"expires": EXPIRY_2_HOURS},  # Task expires after 2 hours
            # Notes:
            # - Runs daily at 05:00 UTC (after all market data tasks complete)
            # - Queries 100 newest unlabeled articles from news_cache
            # - Labels them with Gemini for quality assessment
            # - Retrains sklearn model with accumulated training data
            # - Updates production model if accuracy improves
            # - Stores metrics in ml_model_metrics table
            # - Runs daily to keep model fresh with evolving news patterns
        },
        "update-technical-indicators-daily": {
            "task": "backfill_technical_indicators",
            "schedule": crontab(hour=2, minute=30),  # Daily at 02:30 UTC
            "args": [
                None,
                50,
            ],  # backfill_technical_indicators(symbols=None, batch_size=50) - auto-discovers all symbols
            "options": {"expires": EXPIRY_1_HOUR},  # Task expires after 1 hour
            # Notes:
            # - Changed from update_technical_indicators to backfill_technical_indicators
            # - Runs daily at 02:30 UTC (after OHLCV refresh at 02:00)
            # - Auto-discovers ALL symbols from day_bars table
            # - Calculates indicators for any missing dates (catch-up + new dates)
            # - Permanent fix: ensures indicators stay in sync with OHLCV data
            # - Must run after refresh-daily-ohlcv completes
        },
        "populate-fear-greed-inputs-daily": {
            "task": "populate_fear_greed_inputs",
            "schedule": crontab(hour=2, minute=45),  # Daily at 02:45 UTC
            "args": [FEAR_GREED_LOOKBACK_DAYS],  # Update last N days
            "options": {"expires": EXPIRY_1_HOUR},  # Task expires after 1 hour
            # Notes:
            # - Runs daily at 02:45 UTC (after indicators update at 02:30)
            # - Replaces manual update_fear_greed_inputs.py script
            # - Fetches SPY OHLCV and calculates SMA_200, RSI_14
            # - Fetches VIX if available, uses estimate if missing
            # - Populates fear_greed_inputs table (SPY, VIX, RSI data)
            # - Automatically triggers calculate_fear_greed after completion
            # - Idempotent: Safe to run multiple times
            # - Self-healing: Backfills missing dates within 7-day window
        },
        "calculate-fear-greed-daily": {
            "task": "calculate_fear_greed",
            "schedule": crontab(hour=3, minute=2),  # Daily at 03:02 UTC (staggered from 3:00)
            "args": [None],  # Calculate for latest available date
            "options": {"expires": EXPIRY_1_HOUR},  # Task expires after 1 hour
            # Notes:
            # - Runs daily at 03:02 UTC (after populate-fear-greed-inputs completes at 02:45)
            # - Calculates Fear & Greed Index from inputs table
            # - Uses 252-day rolling window for percentile rankings
            # - Must run after populate-fear-greed-inputs-daily completes
            # - Invalidates Redis cache automatically after successful calculation
        },
        # ============================================================================
        # INTRADAY REFRESH TASKS (generated via helper)
        # ============================================================================
        # Uses _create_intraday_refresh_tasks() for consistent 3-task pattern:
        # - refresh_daily_ohlcv → populate_fear_greed_inputs (+15m) → calculate_fear_greed (+30m)
        # ============================================================================
        # 10:00 AM ET (15:00 UTC) - Morning refresh for TODAY's data
        **_create_intraday_refresh_tasks("morning", hour=15),
        # 12:00 PM ET (17:00 UTC) - Midday refresh with meaningful half-day signals
        **_create_intraday_refresh_tasks("midday", hour=17),
        "update-fear-greed-after-close": {
            "task": "populate_fear_greed_inputs",
            "schedule": crontab(hour=21, minute=45),  # Daily at 21:45 UTC (4:45 PM ET, after close)
            "args": [FEAR_GREED_LOOKBACK_DAYS],
            "options": {"expires": EXPIRY_1_HOUR},
            # Notes:
            # - Runs after market close (16:00 ET) to catch final closing data
            # - Ensures Fear & Greed reflects end-of-day market conditions
        },
        "calculate-fear-greed-after-close": {
            "task": "calculate_fear_greed",
            "schedule": crontab(hour=22, minute=0),  # Daily at 22:00 UTC (5:00 PM ET)
            "args": [None],
            "options": {"expires": EXPIRY_1_HOUR},
            # Notes:
            # - Calculates F&G with end-of-day data
            # - Invalidates Redis cache for immediate fresh data
        },
        "maintain-historical-market-data": {
            "task": "maintain_historical_market_data",
            "schedule": crontab(hour=4, minute=15),  # Daily at 04:15 UTC
            "options": {"expires": EXPIRY_1_HOUR},  # Task expires after 1 hour
            # Notes:
            # - Runs daily at 04:15 UTC (after yfinance reference data at 04:00)
            # - Maintains 1260 trading days (5 years) for backtesting across market cycles
            # - DYNAMICALLY includes: market symbols + ALL watchlist symbols
            # - Idempotent: Checks if data exists, backfills if needed, adds new day if current
            # - Self-healing: Automatically fixes missing or stale data
            # - New watchlist symbols automatically get 5-year backfill on next run
            # - NO MANUAL BACKFILLING NEEDED - task handles all data maintenance
        },
        "refresh-yfinance-reference": {
            "task": "refresh_yfinance_reference_data",
            "schedule": crontab(hour=4, minute=0),  # Daily at 04:00 UTC
            "options": {"expires": EXPIRY_1_HOUR},  # Task expires after 1 hour
            # Notes:
            # - Runs daily at 04:00 UTC
            # - Fetches reference data (including valuation metrics) from yfinance
            # - Updates reference_cache table for all watchlist symbols
            # - Includes P/E, P/B, P/S, PEG, dividend yield, payout ratio
            # - Also fetches bonus metrics: EPS, margins, growth rates, ratios
        },
        "parse-valuation-metrics": {
            "task": "parse_valuation_metrics",
            "schedule": crontab(hour=4, minute=30),  # Daily at 04:30 UTC (after fetch)
            "options": {"expires": EXPIRY_1_HOUR},  # Task expires after 1 hour
            # Notes:
            # - Runs daily at 04:30 UTC (30 minutes after yfinance reference fetch)
            # - Extracts valuation metrics from JSON payloads in reference_cache
            # - Populates structured columns: pe_ratio_trailing, pe_ratio_forward, etc.
            # - Idempotent: Safe to run multiple times
        },
        "refresh-alphavantage-reference-backup": {
            "task": "refresh_alphavantage_reference_backup",
            "schedule": crontab(hour=4, minute=45),  # Daily at 04:45 UTC (after yfinance + parsing)
            "options": {"expires": EXPIRY_1_HOUR},  # Task expires after 1 hour
            # Notes:
            # - Runs daily at 04:45 UTC (after yfinance refresh at 04:00 and parsing at 04:30)
            # - Fetches Alpha Vantage OVERVIEW data as backup for symbols with missing/stale yfinance data
            # - Only processes symbols where yfinance data is missing or >7 days old
            # - Rate limited: 500 calls/day, 5 calls/min (free tier)
            # - Provides 15/16 valuation metrics (missing only payout_ratio, but calculated if possible)
            # - Idempotent: Safe to run multiple times
            # - Self-healing: Automatically fills gaps in valuation data coverage
        },
        "update-earnings-surprises-weekly": {
            "task": "update_earnings_surprises",
            "schedule": crontab(hour=5, minute=0, day_of_week=0),  # Sundays at 05:00 UTC
            "options": {"expires": EXPIRY_2_HOURS},  # Task expires after 2 hours
            # Notes:
            # - Runs weekly on Sundays at 05:00 UTC (GAP-003)
            # - Fetches earnings surprise data (EPS estimate vs actual) from Finnhub
            # - Auto-discovers all watchlist + portfolio symbols
            # - Weekly is sufficient since earnings are quarterly events
            # - Data stored in earnings_surprises table
            # - Used for signal classification (consistent beats = bullish)
        },
        "refresh-analyst-revisions-daily": {
            "task": "refresh_analyst_revisions",
            "schedule": crontab(hour=7, minute=0),  # Daily at 07:00 UTC
            "options": {"expires": EXPIRY_1_HOUR},  # Task expires after 1 hour
            # Notes:
            # - Runs daily at 07:00 UTC (GAP-005: analyst estimate revisions)
            # - Fetches EPS/revenue estimates from FMP API
            # - Tracks revisions over time (7d, 30d, 90d ago)
            # - Calculates revision direction and magnitude
            # - Used for earnings momentum signals (upgrades = bullish)
        },
        "refresh-financial-health-scores-weekly": {
            "task": "refresh_financial_health_scores",
            "schedule": crontab(hour=5, minute=0, day_of_week=0),  # Sundays at 05:00 UTC
            "options": {"expires": EXPIRY_2_HOURS},  # Task expires after 2 hours
            # Notes:
            # - Runs weekly on Sundays at 05:00 UTC (GAP-008, GAP-009)
            # - Calculates Piotroski F-Score (9-point quality metric)
            # - Calculates Altman Z-Score (bankruptcy prediction)
            # - Uses yfinance balance sheet and income statement data
            # - Scores stored in reference_cache (f_score, z_score columns)
            # - Weekly is sufficient since financials update quarterly
        },
        "refresh-risk-metrics-daily": {
            "task": "refresh_risk_metrics",
            "schedule": crontab(hour=5, minute=30),  # Daily at 05:30 UTC
            "options": {"expires": EXPIRY_1_HOUR},  # Task expires after 1 hour
            # Notes:
            # - Runs daily at 05:30 UTC (GAP-027, GAP-022)
            # - Calculates VaR/CVaR (historical simulation method)
            # - Calculates multi-window betas (90d, 1y, 2y)
            # - Requires day_bars data for historical returns
            # - Stores in symbol_risk_metrics table
            # - Uses SPY as market proxy for beta calculation
        },
        "ingest-fundamental-data-weekly": {
            "task": "app.tasks.ingestion.fundamental_ingestion.ingest_fundamental_data",
            "schedule": crontab(hour=6, minute=0, day_of_week=0),  # Sundays at 06:00 UTC
            "options": {"expires": EXPIRY_2_HOURS},  # Task expires after 2 hours
            # Notes:
            # - Runs weekly on Sundays at 06:00 UTC
            # - Fetches and stores (GAP-004, 006, 007, 011):
            #   * Cash flow metrics (FCF, OCF, FCF yield)
            #   * Insider transactions
            #   * Institutional holdings
            #   * Short interest
            # - Uses yfinance as data source
            # - Weekly is sufficient since data updates quarterly/bi-weekly
        },
        "fetch-corporate-actions-weekly": {
            "task": "tasks.fetch_corporate_actions",
            "schedule": crontab(hour=6, minute=30, day_of_week=0),  # Sundays at 06:30 UTC
            "options": {"expires": EXPIRY_2_HOURS},  # Task expires after 2 hours
            # Notes:
            # - Runs weekly on Sundays at 06:30 UTC (FEAT-175)
            # - Fetches share buyback data from yfinance cash flow
            # - Uses quarterly_cashflow 'Repurchase Of Capital Stock' row
            # - Stores in corporate_actions table
            # - Weekly is sufficient since buybacks update quarterly
        },
        "ingest-macro-indicators-daily": {
            "task": "app.tasks.ingestion.fundamental_ingestion.ingest_macro_indicators",
            "schedule": crontab(hour=6, minute=30),  # Daily at 06:30 UTC
            "options": {"expires": EXPIRY_1_HOUR},  # Task expires after 1 hour
            # Notes:
            # - Runs daily at 06:30 UTC
            # - Fetches and stores (GAP-034, 035, 036):
            #   * Yield curve (3M, 2Y, 5Y, 10Y, 30Y, spreads)
            #   * Inflation data (CPI, PCE, breakevens)
            #   * Fed funds rate (FEDFUNDS, EFFR)
            # - Uses FRED API as data source
            # - Requires FRED_API_KEY environment variable
        },
        "fetch-options-activity-daily": {
            "task": "fetch_options_activity_metrics",
            "schedule": crontab(hour=21, minute=15),  # Daily at 21:15 UTC (4:15 PM ET)
            "options": {"expires": EXPIRY_1_HOUR},  # Task expires after 1 hour
            # Notes:
            # - Runs daily at 21:15 UTC (4:15 PM ET, after market close at 4:00 PM)
            # - Scrapes CBOE Most Active Options page
            # - Calculates aggregated metrics:
            #   * Call/put sentiment (% calls in top 25)
            #   * Time horizon (% near-term ≤30 days)
            #   * Concentration (% volume in top 5)
            #   * Sector distribution
            # - Stores in options_market_metrics table
            # - Used for market positioning intelligence
        },
        "fetch-putcall-ratio-market-open": {
            "task": "fetch_putcall_ratio",
            "schedule": crontab(hour=14, minute=30),  # Daily at 14:30 UTC (9:30 AM ET)
            "options": {"expires": EXPIRY_1_HOUR},  # Task expires after 1 hour
            # Notes:
            # - Runs at market open to capture overnight sentiment
            # - Uses yfinance options chains (SPY+QQQ+IWM aggregate)
            # - Replaced CBOE source which was blocked (HTTP 403)
            # - Stores put_call_ratio in fear_greed_inputs table
        },
        "fetch-putcall-ratio-market-close": {
            "task": "fetch_putcall_ratio",
            "schedule": crontab(hour=21, minute=30),  # Daily at 21:30 UTC (4:30 PM ET)
            "options": {"expires": EXPIRY_1_HOUR},  # Task expires after 1 hour
            # Notes:
            # - Runs after market close to capture final daily sentiment
            # - Uses yfinance options chains (SPY+QQQ+IWM aggregate)
            # - Overwrites market-open value with end-of-day data
            # - Stores put_call_ratio in fear_greed_inputs table
        },
        # Note: Tasks at 03:XX UTC are deliberately staggered to prevent resource contention:
        # - 03:00 scan-system-capabilities (anchor)
        # - 03:02 calculate-fear-greed-daily
        # - 03:05 monitor-thesis-health-daily, scan-feature-capabilities
        # - 03:08 daily-rules-validation
        # - 03:10 weekly-optimization-review (Monday only)
        "scan-system-capabilities": {
            "task": "scan_system_capabilities",
            "schedule": crontab(
                hour=3, minute=0
            ),  # Daily at 03:00 UTC (anchor for staggered tasks)
            "options": {"expires": EXPIRY_30_MIN},  # Task expires after 30 minutes
            # Notes:
            # - Runs daily at 03:00 UTC (after data refresh tasks complete)
            # - Auto-discovers all system capabilities:
            #   * Database tables (row counts, completeness, freshness)
            #   * Celery scheduled tasks (schedules, success rates)
            #   * API endpoints (paths, dependencies)
            # - Stores results in capability registry tables:
            #   * db_capabilities
            #   * celery_capabilities
            #   * api_capabilities
            # - Enables AI-powered monitoring and gap detection
            # - Critical for preventing AI agents from breaking features
        },
        "scan-feature-capabilities": {
            "task": "scan_feature_capabilities",
            "schedule": crontab(hour=3, minute=5),  # Daily at 03:05 UTC
            "options": {"expires": EXPIRY_30_MIN},  # Task expires after 30 minutes
            # Notes:
            # - Runs daily at 03:05 UTC (5 minutes after system capability scan)
            # - Scans feature_capabilities and feature_tasks tables
            # - Calculates completion percentages from subtasks
            # - Updates health_status (active/suspect/orphaned)
            # - Detects inconsistencies (passes=true but tasks incomplete)
            # - Enables /capabilities → Features tab monitoring
        },
        # AI analyzer and gap detection tasks removed - migrated to [DEBT] subtasks on features
        # See tasks/tasks-tech-debt-to-feature-subtasks-migration.md
        # ============================================================================
        # QA SYSTEM DAILY SCANS
        # ============================================================================
        # Daily automated QA scanning for code quality issues
        # ============================================================================
        "daily-qa-scan": {
            "task": "tasks.daily_qa_scan",
            "schedule": crontab(hour=4, minute=30),  # Daily at 04:30 UTC
            "options": {"expires": EXPIRY_1_HOUR},  # Task expires after 1 hour
            # Notes:
            # - Runs daily at 04:30 UTC (after capability scans complete at 03:00-03:05)
            # - Scans for 6 issue categories:
            #   * dead_code: Unused functions/classes/imports
            #   * orphan_file: Unreferenced files
            #   * schema_drift: Model vs DB mismatches
            #   * stale_data: Tables not updated recently
            #   * bloat: Functions/files exceeding size limits
            #   * test_gap: Untested code
            # - Upserts detected issues into qa_issues table
            # - Auto-resolves issues no longer detected
            # - Takes daily snapshot for trend tracking
            # - Enables /qa dashboard monitoring
        },
        # ============================================================================
        # ACCEPTANCE CRITERIA AUTO-VERIFICATION
        # ============================================================================
        # These tasks auto-verify API/test/UI criteria on a schedule
        # ============================================================================
        "verify-acceptance-criteria": {
            "task": "verify_all_acceptance_criteria",
            "schedule": crontab(hour=5, minute=0, day_of_week=0),  # Weekly on Sunday at 05:00 UTC
            "options": {"expires": EXPIRY_2_HOURS},  # 2 hour expiry for thorough check
            # Notes:
            # - Changed from daily to weekly to reduce Playwright/browser load
            # - On-demand available via POST /api/capabilities/verify-all
            # - Auto-verifies acceptance criteria by type:
            #   * API criteria: Makes HTTP requests, checks status codes
            #   * Test criteria: Runs pytest tests
            #   * UI criteria: Takes screenshots via browser automation
            # - Updates passed/verified_at/verification_output in database
        },
        # Daily gap analysis workflow removed - migrated to feature-based tracking
        # Merge autonomous AI agent tasks
        **_agent_tasks(),
        # Merge automated maintenance tasks
        **_maintenance_tasks(),
        # ============================================================================
        # STRATEGY MONITORING & GENERATION (Task 4.8)
        # ============================================================================
        "evaluate-strategy-performance": {
            "task": "app.tasks.strategy_monitoring_tasks.evaluate_strategy_performance",
            "schedule": crontab(hour=4, minute=0),  # Daily at 04:00 UTC
            "options": {"expires": EXPIRY_1_HOUR},
            # Notes:
            # - Evaluates all active strategies daily
            # - Calculates 30-day rolling metrics (Sharpe, win rate, drawdown)
            # - Archives strategies with <70% expected performance for >30 days
            # - Updates strategy_performance table with daily metrics
        },
        "auto-promote-strategies": {
            "task": "app.tasks.strategy_monitoring_tasks.auto_promote_strategies",
            "schedule": crontab(hour=4, minute=15),  # Daily at 04:15 UTC (after evaluation)
            "options": {"expires": EXPIRY_1_HOUR},
            # Notes:
            # - Auto-promotes testing strategies to active after validation
            # - Criteria: 3+ days old, expected Sharpe >= 1.0, no blocking issues
            # - Runs after evaluate-strategy-performance to use fresh data
        },
        "generate-weekly-strategies": {
            "task": "app.tasks.strategy_monitoring_tasks.weekly_strategy_generation",
            "schedule": crontab(hour=5, minute=0, day_of_week=0),  # Sunday 05:00 UTC
            "options": {"expires": EXPIRY_2_HOURS},
            # Notes:
            # - Full sweep of top 20 watchlist symbols
            # - Skips symbols that already have active strategies
            # - Runs strategy_research_workflow for each symbol
            # - Commits generated strategies to git with research context
        },
        "weekly-strategy-evolution": {
            "task": "app.tasks.strategy_monitoring_tasks.weekly_strategy_evolution",
            "schedule": crontab(hour=6, minute=0, day_of_week=0),  # Sunday 06:00 UTC
            "options": {"expires": EXPIRY_2_HOURS},
            # Notes:
            # - Evolves underperforming strategies via LLM analysis
            # - Runs after weekly strategy generation (05:00)
            # - Finds strategies performing <90% of expected Sharpe
            # - LLM proposes mutations, tests via walk-forward backtest
            # - Saves best mutation if it beats MAS (90% parent OR buy-hold)
            # - Archives parent, creates child with lineage tracking
            # - Limit: 5 strategies per week to control costs
        },
        "daily-strategy-refresh": {
            "task": "app.tasks.strategy_monitoring_tasks.daily_strategy_refresh",
            "schedule": crontab(hour=5, minute=15),  # Daily at 05:15 UTC
            "options": {"expires": EXPIRY_1_HOUR},
            # Notes:
            # - Runs daily to catch new symbols and replace underperformers
            # - Generates max 5 strategies per day (cost control)
            # - Only for: symbols without strategy OR underperforming (Sharpe < 0.5)
            # - More responsive than weekly-only approach
        },
        "generate-daily-strategy-signals": {
            "task": "app.tasks.strategy_signal_tasks.generate_daily_strategy_signals",
            "schedule": crontab(hour=21, minute=30),  # Daily at 21:30 UTC (after US market close)
            "options": {"expires": EXPIRY_1_HOUR},
            # Notes:
            # - Generates trading signals for all active strategies
            # - Evaluates current market data against strategy parameters
            # - Stores signals in strategy_signals table
            # - BUY signals can trigger auto paper trading (if enabled)
        },
        "auto-paper-trade-from-signals": {
            "task": "app.tasks.strategy_signal_tasks.auto_paper_trade_from_signals",
            "schedule": crontab(hour=21, minute=45),  # Daily at 21:45 UTC (after signals)
            "options": {"expires": EXPIRY_1_HOUR},
            # Notes:
            # - Creates paper trades from BUY signals with strength >= 5
            # - Skips if open position already exists for strategy+symbol
            # - Links trades to strategies via strategy_id
            # - Runs 15 minutes after signal generation to ensure signals are stored
        },
        # ============================================================================
        # PORTFOLIO RISK ANALYTICS (GAP-020)
        # ============================================================================
        "update-portfolio-covariance-daily": {
            "task": "update_portfolio_covariance",
            "schedule": crontab(hour=5, minute=30),  # Daily at 05:30 UTC
            "options": {"expires": EXPIRY_1_HOUR},
            # Notes:
            # - Runs daily at 05:30 UTC (after OHLCV data refresh completes)
            # - Calculates pairwise covariance matrix for all watchlist/portfolio symbols
            # - Uses 252-day (1 year) lookback for statistical significance
            # - Enables proper portfolio volatility calculation: sigma = sqrt(w' * Cov * w)
            # - Fixes GAP-020: Wrong portfolio risk math using weighted average
            # - Results cached in portfolio_covariance table for 24 hours
        },
        # ============================================================================
        # PORTFOLIO DRAWDOWN TRACKING (GAP-023)
        # ============================================================================
        "save-portfolio-snapshots-daily": {
            "task": "save_portfolio_snapshots",
            "schedule": crontab(hour=21, minute=30),  # Daily at 21:30 UTC (4:30 PM ET)
            "options": {"expires": EXPIRY_30_MIN},
            # Notes:
            # - Runs daily at 21:30 UTC (30 min after market close at 4 PM ET)
            # - Saves equity snapshots for all portfolio accounts
            # - Tracks peak equity and calculates drawdown from peak
            # - Enables portfolio-level trading halt at -10% drawdown
            # - Historical snapshots enable equity curve visualization
            # - Fixes GAP-023: No drawdown tracking
        },
        # ============================================================================
        # WATCHLIST AUTOMATION (Tasks 0098)
        # ============================================================================
        # Discovery and trimming of watchlist based on market signals
        # ============================================================================
        "discover-watchlist-candidates-daily": {
            "task": "discover_watchlist_candidates",
            "schedule": crontab(hour=8, minute=0),  # Daily at 08:00 UTC (3 AM ET)
            "options": {"expires": EXPIRY_30_MIN},
            # Notes:
            # - Discovers high-potential symbols from top gainers, volume spikes, news
            # - Scoring: gainers (0-4), volume (0-4), news mentions (0-4) = 0-12
            # - Threshold: discovery_score >= 6.0 (from rules.yaml)
            # - Limits: Max 5 additions per day, respects max watchlist size (50)
            # - Source tracking: source="discovery", auto_added=true
        },
        "trim-underperforming-watchlist-daily": {
            "task": "trim_underperforming_watchlist",
            "schedule": crontab(hour=8, minute=30),  # Daily at 08:30 UTC (30 min after discovery)
            "options": {"expires": EXPIRY_30_MIN},
            # Notes:
            # - Removes underperforming symbols after minimum hold period
            # - Criteria: avg_score < 4.0 AND days_watched >= 7
            # - Excludes symbols owned in portfolio positions
            # - Limits: Max 3 removals per day to prevent mass deletion
            # - Can be disabled via rules.yaml: auto_trim_enabled: false
        },
        "generate-watchlist-daily-report": {
            "task": "generate_daily_watchlist_report",
            "schedule": crontab(hour=9, minute=0),  # Daily at 09:00 UTC (after discovery and trim)
            "options": {"expires": EXPIRY_30_MIN},
            # Notes:
            # - Generates daily summary of watchlist changes
            # - Tracks: symbols added, symbols removed, significant score changes (>10 points)
            # - Stores report in watchlist_daily_reports table
            # - Runs after discovery (08:00) and trim (08:30) complete
            # - Used by frontend WatchlistDailyReport component
        },
        # ============================================================================
        # RULES VALIDATION & OPTIMIZATION (Tier 3 Task 3.0)
        # ============================================================================
        # AI-powered validation of trading rules configuration
        # ============================================================================
        "daily-rules-validation": {
            "task": "daily_rules_validation",
            "schedule": crontab(hour=3, minute=8),  # Daily at 03:08 UTC (staggered from 3:00)
            "options": {"expires": EXPIRY_10_MIN},
            # Notes:
            # - Validates all trading rules for logical consistency
            # - Checks: threshold ranges, contradictions, position sizing, fee assumptions
            # - Alerts on critical failures via maintenance_log
            # - Ensures rules configuration doesn't break trading logic
        },
        "weekly-optimization-review": {
            "task": "weekly_optimization_review",
            "schedule": crontab(hour=3, minute=10, day_of_week=1),  # Monday 03:10 UTC (staggered)
            "options": {"expires": EXPIRY_30_MIN},
            # Notes:
            # - Analyzes recent trading performance vs rules configuration
            # - Identifies unused rules and threshold tuning opportunities
            # - Generates optimization recommendations
            # - Runs weekly to avoid over-fitting to short-term noise
        },
        # ============================================================================
        # ARTIFACT LIFECYCLE TASKS
        # ============================================================================
        "refresh-expired-artifacts": {
            "task": "refresh_expired_artifacts",
            "schedule": crontab(hour=5, minute=30),  # Daily at 05:30 UTC
            "options": {"expires": EXPIRY_1_HOUR},
            # Notes:
            # - Marks expired UI verification artifacts as needing refresh
            # - Runs daily during low-activity hours
            # - Artifacts expire 24 hours after capture
        },
        "cleanup-old-artifact-versions": {
            "task": "cleanup_old_versions",
            "schedule": crontab(hour=6, minute=0),  # Daily at 06:00 UTC
            "options": {"expires": EXPIRY_1_HOUR},
            "kwargs": {"max_versions": 5, "dry_run": False},
            # Notes:
            # - Deletes old artifact versions beyond retention limit
            # - Keeps last 5 versions per feature/criterion
            # - Runs after refresh task completes
        },
        "cleanup-debug-captures": {
            "task": "cleanup_debug_captures",
            "schedule": crontab(hour=6, minute=15),  # Daily at 06:15 UTC
            "options": {"expires": EXPIRY_1_HOUR},
            "kwargs": {"max_age_days": 7, "dry_run": False},
            # Notes:
            # - Deletes DBG-* debug capture directories older than 7 days
            # - These are ad-hoc screenshots that don't need long retention
            # - Runs after artifact version cleanup
        },
        # ============================================================================
        # THESIS MONITORING & AUTOMATION (Task portfolio-ai-1ub)
        # ============================================================================
        # Automated thesis health monitoring, invalidation, and watchlist management
        # Thesis invalidation drives strategy lifecycle (not the other way around)
        # ============================================================================
        "monitor-thesis-health-daily": {
            "task": "monitor_thesis_health",
            "schedule": crontab(hour=3, minute=5),  # Daily at 03:05 UTC (staggered from 3:00)
            "options": {"expires": EXPIRY_30_MIN},  # 30-minute expiry
            # Notes:
            # - Evaluates invalidation triggers for all active theses
            # - Critical triggers (signal change, low cross-val): Invalidate thesis
            # - Non-critical triggers (sentiment shift): Flag for review
            # - Logs all actions to maintenance_log for audit trail
            # - Runs after fear/greed calculation (02:45-03:02)
        },
        "process-invalidated-theses-daily": {
            "task": "process_invalidated_theses",
            "schedule": crontab(hour=3, minute=15),  # Daily at 03:15 UTC (after health check)
            "options": {"expires": EXPIRY_30_MIN},
            # Notes:
            # - Processes recently invalidated theses (last 24 hours)
            # - Respects rules.yaml: auto_remove_on_invalidation (true/false)
            # - Excludes portfolio holdings (exclude_portfolio_holdings: true)
            # - Daily removal limit: max_daily_removals (default 3)
            # - Uses existing remove_symbol_from_watchlist (triggers deletion_audit)
        },
        "archive-strategies-for-invalidated-theses": {
            "task": "archive_strategies_for_invalidated_theses",
            "schedule": crontab(hour=3, minute=30),  # Daily at 03:30 UTC (after processing)
            "options": {"expires": EXPIRY_30_MIN},
            # Notes:
            # - Archives all active strategies for invalidated thesis symbols
            # - Design: Thesis invalidation TRIGGERS strategy archival (not vice versa)
            # - Uses existing strategy archive pattern (sets status='archived')
            # - Logs strategy archival to maintenance_log for audit trail
        },
        # ============================================================================
        # SITEMAP HEALTH MONITORING
        # ============================================================================
        # Dynamic endpoint discovery and health monitoring for all URLs
        # ============================================================================
        "check-sitemap-health-morning": {
            "task": "check_sitemap_health",
            "schedule": crontab(hour=8, minute=0),  # Daily at 08:00 UTC (3 AM ET)
            "options": {"expires": EXPIRY_50_MIN},  # 50-minute expiry
            # Notes:
            # - HTTP-only reachability check for all sitemap entries (no Playwright)
            # - Runs 2x daily (morning + evening) instead of hourly to reduce load
            # - On-demand available via POST /api/sitemap/check-all
        },
        "check-sitemap-health-evening": {
            "task": "check_sitemap_health",
            "schedule": crontab(hour=20, minute=0),  # Daily at 20:00 UTC (3 PM ET)
            "options": {"expires": EXPIRY_50_MIN},
        },
        "discover-sitemap-entries-daily": {
            "task": "discover_sitemap_entries",
            "schedule": crontab(hour=3, minute=30),  # Daily at 03:30 UTC
            "options": {"expires": EXPIRY_30_MIN},  # 30-minute expiry
            # Notes:
            # - Discovers new endpoints from OpenAPI (/openapi.json) and frontend crawler
            # - Imports from existing api_capabilities table
            # - Runs daily to catch new pages/endpoints after deploys
        },
        "cleanup-sitemap-history-daily": {
            "task": "cleanup_sitemap_history",
            "schedule": crontab(hour=4, minute=0),  # Daily at 04:00 UTC
            "options": {"expires": EXPIRY_10_MIN},  # 10-minute expiry
            # Notes:
            # - Deletes health history older than 7 days
            # - Keeps sitemap_health_history table size manageable
            # - Can also be triggered manually from Status page maintenance section
        },
        # ============================================================================
        # FILE AUDIT SCAN
        # ============================================================================
        "scan-files-daily": {
            "task": "scan_files",
            "schedule": crontab(hour=7, minute=30),  # Daily at 07:30 UTC (2:30 AM ET)
            "options": {"expires": EXPIRY_30_MIN},  # 30-minute expiry
            # Notes:
            # - Scans codebase files for audit (LOC, staleness, bloat detection)
            # - Runs after heavy tasks complete (02:00-07:00 UTC)
            # - Can also be triggered manually via POST /api/files/scan
            # - Updates file_audit table with file metrics
        },
    }
