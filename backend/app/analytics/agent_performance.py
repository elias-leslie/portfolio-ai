"""Agent performance metrics calculation.

This module provides functions for calculating and tracking the real-world
performance of AI agent investment ideas through paper trading results.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from app.logging_config import get_logger
from app.storage import PortfolioStorage

logger = get_logger(__name__)


def _fetch_agent_trades(
    storage: PortfolioStorage, agent_type: str, cutoff_date: dt.date
) -> list[dict[str, Any]]:
    """Fetch all trades for agent type since cutoff date.

    Args:
        storage: PortfolioStorage instance
        agent_type: Type of agent
        cutoff_date: Earliest date to include

    Returns:
        List of trade records
    """
    query = """
        SELECT
            io.idea_id,
            io.ticker,
            io.idea_type,
            io.entry_price,
            io.entry_date,
            io.exit_price,
            io.exit_date,
            io.status,
            io.realized_return_pct,
            io.current_return_pct,
            io.holding_days,
            ai.agent_run_id,
            ar.agent_type,
            ar.started_at
        FROM idea_outcomes io
        JOIN agent_ideas ai ON io.idea_id = ai.id
        JOIN agent_runs ar ON ai.agent_run_id = ar.id
        WHERE ar.agent_type = ?
          AND io.created_at >= ?
        ORDER BY io.created_at DESC
    """

    results = storage.query(query, [agent_type, cutoff_date])

    if results.is_empty():
        return []

    return results.to_dicts()


def _calculate_win_loss_metrics(
    closed_trades: list[dict[str, Any]],
) -> tuple[list[float], list[float], list[float]]:
    """Calculate win/loss metrics from closed trades.

    Args:
        closed_trades: List of closed trade records

    Returns:
        Tuple of (returns, winners, losers) lists
    """
    returns = [
        t["realized_return_pct"] for t in closed_trades if t["realized_return_pct"] is not None
    ]

    if not returns:
        return [], [], []

    winners = [r for r in returns if r > 0]
    losers = [r for r in returns if r <= 0]

    return returns, winners, losers


def _calculate_best_worst_trades(
    closed_trades: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Find best and worst trades from closed trades.

    Args:
        closed_trades: List of closed trade records

    Returns:
        Tuple of (best_trade, worst_trade) dicts
    """
    if not closed_trades:
        return None, None

    best_trade_data = max(closed_trades, key=lambda t: t["realized_return_pct"] or 0.0)
    worst_trade_data = min(closed_trades, key=lambda t: t["realized_return_pct"] or 0.0)

    best_trade = {
        "ticker": best_trade_data["ticker"],
        "return": round(best_trade_data["realized_return_pct"] or 0.0, 2),
        "entry_date": str(best_trade_data["entry_date"]) if best_trade_data["entry_date"] else None,
        "exit_date": str(best_trade_data["exit_date"]) if best_trade_data["exit_date"] else None,
        "holding_days": best_trade_data["holding_days"],
    }

    worst_trade = {
        "ticker": worst_trade_data["ticker"],
        "return": round(worst_trade_data["realized_return_pct"] or 0.0, 2),
        "entry_date": str(worst_trade_data["entry_date"])
        if worst_trade_data["entry_date"]
        else None,
        "exit_date": str(worst_trade_data["exit_date"]) if worst_trade_data["exit_date"] else None,
        "holding_days": worst_trade_data["holding_days"],
    }

    return best_trade, worst_trade


