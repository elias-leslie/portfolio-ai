"""Canonical cron schedules for data refresh workflows.

These lists preserve the pre-Hatchet refresh cadence so market sentiment data
stays current throughout the trading day and after the close.
"""

PUTCALL_RATIO_CRONS = [
    "30 14 * * *",
    "39 21 * * *",
]

FEAR_GREED_INPUTS_CRONS = [
    "45 2 * * *",
    "15 15 * * *",
    "15 17 * * *",
    "47 21 * * *",
]

FEAR_GREED_CALC_CRONS = [
    "2 3 * * *",
    "30 15 * * *",
    "30 17 * * *",
    "0 22 * * *",
]

DAILY_OHLCV_CRONS = ["0 2 * * *"]
WATCHLIST_OHLCV_CRONS = ["15 2 * * *"]
HISTORICAL_OHLCV_MAINTENANCE_CRONS = ["15 4 * * *"]
TECHNICAL_INDICATOR_BACKFILL_CRONS = ["30 2 * * *"]
FUNDAMENTAL_INGESTION_CRONS = ["10 6 * * 0"]
MACRO_INDICATOR_INGESTION_CRONS = ["30 6 * * *"]
OPTIONS_ACTIVITY_CRONS = ["15 21 * * *"]
MARKET_PREDICTION_MORNING_CRONS = ["15 13 * * 1-5"]
MARKET_PREDICTION_AFTER_CLOSE_CRONS = ["10 22 * * 1-5"]
MARKET_PREDICTION_SUNDAY_CRONS = ["0 22 * * 0"]
MACRO_CALENDAR_INGESTION_CRONS = ["5 11 * * *"]
