"""Unit tests for market hours utilities."""

from datetime import UTC, datetime

import pytest

from app.utils.market_hours import NY_TZ, get_market_aware_age_hours, is_market_hours, is_stale


class TestIsMarketHours:
    """Test is_market_hours() function."""

    def test_wednesday_10_30_am_et_returns_true(self) -> None:
        """Market is open on Wednesday at 10:30 AM ET."""
        # Wednesday, October 29, 2025, 10:30 AM ET
        dt = datetime(2025, 10, 29, 10, 30, tzinfo=NY_TZ)
        assert is_market_hours(dt) is True

    def test_wednesday_5_00_pm_et_returns_false(self) -> None:
        """Market is closed on Wednesday at 5:00 PM ET (after close)."""
        # Wednesday, October 29, 2025, 5:00 PM ET
        dt = datetime(2025, 10, 29, 17, 0, tzinfo=NY_TZ)
        assert is_market_hours(dt) is False

    def test_saturday_10_30_am_et_returns_false(self) -> None:
        """Market is closed on Saturday."""
        # Saturday, November 1, 2025, 10:30 AM ET
        dt = datetime(2025, 11, 1, 10, 30, tzinfo=NY_TZ)
        assert is_market_hours(dt) is False

    def test_sunday_10_30_am_et_returns_false(self) -> None:
        """Market is closed on Sunday."""
        # Sunday, November 2, 2025, 10:30 AM ET
        dt = datetime(2025, 11, 2, 10, 30, tzinfo=NY_TZ)
        assert is_market_hours(dt) is False

    def test_wednesday_9_00_am_et_returns_false(self) -> None:
        """Market is closed at 9:00 AM ET (before open at 9:30 AM)."""
        # Wednesday, October 29, 2025, 9:00 AM ET
        dt = datetime(2025, 10, 29, 9, 0, tzinfo=NY_TZ)
        assert is_market_hours(dt) is False

    def test_wednesday_9_30_am_et_returns_true(self) -> None:
        """Market opens at exactly 9:30 AM ET."""
        # Wednesday, October 29, 2025, 9:30 AM ET
        dt = datetime(2025, 10, 29, 9, 30, tzinfo=NY_TZ)
        assert is_market_hours(dt) is True

    def test_wednesday_4_00_pm_et_returns_false(self) -> None:
        """Market closes at exactly 4:00 PM ET."""
        # Wednesday, October 29, 2025, 4:00 PM ET
        dt = datetime(2025, 10, 29, 16, 0, tzinfo=NY_TZ)
        assert is_market_hours(dt) is False

    def test_wednesday_3_59_pm_et_returns_true(self) -> None:
        """Market is still open at 3:59 PM ET (one minute before close)."""
        # Wednesday, October 29, 2025, 3:59 PM ET
        dt = datetime(2025, 10, 29, 15, 59, tzinfo=NY_TZ)
        assert is_market_hours(dt) is True

    def test_monday_10_30_am_et_returns_true(self) -> None:
        """Market is open on Monday."""
        # Monday, October 27, 2025, 10:30 AM ET
        dt = datetime(2025, 10, 27, 10, 30, tzinfo=NY_TZ)
        assert is_market_hours(dt) is True

    def test_friday_2_00_pm_et_returns_true(self) -> None:
        """Market is open on Friday."""
        # Friday, October 31, 2025, 2:00 PM ET
        dt = datetime(2025, 10, 31, 14, 0, tzinfo=NY_TZ)
        assert is_market_hours(dt) is True


