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

REMOVED TASKS (migrated elsewhere):
-----------------------------------
  - AI analyzer and gap detection: Migrated to [DEBT] subtasks on features.
    See tasks/tasks-tech-debt-to-feature-subtasks-migration.md
  - Daily gap analysis workflow: Migrated to feature-based tracking.

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
POLL_INTERVAL_60_SEC: float = 60.0  # Standard polling interval for user-configurable tasks
POLL_INTERVAL_30_MIN: float = 1800.0  # 30 minutes - reduced polling for API-heavy tasks
POLL_INTERVAL_12_HOURS: float = 43200.0  # 12 hours - for daily-ish tasks

# Task expiry times (seconds)
EXPIRY_2_MIN: int = 120  # Quick tasks that should be dropped if delayed
EXPIRY_10_MIN: int = 600  # 10-minute expiry for quick monitoring tasks
EXPIRY_28_MIN: int = 1700  # Slightly less than 30-min schedule
EXPIRY_30_MIN: int = 1800  # 30-minute expiry for moderate tasks
EXPIRY_50_MIN: int = 3000  # 50-minute expiry for longer tasks
EXPIRY_1_HOUR: int = 3600  # Longer-running tasks
EXPIRY_2_HOURS: int = 7200  # 2-hour expiry for daily cleanup tasks

# Fear & Greed lookback period (days)
FEAR_GREED_LOOKBACK_DAYS: int = 7

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


def _strategy_tasks() -> dict[str, dict[str, Any]]:
    """Strategy monitoring, portfolio analytics, and watchlist automation tasks.

    Includes:
    - Strategy performance evaluation and auto-promotion
    - Strategy generation and evolution
    - Signal generation and paper trading
    - Portfolio risk analytics and drawdown tracking
    - Watchlist candidate discovery and trimming
    - Rules validation and optimization

    Returns:
        Dict of Celery Beat task definitions for strategy-related tasks
    """
    return {
        # Strategy monitoring & generation
        # Staggered: evaluate at 04:00, yfinance at 04:02, sitemap cleanup at 04:04
        "evaluate-strategy-performance": {
            "task": "app.tasks.strategy.performance_tasks.evaluate_strategy_performance",
            "schedule": crontab(hour=4, minute=0),  # Daily at 04:00 UTC
            "options": {"expires": EXPIRY_1_HOUR},
        },
        "auto-promote-strategies": {
            "task": "app.tasks.strategy.performance_tasks.auto_promote_strategies",
            "schedule": crontab(hour=4, minute=15),  # Daily at 04:15 UTC
            "options": {"expires": EXPIRY_1_HOUR},
        },
        "generate-weekly-strategies": {
            "task": "app.tasks.strategy.generation_tasks.weekly_strategy_generation",
            "schedule": crontab(hour=5, minute=0, day_of_week=0),  # Sunday 05:00 UTC
            "options": {"expires": EXPIRY_2_HOURS},
        },
        # Staggered Sunday 06:XX: evolution at 06:00, sec-cik at 06:05, fundamental at 06:10
        "weekly-strategy-evolution": {
            "task": "app.tasks.strategy.evolution_tasks.weekly_strategy_evolution",
            "schedule": crontab(hour=6, minute=0, day_of_week=0),  # Sunday 06:00 UTC
            "options": {"expires": EXPIRY_2_HOURS},
        },
        "daily-strategy-refresh": {
            "task": "app.tasks.strategy.generation_tasks.daily_strategy_refresh",
            "schedule": crontab(hour=5, minute=15),  # Daily at 05:15 UTC
            "options": {"expires": EXPIRY_1_HOUR},
        },
        "generate-daily-strategy-signals": {
            "task": "app.tasks.strategy_signal_tasks.generate_daily_strategy_signals",
            "schedule": crontab(hour=21, minute=30),  # Daily at 21:30 UTC
            "options": {"expires": EXPIRY_1_HOUR},
        },
        # Staggered 21:45-21:47: paper trade at 21:45, fear-greed at 21:47
        "auto-paper-trade-from-signals": {
            "task": "app.tasks.strategy_signal_tasks.auto_paper_trade_from_signals",
            "schedule": crontab(hour=21, minute=45),  # Daily at 21:45 UTC
            "options": {"expires": EXPIRY_1_HOUR},
        },
        # Portfolio risk analytics
        "update-portfolio-covariance-daily": {
            "task": "update_portfolio_covariance",
            "schedule": crontab(hour=5, minute=30),  # Daily at 05:30 UTC
            "options": {"expires": EXPIRY_1_HOUR},
        },
        # Portfolio drawdown tracking
        "save-portfolio-snapshots-daily": {
            "task": "save_portfolio_snapshots",
            "schedule": crontab(hour=21, minute=33),  # Daily at 21:33 UTC (staggered)
            "options": {"expires": EXPIRY_30_MIN},
        },
        # Watchlist automation
        # Staggered 08:XX: discover at 08:00, sitemap-health at 08:02
        "discover-watchlist-candidates-daily": {
            "task": "discover_watchlist_candidates",
            "schedule": crontab(hour=8, minute=0),  # Daily at 08:00 UTC
            "options": {"expires": EXPIRY_30_MIN},
        },
        "trim-underperforming-watchlist-daily": {
            "task": "trim_underperforming_watchlist",
            "schedule": crontab(hour=8, minute=30),  # Daily at 08:30 UTC
            "options": {"expires": EXPIRY_30_MIN},
        },
        # generate-watchlist-daily-report removed - feature disabled (never executed, no data)
        # Rules validation
        "daily-rules-validation": {
            "task": "daily_rules_validation",
            "schedule": crontab(hour=3, minute=8),  # Daily at 03:08 UTC
            "options": {"expires": EXPIRY_10_MIN},
        },
        "weekly-optimization-review": {
            "task": "weekly_optimization_review",
            "schedule": crontab(hour=3, minute=10, day_of_week=1),  # Monday 03:10 UTC
            "options": {"expires": EXPIRY_30_MIN},
        },
    }


