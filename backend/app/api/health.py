"""Health check endpoints for portfolio-ai."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Response
from fastapi.concurrency import run_in_threadpool

from app.api.health_decision_data import (
    _build_automation_decision_domain,
    _build_household_decision_domain,
    _build_market_data_decision_domain,
    _build_prediction_macro_decision_domain,
    _build_source_decision_domain,
    _summarize_decision_data_domains,
    get_decision_data_health,
)
from app.api.health_models import (
    DATA_FRESHNESS_QUERY,
    DEFAULT_HOURS_WINDOW,
    DEFAULT_STALE_RUN_HOURS,
    DELETION_RATE_CRITICAL_THRESHOLD,
    DELETION_RATE_QUERY,
    DELETION_RATE_WARNING_THRESHOLD,
    FRESHNESS_ALERT_PREFIX,
    FRESHNESS_REMEDIATION_PREFIX,
    MAX_RETURNED_REMEDIATIONS,
    MESSAGE_NO_FRESHNESS_DATA,
    RECENT_REMEDIATIONS_QUERY,
    STALE_MAINTENANCE_RUNS_QUERY,
    STATUS_CRITICAL,
    STATUS_DOWN,
    STATUS_ERROR,
    STATUS_NO_DATA,
    STATUS_OK,
    STATUS_SUCCESS,
    STATUS_UNKNOWN,
    STATUS_WARNING,
    CacheClearResponse,
    DeletionRate,
    DetailedHealthCheckResponse,
    HealthCheckResponse,
    ResponseCacheStats,
    _format_datetime,
    _format_table_count,
    _normalize_datetime,
    _normalize_status,
    _parse_summary_json,
)
from app.logging_config import get_logger
from app.middleware.cache import clear_cache
from app.middleware.cache import get_cache_stats as get_response_cache_stats
from app.storage import get_storage
from app.utils.health_service import HealthCheckService

logger = get_logger(__name__)
router = APIRouter(prefix="/health", tags=["health"])
_state: dict[str, HealthCheckService] = {}
__all__ = [
    "_build_automation_decision_domain",
    "_build_freshness_summary_payload",
    "_build_household_decision_domain",
    "_build_market_data_decision_domain",
    "_build_prediction_macro_decision_domain",
    "_build_source_decision_domain",
    "_summarize_decision_data_domains",
    "get_decision_data_health",
]


def _get_health_service() -> HealthCheckService:
    """Lazy singleton avoids DB connection at import time."""
    if "svc" not in _state:
        _state["svc"] = HealthCheckService()
    return _state["svc"]


def _build_freshness_health(summary: dict[str, Any], check_status: str) -> tuple[str, str]:
    critical_count = int(summary.get("critical", 0) or 0)
    stale_count = int(summary.get("stale", 0) or 0)
    if check_status != STATUS_SUCCESS:
        return check_status, "Latest freshness check did not complete successfully"

    message_parts: list[str] = []
    if critical_count > 0:
        message_parts.append(_format_table_count(critical_count, "overdue"))
    if stale_count > 0:
        message_parts.append(_format_table_count(stale_count, "getting old"))

    if critical_count > 0:
        return STATUS_CRITICAL, "; ".join(message_parts)
    if stale_count > 0:
        return STATUS_WARNING, "; ".join(message_parts)
    return STATUS_SUCCESS, "All checked tables are current"


def _build_freshness_summary_payload(result: Any) -> dict[str, Any]:
    if not result:
        return {
            "last_check": None,
            "status": STATUS_NO_DATA,
            "message": MESSAGE_NO_FRESHNESS_DATA,
        }

    summary = _parse_summary_json(result[0])
    started_at = _normalize_datetime(result[1])
    check_status = _normalize_status(result[2])
    freshness_status, message = _build_freshness_health(summary, check_status)
    return {
        "last_check": _format_datetime(started_at),
        "status": freshness_status,
        "check_status": check_status,
        "message": message,
        "tables_checked": summary.get("tables_checked", 0),
        "fresh": summary.get("fresh", 0),
        "stale": summary.get("stale", 0),
        "critical": summary.get("critical", 0),
        "remediations_triggered": summary.get("remediations_triggered", 0),
    }


def _build_latest_freshness_state(row: Any) -> tuple[dict[str, Any], datetime | None, str | None]:
    if not row:
        return {}, None, None
    return (
        _parse_summary_json(row[0]),
        _normalize_datetime(row[1]),
        _normalize_status(row[2]),
    )


def _get_remediation_resolution_state(
    *,
    table_name: str,
    triggered_at: datetime | None,
    freshness_status: str | None,
    freshness_started_at: datetime | None,
    freshness_summary: dict[str, Any],
) -> tuple[bool, str | None]:
    details = freshness_summary.get("details")
    table_freshness = next(
        (
            detail
            for detail in details
            if isinstance(detail, dict) and detail.get("table_name") == table_name
        ),
        None,
    ) if isinstance(details, list) else None

    if (
        triggered_at is None
        or freshness_status != STATUS_SUCCESS
        or freshness_started_at is None
        or freshness_started_at <= triggered_at
    ):
        return False, None

    if isinstance(table_freshness, dict):
        if bool(table_freshness.get("is_stale")) or bool(table_freshness.get("is_critical")):
            return False, None
        return True, freshness_started_at.isoformat()

    if freshness_summary.get("stale", 0) != 0 or freshness_summary.get("critical", 0) != 0:
        return False, None
    return True, freshness_started_at.isoformat()


def _extract_table_name(task_name: Any) -> str:
    if not isinstance(task_name, str):
        return STATUS_UNKNOWN
    if task_name.startswith(FRESHNESS_ALERT_PREFIX):
        return task_name.removeprefix(FRESHNESS_ALERT_PREFIX)
    if task_name.startswith(FRESHNESS_REMEDIATION_PREFIX):
        return task_name.removeprefix(FRESHNESS_REMEDIATION_PREFIX)
    return STATUS_UNKNOWN


def _remediation_event_type(task_name: Any) -> str:
    if isinstance(task_name, str) and task_name.startswith(FRESHNESS_REMEDIATION_PREFIX):
        return "remediation"
    return "alert"


def _build_remediation_entry(
    *,
    row: Any,
    freshness_status: str | None,
    freshness_started_at: datetime | None,
    freshness_summary: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    task_name, started_at_raw, status_raw, summary_raw, error_message = row
    table_name = _extract_table_name(task_name)
    summary = _parse_summary_json(summary_raw)
    triggered_at = _normalize_datetime(started_at_raw)
    resolved, resolved_at = _get_remediation_resolution_state(
        table_name=table_name,
        triggered_at=triggered_at,
        freshness_status=freshness_status,
        freshness_started_at=freshness_started_at,
        freshness_summary=freshness_summary,
    )
    return table_name, {
        "table_name": table_name,
        "triggered_at": _format_datetime(triggered_at),
        "status": _normalize_status(status_raw),
        "event_type": _remediation_event_type(task_name),
        "age_hours": summary.get("age_hours"),
        "threshold_hours": summary.get("threshold_hours"),
        "reason": summary.get("reason"),
        "remediation_task_name": summary.get("remediation_task_name"),
        "workflow_run_id": summary.get("workflow_run_id"),
        "trigger_status": summary.get("trigger_status"),
        "error_message": str(error_message) if error_message else None,
        "occurrence_count": 1,
        "resolved": resolved,
        "resolved_at": resolved_at,
    }


def _summarize_deletion_counts(result: Any) -> dict[str, int]:
    if result.is_empty():
        return {}
    return {row["table_name"]: row["deletion_count"] for row in result.iter_rows(named=True)}


def _build_deletion_rate_message(
    total_deletions: int,
    hours: int,
) -> tuple[Literal["ok", "warning", "critical"], str]:
    if total_deletions >= DELETION_RATE_CRITICAL_THRESHOLD:
        return (
            STATUS_CRITICAL,
            f"🔴 CRITICAL: {total_deletions} deletions in last {hours}h (threshold: {DELETION_RATE_CRITICAL_THRESHOLD})",
        )
    if total_deletions >= DELETION_RATE_WARNING_THRESHOLD:
        return (
            STATUS_WARNING,
            f"⚠️  WARNING: {total_deletions} deletions in last {hours}h (threshold: {DELETION_RATE_WARNING_THRESHOLD})",
        )
    return STATUS_OK, f"✅ OK: {total_deletions} deletions in last {hours}h"


async def get_data_freshness_summary() -> dict[str, Any]:
    storage = get_storage()
    try:
        with storage.connection() as conn:
            result = conn.execute(DATA_FRESHNESS_QUERY).fetchone()
        return _build_freshness_summary_payload(result)
    except Exception as e:
        logger.error("get_data_freshness_summary_failed", error=str(e), exc_info=True)
        return {"last_check": None, "status": STATUS_ERROR, "error": str(e)}


async def get_recent_remediations(hours: int = DEFAULT_HOURS_WINDOW) -> list[dict[str, Any]]:
    storage = get_storage()
    try:
        with storage.connection() as conn:
            result = conn.execute(RECENT_REMEDIATIONS_QUERY, [hours]).fetchall()
            latest_freshness_row = conn.execute(DATA_FRESHNESS_QUERY).fetchone()

        latest_summary, latest_started_at, latest_status = _build_latest_freshness_state(
            latest_freshness_row
        )
        remediations_by_table: dict[str, dict[str, Any]] = {}
        for row in result:
            table_name, remediation = _build_remediation_entry(
                row=row,
                freshness_status=latest_status,
                freshness_started_at=latest_started_at,
                freshness_summary=latest_summary,
            )
            existing = remediations_by_table.get(table_name)
            if existing:
                existing["occurrence_count"] = int(existing.get("occurrence_count", 1)) + 1
            else:
                remediations_by_table[table_name] = remediation

        return list(remediations_by_table.values())[:MAX_RETURNED_REMEDIATIONS]
    except Exception as e:
        logger.error("get_recent_remediations_failed", error=str(e), exc_info=True)
        return []


async def get_stale_maintenance_runs(hours: int = DEFAULT_STALE_RUN_HOURS) -> list[dict[str, Any]]:
    storage = get_storage()
    try:
        if not isinstance(hours, int) or hours < 0:
            raise ValueError(f"hours must be a non-negative integer, got {hours}")
        with storage.connection() as conn:
            result = conn.execute(STALE_MAINTENANCE_RUNS_QUERY, [hours]).fetchall()
        return [
            {
                "task_name": str(task_name),
                "started_at": _format_datetime(_normalize_datetime(started_at)),
                "dry_run": bool(dry_run),
            }
            for task_name, started_at, dry_run in result
        ]
    except Exception as e:
        logger.error("get_stale_maintenance_runs_failed", error=str(e), exc_info=True)
        return []


def _set_down_status(response: Response, result: dict[str, Any]) -> None:
    if result["status"] == STATUS_DOWN:
        response.status_code = 503


@router.get("", response_model=HealthCheckResponse)
async def health_check(response: Response) -> HealthCheckResponse:
    result = await run_in_threadpool(_get_health_service().perform_health_check)
    _set_down_status(response, result)
    source_status_summary = {name: src.status for name, src in result["sources"].items()}
    logger.info(
        "health_check_performed",
        status=result["status"],
        uptime_seconds=result["uptime_seconds"],
        database_status=result["checks"]["database"].status,
        sources=source_status_summary,
        num_sources=len(result["sources"]),
    )
    return HealthCheckResponse(**result)


@router.get("/detailed", response_model=DetailedHealthCheckResponse)
async def detailed_health_check(response: Response) -> DetailedHealthCheckResponse:
    result = await run_in_threadpool(_get_health_service().perform_detailed_health_check)
    _set_down_status(response, result)
    result["data_freshness_status"] = await get_data_freshness_summary()
    result["decision_data_health"] = await get_decision_data_health(
        health_result=result,
        data_freshness_status=result["data_freshness_status"],
    )
    if (
        result.get("status") == "healthy"
        and result["decision_data_health"].get("status") in {"degraded", "critical", "unknown"}
    ):
        result["status"] = "degraded"
    result["recent_remediations"] = await get_recent_remediations()
    result["stale_maintenance_runs"] = await get_stale_maintenance_runs()
    logger.info(
        "detailed_health_check_endpoint",
        status=result["status"],
        day_bars_symbols=len(result["day_bars_freshness"]),
        worker_active=result["worker"].active if result["worker"] else False,
        api_keys_configured=sum(1 for k in result["api_keys"] if k.configured),
        freshness_status=result["data_freshness_status"].get("status"),
        decision_data_status=result["decision_data_health"].get("status"),
        remediations_count=len(result["recent_remediations"]),
        stale_maintenance_runs=len(result["stale_maintenance_runs"]),
    )
    return DetailedHealthCheckResponse(**result)


@router.get("/simple")
async def simple_health_check() -> dict[str, str]:
    return {"status": "healthy"}


@router.get("/deletion-rate", response_model=DeletionRate)
async def get_deletion_rate(hours: int = 1) -> DeletionRate:
    storage = get_storage()
    try:
        with storage.connection() as conn:
            result = conn.execute(DELETION_RATE_QUERY, [hours]).pl()
        deletions_by_table = _summarize_deletion_counts(result)
        total_deletions = sum(deletions_by_table.values())
        status, message = _build_deletion_rate_message(total_deletions, hours)
        logger.info(
            "deletion_rate_check",
            status=status,
            total_deletions=total_deletions,
            time_window_hours=hours,
            deletions_by_table=deletions_by_table,
        )
        return DeletionRate(
            status=status,
            time_window_hours=hours,
            deletions_by_table=deletions_by_table,
            total_deletions=total_deletions,
            message=message,
        )
    except Exception as e:
        logger.warning("deletion_audit_check_failed", error=str(e))
        return DeletionRate(
            status=STATUS_OK,
            time_window_hours=hours,
            deletions_by_table={},
            total_deletions=0,
            message=f"⚠️  Deletion auditing not enabled (migration 024 required): {e}",
        )


@router.get("/cache/stats", response_model=ResponseCacheStats)
async def get_cache_statistics() -> ResponseCacheStats:
    stats = get_response_cache_stats()
    logger.info(
        "cache_stats_retrieved",
        cache_size=stats["size"],
        hit_rate=stats["hit_rate"],
        total_hits=stats["hits"],
        total_misses=stats["misses"],
    )
    return ResponseCacheStats(**stats)


@router.post("/cache/clear", response_model=CacheClearResponse)
async def clear_response_cache() -> CacheClearResponse:
    cleared_count = clear_cache()
    logger.info("cache_cleared", cleared_entries=cleared_count)
    return CacheClearResponse(
        status=STATUS_SUCCESS,
        cleared_entries=cleared_count,
        message=f"Cleared {cleared_count} cache entries",
    )
