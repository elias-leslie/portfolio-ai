"""Strategy generation tasks.

Celery tasks for generating new trading strategies based on watchlist analysis,
discovery seeds, and scheduled generation workflows.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any

from app.logging_config import get_logger
from app.storage.credential_loader import load_credentials_from_database
from app.strategies.storage import get_strategy_storage
from app.tasks.types import (
    StrategyMonitoringResultDict,
    build_strategy_failure,
    build_strategy_success,
)
from app.utils.rate_limiter import check_daily_limit, increment_daily_count

logger = get_logger(__name__)

# Strategy limits
TOP_WATCHLIST_SYMBOLS = 20  # Top symbols to consider for weekly strategy generation
TOP_WATCHLIST_TRIGGER_SYMBOLS = 10  # Top symbols to consider for trigger-based generation

# Error handling
ERROR_MESSAGE_TRUNCATE = 100  # Truncate error messages to prevent log bloat


def _run_strategy_workflow(
    symbol: str,
    force_regenerate: bool = False,
) -> tuple[str, dict[str, Any] | None]:
    """Run strategy research workflow for a symbol with standardized error handling.

    Wraps asyncio.run pattern and provides consistent result structure.

    Args:
        symbol: Stock symbol to generate strategy for
        force_regenerate: Whether to force regeneration even if strategy exists

    Returns:
        Tuple of (status_message, result_dict or None on error)
    """
    from app.agents.workflows.strategy_research_workflow import strategy_research_workflow

    try:
        result = asyncio.run(
            strategy_research_workflow(symbol=symbol, force_regenerate=force_regenerate)
        )

        if result["status"] == "completed":
            strategy_id = result.get("strategy_id", "unknown")
            logger.info("Strategy generated successfully", symbol=symbol, strategy_id=strategy_id)
            return f"Generated strategy for {symbol}: {strategy_id}", result
        msg = result.get("message", "unknown reason")
        logger.info(
            "Strategy generation skipped/blocked",
            symbol=symbol,
            status=result["status"],
            message=msg,
        )
        return f"Skipped {symbol}: {msg}", result

    except Exception as e:
        logger.exception("Strategy generation failed", symbol=symbol, error=str(e))
        return f"Error for {symbol}: {str(e)[:ERROR_MESSAGE_TRUNCATE]}", None


def _generate_strategies_batch(
    symbols: list[str],
    max_count: int,
    force_regenerate: bool = False,
) -> dict[str, Any]:
    """Generate strategies for a batch of symbols.

    Common helper to iterate over symbols and generate strategies,
    used by weekly_strategy_generation and similar tasks.

    Args:
        symbols: List of symbols to process
        max_count: Maximum number of strategies to generate
        force_regenerate: Whether to force regeneration even if strategy exists

    Returns:
        Dict with generated_count and results list
    """
    results = []
    generated_count = 0

    for symbol in symbols:
        if generated_count >= max_count:
            break

        logger.info("Generating strategy for symbol", symbol=symbol)
        msg, result = _run_strategy_workflow(symbol, force_regenerate=force_regenerate)
        results.append(msg)
        if result and result["status"] == "completed":
            generated_count += 1

    return {
        "generated_count": generated_count,
        "results": results,
    }


def _filter_symbols_without_active_strategy(
    symbols: list[str],
    strategy_storage: Any,
) -> list[str]:
    """Filter out symbols that already have active strategies.

    Args:
        symbols: List of symbols to check
        strategy_storage: Strategy storage instance

    Returns:
        List of symbols without active strategies
    """
    symbols_to_generate = []
    for symbol in symbols:
        existing = strategy_storage.get_active_strategy(symbol)
        if existing:
            logger.debug("Skipping symbol with active strategy", symbol=symbol)
        else:
            symbols_to_generate.append(symbol)
    return symbols_to_generate


def weekly_strategy_generation() -> StrategyMonitoringResultDict:
    """Generate new strategies for top watchlist symbols.

    Schedule: Weekly on Sunday at 05:00 UTC

    Logic:
    1. Get top 20 symbols from watchlist (by priority score)
    2. For each symbol without active strategy:
       - Trigger strategy_research_workflow
    3. Return summary of generation attempts

    Returns:
        Summary dict with generation results
    """
    # Load LLM credentials (e.g., GEMINI_API_KEY) from database
    load_credentials_from_database()

    logger.info("Starting weekly strategy generation")

    try:
        strategy_storage = get_strategy_storage()

        # Get top 20 watchlist symbols ordered by highest overall score
        top_symbols = strategy_storage.get_top_watchlist_symbols(limit=TOP_WATCHLIST_SYMBOLS)

        if not top_symbols:
            logger.info("No watchlist symbols found")
            return build_strategy_success(details=[])

        logger.info("Evaluating top watchlist symbols", count=len(top_symbols))

        # Filter to symbols without active strategies
        symbols_to_generate = _filter_symbols_without_active_strategy(top_symbols, strategy_storage)

        # Generate strategies using shared helper
        batch_result = _generate_strategies_batch(
            symbols=symbols_to_generate,
            max_count=len(symbols_to_generate),
            force_regenerate=False,
        )

        logger.info(
            "Weekly strategy generation complete",
            symbols_evaluated=len(top_symbols),
            strategies_generated=batch_result["generated_count"],
        )

        return build_strategy_success(
            symbols_evaluated=len(top_symbols),
            strategies_generated=batch_result["generated_count"],
            details=batch_result["results"],
        )

    except Exception as e:
        logger.exception("Weekly strategy generation failed", error=str(e))
        return build_strategy_failure(e)


def daily_strategy_refresh(max_symbols: int = 5) -> dict[str, Any]:
    """Daily strategy refresh - regenerate strategies for underperformers.

    Schedule: Daily at 05:00 UTC (after performance evaluation)

    Logic:
    1. Get top 20 watchlist symbols
    2. For each symbol:
       - If no active strategy: generate one
       - If strategy underperforming (30-day Sharpe < 0.5): regenerate
    3. Limit to max_symbols per day to control costs

    Args:
        max_symbols: Maximum strategies to generate per run (default 5)

    Returns:
        Summary dict with generation results
    """
    logger.info("Starting daily strategy refresh", max_symbols=max_symbols)

    try:
        strategy_storage = get_strategy_storage()

        # Get symbols needing strategy generation
        symbols_to_generate = strategy_storage.get_symbols_needing_strategies(max_symbols)

        if not symbols_to_generate:
            logger.info("No symbols need strategy generation")
            return {
                "status": "completed",
                "symbols_evaluated": 0,
                "strategies_generated": 0,
                "details": [],
            }

        logger.info("Found symbols needing strategies", count=len(symbols_to_generate))

        # Separate symbols by force_regenerate flag
        underperforming_symbols = []
        missing_symbols = []
        for row in symbols_to_generate:
            symbol = str(row[0])
            reason = row[2]
            if reason == "underperforming":
                underperforming_symbols.append(symbol)
            else:
                missing_symbols.append(symbol)

        # Generate strategies using shared helper (in priority order)
        all_results = []
        total_generated = 0

        # First, regenerate underperforming strategies (force=True)
        if underperforming_symbols and total_generated < max_symbols:
            batch_result = _generate_strategies_batch(
                symbols=underperforming_symbols,
                max_count=max_symbols - total_generated,
                force_regenerate=True,
            )
            all_results.extend(batch_result["results"])
            total_generated += batch_result["generated_count"]

        # Then, generate missing strategies (force=False)
        if missing_symbols and total_generated < max_symbols:
            batch_result = _generate_strategies_batch(
                symbols=missing_symbols,
                max_count=max_symbols - total_generated,
                force_regenerate=False,
            )
            all_results.extend(batch_result["results"])
            total_generated += batch_result["generated_count"]

        logger.info(
            "Daily strategy refresh complete",
            symbols_evaluated=len(symbols_to_generate),
            strategies_generated=total_generated,
        )

        return {
            "status": "completed",
            "symbols_evaluated": len(symbols_to_generate),
            "strategies_generated": total_generated,
            "details": all_results,
        }

    except Exception as e:
        logger.exception("Daily strategy refresh failed", error=str(e))
        return {"status": "failed", "error": str(e)}


def trigger_strategies_for_top_watchlist(
    top_n: int = TOP_WATCHLIST_TRIGGER_SYMBOLS,
    max_per_day: int = 3,
) -> dict[str, Any]:
    """Generate strategies for top watchlist symbols that don't have one.

    Triggered automatically after watchlist scoring completes (auto-001).
    Rate-limited to max_per_day new strategies per day.

    Args:
        top_n: Number of top symbols to consider (default 10)
        max_per_day: Maximum strategies to generate per day (default 3)

    Returns:
        Summary dict with generation results
    """
    logger.info(
        "trigger_strategies_for_top_watchlist_started",
        top_n=top_n,
        max_per_day=max_per_day,
    )

    try:
        # Check daily rate limit via utility
        rate_result = check_daily_limit("strategy_gen_daily", max_per_day)
        if not rate_result.allowed:
            logger.info(
                "trigger_strategies_rate_limited",
                current_count=rate_result.current_count,
                max_per_day=max_per_day,
            )
            return {
                "status": "rate_limited",
                "generated": 0,
                "reason": f"Daily limit reached ({rate_result.current_count}/{max_per_day})",
            }

        remaining_budget = rate_result.remaining
        strategy_storage = get_strategy_storage()

        # Get top N watchlist symbols by composite score (require non-null scores)
        top_symbols = strategy_storage.get_top_watchlist_symbols(limit=top_n, require_score=True)

        if not top_symbols:
            logger.info("trigger_strategies_no_watchlist_symbols")
            return {"status": "completed", "generated": 0, "reason": "No watchlist symbols"}

        # Filter to symbols without active strategies
        symbols_to_generate = _filter_symbols_without_active_strategy(top_symbols, strategy_storage)

        # Generate strategies using shared helper
        # Note: Rate limit tracking is done post-generation
        batch_result = _generate_strategies_batch(
            symbols=symbols_to_generate,
            max_count=remaining_budget,
            force_regenerate=False,
        )

        # Update rate limit counter for successful generations
        for _ in range(batch_result["generated_count"]):
            increment_daily_count("strategy_gen_daily")

        logger.info(
            "trigger_strategies_for_top_watchlist_completed",
            generated=batch_result["generated_count"],
            remaining_budget=remaining_budget - batch_result["generated_count"],
        )

        return {
            "status": "completed",
            "generated": batch_result["generated_count"],
            "checked": len(top_symbols),
            "details": batch_result["results"],
        }

    except Exception as e:
        logger.exception("trigger_strategies_for_top_watchlist_failed", error=str(e))
        return {"status": "failed", "error": str(e)}


def trigger_strategy_from_seed(seed_id: str, symbol: str) -> dict[str, Any]:
    """Generate strategy from a high-confidence seed.

    Triggered automatically when Discovery Agent stores a seed with confidence >= 7.
    Runs strategy_research_workflow and links the resulting strategy back to the seed.

    Args:
        seed_id: UUID of the strategy_seed that triggered this
        symbol: Stock symbol for strategy generation

    Returns:
        Summary dict with generation result
    """
    logger.info("Generating strategy from seed", seed_id=seed_id, symbol=symbol)
    storage = get_strategy_storage()

    try:
        # Get seed details from storage layer
        seed_data = storage.get_strategy_seed(seed_id)

        if not seed_data:
            logger.error("Seed not found", seed_id=seed_id)
            return {"status": "failed", "error": f"Seed {seed_id} not found"}

        seed_thesis, seed_confidence = seed_data

        logger.info(
            "Processing seed",
            symbol=symbol,
            seed_confidence=seed_confidence,
            thesis_preview=seed_thesis[:100] if seed_thesis else "",
        )

        # Run strategy workflow using shared helper
        _msg, result = _run_strategy_workflow(symbol, force_regenerate=False)

        if result and result["status"] == "completed":
            strategy_id = result.get("strategy_id")

            # Link strategy back to seed via storage layer
            if strategy_id:
                storage.link_strategy_to_seed(
                    strategy_id=strategy_id,
                    seed_id=seed_id,
                    seed_thesis=seed_thesis,
                    seed_confidence=seed_confidence,
                )

                logger.info(
                    "Strategy generated from seed",
                    strategy_id=strategy_id,
                    seed_id=seed_id,
                    symbol=symbol,
                    seed_confidence=seed_confidence,
                )

            return {
                "status": "completed",
                "seed_id": seed_id,
                "strategy_id": strategy_id,
                "symbol": symbol,
                "message": f"Strategy generated from seed (confidence: {seed_confidence})",
            }

        # Strategy not generated (blocked, skipped, or error)
        storage.reject_seed(seed_id)

        reason = (
            result.get("message", result.get("status", "unknown")) if result else "workflow error"
        )
        logger.info(
            "Seed rejected",
            seed_id=seed_id,
            reason=reason,
            symbol=symbol,
            workflow_status=result["status"] if result else "error",
        )

        return {
            "status": "rejected",
            "seed_id": seed_id,
            "symbol": symbol,
            "reason": reason,
        }

    except Exception as e:
        logger.exception("Strategy generation from seed failed", seed_id=seed_id, error=str(e))

        # Mark seed as failed but don't crash
        with contextlib.suppress(Exception):
            storage.reject_seed(seed_id)

        return {"status": "failed", "seed_id": seed_id, "error": str(e)}
