"""Strategy generation API endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.agents.workflows.strategy_research_workflow import strategy_research_workflow
from app.logging_config import get_logger
from app.tasks.strategy.generation_tasks import weekly_strategy_generation

from .strategies_models import GenerateBatchRequest, GenerateStrategyRequest

logger = get_logger(__name__)


async def handle_generate_strategy(request: GenerateStrategyRequest) -> dict[str, Any]:
    """Trigger strategy generation for a single symbol."""
    try:
        logger.info(
            "Triggering strategy generation",
            symbol=request.symbol,
            force=request.force_regenerate,
        )
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


async def _run_batch_for_symbols(
    symbols: list[str], force_regenerate: bool
) -> dict[str, Any]:
    """Run generation for explicit list of symbols."""
    logger.info(
        "Triggering batch strategy generation",
        symbols=symbols,
        force=force_regenerate,
    )
    results: list[dict[str, str | None]] = []
    for symbol in symbols:
        try:
            result = await strategy_research_workflow(
                symbol=symbol,
                force_regenerate=force_regenerate,
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


def _run_weekly_generation(top_n: int, force_regenerate: bool) -> dict[str, Any]:
    """Run weekly generation for top N watchlist symbols."""
    logger.info(
        "Triggering weekly strategy generation",
        top_n=top_n,
        force=force_regenerate,
    )
    gen_result = weekly_strategy_generation()
    return {
        "status": "completed",
        "symbols_evaluated": gen_result.get("symbols_evaluated", 0),
        "strategies_generated": gen_result.get("strategies_generated", 0),
        "details": gen_result.get("details", []),
    }


async def handle_generate_batch(request: GenerateBatchRequest) -> dict[str, Any]:
    """Trigger batch strategy generation for multiple symbols."""
    try:
        if request.symbols:
            return await _run_batch_for_symbols(request.symbols, request.force_regenerate)
        return _run_weekly_generation(request.top_n, request.force_regenerate)
    except Exception as e:
        logger.exception("Batch strategy generation failed", error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Batch strategy generation failed: {e!s}"
        ) from e
