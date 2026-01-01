"""Celery application configuration for background tasks.

This module configures Celery for asynchronous execution of
agent runs and other long-running tasks.
"""

from __future__ import annotations

import os

from celery import Celery  # celery doesn't ship type stubs
from celery.signals import (
    after_setup_logger,
    after_setup_task_logger,
)

from app.celery_schedules import get_beat_schedule

# Import DATABASE_URL from constants (which handles dotenv loading)
from app.constants import DATABASE_URL
from app.logging_config import SyslogPrefixFormatter, _parse_log_level

# Get Redis URL from environment or use default
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Create Celery application with Redis broker + PostgreSQL backend
# Note: Redis is recommended for broker (fast message queue)
#       PostgreSQL is used for result backend (persistent storage)
celery_app = Celery(
    "portfolio-ai",
    broker=f"{REDIS_URL}/0",  # Redis broker (message queue)
    backend=f"db+{DATABASE_URL}",  # PostgreSQL result backend
    broker_connection_retry_on_startup=True,
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    result_extended=True,  # Store extended task metadata (name, args, kwargs, worker)
    task_time_limit=600,  # 10 minutes max per task
    task_soft_time_limit=540,  # 9 minute soft limit
    result_expires=60 * 60 * 24 * 30,  # Results expire after 30 days (2,592,000 seconds)
    worker_prefetch_multiplier=1,  # One task at a time
    worker_max_tasks_per_child=50,  # Restart worker after 50 tasks
)


# Configure Celery Beat schedule for periodic tasks
# Beat schedule is defined in celery_schedules.py for better maintainability
celery_app.conf.beat_schedule = get_beat_schedule()


# Import tasks to register them with Celery
# This must come after celery_app is defined
from app.tasks import (  # noqa: E402, F401
    agent_tasks,
    backtest_tasks,
    capability_tasks,
    cleanup,
    data_freshness_tasks,
    # gap_analysis_tasks removed - migrated to [DEBT] subtasks on features
    ingestion,
    maintenance_tasks,
    ml_training_tasks,
    news_profiling_tasks,
    news_tasks,
    portfolio_tasks,
    qa_tasks,  # NEW: QA system daily scans
    reference_tasks,
    rules_validation_tasks,  # NEW: Rules validation and optimization
    sitemap_tasks,  # NEW: Sitemap health monitoring
    source_health_tasks,
    strategy,  # Strategy performance, generation, and evolution tasks
    strategy_metrics_tasks,
    strategy_signal_tasks,
    verify_criteria,  # NEW: Acceptance criteria auto-verification
    watchlist_discovery,  # NEW: Watchlist auto-discovery and trimming
    watchlist_tasks,
    workflow_tasks,
)
from app.tasks.indicators import (  # noqa: E402, F401
    backfill_technical_indicators,
    calculate_fear_greed,
    update_technical_indicators,
)
from app.tasks.market_data import (  # noqa: E402, F401
    fear_greed_pipeline,
    historical_ohlcv_pipeline,
    options_pipeline,
)


# Configure Celery logging to use syslog prefixes for journald
@after_setup_logger.connect
def setup_celery_logger(logger, *args, **kwargs):  # type: ignore[no-untyped-def]
    """Configure Celery logger to use syslog prefixes for proper journald PRIORITY.

    This signal handler is called after Celery sets up its logger. We replace
    the formatter with our SyslogPrefixFormatter so that log entries have
    correct syslog priority prefixes that systemd parses into the PRIORITY field.
    """
    log_level = _parse_log_level(os.getenv("LOG_LEVEL"))

    # Update all handlers to use syslog formatter
    for handler in logger.handlers:
        handler.setLevel(log_level)
        handler.setFormatter(
            SyslogPrefixFormatter("[%(asctime)s: %(levelname)s/%(processName)s] %(message)s")
        )


@after_setup_task_logger.connect
def setup_celery_task_logger(logger, *args, **kwargs):  # type: ignore[no-untyped-def]
    """Configure Celery task logger to use syslog prefixes for proper journald PRIORITY.

    This signal handler is called after Celery sets up task loggers. We replace
    the formatter with our SyslogPrefixFormatter so that log entries have
    correct syslog priority prefixes that systemd parses into the PRIORITY field.
    """
    log_level = _parse_log_level(os.getenv("LOG_LEVEL"))

    # Update all handlers to use syslog formatter
    for handler in logger.handlers:
        handler.setLevel(log_level)
        handler.setFormatter(
            SyslogPrefixFormatter("[%(asctime)s: %(levelname)s/%(processName)s] %(message)s")
        )
