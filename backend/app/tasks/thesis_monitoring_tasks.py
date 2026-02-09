"""Thesis Monitoring Tasks.

Daily thesis health monitoring and automated lifecycle management:
1. Health check: Evaluate invalidation triggers for all active theses
2. Auto-removal: Remove invalidated symbols from watchlist (unless in portfolio)
3. Strategy archival: Archive strategies when thesis invalidated (thesis drives lifecycle)
4. Audit trail: Log all actions to maintenance_log and deletion_audit

Scheduled via Hatchet cron:
- monitor_thesis_health: Daily 03:00 UTC (after fear/greed calculation)
- process_invalidated_theses: Daily 03:15 UTC (after health check)
- archive_strategies_for_invalidated_theses: Daily 03:30 UTC (after processing)
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any


from ..logging_config import get_logger
from ..rules.loader import get_rules
from ..services.thesis_service import ThesisService
from ..storage import PortfolioStorage
from ..storage.connection import get_connection_manager
from ..strategies.storage import StrategyStorage
from .watchlist_discovery.trimming import remove_symbol_from_watchlist

logger = get_logger(__name__)


def log_thesis_action(
    task_name: str,
    symbol: str,
    action: str,
    details: dict[str, Any],
) -> None:
    """Log thesis action to maintenance_log for audit trail.

    Args:
        task_name: Name of the task
        symbol: Stock symbol
        action: Action taken (invalidated, removed, archived)
        details: Additional details dictionary
    """
    conn_mgr = get_connection_manager()
    with conn_mgr.connection() as conn:
        conn.execute(
            """
            INSERT INTO maintenance_log (task_name, started_at, completed_at, status, summary)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                task_name,
                datetime.now(UTC),
                datetime.now(UTC),
                "success",
                json.dumps(
                    {
                        "symbol": symbol,
                        "action": action,
                        **details,
                    }
                ),
            ),
        )
        conn.commit()


def get_portfolio_symbols(storage: PortfolioStorage) -> set[str]:
    """Get symbols currently held in portfolio.

    Args:
        storage: Portfolio storage instance

    Returns:
        Set of symbols with shares > 0
    """
    df = storage.query(
        "SELECT DISTINCT symbol FROM portfolio_positions WHERE shares > 0",
        [],
    )
    return {str(row["symbol"]) for row in df.iter_rows(named=True)}


def get_active_strategies_for_symbol(
    strategy_storage: StrategyStorage,
    symbol: str,
) -> list[dict[str, Any]]:
    """Get all active strategies for a symbol.

    Args:
        strategy_storage: Strategy storage instance
        symbol: Stock symbol

    Returns:
        List of strategy dicts with id and name
    """
    strategies = strategy_storage.list_strategies(symbol=symbol, status="active")
    return [{"id": str(s.id), "name": s.name} for s in strategies]


def monitor_thesis_health_task() -> dict[str, Any]:
    """Daily thesis health check - evaluate invalidation triggers for all active theses.

    Scheduled: Daily 03:00 UTC (after fear/greed calculation, before strategy tasks)

    Returns:
        Dict with status, theses_checked, triggers_found, invalidated counts
    """
    rules = get_rules()
    tm = rules.thesis_management

    if not tm.thesis_generation_enabled:
        logger.info("thesis_health_check_skipped", reason="thesis_generation_disabled")
        return {"status": "skipped", "reason": "thesis_generation_disabled"}

    conn_mgr = get_connection_manager()
    thesis_service = ThesisService()

    results: dict[str, Any] = {
        "theses_checked": 0,
        "triggers_found": 0,
        "invalidated": 0,
        "flagged": 0,
        "details": [],
    }

    try:
        # Get all active theses
        with conn_mgr.connection() as conn:
            result = conn.execute("SELECT symbol FROM watchlist_thesis WHERE status = 'active'")
            symbols = [str(row[0]) for row in result.fetchall()]

        logger.info("thesis_health_check_started", active_theses=len(symbols))

        for symbol in symbols:
            results["theses_checked"] += 1

            # Check invalidation triggers
            triggers = thesis_service.check_invalidation_triggers(symbol)

            if triggers:
                results["triggers_found"] += 1

                # Get cross-validation score for severity assessment
                thesis = thesis_service.get_thesis(symbol)
                cross_val_score = thesis.cross_validation_score if thesis else None

                # Decide action based on trigger severity
                # Critical triggers: signal change, low cross-val → invalidate
                # Non-critical: sentiment shift → flag for review
                is_critical = any(
                    "Signal changed" in t or "cross-validation" in t.lower() for t in triggers
                )

                if is_critical:
                    # Invalidate thesis
                    reason = "; ".join(triggers)
                    thesis_service.invalidate_thesis(symbol, reason)
                    results["invalidated"] += 1

                    log_thesis_action(
                        "monitor_thesis_health",
                        symbol,
                        "invalidated",
                        {
                            "triggers": triggers,
                            "cross_validation_score": cross_val_score,
                            "severity": "critical",
                        },
                    )

                    results["details"].append(
                        {
                            "symbol": symbol,
                            "action": "invalidated",
                            "triggers": triggers,
                        }
                    )
                else:
                    # Flag for review (update status to flagged_for_review)
                    with conn_mgr.connection() as conn:
                        conn.execute(
                            """
                            UPDATE watchlist_thesis
                            SET status = 'flagged_for_review',
                                updated_at = NOW()
                            WHERE symbol = %s AND status = 'active'
                            """,
                            (symbol,),
                        )
                        conn.commit()

                    results["flagged"] += 1

                    log_thesis_action(
                        "monitor_thesis_health",
                        symbol,
                        "flagged",
                        {
                            "triggers": triggers,
                            "cross_validation_score": cross_val_score,
                            "severity": "non-critical",
                        },
                    )

                    results["details"].append(
                        {
                            "symbol": symbol,
                            "action": "flagged",
                            "triggers": triggers,
                        }
                    )

        logger.info(
            "thesis_health_check_completed",
            checked=results["theses_checked"],
            triggers_found=results["triggers_found"],
            invalidated=results["invalidated"],
            flagged=results["flagged"],
        )

        return {
            "status": "success",
            **results,
        }

    except Exception as e:
        logger.error("thesis_health_check_failed", error=str(e))
        return {"status": "error", "error": str(e)}


