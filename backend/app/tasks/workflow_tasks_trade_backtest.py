"""Backtest preparation and gating logic for paper trade validation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from datetime import date as date_type

from app.agents.tools import AgentTools
from app.agents.workflow_orchestrator import WorkflowOrchestrator
from app.logging_config import get_logger
from app.storage.facade import PortfolioStorage
from app.tasks.workflow_tasks_helpers import (
    _check_backtest_gating,
    _get_available_data_range,
    _resolve_strategy_params,
    _setup_agent_tools,
)

logger = get_logger(__name__)


def _resolve_backtest_date_range(
    storage: PortfolioStorage,
    symbol: str,
    workflow_id: str,
) -> tuple[str, str] | dict[str, object]:
    """Compute start/end dates for backtest, triggering backfill if needed.

    Returns either (start_date, end_date) strings or an early-exit result dict.
    """
    today = datetime.now(UTC).date()
    end_date = today.isoformat()
    requested_start = today - timedelta(days=365)

    data_min, _data_max = _get_available_data_range(storage, symbol)
    if data_min is None:
        logger.warning(f"No historical data for {symbol}, triggering backfill")
        from app.tasks.ingestion.price_ingestion import ingest_historical_ohlcv

        ingest_historical_ohlcv([symbol], days=1300)
        return {
            "status": "pending_data",
            "message": f"Triggered historical data fetch for {symbol}. Retry in 5 minutes.",
            "workflow_id": workflow_id,
        }

    data_min_date = date_type.fromisoformat(data_min)
    if requested_start < data_min_date:
        logger.info(f"Adjusting backtest start to {data_min_date} (data only available from {data_min})")
        return data_min, end_date
    return requested_start.isoformat(), end_date


def _run_backtest(
    tools: AgentTools,
    workflow_id: str,
    orchestrator: WorkflowOrchestrator,
    symbol: str,
    start_date: str,
    end_date: str,
    strategy_name: str,
    min_signal_strength: int,
    max_holding_days: int,
    position_sizing_method: str,
    position_size_value: float,
) -> tuple[dict[str, object] | None, dict[str, object] | None, dict[str, object] | None]:
    """Execute backtest and return (backtest_result, metrics, early_exit_result).

    If early_exit_result is not None, the caller should return it immediately.
    """
    logger.info(f"Executing 1-year backtest for {symbol} ({start_date} to {end_date})")
    backtest_result = tools.execute_run_backtest(
        agent_run_id=workflow_id,
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        strategy=strategy_name,
        min_signal_strength=min_signal_strength,
        max_holding_days=max_holding_days,
        position_sizing_method=position_sizing_method,
        position_size_value=position_size_value,
    )

    if backtest_result.get("status") != "completed":
        error_msg = str(backtest_result.get("error", "Unknown backtest error"))
        logger.error(f"Backtest failed: {error_msg}")
        orchestrator.update_workflow_status(
            workflow_id, status="failed", current_step="backtest_failed", error=error_msg
        )
        return None, None, {
            "status": "failed",
            "workflow_id": workflow_id,
            "error": f"Backtest execution failed: {error_msg}",
        }

    metrics: dict[str, object] = {
        "sharpe_ratio": backtest_result.get("sharpe_ratio", 0.0),
        "win_rate": backtest_result.get("win_rate", 0.0),
        "max_drawdown_pct": backtest_result.get("max_drawdown_pct", 0.0),
        "total_return_pct": backtest_result.get("total_return_pct", 0.0),
        "num_trades": backtest_result.get("num_trades", 0),
    }
    logger.info(f"Backtest complete: {metrics}")
    return backtest_result, metrics, None


def _apply_backtest_gating(
    orchestrator: WorkflowOrchestrator,
    workflow_id: str,
    symbol: str,
    action: str,
    backtest_metrics: dict[str, object],
) -> dict[str, object] | None:
    """Apply hard gating thresholds to backtest metrics.

    Returns an early-exit result dict if gating fails, else None.
    """
    gating_failures = _check_backtest_gating(backtest_metrics)
    if not gating_failures:
        return None

    gating_reason = "; ".join(gating_failures)
    logger.warning(f"Backtest gating FAILED for {symbol}: {gating_reason}")
    orchestrator.complete_workflow(
        workflow_id,
        result={
            "symbol": symbol, "action": action, "approved": False, "trade_id": None,
            "gating_failed": True, "gating_reason": gating_reason,
            "backtest_metrics": backtest_metrics,
        },
    )
    return {
        "status": "completed", "workflow_id": workflow_id, "approved": False,
        "gating_failed": True, "gating_reason": gating_reason,
        "backtest_metrics": backtest_metrics,
    }


def _prepare_backtest(
    storage: PortfolioStorage,
    orchestrator: WorkflowOrchestrator,
    workflow_id: str,
    symbol: str,
) -> tuple[str, str, dict[str, object] | None, dict[str, object] | None] | dict[str, object]:
    """Resolve date range, strategy params, and run backtest.

    Returns either (start, end, backtest_result, metrics) or an early-exit dict.
    """
    date_range = _resolve_backtest_date_range(storage, symbol, workflow_id)
    if isinstance(date_range, dict):
        return date_range
    start_date, end_date = date_range

    try:
        strategy_name, min_sig, max_hold, sizing_method, size_value = _resolve_strategy_params(
            storage, symbol
        )
    except Exception as e:
        logger.error(f"Backtest execution error: {e}")
        orchestrator.update_workflow_status(
            workflow_id, status="failed", current_step="backtest_error", error=str(e)
        )
        return {"status": "failed", "workflow_id": workflow_id,
                "error": f"Backtest execution exception: {e}"}

    tools = _setup_agent_tools(storage)
    backtest_result, backtest_metrics, early_exit = _run_backtest(
        tools, workflow_id, orchestrator, symbol, start_date, end_date,
        strategy_name, min_sig, max_hold, sizing_method, size_value,
    )
    if early_exit is not None:
        return early_exit

    return start_date, end_date, backtest_result, backtest_metrics
