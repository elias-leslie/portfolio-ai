"""Unit tests for PortfolioAnalytics."""

from __future__ import annotations

import math
from unittest.mock import MagicMock, patch

import pytest

from app.portfolio.analytics import PortfolioAnalytics
from app.portfolio.analytics_returns import calculate_position_performances
from app.portfolio.models import Position, PriceData


@pytest.mark.smoke
def test_calculate_portfolio_value() -> None:
    """Test calculating portfolio value."""
    analytics = PortfolioAnalytics()

    positions = [
        Position(
            id="1",
            account_id="acc1",
            symbol="AAPL",
            shares=100.0,
            cost_basis=150.0,
            position_type="long",
        ),
        Position(
            id="2",
            account_id="acc1",
            symbol="GOOGL",
            shares=50.0,
            cost_basis=2000.0,
            position_type="long",
        ),
    ]

    price_data = {
        "AAPL": PriceData(symbol="AAPL", price=180.0),
        "GOOGL": PriceData(symbol="GOOGL", price=2500.0),
    }

    portfolio_value = analytics.calculate_portfolio_value(positions, price_data)

    assert portfolio_value.total_value == 143000.0
    assert portfolio_value.total_cost_basis == 115000.0
    assert portfolio_value.total_gain == 28000.0
    assert abs(portfolio_value.total_gain_pct - 24.35) < 0.01


def test_calculate_portfolio_value_short_position() -> None:
    """Test calculating value with short position."""
    analytics = PortfolioAnalytics()

    positions = [
        Position(
            id="1",
            account_id="acc1",
            symbol="AAPL",
            shares=100.0,
            cost_basis=150.0,
            position_type="short",
        ),
    ]

    price_data = {
        "AAPL": PriceData(symbol="AAPL", price=140.0),
    }

    portfolio_value = analytics.calculate_portfolio_value(positions, price_data)

    # Short position: -(100 * 140) = -14,000
    assert portfolio_value.total_value == -14000.0

    # Short cost: -(100 * 150) = -15,000
    assert portfolio_value.total_cost_basis == -15000.0

    # Gain: -14,000 - (-15,000) = 1,000 (profit from price drop)
    assert portfolio_value.total_gain == 1000.0


def test_calculate_portfolio_beta() -> None:
    """Test calculating portfolio beta."""
    analytics = PortfolioAnalytics()

    positions = [
        Position(
            id="1",
            account_id="acc1",
            symbol="AAPL",
            shares=100.0,
            cost_basis=150.0,
            position_type="long",
        ),
        Position(
            id="2",
            account_id="acc1",
            symbol="GOOGL",
            shares=50.0,
            cost_basis=2000.0,
            position_type="long",
        ),
    ]

    price_data = {
        "AAPL": PriceData(symbol="AAPL", price=180.0, beta=1.2),
        "GOOGL": PriceData(symbol="GOOGL", price=2500.0, beta=0.9),
    }

    portfolio_beta = analytics.calculate_portfolio_beta(positions, price_data)

    # AAPL value: 100 * 180 = 18,000
    # GOOGL value: 50 * 2500 = 125,000
    # Total: 143,000
    # Weighted beta: (18000 * 1.2 + 125000 * 0.9) / 143000 = 0.938
    assert portfolio_beta is not None
    assert abs(portfolio_beta - 0.938) < 0.01


def test_calculate_portfolio_beta_missing_data() -> None:
    """Test beta calculation with missing data."""
    analytics = PortfolioAnalytics()

    positions = [
        Position(
            id="1",
            account_id="acc1",
            symbol="AAPL",
            shares=100.0,
            cost_basis=150.0,
            position_type="long",
        ),
    ]

    price_data = {
        "AAPL": PriceData(symbol="AAPL", price=180.0, beta=None),
    }

    portfolio_beta = analytics.calculate_portfolio_beta(positions, price_data)

    assert portfolio_beta is None


def test_calculate_portfolio_beta_skips_nan_values() -> None:
    """NaN betas should be ignored so analytics remain JSON-serializable."""
    analytics = PortfolioAnalytics()

    positions = [
        Position(
            id="1",
            account_id="acc1",
            symbol="AAPL",
            shares=100.0,
            cost_basis=150.0,
            position_type="long",
        ),
        Position(
            id="2",
            account_id="acc1",
            symbol="MSFT",
            shares=50.0,
            cost_basis=300.0,
            position_type="long",
        ),
    ]

    price_data = {
        "AAPL": PriceData(symbol="AAPL", price=180.0, beta=math.nan),
        "MSFT": PriceData(symbol="MSFT", price=350.0, beta=1.05),
    }

    portfolio_beta = analytics.calculate_portfolio_beta(positions, price_data)

    assert portfolio_beta == 1.05