def process_invalidated_theses_task() -> dict[str, Any]:
    """Process invalidated theses - remove from watchlist based on rules config.

    Scheduled: Daily 03:15 UTC (after thesis health check)

    Respects rules.yaml:
    - auto_remove_on_invalidation: true = auto-remove, false = flag only
    - exclude_portfolio_holdings: never remove symbols owned in portfolio

    Returns:
        Dict with status, processed count, removed/skipped details
    """
    rules = get_rules()
    tm = rules.thesis_management
    wm = rules.watchlist_management

    # Check if auto-removal is enabled
    auto_remove = tm.auto_remove_on_invalidation
    exclude_portfolio = wm.exclude_portfolio_holdings
    max_removals = wm.max_daily_removals

    conn_mgr = get_connection_manager()
    storage = PortfolioStorage()

    results: dict[str, Any] = {
        "auto_remove_enabled": auto_remove,
        "processed": 0,
        "removed": [],
        "skipped_portfolio": [],
        "skipped_disabled": [],
    }

    try:
        # Get recently invalidated theses (last 24 hours)
        with conn_mgr.connection() as conn:
            result = conn.execute(
                """
                SELECT wt.symbol, wt.invalidation_reason, wt.invalidated_at,
                       wi.id as item_id
                FROM watchlist_thesis wt
                JOIN watchlist_items wi ON wi.symbol = wt.symbol
                WHERE wt.status = 'invalidated'
                  AND wt.invalidated_at >= NOW() - INTERVAL '24 hours'
                """
            )
            invalidated = result.fetchall()

        logger.info("process_invalidated_started", count=len(invalidated))

        if not invalidated:
            return {"status": "success", "message": "No invalidated theses to process"}

        # Get portfolio symbols for exclusion
        portfolio_symbols = get_portfolio_symbols(storage) if exclude_portfolio else set()

        removals_today = 0

        for row in invalidated:
            symbol = str(row[0])
            reason = str(row[1]) if row[1] else "Unknown"
            invalidated_at = row[2]
            item_id = str(row[3])

            results["processed"] += 1

            # Check portfolio exclusion
            if symbol in portfolio_symbols:
                results["skipped_portfolio"].append(
                    {
                        "symbol": symbol,
                        "reason": "In portfolio, not removed",
                    }
                )
                logger.info(
                    "thesis_removal_skipped",
                    symbol=symbol,
                    reason="in_portfolio",
                )
                continue

            # Check if auto-removal is enabled
            if not auto_remove:
                results["skipped_disabled"].append(
                    {
                        "symbol": symbol,
                        "reason": "auto_remove_on_invalidation=false",
                    }
                )
                logger.info(
                    "thesis_removal_skipped",
                    symbol=symbol,
                    reason="auto_remove_disabled",
                )
                continue

            # Check daily removal limit
            if removals_today >= max_removals:
                results["skipped_disabled"].append(
                    {
                        "symbol": symbol,
                        "reason": f"daily_limit_reached ({max_removals})",
                    }
                )
                logger.info(
                    "thesis_removal_skipped",
                    symbol=symbol,
                    reason="daily_limit_reached",
                )
                continue

            # Remove from watchlist
            removal_reason = f"Thesis invalidated: {reason}"
            success = remove_symbol_from_watchlist(
                storage,
                item_id,
                symbol,
                removal_reason,
            )

            if success:
                removals_today += 1
                invalidated_at_str = (
                    invalidated_at.isoformat()
                    if isinstance(invalidated_at, datetime)
                    else str(invalidated_at)
                    if invalidated_at
                    else None
                )
                results["removed"].append(
                    {
                        "symbol": symbol,
                        "reason": reason,
                        "invalidated_at": invalidated_at_str,
                    }
                )

                log_thesis_action(
                    "process_invalidated_theses",
                    symbol,
                    "removed_from_watchlist",
                    {
                        "invalidation_reason": reason,
                        "invalidated_at": invalidated_at_str,
                    },
                )

                logger.info(
                    "thesis_removal_completed",
                    symbol=symbol,
                    reason=reason,
                )

        logger.info(
            "process_invalidated_completed",
            processed=results["processed"],
            removed=len(results["removed"]),
            skipped_portfolio=len(results["skipped_portfolio"]),
            skipped_disabled=len(results["skipped_disabled"]),
        )

        return {
            "status": "success",
            **results,
        }

    except Exception as e:
        logger.error("process_invalidated_failed", error=str(e))
        return {"status": "error", "error": str(e)}


