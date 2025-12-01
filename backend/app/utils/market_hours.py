"""Market hours utilities for determining trading hours and data staleness.

This module provides utilities for:
- Checking if current time is during market hours (9:30 AM - 4:00 PM ET, Mon-Fri)
- Extended/pre-market hours detection
- US market holiday calendar with early close days
- Getting last/next trading day
- Market-aware data staleness determination
"""

from datetime import date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

# Constants
NY_TZ = ZoneInfo("America/New_York")
MARKET_OPEN = time(9, 30)  # 9:30 AM ET
MARKET_CLOSE = time(16, 0)  # 4:00 PM ET
PRE_MARKET_OPEN = time(4, 0)  # 4:00 AM ET
AFTER_HOURS_CLOSE = time(20, 0)  # 8:00 PM ET
EARLY_CLOSE = time(13, 0)  # 1:00 PM ET (day before Thanksgiving, Christmas Eve, etc.)

# Staleness thresholds
STALE_THRESHOLD_MARKET_HOURS = timedelta(minutes=15)
STALE_THRESHOLD_AFTER_HOURS = timedelta(hours=24)

# Market status type
MarketStatus = Literal["open", "pre_market", "after_hours", "closed"]

# US Market Holidays (NYSE/NASDAQ) for 2024-2026
# Each entry: (holiday_name, is_early_close). Early close days close at 1:00 PM ET.
US_MARKET_HOLIDAYS: dict[date, tuple[str, bool]] = {
    # 2024 Holidays
    date(2024, 1, 1): ("New Year's Day", False),
    date(2024, 1, 15): ("Martin Luther King Jr. Day", False),
    date(2024, 2, 19): ("Presidents Day", False),
    date(2024, 3, 29): ("Good Friday", False),
    date(2024, 5, 27): ("Memorial Day", False),
    date(2024, 6, 19): ("Juneteenth", False),
    date(2024, 7, 3): ("Day before Independence Day", True),  # Early close
    date(2024, 7, 4): ("Independence Day", False),
    date(2024, 9, 2): ("Labor Day", False),
    date(2024, 11, 28): ("Thanksgiving Day", False),
    date(2024, 11, 29): ("Day after Thanksgiving", True),  # Early close
    date(2024, 12, 24): ("Christmas Eve", True),  # Early close
    date(2024, 12, 25): ("Christmas Day", False),
    # 2025 Holidays
    date(2025, 1, 1): ("New Year's Day", False),
    date(2025, 1, 20): ("Martin Luther King Jr. Day", False),
    date(2025, 2, 17): ("Presidents Day", False),
    date(2025, 4, 18): ("Good Friday", False),
    date(2025, 5, 26): ("Memorial Day", False),
    date(2025, 6, 19): ("Juneteenth", False),
    date(2025, 7, 3): ("Day before Independence Day", True),  # Early close
    date(2025, 7, 4): ("Independence Day", False),
    date(2025, 9, 1): ("Labor Day", False),
    date(2025, 11, 27): ("Thanksgiving Day", False),
    date(2025, 11, 28): ("Day after Thanksgiving", True),  # Early close
    date(2025, 12, 24): ("Christmas Eve", True),  # Early close
    date(2025, 12, 25): ("Christmas Day", False),
    # 2026 Holidays
    date(2026, 1, 1): ("New Year's Day", False),
    date(2026, 1, 19): ("Martin Luther King Jr. Day", False),
    date(2026, 2, 16): ("Presidents Day", False),
    date(2026, 4, 3): ("Good Friday", False),
    date(2026, 5, 25): ("Memorial Day", False),
    date(2026, 6, 19): ("Juneteenth", False),
    date(2026, 7, 3): ("Day before Independence Day", True),  # Early close
    date(2026, 9, 7): ("Labor Day", False),
    date(2026, 11, 26): ("Thanksgiving Day", False),
    date(2026, 11, 27): ("Day after Thanksgiving", True),  # Early close
    date(2026, 12, 24): ("Christmas Eve", True),  # Early close
    date(2026, 12, 25): ("Christmas Day", False),
}


def is_market_holiday(check_date: date | None = None) -> tuple[bool, str | None]:
    """Check if a date is a US market holiday.

    Args:
        check_date: The date to check. If None, uses today in ET.

    Returns:
        Tuple of (is_holiday, holiday_name). holiday_name is None if not a holiday.
    """
    if check_date is None:
        check_date = datetime.now(NY_TZ).date()

    if check_date in US_MARKET_HOLIDAYS:
        holiday_name, is_early = US_MARKET_HOLIDAYS[check_date]
        # If it's an early close day, it's not a full holiday
        if is_early:
            return False, None
        return True, holiday_name
    return False, None


