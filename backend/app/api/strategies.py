"""API endpoints for strategy management.

Provides REST API for:
- Listing strategies with filtering
- Getting strategy details
- Triggering strategy generation
- Updating strategy status (activate/archive)
- Viewing performance comparison
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.agents.workflows.strategy_research_workflow import strategy_research_workflow
from app.logging_config import get_logger
from app.strategies.models import StrategyDefinition
from app.strategies.performance_utils import (
    calculate_performance_status,
    map_performance_flag_to_status,
)
from app.strategies.storage import get_strategy_storage
from app.tasks.strategy.generation_tasks import weekly_strategy_generation
from app.tasks.strategy_signal_tasks import generate_signal_for_strategy
from app.utils.formatters import format_db_date, parse_float

logger = get_logger(__name__)

router = APIRouter(prefix="/api/strategies", tags=["strategies"])


# ============================================================================
# Helper Functions
# ============================================================================


def _get_strategy_or_404(strategy_id: str) -> StrategyDefinition:
    """Get strategy by ID or raise 404 if not found.

    Args:
        strategy_id: Strategy UUID

    Returns:
        Strategy object

    Raises:
        HTTPException: 404 if strategy not found
    """
    storage = get_strategy_storage()
    strategy = storage.get_strategy_by_id(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")
    return strategy


# ============================================================================
# Request/Response Models
# ============================================================================


class StrategyListItem(BaseModel):
    """Strategy list item (summary view)."""

    id: str
    name: str
    symbol: str
    strategy_type: str
    status: Literal["testing", "active", "archived"]
    version: int
    expected_sharpe: float | None
    live_sharpe_ratio: float | None
    live_win_rate: float | None
    trades_count: int
    created_at: str
    activation_date: str | None
    # Performance variance indicator (Task 4.2)
    performance_variance: float | None = None  # Ratio of live vs expected Sharpe
    performance_flag: Literal["exceeding", "meeting", "underperforming", "no_data"] | None = None


class StrategyDetail(BaseModel):
    """Strategy detail view (full data)."""

    id: str
    name: str
    symbol: str
    strategy_type: str
    parameters: dict[str, Any]
    research_summary: dict[str, Any]
    generation_reasoning: str
    backtest_metrics: list[dict[str, Any]]
    expected_sharpe: float | None
    expected_win_rate: float | None
    expected_max_drawdown: float | None
    live_trades_count: int
    live_win_rate: float | None
    live_sharpe_ratio: float | None
    status: Literal["testing", "active", "archived"]
    version: int
    created_at: str
    activation_date: str | None
    archive_date: str | None
    archive_reason: str | None
    performance_history: list[dict[str, Any]]


class GenerateStrategyRequest(BaseModel):
    """Request to generate new strategy."""

    symbol: str = Field(min_length=1, max_length=10)
    force_regenerate: bool = False


class GenerateBatchRequest(BaseModel):
    """Request to generate strategies for multiple symbols."""

    symbols: list[str] | None = Field(
        default=None,
        description="Symbols to generate for. If None, uses top N watchlist symbols.",
    )
    top_n: int = Field(default=20, ge=1, le=50, description="Top N symbols if no list provided")
    force_regenerate: bool = False


class UpdateStrategyStatusRequest(BaseModel):
    """Request to update strategy status."""

    status: Literal["active", "archived"]
    archive_reason: str | None = Field(default=None, description="Reason for archival")


# ============================================================================
# API Endpoints
# ============================================================================


@router.get("", response_model=dict[str, Any])
async def list_strategies(
    symbol: str | None = Query(None, description="Filter by symbol"),
    status: Literal["testing", "active", "archived"] | None = Query(
        None, description="Filter by status"
    ),
    strategy_type: str | None = Query(None, description="Filter by strategy type"),
    limit: int = Query(50, ge=1, le=200, description="Maximum results"),
) -> dict[str, Any]:
    """List strategies with filtering.

    Args:
        symbol: Filter by symbol (optional)
        status: Filter by status (optional)
        strategy_type: Filter by strategy type (optional)
        limit: Maximum results (default 50)

    Returns:
        Dict with strategies list and total count
    """
    try:
        storage = get_strategy_storage()
        strategies = storage.list_strategies(
            symbol=symbol,
            status=status,
            strategy_type=strategy_type,
            limit=limit,
        )

        # Convert to list items (summary view) with performance variance
        items = []
        for s in strategies:
            expected = parse_float(s.expected_sharpe)
            live = parse_float(s.live_sharpe_ratio)

            # Calculate performance variance using shared utility
            variance, flag = calculate_performance_status(expected, live, s.live_trades_count)

            items.append(
                StrategyListItem(
                    id=s.id,
                    name=s.name,
                    symbol=s.symbol,
                    strategy_type=s.strategy_type,
                    status=s.status,
                    version=s.version,
                    expected_sharpe=expected,
                    live_sharpe_ratio=live,
                    live_win_rate=parse_float(s.live_win_rate),
                    trades_count=s.live_trades_count,
                    created_at=format_db_date(s.created_at) or "",
                    activation_date=format_db_date(s.activation_date),
                    performance_variance=variance,
                    performance_flag=flag,
                ).model_dump()
            )

        return {
            "strategies": items,
            "total": len(items),
        }

    except Exception as e:
        logger.exception("Failed to list strategies", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to list strategies: {e!s}") from e


class StrategySummary(BaseModel):
    """Summary statistics for strategies."""

    total: int
    active: int
    testing: int
    archived: int
    avg_expected_sharpe: float | None
    avg_live_sharpe: float | None
    total_trades: int
    exceeding_count: int
    meeting_count: int
    underperforming_count: int


@router.get("/summary", response_model=StrategySummary)
async def get_strategy_summary() -> StrategySummary:
    """Get strategy summary statistics.

    Returns:
        Summary with counts by status and average performance metrics
    """
    try:
        storage = get_strategy_storage()
        strategies = storage.list_strategies(limit=500)

        total = len(strategies)
        active = sum(1 for s in strategies if s.status == "active")
        testing = sum(1 for s in strategies if s.status == "testing")
        archived = sum(1 for s in strategies if s.status == "archived")

        # Average expected Sharpe (excluding nulls)
        expected_sharpes = [float(s.expected_sharpe) for s in strategies if s.expected_sharpe]
        avg_expected = sum(expected_sharpes) / len(expected_sharpes) if expected_sharpes else None

        # Average live Sharpe (excluding nulls)
        live_sharpes = [float(s.live_sharpe_ratio) for s in strategies if s.live_sharpe_ratio]
        avg_live = sum(live_sharpes) / len(live_sharpes) if live_sharpes else None

        # Total trades
        total_trades = sum(s.live_trades_count for s in strategies)

        # Performance flags using shared utility
        exceeding = 0
        meeting = 0
        underperforming = 0

        for s in strategies:
            expected = parse_float(s.expected_sharpe)
            live = parse_float(s.live_sharpe_ratio)
            _, flag = calculate_performance_status(expected, live, s.live_trades_count)
            if flag == "exceeding":
                exceeding += 1
            elif flag == "meeting":
                meeting += 1
            elif flag == "underperforming":
                underperforming += 1

        return StrategySummary(
            total=total,
            active=active,
            testing=testing,
            archived=archived,
            avg_expected_sharpe=round(avg_expected, 2) if avg_expected else None,
            avg_live_sharpe=round(avg_live, 2) if avg_live else None,
            total_trades=total_trades,
            exceeding_count=exceeding,
            meeting_count=meeting,
            underperforming_count=underperforming,
        )

    except Exception as e:
        logger.exception("Failed to get strategy summary", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get strategy summary: {e!s}") from e


@router.get("/{strategy_id}", response_model=StrategyDetail)
async def get_strategy(strategy_id: str) -> StrategyDetail:
    """Get strategy details with full configuration.

    Args:
        strategy_id: Strategy UUID

    Returns:
        Complete strategy details including parameters and performance history
    """
    try:
        strategy = _get_strategy_or_404(strategy_id)
        storage = get_strategy_storage()

        # Get performance history (last 30 days)
        perf_data = storage.get_performance_history(strategy_id, limit=30)

        # Format dates and parse floats
        performance_history = []
        for row in perf_data:
            performance_history.append(
                {
                    "date": format_db_date(row["date"]),
                    "trades_30d": row["trades_30d"],
                    "win_rate_30d": parse_float(row["win_rate_30d"]),
                    "sharpe_ratio_30d": parse_float(row["sharpe_ratio_30d"]),
                    "max_drawdown_30d": parse_float(row["max_drawdown_30d"]),
                    "status": row["status"],
                }
            )

        # Ensure backtest_metrics is a list (stored as JSON, might be dict)
        backtest_metrics: dict[str, Any] | list[dict[str, Any]] = strategy.backtest_metrics
        if isinstance(backtest_metrics, dict):
            # If stored as dict, convert to list for API response
            backtest_metrics_list: list[dict[str, Any]] = [backtest_metrics]
        else:
            backtest_metrics_list = backtest_metrics

        return StrategyDetail(
            id=strategy.id,
            name=strategy.name,
            symbol=strategy.symbol,
            strategy_type=strategy.strategy_type,
            parameters=strategy.parameters,
            research_summary=strategy.research_summary,
            generation_reasoning=strategy.generation_reasoning,
            backtest_metrics=backtest_metrics_list,
            expected_sharpe=parse_float(strategy.expected_sharpe),
            expected_win_rate=parse_float(strategy.expected_win_rate),
            expected_max_drawdown=parse_float(strategy.expected_max_drawdown),
            live_trades_count=strategy.live_trades_count,
            live_win_rate=parse_float(strategy.live_win_rate),
            live_sharpe_ratio=parse_float(strategy.live_sharpe_ratio),
            status=strategy.status,
            version=strategy.version,
            created_at=format_db_date(strategy.created_at) or "",
            activation_date=format_db_date(strategy.activation_date),
            archive_date=format_db_date(strategy.archive_date),
            archive_reason=strategy.archive_reason,
            performance_history=performance_history,
        )

    except Exception as e:
        logger.exception("Failed to get strategy", strategy_id=strategy_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get strategy: {e!s}") from e


@router.post("/generate", response_model=dict[str, Any])
async def generate_strategy(request: GenerateStrategyRequest) -> dict[str, Any]:
    """Trigger strategy generation for symbol.

    Args:
        request: Generation request with symbol and force flag

    Returns:
        Workflow result with status and strategy_id (if successful)
    """
    try:
        logger.info(
            "Triggering strategy generation",
            symbol=request.symbol,
            force=request.force_regenerate,
        )

        # Trigger workflow (synchronous for now, can be async Hatchet workflow later)
        result = await strategy_research_workflow(
            symbol=request.symbol,
            force_regenerate=request.force_regenerate,
        )

        return result

    except Exception as e:
        logger.exception(
            "Strategy generation failed",
            symbol=request.symbol,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=f"Strategy generation failed: {e!s}") from e


@router.post("/generate-batch", response_model=dict[str, Any])
async def generate_batch(request: GenerateBatchRequest) -> dict[str, Any]:
    """Trigger batch strategy generation for multiple symbols.

    Args:
        request: Batch generation request with symbols or top_n

    Returns:
        Summary with task_id for async monitoring
    """
    try:
        # If specific symbols provided, we run synchronously for each
        if request.symbols:
            symbols = request.symbols
            logger.info(
                "Triggering batch strategy generation",
                symbols=symbols,
                force=request.force_regenerate,
            )
            results: list[dict[str, str | None]] = []

            for symbol in symbols:
                try:
                    result = await strategy_research_workflow(
                        symbol=symbol,
                        force_regenerate=request.force_regenerate,
                    )
                    results.append(
                        {
                            "symbol": symbol,
                            "status": result.get("status", "unknown"),
                            "strategy_id": result.get("strategy_id"),
                            "message": result.get("message"),
                        }
                    )
                except Exception as e:
                    results.append(
                        {
                            "symbol": symbol,
                            "status": "failed",
                            "strategy_id": None,
                            "message": str(e),
                        }
                    )

            generated = sum(1 for r in results if r["status"] == "completed")
            return {
                "status": "completed",
                "symbols_processed": len(results),
                "strategies_generated": generated,
                "results": results,
            }

        # Otherwise use top N from watchlist - trigger generation task
        logger.info(
            "Triggering weekly strategy generation",
            top_n=request.top_n,
            force=request.force_regenerate,
        )

        # For now, run synchronously since the task is already sync
        # In future can make this async with task()
        gen_result = weekly_strategy_generation()

        return {
            "status": "completed",
            "symbols_evaluated": gen_result.get("symbols_evaluated", 0),
            "strategies_generated": gen_result.get("strategies_generated", 0),
            "details": gen_result.get("details", []),
        }

    except Exception as e:
        logger.exception("Batch strategy generation failed", error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Batch strategy generation failed: {e!s}"
        ) from e


@router.patch("/{strategy_id}", response_model=dict[str, Any])
async def update_strategy_status(
    strategy_id: str,
    request: UpdateStrategyStatusRequest,
) -> dict[str, Any]:
    """Update strategy status (activate or archive).

    Args:
        strategy_id: Strategy UUID
        request: Status update request

    Returns:
        Updated strategy summary
    """
    try:
        strategy = _get_strategy_or_404(strategy_id)
        storage = get_strategy_storage()

        if request.status == "active":
            storage.activate_strategy(strategy_id)
            logger.info("Strategy activated", strategy_id=strategy_id)
            message = f"Strategy {strategy.name} activated"
        else:  # archived
            reason = request.archive_reason or "Manual archival via API"
            storage.archive_strategy(strategy_id, reason)
            logger.info("Strategy archived", strategy_id=strategy_id, reason=reason)
            message = f"Strategy {strategy.name} archived"

        # Get updated strategy
        updated = storage.get_strategy_by_id(strategy_id)
        if not updated:
            raise HTTPException(status_code=500, detail="Failed to retrieve updated strategy")

        return {
            "strategy": {
                "id": updated.id,
                "name": updated.name,
                "symbol": updated.symbol,
                "status": updated.status,
                "version": updated.version,
            },
            "message": message,
        }

    except Exception as e:
        logger.exception("Failed to update strategy status", strategy_id=strategy_id, error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to update strategy status: {e!s}"
        ) from e


@router.get("/{strategy_id}/performance", response_model=dict[str, Any])
async def get_strategy_performance(strategy_id: str) -> dict[str, Any]:
    """Get performance comparison (backtest vs live).

    Args:
        strategy_id: Strategy UUID

    Returns:
        Performance comparison with expected vs actual metrics
    """
    try:
        strategy = _get_strategy_or_404(strategy_id)

        # Calculate performance using shared utility
        expected_sharpe = parse_float(strategy.expected_sharpe)
        actual_sharpe = parse_float(strategy.live_sharpe_ratio)
        performance_ratio, flag = calculate_performance_status(
            expected_sharpe, actual_sharpe, strategy.live_trades_count
        )

        # Map flag to status string for backward compatibility
        status = map_performance_flag_to_status(flag)

        return {
            "expected": {
                "sharpe": expected_sharpe or 0.0,
                "win_rate": parse_float(strategy.expected_win_rate),
                "max_drawdown": parse_float(strategy.expected_max_drawdown),
            },
            "actual_30d": {
                "sharpe": actual_sharpe or 0.0,
                "win_rate": parse_float(strategy.live_win_rate),
                "trades_count": strategy.live_trades_count,
            },
            "performance_ratio": performance_ratio or 0.0,
            "status": status,
        }

    except Exception as e:
        logger.exception(
            "Failed to get strategy performance", strategy_id=strategy_id, error=str(e)
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to get strategy performance: {e!s}"
        ) from e


@router.get("/{strategy_id}/signal", response_model=dict[str, Any])
async def get_strategy_signal(strategy_id: str) -> dict[str, Any]:
    """Get current trading signal for a strategy.

    Args:
        strategy_id: Strategy UUID

    Returns:
        Current signal with type, strength, reasons, and timestamp
    """
    try:
        strategy = _get_strategy_or_404(strategy_id)

        # Check for stored signal from today
        storage = get_strategy_storage()
        signals = storage.get_strategy_signals(strategy_id, limit=1)

        if signals:
            signal = signals[0]
            return {
                "strategy_id": strategy_id,
                "symbol": strategy.symbol,
                "signal_type": signal["signal_type"],
                "signal_strength": signal["signal_strength"],
                "reasons": signal["reasons"],
                "market_data": signal["market_data"],
                "generated_at": format_db_date(signal["created_at"]),
                "source": "stored",
            }

        # Generate fresh signal if none stored
        signal_data = generate_signal_for_strategy(strategy_id, strategy.symbol)

        if "error" in signal_data:
            raise HTTPException(status_code=400, detail=signal_data["error"])

        signal_data["source"] = "generated"
        return signal_data

    except Exception as e:
        logger.exception("Failed to get strategy signal", strategy_id=strategy_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get strategy signal: {e!s}") from e


@router.post("/{strategy_id}/signal/generate", response_model=dict[str, Any])
async def generate_strategy_signal(strategy_id: str) -> dict[str, Any]:
    """Force generate a new signal for a strategy (ignores stored signals).

    Args:
        strategy_id: Strategy UUID

    Returns:
        Newly generated signal
    """
    try:
        strategy = _get_strategy_or_404(strategy_id)

        # Generate fresh signal
        signal_data = generate_signal_for_strategy(strategy_id, strategy.symbol)

        if "error" in signal_data:
            raise HTTPException(status_code=400, detail=signal_data["error"])

        # Store the signal
        storage = get_strategy_storage()
        signal_id = storage.store_signal(signal_data)

        signal_data["signal_id"] = signal_id
        signal_data["source"] = "generated"
        return signal_data

    except Exception as e:
        logger.exception(
            "Failed to generate strategy signal", strategy_id=strategy_id, error=str(e)
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to generate strategy signal: {e!s}"
        ) from e


@router.get("/{strategy_id}/evolution", response_model=dict[str, Any])
async def get_strategy_evolution(strategy_id: str) -> dict[str, Any]:
    """Get the full evolution timeline for a strategy.

    Shows: Seed -> Backtest -> Strategy -> Signals -> Trades -> Performance
    """
    try:
        strategy = _get_strategy_or_404(strategy_id)
        storage = get_strategy_storage()

        # Get seed info if strategy originated from a seed
        seed_raw = storage.get_seed_by_strategy_id(strategy_id)
        seed_info = None
        if seed_raw:
            seed_info = {
                "id": seed_raw["id"],
                "thesis": seed_raw["thesis"],
                "confidence": seed_raw["confidence"],
                "created_at": format_db_date(seed_raw["created_at"]),
            }

        # Get backtest runs for this strategy
        backtests_raw = storage.get_backtest_runs(strategy_id, limit=5)
        backtests = [
            {
                **bt,
                "start_date": format_db_date(bt["start_date"]),
                "end_date": format_db_date(bt["end_date"]),
                "created_at": format_db_date(bt["created_at"]),
            }
            for bt in backtests_raw
        ]

        # Get recent signals
        signals_raw = storage.get_strategy_signals(strategy_id, limit=10)
        signals = [
            {
                **sig,
                "signal_date": format_db_date(sig["signal_date"]),
                "created_at": format_db_date(sig["created_at"]),
            }
            for sig in signals_raw
        ]

        # Get recent trades (paper trades linked to this strategy)
        trades_raw = storage.get_symbol_trades(strategy.symbol, limit=10)
        trades = [
            {
                **trade,
                "entry_date": format_db_date(trade["entry_date"]),
            }
            for trade in trades_raw
        ]

        return {
            "strategy_id": strategy_id,
            "name": strategy.name,
            "symbol": strategy.symbol,
            "status": strategy.status,
            "seed": seed_info,
            "backtests": backtests,
            "signals": signals,
            "trades": trades,
            "performance": {
                "expected_sharpe": parse_float(strategy.expected_sharpe),
                "live_sharpe": parse_float(strategy.live_sharpe_ratio),
                "live_win_rate": parse_float(strategy.live_win_rate),
                "total_trades": strategy.live_trades_count or 0,
            },
        }

    except Exception as e:
        logger.exception("Failed to get strategy evolution", strategy_id=strategy_id, error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to get strategy evolution: {e!s}"
        ) from e
