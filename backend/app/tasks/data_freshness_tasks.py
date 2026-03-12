"""Task for automated data freshness monitoring and refresh.

VISION.md requirement: <24 hour data freshness for all monitored symbols
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import TypedDict

from app.logging_config import get_logger
from app.services.data_freshness_service import check_all_tables_freshness
from app.services.maintenance_tracker import record_maintenance_completion, record_maintenance_start
from app.storage import get_storage
from app.storage.connection import get_connection_manager
from app.tasks.watchlist_tasks import refresh_watchlist_scores_task

logger = get_logger(__name__)

_STALE_SECONDS = 24 * 3600


def _fetch_symbol_rows() -> list[tuple[str | int | float | bool | None, ...]]:
    """Return (symbol, last_fetched) rows from the watchlist."""
    storage = get_storage()
    with storage.connection() as conn:
        return conn.execute(
            """
            SELECT wi.symbol, MAX(ws.fetched_at) as last_fetched
            FROM watchlist_items wi
            LEFT JOIN watchlist_snapshots_v ws ON wi.id = ws.item_id
            GROUP BY wi.symbol
            """
        ).fetchall()


def _is_stale(last_fetched: object, now: dt.datetime) -> bool:
    if last_fetched is None:
        return True
    if isinstance(last_fetched, dt.datetime):
        return (now - last_fetched).total_seconds() > _STALE_SECONDS
    return True


class _FreshnessResult(TypedDict):
    symbols_checked: int
    stale_found: int
    stale_symbols: list[str]


def _check_data_freshness_impl() -> _FreshnessResult:
    """Identify stale watchlist symbols."""
    rows = _fetch_symbol_rows()
    if not rows:
        return {"symbols_checked": 0, "stale_found": 0, "stale_symbols": []}

    now = dt.datetime.now(dt.UTC)
    stale: list[str] = [str(r[0]) for r in rows if r[0] and _is_stale(r[1], now)]
    return {"symbols_checked": len(rows), "stale_found": len(stale), "stale_symbols": stale}


def _refresh_stale(stale_symbols: list[str]) -> tuple[int, int]:
    """Trigger watchlist refresh; return (refreshed, failed)."""
    try:
        refresh_watchlist_scores_task(account_id="default")
        logger.info("watchlist_refreshed", stale_count=len(stale_symbols))
        return len(stale_symbols), 0
    except Exception as e:
        logger.error("watchlist_refresh_failed", error=str(e), exc_info=True)
        return 0, len(stale_symbols)


def _error_response(e: Exception, duration: float) -> dict[str, object]:
    return {"status": "failed", "error": str(e), "execution_time_sec": round(duration, 2)}


def maintain_data_freshness() -> dict[str, object]:
    """Check all watchlist symbols for freshness and auto-refresh stale data.

    VISION.md requirement: <24 hour data freshness for all monitored tables
    """
    task_id = str(uuid.uuid4())
    start = dt.datetime.now(dt.UTC)
    log_id = record_maintenance_start(task_name="maintain_data_freshness", dry_run=False)
    logger.info("maintain_data_freshness_started", task_id=task_id)

    try:
        freshness = _check_data_freshness_impl()
        stale = freshness["stale_symbols"]

        if not stale:
            result: dict[str, object] = {
                "status": "success",
                "symbols_checked": freshness["symbols_checked"],
                "stale_found": 0,
                "refreshed": 0,
                "failed": 0,
                "execution_time_sec": round((dt.datetime.now(dt.UTC) - start).total_seconds(), 2),
            }
            record_maintenance_completion(log_id, "success", result, None)
            logger.info("maintain_data_freshness_completed_no_stale", **result)
            return result

        refreshed, failed = _refresh_stale(stale)
        result = {
            "status": "success",
            "symbols_checked": freshness["symbols_checked"],
            "stale_found": len(stale),
            "refreshed": refreshed,
            "failed": failed,
            "execution_time_sec": round((dt.datetime.now(dt.UTC) - start).total_seconds(), 2),
        }
        record_maintenance_completion(log_id, "success", result, None)
        logger.info("maintain_data_freshness_completed", **result)
        return result

    except Exception as e:
        duration = (dt.datetime.now(dt.UTC) - start).total_seconds()
        error_result = _error_response(e, duration)
        record_maintenance_completion(log_id, "error", error_result, str(e))
        logger.error("maintain_data_freshness_failed", task_id=task_id, error=str(e), duration_seconds=round(duration, 2))
        return error_result


def check_all_data_freshness(auto_remediate: bool = True) -> dict[str, object]:
    """Check all critical tables for freshness; auto-remediate if auto_remediate=True.

    VISION.md requirement: <24 hour data freshness for all monitored tables
    """
    task_id = str(uuid.uuid4())
    start = dt.datetime.now(dt.UTC)
    logger.info("check_all_data_freshness_started", task_id=task_id, auto_remediate=auto_remediate)
    log_id = record_maintenance_start(task_name="check_all_data_freshness", dry_run=False)

    try:
        r = check_all_tables_freshness(get_connection_manager(), auto_remediate=auto_remediate)
        duration = (dt.datetime.now(dt.UTC) - start).total_seconds()
        response: dict[str, object] = {
            "status": "success",
            "tables_checked": r["tables_checked"],
            "fresh": r["fresh"],
            "stale": r["stale"],
            "critical": r["critical"],
            "alerts_created": r["alerts_created"],
            "remediations_triggered": r.get("remediations_triggered", 0),
            "execution_time_sec": round(duration, 2),
        }
        record_maintenance_completion(log_id=log_id, status="success", summary=response, error_message=None)
        logger.info("check_all_data_freshness_completed", **response)
        return response

    except Exception as e:
        duration = (dt.datetime.now(dt.UTC) - start).total_seconds()
        record_maintenance_completion(
            log_id=log_id, status="error",
            summary={"execution_time_sec": round(duration, 2)}, error_message=str(e),
        )
        logger.error("check_all_data_freshness_failed", task_id=task_id, error=str(e), duration_seconds=round(duration, 2))
        return _error_response(e, duration)
