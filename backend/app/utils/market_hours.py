"""Market hours utilities for determining trading hours and data staleness.

This module provides utilities for:
- Checking if current time is during market hours (9:30 AM - 4:00 PM ET, Mon-Fri)
- Determining if watchlist data is stale based on market hours context
  - During market hours: stale if >15 minutes old
  - After hours: stale if >24 hours old
"""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

# Constants
NY_TZ = ZoneInfo("America/New_York")
MARKET_OPEN = time(9, 30)  # 9:30 AM ET
MARKET_CLOSE = time(16, 0)  # 4:00 PM ET

# Staleness thresholds
STALE_THRESHOLD_MARKET_HOURS = timedelta(minutes=15)
STALE_THRESHOLD_AFTER_HOURS = timedelta(hours=24)


def is_market_hours(now: datetime | None = None) -> bool:
    """
    Check if the U.S. stock market is currently open.

    Markets are open Monday-Friday, 9:30 AM - 4:00 PM Eastern Time.
    This does not account for market holidays (TODO: integrate holiday calendar).

    Args:
        now: The datetime to check. If None, uses current time in ET.

    Returns:
        True if markets are open, False otherwise.

    Examples:
        >>> # Wednesday, 10:30 AM ET
        >>> is_market_hours(datetime(2025, 10, 29, 10, 30, tzinfo=NY_TZ))
        True

        >>> # Wednesday, 5:00 PM ET
        >>> is_market_hours(datetime(2025, 10, 29, 17, 0, tzinfo=NY_TZ))
        False

        >>> # Saturday, 10:30 AM ET
        >>> is_market_hours(datetime(2025, 11, 1, 10, 30, tzinfo=NY_TZ))
        False
    """
    if now is None:
        now = datetime.now(NY_TZ)
    else:
        # Convert to Eastern Time if not already
        now = now.astimezone(NY_TZ)

    # Check if weekend (Monday=0, Sunday=6)
    if now.weekday() >= 5:  # Saturday or Sunday
        return False

    # Check if within market hours
    current_time = now.time()
    return MARKET_OPEN <= current_time < MARKET_CLOSE


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
