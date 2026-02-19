"""Trading day utilities for the US stock market.

Provides functions to determine if a date is a trading day, navigate
between trading days, and determine market close times.
"""

from datetime import date, datetime, time, timedelta

from app.utils._market_calendar import NY_TZ, is_early_close_day, is_market_holiday

# Market open/close time constants
MARKET_OPEN = time(9, 30)  # 9:30 AM ET
MARKET_CLOSE = time(16, 0)  # 4:00 PM ET
EARLY_CLOSE = time(13, 0)  # 1:00 PM ET (day before Thanksgiving, Christmas Eve, etc.)


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

    if check_date.weekday() >= 5:  # Saturday or Sunday
        return False

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

    check_date = from_date
    max_lookback = 10  # Safety limit (longest holiday streak is ~4 days)
    for _ in range(max_lookback):
        if is_trading_day(check_date):
            return check_date
        check_date -= timedelta(days=1)

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

    check_date = from_date + timedelta(days=1)
    max_lookahead = 10  # Safety limit
    for _ in range(max_lookahead):
        if is_trading_day(check_date):
            return check_date
        check_date += timedelta(days=1)

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


def get_expected_data_date(now: datetime | None = None) -> date:
    """Get the date that market data SHOULD be available for.

    Returns the most recent trading day where market has closed.
    Used to determine if data is stale vs current.

    Args:
        now: The datetime to check. If None, uses current time in ET.

    Returns:
        The date data should be available for.

    Examples:
        - 8 AM Mon Dec 11: Returns Dec 10 (market hasn't opened yet)
        - 12 PM Mon Dec 11: Returns Dec 10 (market open, today incomplete)
        - 5 PM Mon Dec 11: Returns Dec 11 (market closed, today complete)
        - 10 AM Sat Dec 13: Returns Dec 12 (Friday's data should exist)
    """
    if now is None:
        now = datetime.now(NY_TZ)
    else:
        now = now.astimezone(NY_TZ)

    today = now.date()
    current_time = now.time()

    if is_trading_day(today):
        close_time = get_market_close_time(today)
        if current_time >= close_time:
            return today

    yesterday = today - timedelta(days=1)
    return get_last_trading_day(yesterday)
