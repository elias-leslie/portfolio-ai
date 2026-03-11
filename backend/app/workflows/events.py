"""Event dispatch system (replaces app/tasks/triggers.py).

Routes domain events to the appropriate Hatchet workflows.
Provides both async and sync entry points.
"""

from __future__ import annotations

import asyncio
from typing import Any

from hatchet_sdk import ConcurrencyExpression, ConcurrencyLimitStrategy, Context

from ..hatchet_app import hatchet
from ..logging_config import get_logger
from .models import InsightInput, SeedInput, SymbolInput

logger = get_logger(__name__)


async def emit_event(event_type: str, payload: dict[str, Any]) -> bool:
    """Emit an event to trigger downstream Hatchet workflows.

    Dispatches events via Hatchet workflows.
    Hatchet's ConcurrencyExpression handles backpressure natively.

    Args:
        event_type: Type of event (e.g., "strategy_performance_updated")
        payload: Event data (symbol, ids, etc.)

    Returns:
        True if event was dispatched, False if skipped
    """
    logger.info("event_emitted", event_type=event_type, payload=payload)

    if event_type == "strategy_performance_updated":
        return await _on_strategy_performance_updated(payload)
    if event_type == "seed_created":
        return await _on_seed_created(payload)
    if event_type == "price_alert_triggered":
        return await _on_price_alert_triggered(payload)
    if event_type == "earnings_released":
        return await _on_earnings_released(payload)
    if event_type == "insight_generated":
        return await _on_insight_generated(payload)
    logger.warning("unknown_event_type", event_type=event_type)
    return False


def emit_event_sync(event_type: str, payload: dict[str, Any]) -> bool:
    """Synchronous wrapper for emit_event.

    For callers in sync code that can't use await.
    Creates a new event loop to dispatch asynchronously.
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(emit_event(event_type, payload))
    finally:
        loop.close()


async def _on_strategy_performance_updated(payload: dict[str, Any]) -> bool:
    from .watchlist import refresh_single_symbol_wf

    symbol = payload.get("symbol")
    if not symbol:
        logger.warning("strategy_performance_event_missing_symbol", payload=payload)
        return False

    await refresh_single_symbol_wf.aio_run_no_wait(SymbolInput(symbol=symbol))
    logger.info(
        "triggered_watchlist_refresh_from_performance",
        symbol=symbol,
        strategy_id=payload.get("strategy_id"),
    )
    return True


async def _on_seed_created(payload: dict[str, Any]) -> bool:
    from .strategy import trigger_from_seed_wf

    seed_id = payload.get("seed_id")
    symbol = payload.get("symbol")
    confidence = payload.get("confidence", 0)

    if not seed_id or not symbol:
        logger.warning("seed_created_event_missing_fields", payload=payload)
        return False

    if confidence >= 7:
        await trigger_from_seed_wf.aio_run_no_wait(SeedInput(seed_id=seed_id, symbol=symbol))
        logger.info(
            "triggered_strategy_from_seed_event",
            seed_id=seed_id,
            symbol=symbol,
            confidence=confidence,
        )
        return True

    logger.debug("seed_confidence_too_low", seed_id=seed_id, symbol=symbol, confidence=confidence)
    return False


async def _on_price_alert_triggered(payload: dict[str, Any]) -> bool:
    from .strategy import generate_signal_wf
    from .watchlist import refresh_single_symbol_wf

    symbol = payload.get("symbol")
    if not symbol:
        logger.warning("price_alert_event_missing_symbol", payload=payload)
        return False

    await refresh_single_symbol_wf.aio_run_no_wait(SymbolInput(symbol=symbol))
    await generate_signal_wf.aio_run_no_wait(
        SymbolInput(symbol=symbol)
    )
    logger.info(
        "triggered_from_price_alert",
        symbol=symbol,
        alert_type=payload.get("alert_type"),
        price=payload.get("price"),
    )
    return True


async def _on_earnings_released(payload: dict[str, Any]) -> bool:
    from .strategy import generate_signal_wf
    from .watchlist import refresh_single_symbol_wf

    symbol = payload.get("symbol")
    if not symbol:
        logger.warning("earnings_released_event_missing_symbol", payload=payload)
        return False

    await refresh_single_symbol_wf.aio_run_no_wait(SymbolInput(symbol=symbol))
    await generate_signal_wf.aio_run_no_wait(
        SymbolInput(symbol=symbol)
    )
    logger.info(
        "triggered_from_earnings_release",
        symbol=symbol,
        earnings_date=payload.get("earnings_date"),
    )
    return True


async def _on_insight_generated(payload: dict[str, Any]) -> bool:
    output = payload.get("output")
    if not output:
        logger.warning("insight_generated_event_missing_output", payload_keys=list(payload.keys()))
        return False

    await cross_validate_insight_wf.aio_run_no_wait(
        InsightInput(
            output=output,
            context_type=payload.get("context_type", "insight"),
            symbol=payload.get("symbol"),
            confidence=payload.get("confidence"),
        )
    )
    logger.info(
        "triggered_cross_validation_from_insight",
        context_type=payload.get("context_type"),
        symbol=payload.get("symbol"),
        output_length=len(output),
    )
    return True


@hatchet.task(
    name="portfolio-cross-validate-insight",
    input_validator=InsightInput,
    execution_timeout="600s",
    retries=1,
    concurrency=ConcurrencyExpression(
        expression="'portfolio-cross-validate-insight'",
        max_runs=3,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def cross_validate_insight_wf(input: InsightInput, ctx: Context) -> dict[str, Any]:
    from ..services.cross_validation import CrossValidationService

    def _validate() -> dict[str, Any]:
        service = CrossValidationService()
        result = service.validate(
            generator_output=input.output,
            context_type=input.context_type,
            context_symbol=input.symbol,
            generator_confidence=input.confidence,
        )
        return {
            "status": "completed",
            "validation_id": result.id,
            "approved": result.validator_approved,
            "has_disagreement": result.has_disagreement,
        }

    return await asyncio.to_thread(_validate)
