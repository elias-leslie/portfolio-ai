"""Unit tests for PortfolioAnalytics."""

from __future__ import annotations

from app.portfolio.analytics import PortfolioAnalytics
from app.portfolio.models import Position, PriceData


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

    # AAPL: 100 * 180 = 18,000
    # GOOGL: 50 * 2500 = 125,000
    # Total: 143,000
    assert portfolio_value.total_value == 143000.0

    # AAPL cost: 100 * 150 = 15,000
    # GOOGL cost: 50 * 2000 = 100,000
    # Total cost: 115,000
    assert portfolio_value.total_cost_basis == 115000.0

    # Gain: 143,000 - 115,000 = 28,000
    assert portfolio_value.total_gain == 28000.0

    # Gain %: 28,000 / 115,000 * 100 = 24.35%
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

    # AAPL: 100 * 180 = 18,000 (Tech)
    # GOOGL: 50 * 2500 = 125,000 (Tech)
    # JPM: 200 * 150 = 30,000 (Financials)
    # Total: 173,000
    # Tech: 143,000 / 173,000 = 82.66%
    # Financials: 30,000 / 173,000 = 17.34%

    assert "Technology" in sector_exposure
    assert "Financials" in sector_exposure
    assert abs(sector_exposure["Technology"] - 82.66) < 0.01
    assert abs(sector_exposure["Financials"] - 17.34) < 0.01


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