def _monitoring_tasks() -> dict[str, dict[str, Any]]:
    """Monitoring and lifecycle tasks for artifacts, theses, sitemap, and files.

    Includes:
    - Artifact refresh and cleanup
    - Thesis health monitoring and processing
    - Sitemap health checks and discovery
    - File audit scanning

    Returns:
        Dict of Celery Beat task definitions for monitoring tasks
    """
    return {
        # Artifact lifecycle
        "refresh-expired-artifacts": {
            "task": "refresh_expired_artifacts",
            "schedule": crontab(hour=5, minute=33),  # Daily at 05:33 UTC (staggered)
            "options": {"expires": EXPIRY_1_HOUR},
        },
        "cleanup-old-artifact-versions": {
            "task": "cleanup_old_versions",
            "schedule": crontab(hour=6, minute=0),  # Daily at 06:00 UTC
            "options": {"expires": EXPIRY_1_HOUR},
            "kwargs": {"max_versions": 5, "dry_run": False},
        },
        "cleanup-debug-captures": {
            "task": "cleanup_debug_captures",
            "schedule": crontab(hour=6, minute=15),  # Daily at 06:15 UTC
            "options": {"expires": EXPIRY_1_HOUR},
            "kwargs": {"max_age_days": 7, "dry_run": False},
        },
        # Thesis monitoring
        "monitor-thesis-health-daily": {
            "task": "monitor_thesis_health",
            "schedule": crontab(hour=3, minute=5),  # Daily at 03:05 UTC
            "options": {"expires": EXPIRY_30_MIN},
        },
        "process-invalidated-theses-daily": {
            "task": "process_invalidated_theses",
            "schedule": crontab(hour=3, minute=15),  # Daily at 03:15 UTC
            "options": {"expires": EXPIRY_30_MIN},
        },
        "archive-strategies-for-invalidated-theses": {
            "task": "archive_strategies_for_invalidated_theses",
            "schedule": crontab(hour=3, minute=30),  # Daily at 03:30 UTC
            "options": {"expires": EXPIRY_30_MIN},
        },
        # Sitemap health
        "check-sitemap-health-morning": {
            "task": "check_sitemap_health",
            "schedule": crontab(hour=8, minute=2),  # Daily at 08:02 UTC (staggered)
            "options": {"expires": EXPIRY_50_MIN},
        },
        "check-sitemap-health-evening": {
            "task": "check_sitemap_health",
            "schedule": crontab(hour=20, minute=0),  # Daily at 20:00 UTC
            "options": {"expires": EXPIRY_50_MIN},
        },
        "discover-sitemap-entries-daily": {
            "task": "discover_sitemap_entries",
            "schedule": crontab(hour=3, minute=33),  # Daily at 03:33 UTC (staggered)
            "options": {"expires": EXPIRY_30_MIN},
        },
        "cleanup-sitemap-history-daily": {
            "task": "cleanup_sitemap_history",
            "schedule": crontab(hour=4, minute=4),  # Daily at 04:04 UTC (staggered)
            "options": {"expires": EXPIRY_10_MIN},
        },
        # File audit
        "scan-files-daily": {
            "task": "scan_files",
            "schedule": crontab(hour=7, minute=30),  # Daily at 07:30 UTC
            "options": {"expires": EXPIRY_30_MIN},
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
            "options": {"expires": EXPIRY_1_HOUR},
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
            "schedule": crontab(day_of_week=0, hour=5, minute=5),  # Sunday 05:05 UTC
            "args": [CLEANUP_MODELS_KEEP_COUNT],
            "options": {"expires": EXPIRY_1_HOUR},
        },
        "cleanup-solution-state-weekly": {
            "task": "cleanup_solution_state_task",
            "schedule": crontab(day_of_week=0, hour=5, minute=25),  # Sunday 05:25 UTC
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
            "schedule": crontab(hour=5, minute=36),  # Daily at 05:36 UTC (staggered)
            "options": {"expires": EXPIRY_10_MIN},
        },
        "refresh-sec-cik-cache-weekly": {
            "task": "refresh_sec_cik_cache",
            "schedule": crontab(
                hour=6, minute=5, day_of_week=0
            ),  # Weekly on Sunday at 06:05 UTC (staggered)
            "options": {"expires": EXPIRY_1_HOUR},
        },
    }


