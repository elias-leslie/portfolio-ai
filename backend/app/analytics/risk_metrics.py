"""Portfolio risk metrics: VaR, CVaR, and extended beta calculations.

GAP-027: Value at Risk (VaR) and Conditional VaR (CVaR/Expected Shortfall)
GAP-022: Long-window beta estimation (1-year, 2-year in addition to 90-day)

Uses historical simulation method for VaR/CVaR calculation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from app.constants import TRADING_DAYS_PER_YEAR
from app.logging_config import get_logger

if TYPE_CHECKING:
    from app.storage import PortfolioStorage

logger = get_logger(__name__)


# Default confidence levels
VAR_CONFIDENCE_95 = 0.95
VAR_CONFIDENCE_99 = 0.99


@dataclass
class VaRResult:
    """Value at Risk calculation result."""

    symbol: str
    var_95: float | None = None  # 95% VaR (daily)
    var_99: float | None = None  # 99% VaR (daily)
    cvar_95: float | None = None  # 95% CVaR (Expected Shortfall)
    cvar_99: float | None = None  # 99% CVaR
    observations: int = 0
    error: str | None = None


@dataclass
class BetaResult:
    """Extended beta calculation result."""

    symbol: str
    beta_90d: float | None = None  # 90-day rolling beta (default)
    beta_1y: float | None = None  # 1-year beta
    beta_2y: float | None = None  # 2-year beta
    r_squared_1y: float | None = None  # R-squared for 1-year regression
    observations_90d: int = 0
    observations_1y: int = 0
    observations_2y: int = 0
    error: str | None = None


def calculate_var_cvar(
    returns: list[float],
    confidence: float = VAR_CONFIDENCE_95,
) -> tuple[float | None, float | None]:
    """Calculate VaR and CVaR using historical simulation.

    VaR (Value at Risk): Maximum expected loss at a given confidence level.
    CVaR (Conditional VaR / Expected Shortfall): Average loss beyond VaR.

    Args:
        returns: List of daily returns (as decimals, e.g., -0.02 for -2%)
        confidence: Confidence level (e.g., 0.95 for 95%)

    Returns:
        Tuple of (VaR, CVaR) as positive values representing loss.
        Returns (None, None) if insufficient data.
    """
    n = len(returns)
    if n < 30:  # Need sufficient observations for historical VaR
        return None, None

    # Sort returns from worst to best
    sorted_returns = sorted(returns)

    # VaR is the return at the (1 - confidence) percentile
    # For 95% confidence, we look at the 5th percentile (worst 5%)
    var_index = int((1 - confidence) * n)
    var_index = max(0, min(var_index, n - 1))

    var_value = -sorted_returns[var_index]  # Negative because loss is positive

    # CVaR is the average of returns beyond VaR
    # Average of the worst (1 - confidence)% of returns
    tail_returns = sorted_returns[: var_index + 1]
    if tail_returns:
        cvar_value = -sum(tail_returns) / len(tail_returns)
    else:
        cvar_value = var_value

    return round(var_value, 6), round(cvar_value, 6)


def get_daily_returns(
    storage: PortfolioStorage,
    symbol: str,
    lookback_days: int = TRADING_DAYS_PER_YEAR,
) -> list[tuple[date, float]]:
    """Get daily returns for a symbol from day_bars.

    Args:
        storage: Database storage instance
        symbol: Stock symbol
        lookback_days: Number of calendar days to look back

    Returns:
        List of (date, return) tuples sorted by date
    """
    query = """
        SELECT date, close
        FROM day_bars
        WHERE symbol = %s
          AND date >= CURRENT_DATE - INTERVAL '%s days'
        ORDER BY date
    """

    result = storage.query(query, [symbol, lookback_days])

    if result.is_empty():
        return []

    prices = [(row["date"], row["close"]) for row in result.iter_rows(named=True)]

    # Calculate returns
    returns = []
    for i in range(1, len(prices)):
        prev_price = prices[i - 1][1]
        curr_price = prices[i][1]
        curr_date = prices[i][0]
        if prev_price > 0:
            daily_return = (curr_price - prev_price) / prev_price
            returns.append((curr_date, daily_return))

    return returns


def get_market_returns(
    storage: PortfolioStorage,
    lookback_days: int = TRADING_DAYS_PER_YEAR,
) -> dict[date, float]:
    """Get market (SPY) daily returns.

    Args:
        storage: Database storage instance
        lookback_days: Number of calendar days to look back

    Returns:
        Dictionary mapping date to return
    """
    returns = get_daily_returns(storage, "SPY", lookback_days)
    return dict(returns)


def calculate_beta(
    stock_returns: list[tuple[date, float]],
    market_returns: dict[date, float],
) -> tuple[float | None, float | None, int]:
    """Calculate beta coefficient using OLS regression.

    Beta = Cov(stock, market) / Var(market)

    Args:
        stock_returns: List of (date, return) tuples for stock
        market_returns: Dictionary of date -> return for market

    Returns:
        Tuple of (beta, r_squared, observations)
    """
    # Align returns by date
    aligned_stock = []
    aligned_market = []

    for stock_date, stock_ret in stock_returns:
        if stock_date in market_returns:
            aligned_stock.append(stock_ret)
            aligned_market.append(market_returns[stock_date])

    n = len(aligned_stock)
    if n < 30:  # Need sufficient observations
        return None, None, n

    # Calculate means
    mean_stock = sum(aligned_stock) / n
    mean_market = sum(aligned_market) / n

    # Calculate covariance and variance
    cov = (
        sum(
            (s - mean_stock) * (m - mean_market)
            for s, m in zip(aligned_stock, aligned_market, strict=True)
        )
        / n
    )
    var_market = sum((m - mean_market) ** 2 for m in aligned_market) / n

    if var_market == 0:
        return None, None, n

    beta = cov / var_market

    # Calculate R-squared
    var_stock = sum((s - mean_stock) ** 2 for s in aligned_stock) / n
    if var_stock > 0:
        r_squared = (cov**2) / (var_stock * var_market)
    else:
        r_squared = 0.0

    return round(beta, 4), round(r_squared, 4), n


def calculate_symbol_var(
    storage: PortfolioStorage,
    symbol: str,
) -> VaRResult:
    """Calculate VaR and CVaR for a single symbol.

    Args:
        storage: Database storage instance
        symbol: Stock symbol

    Returns:
        VaRResult with 95% and 99% VaR/CVaR
    """
    # Get 1 year of returns
    returns_with_dates = get_daily_returns(storage, symbol, TRADING_DAYS_PER_YEAR * 2)
    returns = [r for _, r in returns_with_dates]

    if len(returns) < 30:
        return VaRResult(
            symbol=symbol,
            observations=len(returns),
            error="Insufficient data for VaR calculation",
        )

    var_95, cvar_95 = calculate_var_cvar(returns, VAR_CONFIDENCE_95)
    var_99, cvar_99 = calculate_var_cvar(returns, VAR_CONFIDENCE_99)

    return VaRResult(
        symbol=symbol,
        var_95=var_95,
        var_99=var_99,
        cvar_95=cvar_95,
        cvar_99=cvar_99,
        observations=len(returns),
    )


def calculate_symbol_beta(
    storage: PortfolioStorage,
    symbol: str,
) -> BetaResult:
    """Calculate multi-window betas for a single symbol.

    Args:
        storage: Database storage instance
        symbol: Stock symbol

    Returns:
        BetaResult with 90-day, 1-year, and 2-year betas
    """
    # Get market returns for full period (2 years)
    market_returns = get_market_returns(storage, TRADING_DAYS_PER_YEAR * 3)

    if len(market_returns) < 60:
        return BetaResult(
            symbol=symbol,
            error="Insufficient market data for beta calculation",
        )

    # Get stock returns for full period
    stock_returns = get_daily_returns(storage, symbol, TRADING_DAYS_PER_YEAR * 3)

    if len(stock_returns) < 60:
        return BetaResult(
            symbol=symbol,
            error="Insufficient stock data for beta calculation",
        )

    # Calculate 90-day beta
    recent_90d = stock_returns[-90:] if len(stock_returns) >= 90 else stock_returns
    beta_90d, _, obs_90d = calculate_beta(recent_90d, market_returns)

    # Calculate 1-year beta
    recent_1y = stock_returns[-TRADING_DAYS_PER_YEAR:] if len(stock_returns) >= TRADING_DAYS_PER_YEAR else stock_returns
    beta_1y, r_squared_1y, obs_1y = calculate_beta(recent_1y, market_returns)

    # Calculate 2-year beta
    two_years = TRADING_DAYS_PER_YEAR * 2
    recent_2y = stock_returns[-two_years:] if len(stock_returns) >= two_years else stock_returns
    beta_2y, _, obs_2y = calculate_beta(recent_2y, market_returns)

    return BetaResult(
        symbol=symbol,
        beta_90d=beta_90d,
        beta_1y=beta_1y,
        beta_2y=beta_2y,
        r_squared_1y=r_squared_1y,
        observations_90d=obs_90d,
        observations_1y=obs_1y,
        observations_2y=obs_2y,
    )


def calculate_portfolio_var(
    storage: PortfolioStorage,
    positions: list[tuple[str, float]],  # (symbol, weight) pairs
) -> tuple[float | None, float | None]:
    """Calculate portfolio-level VaR using historical simulation.

    Uses portfolio returns based on weighted positions.

    Args:
        storage: Database storage instance
        positions: List of (symbol, weight) tuples, weights should sum to 1.0

    Returns:
        Tuple of (VaR_95, CVaR_95) for the portfolio
    """
    if not positions:
        return None, None

    # Get returns for all symbols
    all_returns: dict[str, dict[date, float]] = {}
    for symbol, _ in positions:
        returns = get_daily_returns(storage, symbol, TRADING_DAYS_PER_YEAR)
        all_returns[symbol] = dict(returns)

    if not all_returns:
        return None, None

    # Find common dates across all positions
    common_dates = set.intersection(*(set(returns.keys()) for returns in all_returns.values()))

    if len(common_dates) < 30:
        return None, None

    # Calculate portfolio returns for each date
    portfolio_returns = []
    for d in sorted(common_dates):
        port_return = sum(weight * all_returns[symbol].get(d, 0.0) for symbol, weight in positions)
        portfolio_returns.append(port_return)

    return calculate_var_cvar(portfolio_returns, VAR_CONFIDENCE_95)
