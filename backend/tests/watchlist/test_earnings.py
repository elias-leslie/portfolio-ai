"""Tests for earnings calendar fetching and warning system."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import cast
from unittest.mock import MagicMock, patch

from app.storage.connection import ConnectionManager
from app.storage.types import DatabaseConnection
from app.utils.db_helpers import ensure_symbol_exists
from app.watchlist.earnings import (
    fetch_earnings_date,
    fetch_earnings_date_cached,
    generate_earnings_warning,
)


class TestFetchEarningsDate:
    """Test earnings date fetching from multiple sources."""

    @patch("app.watchlist.earnings.yf.Ticker")
    def test_fetch_from_yfinance_success(self, mock_ticker_class: MagicMock) -> None:
        """Test successful fetch from YFinance."""
        mock_ticker = MagicMock()
        # YFinance returns earnings date in calendar.earnings
        mock_ticker.calendar = {"Earnings Date": ["2025-11-15"]}
        mock_ticker_class.return_value = mock_ticker

        earnings_date = fetch_earnings_date("NVDA")

        assert earnings_date is not None
        assert isinstance(earnings_date, datetime)
        assert earnings_date.year == 2025
        assert earnings_date.month == 11
        assert earnings_date.day == 15

    @patch("app.watchlist.earnings.yf.Ticker")
    def test_fetch_from_yfinance_missing_calendar(self, mock_ticker_class: MagicMock) -> None:
        """Test YFinance with missing calendar data."""
        mock_ticker = MagicMock()
        mock_ticker.calendar = {}
        mock_ticker_class.return_value = mock_ticker

        with patch("app.watchlist.earnings._fetch_from_finnhub", return_value=None):
            earnings_date = fetch_earnings_date("NVDA")

        # Should return None when calendar is empty
        assert earnings_date is None

    @patch("app.watchlist.earnings.yf.Ticker")
    def test_fetch_from_yfinance_api_error(self, mock_ticker_class: MagicMock) -> None:
        """Test YFinance when API raises exception."""
        mock_ticker_class.side_effect = Exception("API Error")

        with patch("app.watchlist.earnings._fetch_from_finnhub", return_value=None):
            earnings_date = fetch_earnings_date("NVDA")

        assert earnings_date is None

    @patch("requests.get")
    @patch("app.watchlist.earnings.yf.Ticker")
    def test_failover_to_finnhub(self, mock_yf: MagicMock, mock_get: MagicMock) -> None:
        """Test failover to Finnhub when YFinance fails."""
        # YFinance returns None
        mock_yf.return_value.calendar = {}

        # Finnhub returns earnings calendar
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "earningsCalendar": [
                {
                    "date": "2025-11-15",
                    "symbol": "NVDA",
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        with patch.dict("os.environ", {"FINNHUB_API_KEY": "test_key"}):
            earnings_date = fetch_earnings_date("NVDA")

        assert earnings_date is not None
        assert earnings_date.year == 2025
        assert earnings_date.month == 11

    @patch("requests.get")
    @patch("app.watchlist.earnings.yf.Ticker")
    def test_all_sources_fail(self, mock_yf: MagicMock, mock_get: MagicMock) -> None:
        """Test when all sources fail."""
        # YFinance fails
        mock_yf.return_value.calendar = {}

        # Finnhub fails
        mock_get.side_effect = Exception("API Error")

        with patch.dict("os.environ", {"FINNHUB_API_KEY": "test_key"}):
            earnings_date = fetch_earnings_date("NVDA")

        assert earnings_date is None


class TestGenerateEarningsWarning:
    """Test earnings warning generation logic."""

    def test_warning_0_5_days_away(self) -> None:
        """Test 🔴 warning for earnings 0-5 days away."""
        # Earnings in 2 days
        earnings_date = datetime.now(UTC) + timedelta(days=2)

        warning = generate_earnings_warning(earnings_date)

        assert warning is not None
        assert "🔴" in warning
        assert "2 DAYS" in warning or "2 days" in warning
        assert "High volatility" in warning or "volatility" in warning.lower()

    def test_warning_6_14_days_away(self) -> None:
        """Test ⚠ warning for earnings 6-14 days away."""
        # Earnings in 10 days
        earnings_date = datetime.now(UTC) + timedelta(days=10)

        warning = generate_earnings_warning(earnings_date)

        assert warning is not None
        assert "⚠" in warning
        assert "10" in warning or "days" in warning

    def test_warning_15_30_days_away(self) -> None:
        """Test 💡 info for earnings 15-30 days away."""
        # Earnings in 20 days
        earnings_date = datetime.now(UTC) + timedelta(days=20)

        warning = generate_earnings_warning(earnings_date)

        assert warning is not None
        assert "💡" in warning
        assert "20" in warning or "3 weeks" in warning

    def test_no_warning_over_30_days(self) -> None:
        """Test no warning for earnings >30 days away."""
        # Earnings in 45 days
        earnings_date = datetime.now(UTC) + timedelta(days=45)

        warning = generate_earnings_warning(earnings_date)

        assert warning is None

    def test_warning_today(self) -> None:
        """Test 🔴 warning for earnings today."""
        earnings_date = datetime.now(UTC)

        warning = generate_earnings_warning(earnings_date)

        assert warning is not None
        assert "🔴" in warning
        assert "TODAY" in warning or "0" in warning

    def test_warning_past_earnings(self) -> None:
        """Test no warning for past earnings."""
        # Earnings was yesterday
        earnings_date = datetime.now(UTC) - timedelta(days=1)

        warning = generate_earnings_warning(earnings_date)

        assert warning is None

    def test_warning_none_input(self) -> None:
        """Test that None input returns None."""
        warning = generate_earnings_warning(None)

        assert warning is None

    def test_days_away_calculation(self) -> None:
        """Test that days_away is returned correctly."""
        # Earnings in 7 days
        earnings_date = datetime.now(UTC) + timedelta(days=7)

        warning = generate_earnings_warning(earnings_date)

        assert warning is not None
        # Should mention 7 days or "1 week"
        assert "7" in warning or "week" in warning.lower()


class TestEarningsCaching:
    """Test caching functionality for earnings dates (30-day TTL)."""

    @patch("app.watchlist.earnings.fetch_earnings_date")
    def test_cache_stores_earnings_date_on_first_fetch(self, mock_fetch: MagicMock) -> None:
        """Test that earnings date is stored in reference_cache on first fetch."""
        earnings_date = datetime(2025, 11, 15, 10, 0, 0)
        mock_fetch.return_value = earnings_date

        cm = ConnectionManager()
        with cm.connection() as conn:
            db_conn = cast(DatabaseConnection, conn)
            ensure_symbol_exists(db_conn, "NVDA")
            # First call should fetch from API and cache
            result = fetch_earnings_date_cached(db_conn, "NVDA")

            assert result is not None
            assert result == earnings_date

            # Verify data was cached
            cached_row = conn.execute(
                "SELECT payload FROM reference_cache WHERE symbol = %s AND source = %s",
                ["NVDA", "earnings"],
            ).fetchone()

            assert cached_row is not None
            cached_data = cached_row[0]
            assert isinstance(cached_data, dict)
            assert "earnings_date" in cached_data
            # Should be stored as ISO string
            assert cached_data["earnings_date"] == earnings_date.isoformat()

    @patch("app.watchlist.earnings.fetch_earnings_date")
    def test_cache_hit_avoids_refetch(self, mock_fetch: MagicMock) -> None:
        """Test that cache hit avoids calling API again (within 30-day TTL)."""
        earnings_date = datetime(2025, 12, 20, 16, 30, 0)
        mock_fetch.return_value = earnings_date

        cm = ConnectionManager()
        with cm.connection() as conn:
            db_conn = cast(DatabaseConnection, conn)
            ensure_symbol_exists(db_conn, "META")
            # First call - fetches from API
            result1 = fetch_earnings_date_cached(db_conn, "META")
            assert result1 is not None
            assert result1 == earnings_date
            assert mock_fetch.call_count == 1

            # Second call within TTL - should use cache, not call API again
            result2 = fetch_earnings_date_cached(db_conn, "META")
            assert result2 is not None
            assert result2 == earnings_date
            assert mock_fetch.call_count == 1  # Still only 1 call

    @patch("app.watchlist.earnings.fetch_earnings_date")
    def test_cache_ttl_expiration_triggers_refresh(self, mock_fetch: MagicMock) -> None:
        """Test that cache older than 30 days triggers re-fetch."""
        # First fetch
        old_earnings = datetime(2025, 11, 15, 10, 0, 0)
        mock_fetch.return_value = old_earnings

        cm = ConnectionManager()
        with cm.connection() as conn:
            db_conn = cast(DatabaseConnection, conn)
            ensure_symbol_exists(db_conn, "NVDA")
            # First call - caches data
            result1 = fetch_earnings_date_cached(db_conn, "NVDA")
            assert result1 is not None
            assert result1 == old_earnings
            assert mock_fetch.call_count == 1

            # Manually age the cache to 31 days ago (expired)
            expired_date = date.today() - timedelta(days=31)
            conn.execute(
                "UPDATE reference_cache SET as_of_date = %s WHERE symbol = %s AND source = %s",
                [expired_date.isoformat(), "NVDA", "earnings"],
            )
            conn.commit()

            # Updated data for second fetch
            new_earnings = datetime(2025, 12, 20, 16, 0, 0)
            mock_fetch.return_value = new_earnings

            # Second call - should detect stale cache and re-fetch
            result2 = fetch_earnings_date_cached(db_conn, "NVDA")
            assert result2 is not None
            assert result2 == new_earnings  # New data
            assert mock_fetch.call_count == 2  # Called again

    @patch("app.watchlist.earnings.fetch_earnings_date")
    def test_cache_handles_none_return_gracefully(self, mock_fetch: MagicMock) -> None:
        """Test that None return from API is cached (to avoid repeated lookups)."""
        mock_fetch.return_value = None  # No earnings date available

        cm = ConnectionManager()
        with cm.connection() as conn:
            db_conn = cast(DatabaseConnection, conn)
            ensure_symbol_exists(db_conn, "UNKNOWN")
            result = fetch_earnings_date_cached(db_conn, "UNKNOWN")

            assert result is None
            # Should have cached the None result
            cached_row = conn.execute(
                "SELECT payload FROM reference_cache WHERE symbol = %s AND source = %s",
                ["UNKNOWN", "earnings"],
            ).fetchone()
            assert cached_row is not None
            cached_data = cached_row[0]
            assert isinstance(cached_data, dict)
            assert cached_data["earnings_date"] is None