def _data_refresh_tasks() -> dict[str, dict[str, Any]]:
    """Daily data refresh tasks for OHLCV, technical indicators, and Fear & Greed.

    Includes daily OHLCV refresh, technical indicator backfill, Fear & Greed
    calculation, and intraday refresh chains (morning, midday, after-close).
    """
    return {
        "refresh-daily-ohlcv": {
            "task": "refresh_daily_ohlcv",
            "schedule": crontab(hour=2, minute=0),
            "args": [ALL_MARKET_SYMBOLS],
            "options": {"expires": EXPIRY_1_HOUR},
        },
        "refresh-watchlist-ohlcv": {
            "task": "refresh_watchlist_ohlcv",
            "schedule": crontab(hour=2, minute=15),
            "options": {"expires": EXPIRY_1_HOUR},
        },
        "update-technical-indicators-daily": {
            "task": "backfill_technical_indicators",
            "schedule": crontab(hour=2, minute=30),
            "args": [None, 50],
            "options": {"expires": EXPIRY_1_HOUR},
        },
        "populate-fear-greed-inputs-daily": {
            "task": "populate_fear_greed_inputs",
            "schedule": crontab(hour=2, minute=45),
            "args": [FEAR_GREED_LOOKBACK_DAYS],
            "options": {"expires": EXPIRY_1_HOUR},
        },
        "calculate-fear-greed-daily": {
            "task": "calculate_fear_greed",
            "schedule": crontab(hour=3, minute=2),
            "args": [None],
            "options": {"expires": EXPIRY_1_HOUR},
        },
        # Intraday refresh chains (morning, midday)
        **_create_intraday_refresh_tasks("morning", hour=15),
        **_create_intraday_refresh_tasks("midday", hour=17),
        "update-fear-greed-after-close": {
            "task": "populate_fear_greed_inputs",
            "schedule": crontab(hour=21, minute=47),
            "args": [FEAR_GREED_LOOKBACK_DAYS],
            "options": {"expires": EXPIRY_1_HOUR},
        },
        "calculate-fear-greed-after-close": {
            "task": "calculate_fear_greed",
            "schedule": crontab(hour=22, minute=0),
            "args": [None],
            "options": {"expires": EXPIRY_1_HOUR},
        },
    }