def is_early_close_day(check_date: date | None = None) -> tuple[bool, str | None]:
    """Check if a date is an early close day (market closes at 1 PM ET).

    Args:
        check_date: The date to check. If None, uses today in ET.

    Returns:
        Tuple of (is_early_close, day_name). day_name is None if not early close.
    """
    if check_date is None:
        check_date = datetime.now(NY_TZ).date()

    if check_date in US_MARKET_HOLIDAYS:
        day_name, is_early = US_MARKET_HOLIDAYS[check_date]
        if is_early:
            return True, day_name
    return False, None


def is_trading_day(check_date: date | None = None) -> bool:
    """Check if a date is a trading day (market open at some point).

    A trading day is:
    - Not a weekend (Saturday/Sunday)
    - Not a full market holiday
    - Early close days ARE trading days

    Args:
        check_date: The date to check. If None, uses today in ET.

    Returns:
        True if the market is open at some point on this day.
    """
    if check_date is None:
        check_date = datetime.now(NY_TZ).date()

    # Weekend check
    if check_date.weekday() >= 5:  # Saturday or Sunday
        return False

    # Holiday check (early close days are still trading days)
    is_holiday, _ = is_market_holiday(check_date)
    return not is_holiday


def get_last_trading_day(from_date: date | None = None) -> date:
    """Get the most recent trading day on or before the given date.

    Args:
        from_date: The date to start from. If None, uses today in ET.

    Returns:
        The most recent trading day (could be from_date if it's a trading day).
    """
    if from_date is None:
        from_date = datetime.now(NY_TZ).date()

    # Walk backwards until we find a trading day
    check_date = from_date
    max_lookback = 10  # Safety limit (longest holiday streak is ~4 days)
    for _ in range(max_lookback):
        if is_trading_day(check_date):
            return check_date
        check_date -= timedelta(days=1)

    # Should never reach here, but return the earliest checked date
    return check_date


def get_next_trading_day(from_date: date | None = None) -> date:
    """Get the next trading day after the given date.

    Args:
        from_date: The date to start from. If None, uses today in ET.

    Returns:
        The next trading day (never includes from_date).
    """
    if from_date is None:
        from_date = datetime.now(NY_TZ).date()

    # Walk forward until we find a trading day
    check_date = from_date + timedelta(days=1)
    max_lookahead = 10  # Safety limit
    for _ in range(max_lookahead):
        if is_trading_day(check_date):
            return check_date
        check_date += timedelta(days=1)

    # Should never reach here
    return check_date


def get_market_close_time(check_date: date | None = None) -> time:
    """Get the market close time for a given date.

    Args:
        check_date: The date to check. If None, uses today in ET.

    Returns:
        Market close time (1 PM for early close days, 4 PM normally).
    """
    if check_date is None:
        check_date = datetime.now(NY_TZ).date()

    is_early, _ = is_early_close_day(check_date)
    return EARLY_CLOSE if is_early else MARKET_CLOSE


def get_market_status(now: datetime | None = None) -> MarketStatus:  # noqa: PLR0911
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

    today = now.date()
    current_time = now.time()

    # Check if weekend
    if now.weekday() >= 5:
        return "closed"

    # Check if holiday
    is_holiday, _ = is_market_holiday(today)
    if is_holiday:
        return "closed"

    # Get close time (handles early close days)
    close_time = get_market_close_time(today)

    # Determine status based on time
    if current_time < PRE_MARKET_OPEN:
        return "closed"
    if current_time < MARKET_OPEN:
        return "pre_market"
    if current_time < close_time:
        return "open"
    if current_time < AFTER_HOURS_CLOSE:
        return "after_hours"
    return "closed"


