"""Tests for earnings surprise scoring (GAP-003)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch

from app.analytics.earnings_surprise import (
    EarningsSurprise,
    calculate_earnings_surprise_score,
    fetch_earnings_surprises_from_finnhub,
    get_recent_earnings_surprises,
    save_earnings_surprises,
)


class TestEarningsSurpriseDataclass:
    """Tests for EarningsSurprise dataclass."""

    def test_create_full_surprise(self) -> None:
        """Test creating a complete earnings surprise record."""
        surprise = EarningsSurprise(
            symbol="NVDA",
            earnings_date=date(2024, 11, 20),
            fiscal_quarter="Q3 2024",
            eps_estimate=Decimal("0.58"),
            eps_actual=Decimal("0.62"),
            surprise_pct=Decimal("6.9"),
            surprise_direction="beat",
        )

        assert surprise.symbol == "NVDA"
        assert surprise.earnings_date == date(2024, 11, 20)
        assert surprise.fiscal_quarter == "Q3 2024"
        assert surprise.eps_estimate == Decimal("0.58")
        assert surprise.eps_actual == Decimal("0.62")
        assert surprise.surprise_pct == Decimal("6.9")
        assert surprise.surprise_direction == "beat"

    def test_create_minimal_surprise(self) -> None:
        """Test creating surprise with minimal required fields."""
        surprise = EarningsSurprise(
            symbol="AAPL",
            earnings_date=date(2024, 10, 31),
            fiscal_quarter=None,
            eps_estimate=None,
            eps_actual=None,
            surprise_pct=None,
            surprise_direction="inline",
        )

        assert surprise.symbol == "AAPL"
        assert surprise.fiscal_quarter is None


class TestFetchEarningsSurprises:
    """Tests for fetching earnings surprises from Finnhub."""

    @patch.dict("os.environ", {"FINNHUB_API_KEY": ""})
    def test_missing_api_key_returns_empty(self) -> None:
        """Test that missing API key returns empty list."""
        result = fetch_earnings_surprises_from_finnhub("NVDA")
        assert result == []

    @patch("app.analytics.earnings_surprise.requests.get")
    @patch.dict("os.environ", {"FINNHUB_API_KEY": "test_key"})
    def test_successful_fetch(self, mock_get: MagicMock) -> None:
        """Test successful API fetch and parsing."""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "actual": 0.62,
                "estimate": 0.58,
                "period": "2024-11-20",
                "surprisePercent": 6.9,
            },
            {
                "actual": 0.55,
                "estimate": 0.52,
                "period": "2024-08-21",
                "surprisePercent": 5.77,
            },
        ]
        mock_get.return_value = mock_response

        result = fetch_earnings_surprises_from_finnhub("NVDA", limit=2)

        assert len(result) == 2
        assert result[0].symbol == "NVDA"
        assert result[0].surprise_direction == "beat"
        assert result[0].eps_actual == Decimal("0.62")

    @patch("app.analytics.earnings_surprise.requests.get")
    @patch.dict("os.environ", {"FINNHUB_API_KEY": "test_key"})
    def test_skip_future_earnings(self, mock_get: MagicMock) -> None:
        """Test that future earnings without actuals are skipped."""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "actual": None,  # Future earnings, no actual yet
                "estimate": 0.65,
                "period": "2025-02-20",
            },
            {
                "actual": 0.62,
                "estimate": 0.58,
                "period": "2024-11-20",
                "surprisePercent": 6.9,
            },
        ]
        mock_get.return_value = mock_response

        result = fetch_earnings_surprises_from_finnhub("NVDA")

        assert len(result) == 1
        assert result[0].eps_actual is not None


class TestSaveEarningsSurprises:
    """Tests for saving earnings surprises to database."""

    def test_save_empty_list_returns_zero(self) -> None:
        """Test saving empty list returns zero."""
        mock_storage = MagicMock()
        result = save_earnings_surprises(mock_storage, [])
        assert result == 0
        # No connection opened for empty list
        mock_storage.connection.assert_not_called()

    def test_save_single_surprise(self) -> None:
        """Test saving a single earnings surprise."""
        # Mock the connection context manager
        mock_conn = MagicMock()
        mock_storage = MagicMock()
        mock_storage.connection.return_value.__enter__.return_value = mock_conn

        surprise = EarningsSurprise(
            symbol="NVDA",
            earnings_date=date(2024, 11, 20),
            fiscal_quarter="Q3 2024",
            eps_estimate=Decimal("0.58"),
            eps_actual=Decimal("0.62"),
            surprise_pct=Decimal("6.9"),
            surprise_direction="beat",
        )

        result = save_earnings_surprises(mock_storage, [surprise])

        assert result == 1
        # Implementation calls execute twice: once for symbol upsert, once for earnings insert
        assert mock_conn.execute.call_count == 2
        mock_conn.commit.assert_called_once()


class TestGetRecentEarningsSurprises:
    """Tests for retrieving earnings surprises from database."""

    def test_empty_result(self) -> None:
        """Test handling empty query result."""
        mock_storage = MagicMock()
        mock_result = MagicMock()
        mock_result.is_empty.return_value = True
        mock_storage.query.return_value = mock_result

        result = get_recent_earnings_surprises(mock_storage, "UNKNOWN")

        assert result == []

    def test_returns_dicts(self) -> None:
        """Test that results are returned as list of dicts."""
        mock_storage = MagicMock()
        mock_result = MagicMock()
        mock_result.is_empty.return_value = False
        mock_result.to_dicts.return_value = [
            {
                "symbol": "NVDA",
                "earnings_date": "2024-11-20",
                "surprise_direction": "beat",
            }
        ]
        mock_storage.query.return_value = mock_result

        result = get_recent_earnings_surprises(mock_storage, "NVDA")

        assert len(result) == 1
        assert result[0]["symbol"] == "NVDA"


class TestCalculateEarningsSurpriseScore:
    """Tests for earnings surprise scoring logic."""

    def _mock_storage_with_surprises(self, surprises: list[dict[str, Any]]) -> MagicMock:
        """Create mock storage with specified surprise data."""
        mock_storage = MagicMock()
        mock_result = MagicMock()
        mock_result.is_empty.return_value = len(surprises) == 0
        mock_result.to_dicts.return_value = surprises
        mock_storage.query.return_value = mock_result
        return mock_storage

    def test_no_data_returns_zero_score(self) -> None:
        """Test that no earnings data returns zero score."""
        mock_storage = self._mock_storage_with_surprises([])

        score, reasons = calculate_earnings_surprise_score(mock_storage, "UNKNOWN")

        assert score == 0
        assert reasons == []

    def test_consistent_beats_4_points(self) -> None:
        """Test 4+ beats with no misses = 4 points."""
        surprises = [
            {"symbol": "NVDA", "surprise_direction": "beat"},
            {"symbol": "NVDA", "surprise_direction": "beat"},
            {"symbol": "NVDA", "surprise_direction": "beat"},
            {"symbol": "NVDA", "surprise_direction": "beat"},
        ]
        mock_storage = self._mock_storage_with_surprises(surprises)

        score, reasons = calculate_earnings_surprise_score(mock_storage, "NVDA")

        assert score == 4
        assert len(reasons) == 1
        assert "4/4 quarters beat" in reasons[0]

    def test_good_track_record_3_points(self) -> None:
        """Test 2+ beats with 1 or fewer misses = 3 points."""
        surprises = [
            {"symbol": "NVDA", "surprise_direction": "beat"},
            {"symbol": "NVDA", "surprise_direction": "beat"},
            {"symbol": "NVDA", "surprise_direction": "inline"},
            {"symbol": "NVDA", "surprise_direction": "miss"},
        ]
        mock_storage = self._mock_storage_with_surprises(surprises)

        score, _reasons = calculate_earnings_surprise_score(mock_storage, "NVDA")

        assert score == 3

    def test_recent_beat_2_points(self) -> None:
        """Test recent beat (most recent quarter) = 2 points."""
        surprises: list[dict[str, Any]] = [
            {"symbol": "NVDA", "surprise_direction": "beat", "surprise_pct": 5.0},
            {"symbol": "NVDA", "surprise_direction": "miss"},
            {"symbol": "NVDA", "surprise_direction": "miss"},
        ]
        mock_storage = self._mock_storage_with_surprises(surprises)

        score, reasons = calculate_earnings_surprise_score(mock_storage, "NVDA")

        assert score == 2
        assert "Recent earnings beat" in reasons[0]

    def test_large_beat_shows_percentage(self) -> None:
        """Test large beat shows percentage in reason."""
        surprises = [
            {"symbol": "NVDA", "surprise_direction": "beat", "surprise_pct": 15.0},
        ]
        mock_storage = self._mock_storage_with_surprises(surprises)

        score, reasons = calculate_earnings_surprise_score(mock_storage, "NVDA")

        assert score == 2
        assert "+15.0% surprise" in reasons[0]

    def test_inline_results_1_point(self) -> None:
        """Test inline (met expectations) = 1 point."""
        surprises = [
            {"symbol": "NVDA", "surprise_direction": "inline"},
            {"symbol": "NVDA", "surprise_direction": "miss"},
        ]
        mock_storage = self._mock_storage_with_surprises(surprises)

        score, reasons = calculate_earnings_surprise_score(mock_storage, "NVDA")

        assert score == 1
        assert "met expectations" in reasons[0]

    def test_consistent_misses_negative_1(self) -> None:
        """Test consistent misses (3+) = -1 point."""
        surprises = [
            {"symbol": "BAD", "surprise_direction": "miss"},
            {"symbol": "BAD", "surprise_direction": "miss"},
            {"symbol": "BAD", "surprise_direction": "miss"},
        ]
        mock_storage = self._mock_storage_with_surprises(surprises)

        score, reasons = calculate_earnings_surprise_score(mock_storage, "BAD")

        assert score == -1
        assert "missed estimates" in reasons[0]

    def test_single_miss_zero_points(self) -> None:
        """Test single recent miss = 0 points (no reason)."""
        surprises = [
            {"symbol": "OOPS", "surprise_direction": "miss"},
        ]
        mock_storage = self._mock_storage_with_surprises(surprises)

        score, reasons = calculate_earnings_surprise_score(mock_storage, "OOPS")

        assert score == 0
        assert reasons == []
