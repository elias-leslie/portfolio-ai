"""Strategy performance monitoring tasks.

Celery tasks for evaluating active strategies and archiving underperformers.
Runs daily to track live performance vs expected metrics.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, Literal

from app.celery_app import celery_app
from app.logging_config import get_logger
from app.storage.connection import get_connection_manager
from app.storage.credential_loader import load_credentials_from_database
from app.strategies.storage import get_strategy_storage
from app.utils.rate_limiter import check_daily_limit, increment_daily_count

logger = get_logger(__name__)

# Strategy performance thresholds
PERFORMANCE_RATIO_THRESHOLD = 0.7  # Archive if performance < 70% of expected
DEFAULT_ROLLING_WINDOW_DAYS = 30  # Rolling window for metrics calculation
UNDERPERFORMANCE_SHARPE_THRESHOLD = 0.5  # Sharpe ratio threshold for regeneration
EVOLUTION_TRIGGER_THRESHOLD = 0.9  # 90% of expected performance triggers evolution


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
        result = asyncio.run(strategy_research_workflow(symbol=symbol, force_regenerate=force_regenerate))

        if result["status"] == "completed":
            strategy_id = result.get("strategy_id", "unknown")
            logger.info("Strategy generated successfully", symbol=symbol, strategy_id=strategy_id)
            return f"Generated strategy for {symbol}: {strategy_id}", result
        msg = result.get("message", "unknown reason")
        logger.info("Strategy generation skipped/blocked", symbol=symbol, status=result["status"], message=msg)
        return f"Skipped {symbol}: {msg}", result

    except Exception as e:
        logger.exception("Strategy generation failed", symbol=symbol, error=str(e))
        return f"Error for {symbol}: {str(e)[:100]}", None


def _should_archive_strategy(performance_ratio: float, days_since_activation: int) -> bool:
    """Determine if a strategy should be archived based on performance.

    Args:
        performance_ratio: Actual/expected performance ratio
        days_since_activation: Days since strategy was activated

    Returns:
        True if strategy should be archived
    """
    return (
        performance_ratio < PERFORMANCE_RATIO_THRESHOLD
        and days_since_activation > DEFAULT_ROLLING_WINDOW_DAYS
    )


def _evaluate_single_strategy(
    strategy: Any,
    conn: Any,
    strategy_storage: Any,
) -> tuple[str | None, bool]:
    """Evaluate a single strategy and update its metrics.

    Args:
        strategy: Strategy object to evaluate
        conn: Database connection
        strategy_storage: Strategy storage instance

    Returns:
        Tuple of (result_message_or_none, was_archived)
    """
    # Calculate rolling metrics from paper_trade_transactions
    metrics = _calculate_rolling_metrics(
        conn, strategy.id, window_days=DEFAULT_ROLLING_WINDOW_DAYS
    )

    # Compare to expected metrics
    expected_sharpe = float(strategy.expected_sharpe or 0.0)
    actual_sharpe = metrics["sharpe_ratio_30d"]
    performance_ratio = actual_sharpe / expected_sharpe if expected_sharpe > 0 else 0

    # Determine status
    days_since_activation = (
        (datetime.now() - strategy.activation_date).days
        if strategy.activation_date
        else 0
    )

    archived = False
    result_msg: str | None = None

    # Decision logic: Archive if underperforming for >30 days
    if _should_archive_strategy(performance_ratio, days_since_activation):
        reason = (
            f"Underperforming: {actual_sharpe:.2f} Sharpe vs "
            f"{expected_sharpe:.2f} expected ({performance_ratio:.1%})"
        )
        strategy_storage.archive_strategy(strategy.id, reason)
        archived = True
        result_msg = f"Archived {strategy.name}: {performance_ratio:.1%} of expected performance"
        logger.warning(
            "Strategy archived due to underperformance",
            strategy_id=strategy.id,
            strategy_name=strategy.name,
            performance_ratio=performance_ratio,
        )
    else:
        # Update live performance metrics
        strategy_storage.update_live_performance(
            strategy_id=strategy.id,
            trades_count=metrics["trades_30d"],
            win_rate=metrics["win_rate_30d"],
            sharpe_ratio=actual_sharpe,
        )

    # Record daily performance
    status: Literal["active", "underperforming"] = (
        "underperforming" if performance_ratio < PERFORMANCE_RATIO_THRESHOLD else "active"
    )
    strategy_storage.record_daily_performance(
        strategy_id=strategy.id,
        date=date.today(),
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

    # Emit event for downstream triggers (auto-003)
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

    return result_msg, archived


@celery_app.task(name="app.tasks.strategy_monitoring_tasks.evaluate_strategy_performance")
def evaluate_strategy_performance() -> dict[str, Any]:
    """Evaluate all active strategies and archive underperformers.

    Schedule: Daily at 04:00 UTC (after market data updated)

    Logic:
    1. For each active strategy:
       - Calculate 30-day rolling metrics (Sharpe, win rate, max drawdown)
       - Compare to expected metrics from backtest
       - Archive if performance < 70% of expected for >30 days
    2. Update strategy_performance table with daily metrics
    3. Return summary of strategies evaluated and actions taken

    Returns:
        Summary dict with evaluation results
    """
    logger.info("Starting strategy performance evaluation")

    try:
        strategy_storage = get_strategy_storage()
        with get_connection_manager().connection() as conn:
            # Get all active strategies
            active_strategies = strategy_storage.list_strategies(status="active")

            if not active_strategies:
                logger.info("No active strategies to evaluate")
                return {
                    "status": "completed",
                    "strategies_evaluated": 0,
                    "strategies_archived": 0,
                    "details": [],
                }

            logger.info(f"Evaluating {len(active_strategies)} active strategies")

            results = []
            archived_count = 0

            for strategy in active_strategies:
                try:
                    result_msg, archived = _evaluate_single_strategy(
                        strategy, conn, strategy_storage
                    )
                    if result_msg:
                        results.append(result_msg)
                    if archived:
                        archived_count += 1

                except Exception as e:
                    logger.exception(
                        "Failed to evaluate strategy",
                        strategy_id=strategy.id,
                        strategy_name=strategy.name,
                        error=str(e),
                    )
                    results.append(f"Error evaluating {strategy.name}: {str(e)[:100]}")

            logger.info(
                "Strategy performance evaluation complete",
                strategies_evaluated=len(active_strategies),
                strategies_archived=archived_count,
            )

            return {
                "status": "completed",
                "strategies_evaluated": len(active_strategies),
                "strategies_archived": archived_count,
                "details": results,
            }

    except Exception as e:
        logger.exception("Strategy performance evaluation failed", error=str(e))
        return {
            "status": "failed",
            "error": str(e),
        }


def _calculate_today_metrics(trades: list[dict[str, Any]], today: date) -> dict[str, Any]:
    """Calculate metrics for trades made today.

    Args:
        trades: List of trade dicts with 'date' and 'pnl' keys
        today: Today's date

    Returns:
        Dict with trades_today, wins_today, losses_today, pnl_today
    """
    today_trades = [t for t in trades if t["date"] == today]
    trades_today = len(today_trades)
    wins_today = sum(1 for t in today_trades if t["pnl"] > 0)
    losses_today = trades_today - wins_today
    pnl_today = sum(t["pnl"] for t in today_trades)
    return {
        "trades_today": trades_today,
        "wins_today": wins_today,
        "losses_today": losses_today,
        "pnl_today": pnl_today,
    }


def _calculate_sharpe_ratio(daily_returns: list[float]) -> float:
    """Calculate simplified Sharpe ratio from daily returns.

    Uses mean/std without risk-free rate adjustment.

    Args:
        daily_returns: List of daily PnL values

    Returns:
        Sharpe ratio (0.0 if insufficient data)
    """
    if len(daily_returns) <= 1:
        return 0.0

    mean_return = sum(daily_returns) / len(daily_returns)
    variance = sum((r - mean_return) ** 2 for r in daily_returns) / len(daily_returns)
    std_dev = variance**0.5
    return mean_return / std_dev if std_dev > 0 else 0.0


def _calculate_max_drawdown(trades: list[dict[str, Any]]) -> float:
    """Calculate maximum drawdown from trade sequence.

    Args:
        trades: List of trade dicts with 'pnl' key

    Returns:
        Max drawdown as fraction (0.0 to 1.0)
    """
    cumulative_pnl = 0.0
    peak_pnl = 0.0
    max_drawdown = 0.0

    for t in trades:
        cumulative_pnl += t["pnl"]
        peak_pnl = max(peak_pnl, cumulative_pnl)
        drawdown = (peak_pnl - cumulative_pnl) / peak_pnl if peak_pnl > 0 else 0.0
        max_drawdown = max(max_drawdown, drawdown)

    return max_drawdown


def _calculate_rolling_metrics(
    conn: Any, strategy_id: str, window_days: int = 30
) -> dict[str, Any]:
    """Calculate rolling performance metrics for a strategy.

    Args:
        conn: Database connection
        strategy_id: Strategy UUID
        window_days: Rolling window size (default 30 days)

    Returns:
        Dict with calculated metrics
    """
    cutoff_date = date.today() - timedelta(days=window_days)

    try:
        result = conn.execute(
            """
            SELECT
                o.created_at::DATE as trade_date,
                o.realized_pnl as pnl
            FROM idea_outcomes o
            WHERE o.realized_pnl IS NOT NULL
              AND o.created_at >= %s
              AND o.strategy_id = %s
            ORDER BY o.created_at
            """,
            [cutoff_date, strategy_id],
        )
        rows = result.fetchall()
    except Exception as e:
        logger.warning(f"Could not query trades for strategy {strategy_id}: {e}")
        rows = []

    # Default return for no trades
    empty_metrics = {
        "trades_today": 0,
        "wins_today": 0,
        "losses_today": 0,
        "pnl_today": 0.0,
        "trades_30d": 0,
        "win_rate_30d": 0.0,
        "sharpe_ratio_30d": 0.0,
        "max_drawdown_30d": 0.0,
    }

    if not rows or len(rows) == 0:
        # No trades in window
        return empty_metrics

    # Convert rows to list of dicts for easier access
    # Rows are tuples: (trade_date, pnl)
    trades = []
    for row in rows:
        if isinstance(row, tuple):
            trade_date, pnl = row[0], row[1]
        else:
            trade_date = row.get("trade_date", row.get("date"))
            pnl = row.get("pnl", 0.0)

        if pnl is None:
            continue

        trades.append({"date": trade_date, "pnl": float(pnl)})

    if not trades:
        return empty_metrics

    # Calculate metrics using helpers
    today = date.today()
    today_metrics = _calculate_today_metrics(trades, today)

    # 30-day metrics
    trades_30d = len(trades)
    wins_30d = sum(1 for t in trades if t["pnl"] > 0)
    win_rate_30d = wins_30d / trades_30d if trades_30d > 0 else 0.0

    # Sharpe ratio and max drawdown
    daily_returns = [t["pnl"] for t in trades]
    sharpe_ratio_30d = _calculate_sharpe_ratio(daily_returns)
    max_drawdown = _calculate_max_drawdown(trades)

    return {
        **today_metrics,
        "trades_30d": trades_30d,
        "win_rate_30d": win_rate_30d,
        "sharpe_ratio_30d": sharpe_ratio_30d,
        "max_drawdown_30d": max_drawdown,
    }


@celery_app.task(name="app.tasks.strategy_monitoring_tasks.auto_promote_strategies")
def auto_promote_strategies(
    min_days: int = 3,
    min_sharpe: float = 1.0,
) -> dict[str, Any]:
    """Auto-promote testing strategies that meet validation criteria.

    Schedule: Daily at 04:15 UTC (after performance evaluation)

    Criteria for promotion:
    1. Strategy in 'testing' status for >= min_days
    2. Expected Sharpe ratio >= min_sharpe
    3. No blocking issues (negative Sharpe, etc.)

    Args:
        min_days: Minimum days in testing before promotion (default 3)
        min_sharpe: Minimum expected Sharpe to promote (default 1.0)

    Returns:
        Summary dict with promotion results
    """
    logger.info(
        "Starting auto-promotion of validated strategies", min_days=min_days, min_sharpe=min_sharpe
    )

    try:
        strategy_storage = get_strategy_storage()
        testing_strategies = strategy_storage.list_strategies(status="testing")

        if not testing_strategies:
            logger.info("No testing strategies to evaluate")
            return {
                "status": "completed",
                "strategies_evaluated": 0,
                "strategies_promoted": 0,
                "details": [],
            }

        logger.info(f"Evaluating {len(testing_strategies)} testing strategies for promotion")

        results = []
        promoted_count = 0

        for strategy in testing_strategies:
            try:
                # Check age (handle timezone-aware datetimes)
                now = datetime.now(UTC)
                created = strategy.created_at
                if created and created.tzinfo is None:
                    created = created.replace(tzinfo=UTC)
                days_since_creation = (now - created).days if created else 0

                if days_since_creation < min_days:
                    logger.debug(
                        f"Skipping {strategy.name}: only {days_since_creation} days old (need {min_days})"
                    )
                    continue

                # Check expected Sharpe
                expected_sharpe = float(strategy.expected_sharpe or 0.0)

                if expected_sharpe < min_sharpe:
                    logger.debug(
                        f"Skipping {strategy.name}: Sharpe {expected_sharpe:.2f} < {min_sharpe}"
                    )
                    continue

                # Check for blocking issues (negative Sharpe = likely bad strategy)
                if expected_sharpe < 0:
                    logger.debug(f"Skipping {strategy.name}: negative expected Sharpe")
                    continue

                # All criteria met - promote!
                strategy_storage.activate_strategy(strategy.id)
                promoted_count += 1
                results.append(
                    f"Promoted {strategy.name} (Sharpe={expected_sharpe:.2f}, age={days_since_creation}d)"
                )

                logger.info(
                    "Strategy auto-promoted",
                    strategy_id=strategy.id,
                    strategy_name=strategy.name,
                    expected_sharpe=expected_sharpe,
                    days_since_creation=days_since_creation,
                )

            except Exception as e:
                logger.exception(
                    "Failed to evaluate strategy for promotion",
                    strategy_id=strategy.id,
                    error=str(e),
                )

        logger.info(
            "Auto-promotion complete",
            strategies_evaluated=len(testing_strategies),
            strategies_promoted=promoted_count,
        )

        return {
            "status": "completed",
            "strategies_evaluated": len(testing_strategies),
            "strategies_promoted": promoted_count,
            "details": results,
        }

    except Exception as e:
        logger.exception("Auto-promotion failed", error=str(e))
        return {"status": "failed", "error": str(e)}


@celery_app.task(name="app.tasks.strategy_monitoring_tasks.weekly_strategy_generation")
def weekly_strategy_generation() -> dict[str, Any]:
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

    # Import here to avoid circular dependency

    try:
        strategy_storage = get_strategy_storage()

        # Get top 20 watchlist symbols ordered by highest overall score
        top_symbols = strategy_storage.get_top_watchlist_symbols(limit=20)

        if not top_symbols:
            logger.info("No watchlist symbols found")
            return {
                "status": "completed",
                "symbols_evaluated": 0,
                "strategies_generated": 0,
                "details": [],
            }

        logger.info(f"Evaluating {len(top_symbols)} top watchlist symbols")

        results = []
        generated_count = 0

        for symbol in top_symbols:
            # Check if active strategy already exists
            existing = strategy_storage.get_active_strategy(symbol)
            if existing:
                logger.info(f"Skipping {symbol}: active strategy exists ({existing.name})")
                continue

            # Generate new strategy
            logger.info(f"Generating strategy for {symbol}")
            msg, result = _run_strategy_workflow(symbol, force_regenerate=False)
            results.append(msg)
            if result and result["status"] == "completed":
                generated_count += 1

        logger.info(
            "Weekly strategy generation complete",
            symbols_evaluated=len(top_symbols),
            strategies_generated=generated_count,
        )

        return {
            "status": "completed",
            "symbols_evaluated": len(top_symbols),
            "strategies_generated": generated_count,
            "details": results,
        }

    except Exception as e:
        logger.exception("Weekly strategy generation failed", error=str(e))
        return {
            "status": "failed",
            "error": str(e),
        }


@celery_app.task(name="app.tasks.strategy_monitoring_tasks.daily_strategy_refresh")
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
        with get_connection_manager().connection() as conn:
            # Get symbols needing strategy generation:
            # 1. Top watchlist symbols without active strategy
            # 2. Symbols with underperforming strategies (30-day Sharpe < 0.5)
            symbols_to_generate = conn.execute(
                """
                WITH latest_scores AS (
                    SELECT DISTINCT ON (wi.symbol)
                        wi.symbol,
                        ws.overall_score
                    FROM watchlist_items wi
                    LEFT JOIN watchlist_snapshots_v ws ON wi.id = ws.item_id
                    ORDER BY wi.symbol, ws.fetched_at DESC
                ),
                active_strategies AS (
                    SELECT symbol, id, expected_sharpe
                    FROM strategy_definitions
                    WHERE status = 'active'
                ),
                underperforming AS (
                    SELECT DISTINCT sd.symbol
                    FROM strategy_definitions sd
                    JOIN strategy_performance sp ON sd.id = sp.strategy_id
                    WHERE sd.status = 'active'
                      AND sp.date >= CURRENT_DATE - INTERVAL '30 days'
                    GROUP BY sd.symbol
                    HAVING AVG(sp.sharpe_ratio_30d) < 0.5
                )
                SELECT ls.symbol, ls.overall_score,
                       CASE
                           WHEN acts.id IS NULL THEN 'no_strategy'
                           WHEN under.symbol IS NOT NULL THEN 'underperforming'
                           ELSE 'active'
                       END as reason
                FROM latest_scores ls
                LEFT JOIN active_strategies acts ON ls.symbol = acts.symbol
                LEFT JOIN underperforming under ON ls.symbol = under.symbol
                WHERE acts.id IS NULL OR under.symbol IS NOT NULL
                ORDER BY ls.overall_score DESC NULLS LAST
                LIMIT %s
                """,
                (max_symbols * 2,),  # Fetch extra in case some fail
            ).fetchall()

            if not symbols_to_generate:
                logger.info("No symbols need strategy generation")
                return {
                    "status": "completed",
                    "symbols_evaluated": 0,
                    "strategies_generated": 0,
                    "details": [],
                }

            logger.info(f"Found {len(symbols_to_generate)} symbols needing strategies")

            results = []
            generated_count = 0

            for row in symbols_to_generate:
                if generated_count >= max_symbols:
                    break

                symbol = str(row[0])
                reason = row[2]

                # Force regenerate if underperforming
                force = reason == "underperforming"

                logger.info(f"Generating strategy for {symbol} (reason: {reason})")
                msg, result = _run_strategy_workflow(symbol, force_regenerate=force)
                results.append(msg)
                if result and result["status"] == "completed":
                    generated_count += 1

            logger.info(
                "Daily strategy refresh complete",
                symbols_evaluated=len(symbols_to_generate),
                strategies_generated=generated_count,
            )

            return {
                "status": "completed",
                "symbols_evaluated": len(symbols_to_generate),
                "strategies_generated": generated_count,
                "details": results,
            }

    except Exception as e:
        logger.exception("Daily strategy refresh failed", error=str(e))
        return {"status": "failed", "error": str(e)}


@celery_app.task(name="app.tasks.strategy_monitoring_tasks.weekly_strategy_evolution")
def weekly_strategy_evolution() -> dict[str, Any]:
    """Weekly strategy evolution - evolve underperforming strategies via LLM.

    Schedule: Weekly on Sunday at 06:00 UTC (after weekly strategy generation)

    Evolution Logic:
    1. Find active strategies underperforming by >10% (Sharpe ratio)
    2. For each strategy:
       - Analyze performance with LLM diagnosis
       - Propose parameter mutations
       - Test mutations via walk-forward backtest
       - Save best mutation if it meets MAS (Minimum Acceptable Score)
    3. Archive parent strategy, activate evolved child

    MAS Criteria:
    - Child Sharpe >= 90% of parent Sharpe
    - OR Child Sharpe > Buy & Hold Benchmark

    Returns:
        Summary dict with evolution results
    """
    logger.info("Starting weekly strategy evolution")

    from app.agents.strategy_evolution_agent import get_strategy_evolution_agent

    try:
        evolution_agent = get_strategy_evolution_agent()
        get_strategy_storage()

        # Find underperforming active strategies (performance < 90% of expected)
        with get_connection_manager().connection() as conn:
            underperforming_strategies = conn.execute(
                """
                SELECT DISTINCT sd.id, sd.symbol, sd.name,
                       sd.expected_sharpe,
                       AVG(sp.sharpe_ratio_30d) as actual_sharpe,
                       AVG(sp.sharpe_ratio_30d) / NULLIF(sd.expected_sharpe, 0) as performance_ratio
                FROM strategy_definitions sd
                JOIN strategy_performance sp ON sd.id = sp.strategy_id
                WHERE sd.status = 'active'
                  AND sp.date >= CURRENT_DATE - INTERVAL '30 days'
                  AND sd.expected_sharpe > 0
                GROUP BY sd.id, sd.symbol, sd.name, sd.expected_sharpe
                HAVING AVG(sp.sharpe_ratio_30d) / NULLIF(sd.expected_sharpe, 0) < 0.9
                ORDER BY performance_ratio ASC
                LIMIT 5
                """
            ).fetchall()

        if not underperforming_strategies:
            logger.info("No underperforming strategies found")
            return {
                "status": "completed",
                "strategies_evaluated": 0,
                "strategies_evolved": 0,
                "details": [],
            }

        logger.info(f"Found {len(underperforming_strategies)} underperforming strategies")

        results = []
        evolved_count = 0

        for row in underperforming_strategies:
            strategy_id = str(row[0])
            symbol = row[1]
            name = row[2]
            expected_sharpe = float(row[3] or 0.0)
            actual_sharpe = float(row[4] or 0.0)
            performance_ratio = float(row[5] or 0.0)

            logger.info(
                f"Attempting evolution: {symbol} {name} "
                f"(Sharpe: {actual_sharpe:.2f} vs expected {expected_sharpe:.2f}, "
                f"ratio: {performance_ratio:.1%})"
            )

            try:
                # Evolve strategy
                result = asyncio.run(
                    evolution_agent.evolve_strategy(
                        strategy_id=strategy_id,
                        reason=f"underperforming_{performance_ratio:.0%}",
                    )
                )

                if result.success:
                    evolved_count += 1
                    results.append(
                        f"Evolved {symbol}: {result.parent_sharpe:.2f} → {result.child_sharpe:.2f} "
                        f"({result.mutations_tested} mutations tested)"
                    )
                    logger.info(
                        "Strategy evolved successfully",
                        symbol=symbol,
                        original_id=strategy_id,
                        new_id=result.new_strategy_id,
                        sharpe_improvement=result.child_sharpe - result.parent_sharpe
                        if result.child_sharpe
                        else 0,
                    )
                else:
                    results.append(f"Evolution failed for {symbol}: {result.message}")
                    logger.info(
                        "Strategy evolution failed",
                        symbol=symbol,
                        strategy_id=strategy_id,
                        reason=result.message,
                    )

            except Exception as e:
                logger.exception("Strategy evolution error", symbol=symbol, error=str(e))
                results.append(f"Error for {symbol}: {str(e)[:100]}")

        logger.info(
            "Weekly strategy evolution complete",
            strategies_evaluated=len(underperforming_strategies),
            strategies_evolved=evolved_count,
        )

        return {
            "status": "completed",
            "strategies_evaluated": len(underperforming_strategies),
            "strategies_evolved": evolved_count,
            "details": results,
        }

    except Exception as e:
        logger.exception("Weekly strategy evolution failed", error=str(e))
        return {"status": "failed", "error": str(e)}


@celery_app.task(name="app.tasks.strategy_monitoring_tasks.trigger_strategies_for_top_watchlist")
def trigger_strategies_for_top_watchlist(
    top_n: int = 10,
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

        generated_count = 0
        results = []

        for symbol in top_symbols:
            if generated_count >= remaining_budget:
                break

            # Check if active strategy exists
            existing = strategy_storage.get_active_strategy(symbol)
            if existing:
                logger.debug(f"Skipping {symbol}: active strategy exists")
                continue

            # Generate strategy
            logger.info(f"Auto-generating strategy for {symbol}")
            msg, result = _run_strategy_workflow(symbol, force_regenerate=False)
            results.append(msg)

            if result and result["status"] == "completed":
                generated_count += 1
                # Increment daily rate limit counter
                increment_daily_count("strategy_gen_daily")
                logger.info(
                    "strategy_auto_generated",
                    symbol=symbol,
                    strategy_id=result.get("strategy_id"),
                )

        logger.info(
            "trigger_strategies_for_top_watchlist_completed",
            generated=generated_count,
            remaining_budget=remaining_budget - generated_count,
        )

        return {
            "status": "completed",
            "generated": generated_count,
            "checked": len(top_symbols),
            "details": results,
        }

    except Exception as e:
        logger.exception("trigger_strategies_for_top_watchlist_failed", error=str(e))
        return {"status": "failed", "error": str(e)}


@celery_app.task(name="app.tasks.strategy_monitoring_tasks.trigger_strategy_from_seed")
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
    logger.info(f"Generating strategy from seed {seed_id} for {symbol}")

    try:
        with get_connection_manager().connection() as conn:
            # Get seed details
            seed_row = conn.execute(
                "SELECT thesis, confidence FROM strategy_seeds WHERE id = %s",
                [seed_id],
            ).fetchone()

            if not seed_row:
                logger.error(f"Seed {seed_id} not found")
                return {"status": "failed", "error": f"Seed {seed_id} not found"}

            seed_thesis = str(seed_row[0]) if seed_row[0] else ""
            seed_confidence = float(seed_row[1]) if seed_row[1] is not None else 0.0

            logger.info(
                f"Processing seed: symbol={symbol}, confidence={seed_confidence}, "
                f"thesis={seed_thesis[:100] if seed_thesis else ''}..."
            )

            # Run strategy workflow using shared helper
            _msg, result = _run_strategy_workflow(symbol, force_regenerate=False)

            if result and result["status"] == "completed":
                strategy_id = result.get("strategy_id")

                # Link strategy back to seed
                if strategy_id:
                    conn.execute(
                        """
                        UPDATE strategy_definitions
                        SET seed_id = %s, seed_thesis = %s, seed_confidence = %s
                        WHERE id = %s
                        """,
                        [seed_id, seed_thesis, seed_confidence, strategy_id],
                    )

                    # Update seed status to converted
                    conn.execute(
                        """
                        UPDATE strategy_seeds
                        SET status = 'converted', strategy_id = %s, processed_at = NOW()
                        WHERE id = %s
                        """,
                        [strategy_id, seed_id],
                    )
                    conn.commit()

                    logger.info(
                        f"Strategy {strategy_id} generated from seed {seed_id}",
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
            conn.execute(
                """
                UPDATE strategy_seeds
                SET status = 'rejected', processed_at = NOW()
                WHERE id = %s
                """,
                [seed_id],
            )
            conn.commit()

            reason = result.get("message", result.get("status", "unknown")) if result else "workflow error"
            logger.info(
                f"Seed {seed_id} rejected: {reason}",
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
        try:
            with get_connection_manager().connection() as conn:
                conn.execute(
                    "UPDATE strategy_seeds SET status = 'rejected', processed_at = NOW() WHERE id = %s",
                    [seed_id],
                )
                conn.commit()
        except Exception:
            pass

        return {"status": "failed", "seed_id": seed_id, "error": str(e)}
