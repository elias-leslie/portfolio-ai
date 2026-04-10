"""Health check endpoints for portfolio-ai."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from ..logging_config import get_logger
from ..middleware.cache import clear_cache
from ..middleware.cache import get_cache_stats as get_response_cache_stats
from ..storage import get_storage
from ..utils.health_service import (
    AgentStats,
    APIKeyStatus,
    APIQuotaInfo,
    CacheStats,
    CheckResult,
    DayBarFreshness,
    DiskUsageInfo,
    HealthCheckService,
    SourceHealthCheck,
    WatchlistStats,
    WorkerInfo,
)
from ..utils.health_workflows import WorkflowHealthInfo

logger = get_logger(__name__)
router = APIRouter(prefix="/health", tags=["health"])

_state: dict[str, HealthCheckService] = {}


def _get_health_service() -> HealthCheckService:
    """Lazy singleton for HealthCheckService to avoid DB connection at import time."""
    if "svc" not in _state:
        _state["svc"] = HealthCheckService()
    return _state["svc"]

FRESHNESS_TASK_NAME = "check_all_data_freshness"
FRESHNESS_ALERT_PREFIX = "data_freshness_alert_"
DEFAULT_HOURS_WINDOW = 24
DEFAULT_STALE_RUN_HOURS = 2
MAX_RECENT_REMEDIATIONS = 100
MAX_RETURNED_REMEDIATIONS = 20
MAX_STALE_RUNS = 50
DELETION_RATE_WARNING_THRESHOLD = 10
DELETION_RATE_CRITICAL_THRESHOLD = 100
STATUS_OK = "ok"
STATUS_WARNING = "warning"
STATUS_CRITICAL = "critical"
STATUS_DOWN = "down"
STATUS_SUCCESS = "success"
STATUS_UNKNOWN = "unknown"
STATUS_NO_DATA = "no_data"
STATUS_ERROR = "error"
MESSAGE_NO_FRESHNESS_DATA = "No freshness checks have been run yet"
RUNNING_STATUS = "running"

DATA_FRESHNESS_QUERY = """
    SELECT summary, started_at, status
    FROM maintenance_log
    WHERE task_name = 'check_all_data_freshness'
    ORDER BY started_at DESC
    LIMIT 1
"""

RECENT_REMEDIATIONS_QUERY = """
    SELECT task_name, started_at, status, summary, error_message
    FROM maintenance_log
    WHERE task_name LIKE 'data_freshness_alert_%%'
    AND started_at > NOW() - make_interval(hours => ?)
    ORDER BY started_at DESC
    LIMIT 100
"""

STALE_MAINTENANCE_RUNS_QUERY = """
    SELECT task_name, started_at, dry_run
    FROM maintenance_log
    WHERE status = 'running'
      AND started_at < NOW() - make_interval(hours => ?)
      AND NOT EXISTS (
          SELECT 1
          FROM maintenance_log newer
          WHERE newer.task_name = maintenance_log.task_name
            AND newer.started_at > maintenance_log.started_at
      )
    ORDER BY started_at ASC
    LIMIT 50
"""

DELETION_RATE_QUERY = """
    SELECT
        table_name,
        COUNT(*) as deletion_count
    FROM deletion_audit
    WHERE deleted_at > NOW() - make_interval(hours => ?)
    GROUP BY table_name
    ORDER BY deletion_count DESC
