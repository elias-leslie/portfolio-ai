"""Fundamental data: earnings, financial health, risk metrics, macro."""

from typing import Any

from celery.schedules import crontab

from .constants import EXPIRY_1_HOUR, EXPIRY_2_HOURS


def get_tasks() -> dict[str, dict[str, Any]]:
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
