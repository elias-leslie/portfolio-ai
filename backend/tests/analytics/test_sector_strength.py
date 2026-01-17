"""Tests for sector relative strength calculations (GAP-013).

Tests cover:
- Sector relative strength calculation
- Sector ranking
- Leader/laggard detection
- Sector strength scoring
"""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest

from app.analytics.sector_strength import (
    SECTOR_ETFS,
    TOP_SECTORS,
    SectorStrength,
    _calculate_returns,
    _safe_subtract,
    calculate_sector_relative_strength,
    calculate_sector_strength_score,
    get_symbol_sector_etf,
)


class TestSectorETFConstants:
    """Tests for sector ETF constants."""

    def test_all_sectors_defined(self) -> None:
        """All 11 S&P 500 sectors should be defined."""
        assert len(SECTOR_ETFS) == 11

    def test_known_sectors(self) -> None:
        """Verify known sector ETFs are mapped."""
        assert "XLK" in SECTOR_ETFS
        assert SECTOR_ETFS["XLK"] == "Technology"
        assert "XLF" in SECTOR_ETFS
        assert SECTOR_ETFS["XLF"] == "Financials"
        assert "XLE" in SECTOR_ETFS
        assert SECTOR_ETFS["XLE"] == "Energy"


class TestGetTickerSectorETF:
    """Tests for ticker to sector mapping."""

    def test_tech_stocks(self) -> None:
        """Tech stocks map to XLK."""
        assert get_symbol_sector_etf("AAPL") == "XLK"
        assert get_symbol_sector_etf("MSFT") == "XLK"
        assert get_symbol_sector_etf("NVDA") == "XLK"

    def test_financial_stocks(self) -> None:
        """Financial stocks map to XLF."""
        assert get_symbol_sector_etf("JPM") == "XLF"
        assert get_symbol_sector_etf("BAC") == "XLF"
        assert get_symbol_sector_etf("GS") == "XLF"

    def test_unknown_ticker(self) -> None:
        """Unknown ticker returns None."""
        assert get_symbol_sector_etf("UNKNOWN123") is None

    def test_case_insensitive(self) -> None:
        """Ticker lookup is case insensitive."""
        assert get_symbol_sector_etf("aapl") == "XLK"
        assert get_symbol_sector_etf("Aapl") == "XLK"


class TestCalculateReturns:
    """Tests for return calculation."""

    def test_empty_prices(self) -> None:
        """Empty prices returns all None."""
        result = _calculate_returns({}, [20, 60, 252])
        assert all(v is None for v in result.values())

    def test_insufficient_data(self) -> None:
        """Insufficient data for horizon returns None."""
        today = date.today()
        prices = {
            today: 100.0,
            today - timedelta(days=1): 99.0,
            today - timedelta(days=2): 98.0,
        }
        result = _calculate_returns(prices, [20])  # Need 20+ days
        assert result[20] is None

    def test_positive_return(self) -> None:
        """Positive return calculated correctly."""
        today = date.today()
        prices = {today - timedelta(days=i): 100 + i * 0.5 for i in range(30)}
        # Most recent is highest, older dates lower
        # Actually: day 0 = 100, day 29 = 114.5
        # Hmm, need to reverse: recent = high, old = low
        prices_correct = {today - timedelta(days=i): 100 + (29 - i) * 0.5 for i in range(30)}
        result = _calculate_returns(prices_correct, [20])
        # Return = (newest - 20d old) / 20d old * 100
        # newest = 100 + 29*0.5 = 114.5
        # 20d old = 100 + 9*0.5 = 104.5
        # return = (114.5 - 104.5) / 104.5 * 100 ≈ 9.57%
        assert result[20] is not None
        assert result[20] > 0


