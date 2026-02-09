"""Event-driven task triggers for automation pipeline (auto-003).

This module centralizes event handlers that trigger downstream tasks
when upstream events occur. Replaces some time-based schedules with
event-driven cascades for tighter integration.

Event Types:
- strategy_performance_updated: After daily strategy evaluation
- seed_created: After Discovery Agent stores high-confidence seed
- price_alert_triggered: After price crosses threshold
- earnings_released: After earnings date passes
- insight_generated: After AI generates insight (triggers cross-validation)

Usage:
    from app.tasks.triggers import emit_event

    # After strategy evaluation completes
    emit_event("strategy_performance_updated", {"strategy_id": "...", "symbol": "AAPL"})
"""

from __future__ import annotations

from typing import Any

from app.logging_config import get_logger
from app.services.celery_inspector import should_skip_cascade

logger = get_logger(__name__)


def emit_event(event_type: str, payload: dict[str, Any]) -> bool:
    """Emit an event to trigger downstream tasks.

    Args:
        event_type: Type of event (e.g., "strategy_performance_updated")
        payload: Event data (symbol, ids, etc.)

    Returns:
        True if event was emitted, False if skipped (backpressure)
    """
    # Check backpressure before dispatching
    if should_skip_cascade():
        logger.info(
            "event_skipped_backpressure",
            event_type=event_type,
            payload_keys=list(payload.keys()),
        )
        return False

    logger.info(
        "event_emitted",
        event_type=event_type,
        payload=payload,
    )

    # Route event to appropriate handler
    if event_type == "strategy_performance_updated":
        _on_strategy_performance_updated(payload)
    elif event_type == "seed_created":
        _on_seed_created(payload)
    elif event_type == "price_alert_triggered":
        _on_price_alert_triggered(payload)
    elif event_type == "earnings_released":
        _on_earnings_released(payload)
    elif event_type == "insight_generated":
        _on_insight_generated(payload)
    else:
        logger.warning("unknown_event_type", event_type=event_type)
        return False

    return True


def _on_strategy_performance_updated(payload: dict[str, Any]) -> None:
    """Handle strategy performance update event.

    Triggers:
    - Watchlist score refresh for the symbol (performance_factor pillar update)
    """
    symbol = payload.get("symbol")
    strategy_id = payload.get("strategy_id")

    if not symbol:
        logger.warning("strategy_performance_event_missing_symbol", payload=payload)
        return

    # Trigger watchlist refresh for the specific symbol
    from app.tasks.watchlist_tasks import refresh_single_symbol_scores_task

    refresh_single_symbol_scores_task.delay(symbol)
    logger.info(
        "triggered_watchlist_refresh_from_performance",
        symbol=symbol,
        strategy_id=strategy_id,
    )


def _on_seed_created(payload: dict[str, Any]) -> None:
    """Handle new strategy seed creation event.

    Triggers:
    - Strategy generation if confidence >= 7
    """
    seed_id = payload.get("seed_id")
    symbol = payload.get("symbol")
    confidence = payload.get("confidence", 0)

    if not seed_id or not symbol:
        logger.warning("seed_created_event_missing_fields", payload=payload)
        return

    # Only trigger for high-confidence seeds
    if confidence >= 7:
        from app.tasks.strategy.generation_tasks import (
            trigger_strategy_from_seed,
        )

        trigger_strategy_from_seed.delay(seed_id, symbol)
        logger.info(
            "triggered_strategy_from_seed_event",
            seed_id=seed_id,
            symbol=symbol,
            confidence=confidence,
        )
    else:
        logger.debug(
            "seed_confidence_too_low",
            seed_id=seed_id,
            symbol=symbol,
            confidence=confidence,
        )


