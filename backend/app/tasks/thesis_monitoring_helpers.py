"""Thesis Monitoring Helpers.

Internal helper functions for thesis monitoring tasks:
- Audit logging
- Portfolio/strategy lookups
- Per-symbol processing logic for health check, invalidation, and archival
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from ..logging_config import get_logger
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
                json.dumps({"symbol": symbol, "action": action, **details}),
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


def get_invalidated_theses_last_24h() -> list[Any]:
    """Fetch theses invalidated in the last 24 hours with watchlist join.

    Returns:
        List of rows: (symbol, invalidation_reason, invalidated_at, item_id)
    """
    conn_mgr = get_connection_manager()
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
        return result.fetchall()


def get_invalidated_symbols_last_24h() -> list[Any]:
    """Fetch symbols with invalidated theses in the last 24 hours (no join).

    Returns:
        List of rows: (symbol, invalidation_reason, invalidated_at)
    """
    conn_mgr = get_connection_manager()
    with conn_mgr.connection() as conn:
        result = conn.execute(
            """
            SELECT symbol, invalidation_reason, invalidated_at
            FROM watchlist_thesis
            WHERE status = 'invalidated'
              AND invalidated_at >= NOW() - INTERVAL '24 hours'
            """
        )
        return result.fetchall()


def flag_thesis_for_review(symbol: str) -> None:
    """Update thesis status to flagged_for_review in the database.

    Args:
        symbol: Stock symbol whose thesis to flag
    """
    conn_mgr = get_connection_manager()
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


def process_symbol_health(
    symbol: str,
    thesis_service: ThesisService,
    results: dict[str, Any],
) -> None:
    """Evaluate health triggers for one symbol and update results in place.

    Args:
        symbol: Stock symbol to check
        thesis_service: ThesisService instance
        results: Mutable results dict updated in place
    """
    triggers = thesis_service.check_invalidation_triggers(symbol)
    if not triggers:
        return

    results["triggers_found"] += 1
    thesis = thesis_service.get_thesis(symbol)
    cross_val_score = thesis.cross_validation_score if thesis else None
    is_critical = any(
        "Signal changed" in t or "cross-validation" in t.lower() for t in triggers
    )

    if is_critical:
        _handle_critical_trigger(symbol, triggers, cross_val_score, thesis_service, results)
    else:
        _handle_non_critical_trigger(symbol, triggers, cross_val_score, results)


def _handle_critical_trigger(
    symbol: str,
    triggers: list[str],
    cross_val_score: float | None,
    thesis_service: ThesisService,
    results: dict[str, Any],
) -> None:
    """Invalidate thesis and record result for a critical trigger.

    Args:
        symbol: Stock symbol
        triggers: List of trigger descriptions
        cross_val_score: Cross-validation score or None
        thesis_service: ThesisService instance
        results: Mutable results dict updated in place
    """
    reason = "; ".join(triggers)
    thesis_service.invalidate_thesis(symbol, reason)
    results["invalidated"] += 1

    log_thesis_action(
        "monitor_thesis_health",
        symbol,
        "invalidated",
        {"triggers": triggers, "cross_validation_score": cross_val_score, "severity": "critical"},
    )
    results["details"].append({"symbol": symbol, "action": "invalidated", "triggers": triggers})


def _handle_non_critical_trigger(
    symbol: str,
    triggers: list[str],
    cross_val_score: float | None,
    results: dict[str, Any],
) -> None:
    """Flag thesis for review and record result for a non-critical trigger.

    Args:
        symbol: Stock symbol
        triggers: List of trigger descriptions
        cross_val_score: Cross-validation score or None
        results: Mutable results dict updated in place
    """
    flag_thesis_for_review(symbol)
    results["flagged"] += 1

    log_thesis_action(
        "monitor_thesis_health",
        symbol,
        "flagged",
        {"triggers": triggers, "cross_validation_score": cross_val_score, "severity": "non-critical"},
    )
    results["details"].append({"symbol": symbol, "action": "flagged", "triggers": triggers})


def to_iso_string(value: Any) -> str | None:
    """Convert a datetime or other value to ISO string or None.

    Args:
        value: datetime or other value

    Returns:
        ISO format string if datetime, str() otherwise, None if falsy
    """
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value) if value else None


def process_single_invalidated_thesis(
    row: Any,
    portfolio_symbols: set[str],
    auto_remove: bool,
    max_removals: int,
    removals_today: int,
    storage: PortfolioStorage,
    results: dict[str, Any],
) -> int:
    """Process one invalidated thesis row for watchlist removal.

    Args:
        row: DB row (symbol, reason, invalidated_at, item_id)
        portfolio_symbols: Symbols currently in portfolio
        auto_remove: Whether auto-removal is enabled
        max_removals: Max daily removals allowed
        removals_today: Current count of removals done today
        storage: PortfolioStorage instance
        results: Mutable results dict updated in place

    Returns:
        Updated removals_today count
    """
    symbol = str(row[0])
    reason = str(row[1]) if row[1] else "Unknown"
    invalidated_at = row[2]
    item_id = str(row[3])
    results["processed"] += 1

    if symbol in portfolio_symbols:
        results["skipped_portfolio"].append({"symbol": symbol, "reason": "In portfolio, not removed"})
        logger.info("thesis_removal_skipped", symbol=symbol, reason="in_portfolio")
        return removals_today

    if not auto_remove:
        results["skipped_disabled"].append({"symbol": symbol, "reason": "auto_remove_on_invalidation=false"})
        logger.info("thesis_removal_skipped", symbol=symbol, reason="auto_remove_disabled")
        return removals_today

    if removals_today >= max_removals:
        results["skipped_disabled"].append({"symbol": symbol, "reason": f"daily_limit_reached ({max_removals})"})
        logger.info("thesis_removal_skipped", symbol=symbol, reason="daily_limit_reached")
        return removals_today

    removal_reason = f"Thesis invalidated: {reason}"
    success = remove_symbol_from_watchlist(storage, item_id, symbol, removal_reason)
    if not success:
        return removals_today

    removals_today += 1
    invalidated_at_str = to_iso_string(invalidated_at)
    results["removed"].append({"symbol": symbol, "reason": reason, "invalidated_at": invalidated_at_str})
    log_thesis_action(
        "process_invalidated_theses",
        symbol,
        "removed_from_watchlist",
        {"invalidation_reason": reason, "invalidated_at": invalidated_at_str},
    )
    logger.info("thesis_removal_completed", symbol=symbol, reason=reason)
    return removals_today


def archive_strategies_for_symbol(
    symbol: str,
    thesis_reason: str,
    invalidated_at: Any,
    strategy_storage: StrategyStorage,
    results: dict[str, Any],
) -> None:
    """Archive all active strategies for a symbol with thesis invalidation reason.

    Args:
        symbol: Stock symbol
        thesis_reason: Reason thesis was invalidated
        invalidated_at: When the thesis was invalidated
        strategy_storage: StrategyStorage instance
        results: Mutable results dict updated in place
    """
    strategies = get_active_strategies_for_symbol(strategy_storage, symbol)
    invalidated_at_str = to_iso_string(invalidated_at)

    for strategy in strategies:
        strategy_id = strategy["id"]
        strategy_name = strategy["name"]
        archive_reason = f"Thesis invalidated: {thesis_reason}"

        try:
            strategy_storage.archive_strategy(strategy_id, archive_reason)
            results["strategies_archived"] += 1
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
            results["details"].append({
                "symbol": symbol,
                "strategy_id": strategy_id,
                "strategy_name": strategy_name,
            })
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
