"""Reference data tasks: yfinance, Alpha Vantage, valuation parsing."""

from typing import Any

from celery.schedules import crontab

from .constants import EXPIRY_1_HOUR


def get_tasks() -> dict[str, dict[str, Any]]:
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
