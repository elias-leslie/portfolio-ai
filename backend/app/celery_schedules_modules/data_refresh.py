"""Daily data refresh tasks for OHLCV, technical indicators, and Fear & Greed."""

from typing import Any

from celery.schedules import crontab

from .constants import (
    ALL_MARKET_SYMBOLS,
    EXPIRY_1_HOUR,
    FEAR_GREED_LOOKBACK_DAYS,
)


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


def get_tasks() -> dict[str, dict[str, Any]]:
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