def is_market_open(now: datetime | None = None) -> bool:
    """Check if the market is currently open for regular trading.

    Alias for is_market_hours() that also checks holidays.

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


def get_hours_since_last_close(now: datetime | None = None) -> float:
    """Calculate hours since the last market close.

    Useful for determining data freshness in market-aware context.
    On a Monday morning, this returns hours since Friday's close.

    Args:
        now: The datetime to check. If None, uses current time in ET.

    Returns:
        Hours since last market close (as float).
    """
    if now is None:
        now = datetime.now(NY_TZ)
    else:
        now = now.astimezone(NY_TZ)

    today = now.date()
    current_time = now.time()

    # If market is currently open or was open today, check today's close
    status = get_market_status(now)
    if status == "open":
        # Market is open, so "since close" is 0 (or negative conceptually)
        return 0.0

    # Find the last trading day
    if is_trading_day(today) and current_time >= get_market_close_time(today):
        # Today was a trading day and market has closed
        last_trading = today
    else:
        # Find the previous trading day
        last_trading = get_last_trading_day(today - timedelta(days=1))

    # Get the close time for that day
    close_time = get_market_close_time(last_trading)

    # Calculate hours since close
    close_dt = datetime.combine(last_trading, close_time, tzinfo=NY_TZ)
    delta = now - close_dt
    return max(0.0, delta.total_seconds() / 3600)


def is_market_hours(now: datetime | None = None) -> bool:
    """Check if the U.S. stock market is currently open.

    Markets are open Monday-Friday, 9:30 AM - 4:00 PM Eastern Time.
    Now includes holiday checking.

    Args:
        now: The datetime to check. If None, uses current time in ET.

    Returns:
        True if markets are open, False otherwise.
    """
    if now is None:
        now = datetime.now(NY_TZ)
    else:
        now = now.astimezone(NY_TZ)

    # Check if weekend (Monday=0, Sunday=6)
    if now.weekday() >= 5:
        return False

    # Check if holiday
    is_holiday, _ = is_market_holiday(now.date())
    if is_holiday:
        return False

    # Check if within market hours (respecting early close)
    current_time = now.time()
    close_time = get_market_close_time(now.date())
    return MARKET_OPEN <= current_time < close_time


def is_stale(fetched_at: datetime, now: datetime | None = None) -> bool:
    """
    Determine if market data is stale based on when it was fetched.

    Staleness criteria:
    - During market hours: Data older than 15 minutes is stale
    - After hours/weekends: Data older than 24 hours is stale

    Args:
        fetched_at: When the data was last fetched (timezone-aware datetime)
        now: Current time for comparison. If None, uses current time in ET.

    Returns:
        True if data is stale, False otherwise.

    Examples:
        >>> # During market hours (Wed 10:30 AM ET), data 10 min old = not stale
        >>> fetched = datetime(2025, 10, 29, 10, 20, tzinfo=NY_TZ)
        >>> now = datetime(2025, 10, 29, 10, 30, tzinfo=NY_TZ)
        >>> is_stale(fetched, now)
        False

        >>> # During market hours, data 20 min old = stale
        >>> fetched = datetime(2025, 10, 29, 10, 10, tzinfo=NY_TZ)
        >>> now = datetime(2025, 10, 29, 10, 30, tzinfo=NY_TZ)
        >>> is_stale(fetched, now)
        True

        >>> # After hours (Wed 5 PM ET), data 5 hours old = not stale
        >>> fetched = datetime(2025, 10, 29, 12, 0, tzinfo=NY_TZ)
        >>> now = datetime(2025, 10, 29, 17, 0, tzinfo=NY_TZ)
        >>> is_stale(fetched, now)
        False

        >>> # After hours, data 25 hours old = stale
        >>> fetched = datetime(2025, 10, 28, 16, 0, tzinfo=NY_TZ)
        >>> now = datetime(2025, 10, 29, 17, 0, tzinfo=NY_TZ)
        >>> is_stale(fetched, now)
        True
    """
    if now is None:
        now = datetime.now(NY_TZ)
    else:
        now = now.astimezone(NY_TZ)

    # Ensure fetched_at is timezone-aware
    if fetched_at.tzinfo is None:
        raise ValueError("fetched_at must be timezone-aware")

    fetched_at = fetched_at.astimezone(NY_TZ)
    age = now - fetched_at

    # Use different thresholds based on market status
    if is_market_hours(now):
        return age > STALE_THRESHOLD_MARKET_HOURS
    return age > STALE_THRESHOLD_AFTER_HOURS


def get_market_aware_age_hours(
    last_update: datetime,
    now: datetime,
    is_market_data: bool,
) -> float:
    """Calculate market-aware data age in hours.

    For market data:
    - On weekends/holidays, age is calculated from last trading day's close
    - This prevents false "stale" alerts when data IS current for market status

    For non-market data:
    - Uses simple calendar hour calculation

    Args:
        last_update: When data was last updated (must be timezone-aware)
        now: Current datetime for comparison (must be timezone-aware)
        is_market_data: Whether this table contains market-dependent data

    Returns:
        Age in hours (market-aware for market data, calendar for non-market)
    """
    if not is_market_data:
        # Simple calendar calculation for non-market data
        age = now - last_update
        return age.total_seconds() / 3600

    # Market-aware calculation
    # If data is from the last trading day, calculate hours since that close
    last_trading = get_last_trading_day(now.date())
    last_update_date = last_update.date() if isinstance(last_update, datetime) else last_update

    # If last update is on or after the last trading day, data is fresh
    if last_update_date >= last_trading:
        # Calculate actual calendar hours for display
        age = now - last_update
        return age.total_seconds() / 3600

    # Data is older than last trading day - calculate from that trading day
    # This handles the case where Friday's data is still "fresh" on Sunday
    hours_since_close = get_hours_since_last_close(now)

    # Add the days between last_update and last_trading_day
    days_old = (last_trading - last_update_date).days
    extra_hours = days_old * 24  # Each trading day adds ~24 hours

    return hours_since_close + extra_hours
