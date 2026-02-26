"""Private helpers for strategy performance monitoring.

Internal helpers for metrics calculation, archive decisions, and
performance recording. Not part of the public API.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, Literal

from app.backtest.metrics import calculate_simple_max_drawdown, calculate_simple_sharpe
from app.logging_config import get_logger
from app.strategies.storage import StrategyStorage

logger = get_logger(__name__)

PERFORMANCE_RATIO_THRESHOLD = 0.7
ERROR_MESSAGE_TRUNCATE = 100


def _should_archive_strategy(performance_ratio: float, days_since_activation: int) -> bool:
    """Return True if strategy should be archived based on performance."""
    return (
        performance_ratio < PERFORMANCE_RATIO_THRESHOLD
        and days_since_activation > StrategyStorage.PERFORMANCE_WINDOW_DAYS
    )


def _compute_performance_ratio(
    strategy: Any,
    metrics: dict[str, Any],
) -> tuple[float, float, float]:
    """Return (expected_sharpe, actual_sharpe, performance_ratio) for a strategy."""
    expected_sharpe = float(strategy.expected_sharpe or 0.0)
    actual_sharpe = metrics["sharpe_ratio_30d"]
    performance_ratio = actual_sharpe / expected_sharpe if expected_sharpe > 0 else 0
    return expected_sharpe, actual_sharpe, performance_ratio


def _determine_archive_decision(
    strategy: Any,
    metrics: dict[str, Any],
    strategy_storage: Any,
) -> tuple[bool, str | None]:
    """Determine and execute archival if criteria are met.

    Returns:
        Tuple of (was_archived, result_message_or_none)
    """
    expected_sharpe, actual_sharpe, performance_ratio = _compute_performance_ratio(
        strategy, metrics
    )
    days_since_activation = (
        (datetime.now(UTC) - strategy.activation_date).days if strategy.activation_date else 0
    )

    if not _should_archive_strategy(performance_ratio, days_since_activation):
        return False, None

    reason = (
        f"Underperforming: {actual_sharpe:.2f} Sharpe vs "
        f"{expected_sharpe:.2f} expected ({performance_ratio:.1%})"
    )
    strategy_storage.archive_strategy(strategy.id, reason)
    logger.warning(
        "Strategy archived due to underperformance",
        strategy_id=strategy.id,
        strategy_name=strategy.name,
        performance_ratio=performance_ratio,
    )
    return True, f"Archived {strategy.name}: {performance_ratio:.1%} of expected performance"


def _update_live_metrics_if_active(
    strategy: Any,
    metrics: dict[str, Any],
    strategy_storage: Any,
    archived: bool,
) -> None:
    """Update live performance metrics if strategy is not archived."""
    if archived:
        return
    strategy_storage.update_live_performance(
        strategy_id=strategy.id,
        trades_count=metrics["trades_30d"],
        win_rate=metrics["win_rate_30d"],
        sharpe_ratio=metrics["sharpe_ratio_30d"],
    )


def _record_and_emit_performance(
    strategy: Any,
    metrics: dict[str, Any],
    strategy_storage: Any,
) -> None:
    """Record daily performance and emit event for downstream triggers."""
    _, actual_sharpe, performance_ratio = _compute_performance_ratio(strategy, metrics)

    status: Literal["active", "underperforming"] = (
        "underperforming" if performance_ratio < PERFORMANCE_RATIO_THRESHOLD else "active"
    )

    strategy_storage.record_daily_performance(
        strategy_id=strategy.id,
        date=datetime.now(UTC).date(),
        trades_today=metrics["trades_today"],
        wins_today=metrics["wins_today"],
        losses_today=metrics["losses_today"],
        pnl_today=Decimal(str(metrics["pnl_today"])),
        trades_30d=metrics["trades_30d"],
        win_rate_30d=metrics["win_rate_30d"],
        sharpe_ratio_30d=actual_sharpe,
        max_drawdown_30d=metrics["max_drawdown_30d"],
        status=status,
        notes=f"Performance ratio: {performance_ratio:.2f}" if status == "underperforming" else None,
    )

    logger.info(
        "Strategy evaluated",
        strategy_id=strategy.id,
        strategy_name=strategy.name,
        trades_30d=metrics["trades_30d"],
        sharpe_30d=actual_sharpe,
        performance_ratio=performance_ratio,
        status=status,
    )

    from app.tasks.triggers import emit_event

    emit_event(
        "strategy_performance_updated",
        {
            "strategy_id": strategy.id,
            "symbol": strategy.symbol,
            "sharpe_30d": actual_sharpe,
            "performance_ratio": performance_ratio,
            "status": status,
        },
    )


def _calculate_today_metrics(trades: list[dict[str, Any]], today: date) -> dict[str, Any]:
    """Calculate metrics for trades made today."""
    today_trades = [t for t in trades if t["date"] == today]
    trades_today = len(today_trades)
    wins_today = sum(1 for t in today_trades if t["pnl"] > 0)
    return {
        "trades_today": trades_today,
        "wins_today": wins_today,
        "losses_today": trades_today - wins_today,
        "pnl_today": sum(t["pnl"] for t in today_trades),
    }


def _parse_trade_rows(rows: list[Any]) -> list[dict[str, Any]]:
    """Normalise raw DB rows to list of {date, pnl} dicts."""
    trades: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, tuple):
            trade_date, pnl = row[0], row[1]
        else:
            trade_date = row.get("trade_date", row.get("date"))
            pnl = row.get("pnl", 0.0)
        if pnl is None:
            continue
        trades.append({"date": trade_date, "pnl": float(pnl)})
    return trades


_EMPTY_METRICS: dict[str, Any] = {
    "trades_today": 0,
    "wins_today": 0,
    "losses_today": 0,
    "pnl_today": 0.0,
    "trades_30d": 0,
    "win_rate_30d": 0.0,
    "sharpe_ratio_30d": 0.0,
    "max_drawdown_30d": 0.0,
}


def _calculate_rolling_metrics(
    strategy_storage: Any,
    strategy_id: str,
    window_days: int = StrategyStorage.PERFORMANCE_WINDOW_DAYS,
) -> dict[str, Any]:
    """Calculate rolling performance metrics for a strategy."""
    cutoff_date = datetime.now(UTC).date() - timedelta(days=window_days)

    try:
        rows = strategy_storage.get_strategy_trades(strategy_id, cutoff_date)
    except Exception as e:
        logger.warning("Could not query trades for strategy", strategy_id=strategy_id, error=str(e))
        rows = []

    if not rows:
        return dict(_EMPTY_METRICS)

    trades = _parse_trade_rows(rows)
    if not trades:
        return dict(_EMPTY_METRICS)

    today = datetime.now(UTC).date()
    today_metrics = _calculate_today_metrics(trades, today)

    trades_30d = len(trades)
    wins_30d = sum(1 for t in trades if t["pnl"] > 0)
    daily_returns = [t["pnl"] for t in trades]

    return {
        **today_metrics,
        "trades_30d": trades_30d,
        "win_rate_30d": wins_30d / trades_30d if trades_30d > 0 else 0.0,
        "sharpe_ratio_30d": calculate_simple_sharpe(daily_returns),
        "max_drawdown_30d": calculate_simple_max_drawdown(daily_returns),
    }


def _evaluate_single_strategy(
    strategy: Any,
    conn: Any,
    strategy_storage: Any,
) -> tuple[str | None, bool]:
    """Evaluate one strategy: metrics → archive decision → update → record.

    Returns:
        Tuple of (result_message_or_none, was_archived)
    """
    metrics = _calculate_rolling_metrics(strategy_storage, strategy.id)
    archived, result_msg = _determine_archive_decision(strategy, metrics, strategy_storage)
    _update_live_metrics_if_active(strategy, metrics, strategy_storage, archived)
    _record_and_emit_performance(strategy, metrics, strategy_storage)
    return result_msg, archived


def _days_since(dt: datetime | None) -> int:
    """Return integer days elapsed since *dt* (UTC-aware)."""
    if not dt:
        return 0
    now = datetime.now(UTC)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return (now - dt).days


def _promotion_skip_reason(
    strategy: Any,
    min_days: int,
    min_sharpe: float,
) -> str | None:
    """Return a skip reason string, or None if strategy meets promotion criteria."""
    days = _days_since(strategy.created_at)
    if days < min_days:
        return f"insufficient age ({days}d < {min_days}d)"

    expected_sharpe = float(strategy.expected_sharpe or 0.0)
    if expected_sharpe < min_sharpe:
        return f"Sharpe below minimum ({expected_sharpe:.2f} < {min_sharpe:.2f})"

    if expected_sharpe < 0:
        return "negative expected Sharpe"

    return None
