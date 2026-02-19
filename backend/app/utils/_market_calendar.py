"""US market holiday calendar data and holiday-checking utilities.

Contains the NYSE/NASDAQ holiday calendar for 2024-2026 and functions
to determine whether a given date is a holiday or early close day.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

NY_TZ = ZoneInfo("America/New_York")

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

    if check_date not in US_MARKET_HOLIDAYS:
        return False, None

    holiday_name, is_early = US_MARKET_HOLIDAYS[check_date]
    if is_early:
        return False, None
    return True, holiday_name


def is_early_close_day(check_date: date | None = None) -> tuple[bool, str | None]:
    """Check if a date is an early close day (market closes at 1 PM ET).

    Args:
        check_date: The date to check. If None, uses today in ET.

    Returns:
        Tuple of (is_early_close, day_name). day_name is None if not early close.
    """
    if check_date is None:
        check_date = datetime.now(NY_TZ).date()

    if check_date not in US_MARKET_HOLIDAYS:
        return False, None

    day_name, is_early = US_MARKET_HOLIDAYS[check_date]
    if is_early:
        return True, day_name
    return False, None
