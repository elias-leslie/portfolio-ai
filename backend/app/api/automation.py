"""Automation API endpoints for triggering trading pipeline stages.

Provides manual triggers for:
- Strategy research/generation
- Signal generation
- Auto paper trading
- Full pipeline run
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.hatchet_app import get_hatchet
from app.logging_config import get_logger
from app.storage.connection import get_connection_manager

logger = get_logger(__name__)

router = APIRouter(prefix="/api/automation", tags=["automation"])


class PipelineStageRequest(BaseModel):
    """Request model for triggering a pipeline stage."""

    symbol: str | None = Field(None, description="Specific symbol (optional)")
    force: bool = Field(False, description="Force regeneration even if strategy exists")


class PipelineResponse(BaseModel):
    """Response model for pipeline trigger."""

    status: str
    task_id: str | None = None
    stage: str
    message: str


class PipelineStatusResponse(BaseModel):
    """Response model for pipeline status."""

    stages: dict[str, dict[str, Any]]
    last_run: dict[str, str | None]


# ============================================================================
# Endpoints
# ============================================================================


@router.post("/run/strategy-research", response_model=PipelineResponse)
async def trigger_strategy_research(
    symbol: str | None = Query(None, description="Specific symbol to research"),
    force: bool = Query(False, description="Force regeneration"),
) -> PipelineResponse:
    """Trigger strategy research workflow.

    If symbol provided, runs for that symbol only.
    Otherwise runs daily_strategy_refresh for top watchlist symbols.
    """
    try:
        hatchet = get_hatchet()
        if symbol:
            workflow_run = hatchet.admin.run_workflow(
                "portfolio-strategy-research-symbol",
                {"symbol": symbol, "force": force},
            )
            message = f"Started strategy research for {symbol}"
        else:
            workflow_run = hatchet.admin.run_workflow(
                "portfolio-daily-strategy",
                {},
            )
            message = "Started strategy research for top 5 watchlist symbols"

        logger.info("strategy_research_triggered", symbol=symbol, task_id=workflow_run.workflow_run_id)

        return PipelineResponse(
            status="started",
            task_id=workflow_run.workflow_run_id,
            stage="strategy_research",
            message=message,
        )

    except Exception as e:
        logger.exception("strategy_research_trigger_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/run/signal-generation", response_model=PipelineResponse)
async def trigger_signal_generation() -> PipelineResponse:
    """Trigger signal generation for all active strategies."""
    try:
        hatchet = get_hatchet()
        workflow_run = hatchet.admin.run_workflow(
            "portfolio-daily-signals",
            {},
        )

        logger.info("signal_generation_triggered", task_id=workflow_run.workflow_run_id)

        return PipelineResponse(
            status="started",
            task_id=workflow_run.workflow_run_id,
            stage="signal_generation",
            message="Started signal generation for all active strategies",
        )

    except Exception as e:
        logger.exception("signal_generation_trigger_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/run/auto-paper-trade", response_model=PipelineResponse)
async def trigger_auto_paper_trade(
    min_strength: int = Query(5, ge=1, le=10, description="Minimum signal strength"),
) -> PipelineResponse:
    """Trigger auto paper trading from signals."""
    try:
        hatchet = get_hatchet()
        workflow_run = hatchet.admin.run_workflow(
            "portfolio-auto-paper-trade",
            {"min_signal_strength": min_strength},
        )

        logger.info("auto_paper_trade_triggered", task_id=workflow_run.workflow_run_id, min_strength=min_strength)

        return PipelineResponse(
            status="started",
            task_id=workflow_run.workflow_run_id,
            stage="auto_paper_trade",
            message=f"Started auto paper trading (min strength: {min_strength})",
        )

    except Exception as e:
        logger.exception("auto_paper_trade_trigger_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/run/full-pipeline", response_model=dict[str, Any])
async def trigger_full_pipeline(
    skip_research: bool = Query(False, description="Skip strategy research stage"),
) -> dict[str, Any]:
    """Trigger full trading pipeline.

    Stages:
    1. Strategy research (optional, can skip if strategies exist)
    2. Signal generation
    3. Auto paper trading

    Each stage runs as a separate Hatchet workflow.
    """
    try:
        hatchet = get_hatchet()
        tasks = {}

        # Stage 1: Strategy research (optional)
        if not skip_research:
            run1 = hatchet.admin.run_workflow("portfolio-daily-strategy", {})
            tasks["strategy_research"] = {
                "task_id": run1.workflow_run_id,
                "status": "started",
            }

        # Stage 2: Signal generation
        run2 = hatchet.admin.run_workflow("portfolio-daily-signals", {})
        tasks["signal_generation"] = {
            "task_id": run2.workflow_run_id,
            "status": "started",
        }

        # Stage 3: Auto paper trading
        run3 = hatchet.admin.run_workflow("portfolio-auto-paper-trade", {})
        tasks["auto_paper_trade"] = {
            "task_id": run3.workflow_run_id,
            "status": "started",
        }

        logger.info(
            "full_pipeline_triggered",
            stages=list(tasks.keys()),
            skip_research=skip_research,
        )

        return {
            "status": "started",
            "message": f"Started {len(tasks)} pipeline stages",
            "stages": tasks,
        }

    except Exception as e:
        logger.exception("full_pipeline_trigger_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/status", response_model=PipelineStatusResponse)
async def get_pipeline_status() -> PipelineStatusResponse:
    """Get current pipeline status and last run times."""
    try:
        conn_mgr = get_connection_manager()

        with conn_mgr.connection() as conn:
            # Get active strategy count
            active_strategies = conn.execute(
                "SELECT COUNT(*) FROM strategy_definitions WHERE status = 'active'"
            ).fetchone()

            # Get today's signals
            today_signals = conn.execute(
                """
                SELECT COUNT(*) FROM strategy_signals
                WHERE signal_date = CURRENT_DATE
                """
            ).fetchone()

            # Get open paper trades
            open_trades = conn.execute(
                "SELECT COUNT(*) FROM idea_outcomes WHERE status = 'open'"
            ).fetchone()

            # Get last backtest run
            last_backtest = conn.execute("SELECT MAX(created_at) FROM backtest_runs").fetchone()

        # Handle last_backtest datetime conversion
        last_backtest_str = None
        if last_backtest and last_backtest[0] is not None:
            backtest_obj = last_backtest[0]
            if hasattr(backtest_obj, "isoformat"):
                last_backtest_str = backtest_obj.isoformat()

        return PipelineStatusResponse(
            stages={
                "strategies": {
                    "active_count": active_strategies[0] if active_strategies else 0,
                },
                "signals": {
                    "today_count": today_signals[0] if today_signals else 0,
                },
                "paper_trades": {
                    "open_count": open_trades[0] if open_trades else 0,
                },
            },
            last_run={
                "backtest": last_backtest_str,
            },
        )

    except Exception as e:
        logger.exception("pipeline_status_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e