class TestIsStale:
    """Test is_stale() function."""

    def test_10_min_old_during_market_hours_not_stale(self) -> None:
        """Data 10 minutes old during market hours is not stale (<15 min threshold)."""
        fetched_at = datetime(2025, 10, 29, 10, 20, tzinfo=NY_TZ)
        now = datetime(2025, 10, 29, 10, 30, tzinfo=NY_TZ)
        assert is_stale(fetched_at, now) is False

    def test_20_min_old_during_market_hours_is_stale(self) -> None:
        """Data 20 minutes old during market hours is stale (>15 min threshold)."""
        fetched_at = datetime(2025, 10, 29, 10, 10, tzinfo=NY_TZ)
        now = datetime(2025, 10, 29, 10, 30, tzinfo=NY_TZ)
        assert is_stale(fetched_at, now) is True

    def test_15_min_old_during_market_hours_not_stale(self) -> None:
        """Data exactly 15 minutes old during market hours is not stale (boundary test)."""
        fetched_at = datetime(2025, 10, 29, 10, 15, tzinfo=NY_TZ)
        now = datetime(2025, 10, 29, 10, 30, tzinfo=NY_TZ)
        assert is_stale(fetched_at, now) is False

    def test_5_hours_old_after_hours_not_stale(self) -> None:
        """Data 5 hours old after market hours is not stale (<24 hour threshold)."""
        fetched_at = datetime(2025, 10, 29, 12, 0, tzinfo=NY_TZ)
        now = datetime(2025, 10, 29, 17, 0, tzinfo=NY_TZ)
        assert is_stale(fetched_at, now) is False

    def test_25_hours_old_after_hours_is_stale(self) -> None:
        """Data 25 hours old after market hours is stale (>24 hour threshold)."""
        fetched_at = datetime(2025, 10, 28, 16, 0, tzinfo=NY_TZ)
        now = datetime(2025, 10, 29, 17, 0, tzinfo=NY_TZ)
        assert is_stale(fetched_at, now) is True

    def test_24_hours_old_after_hours_not_stale(self) -> None:
        """Data exactly 24 hours old after market hours is not stale (boundary test)."""
        fetched_at = datetime(2025, 10, 28, 17, 0, tzinfo=NY_TZ)
        now = datetime(2025, 10, 29, 17, 0, tzinfo=NY_TZ)
        assert is_stale(fetched_at, now) is False

    def test_30_min_old_after_hours_not_stale(self) -> None:
        """Data 30 minutes old after hours is not stale (different threshold than market hours)."""
        # After 4 PM ET, data is not stale even if >15 minutes old
        fetched_at = datetime(2025, 10, 29, 16, 30, tzinfo=NY_TZ)
        now = datetime(2025, 10, 29, 17, 0, tzinfo=NY_TZ)
        assert is_stale(fetched_at, now) is False

    def test_saturday_old_data_uses_after_hours_threshold(self) -> None:
        """Data on Saturday uses after-hours threshold (24 hours)."""
        # Saturday, data from Friday morning (>24h ago) is stale
        fetched_at = datetime(2025, 10, 31, 10, 0, tzinfo=NY_TZ)  # Friday
        now = datetime(2025, 11, 1, 11, 0, tzinfo=NY_TZ)  # Saturday, 25h later
        assert is_stale(fetched_at, now) is True

    def test_timezone_aware_required(self) -> None:
        """Fetched_at must be timezone-aware."""
        # Naive datetime (no timezone)
        fetched_at = datetime(2025, 10, 29, 10, 0)
        now = datetime(2025, 10, 29, 10, 30, tzinfo=NY_TZ)

        with pytest.raises(ValueError, match="must be timezone-aware"):
            is_stale(fetched_at, now)


class TestMarketAwareAge:
    """Test get_market_aware_age_hours()."""

    def test_uses_market_day_instead_of_utc_day_after_hours(self) -> None:
        """Evening ET checks age from the expected market close, not the UTC day."""
        last_update = datetime(2026, 3, 9, 22, 30, tzinfo=NY_TZ)
        now = datetime(2026, 3, 11, 0, 0, tzinfo=UTC)

        age_hours = get_market_aware_age_hours(
            last_update=last_update,
            now=now,
            is_market_data=True,
        )

        assert age_hours == 4.0

    def test_latest_expected_daily_bar_is_current_during_monday_market_hours(self) -> None:
        """Friday's completed daily bar is still current before Monday closes."""
        last_update = datetime(2026, 5, 1, 16, 0, tzinfo=NY_TZ)
        now = datetime(2026, 5, 4, 12, 0, tzinfo=NY_TZ)

        age_hours = get_market_aware_age_hours(
            last_update=last_update,
            now=now,
            is_market_data=True,
        )

        assert age_hours == 0.0