def archive_strategies_for_invalidated_theses_task() -> dict[str, Any]:
    """Archive strategies when thesis invalidated (thesis invalidation triggers strategy lifecycle).

    Scheduled: Daily 03:30 UTC (after thesis processing)

    The design principle: Thesis invalidation drives strategy lifecycle, not the other way around.
    When a thesis is invalidated, all active strategies for that symbol should be archived.

    Returns:
        Dict with status, strategies_archived count, details
    """
    conn_mgr = get_connection_manager()
    strategy_storage = StrategyStorage()

    results: dict[str, Any] = {
        "symbols_processed": 0,
        "strategies_archived": 0,
        "details": [],
    }

    try:
        # Get recently invalidated theses (last 24 hours)
        with conn_mgr.connection() as conn:
            result = conn.execute(
                """
                SELECT symbol, invalidation_reason, invalidated_at
                FROM watchlist_thesis
                WHERE status = 'invalidated'
                  AND invalidated_at >= NOW() - INTERVAL '24 hours'
                """
            )
            invalidated = result.fetchall()

        logger.info("archive_strategies_started", invalidated_count=len(invalidated))

        for row in invalidated:
            symbol = str(row[0])
            thesis_reason = str(row[1]) if row[1] else "Unknown"
            invalidated_at = row[2]

            results["symbols_processed"] += 1

            # Get all active strategies for this symbol using StrategyStorage
            strategies = get_active_strategies_for_symbol(strategy_storage, symbol)

            for strategy in strategies:
                strategy_id = strategy["id"]
                strategy_name = strategy["name"]

                # Archive with thesis invalidation reason using StrategyStorage
                archive_reason = f"Thesis invalidated: {thesis_reason}"
                try:
                    strategy_storage.archive_strategy(strategy_id, archive_reason)
                    results["strategies_archived"] += 1

                    invalidated_at_str = (
                        invalidated_at.isoformat()
                        if isinstance(invalidated_at, datetime)
                        else str(invalidated_at)
                        if invalidated_at
                        else None
                    )
                    log_thesis_action(
                        "archive_strategies_for_invalidated_theses",
                        symbol,
                        "strategy_archived",
                        {
                            "strategy_id": strategy_id,
                            "strategy_name": strategy_name,
                            "archive_reason": archive_reason,
                            "thesis_invalidated_at": invalidated_at_str,
                        },
                    )

                    results["details"].append(
                        {
                            "symbol": symbol,
                            "strategy_id": strategy_id,
                            "strategy_name": strategy_name,
                        }
                    )

                    logger.info(
                        "strategy_archived_for_thesis",
                        symbol=symbol,
                        strategy_id=strategy_id,
                        reason=archive_reason,
                    )
                except Exception as e:
                    logger.error(
                        "strategy_archive_failed",
                        strategy_id=strategy_id,
                        symbol=symbol,
                        error=str(e),
                    )

        logger.info(
            "archive_strategies_completed",
            symbols_processed=results["symbols_processed"],
            strategies_archived=results["strategies_archived"],
        )

        return {
            "status": "success",
            **results,
        }

    except Exception as e:
        logger.error("archive_strategies_failed", error=str(e))
        return {"status": "error", "error": str(e)}
