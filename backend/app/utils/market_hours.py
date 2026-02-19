"""Market hours utilities for determining trading hours and data staleness.

This module provides utilities for:
- Checking if current time is during market hours (9:30 AM - 4:00 PM ET, Mon-Fri)
- Extended/pre-market hours detection
- US market holiday calendar with early close days
- Getting last/next trading day
- Market-aware data staleness determination

Public API is re-exported from focused submodules:
- _market_calendar: Holiday data and holiday/early-close detection
- _market_trading_days: Trading day navigation and close-time lookup
- _market_status: Market status classification (open/pre_market/after_hours/closed)
- _market_staleness: Staleness thresholds and age calculations
"""

from app.utils._market_calendar import (
    NY_TZ,
    US_MARKET_HOLIDAYS,
    is_early_close_day,
    is_market_holiday,
)
from app.utils._market_staleness import (
    STALE_THRESHOLD_AFTER_HOURS,
    STALE_THRESHOLD_MARKET_HOURS,
    get_hours_since_last_close,
    get_market_aware_age_hours,
    is_stale,
)
from app.utils._market_status import (
    AFTER_HOURS_CLOSE,
    PRE_MARKET_OPEN,
    MarketStatus,
    get_market_status,
    is_after_hours,
    is_market_hours,
    is_market_open,
    is_pre_market,
)
from app.utils._market_trading_days import (
    EARLY_CLOSE,
    MARKET_CLOSE,
    MARKET_OPEN,
    get_expected_data_date,
    get_last_trading_day,
    get_market_close_time,
    get_next_trading_day,
    is_trading_day,
)

__all__ = [
    "AFTER_HOURS_CLOSE",
    "EARLY_CLOSE",
    "MARKET_CLOSE",
    "MARKET_OPEN",
    "NY_TZ",
    "PRE_MARKET_OPEN",
    "STALE_THRESHOLD_AFTER_HOURS",
    "STALE_THRESHOLD_MARKET_HOURS",
    "US_MARKET_HOLIDAYS",
    "MarketStatus",
    "get_expected_data_date",
    "get_hours_since_last_close",
    "get_last_trading_day",
    "get_market_aware_age_hours",
    "get_market_close_time",
    "get_market_status",
    "get_next_trading_day",
    "is_after_hours",
    "is_early_close_day",
    "is_market_holiday",
    "is_market_hours",
    "is_market_open",
    "is_pre_market",
    "is_stale",
    "is_trading_day",
]