"""


class HealthCheckResponse(BaseModel):
    status: Literal["healthy", "degraded", "down"]
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    version: str = "1.0.0"
    uptime_seconds: int
    checks: dict[str, CheckResult]
    sources: dict[str, SourceHealthCheck] = Field(default_factory=dict)
    services: dict[str, Any] = Field(default_factory=dict)
    cache_stats: CacheStats | None = None
    agent_stats: AgentStats | None = None
    watchlist_stats: WatchlistStats | None = None
    api_quotas: list[APIQuotaInfo] = Field(default_factory=list)
    workflow_health: WorkflowHealthInfo | None = None


class DetailedHealthCheckResponse(HealthCheckResponse):
    day_bars_freshness: list[DayBarFreshness] = Field(default_factory=list)
    worker: WorkerInfo | None = None
    api_keys: list[APIKeyStatus] = Field(default_factory=list)
    disk_usage: DiskUsageInfo | None = None
    workflow_metrics: dict[str, Any] = Field(default_factory=dict)
    data_freshness_status: dict[str, Any] = Field(default_factory=dict)
    recent_remediations: list[dict[str, Any]] = Field(default_factory=list)
    stale_maintenance_runs: list[dict[str, Any]] = Field(default_factory=list)


class DeletionRate(BaseModel):
    status: Literal["ok", "warning", "critical"]
    time_window_hours: int
    deletions_by_table: dict[str, int]
    total_deletions: int
    alert_threshold_warning: int = DELETION_RATE_WARNING_THRESHOLD
    alert_threshold_critical: int = DELETION_RATE_CRITICAL_THRESHOLD
    message: str


class ResponseCacheStats(BaseModel):
    enabled: bool
    size: int
    max_size: int
    ttl_default: int
    hits: int
    misses: int
    hit_rate: float
    invalidations: int


class CacheClearResponse(BaseModel):
    status: str
    cleared_entries: int
    message: str


def _parse_summary_json(summary_json: Any) -> dict[str, Any]:
    if isinstance(summary_json, str):
        try:
            parsed = json.loads(summary_json)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    if isinstance(summary_json, dict):
        return summary_json
    return {}


def _normalize_datetime(value: Any) -> datetime | None:
    return value if isinstance(value, datetime) else None


def _normalize_status(value: Any) -> str:
    return str(value) if value else STATUS_UNKNOWN


def _format_datetime(value: datetime | None) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None


def _format_table_count(count: int, label: str) -> str:
    return f"{count} table{'s' if count != 1 else ''} {label}"


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


def _get_remediation_resolution_state(
    *,
    table_name: str,
    triggered_at: datetime | None,
    freshness_status: str | None,
    freshness_started_at: datetime | None,
    freshness_summary: dict[str, Any],
) -> tuple[bool, str | None]:
    table_freshness = None
    details = freshness_summary.get("details")
    if isinstance(details, list):
        for detail in details:
            if isinstance(detail, dict) and detail.get("table_name") == table_name:
                table_freshness = detail
                break

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
    return task_name.replace(FRESHNESS_ALERT_PREFIX, "") if isinstance(task_name, str) else STATUS_UNKNOWN


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
        "age_hours": summary.get("age_hours"),
        "threshold_hours": summary.get("threshold_hours"),
        "reason": summary.get("reason"),
        "error_message": str(error_message) if error_message else None,
        "occurrence_count": 1,
        "resolved": resolved,
        "resolved_at": resolved_at,
    }


def _summarize_deletion_counts(result: Any) -> dict[str, int]:
    if result.is_empty():
        return {}
    return {
        row["table_name"]: row["deletion_count"]
        for row in result.iter_rows(named=True)
    }


def _build_deletion_rate_message(total_deletions: int, hours: int) -> tuple[Literal["ok", "warning", "critical"], str]:
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

        latest_freshness_summary, latest_freshness_started_at, latest_freshness_status = (
            _build_latest_freshness_state(latest_freshness_row)
        )
        remediations_by_table: dict[str, dict[str, Any]] = {}
        for row in result:
            table_name, remediation = _build_remediation_entry(
                row=row,
                freshness_status=latest_freshness_status,
                freshness_started_at=latest_freshness_started_at,
                freshness_summary=latest_freshness_summary,
            )
            existing = remediations_by_table.get(table_name)
            if existing:
                existing["occurrence_count"] = int(existing.get("occurrence_count", 1)) + 1
                continue
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
    result["recent_remediations"] = await get_recent_remediations()
    result["stale_maintenance_runs"] = await get_stale_maintenance_runs()
    logger.info(
        "detailed_health_check_endpoint",
        status=result["status"],
        day_bars_symbols=len(result["day_bars_freshness"]),
        worker_active=result["worker"].active if result["worker"] else False,
        api_keys_configured=sum(1 for k in result["api_keys"] if k.configured),
        freshness_status=result["data_freshness_status"].get("status"),
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
