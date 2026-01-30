"""Remaining static schedule tasks: paper trades, news, ML model."""

from typing import Any

from celery.schedules import crontab

from .constants import EXPIRY_1_HOUR, EXPIRY_2_HOURS, POLL_INTERVAL_12_HOURS


def get_tasks() -> dict[str, dict[str, Any]]:
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