def test_calculate_sector_exposure() -> None:
    """Test calculating sector exposure."""
    analytics = PortfolioAnalytics()

    positions = [
        Position(
            id="1",
            account_id="acc1",
            symbol="AAPL",
            shares=100.0,
            cost_basis=150.0,
            position_type="long",
        ),
        Position(
            id="2",
            account_id="acc1",
            symbol="GOOGL",
            shares=50.0,
            cost_basis=2000.0,
            position_type="long",
        ),
        Position(
            id="3",
            account_id="acc1",
            symbol="JPM",
            shares=200.0,
            cost_basis=100.0,
            position_type="long",
        ),
    ]

    price_data = {
        "AAPL": PriceData(symbol="AAPL", price=180.0, sector="Technology"),
        "GOOGL": PriceData(symbol="GOOGL", price=2500.0, sector="Technology"),
        "JPM": PriceData(symbol="JPM", price=150.0, sector="Financials"),
    }

    sector_exposure = analytics.calculate_sector_exposure(positions, price_data)

    assert "Technology" in sector_exposure
    assert "Financials" in sector_exposure
    assert abs(sector_exposure["Technology"] - 82.66) < 0.01
    assert abs(sector_exposure["Financials"] - 17.34) < 0.01


def test_calculate_sector_exposure_uses_fund_labels_when_available() -> None:
    """ETF labels should be preserved so exposure doesn't collapse into Unknown."""
    analytics = PortfolioAnalytics()

    positions = [
        Position(
            id="1",
            account_id="acc1",
            symbol="VTI",
            shares=100.0,
            cost_basis=300.0,
            position_type="long",
        ),
        Position(
            id="2",
            account_id="acc1",
            symbol="VUG",
            shares=10.0,
            cost_basis=450.0,
            position_type="long",
        ),
    ]

    price_data = {
        "VTI": PriceData(symbol="VTI", price=330.0, sector="Broad Market Index"),
        "VUG": PriceData(symbol="VUG", price=460.0, sector="Large-Cap Growth Fund"),
    }

    sector_exposure = analytics.calculate_sector_exposure(positions, price_data)

    assert sector_exposure["Broad Market Index"] == pytest.approx(
        (33000.0 / 37600.0) * 100
    )
    assert sector_exposure["Large-Cap Growth Fund"] == pytest.approx(
        (4600.0 / 37600.0) * 100
    )
    assert "Unknown" not in sector_exposure


def test_calculate_concentration_risk() -> None:
    """Test calculating concentration risk metrics."""
    analytics = PortfolioAnalytics()

    positions = [
        Position(
            id="1",
            account_id="acc1",
            symbol="AAPL",
            shares=100.0,
            cost_basis=150.0,
            position_type="long",
        ),
        Position(
            id="2",
            account_id="acc1",
            symbol="GOOGL",
            shares=50.0,
            cost_basis=2000.0,
            position_type="long",
        ),
        Position(
            id="3",
            account_id="acc1",
            symbol="JPM",
            shares=200.0,
            cost_basis=100.0,
            position_type="long",
        ),
    ]

    price_data = {
        "AAPL": PriceData(symbol="AAPL", price=180.0),
        "GOOGL": PriceData(symbol="GOOGL", price=2500.0),
        "JPM": PriceData(symbol="JPM", price=150.0),
    }

    concentration = analytics.calculate_concentration_risk(positions, price_data)

    # AAPL: 18,000
    # GOOGL: 125,000 (largest)
    # JPM: 30,000
    # Total: 173,000

    # Top holding: 125,000 / 173,000 = 72.25%
    assert abs(concentration.top_holding_pct - 72.25) < 0.01

    # Top 3: 173,000 / 173,000 = 100%
    assert abs(concentration.top_3_pct - 100.0) < 0.01

    # Herfindahl Index should be > 0
    assert concentration.herfindahl_index > 0


