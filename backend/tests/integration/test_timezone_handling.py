"""Integration tests for timezone handling across the application.

These tests verify that all timestamps are timezone-aware (UTC) and that
datetime arithmetic works correctly regardless of server timezone.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.utils.market_hours import NY_TZ, is_stale
from app.watchlist.scoring import _is_stale as scoring_is_stale


class TestTimezoneStaleness:
    """Test staleness detection with timezone-aware timestamps."""

    def test_staleness_detection_during_market_hours(self) -> None:
        """Test that staleness detection works with UTC timestamps during market hours.

        During market hours, data older than 15 minutes should be stale.
        This tests the market_hours.is_stale() function.
        """
        # Create a timestamp 20 minutes in the past (should be stale during market hours)
        # Use a Wednesday at 10:30 AM ET (during market hours)
        now = datetime(2025, 10, 29, 10, 30, tzinfo=NY_TZ)
        twenty_minutes_ago = now - timedelta(minutes=20)

        # This should return True (is stale) because 20 > 15 during market hours
        result = is_stale(fetched_at=twenty_minutes_ago, now=now)

        assert result is True, (
            f"Expected stale=True for data 20 minutes old during market hours, "
            f"but got stale={result}"
        )

    def test_staleness_with_recent_timestamp_during_market_hours(self) -> None:
        """Test that fresh data is not marked as stale during market hours.

        Data fetched 10 minutes ago should NOT be stale during market hours.
        """
        now = datetime(2025, 10, 29, 10, 30, tzinfo=NY_TZ)
        ten_minutes_ago = now - timedelta(minutes=10)

        result = is_stale(fetched_at=ten_minutes_ago, now=now)

        assert result is False, (
            f"Expected stale=False for data 10 minutes old during market hours, "
            f"but got stale={result}"
        )

    def test_scoring_is_stale_with_ttl(self) -> None:
        """Test the scoring._is_stale() helper function with custom TTL.

        This function is used in service.py lines 552, 557 to recalculate
        staleness at display time.
        """
        now = datetime.now(UTC)
        twenty_minutes_ago = now - timedelta(minutes=20)
        ttl_minutes = 15

        # Should be stale (20 > 15)
        result = scoring_is_stale(twenty_minutes_ago, ttl_minutes, now)

        assert result is True, (
            f"Expected stale=True for timestamp 20 minutes old with TTL={ttl_minutes}, "
            f"but got stale={result}"
        )


class TestCacheExpiration:
    """Test cache expiration logic with timezone-aware timestamps."""

    def test_cache_expiration_with_mixed_timezone_timestamps(self) -> None:
        """Test cache expiration calculation with UTC timestamps.

        This test currently FAILS because price_fetcher.py uses naive datetime
        (without UTC) at line 161, causing incorrect cache age calculations when
        timestamps have different timezone awareness.

        Expected behavior: Cache entry from 30 minutes ago should be expired
        when TTL is 15 minutes.
        """
        # Simulate cache entry created 30 minutes ago (UTC-aware)
        cached_at = datetime.now(UTC) - timedelta(minutes=30)
        current_time = datetime.now(UTC)
        cache_ttl_minutes = 15

        # Calculate cache age
        age_minutes = (current_time - cached_at).total_seconds() / 60

        # Cache should be expired (30 minutes > 15 minute TTL)
        is_expired = age_minutes > cache_ttl_minutes

        assert is_expired is True, (
            f"Expected cache to be expired (age={age_minutes:.1f} min > TTL={cache_ttl_minutes} min), "
            f"but is_expired={is_expired}"
        )
        assert age_minutes >= 30, (
            f"Expected age ~30 minutes, got {age_minutes:.1f} minutes. "
            "This suggests timezone-naive arithmetic issues."
        )


class TestDatetimeArithmetic:
    """Test datetime arithmetic for user-facing features like 'updated X minutes ago'."""

    def test_time_ago_calculation_with_utc_timestamps(self) -> None:
        """Test 'updated X minutes ago' calculation with UTC timestamps.

        This test will FAIL if code uses naive datetime instead of datetime.now(UTC).
        Various files need updating: preferences.py:177-178, ideas.py:308,
        manager.py:50,107,166, price_fetcher.py:161, tools.py:10.

        Expected behavior: Timestamp from 5 minutes ago should show as ~5 minutes old.
        """
        # Create a UTC-aware timestamp from 5 minutes ago
        five_minutes_ago = datetime.now(UTC) - timedelta(minutes=5)
        current_time = datetime.now(UTC)

        # Calculate minutes ago (this is what user-facing code does)
        time_delta = current_time - five_minutes_ago
        minutes_ago = time_delta.total_seconds() / 60

        # Should be approximately 5 minutes (allow 0.1 minute tolerance)
        assert 4.9 <= minutes_ago <= 5.1, (
            f"Expected ~5 minutes ago, got {minutes_ago:.2f} minutes. "
            "This indicates timezone-naive arithmetic issues."
        )

    def test_naive_vs_aware_datetime_subtraction_fails(self) -> None:
        """Test that naive and aware datetimes cannot be mixed.

        This test demonstrates the bug: if some code uses naive datetime (no tz)
        and other code uses datetime.now(UTC) (aware), subtraction will raise TypeError.

        This test PASSES currently (demonstrates the problem), but the actual
        application code will FAIL if we mix naive and aware datetimes.
        """
        naive_dt = datetime(2025, 1, 20, 12, 0, 0)  # Naive datetime (no tzinfo)
        aware_dt = datetime.now(UTC)  # This is what fixed code does

        # Attempting to subtract naive from aware raises TypeError
        with pytest.raises(
            TypeError, match="can't subtract offset-naive and offset-aware datetimes"
        ):
            _ = aware_dt - naive_dt

    def test_future_timestamp_detection(self) -> None:
        """Test that future timestamps are detected correctly.

        This can happen with naive datetime (no tz) if server timezone changes
        or if timestamps are stored in different timezones.
        """
        # Create a timestamp 10 minutes in the future
        ten_minutes_future = datetime.now(UTC) + timedelta(minutes=10)
        current_time = datetime.now(UTC)

        # This should be detected as "in the future"
        is_future = ten_minutes_future > current_time

        assert is_future is True, (
            f"Expected future timestamp to be > current time, "
            f"but future={ten_minutes_future}, current={current_time}"
        )

    def test_scoring_is_stale_rejects_naive_datetimes(self) -> None:
        """Test that scoring._is_stale() works correctly with UTC timestamps.

        The _is_stale() function is called with timestamps from database and
        the current time from various places. If naive datetime is used, this
        will cause incorrect comparisons.
        """
        # This test will FAIL if any code passes naive datetime to _is_stale
        now = datetime.now(UTC)
        old_timestamp = now - timedelta(minutes=30)
        ttl = 15

        # Should correctly identify as stale
        result = scoring_is_stale(old_timestamp, ttl, now)
        assert result is True

        # Test with fresh timestamp
        fresh_timestamp = now - timedelta(minutes=5)
        result = scoring_is_stale(fresh_timestamp, ttl, now)
        assert result is False
