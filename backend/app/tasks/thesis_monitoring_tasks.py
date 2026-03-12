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

from typing import Any

from ..logging_config import get_logger
from ..rules.loader import get_rules
from ..services.preferences_service import get_automation_preferences
from ..services.thesis_service import ThesisService
from ..storage import PortfolioStorage
from ..storage.connection import get_connection_manager
from ..strategies.storage import StrategyStorage
from .thesis_monitoring_helpers import (
    archive_strategies_for_symbol,
    get_invalidated_symbols_last_24h,
    get_invalidated_theses_last_24h,
    get_portfolio_symbols,
    log_thesis_action,
    process_single_invalidated_thesis,
    process_symbol_health,
)

# Re-export helpers so existing importers remain unaffected
__all__ = [
    "archive_strategies_for_invalidated_theses_task",
    "get_portfolio_symbols",
    "log_thesis_action",
    "monitor_thesis_health_task",
    "process_invalidated_theses_task",
]

logger = get_logger(__name__)


def monitor_thesis_health_task() -> dict[str, Any]:
    """Daily thesis health check - evaluate invalidation triggers for all active theses.

    Scheduled: Daily 03:00 UTC (after fear/greed calculation, before strategy tasks)

    Returns:
        Dict with status, theses_checked, triggers_found, invalidated counts
    """
    automation = get_automation_preferences()
    if not bool(automation["thesis_generation_enabled"]["enabled"]):
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
        with conn_mgr.connection() as conn:
            result = conn.execute("SELECT symbol FROM watchlist_thesis WHERE status = 'active'")
            symbols = [str(row[0]) for row in result.fetchall()]

        logger.info("thesis_health_check_started", active_theses=len(symbols))

        for symbol in symbols:
            results["theses_checked"] += 1
            process_symbol_health(symbol, thesis_service, results)

        logger.info(
            "thesis_health_check_completed",
            checked=results["theses_checked"],
            triggers_found=results["triggers_found"],
            invalidated=results["invalidated"],
            flagged=results["flagged"],
        )
        return {"status": "success", **results}

    except Exception as e:
        logger.error("thesis_health_check_failed", error=str(e), exc_info=True)
        return {"status": "error", "error": str(e)}


def process_invalidated_theses_task() -> dict[str, Any]:
    """Process invalidated theses - remove from watchlist based on rules config.

    Scheduled: Daily 03:15 UTC. Respects auto_remove_on_invalidation and
    exclude_portfolio_holdings from rules.yaml.

    Returns:
        Dict with status, processed count, removed/skipped details
    """
    rules = get_rules()
    automation = get_automation_preferences()
    auto_remove = bool(automation["auto_remove_on_invalidation"]["enabled"])
    exclude_portfolio = rules.watchlist_management.exclude_portfolio_holdings
    max_removals = rules.watchlist_management.max_daily_removals
    storage = PortfolioStorage()
    results: dict[str, Any] = {
        "auto_remove_enabled": auto_remove,
        "processed": 0,
        "removed": [],
        "skipped_portfolio": [],
        "skipped_disabled": [],
    }

    try:
        invalidated = get_invalidated_theses_last_24h()
        logger.info("process_invalidated_started", count=len(invalidated))

        if not invalidated:
            return {"status": "success", "message": "No invalidated theses to process"}

        portfolio_symbols = get_portfolio_symbols(storage) if exclude_portfolio else set()
        removals_today = 0

        for row in invalidated:
            removals_today = process_single_invalidated_thesis(
                row, portfolio_symbols, auto_remove, max_removals, removals_today, storage, results
            )

        logger.info(
            "process_invalidated_completed",
            processed=results["processed"],
            removed=len(results["removed"]),
            skipped_portfolio=len(results["skipped_portfolio"]),
            skipped_disabled=len(results["skipped_disabled"]),
        )
        return {"status": "success", **results}

    except Exception as e:
        logger.error("process_invalidated_failed", error=str(e), exc_info=True)
        return {"status": "error", "error": str(e)}


def archive_strategies_for_invalidated_theses_task() -> dict[str, Any]:
    """Archive strategies when thesis invalidated (thesis invalidation triggers strategy lifecycle).

    Scheduled: Daily 03:30 UTC (after thesis processing)

    The design principle: Thesis invalidation drives strategy lifecycle, not the other way around.
    When a thesis is invalidated, all active strategies for that symbol should be archived.

    Returns:
        Dict with status, strategies_archived count, details
    """
    strategy_storage = StrategyStorage()
    results: dict[str, Any] = {
        "symbols_processed": 0,
        "strategies_archived": 0,
        "details": [],
    }

    try:
        invalidated = get_invalidated_symbols_last_24h()
        logger.info("archive_strategies_started", invalidated_count=len(invalidated))

        for row in invalidated:
            symbol = str(row[0])
            thesis_reason = str(row[1]) if row[1] else "Unknown"
            invalidated_at = row[2]
            results["symbols_processed"] += 1
            archive_strategies_for_symbol(
                symbol, thesis_reason, invalidated_at, strategy_storage, results
            )

        logger.info(
            "archive_strategies_completed",
            symbols_processed=results["symbols_processed"],
            strategies_archived=results["strategies_archived"],
        )
        return {"status": "success", **results}

    except Exception as e:
        logger.error("archive_strategies_failed", error=str(e), exc_info=True)
        return {"status": "error", "error": str(e)}