def _market_data_tasks() -> dict[str, dict[str, Any]]:
    """Options, put/call ratio, and historical market data tasks."""
    return {
        "maintain-historical-market-data": {
            "task": "maintain_historical_market_data",
            "schedule": crontab(hour=4, minute=15),
            "options": {"expires": EXPIRY_1_HOUR},
        },
        "fetch-options-activity-daily": {
            "task": "fetch_options_activity_metrics",
            "schedule": crontab(hour=21, minute=15),
            "options": {"expires": EXPIRY_1_HOUR},
        },
        "fetch-putcall-ratio-market-open": {
            "task": "fetch_putcall_ratio",
            "schedule": crontab(hour=14, minute=30),
            "options": {"expires": EXPIRY_1_HOUR},
        },
        "fetch-putcall-ratio-market-close": {
            "task": "fetch_putcall_ratio",
            "schedule": crontab(hour=21, minute=39),
            "options": {"expires": EXPIRY_1_HOUR},
        },
    }


def _reference_data_tasks() -> dict[str, dict[str, Any]]:
    """Reference data tasks: yfinance, Alpha Vantage, valuation parsing."""
    return {
        "refresh-yfinance-reference": {
            "task": "refresh_yfinance_reference_data",
            "schedule": crontab(hour=4, minute=2),
            "options": {"expires": EXPIRY_1_HOUR},
        },
        "parse-valuation-metrics": {
            "task": "parse_valuation_metrics",
            "schedule": crontab(hour=4, minute=30),
            "options": {"expires": EXPIRY_1_HOUR},
        },
        "refresh-alphavantage-reference-backup": {
            "task": "refresh_alphavantage_reference_backup",
            "schedule": crontab(hour=4, minute=45),
            "options": {"expires": EXPIRY_1_HOUR},
        },
    }


def _fundamental_tasks() -> dict[str, dict[str, Any]]:
    """Fundamental data: earnings, financial health, risk metrics, macro."""
    return {
        "update-earnings-surprises-weekly": {
            "task": "update_earnings_surprises",
            "schedule": crontab(hour=5, minute=10, day_of_week=0),
            "options": {"expires": EXPIRY_2_HOURS},
        },
        "refresh-analyst-revisions-daily": {
            "task": "refresh_analyst_revisions",
            "schedule": crontab(hour=7, minute=0),
            "options": {"expires": EXPIRY_1_HOUR},
        },
        "refresh-financial-health-scores-weekly": {
            "task": "refresh_financial_health_scores",
            "schedule": crontab(hour=5, minute=15, day_of_week=0),
            "options": {"expires": EXPIRY_2_HOURS},
        },
        "refresh-risk-metrics-daily": {
            "task": "refresh_risk_metrics",
            "schedule": crontab(hour=5, minute=39),
            "options": {"expires": EXPIRY_1_HOUR},
        },
        "ingest-fundamental-data-weekly": {
            "task": "app.tasks.ingestion.fundamental_ingestion.ingest_fundamental_data",
            "schedule": crontab(hour=6, minute=10, day_of_week=0),
            "options": {"expires": EXPIRY_2_HOURS},
        },
        "fetch-corporate-actions-weekly": {
            "task": "tasks.fetch_corporate_actions",
            "schedule": crontab(hour=6, minute=30, day_of_week=0),
            "options": {"expires": EXPIRY_2_HOURS},
        },
        "ingest-macro-indicators-daily": {
            "task": "app.tasks.ingestion.fundamental_ingestion.ingest_macro_indicators",
            "schedule": crontab(hour=6, minute=30),
            "options": {"expires": EXPIRY_1_HOUR},
        },
    }


