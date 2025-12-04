"""Performance Metrics Collector for LLM Agent Prompts.

Provides rolling performance metrics to inject into agent prompts,
enabling behavioral calibration based on actual trading results.

Section 1.1: Add Performance Feedback to Trading Prompts
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from app.logging_config import get_logger
from app.rules import get_rules

if TYPE_CHECKING:
    from app.storage.facade import PortfolioStorage

logger = get_logger(__name__)


@dataclass
class PerformanceMetrics:
    """Rolling performance metrics for agent prompts."""

    # Core metrics
    session_return_pct: float  # Total return this period
    rolling_sharpe: float | None  # Annualized Sharpe ratio
    win_rate: float | None  # Win rate %
    current_drawdown_pct: float  # Current drawdown from peak

    # Benchmark comparison
    excess_vs_bh: float | None  # Excess return vs buy-and-hold
    beats_benchmark: bool | None  # Whether beating benchmark

    # Volume metrics
    num_trades: int  # Number of trades in period
    avg_trade_return_pct: float | None  # Average return per trade

    # Period info
    period_days: int
    period_start: datetime
    period_end: datetime


def get_rolling_performance_metrics(
    storage: PortfolioStorage,
    days: int = 30,
) -> PerformanceMetrics:
    """Get rolling performance metrics for the specified period.

    Args:
        storage: PortfolioStorage instance
        days: Lookback period in days (default 30)

    Returns:
        PerformanceMetrics dataclass with all metrics
    """
    period_end = datetime.now()
    period_start = period_end - timedelta(days=days)

    # Query paper trades for the period
    trades_df = storage.query(
        """
        SELECT id, symbol, action, quantity, entry_price, exit_price,
               pnl, pnl_pct, status, created_at, closed_at
        FROM paper_trades
        WHERE created_at >= $1
          AND status IN ('closed', 'completed')
        ORDER BY created_at ASC
        """,
        [period_start],
    )

    # Calculate trade-level metrics
    num_trades = len(trades_df) if not trades_df.is_empty() else 0
    win_rate = None
    avg_trade_return_pct = None
    session_return_pct = 0.0

    if num_trades > 0:
        # Calculate win rate
        pnl_col = trades_df["pnl"]
        winning_trades = sum(1 for pnl in pnl_col if pnl is not None and float(pnl) > 0)
        win_rate = (winning_trades / num_trades) * 100

        # Calculate average return per trade
        pnl_pcts = [float(p) for p in trades_df["pnl_pct"] if p is not None]
        if pnl_pcts:
            avg_trade_return_pct = sum(pnl_pcts) / len(pnl_pcts)
            session_return_pct = sum(pnl_pcts)

    # Query recent backtest runs for Sharpe and benchmark
    backtest_df = storage.query(
        """
        SELECT id, sharpe_ratio, total_return_pct, max_drawdown_pct,
               buy_hold_return, excess_return, beats_buy_hold
        FROM backtest_runs
        WHERE created_at >= $1
          AND status = 'completed'
        ORDER BY created_at DESC
        LIMIT 10
        """,
        [period_start],
    )

    # Calculate aggregate backtest metrics
    rolling_sharpe = None
    excess_vs_bh = None
    beats_benchmark = None
    current_drawdown_pct = 0.0

    if not backtest_df.is_empty():
        # Average Sharpe from recent backtests
        sharpe_vals = [float(s) for s in backtest_df["sharpe_ratio"] if s is not None]
        if sharpe_vals:
            rolling_sharpe = sum(sharpe_vals) / len(sharpe_vals)

        # Average excess return vs benchmark
        excess_vals = [float(e) for e in backtest_df["excess_return"] if e is not None]
        if excess_vals:
            excess_vs_bh = sum(excess_vals) / len(excess_vals)
            beats_benchmark = excess_vs_bh > 0

        # Use most recent drawdown
        drawdown_vals = [float(d) for d in backtest_df["max_drawdown_pct"] if d is not None]
        if drawdown_vals:
            current_drawdown_pct = drawdown_vals[0]  # Most recent

    logger.info(
        "performance_metrics_collected",
        days=days,
        num_trades=num_trades,
        win_rate=win_rate,
        rolling_sharpe=rolling_sharpe,
        excess_vs_bh=excess_vs_bh,
    )

    return PerformanceMetrics(
        session_return_pct=session_return_pct,
        rolling_sharpe=rolling_sharpe,
        win_rate=win_rate,
        current_drawdown_pct=current_drawdown_pct,
        excess_vs_bh=excess_vs_bh,
        beats_benchmark=beats_benchmark,
        num_trades=num_trades,
        avg_trade_return_pct=avg_trade_return_pct,
        period_days=days,
        period_start=period_start,
        period_end=period_end,
    )


def format_performance_context(metrics: PerformanceMetrics) -> str:
    """Format performance metrics for injection into agent prompts.

    Args:
        metrics: PerformanceMetrics from get_rolling_performance_metrics()

    Returns:
        Formatted string for prompt injection
    """
    # Format individual metrics
    sharpe_str = f"{metrics.rolling_sharpe:.2f}" if metrics.rolling_sharpe is not None else "N/A"
    win_rate_str = f"{metrics.win_rate:.1f}%" if metrics.win_rate is not None else "N/A"
    excess_str = f"{metrics.excess_vs_bh:+.2f}%" if metrics.excess_vs_bh is not None else "N/A"
    avg_trade_str = (
        f"{metrics.avg_trade_return_pct:+.2f}%"
        if metrics.avg_trade_return_pct is not None
        else "N/A"
    )

    context = f"""