def _build_performance_metrics(
    total_ideas: int,
    open_ideas: int,
    closed_ideas: int,
    returns: list[float],
    winners: list[float],
    losers: list[float],
    best_trade: dict[str, Any] | None,
    worst_trade: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build performance metrics dict from calculated values.

    Args:
        total_ideas: Total number of ideas
        open_ideas: Number of open trades
        closed_ideas: Number of closed trades
        returns: List of all returns
        winners: List of winning returns
        losers: List of losing returns
        best_trade: Best trade data
        worst_trade: Worst trade data

    Returns:
        Dict with performance metrics
    """
    if not returns:
        return {
            "win_rate": 0.0,
            "average_return": 0.0,
            "average_winner": 0.0,
            "average_loser": 0.0,
            "win_loss_ratio": None,
            "total_ideas": total_ideas,
            "open_ideas": open_ideas,
            "closed_ideas": closed_ideas,
            "best_trade": best_trade,
            "worst_trade": worst_trade,
        }

    # Calculate metrics
    win_rate = (len(winners) / len(returns)) * 100 if returns else 0.0
    average_return = sum(returns) / len(returns) if returns else 0.0
    average_winner = sum(winners) / len(winners) if winners else 0.0
    average_loser = sum(losers) / len(losers) if losers else 0.0

    # Calculate win/loss ratio
    if losers and average_loser != 0:
        win_loss_ratio = average_winner / abs(average_loser)
    else:
        win_loss_ratio = float("inf") if winners else 0.0

    return {
        "win_rate": round(win_rate, 2),
        "average_return": round(average_return, 2),
        "average_winner": round(average_winner, 2),
        "average_loser": round(average_loser, 2),
        "win_loss_ratio": round(win_loss_ratio, 2) if win_loss_ratio != float("inf") else None,
        "total_ideas": total_ideas,
        "open_ideas": open_ideas,
        "closed_ideas": closed_ideas,
        "best_trade": best_trade,
        "worst_trade": worst_trade,
    }


def get_agent_performance(
    storage: PortfolioStorage,
    agent_type: str,
    days: int = 90,
) -> dict[str, Any]:
    """Calculate performance metrics for an agent based on paper trading results.

    Analyzes paper trading outcomes to determine win rate, average returns,
    and other key performance indicators for the specified agent type over
    the given time period.

    Args:
        storage: PortfolioStorage instance for database access
        agent_type: Type of agent (e.g., "DiscoveryAgent", "PortfolioAnalyzerAgent")
        days: Number of days to look back for performance calculation (default: 90)

    Returns:
        Dict with performance metrics:
        - agent_type: Agent type name
        - period_days: Number of days analyzed
        - metrics: Dict containing:
            - win_rate: Percentage of winning trades (0-100)
            - average_return: Mean return percentage of all closed trades
            - average_winner: Mean return of winning trades
            - average_loser: Mean return of losing trades
            - win_loss_ratio: Ratio of avg_winner to abs(avg_loser)
            - total_ideas: Total number of ideas generated
            - open_ideas: Number of currently open trades
            - closed_ideas: Number of closed trades
            - best_trade: Dict with ticker and return of best trade
            - worst_trade: Dict with ticker and return of worst trade

    Example:
        >>> storage = get_storage()
        >>> perf = get_agent_performance(storage, "DiscoveryAgent", days=90)
        >>> print(f"Win rate: {perf['metrics']['win_rate']:.1f}%")
        Win rate: 68.0%
        >>> print(f"Avg return: {perf['metrics']['average_return']:.2f}%")
        Avg return: 5.20%
    """
    # Fetch trades for agent
    cutoff_date = dt.date.today() - dt.timedelta(days=days)
    trades = _fetch_agent_trades(storage, agent_type, cutoff_date)

    if not trades:
        logger.info("agent_performance_no_data", agent_type=agent_type, days=days)
        return _empty_performance_metrics(agent_type, days)

    # Categorize trades
    total_ideas = len(trades)
    open_trades = [t for t in trades if t["status"] == "open"]
    closed_trades = [t for t in trades if t["status"] in ["target_hit", "stop_hit", "expired"]]

    open_ideas = len(open_trades)
    closed_ideas = len(closed_trades)

    # Check if we have closed trades
    if closed_ideas == 0:
        logger.info(
            "agent_performance_no_closed_trades",
            agent_type=agent_type,
            days=days,
            total_ideas=total_ideas,
        )
        return _empty_performance_metrics(
            agent_type, days, total_ideas=total_ideas, open_ideas=open_ideas
        )

    # Calculate win/loss metrics
    returns, winners, losers = _calculate_win_loss_metrics(closed_trades)

    if not returns:
        logger.warning(
            "agent_performance_no_returns_data",
            agent_type=agent_type,
            closed_ideas=closed_ideas,
        )
        return _empty_performance_metrics(
            agent_type,
            days,
            total_ideas=total_ideas,
            open_ideas=open_ideas,
            closed_ideas=closed_ideas,
        )

    # Find best and worst trades
    best_trade, worst_trade = _calculate_best_worst_trades(closed_trades)

    # Build metrics
    metrics = _build_performance_metrics(
        total_ideas, open_ideas, closed_ideas, returns, winners, losers, best_trade, worst_trade
    )

    logger.info(
        "agent_performance_calculated",
        agent_type=agent_type,
        days=days,
        win_rate=metrics["win_rate"],
        average_return=metrics["average_return"],
        total_ideas=total_ideas,
        closed_ideas=closed_ideas,
    )

    return {
        "agent_type": agent_type,
        "period_days": days,
        "metrics": metrics,
    }


def _empty_performance_metrics(
    agent_type: str,
    days: int,
    total_ideas: int = 0,
    open_ideas: int = 0,
    closed_ideas: int = 0,
) -> dict[str, Any]:
    """Return empty performance metrics structure.

    Used when there's no data available for the specified agent type and period.

    Args:
        agent_type: Type of agent
        days: Number of days analyzed
        total_ideas: Total number of ideas (default: 0)
        open_ideas: Number of open trades (default: 0)
        closed_ideas: Number of closed trades (default: 0)

    Returns:
        Dict with empty/zero metrics
    """
    return {
        "agent_type": agent_type,
        "period_days": days,
        "metrics": {
            "win_rate": 0.0,
            "average_return": 0.0,
            "average_winner": 0.0,
            "average_loser": 0.0,
            "win_loss_ratio": None,
            "total_ideas": total_ideas,
            "open_ideas": open_ideas,
            "closed_ideas": closed_ideas,
            "best_trade": None,
            "worst_trade": None,
        },
    }


def get_agent_performance_summary(storage: PortfolioStorage, days: int = 30) -> dict[str, Any]:
    """Get performance summary for all agent types.

    Calculates performance metrics for all agents and returns a summary
    for easy comparison.

    Args:
        storage: PortfolioStorage instance for database access
        days: Number of days to look back (default: 30)

    Returns:
        Dict with performance summaries for each agent type:
        - agents: List of dicts, each containing agent_type and metrics
        - period_days: Number of days analyzed
        - total_agents: Number of agent types tracked

    Example:
        >>> storage = get_storage()
        >>> summary = get_agent_performance_summary(storage, days=30)
        >>> for agent in summary['agents']:
        ...     print(f"{agent['agent_type']}: {agent['win_rate']:.1f}% win rate")
        DiscoveryAgent: 68.0% win rate
        PortfolioAnalyzerAgent: 72.5% win rate
    """
    # Get unique agent types from agent_runs
    agent_types_query = """
        SELECT DISTINCT agent_type
        FROM agent_runs
        ORDER BY agent_type
    """

    agent_types_result = storage.query(agent_types_query)

    if agent_types_result.is_empty():
        return {
            "agents": [],
            "period_days": days,
            "total_agents": 0,
        }

    agent_types = [row["agent_type"] for row in agent_types_result.to_dicts()]

    # Get performance for each agent type
    agents_performance = []
    for agent_type in agent_types:
        perf = get_agent_performance(storage, agent_type, days=days)
        agents_performance.append(
            {
                "agent_type": agent_type,
                **perf["metrics"],
            }
        )

    return {
        "agents": agents_performance,
        "period_days": days,
        "total_agents": len(agents_performance),
    }
