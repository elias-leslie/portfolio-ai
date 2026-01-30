"""Options, put/call ratio, and historical market data tasks."""

from typing import Any

from celery.schedules import crontab

from .constants import EXPIRY_1_HOUR


def get_tasks() -> dict[str, dict[str, Any]]:
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