def _capability_scan_tasks() -> dict[str, dict[str, Any]]:
    """QA scanning and capability discovery tasks."""
    return {
        "scan-system-capabilities": {
            "task": "scan_system_capabilities",
            "schedule": crontab(hour=3, minute=0),
            "options": {"expires": EXPIRY_30_MIN},
        },
        "scan-feature-capabilities": {
            "task": "scan_feature_capabilities",
            "schedule": crontab(hour=3, minute=5),
            "options": {"expires": EXPIRY_30_MIN},
        },
        "daily-qa-scan": {
            "task": "tasks.daily_qa_scan",
            "schedule": crontab(hour=4, minute=30),
            "options": {"expires": EXPIRY_1_HOUR},
        },
        "verify-acceptance-criteria": {
            "task": "verify_all_acceptance_criteria",
            "schedule": crontab(hour=5, minute=20, day_of_week=0),
            "options": {"expires": EXPIRY_2_HOURS},
        },
    }


def _static_schedule_tasks() -> dict[str, dict[str, Any]]:
    """Remaining static schedule tasks: paper trades, news, ML model."""
    return {
        "update-paper-trades-daily": {
            "task": "update_paper_trades_task",
            "schedule": crontab(hour=21, minute=36),
            "options": {"expires": EXPIRY_1_HOUR},
        },
        "profile-news-sources": {
            "task": "profile_news_sources",
            "schedule": POLL_INTERVAL_12_HOURS,
            "args": ["default"],
            "options": {"expires": EXPIRY_1_HOUR},
        },
        "retrain-article-quality-model": {
            "task": "retrain_article_quality_model",
            "schedule": crontab(hour=5, minute=0),
            "options": {"expires": EXPIRY_2_HOURS},
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
            "schedule": crontab(hour=3, minute=36),  # Daily at 03:36 UTC (staggered)
            "options": {"expires": EXPIRY_30_MIN},  # 30-minute expiry
        },
        "run-portfolio-analyzer-daily": {
            "task": "run_portfolio_analyzer",
            "schedule": crontab(hour=3, minute=39),  # Daily at 03:39 UTC (staggered)
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
            "schedule": crontab(minute=25),  # Hourly at :25 (was 30min, caused CPU spikes)
            "args": ["default"],
            "options": {"expires": EXPIRY_50_MIN},  # 50 min expiry for hourly schedule
            # Notes:
            # - Changed from 30min to hourly to reduce CPU load (task takes 4-5 min)
            # - Runs at :25 to avoid collision with other hourly tasks
            # - Task checks: news_refresh_override → default_refresh_minutes → 15 min
            # - Uses optimized JOIN query from Issue #5 fix
        },
    }


def get_beat_schedule() -> dict[str, dict[str, Any]]:
    """Get Celery Beat schedule configuration.

    Merges all categorized task helpers into a single beat schedule.
    See individual helper functions for task details and documentation.

    Task Categories:
    - User-configurable: watchlist scores, news sentiment
    - Static schedule: paper trades, news profiling, ML model training
    - Data refresh: OHLCV, indicators, Fear & Greed
    - Market data: options, put/call ratios, historical data
    - Reference data: yfinance, Alpha Vantage, valuations
    - Fundamentals: earnings, financial health, risk, macro
    - Capability scans: system/feature discovery, QA
    - Agents: discovery agent, portfolio analyzer
    - Maintenance: freshness, cleanup, disk space
    - Strategy: performance, generation, signals, portfolio
    - Monitoring: artifacts, theses, sitemap, files

    Returns:
        dict: Beat schedule with all periodic tasks
    """
    return {
        **_user_configurable_tasks(),
        **_static_schedule_tasks(),
        **_data_refresh_tasks(),
        **_market_data_tasks(),
        **_reference_data_tasks(),
        **_fundamental_tasks(),
        **_capability_scan_tasks(),
        **_agent_tasks(),
        **_maintenance_tasks(),
        **_strategy_tasks(),
        **_monitoring_tasks(),
    }
