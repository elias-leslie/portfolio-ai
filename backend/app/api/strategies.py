"""API endpoints for strategy management.

Provides REST API for:
- Listing strategies with filtering
- Getting strategy details
- Triggering strategy generation
- Updating strategy status (activate/archive)
- Viewing performance comparison
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.agents.workflows.strategy_research_workflow import strategy_research_workflow
from app.logging_config import get_logger
from app.storage.connection import get_connection_manager
from app.strategies.performance_utils import calculate_performance_status
from app.strategies.storage import get_strategy_storage
from app.tasks.strategy_monitoring_tasks import weekly_strategy_generation
from app.tasks.strategy_signal_tasks import generate_signal_for_strategy, store_signal

logger = get_logger(__name__)

router = APIRouter(prefix="/api/strategies", tags=["strategies"])


# ============================================================================
# Helper Functions
# ============================================================================


def _get_strategy_or_404(strategy_id: str):
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


def _safe_datetime_to_iso(dt: Any) -> str | None:
    """Convert datetime/date to ISO string, handling None and various types.

    Args:
        dt: Datetime, date, or None value

    Returns:
        ISO format string or None
    """
    if dt is None:
        return None
    if isinstance(dt, (datetime, date)):
        return dt.isoformat()
    if hasattr(dt, "isoformat"):
        return dt.isoformat()
    return str(dt)


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
            expected = float(s.expected_sharpe) if s.expected_sharpe else None
            live = float(s.live_sharpe_ratio) if s.live_sharpe_ratio else None

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
                    live_win_rate=float(s.live_win_rate) if s.live_win_rate else None,
                    trades_count=s.live_trades_count,
                    created_at=_safe_datetime_to_iso(s.created_at),
                    activation_date=_safe_datetime_to_iso(s.activation_date),
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
            expected = float(s.expected_sharpe) if s.expected_sharpe else None
            live = float(s.live_sharpe_ratio) if s.live_sharpe_ratio else None
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
        conn_mgr = storage.conn
        with conn_mgr.connection() as conn:
            perf_rows = conn.execute(
                """
                SELECT date, trades_30d, win_rate_30d, sharpe_ratio_30d, max_drawdown_30d, status
                FROM strategy_performance
                WHERE strategy_id = %s
                ORDER BY date DESC
                LIMIT 30
                """,
                (strategy_id,),
            ).fetchall()

        # Convert tuples to dicts for easy access
        # Database returns tuples, map them to column names
        performance_history = []
        for row in perf_rows:
            # row is a tuple: (date, trades_30d, win_rate_30d, sharpe_ratio_30d, max_drawdown_30d, status)
            date_val = row[0]
            if isinstance(date_val, datetime):
                date_iso = date_val.isoformat()
            else:
                date_iso = str(date_val)

            performance_history.append(
                {
                    "date": date_iso,
                    "trades_30d": row[1],
                    "win_rate_30d": float(row[2]) if row[2] is not None else None,
                    "sharpe_ratio_30d": float(row[3]) if row[3] is not None else None,
                    "max_drawdown_30d": float(row[4]) if row[4] is not None else None,
                    "status": row[5],
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
            expected_sharpe=float(strategy.expected_sharpe) if strategy.expected_sharpe else None,
            expected_win_rate=float(strategy.expected_win_rate)
            if strategy.expected_win_rate
            else None,
            expected_max_drawdown=float(strategy.expected_max_drawdown)
            if strategy.expected_max_drawdown
            else None,
            live_trades_count=strategy.live_trades_count,
            live_win_rate=float(strategy.live_win_rate) if strategy.live_win_rate else None,
            live_sharpe_ratio=float(strategy.live_sharpe_ratio)
            if strategy.live_sharpe_ratio
            else None,
            status=strategy.status,
            version=strategy.version,
            created_at=strategy.created_at.isoformat(),
            activation_date=strategy.activation_date.isoformat()
            if strategy.activation_date
            else None,
            archive_date=strategy.archive_date.isoformat() if strategy.archive_date else None,
            archive_reason=strategy.archive_reason,
            performance_history=performance_history,
        )

    except HTTPException:
        raise
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

        # Trigger workflow (synchronous for now, can be async Celery task later)
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

        # Otherwise use top N from watchlist - trigger Celery task
        logger.info(
            "Triggering weekly strategy generation",
            top_n=request.top_n,
            force=request.force_regenerate,
        )

        # For now, run synchronously since the Celery task is already sync
        # In future can make this async with task.delay()
        result = weekly_strategy_generation()

        return {
            "status": "completed",
            "symbols_evaluated": result.get("symbols_evaluated", 0),
            "strategies_generated": result.get("strategies_generated", 0),
            "details": result.get("details", []),
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

    except HTTPException:
        raise
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

        # Calculate performance ratio
        expected_sharpe = float(strategy.expected_sharpe or 0.0)
        actual_sharpe = float(strategy.live_sharpe_ratio or 0.0)
        performance_ratio = actual_sharpe / expected_sharpe if expected_sharpe > 0 else 0.0

        # Determine status
        if strategy.live_trades_count == 0:
            status = "no_live_data"
        elif performance_ratio >= 0.9:
            status = "exceeding_expectations"
        elif performance_ratio >= 0.7:
            status = "meeting_expectations"
        else:
            status = "underperforming"

        return {
            "expected": {
                "sharpe": expected_sharpe,
                "win_rate": float(strategy.expected_win_rate)
                if strategy.expected_win_rate
                else None,
                "max_drawdown": float(strategy.expected_max_drawdown)
                if strategy.expected_max_drawdown
                else None,
            },
            "actual_30d": {
                "sharpe": actual_sharpe,
                "win_rate": float(strategy.live_win_rate) if strategy.live_win_rate else None,
                "trades_count": strategy.live_trades_count,
            },
            "performance_ratio": performance_ratio,
            "status": status,
        }

    except HTTPException:
        raise
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
        conn_mgr = get_connection_manager()
        with conn_mgr.connection() as conn:
            result = conn.execute(
                """
                SELECT signal_type, signal_strength, reasons, market_data, created_at
                FROM strategy_signals
                WHERE strategy_id = %s
                ORDER BY signal_date DESC
                LIMIT 1
                """,
                (strategy_id,),
            ).fetchone()

        if result:
            generated_at_obj = result[4]
            generated_at_str = None
            if generated_at_obj is not None and hasattr(generated_at_obj, "isoformat"):
                generated_at_str = generated_at_obj.isoformat()

            return {
                "strategy_id": strategy_id,
                "symbol": strategy.symbol,
                "signal_type": result[0],
                "signal_strength": result[1],
                "reasons": result[2] or [],
                "market_data": result[3] or {},
                "generated_at": generated_at_str,
                "source": "stored",
            }

        # Generate fresh signal if none stored
        signal_data = generate_signal_for_strategy(strategy_id, strategy.symbol)

        if "error" in signal_data:
            raise HTTPException(status_code=400, detail=signal_data["error"])

        signal_data["source"] = "generated"
        return signal_data

    except HTTPException:
        raise
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
        conn_mgr = get_connection_manager()
        with conn_mgr.connection() as conn:
            signal_id = store_signal(conn, signal_data)
            conn.commit()

        signal_data["signal_id"] = signal_id
        signal_data["source"] = "generated"
        return signal_data

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "Failed to generate strategy signal", strategy_id=strategy_id, error=str(e)
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to generate strategy signal: {e!s}"
        ) from e


# ============================================================================
# Strategy Seeds Endpoints (separate router to avoid path conflicts)
# ============================================================================

seeds_router = APIRouter(prefix="/api/strategy-seeds", tags=["strategy-seeds"])


class StrategySeedItem(BaseModel):
    """Strategy seed item."""

    id: str
    symbol: str
    thesis: str
    confidence: float
    status: Literal["pending", "processing", "converted", "rejected"]
    strategy_id: str | None = None
    created_at: str
    processed_at: str | None = None


class StrategySeedList(BaseModel):
    """List of strategy seeds."""

    seeds: list[StrategySeedItem]
    total: int


@seeds_router.get("/", response_model=StrategySeedList)
async def list_strategy_seeds(
    status: str | None = Query(default=None, description="Filter by status"),
    symbol: str | None = Query(default=None, description="Filter by symbol"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> StrategySeedList:
    """List strategy seeds with optional filtering.

    Seeds are AI-generated investment ideas that can evolve into strategies.
    High-confidence seeds (>=7/10) automatically trigger strategy workflows.
    """
    try:
        conn_mgr = get_connection_manager()
        with conn_mgr.connection() as conn:
            # Build query with filters
            conditions = []
            params: list[Any] = []

            if status:
                conditions.append(f"status = ${len(params) + 1}")
                params.append(status)
            if symbol:
                conditions.append(f"symbol = ${len(params) + 1}")
                params.append(symbol.upper())

            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

            # Get total count
            count_query = f"SELECT COUNT(*) FROM strategy_seeds {where_clause}"
            count_row = conn.execute(count_query, params).fetchone()
            total_val = count_row[0] if count_row else 0
            total = int(total_val) if isinstance(total_val, (int, float, str)) else 0

            # Get seeds with pagination
            query = f"""
                SELECT id, symbol, thesis, confidence, status, strategy_id,
                       created_at, processed_at
                FROM strategy_seeds
                {where_clause}
                ORDER BY created_at DESC
                LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}
            """
            params.extend([limit, offset])
            rows = conn.execute(query, params).fetchall()

            seeds = []
            for row in rows:
                created = row[6]
                processed = row[7]
                created_str = (
                    created.isoformat() if isinstance(created, datetime) else str(created or "")
                )
                processed_str = processed.isoformat() if isinstance(processed, datetime) else None
                seeds.append(
                    StrategySeedItem(
                        id=str(row[0]),
                        symbol=str(row[1]),
                        thesis=str(row[2]),
                        confidence=float(row[3]) if row[3] is not None else 0.0,
                        status=str(row[4]),  # type: ignore[arg-type]
                        strategy_id=str(row[5]) if row[5] else None,
                        created_at=created_str,
                        processed_at=processed_str,
                    )
                )

            return StrategySeedList(seeds=seeds, total=total)

    except Exception as e:
        logger.exception("Failed to list strategy seeds", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to list strategy seeds: {e!s}") from e


@seeds_router.get("/{seed_id}", response_model=StrategySeedItem)
async def get_strategy_seed(seed_id: str) -> StrategySeedItem:
    """Get a specific strategy seed by ID."""
    try:
        conn_mgr = get_connection_manager()
        with conn_mgr.connection() as conn:
            row = conn.execute(
                """
                SELECT id, symbol, thesis, confidence, status, strategy_id,
                       created_at, processed_at
                FROM strategy_seeds
                WHERE id = %s
                """,
                [seed_id],
            ).fetchone()

            if not row:
                raise HTTPException(status_code=404, detail=f"Seed {seed_id} not found")

            created = row[6]
            processed = row[7]
            created_str = (
                created.isoformat() if isinstance(created, datetime) else str(created or "")
            )
            processed_str = processed.isoformat() if isinstance(processed, datetime) else None
            return StrategySeedItem(
                id=str(row[0]),
                symbol=str(row[1]),
                thesis=str(row[2]),
                confidence=float(row[3]) if row[3] is not None else 0.0,
                status=str(row[4]),  # type: ignore[arg-type]
                strategy_id=str(row[5]) if row[5] else None,
                created_at=created_str,
                processed_at=processed_str,
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get strategy seed", seed_id=seed_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get strategy seed: {e!s}") from e


@router.get("/{strategy_id}/evolution", response_model=dict[str, Any])
async def get_strategy_evolution(strategy_id: str) -> dict[str, Any]:
    """Get the full evolution timeline for a strategy.

    Shows: Seed -> Backtest -> Strategy -> Signals -> Trades -> Performance
    """
    try:
        strategy = _get_strategy_or_404(strategy_id)

        conn_mgr = get_connection_manager()
        with conn_mgr.connection() as conn:
            # Get seed info if strategy originated from a seed
            seed_info = None
            seed_row = conn.execute(
                "SELECT id, thesis, confidence, created_at FROM strategy_seeds WHERE strategy_id = %s",
                [strategy_id],
            ).fetchone()
            if seed_row:
                seed_created = seed_row[3]
                seed_created_str = (
                    seed_created.isoformat() if isinstance(seed_created, datetime) else None
                )
                seed_info = {
                    "id": str(seed_row[0]),
                    "thesis": str(seed_row[1]),
                    "confidence": float(seed_row[2]) if seed_row[2] is not None else 0.0,
                    "created_at": seed_created_str,
                }

            # Get backtest runs for this strategy
            backtest_rows = conn.execute(
                """
                SELECT id, start_date, end_date, sharpe_ratio, total_return_pct,
                       max_drawdown_pct, win_rate, num_trades, status, created_at
                FROM backtest_runs
                WHERE strategy_definition_id = %s
                ORDER BY created_at DESC
                LIMIT 5
                """,
                [strategy_id],
            ).fetchall()

            backtests = []
            for row in backtest_rows:
                bt_created = row[9]
                bt_created_str = (
                    bt_created.isoformat() if isinstance(bt_created, datetime) else None
                )
                backtests.append(
                    {
                        "id": str(row[0]),
                        "start_date": str(row[1]) if row[1] else None,
                        "end_date": str(row[2]) if row[2] else None,
                        "sharpe_ratio": float(row[3]) if row[3] is not None else None,
                        "total_return_pct": float(row[4]) if row[4] is not None else None,
                        "max_drawdown_pct": float(row[5]) if row[5] is not None else None,
                        "win_rate": float(row[6]) if row[6] is not None else None,
                        "num_trades": int(row[7]) if row[7] else 0,
                        "status": str(row[8]),
                        "created_at": bt_created_str,
                    }
                )

            # Get recent signals
            signal_rows = conn.execute(
                """
                SELECT id, signal_type, signal_strength, signal_date, reasons, created_at
                FROM strategy_signals
                WHERE strategy_id = %s
                ORDER BY created_at DESC
                LIMIT 10
                """,
                [strategy_id],
            ).fetchall()

            signals: list[dict[str, Any]] = []
            for row in signal_rows:
                sig_created = row[5]
                sig_created_str = (
                    sig_created.isoformat() if isinstance(sig_created, datetime) else None
                )
                sig_date = row[3]
                sig_date_str = (
                    sig_date.isoformat() if isinstance(sig_date, (datetime, date)) else None
                )
                signals.append(
                    {
                        "id": str(row[0]),
                        "signal_type": str(row[1]),
                        "signal_strength": int(row[2]) if row[2] else None,
                        "signal_date": sig_date_str,
                        "reasons": row[4] if row[4] else [],
                        "created_at": sig_created_str,
                    }
                )

            # Get recent trades (paper trades linked to this strategy)
            trade_rows = conn.execute(
                """
                SELECT io.idea_id, io.symbol, io.entry_price, io.exit_price,
                       io.current_return_pct, io.status, io.entry_date
                FROM idea_outcomes io
                WHERE io.symbol = %s
                ORDER BY io.entry_date DESC
                LIMIT 10
                """,
                [strategy.symbol],
            ).fetchall()

            trades = []
            for row in trade_rows:
                entry_date = row[6]
                entry_date_str = str(entry_date) if entry_date else None
                trades.append(
                    {
                        "id": str(row[0]),
                        "symbol": str(row[1]),
                        "entry_price": float(row[2]) if row[2] is not None else None,
                        "exit_price": float(row[3]) if row[3] is not None else None,
                        "return_pct": float(row[4]) if row[4] is not None else None,
                        "status": str(row[5]),
                        "entry_date": entry_date_str,
                    }
                )

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
                    "expected_sharpe": float(strategy.expected_sharpe)
                    if strategy.expected_sharpe
                    else None,
                    "live_sharpe": float(strategy.live_sharpe_ratio)
                    if strategy.live_sharpe_ratio
                    else None,
                    "live_win_rate": float(strategy.live_win_rate)
                    if strategy.live_win_rate
                    else None,
                    "total_trades": strategy.live_trades_count or 0,
                },
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get strategy evolution", strategy_id=strategy_id, error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to get strategy evolution: {e!s}"
        ) from e