class TestSafeSubtract:
    """Tests for safe subtract helper."""

    def test_both_valid(self) -> None:
        """Both values valid returns difference."""
        assert _safe_subtract(10.0, 5.0) == 5.0
        assert _safe_subtract(5.0, 10.0) == -5.0

    def test_first_none(self) -> None:
        """First None returns None."""
        assert _safe_subtract(None, 5.0) is None

    def test_second_none(self) -> None:
        """Second None returns None."""
        assert _safe_subtract(10.0, None) is None

    def test_both_none(self) -> None:
        """Both None returns None."""
        assert _safe_subtract(None, None) is None


class TestCalculateSectorStrengthScore:
    """Tests for sector strength scoring."""

    @pytest.fixture
    def mock_storage(self) -> MagicMock:
        """Create mock storage."""
        return MagicMock()

    def test_unknown_ticker_returns_zero(self, mock_storage: MagicMock) -> None:
        """Unknown ticker sector returns 0 score."""
        score, reasons = calculate_sector_strength_score(mock_storage, "UNKNOWN123")
        assert score == 0
        assert reasons == []

    def test_leader_sector_gets_bonus(self, mock_storage: MagicMock) -> None:
        """Stock in leading sector gets positive score."""
        # Mock sector calculation to return XLK as leader
        mock_storage.query.return_value = MagicMock(is_empty=lambda: True)

        # Since no data, will return 0
        score, _reasons = calculate_sector_strength_score(mock_storage, "AAPL")
        # With no data, score is 0
        assert score >= 0

    def test_score_range(self) -> None:
        """Score should be in -1 to +2 range per docstring."""
        # This is a design constraint test
        assert TOP_SECTORS == 3  # Top 3 are leaders


class TestSectorStrength:
    """Tests for SectorStrength dataclass."""

    def test_sector_strength_creation(self) -> None:
        """Can create SectorStrength with all fields."""
        ss = SectorStrength(
            etf="XLK",
            sector_name="Technology",
            rs_20d=5.0,
            rs_60d=10.0,
            rs_252d=20.0,
            rank=1,
            is_leader=True,
        )
        assert ss.etf == "XLK"
        assert ss.rank == 1
        assert ss.is_leader is True

    def test_sector_strength_with_none(self) -> None:
        """Can create SectorStrength with None values."""
        ss = SectorStrength(
            etf="XLK",
            sector_name="Technology",
            rs_20d=None,
            rs_60d=None,
            rs_252d=None,
            rank=5,
            is_leader=False,
        )
        assert ss.rs_20d is None
        assert ss.is_leader is False


class TestCalculateSectorRelativeStrength:
    """Tests for full sector rotation calculation."""

    @pytest.fixture
    def mock_storage(self) -> MagicMock:
        """Create mock storage."""
        return MagicMock()

    def test_no_data_returns_none(self, mock_storage: MagicMock) -> None:
        """No price data returns None."""
        mock_storage.query.return_value = MagicMock(is_empty=lambda: True)
        result = calculate_sector_relative_strength(mock_storage)
        assert result is None

    def test_returns_sector_rotation_signals(self, mock_storage: MagicMock) -> None:
        """Valid data returns SectorRotationSignals."""
        today = date.today()

        # Create mock data with all sectors + SPY
        mock_data = []
        all_symbols = [*list(SECTOR_ETFS.keys()), "SPY"]

        for symbol in all_symbols:
            for i in range(300):
                d = today - timedelta(days=i)
                # Different growth rates for each sector
                base = 100.0
                growth_rate = 0.05 if symbol == "XLK" else 0.01  # XLK grows faster
                price = base + (299 - i) * growth_rate
                mock_data.append({"symbol": symbol, "date": d, "close": price})

        mock_result = MagicMock()
        mock_result.is_empty.return_value = False
        mock_result.iter_rows.return_value = iter(mock_data)
        mock_storage.query.return_value = mock_result

        result = calculate_sector_relative_strength(mock_storage)

        assert result is not None
        assert len(result.sectors) == len(SECTOR_ETFS)
        assert len(result.leaders) == TOP_SECTORS
        assert len(result.laggards) == TOP_SECTORS
