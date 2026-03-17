"""
Performance metrics calculations for backtests.

Reuses existing analytics patterns from:
- analytics_risk.py: Sharpe ratio calculation
- agent_performance.py: Win/loss metrics
- paper_trading_portfolio.py: Trade return patterns
"""

import math
from decimal import Decimal

from app.backtest.models import BacktestEquity, BacktestTrade
from app.constants import TRADING_DAYS_PER_YEAR
from app.logging_config import get_logger

logger = get_logger(__name__)


def calculate_total_return(initial_capital: Decimal, final_equity: Decimal) -> Decimal:
    """Calculate total return percentage.

    Args:
        initial_capital: Starting capital
        final_equity: Final equity value

    Returns:
        Total return percentage (e.g., 15.5 for 15.5% gain)
    """
    if initial_capital == 0:
        return Decimal("0.0")

    return (final_equity - initial_capital) / initial_capital * Decimal("100.0")


def calculate_max_drawdown(equity_curve: list[BacktestEquity]) -> Decimal:
    """Calculate maximum drawdown from peak equity.

    Args:
        equity_curve: List of daily equity snapshots

    Returns:
        Maximum drawdown percentage (positive value, e.g., 12.5 for 12.5% drawdown)
    """
    if not equity_curve:
        return Decimal("0.0")

    max_dd = Decimal("0.0")
    peak_equity = equity_curve[0].equity

    for snapshot in equity_curve:
        peak_equity = max(peak_equity, snapshot.equity)

        drawdown = (
            (peak_equity - snapshot.equity) / peak_equity * Decimal("100.0")
            if peak_equity > 0
            else Decimal("0.0")
        )

        max_dd = max(max_dd, drawdown)

    return max_dd


def calculate_simple_max_drawdown(pnl_values: list[float]) -> float:
    """Calculate maximum drawdown from cumulative PnL values.

    A simpler version that works with raw PnL values (not equity curve objects).
    Useful for strategy monitoring where we have trade-level PnL.

    Args:
        pnl_values: List of individual PnL values (profits/losses)

    Returns:
        Max drawdown as fraction (0.0 to 1.0)
    """
    if not pnl_values:
        return 0.0

    cumulative_pnl = 0.0
    peak_pnl = 0.0
    max_drawdown = 0.0

    for pnl in pnl_values:
        cumulative_pnl += pnl
        peak_pnl = max(peak_pnl, cumulative_pnl)
        drawdown = (peak_pnl - cumulative_pnl) / peak_pnl if peak_pnl > 0 else 0.0
        max_drawdown = max(max_drawdown, drawdown)

    return max_drawdown


def calculate_sharpe_ratio(
    equity_curve: list[BacktestEquity], risk_free_rate: Decimal = Decimal("0.045")
) -> Decimal:
    """Calculate annualized Sharpe ratio.

    Reuses pattern from analytics_risk.py:calculate_sharpe_ratio()

    Args:
        equity_curve: List of daily equity snapshots
        risk_free_rate: Annual risk-free rate (default: 4.5%)

    Returns:
        Annualized Sharpe ratio (e.g., 1.25)
        Returns 0.0 if insufficient data or zero volatility
    """
    if len(equity_curve) < 2:
        return Decimal("0.0")

    # Calculate daily returns
    daily_returns = []
    for i in range(1, len(equity_curve)):
        prev_equity = equity_curve[i - 1].equity
        curr_equity = equity_curve[i].equity

        if prev_equity > 0:
            daily_return = (curr_equity - prev_equity) / prev_equity
            daily_returns.append(float(daily_return))

    if not daily_returns:
        return Decimal("0.0")

    # Calculate mean and standard deviation
    mean_return = sum(daily_returns) / len(daily_returns)
    variance = sum((r - mean_return) ** 2 for r in daily_returns) / len(daily_returns)
    std_dev = math.sqrt(variance)

    if std_dev == 0:
        return Decimal("0.0")

    # Sharpe ratio = (Portfolio Return - Risk-Free Rate) / Volatility
    # Calculate using daily returns annualized
    daily_rf = float(risk_free_rate) / TRADING_DAYS_PER_YEAR
    excess_return = mean_return - daily_rf
    sharpe = excess_return * math.sqrt(TRADING_DAYS_PER_YEAR) / std_dev if std_dev > 0 else 0.0

    # Guard against NaN/inf values
    if math.isnan(sharpe) or math.isinf(sharpe):
        logger.warning("sharpe_invalid_value", sharpe=sharpe)
        return Decimal("0.0")

    return Decimal(str(round(sharpe, 4)))


