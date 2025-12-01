"""Kelly criterion position sizing (GAP-045).

The Kelly criterion determines the optimal bet size to maximize long-term
portfolio growth rate, given a strategy's win rate and win/loss ratio.

Formula: Kelly% = (p * b - q) / b
  where: p = win probability
         q = loss probability (1 - p)
         b = win/loss ratio (avg_win / avg_loss)

We use fractional Kelly (25-50%) to reduce volatility and account
for estimation error in historical statistics.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.logging_config import get_logger

if TYPE_CHECKING:
    from app.storage import PortfolioStorage

logger = get_logger(__name__)

# Fractional Kelly multiplier (reduce full Kelly to manage variance)
DEFAULT_KELLY_FRACTION = 0.25  # 25% of full Kelly (conservative)

# Minimum trades required for statistical significance
MIN_TRADES_FOR_KELLY = 30

# Maximum position as fraction of portfolio (even with great edge)
MAX_POSITION_PERCENT = 0.25  # 25% max

# Minimum position as fraction of portfolio (if Kelly suggests too small)
MIN_POSITION_PERCENT = 0.01  # 1% min


def calculate_kelly_fraction(
    win_rate: float,
    avg_win: float,
    avg_loss: float,
    kelly_multiplier: float = DEFAULT_KELLY_FRACTION,
) -> float:
    """Calculate Kelly fraction for position sizing.

    Formula: Kelly% = (p * b - q) / b
      where: p = win rate
             q = 1 - p
             b = avg_win / abs(avg_loss)

    Args:
        win_rate: Win probability (0-1)
        avg_win: Average winning trade return (positive, as decimal e.g. 0.05 = 5%)
        avg_loss: Average losing trade return (negative, as decimal e.g. -0.03 = -3%)
        kelly_multiplier: Fractional Kelly (default 0.25 = 25%)

    Returns:
        Position size as fraction of portfolio (0-MAX_POSITION_PERCENT)
    """
    # Validate inputs
    if win_rate <= 0 or win_rate >= 1:
        logger.warning(
            "kelly_invalid_win_rate",
            win_rate=win_rate,
        )
        return MIN_POSITION_PERCENT

    if avg_win <= 0:
        logger.warning(
            "kelly_invalid_avg_win",
            avg_win=avg_win,
        )
        return MIN_POSITION_PERCENT

    if avg_loss >= 0:
        logger.warning(
            "kelly_invalid_avg_loss",
            avg_loss=avg_loss,
        )
        return MIN_POSITION_PERCENT

    # Calculate Kelly
    p = win_rate
    q = 1 - p
    b = avg_win / abs(avg_loss)

    # Kelly formula
    full_kelly = (p * b - q) / b

    # Apply fractional Kelly
    fractional_kelly = full_kelly * kelly_multiplier

    # Bound to reasonable range
    if fractional_kelly <= 0:
        # Negative Kelly = no edge, use minimum
        logger.info(
            "kelly_no_edge",
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            full_kelly=full_kelly,
        )
        return MIN_POSITION_PERCENT

    bounded_kelly = max(MIN_POSITION_PERCENT, min(fractional_kelly, MAX_POSITION_PERCENT))

    logger.info(
        "kelly_calculated",
        win_rate=win_rate,
        avg_win=avg_win,
        avg_loss=avg_loss,
        b_ratio=b,
        full_kelly=full_kelly,
        fractional_kelly=fractional_kelly,
        bounded_kelly=bounded_kelly,
    )

    return bounded_kelly


def get_strategy_stats(
    storage: PortfolioStorage,
    strategy_name: str | None = None,
    lookback_days: int = 365,
) -> tuple[float | None, float | None, float | None, int]:
    """Get win rate and average win/loss from historical backtest trades.

    Args:
        storage: Database storage instance
        strategy_name: Optional filter by strategy name
        lookback_days: Days of history to consider

    Returns:
        Tuple of (win_rate, avg_win, avg_loss, trade_count)
        Returns (None, None, None, 0) if insufficient data
    """
    # Query historical trades from backtest_trades
    if strategy_name:
        query = """
            SELECT
                bt.pnl_pct
            FROM backtest_trades bt
            JOIN backtest_runs br ON bt.run_id = br.id
            WHERE br.strategy = $1
              AND bt.exit_date >= CURRENT_DATE - INTERVAL '1 day' * $2
              AND bt.pnl_pct IS NOT NULL
        """
        params: list[str | int] = [strategy_name, lookback_days]
    else:
        query = """
            SELECT
                bt.pnl_pct
            FROM backtest_trades bt
            WHERE bt.exit_date >= CURRENT_DATE - INTERVAL '1 day' * $1
              AND bt.pnl_pct IS NOT NULL
        """
        params = [lookback_days]

    result = storage.query(query, list(params))

    if result.is_empty():
        return None, None, None, 0

    pnl_values = result.get_column("pnl_pct").to_list()
    trade_count = len(pnl_values)

    if trade_count < MIN_TRADES_FOR_KELLY:
        logger.warning(
            "kelly_insufficient_trades",
            trade_count=trade_count,
            min_required=MIN_TRADES_FOR_KELLY,
        )
        return None, None, None, trade_count

    # Calculate statistics
    wins = [p for p in pnl_values if p > 0]
    losses = [p for p in pnl_values if p < 0]

    if len(wins) == 0 or len(losses) == 0:
        logger.warning(
            "kelly_no_wins_or_losses",
            wins_count=len(wins),
            losses_count=len(losses),
        )
        return None, None, None, trade_count

    win_rate = len(wins) / trade_count
    avg_win = sum(wins) / len(wins) / 100  # Convert from percent to decimal
    avg_loss = sum(losses) / len(losses) / 100  # Convert from percent to decimal

    return win_rate, avg_win, avg_loss, trade_count


def calculate_kelly_position_size(
    storage: PortfolioStorage,
    portfolio_value: float,
    entry_price: float,
    strategy_name: str | None = None,
    kelly_multiplier: float = DEFAULT_KELLY_FRACTION,
) -> tuple[int, dict[str, float | int | str | None]]:
    """Calculate position size using Kelly criterion.

    Args:
        storage: Database storage instance
        portfolio_value: Total portfolio value in dollars
        entry_price: Entry price per share
        strategy_name: Optional filter by strategy name
        kelly_multiplier: Fractional Kelly (default 0.25 = 25%)

    Returns:
        Tuple of (shares, details):
        - shares: Number of shares to buy
        - details: Dict with kelly_fraction, position_value, etc.
    """
    # Get strategy statistics
    win_rate, avg_win, avg_loss, trade_count = get_strategy_stats(
        storage, strategy_name
    )

    details: dict[str, float | int | str | None] = {
        "win_rate": win_rate,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "trade_count": trade_count,
        "kelly_fraction": None,
        "position_value": None,
        "shares": 0,
        "strategy_name": strategy_name,
    }

    if win_rate is None or avg_win is None or avg_loss is None:
        # Insufficient data - use minimum position
        position_value = portfolio_value * MIN_POSITION_PERCENT
        shares = int(position_value / entry_price)
        details["kelly_fraction"] = MIN_POSITION_PERCENT
        details["position_value"] = position_value
        details["shares"] = shares
        details["reason"] = "insufficient_data"
        logger.info(
            "kelly_fallback_minimum",
            reason="insufficient_historical_data",
            trade_count=trade_count,
            shares=shares,
        )
        return shares, details

    # Calculate Kelly fraction
    kelly_fraction = calculate_kelly_fraction(
        win_rate, avg_win, avg_loss, kelly_multiplier
    )

    # Calculate position
    position_value = portfolio_value * kelly_fraction
    shares = int(position_value / entry_price)

    details["kelly_fraction"] = kelly_fraction
    details["position_value"] = position_value
    details["shares"] = shares

    logger.info(
        "kelly_position_sized",
        portfolio_value=portfolio_value,
        kelly_fraction=kelly_fraction,
        position_value=position_value,
        shares=shares,
        entry_price=entry_price,
    )

    return shares, details
