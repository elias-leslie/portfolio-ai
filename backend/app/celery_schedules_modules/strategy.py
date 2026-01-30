"""Strategy monitoring, portfolio analytics, and watchlist automation tasks."""

from typing import Any

from celery.schedules import crontab

from .constants import EXPIRY_1_HOUR, EXPIRY_2_HOURS, EXPIRY_10_MIN, EXPIRY_30_MIN


def get_tasks() -> dict[str, dict[str, Any]]:
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
