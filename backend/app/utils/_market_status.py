"""Market status detection utilities.

Provides functions for determining the current market status
(open, pre-market, after-hours, closed) based on time and holiday calendar.
"""

from datetime import datetime, time
from typing import Literal

from app.utils._market_calendar import NY_TZ, is_market_holiday
from app.utils._market_trading_days import MARKET_OPEN, get_market_close_time

# Extended hours time constants
PRE_MARKET_OPEN = time(4, 0)   # 4:00 AM ET
AFTER_HOURS_CLOSE = time(20, 0)  # 8:00 PM ET

# Market status type alias
MarketStatus = Literal["open", "pre_market", "after_hours", "closed"]


def _is_non_trading_day(now: datetime) -> bool:
    """Return True if the given datetime falls on a weekend or market holiday."""
    is_holiday, _ = is_market_holiday(now.date())
    return now.weekday() >= 5 or is_holiday


def _classify_trading_session(
    current_time: time,
    close_time: time,
) -> MarketStatus:
    """Map a time-of-day to the appropriate trading session label."""
    if current_time < PRE_MARKET_OPEN:
        return "closed"
    if current_time < MARKET_OPEN:
        return "pre_market"
    if current_time < close_time:
        return "open"
    if current_time < AFTER_HOURS_CLOSE:
        return "after_hours"
    return "closed"


def get_market_status(now: datetime | None = None) -> MarketStatus:
    """Get the current market status.

    Args:
        now: The datetime to check. If None, uses current time in ET.

    Returns:
        "open" - Regular trading hours (9:30 AM - 4 PM ET)
        "pre_market" - Pre-market trading (4 AM - 9:30 AM ET)
        "after_hours" - After-hours trading (4 PM - 8 PM ET)
        "closed" - Market fully closed (weekends, holidays, overnight)
    """
    if now is None:
        now = datetime.now(NY_TZ)
    else:
        now = now.astimezone(NY_TZ)

    if _is_non_trading_day(now):
        return "closed"

    close_time = get_market_close_time(now.date())
    return _classify_trading_session(now.time(), close_time)


def is_market_open(now: datetime | None = None) -> bool:
    """Check if the market is currently open for regular trading.

    Args:
        now: The datetime to check. If None, uses current time in ET.

    Returns:
        True if market is open for regular trading, False otherwise.
    """
    return get_market_status(now) == "open"


def is_pre_market(now: datetime | None = None) -> bool:
    """Check if currently in pre-market hours (4 AM - 9:30 AM ET).

    Args:
        now: The datetime to check. If None, uses current time in ET.

    Returns:
        True if in pre-market hours, False otherwise.
    """
    return get_market_status(now) == "pre_market"


def is_after_hours(now: datetime | None = None) -> bool:
    """Check if currently in after-hours trading (4 PM - 8 PM ET).

    Args:
        now: The datetime to check. If None, uses current time in ET.

    Returns:
        True if in after-hours trading, False otherwise.
    """
    return get_market_status(now) == "after_hours"


def is_market_hours(now: datetime | None = None) -> bool:
    """Check if the U.S. stock market is currently open.

    Markets are open Monday-Friday, 9:30 AM - 4:00 PM Eastern Time.
    Includes holiday and early close day checking.

    Args:
        now: The datetime to check. If None, uses current time in ET.

    Returns:
        True if markets are open, False otherwise.
    """
    if now is None:
        now = datetime.now(NY_TZ)
    else:
        now = now.astimezone(NY_TZ)

    if now.weekday() >= 5:
        return False

    is_holiday, _ = is_market_holiday(now.date())
    if is_holiday:
        return False

    current_time = now.time()
    close_time = get_market_close_time(now.date())
    return MARKET_OPEN <= current_time < close_time