YOUR PERFORMANCE METRICS ({metrics.period_days}-day rolling):
- Session Return: {metrics.session_return_pct:+.2f}%
- Rolling Sharpe: {sharpe_str}
- Win Rate: {win_rate_str}
- Current Drawdown: -{metrics.current_drawdown_pct:.1f}%
- Excess vs Buy-Hold: {excess_str}
- Trades Executed: {metrics.num_trades}
- Avg Trade Return: {avg_trade_str}
"""

    return context.strip()


def get_behavioral_guidance(metrics: PerformanceMetrics) -> str:
    """Generate behavioral calibration guidance based on performance.

    Args:
        metrics: PerformanceMetrics from get_rolling_performance_metrics()

    Returns:
        Behavioral guidance string for prompt injection
    """
    guidance_lines = []
    rules = get_rules()

    # Check Sharpe ratio
    if metrics.rolling_sharpe is not None and metrics.rolling_sharpe < 0.5:
        guidance_lines.append(
            "- CAUTION: Low Sharpe ratio. Consider reducing position sizes and being more selective."
        )

    # Check drawdown
    drawdown_warning = rules.risk_management.drawdown_warning_level_1
    if metrics.current_drawdown_pct > drawdown_warning:
        guidance_lines.append(
            f"- WARNING: Drawdown at {metrics.current_drawdown_pct:.1f}%. "
            "Be more conservative and tighten stop-losses."
        )

    # Check benchmark performance
    if metrics.excess_vs_bh is not None and metrics.excess_vs_bh < 0:
        guidance_lines.append(
            "- NOTE: Underperforming buy-and-hold. Question if active trading adds value here."
        )

    # Check win rate
    if metrics.win_rate is not None and metrics.win_rate < 40:
        guidance_lines.append(
            "- CONCERN: Low win rate. Focus on higher-conviction opportunities only."
        )

    if not guidance_lines:
        guidance_lines.append("- Performance on track. Maintain current approach.")

    return "\n".join(["BEHAVIORAL CALIBRATION:"] + guidance_lines)


def get_full_performance_prompt_section(storage: PortfolioStorage, days: int = 30) -> str:
    """Get complete performance section for agent prompts.

    Combines metrics and behavioral guidance into single prompt section.

    Args:
        storage: PortfolioStorage instance
        days: Lookback period in days

    Returns:
        Complete formatted string ready for prompt injection
    """
    metrics = get_rolling_performance_metrics(storage, days)
    context = format_performance_context(metrics)
    guidance = get_behavioral_guidance(metrics)

    return f"{context}\n\n{guidance}"
