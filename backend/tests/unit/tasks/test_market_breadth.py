"""Unit tests for market breadth calculation."""

from __future__ import annotations

import datetime as dt
from unittest.mock import MagicMock

import pytest

from app.tasks.market_data.fear_greed_pipeline import _calculate_market_breadth


class TestCalculateMarketBreadth:
    """Test _calculate_market_breadth helper function."""

    @pytest.fixture
    def mock_storage(self) -> MagicMock:
        """Create mock storage with connection context manager."""
        storage = MagicMock()
        conn = MagicMock()
        storage.connection.return_value.__enter__ = MagicMock(return_value=conn)
        storage.connection.return_value.__exit__ = MagicMock(return_value=False)
        return storage

    def test_all_sectors_up(self, mock_storage: MagicMock) -> None:
        """Test market breadth when all sectors are up (100%)."""
        target_date = dt.date(2025, 11, 12)

        # Mock query result: all 11 sectors up
        mock_conn = mock_storage.connection.return_value.__enter__.return_value
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            ("XLK", 300.0, 295.0),  # Tech up
            ("XLF", 53.0, 52.0),  # Financials up
            ("XLE", 90.0, 88.0),  # Energy up
            ("XLV", 150.0, 148.0),  # Healthcare up
            ("XLY", 200.0, 195.0),  # Consumer Discretionary up
            ("XLP", 80.0, 79.0),  # Consumer Staples up
            ("XLI", 120.0, 118.0),  # Industrials up
            ("XLU", 70.0, 69.0),  # Utilities up
            ("XLRE", 40.0, 39.0),  # Real Estate up
            ("XLB", 85.0, 84.0),  # Materials up
            ("XLC", 75.0, 74.0),  # Communication Services up
        ]
        mock_conn.execute.return_value = mock_result

        breadth_pct = _calculate_market_breadth(mock_storage, target_date)

        assert breadth_pct == 100.0
        assert mock_conn.execute.called

    def test_mixed_sectors(self, mock_storage: MagicMock) -> None:
        """Test market breadth with mixed sector performance (6 up, 5 down)."""
        target_date = dt.date(2025, 11, 12)

        # Mock query result: 6 sectors up, 5 down
        mock_conn = mock_storage.connection.return_value.__enter__.return_value
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            ("XLK", 300.0, 295.0),  # Tech up
            ("XLF", 53.0, 54.0),  # Financials down
            ("XLE", 90.0, 92.0),  # Energy down
            ("XLV", 150.0, 148.0),  # Healthcare up
            ("XLY", 200.0, 195.0),  # Consumer Discretionary up
            ("XLP", 80.0, 81.0),  # Consumer Staples down
            ("XLI", 120.0, 118.0),  # Industrials up
            ("XLU", 70.0, 71.0),  # Utilities down
            ("XLRE", 40.0, 39.0),  # Real Estate up
            ("XLB", 85.0, 86.0),  # Materials down
            ("XLC", 75.0, 74.0),  # Communication Services up
        ]
        mock_conn.execute.return_value = mock_result

        breadth_pct = _calculate_market_breadth(mock_storage, target_date)

        # 6 out of 11 = 54.54%
        assert breadth_pct == pytest.approx(54.54, rel=0.01)

    def test_all_sectors_down(self, mock_storage: MagicMock) -> None:
        """Test market breadth when all sectors are down (0%)."""
        target_date = dt.date(2025, 11, 12)

        # Mock query result: all 11 sectors down
        mock_conn = mock_storage.connection.return_value.__enter__.return_value
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            ("XLK", 295.0, 300.0),  # Tech down
            ("XLF", 52.0, 53.0),  # Financials down
            ("XLE", 88.0, 90.0),  # Energy down
            ("XLV", 148.0, 150.0),  # Healthcare down
            ("XLY", 195.0, 200.0),  # Consumer Discretionary down
            ("XLP", 79.0, 80.0),  # Consumer Staples down
            ("XLI", 118.0, 120.0),  # Industrials down
            ("XLU", 69.0, 70.0),  # Utilities down
            ("XLRE", 39.0, 40.0),  # Real Estate down
            ("XLB", 84.0, 85.0),  # Materials down
            ("XLC", 74.0, 75.0),  # Communication Services down
        ]
        mock_conn.execute.return_value = mock_result

        breadth_pct = _calculate_market_breadth(mock_storage, target_date)

        assert breadth_pct == 0.0

    def test_insufficient_data_returns_none(self, mock_storage: MagicMock) -> None:
        """Test that insufficient data (<8 sectors) returns None."""
        target_date = dt.date(2025, 11, 12)

        # Mock query result: only 7 sectors (below minimum of 8)
        mock_conn = mock_storage.connection.return_value.__enter__.return_value
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            ("XLK", 300.0, 295.0),
            ("XLF", 53.0, 52.0),
            ("XLE", 90.0, 88.0),
            ("XLV", 150.0, 148.0),
            ("XLY", 200.0, 195.0),
            ("XLP", 80.0, 79.0),
            ("XLI", 120.0, 118.0),
        ]
        mock_conn.execute.return_value = mock_result

        breadth_pct = _calculate_market_breadth(mock_storage, target_date)

        assert breadth_pct is None

    def test_no_data_returns_none(self, mock_storage: MagicMock) -> None:
        """Test that no data returns None."""
        target_date = dt.date(2025, 11, 12)

        # Mock query result: empty (no data)
        mock_conn = mock_storage.connection.return_value.__enter__.return_value
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_conn.execute.return_value = mock_result

        breadth_pct = _calculate_market_breadth(mock_storage, target_date)

        assert breadth_pct is None

    def test_missing_previous_close_excluded(self, mock_storage: MagicMock) -> None:
        """Test that sectors with missing previous close are excluded."""
        target_date = dt.date(2025, 11, 12)

        # Mock query result: 2 sectors missing prev_close (None)
        mock_conn = mock_storage.connection.return_value.__enter__.return_value
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            ("XLK", 300.0, 295.0),  # Valid, up
            ("XLF", 53.0, None),  # Missing prev_close, excluded
            ("XLE", 90.0, 88.0),  # Valid, up
            ("XLV", 150.0, 148.0),  # Valid, up
            ("XLY", 200.0, None),  # Missing prev_close, excluded
            ("XLP", 80.0, 79.0),  # Valid, up
            ("XLI", 120.0, 118.0),  # Valid, up
            ("XLU", 70.0, 69.0),  # Valid, up
            ("XLRE", 40.0, 39.0),  # Valid, up
            ("XLB", 85.0, 84.0),  # Valid, up
            ("XLC", 75.0, 74.0),  # Valid, up
        ]
        mock_conn.execute.return_value = mock_result

        breadth_pct = _calculate_market_breadth(mock_storage, target_date)

        # 9 valid sectors (2 excluded), all up = 100%
        assert breadth_pct == 100.0

    def test_exact_minimum_sectors(self, mock_storage: MagicMock) -> None:
        """Test with exact minimum sectors (8) - should succeed."""
        target_date = dt.date(2025, 11, 12)

        # Mock query result: exactly 8 sectors (minimum required)
        mock_conn = mock_storage.connection.return_value.__enter__.return_value
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            ("XLK", 300.0, 295.0),  # Up
            ("XLF", 53.0, 52.0),  # Up
            ("XLE", 90.0, 92.0),  # Down
            ("XLV", 150.0, 148.0),  # Up
            ("XLY", 200.0, 195.0),  # Up
            ("XLP", 80.0, 79.0),  # Up
            ("XLI", 120.0, 118.0),  # Up
            ("XLU", 70.0, 71.0),  # Down
        ]
        mock_conn.execute.return_value = mock_result

        breadth_pct = _calculate_market_breadth(mock_storage, target_date)

        # 6 out of 8 = 75%
        assert breadth_pct == 75.0
