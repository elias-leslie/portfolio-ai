"""Strategy generation tasks.

Tasks for generating new trading strategies based on watchlist analysis,
discovery seeds, and scheduled generation workflows.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any

from app.constants import ERROR_MESSAGE_TRUNCATE
from app.logging_config import get_logger
from app.storage.credential_loader import load_credentials_from_database
from app.strategies.storage import get_strategy_storage
from app.tasks.types import (
    StrategyMonitoringResultDict,
    build_strategy_failure,
    build_strategy_success,
)
from app.utils.rate_limiter import check_daily_limit, increment_daily_count
from app.utils.task_lifecycle import task_cleanup

logger = get_logger(__name__)

# Strategy limits
TOP_WATCHLIST_SYMBOLS = 20  # Top symbols to consider for weekly strategy generation
TOP_WATCHLIST_TRIGGER_SYMBOLS = 10  # Top symbols to consider for trigger-based generation


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
    finally:
        task_cleanup("run_strategy_workflow")


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


def _run_weekly_generation(
    strategy_storage: Any,
) -> StrategyMonitoringResultDict:
    """Core logic for weekly strategy generation.

    Args:
        strategy_storage: Strategy storage instance

    Returns:
        Summary dict with generation results
    """
    top_symbols = strategy_storage.get_top_watchlist_symbols(limit=TOP_WATCHLIST_SYMBOLS)

    if not top_symbols:
        logger.info("No watchlist symbols found")
        return build_strategy_success(details=[])

    logger.info("Evaluating top watchlist symbols", count=len(top_symbols))

    symbols_to_generate = _filter_symbols_without_active_strategy(top_symbols, strategy_storage)

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
        return _run_weekly_generation(strategy_storage)
    except Exception as e:
        logger.exception("Weekly strategy generation failed", error=str(e))
        return build_strategy_failure(e)


def _categorize_refresh_symbols(
    symbols_to_generate: list[Any],
) -> tuple[list[str], list[str]]:
    """Separate symbols by generation reason into underperforming and missing.

    Args:
        symbols_to_generate: List of rows with (symbol, ..., reason, ...)

    Returns:
        Tuple of (underperforming_symbols, missing_symbols)
    """
    underperforming_symbols = []
    missing_symbols = []
    for row in symbols_to_generate:
        symbol = str(row[0])
        reason = row[2]
        if reason == "underperforming":
            underperforming_symbols.append(symbol)
        else:
            missing_symbols.append(symbol)
    return underperforming_symbols, missing_symbols


def _run_refresh_batches(
    underperforming_symbols: list[str],
    missing_symbols: list[str],
    max_symbols: int,
) -> tuple[list[str], int]:
    """Run generation batches for underperforming and missing symbols in priority order.

    Args:
        underperforming_symbols: Symbols with underperforming strategies (force regenerate)
        missing_symbols: Symbols without any strategy
        max_symbols: Maximum total strategies to generate

    Returns:
        Tuple of (all_results, total_generated)
    """
    all_results: list[str] = []
    total_generated = 0

    if underperforming_symbols and total_generated < max_symbols:
        batch_result = _generate_strategies_batch(
            symbols=underperforming_symbols,
            max_count=max_symbols - total_generated,
            force_regenerate=True,
        )
        all_results.extend(batch_result["results"])
        total_generated += batch_result["generated_count"]

    if missing_symbols and total_generated < max_symbols:
        batch_result = _generate_strategies_batch(
            symbols=missing_symbols,
            max_count=max_symbols - total_generated,
            force_regenerate=False,
        )
        all_results.extend(batch_result["results"])
        total_generated += batch_result["generated_count"]

    return all_results, total_generated


def _run_daily_refresh(strategy_storage: Any, max_symbols: int) -> dict[str, Any]:
    """Core logic for daily strategy refresh.

    Args:
        strategy_storage: Strategy storage instance
        max_symbols: Maximum strategies to generate

    Returns:
        Summary dict with generation results
    """
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

    underperforming_symbols, missing_symbols = _categorize_refresh_symbols(symbols_to_generate)
    all_results, total_generated = _run_refresh_batches(
        underperforming_symbols, missing_symbols, max_symbols
    )

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
        return _run_daily_refresh(strategy_storage, max_symbols)
    except Exception as e:
        logger.exception("Daily strategy refresh failed", error=str(e))
        return {"status": "failed", "error": str(e)}


def _check_trigger_rate_limit(
    max_per_day: int,
) -> tuple[bool, dict[str, Any] | None, int]:
    """Check daily rate limit for trigger-based strategy generation.

    Args:
        max_per_day: Maximum strategies to generate per day

    Returns:
        Tuple of (allowed, error_response_or_None, remaining_budget)
    """
    rate_result = check_daily_limit("strategy_gen_daily", max_per_day)
    if not rate_result.allowed:
        logger.info(
            "trigger_strategies_rate_limited",
            current_count=rate_result.current_count,
            max_per_day=max_per_day,
        )
        return False, {
            "status": "rate_limited",
            "generated": 0,
            "reason": f"Daily limit reached ({rate_result.current_count}/{max_per_day})",
        }, 0
    return True, None, rate_result.remaining


def _run_trigger_generation(
    top_n: int,
    remaining_budget: int,
    strategy_storage: Any,
) -> dict[str, Any]:
    """Run generation for top watchlist symbols within budget.

    Args:
        top_n: Number of top symbols to consider
        remaining_budget: Maximum number of strategies to generate
        strategy_storage: Strategy storage instance

    Returns:
        Summary dict with generation results
    """
    top_symbols = strategy_storage.get_top_watchlist_symbols(limit=top_n, require_score=True)

    if not top_symbols:
        logger.info("trigger_strategies_no_watchlist_symbols")
        return {"status": "completed", "generated": 0, "reason": "No watchlist symbols"}

    symbols_to_generate = _filter_symbols_without_active_strategy(top_symbols, strategy_storage)

    batch_result = _generate_strategies_batch(
        symbols=symbols_to_generate,
        max_count=remaining_budget,
        force_regenerate=False,
    )

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
        allowed, rate_limited_response, remaining_budget = _check_trigger_rate_limit(max_per_day)
        if not allowed:
            return rate_limited_response  # type: ignore[return-value]

        strategy_storage = get_strategy_storage()
        return _run_trigger_generation(top_n, remaining_budget, strategy_storage)

    except Exception as e:
        logger.exception("trigger_strategies_for_top_watchlist_failed", error=str(e))
        return {"status": "failed", "error": str(e)}


def _link_strategy_to_seed(
    storage: Any,
    strategy_id: str,
    seed_id: str,
    seed_thesis: str,
    seed_confidence: Any,
    symbol: str,
) -> None:
    """Link a generated strategy back to its originating seed.

    Args:
        storage: Strategy storage instance
        strategy_id: ID of the generated strategy
        seed_id: ID of the originating seed
        seed_thesis: Thesis text from the seed
        seed_confidence: Confidence score of the seed
        symbol: Stock symbol
    """
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


def _reject_seed_with_log(
    storage: Any,
    result: dict[str, Any] | None,
    seed_id: str,
    symbol: str,
) -> dict[str, Any]:
    """Reject a seed and log the reason.

    Args:
        storage: Strategy storage instance
        result: Workflow result dict or None on error
        seed_id: ID of the seed to reject
        symbol: Stock symbol

    Returns:
        Rejected status dict
    """
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
    return {"status": "rejected", "seed_id": seed_id, "symbol": symbol, "reason": reason}


def _handle_seed_workflow_result(
    storage: Any,
    result: dict[str, Any] | None,
    seed_id: str,
    seed_thesis: str,
    seed_confidence: Any,
    symbol: str,
) -> dict[str, Any]:
    """Handle the result of a seed-triggered strategy workflow.

    Args:
        storage: Strategy storage instance
        result: Workflow result dict or None on error
        seed_id: ID of the originating seed
        seed_thesis: Thesis text from the seed
        seed_confidence: Confidence score of the seed
        symbol: Stock symbol

    Returns:
        Summary dict with generation result
    """
    if result and result["status"] == "completed":
        strategy_id = result.get("strategy_id")
        if strategy_id:
            _link_strategy_to_seed(
                storage, strategy_id, seed_id, seed_thesis, seed_confidence, symbol
            )
        return {
            "status": "completed",
            "seed_id": seed_id,
            "strategy_id": strategy_id,
            "symbol": symbol,
            "message": f"Strategy generated from seed (confidence: {seed_confidence})",
        }

    return _reject_seed_with_log(storage, result, seed_id, symbol)


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
        seed_data = storage.get_strategy_seed(seed_id)

        if not seed_data:
            logger.error("seed_not_found", seed_id=seed_id)
            return {"status": "failed", "error": f"Seed {seed_id} not found"}

        seed_thesis, seed_confidence = seed_data

        logger.info(
            "Processing seed",
            symbol=symbol,
            seed_confidence=seed_confidence,
            thesis_preview=seed_thesis[:100] if seed_thesis else "",
        )

        _msg, result = _run_strategy_workflow(symbol, force_regenerate=False)

        return _handle_seed_workflow_result(
            storage, result, seed_id, seed_thesis, seed_confidence, symbol
        )

    except Exception as e:
        logger.exception("Strategy generation from seed failed", seed_id=seed_id, error=str(e))

        with contextlib.suppress(Exception):
            storage.reject_seed(seed_id)

        return {"status": "failed", "seed_id": seed_id, "error": str(e)}
