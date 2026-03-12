"""Performance analysis for strategy evolution."""

from __future__ import annotations

from datetime import date, timedelta

from app.logging_config import get_logger
from app.storage.connection import get_connection_manager
from app.strategies.models import StrategyDefinition

from .llm_prompts import llm_diagnose_performance
from .models import StrategyAnalysis

logger = get_logger(__name__)


async def analyze_strategy_performance(
    strategy: StrategyDefinition,
    days: int = 30,
) -> StrategyAnalysis:
    """Analyze strategy performance using LLM diagnosis.

    Args:
        strategy: Strategy definition
        days: Days of history to analyze (default 30)

    Returns:
        StrategyAnalysis with LLM-generated diagnosis
    """
    logger.info("analyzing_strategy_performance", strategy_id=strategy.id, days=days)

    # Get performance metrics from strategy_performance table
    cutoff_date = date.today() - timedelta(days=days)

    with get_connection_manager().connection() as conn:
        result = conn.execute(
            """
            SELECT
                COUNT(*) as trades,
                AVG(CASE WHEN pnl_today > 0 THEN 1.0 ELSE 0.0 END) as win_rate,
                AVG(pnl_today) as avg_pnl,
                AVG(sharpe_ratio_30d) as actual_sharpe,
                MAX(max_drawdown_30d) as max_drawdown
            FROM strategy_performance
            WHERE strategy_id = %s AND date >= %s
            """,
            [strategy.id, cutoff_date.isoformat()],
        ).fetchone()

    if not result:
        # No trades in period
        raise ValueError(f"No performance data for strategy {strategy.id} in last {days} days")

    # Type narrowing for result[0] - COUNT(*) returns int, never None
    trade_count_raw = result[0]
    if trade_count_raw is None or (
        isinstance(trade_count_raw, (int, float, str)) and int(trade_count_raw) == 0
    ):
        raise ValueError(f"No performance data for strategy {strategy.id} in last {days} days")

    trades_count = int(trade_count_raw)
    win_rate = float(result[1] or 0.0)
    avg_pnl = float(result[2] or 0.0)
    actual_sharpe = float(result[3] or 0.0)
    max_drawdown = float(result[4] or 0.0)

    expected_sharpe = float(strategy.expected_sharpe or 0.0)
    performance_ratio = actual_sharpe / expected_sharpe if expected_sharpe > 0 else 0.0

    # Calculate buy-and-hold benchmark (SPY)
    buy_hold_sharpe = await calculate_buy_hold_sharpe(strategy.symbol, days)
    beats_benchmark = actual_sharpe > buy_hold_sharpe

    # Determine if underperforming
    underperforming = performance_ratio < 0.9  # <90% of expected

    # LLM diagnosis
    diagnosis = await llm_diagnose_performance(
        strategy=strategy,
        actual_sharpe=actual_sharpe,
        expected_sharpe=expected_sharpe,
        trades_count=trades_count,
        win_rate=win_rate,
        avg_pnl=avg_pnl,
        max_drawdown=max_drawdown,
        buy_hold_sharpe=buy_hold_sharpe,
    )

    return StrategyAnalysis(
        strategy_id=strategy.id,
        symbol=strategy.symbol,
        days_analyzed=days,
        actual_sharpe=actual_sharpe,
        expected_sharpe=expected_sharpe,
        performance_ratio=performance_ratio,
        trades_count=trades_count,
        win_rate=win_rate,
        avg_pnl=avg_pnl,
        max_drawdown=max_drawdown,
        underperforming=underperforming,
        diagnosis=diagnosis,
        buy_hold_sharpe=buy_hold_sharpe,
        beats_benchmark=beats_benchmark,
    )


async def calculate_buy_hold_sharpe(symbol: str, days: int) -> float:
    """Calculate buy-and-hold Sharpe ratio for benchmark.

    Args:
        symbol: Stock symbol
        days: Number of days to calculate over

    Returns:
        Buy & hold Sharpe ratio
    """
    # Use SPY as benchmark for all stocks
    benchmark_symbol = "SPY"

    with get_connection_manager().connection() as conn:
        result = conn.execute(
            """
            SELECT close
            FROM day_bars
            WHERE symbol = %s
              AND date >= CURRENT_DATE - INTERVAL '%s days'
            ORDER BY date
            """,
            (benchmark_symbol, days),
        ).fetchall()

    if len(result) < 2:
        logger.warning("insufficient_buyhold_data", data_points=len(result))
        return 0.0

    # Calculate daily returns - type narrowing for row[0]
    prices: list[float] = []
    for row in result:
        price_val = row[0]
        if price_val is not None:
            prices.append(float(price_val))

    if len(prices) < 2:
        logger.warning(
            f"Insufficient non-null prices for buy-hold calculation ({len(prices)} prices)"
        )
        return 0.0
    returns = [(prices[i] - prices[i - 1]) / prices[i - 1] for i in range(1, len(prices))]

    # Calculate Sharpe ratio using mean return divided by standard deviation, then annualized
    if len(returns) < 2:
        return 0.0

    mean_return = sum(returns) / len(returns)
    variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
    std_dev = variance**0.5

    if std_dev == 0:
        return 0.0

    # Annualize (252 trading days)
    sharpe = (mean_return / std_dev) * (252**0.5)
    return float(sharpe)
