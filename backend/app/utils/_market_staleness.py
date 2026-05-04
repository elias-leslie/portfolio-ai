"""Market-aware data staleness utilities.

Provides functions for determining if market data is stale and calculating
market-aware data ages that account for trading vs. non-trading periods.
"""

from datetime import date, datetime, timedelta

from app.utils._market_calendar import NY_TZ
from app.utils._market_status import is_market_hours
from app.utils._market_trading_days import (
    get_expected_data_date,
    get_last_trading_day,
    get_market_close_time,
    get_next_trading_day,
    is_trading_day,
)

# Staleness thresholds
STALE_THRESHOLD_MARKET_HOURS = timedelta(minutes=15)
STALE_THRESHOLD_AFTER_HOURS = timedelta(hours=24)


def get_hours_since_last_close(now: datetime | None = None) -> float:
    """Calculate hours since the last market close.

    Useful for determining data freshness in market-aware context.
    On a Monday morning, this returns hours since Friday's close.

    Args:
        now: The datetime to check. If None, uses current time in ET.

    Returns:
        Hours since last market close (as float).
    """
    from app.utils._market_status import get_market_status  # noqa: PLC0415

    if now is None:
        now = datetime.now(NY_TZ)
    else:
        now = now.astimezone(NY_TZ)

    today = now.date()
    current_time = now.time()

    status = get_market_status(now)
    if status == "open":
        return 0.0

    if is_trading_day(today) and current_time >= get_market_close_time(today):
        last_trading = today
    else:
        last_trading = get_last_trading_day(today - timedelta(days=1))

    close_time = get_market_close_time(last_trading)
    close_dt = datetime.combine(last_trading, close_time, tzinfo=NY_TZ)
    delta = now - close_dt
    return max(0.0, delta.total_seconds() / 3600)


def is_stale(fetched_at: datetime, now: datetime | None = None) -> bool:
    """Determine if market data is stale based on when it was fetched.

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
    """
    if now is None:
        now = datetime.now(NY_TZ)
    else:
        now = now.astimezone(NY_TZ)

    if fetched_at.tzinfo is None:
        raise ValueError("fetched_at must be timezone-aware")

    fetched_at = fetched_at.astimezone(NY_TZ)
    age = now - fetched_at

    if is_market_hours(now):
        return age > STALE_THRESHOLD_MARKET_HOURS
    return age > STALE_THRESHOLD_AFTER_HOURS


def _missed_trading_days(last_update_date: date, expected_data_date: date) -> int:
    if last_update_date >= expected_data_date:
        return 0

    missed = 0
    check_date = get_next_trading_day(last_update_date)
    while check_date <= expected_data_date:
        missed += 1
        check_date = get_next_trading_day(check_date)
    return missed


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
        age = now - last_update
        return age.total_seconds() / 3600

    market_now = now.astimezone(NY_TZ)
    market_last_update = last_update.astimezone(NY_TZ)
    expected_data_date = get_expected_data_date(market_now)
    last_update_date: date = market_last_update.date()

    if last_update_date >= expected_data_date:
        return 0.0

    expected_close_dt = datetime.combine(
        expected_data_date,
        get_market_close_time(expected_data_date),
        tzinfo=NY_TZ,
    )
    hours_since_expected_close = max(
        0.0,
        (market_now - expected_close_dt).total_seconds() / 3600,
    )
    extra_hours = max(0, _missed_trading_days(last_update_date, expected_data_date) - 1) * 24

    return hours_since_expected_close + extra_hours