def calculate_simple_sharpe(daily_returns: list[float]) -> float:
    """Calculate simplified Sharpe ratio from daily returns.

    A simpler version without risk-free rate adjustment or annualization.
    Useful for quick performance monitoring.

    Args:
        daily_returns: List of daily return/PnL values

    Returns:
        Sharpe ratio (0.0 if insufficient data or zero variance)
    """
    if len(daily_returns) <= 1:
        return 0.0

    mean_return = sum(daily_returns) / len(daily_returns)
    variance = sum((r - mean_return) ** 2 for r in daily_returns) / len(daily_returns)
    std_dev = variance**0.5
    return mean_return / std_dev if std_dev > 0 else 0.0


def calculate_win_rate(trades: list[BacktestTrade]) -> Decimal:
    """Calculate percentage of winning trades.

    Args:
        trades: List of completed trades

    Returns:
        Win rate percentage (e.g., 55.5 for 55.5% win rate)
    """
    if not trades:
        return Decimal("0.0")

    winning_trades = sum(1 for trade in trades if trade.pnl and trade.pnl > 0)
    return Decimal(str(winning_trades)) / Decimal(str(len(trades))) * Decimal("100.0")


def calculate_average_win_loss(
    trades: list[BacktestTrade],
) -> tuple[Decimal, Decimal]:
    """Calculate average winning and losing trade PnL.

    Reuses pattern from agent_performance.py:_calculate_win_loss_metrics()

    Args:
        trades: List of completed trades

    Returns:
        (average_win, average_loss) in dollars
    """
    if not trades:
        return (Decimal("0.0"), Decimal("0.0"))

    winners = [trade.pnl for trade in trades if trade.pnl and trade.pnl > 0]
    losers = [abs(trade.pnl) for trade in trades if trade.pnl and trade.pnl < 0]

    avg_win = Decimal(str(sum(winners) / len(winners))) if winners else Decimal("0.0")
    avg_loss = Decimal(str(sum(losers) / len(losers))) if losers else Decimal("0.0")

    return (avg_win, avg_loss)


def calculate_profit_factor(trades: list[BacktestTrade]) -> Decimal:
    """Calculate profit factor (sum of wins / sum of losses).

    A profit factor > 1.0 indicates profitable strategy.
    Common ranges:
    - < 1.0: Losing strategy
    - 1.0-1.5: Marginally profitable
    - 1.5-2.0: Good strategy
    - > 2.0: Excellent strategy

    Args:
        trades: List of completed trades

    Returns:
        Profit factor (e.g., 1.75)
        Returns 0.0 if no losing trades (infinite profit factor edge case)
    """
    if not trades:
        return Decimal("0.0")

    total_wins = Decimal(str(sum(trade.pnl for trade in trades if trade.pnl and trade.pnl > 0)))
    total_losses = Decimal(
        str(abs(sum(trade.pnl for trade in trades if trade.pnl and trade.pnl < 0)))
    )

    if total_losses == 0:
        # Edge case: Only winning trades (infinite profit factor)
        # Return 999.0 as a practical upper bound
        return Decimal("999.0") if total_wins > 0 else Decimal("0.0")

    return total_wins / total_losses


def calculate_win_loss_ratio(trades: list[BacktestTrade]) -> Decimal:
    """Calculate win/loss ratio (average win / average loss).

    Args:
        trades: List of completed trades

    Returns:
        Win/loss ratio (e.g., 2.5 means avg win is 2.5x avg loss)
    """
    avg_win, avg_loss = calculate_average_win_loss(trades)

    if avg_loss == 0:
        return Decimal("999.0") if avg_win > 0 else Decimal("0.0")

    return avg_win / avg_loss