def test_calculate_concentration_risk_aggregates_duplicate_symbols() -> None:
    """A holding split across accounts is one economic exposure."""
    analytics = PortfolioAnalytics()
    positions = [
        Position(
            id="vti-taxable",
            account_id="taxable",
            symbol="VTI",
            shares=100.0,
            cost_basis=80.0,
            position_type="long",
        ),
        Position(
            id="vti-ira",
            account_id="ira",
            symbol="VTI",
            shares=50.0,
            cost_basis=90.0,
            position_type="long",
        ),
        Position(
            id="tsla",
            account_id="taxable",
            symbol="TSLA",
            shares=100.0,
            cost_basis=40.0,
            position_type="long",
        ),
        Position(
            id="vug",
            account_id="ira",
            symbol="VUG",
            shares=10.0,
            cost_basis=180.0,
            position_type="long",
        ),
    ]
    price_data = {
        "VTI": PriceData(symbol="VTI", price=100.0),
        "TSLA": PriceData(symbol="TSLA", price=50.0),
        "VUG": PriceData(symbol="VUG", price=200.0),
    }

    concentration = analytics.calculate_concentration_risk(positions, price_data)

    assert concentration.top_holding_pct == pytest.approx(68.181818, rel=1e-4)
    assert concentration.top_3_pct == pytest.approx(100.0)
    assert concentration.herfindahl_index == pytest.approx(5247.933884, rel=1e-4)


def test_calculate_full_analytics() -> None:
    """Test calculating complete portfolio analytics."""
    analytics = PortfolioAnalytics()

    positions = [
        Position(
            id="1",
            account_id="acc1",
            symbol="AAPL",
            shares=100.0,
            cost_basis=150.0,
            position_type="long",
        ),
        Position(
            id="2",
            account_id="acc1",
            symbol="GOOGL",
            shares=50.0,
            cost_basis=2000.0,
            position_type="long",
        ),
    ]

    price_data = {
        "AAPL": PriceData(symbol="AAPL", price=180.0, beta=1.2, sector="Technology"),
        "GOOGL": PriceData(symbol="GOOGL", price=2500.0, beta=0.9, sector="Technology"),
    }

    full_analytics = analytics.calculate_full_analytics(positions, price_data)

    assert full_analytics.portfolio_value.total_value == 143000.0
    assert full_analytics.portfolio_beta is not None
    assert full_analytics.num_positions == 2
    assert full_analytics.num_symbols == 2
    assert "Technology" in full_analytics.sector_exposure


def test_calculate_full_analytics_keeps_position_and_holding_counts_separate() -> None:
    """Duplicate account rows should not inflate diversification holding count."""
    analytics = PortfolioAnalytics()
    positions = [
        Position(
            id="aapl-taxable",
            account_id="taxable",
            symbol="AAPL",
            shares=100.0,
            cost_basis=150.0,
            position_type="long",
        ),
        Position(
            id="aapl-ira",
            account_id="ira",
            symbol="AAPL",
            shares=50.0,
            cost_basis=170.0,
            position_type="long",
        ),
        Position(
            id="msft",
            account_id="ira",
            symbol="MSFT",
            shares=50.0,
            cost_basis=300.0,
            position_type="long",
        ),
    ]
    price_data = {
        "AAPL": PriceData(symbol="AAPL", price=180.0, sector="Technology"),
        "MSFT": PriceData(symbol="MSFT", price=330.0, sector="Technology"),
    }

    full_analytics = analytics.calculate_full_analytics(positions, price_data)

    assert full_analytics.num_positions == 3
    assert full_analytics.num_symbols == 2
    assert full_analytics.diversification_score is not None
    assert full_analytics.diversification_score.num_holdings == 2
    assert [performance.symbol for performance in full_analytics.top_performers] == [
        "AAPL",
        "MSFT",
    ]


def test_calculate_full_analytics_passes_storage_to_covariance_path() -> None:
    """Full analytics should pass storage into covariance-backed volatility calculation."""
    analytics = PortfolioAnalytics()
    mock_storage = MagicMock()

    positions = [
        Position(
            id="1",
            account_id="acc1",
            symbol="AAPL",
            shares=100.0,
            cost_basis=150.0,
            position_type="long",
        ),
        Position(
            id="2",
            account_id="acc2",
            symbol="MSFT",
            shares=50.0,
            cost_basis=300.0,
            position_type="long",
        ),
    ]

    price_data = {
        "AAPL": PriceData(symbol="AAPL", price=180.0, beta=1.2, volatility=0.24),
        "MSFT": PriceData(symbol="MSFT", price=350.0, beta=1.0, volatility=0.20),
    }

    with (
        patch(
            "app.portfolio.analytics.calculate_portfolio_volatility",
            return_value=0.18,
        ) as mock_volatility,
        patch(
            "app.portfolio.analytics.calculate_sharpe_ratio",
            return_value=1.1,
        ) as mock_sharpe,
    ):
        analytics.calculate_full_analytics(
            positions,
            price_data,
            storage=mock_storage,
            account_ids=["acc1", "acc2"],
        )

    mock_volatility.assert_called_once_with(
        positions,
        price_data,
        mock_storage,
        account_ids=["acc1", "acc2"],
    )
    mock_sharpe.assert_called_once()
    assert mock_sharpe.call_args.kwargs["storage"] is mock_storage
    assert mock_sharpe.call_args.kwargs["account_ids"] == ["acc1", "acc2"]