def _on_price_alert_triggered(payload: dict[str, Any]) -> None:
    """Handle price alert trigger event.

    Triggers:
    - Immediate watchlist refresh for the symbol
    - Generate signal for symbol's active strategy
    """
    symbol = payload.get("symbol")
    alert_type = payload.get("alert_type")  # "above_threshold" or "below_threshold"
    price = payload.get("price")

    if not symbol:
        logger.warning("price_alert_event_missing_symbol", payload=payload)
        return

    # Trigger watchlist refresh
    from app.tasks.watchlist_tasks import refresh_single_symbol_scores_task

    refresh_single_symbol_scores_task.delay(symbol)

    # Also trigger signal generation if there's an active strategy
    from app.tasks.strategy_signal_tasks import (
        generate_signal_for_strategy_task,
    )

    # This will check for active strategy internally
    generate_signal_for_strategy_task.delay(symbol)

    logger.info(
        "triggered_from_price_alert",
        symbol=symbol,
        alert_type=alert_type,
        price=price,
    )


def _on_earnings_released(payload: dict[str, Any]) -> None:
    """Handle earnings release event.

    Triggers:
    - Strategy signal generation for the symbol
    - Watchlist refresh to update catalyst scores
    """
    symbol = payload.get("symbol")
    earnings_date = payload.get("earnings_date")

    if not symbol:
        logger.warning("earnings_released_event_missing_symbol", payload=payload)
        return

    # Trigger watchlist refresh (catalyst scores may change)
    from app.tasks.watchlist_tasks import refresh_single_symbol_scores_task

    refresh_single_symbol_scores_task.delay(symbol)

    # Trigger signal generation
    from app.tasks.strategy_signal_tasks import (
        generate_signal_for_strategy_task,
    )

    generate_signal_for_strategy_task.delay(symbol)

    logger.info(
        "triggered_from_earnings_release",
        symbol=symbol,
        earnings_date=earnings_date,
    )


def _on_insight_generated(payload: dict[str, Any]) -> None:
    """Handle insight generation event.

    Triggers:
    - Cross-validation of the generated insight (Gemini -> Claude validation)

    Expected payload:
    - output: The generated insight text
    - context_type: Type of insight (e.g., "analysis", "recommendation")
    - symbol: Stock symbol (optional)
    - confidence: Generator's confidence (optional)
    """
    output = payload.get("output")
    context_type = payload.get("context_type", "insight")
    symbol = payload.get("symbol")
    confidence = payload.get("confidence")

    if not output:
        logger.warning("insight_generated_event_missing_output", payload_keys=list(payload.keys()))
        return

    # Trigger cross-validation asynchronously
    cross_validate_insight_task.delay(
        output=output,
        context_type=context_type,
        symbol=symbol,
        confidence=confidence,
    )
    logger.info(
        "triggered_cross_validation_from_insight",
        context_type=context_type,
        symbol=symbol,
        output_length=len(output),
    )


def cross_validate_insight_task(
    output: str,
    context_type: str = "insight",
    symbol: str | None = None,
    confidence: float | None = None,
) -> dict[str, Any]:
    """Cross-validate an AI-generated insight using Claude.

    Args:
        output: The generated insight text to validate
        context_type: Type of content (insight, recommendation, analysis)
        symbol: Stock symbol if applicable
        confidence: Generator's confidence (0-1)

    Returns:
        Dict with validation result status
    """
    from app.services.cross_validation import CrossValidationService

    try:
        service = CrossValidationService()
        result = service.validate(
            generator_output=output,
            context_type=context_type,
            context_symbol=symbol,
            generator_confidence=confidence,
        )

        logger.info(
            "cross_validation_complete",
            validation_id=result.id,
            approved=result.validator_approved,
            has_disagreement=result.has_disagreement,
            status=result.status.value,
        )

        return {
            "status": "completed",
            "validation_id": result.id,
            "approved": result.validator_approved,
            "has_disagreement": result.has_disagreement,
        }
    except Exception as e:
        logger.error("cross_validation_failed", error=str(e), exc_info=True)
        return {
            "status": "failed",
            "error": str(e),
        }
def emit_event_async(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Async wrapper for emit_event to allow Celery .delay() calls.

    Args:
        event_type: Type of event
        payload: Event data

    Returns:
        Dict with status and event details
    """
    success = emit_event(event_type, payload)
    return {
        "event_type": event_type,
        "emitted": success,
        "payload_keys": list(payload.keys()),
    }
