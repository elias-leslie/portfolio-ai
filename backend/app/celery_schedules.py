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

from celery.schedules import crontab

from app.constants import ALL_MARKET_SYMBOLS


def get_beat_schedule() -> dict[str, object]:
    """Get Celery Beat schedule configuration.

    Returns:
        dict: Beat schedule with all periodic tasks
    """
    return {
        # ============================================================================
        # USER-CONFIGURABLE BACKEND REFRESH TASKS
        # ============================================================================
        # These tasks poll frequently (60s) but honor user preference intervals
        # Task logic checks: last_refresh_time + user_interval < now → execute
        # ============================================================================
        "refresh-watchlist-scores": {
            "task": "refresh_watchlist_scores",
            "schedule": 60.0,  # Poll every 60 seconds (Beat check interval)
            "args": ["default"],  # account_id
            "options": {"expires": 120},  # Task expires after 2 minutes if not picked up
            # Notes:
            # - Task checks: watchlist_refresh_override → default_refresh_minutes → 15 min
            # - Skips execution if not enough time elapsed since last refresh
            # - Runs 24/7 to capture after-hours and weekend data
            # - Issue #4 fix: Uses Redis cache for watchlist symbols (60s TTL)
        },
        # Future: Portfolio analytics refresh
        # Note: Commented example for future implementation
        # "refresh-portfolio-analytics": {
        #     "task": "refresh_portfolio_analytics",  # noqa: ERA001
        #     "schedule": 60.0,  # Poll every 60 seconds  # noqa: ERA001
        #     "args": ["default"],  # noqa: ERA001
        #     "options": {"expires": 120},  # noqa: ERA001
        #     # Task checks: portfolio_refresh_override → default_refresh_minutes → 15 min
        # },
        "refresh-news-sentiment": {
            "task": "refresh_news_sentiment",
            "schedule": 65.0,  # Poll every 65 seconds (5s offset from watchlist)
            "args": ["default"],
            "options": {"expires": 120},
            # Notes:
            # - Task checks: news_refresh_override → default_refresh_minutes → 15 min
            # - 5-second offset reduces contention with watchlist refresh
            # - Still allows concurrent execution when both tasks need to run
            # - Uses optimized JOIN query from Issue #5 fix
        },
        # ============================================================================
        # STATIC SCHEDULE TASKS (NOT CONFIGURABLE)
        # ============================================================================
        # These tasks run on fixed schedules regardless of user preferences
        # ============================================================================
        "update-paper-trades-daily": {
            "task": "update_paper_trades_task",
            "schedule": crontab(hour=21, minute=30),  # Daily at 21:30 UTC (4:30 PM ET)
            "options": {"expires": 3600},  # Task expires after 1 hour
            # Notes:
            # - Runs daily at 21:30 UTC (4:30 PM ET, market close + 30 min)
            # - Not configurable by user (business logic requirement)
        },
        "profile-news-sources": {
            "task": "profile_news_sources",
            "schedule": 43200.0,  # Every 12 hours (configurable via user preferences)
            "args": ["default"],  # user_id
            "options": {"expires": 3600},  # Task expires after 1 hour
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
            "options": {"expires": 3600},  # Task expires after 1 hour
            # Notes:
            # - Runs daily at 02:00 UTC
            # - Ensures SPY + market indicators + sector ETFs fresh for market intelligence
            # - Fetches last 5 days to account for holidays/weekends
            # - Symbol list: app.constants.ALL_MARKET_SYMBOLS (DRY principle)
        },
        "refresh-watchlist-ohlcv": {
            "task": "refresh_watchlist_ohlcv",
            "schedule": crontab(hour=2, minute=15),  # Daily at 02:15 UTC (after market indicators)
            "options": {"expires": 3600},  # Task expires after 1 hour
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
            "options": {"expires": 7200},  # Task expires after 2 hours
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
            ],  # backfill_technical_indicators(tickers=None, batch_size=50) - auto-discovers all tickers
            "options": {"expires": 3600},  # Task expires after 1 hour
            # Notes:
            # - Changed from update_technical_indicators to backfill_technical_indicators
            # - Runs daily at 02:30 UTC (after OHLCV refresh at 02:00)
            # - Auto-discovers ALL tickers from day_bars table
            # - Calculates indicators for any missing dates (catch-up + new dates)
            # - Permanent fix: ensures indicators stay in sync with OHLCV data
            # - Must run after refresh-daily-ohlcv completes
        },
        "populate-fear-greed-inputs-daily": {
            "task": "populate_fear_greed_inputs",
            "schedule": crontab(hour=2, minute=45),  # Daily at 02:45 UTC
            "args": [7],  # Update last 7 days
            "options": {"expires": 3600},  # Task expires after 1 hour
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
            "schedule": crontab(hour=3, minute=0),  # Daily at 03:00 UTC
            "args": [None],  # Calculate for latest available date
            "options": {"expires": 3600},  # Task expires after 1 hour
            # Notes:
            # - Runs daily at 03:00 UTC (after populate-fear-greed-inputs completes at 02:45)
            # - Calculates Fear & Greed Index from inputs table
            # - Uses 252-day rolling window for percentile rankings
            # - Must run after populate-fear-greed-inputs-daily completes
            # - Invalidates Redis cache automatically after successful calculation
        },
        # Additional intraday runs to ensure data stays current
        "maintain-market-data-midday": {
            "task": "maintain_historical_market_data",
            "schedule": crontab(hour=17, minute=0),  # Daily at 17:00 UTC (12:00 PM ET, midday)
            "options": {"expires": 3600},
            # Notes:
            # - Midday check to catch intraday data updates and new watchlist symbols
            # - Ensures new symbols added during the day get 5-year backfill same day
            # - Self-healing: Catches any symbols that failed in morning run
        },
        "update-fear-greed-after-close": {
            "task": "populate_fear_greed_inputs",
            "schedule": crontab(hour=21, minute=45),  # Daily at 21:45 UTC (4:45 PM ET, after close)
            "args": [7],
            "options": {"expires": 3600},
            # Notes:
            # - Runs after market close (16:00 ET) to catch final closing data
            # - Ensures Fear & Greed reflects end-of-day market conditions
        },
        "calculate-fear-greed-after-close": {
            "task": "calculate_fear_greed",
            "schedule": crontab(hour=22, minute=0),  # Daily at 22:00 UTC (5:00 PM ET)
            "args": [None],
            "options": {"expires": 3600},
            # Notes:
            # - Calculates F&G with end-of-day data
            # - Invalidates Redis cache for immediate fresh data
        },
        "maintain-historical-market-data": {
            "task": "maintain_historical_market_data",
            "schedule": crontab(hour=4, minute=15),  # Daily at 04:15 UTC
            "options": {"expires": 3600},  # Task expires after 1 hour
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
            "options": {"expires": 3600},  # Task expires after 1 hour
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
            "options": {"expires": 3600},  # Task expires after 1 hour
            # Notes:
            # - Runs daily at 04:30 UTC (30 minutes after yfinance reference fetch)
            # - Extracts valuation metrics from JSON payloads in reference_cache
            # - Populates structured columns: pe_ratio_trailing, pe_ratio_forward, etc.
            # - Idempotent: Safe to run multiple times
        },
        "refresh-alphavantage-reference-backup": {
            "task": "refresh_alphavantage_reference_backup",
            "schedule": crontab(hour=4, minute=45),  # Daily at 04:45 UTC (after yfinance + parsing)
            "options": {"expires": 3600},  # Task expires after 1 hour
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
            "options": {"expires": 7200},  # Task expires after 2 hours
            # Notes:
            # - Runs weekly on Sundays at 05:00 UTC (GAP-003)
            # - Fetches earnings surprise data (EPS estimate vs actual) from Finnhub
            # - Auto-discovers all watchlist + portfolio tickers
            # - Weekly is sufficient since earnings are quarterly events
            # - Data stored in earnings_surprises table
            # - Used for signal classification (consistent beats = bullish)
        },
        "fetch-options-activity-daily": {
            "task": "fetch_options_activity_metrics",
            "schedule": crontab(hour=21, minute=15),  # Daily at 21:15 UTC (4:15 PM ET)
            "options": {"expires": 3600},  # Task expires after 1 hour
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
            "options": {"expires": 3600},  # Task expires after 1 hour
            # Notes:
            # - Runs at market open to capture overnight sentiment
            # - Uses yfinance options chains (SPY+QQQ+IWM aggregate)
            # - Replaced CBOE source which was blocked (HTTP 403)
            # - Stores put_call_ratio in fear_greed_inputs table
        },
        "fetch-putcall-ratio-market-close": {
            "task": "fetch_putcall_ratio",
            "schedule": crontab(hour=21, minute=30),  # Daily at 21:30 UTC (4:30 PM ET)
            "options": {"expires": 3600},  # Task expires after 1 hour
            # Notes:
            # - Runs after market close to capture final daily sentiment
            # - Uses yfinance options chains (SPY+QQQ+IWM aggregate)
            # - Overwrites market-open value with end-of-day data
            # - Stores put_call_ratio in fear_greed_inputs table
        },
        "scan-system-capabilities": {
            "task": "scan_system_capabilities",
            "schedule": crontab(hour=3, minute=0),  # Daily at 03:00 UTC
            "options": {"expires": 1800},  # Task expires after 30 minutes
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
        "analyze-capabilities": {
            "task": "analyze_capabilities",
            "schedule": crontab(hour=3, minute=15),  # Daily at 03:15 UTC (15 min after scan)
            "options": {"expires": 1800},  # Task expires after 30 minutes
            # Notes:
            # - Runs daily at 03:15 UTC (15 minutes after capability scan)
            # - Uses Claude AI to analyze capability data and identify:
            #   * Data quality issues (stale, incomplete, missing fields)
            #   * Missing capabilities (gaps in data sources, missing tasks)
            #   * Broken dependencies (tasks failing, endpoints broken)
            # - Stores insights in capability_insights table
            # - Filters insights by confidence threshold (default: 0.70)
            # - Provides actionable suggestions with file paths
            # - Critical for proactive monitoring before AI agents break things
        },
        # ============================================================================
        # TRADING INTELLIGENCE GAP DETECTION
        # ============================================================================
        # These tasks monitor and alert on data gaps that limit trading edge
        # ============================================================================
        "analyze-trading-gaps-daily": {
            "task": "analyze_trading_gaps",
            "schedule": crontab(hour=3, minute=25),  # Daily at 03:25 UTC (after capabilities)
            "options": {"expires": 900},  # Task expires after 15 minutes
            # Notes:
            # - Runs daily at 03:25 UTC (after capability analysis at 03:15)
            # - Identifies missing data capabilities needed for trading strategies
            # - Calculates coverage % per analysis type (technical, fundamental, etc.)
            # - Stores results in gap_analysis_history table for trending
            # - Critical for understanding what data limits trading edge
        },
        "track-gap-trends": {
            "task": "track_gap_trends",
            "schedule": crontab(hour=3, minute=28),  # Daily at 03:28 UTC (after gap analysis)
            "options": {"expires": 300},  # Task expires after 5 minutes
            # Notes:
            # - Runs daily at 03:28 UTC (3 minutes after gap analysis)
            # - Analyzes 30-day trends: coverage improvements, regressions
            # - Tracks: "Fundamental coverage improved 40% → 65% this month"
            # - Helps prioritize gap-filling efforts
        },
        "alert-critical-gaps": {
            "task": "alert_critical_gaps",
            "schedule": crontab(hour=3, minute=29),  # Daily at 03:29 UTC (before workflow)
            "options": {"expires": 300},  # Task expires after 5 minutes
            # Notes:
            # - Runs daily at 03:29 UTC (just before workflow at 03:30)
            # - Creates status log entries for:
            #   * P0 (critical) gaps blocking trading strategies
            #   * Analysis types with coverage <50%
            # - Alerts visible in system health dashboard
        },
        # ============================================================================
        # MULTI-AGENT WORKFLOW TASKS
        # ============================================================================
        # These tasks orchestrate collaboration between multiple AI agents
        # ============================================================================
        "daily-gap-analysis-workflow": {
            "task": "app.tasks.workflow_tasks.daily_gap_analysis_workflow",
            "schedule": crontab(hour=3, minute=30),  # Daily at 03:30 UTC (after gap alerts)
            "options": {"expires": 1800},  # Task expires after 30 minutes
            # Notes:
            # - Runs daily at 03:30 UTC (after gap alerts at 03:29)
            # - Multi-agent workflow:
            #   1. Gemini agent analyzes current market gaps
            #   2. Claude agent validates and enhances analysis
            #   3. Consensus mechanism resolves conflicts
            #   4. Generate final report and commit to git
            # - Infrastructure ready, awaiting agent execution implementation
            # - Part of Phase 3 autonomous trading intelligence
        },
        # ============================================================================
        # AUTONOMOUS AI AGENT TASKS
        # ============================================================================
        # Discovery Agent and Portfolio Analyzer generate investment ideas daily
        # at 03:30 UTC to fulfill VISION.md requirement for autonomous scheduling
        # ============================================================================
        "run-discovery-agent-daily": {
            "task": "run_discovery_agent",
            "schedule": crontab(hour=3, minute=30),  # Daily at 03:30 UTC
            "options": {"expires": 1800},  # 30-minute expiry
        },
        "run-portfolio-analyzer-daily": {
            "task": "run_portfolio_analyzer",
            "schedule": crontab(hour=3, minute=30),  # Daily at 03:30 UTC
            "options": {"expires": 1800},  # 30-minute expiry
        },
        # ============================================================================
        # AUTOMATED MAINTENANCE TASKS
        # ============================================================================
        # These tasks maintain system health through automated cleanup and monitoring
        # ============================================================================
        "maintain-data-freshness": {
            "task": "maintain_data_freshness",
            "schedule": crontab(hour="*/2"),  # Every 2 hours
            "options": {"expires": 3600},  # 1-hour expiry
        },
        "check-all-data-freshness": {
            "task": "check_all_data_freshness",
            "schedule": crontab(minute=0, hour="*/2"),  # Every 2 hours
            "options": {"expires": 3600},  # 1-hour expiry
            # Notes:
            # - Runs every 2 hours to monitor all critical tables
            # - Checks: day_bars, technical_indicators, fear_greed_inputs,
            #   fear_greed_daily, options_market_metrics, news_cache, reference_cache
            # - Creates maintenance_log alerts for critically stale data
            # - Trading day awareness: Skips weekend/holiday alerts for market data
            # - Complements maintain-data-freshness (watchlist-specific)
        },
        "cleanup-old-logs-daily": {
            "task": "cleanup_old_logs_task",
            "schedule": crontab(hour=2, minute=0),  # Daily at 02:00 UTC
            "args": [7],  # Delete logs older than 7 days
            "options": {"expires": 3600},
            # Notes:
            # - Runs daily at 02:00 UTC (before market data tasks)
            # - Deletes rotated log files (.log.TIMESTAMP) older than 7 days
            # - Searches /tmp and /var/log/portfolio-ai directories
            # - Tracks bytes freed in maintenance_stats table
        },
        "cleanup-temp-files-daily": {
            "task": "cleanup_temp_files_task",
            "schedule": crontab(hour=2, minute=15),  # Daily at 02:15 UTC
            "args": [24],  # Delete temp files older than 24 hours
            "options": {"expires": 3600},
            # Notes:
            # - Runs daily at 02:15 UTC (15 min after log cleanup)
            # - Deletes temporary files matching patterns (portfolio-ai-*, celery-*, tmpfile*, *.tmp)
            # - Only processes /tmp directory
            # - Tracks bytes freed in maintenance_stats table
        },
        "vacuum-database-weekly": {
            "task": "vacuum_database_task",
            "schedule": crontab(day_of_week=0, hour=3, minute=30),  # Sunday 03:30 UTC
            "args": [None],  # Vacuum all tables
            "options": {"expires": 7200},  # 2 hour timeout for large databases
            # Notes:
            # - Runs weekly on Sunday at 03:30 UTC (after capability analysis)
            # - VACUUM ANALYZE reclaims space and updates table statistics
            # - Improves query performance by updating planner statistics
            # - Can take several minutes for large tables
        },
        "cleanup-old-news-weekly": {
            "task": "cleanup_old_news_task",
            "schedule": crontab(day_of_week=0, hour=4, minute=0),  # Sunday 04:00 UTC
            "args": [90],  # Delete news older than 90 days
            "options": {"expires": 3600},
            # Notes:
            # - Runs weekly on Sunday at 04:00 UTC (after database vacuum)
            # - Deletes news articles from news_cache older than 90 days
            # - Prevents unbounded growth of news_cache table
            # - Tracks rows deleted in maintenance_stats table
        },
        "cleanup-old-agent-runs-weekly": {
            "task": "cleanup_old_agent_runs_task",
            "schedule": crontab(day_of_week=0, hour=4, minute=15),  # Sunday 04:15 UTC
            "args": [30],  # Delete agent runs older than 30 days
            "options": {"expires": 3600},
            # Notes:
            # - Runs weekly on Sunday at 04:15 UTC (after news cleanup)
            # - Deletes agent runs and associated ideas older than 30 days
            # - Prevents unbounded growth of agent_runs and agent_ideas tables
            # - Tracks runs/ideas deleted in maintenance_stats table
        },
        "cleanup-orphaned-data-weekly": {
            "task": "cleanup_orphaned_data_task",
            "schedule": crontab(day_of_week=0, hour=4, minute=30),  # Sunday 04:30 UTC
            "options": {"expires": 3600},
            # Notes:
            # - Runs weekly on Sunday at 04:30 UTC (after agent run cleanup)
            # - Removes orphaned records (ideas without runs, insights without capabilities)
            # - Maintains referential integrity after deletions
            # - Tracks orphaned records deleted in maintenance_stats table
        },
        "check-disk-space-periodic": {
            "task": "check_disk_space_task",
            "schedule": crontab(hour="*/6"),  # Every 6 hours
            "options": {"expires": 600},
            # Notes:
            # - Runs every 6 hours (00:00, 06:00, 12:00, 18:00 UTC)
            # - Checks disk usage for /, /tmp, /var/log partitions
            # - Alerts (via logs) if any partition > 85% used
            # - Tracks disk usage trends in maintenance_stats table
            # - Critical for preventing disk space issues
        },
        "check-data-source-health-periodic": {
            "task": "check_data_source_health",
            "schedule": crontab(minute=30, hour="*/6"),  # Every 6 hours at :30
            "options": {"expires": 600},
            # Notes:
            # - Runs every 6 hours at :30 (00:30, 06:30, 12:30, 18:30 UTC)
            # - Tests each data source with SPY OHLCV fetch
            # - Categorizes sources: healthy, degraded, down
            # - Provides visibility into source availability
            # - Complements multi-source fallback logging
        },
        "get-database-size-daily": {
            "task": "get_database_size_task",
            "schedule": crontab(hour=5, minute=0),  # Daily at 05:00 UTC
            "options": {"expires": 600},
            # Notes:
            # - Runs daily at 05:00 UTC (after all cleanup tasks complete)
            # - Gets total database size and top 10 largest tables
            # - Tracks database growth trends in maintenance_stats table
            # - Helps identify which tables are growing fastest
        },
        # NOTE: Removed ghost tasks (functions never implemented):
        # - check-workflow-failures-every-6h
        # - monitor-api-rate-limits-every-6h
        # - monitor-workflow-timeouts-every-6h
        # Removed by /scrub_it on 2025-12-02
        # ============================================================================
        # STRATEGY MONITORING & GENERATION (Task 4.8)
        # ============================================================================
        "evaluate-strategy-performance": {
            "task": "app.tasks.strategy_monitoring_tasks.evaluate_strategy_performance",
            "schedule": crontab(hour=4, minute=0),  # Daily at 04:00 UTC
            "options": {"expires": 3600},
            # Notes:
            # - Evaluates all active strategies daily
            # - Calculates 30-day rolling metrics (Sharpe, win rate, drawdown)
            # - Archives strategies with <70% expected performance for >30 days
            # - Updates strategy_performance table with daily metrics
        },
        "auto-promote-strategies": {
            "task": "app.tasks.strategy_monitoring_tasks.auto_promote_strategies",
            "schedule": crontab(hour=4, minute=15),  # Daily at 04:15 UTC (after evaluation)
            "options": {"expires": 3600},
            # Notes:
            # - Auto-promotes testing strategies to active after validation
            # - Criteria: 3+ days old, expected Sharpe >= 1.0, no blocking issues
            # - Runs after evaluate-strategy-performance to use fresh data
        },
        "generate-weekly-strategies": {
            "task": "app.tasks.strategy_monitoring_tasks.weekly_strategy_generation",
            "schedule": crontab(hour=5, minute=0, day_of_week=0),  # Sunday 05:00 UTC
            "options": {"expires": 7200},
            # Notes:
            # - Full sweep of top 20 watchlist symbols
            # - Skips symbols that already have active strategies
            # - Runs strategy_research_workflow for each symbol
            # - Commits generated strategies to git with research context
        },
        "daily-strategy-refresh": {
            "task": "app.tasks.strategy_monitoring_tasks.daily_strategy_refresh",
            "schedule": crontab(hour=5, minute=15),  # Daily at 05:15 UTC
            "options": {"expires": 3600},
            # Notes:
            # - Runs daily to catch new symbols and replace underperformers
            # - Generates max 5 strategies per day (cost control)
            # - Only for: symbols without strategy OR underperforming (Sharpe < 0.5)
            # - More responsive than weekly-only approach
        },
        "generate-daily-strategy-signals": {
            "task": "app.tasks.strategy_signal_tasks.generate_daily_strategy_signals",
            "schedule": crontab(hour=21, minute=30),  # Daily at 21:30 UTC (after US market close)
            "options": {"expires": 3600},
            # Notes:
            # - Generates trading signals for all active strategies
            # - Evaluates current market data against strategy parameters
            # - Stores signals in strategy_signals table
            # - BUY signals can trigger auto paper trading (if enabled)
        },
        "auto-paper-trade-from-signals": {
            "task": "app.tasks.strategy_signal_tasks.auto_paper_trade_from_signals",
            "schedule": crontab(hour=21, minute=45),  # Daily at 21:45 UTC (after signals)
            "options": {"expires": 3600},
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
            "options": {"expires": 3600},
            # Notes:
            # - Runs daily at 05:30 UTC (after OHLCV data refresh completes)
            # - Calculates pairwise covariance matrix for all watchlist/portfolio tickers
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
            "options": {"expires": 1800},
            # Notes:
            # - Runs daily at 21:30 UTC (30 min after market close at 4 PM ET)
            # - Saves equity snapshots for all portfolio accounts
            # - Tracks peak equity and calculates drawdown from peak
            # - Enables portfolio-level trading halt at -10% drawdown
            # - Historical snapshots enable equity curve visualization
            # - Fixes GAP-023: No drawdown tracking
        },
    }