def test_calculate_full_analytics_passes_account_ids_to_volatility() -> None:
    """Volatility should use real account ids for covariance cache scoping."""
    analytics = PortfolioAnalytics()
    mock_storage = MagicMock()

    positions = [
        Position(
            id="1",
            account_id="acc1",
            symbol="AAPL",
            shares=100.0,
            cost_basis=150.0,
            position_type="long",
        ),
        Position(
            id="2",
            account_id="acc2",
            symbol="MSFT",
            shares=50.0,
            cost_basis=300.0,
            position_type="long",
        ),
    ]

    price_data = {
        "AAPL": PriceData(symbol="AAPL", price=180.0, beta=1.2, volatility=0.24),
        "MSFT": PriceData(symbol="MSFT", price=350.0, beta=1.0, volatility=0.20),
    }

    with patch(
        "app.portfolio.analytics.calculate_portfolio_volatility",
        return_value=0.18,
    ) as mock_volatility:
        analytics.calculate_full_analytics(
            positions,
            price_data,
            storage=mock_storage,
            account_ids=["acc1", "acc2"],
        )

    mock_volatility.assert_called_once_with(
        positions,
        price_data,
        mock_storage,
        account_ids=["acc1", "acc2"],
    )


def test_calculate_full_analytics_returns_no_sharpe_without_return_history() -> None:
    """Sharpe should be unavailable when we only have unrealized P&L, not a return series."""
    analytics = PortfolioAnalytics()

    positions = [
        Position(
            id="1",
            account_id="acc1",
            symbol="AAPL",
            shares=100.0,
            cost_basis=150.0,
            position_type="long",
        ),
        Position(
            id="2",
            account_id="acc1",
            symbol="GOOGL",
            shares=50.0,
            cost_basis=2000.0,
            position_type="long",
        ),
    ]

    price_data = {
        "AAPL": PriceData(symbol="AAPL", price=180.0, beta=1.2, volatility=0.25),
        "GOOGL": PriceData(symbol="GOOGL", price=2500.0, beta=0.9, volatility=0.20),
    }

    full_analytics = analytics.calculate_full_analytics(positions, price_data)

    assert full_analytics.sharpe_ratio is None


def test_calculate_portfolio_value_with_price_errors() -> None:
    """Test portfolio value calculation skips positions with price errors."""
    analytics = PortfolioAnalytics()

    positions = [
        Position(
            id="1",
            account_id="acc1",
            symbol="AAPL",
            shares=100.0,
            cost_basis=150.0,
            position_type="long",
        ),
        Position(
            id="2",
            account_id="acc1",
            symbol="INVALID",
            shares=50.0,
            cost_basis=100.0,
            position_type="long",
        ),
    ]

    price_data = {
        "AAPL": PriceData(symbol="AAPL", price=180.0),
        "INVALID": PriceData(symbol="INVALID", price=0.0, error="Symbol not found"),
    }

    portfolio_value = analytics.calculate_portfolio_value(positions, price_data)

    # Should only include AAPL, skip INVALID
    assert portfolio_value.total_value == 18000.0
    assert portfolio_value.total_cost_basis == 15000.0


def test_calculate_portfolio_beta_with_price_errors() -> None:
    """Test beta calculation skips positions with price errors."""
    analytics = PortfolioAnalytics()

    positions = [
        Position(
            id="1",
            account_id="acc1",
            symbol="AAPL",
            shares=100.0,
            cost_basis=150.0,
            position_type="long",
        ),
        Position(
            id="2",
            account_id="acc1",
            symbol="INVALID",
            shares=50.0,
            cost_basis=100.0,
            position_type="long",
        ),
    ]

    price_data = {
        "AAPL": PriceData(symbol="AAPL", price=180.0, beta=1.2),
        "INVALID": PriceData(symbol="INVALID", price=0.0, beta=1.0, error="Symbol not found"),
    }

    portfolio_beta = analytics.calculate_portfolio_beta(positions, price_data)

    # Should only include AAPL, skip INVALID
    assert portfolio_beta == 1.2


