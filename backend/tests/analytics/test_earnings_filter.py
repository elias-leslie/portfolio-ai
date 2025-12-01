"""Tests for earnings proximity filter (GAP-003)."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import polars as pl
import pytest

from app.analytics.earnings_filter import (
    MIN_DAYS_BEFORE_EARNINGS,
    check_earnings_proximity,
    get_next_earnings_date,
    should_block_for_earnings,
)


class TestGetNextEarningsDate:
    """Tests for earnings date retrieval from cache."""

    def test_earnings_date_from_cache(self) -> None:
        """Returns earnings date from cache."""
        storage = MagicMock()
        earnings_date = "2025-12-15T00:00:00"
        storage.query.return_value = pl.DataFrame({
            "payload": [{"earnings_date": earnings_date}]
        })

        result = get_next_earnings_date(storage, "AAPL")

        assert result is not None
        assert result.isoformat() == earnings_date

    def test_no_cache_returns_none(self) -> None:
        """Returns None when no cache entry exists."""
        storage = MagicMock()
        storage.query.return_value = pl.DataFrame()

        result = get_next_earnings_date(storage, "NEWSTOCK")

        assert result is None

    def test_null_earnings_date_returns_none(self) -> None:
        """Returns None when cached earnings_date is null."""
        storage = MagicMock()
        storage.query.return_value = pl.DataFrame({
            "payload": [{"earnings_date": None}]
        })

        result = get_next_earnings_date(storage, "AAPL")

        assert result is None


class TestCheckEarningsProximity:
    """Tests for earnings proximity check."""

    def test_far_from_earnings_passes(self) -> None:
        """Trade allowed when far from earnings."""
        storage = MagicMock()
        # Earnings 30 days away
        future_date = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        earnings_date = (future_date.replace(tzinfo=None) +
                        __import__("datetime").timedelta(days=30))
        storage.query.return_value = pl.DataFrame({
            "payload": [{"earnings_date": earnings_date.isoformat()}]
        })

        is_ok, message, details = check_earnings_proximity(storage, "AAPL")

        assert is_ok is True
        assert "OK" in message

    def test_close_to_earnings_blocks(self) -> None:
        """Trade blocked when too close to earnings."""
        storage = MagicMock()
        # Earnings tomorrow
        future_date = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        earnings_date = (future_date.replace(tzinfo=None) +
                        __import__("datetime").timedelta(days=1))
        storage.query.return_value = pl.DataFrame({
            "payload": [{"earnings_date": earnings_date.isoformat()}]
        })

        is_ok, message, details = check_earnings_proximity(storage, "AAPL")

        assert is_ok is False
        assert "BLOCKED" in message
        assert details["days_away"] == 1

    def test_earnings_today_blocks(self) -> None:
        """Trade blocked on earnings day."""
        storage = MagicMock()
        # Earnings today
        today = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0, tzinfo=None
        )
        storage.query.return_value = pl.DataFrame({
            "payload": [{"earnings_date": today.isoformat()}]
        })

        is_ok, message, details = check_earnings_proximity(storage, "AAPL")

        assert is_ok is False
        assert "BLOCKED" in message

    def test_past_earnings_allows(self) -> None:
        """Trade allowed after earnings has passed."""
        storage = MagicMock()
        # Earnings 5 days ago
        past_date = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        earnings_date = (past_date.replace(tzinfo=None) -
                        __import__("datetime").timedelta(days=5))
        storage.query.return_value = pl.DataFrame({
            "payload": [{"earnings_date": earnings_date.isoformat()}]
        })

        is_ok, message, details = check_earnings_proximity(storage, "AAPL")

        assert is_ok is True
        assert "passed" in message.lower()

    def test_unknown_earnings_allows_with_warning(self) -> None:
        """Trade allowed when earnings date unknown."""
        storage = MagicMock()
        storage.query.return_value = pl.DataFrame()

        is_ok, message, details = check_earnings_proximity(storage, "NEWSTOCK")

        assert is_ok is True
        assert "unknown" in message.lower()


class TestShouldBlockForEarnings:
    """Tests for quick block check."""

    def test_returns_true_when_too_close(self) -> None:
        """Returns True (block) when too close to earnings."""
        storage = MagicMock()
        # Earnings tomorrow
        future_date = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        earnings_date = (future_date.replace(tzinfo=None) +
                        __import__("datetime").timedelta(days=1))
        storage.query.return_value = pl.DataFrame({
            "payload": [{"earnings_date": earnings_date.isoformat()}]
        })

        should_block = should_block_for_earnings(storage, "AAPL")

        assert should_block is True

    def test_returns_false_when_far(self) -> None:
        """Returns False (allow) when far from earnings."""
        storage = MagicMock()
        # Earnings 30 days away
        future_date = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        earnings_date = (future_date.replace(tzinfo=None) +
                        __import__("datetime").timedelta(days=30))
        storage.query.return_value = pl.DataFrame({
            "payload": [{"earnings_date": earnings_date.isoformat()}]
        })

        should_block = should_block_for_earnings(storage, "AAPL")

        assert should_block is False