def test_calculate_sector_exposure_with_price_errors() -> None:
    """Test sector exposure calculation skips positions with price errors."""
    analytics = PortfolioAnalytics()

    positions = [
        Position(
            id="1",
            account_id="acc1",
            symbol="AAPL",
            shares=100.0,
            cost_basis=150.0,
            position_type="long",
        ),
        Position(
            id="2",
            account_id="acc1",
            symbol="INVALID",
            shares=50.0,
            cost_basis=100.0,
            position_type="long",
        ),
    ]

    price_data = {
        "AAPL": PriceData(symbol="AAPL", price=180.0, sector="Technology"),
        "INVALID": PriceData(
            symbol="INVALID", price=0.0, sector="Unknown", error="Symbol not found"
        ),
    }

    sector_exposure = analytics.calculate_sector_exposure(positions, price_data)

    # Should only include AAPL, skip INVALID
    assert "Technology" in sector_exposure
    assert sector_exposure["Technology"] == 100.0
    assert "Unknown" not in sector_exposure


def test_calculate_concentration_risk_with_price_errors() -> None:
    """Test concentration risk calculation skips positions with price errors."""
    analytics = PortfolioAnalytics()

    positions = [
        Position(
            id="1",
            account_id="acc1",
            symbol="AAPL",
            shares=100.0,
            cost_basis=150.0,
            position_type="long",
        ),
        Position(
            id="2",
            account_id="acc1",
            symbol="GOOGL",
            shares=50.0,
            cost_basis=2000.0,
            position_type="long",
        ),
        Position(
            id="3",
            account_id="acc1",
            symbol="INVALID",
            shares=1000.0,
            cost_basis=100.0,
            position_type="long",
        ),
    ]

    price_data = {
        "AAPL": PriceData(symbol="AAPL", price=180.0),
        "GOOGL": PriceData(symbol="GOOGL", price=2500.0),
        "INVALID": PriceData(symbol="INVALID", price=0.0, error="Symbol not found"),
    }

    concentration = analytics.calculate_concentration_risk(positions, price_data)

    # Should only include AAPL and GOOGL, skip INVALID
    # GOOGL: 125,000 (largest)
    # AAPL: 18,000
    # Total: 143,000
    # Top holding: 125,000 / 143,000 = 87.41%
    assert abs(concentration.top_holding_pct - 87.41) < 0.01


def test_calculate_position_performances_returns_gain_and_weight_for_each_position() -> None:
    """Shared performance helper should return reusable gain and concentration metrics."""
    positions = [
        Position(
            id="1",
            account_id="acc1",
            symbol="AAPL",
            shares=100.0,
            cost_basis=150.0,
            position_type="long",
        ),
        Position(
            id="2",
            account_id="acc1",
            symbol="MSFT",
            shares=50.0,
            cost_basis=300.0,
            position_type="long",
        ),
    ]
    price_data = {
        "AAPL": PriceData(symbol="AAPL", price=180.0),
        "MSFT": PriceData(symbol="MSFT", price=330.0),
    }

    performances = calculate_position_performances(positions, price_data)

    assert [performance.symbol for performance in performances] == ["AAPL", "MSFT"]
    assert performances[0].gain_pct == pytest.approx(20.0)
    assert performances[0].weight_pct == pytest.approx(52.173913, rel=1e-4)
    assert performances[1].gain_pct == pytest.approx(10.0)
    assert performances[1].weight_pct == pytest.approx(47.826087, rel=1e-4)


def test_calculate_position_performances_aggregates_duplicate_symbols() -> None:
    """Overview performers should not show duplicate ticker rows."""
    positions = [
        Position(
            id="aapl-taxable",
            account_id="taxable",
            symbol="AAPL",
            shares=100.0,
            cost_basis=150.0,
            position_type="long",
        ),
        Position(
            id="aapl-ira",
            account_id="ira",
            symbol="AAPL",
            shares=50.0,
            cost_basis=170.0,
            position_type="long",
        ),
        Position(
            id="msft",
            account_id="ira",
            symbol="MSFT",
            shares=50.0,
            cost_basis=300.0,
            position_type="long",
        ),
    ]
    price_data = {
        "AAPL": PriceData(symbol="AAPL", price=180.0),
        "MSFT": PriceData(symbol="MSFT", price=330.0),
    }

    performances = calculate_position_performances(positions, price_data)

    assert [performance.symbol for performance in performances] == ["AAPL", "MSFT"]
    assert performances[0].current_value == pytest.approx(27_000.0)
    assert performances[0].gain_amount == pytest.approx(3_500.0)
    assert performances[0].gain_pct == pytest.approx(14.893617, rel=1e-4)
    assert performances[0].weight_pct == pytest.approx(62.068966, rel=1e-4)
