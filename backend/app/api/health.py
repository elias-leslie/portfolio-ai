"""Health check endpoints for portfolio-ai.

This module provides comprehensive health checks for monitoring
system status, dependencies, and service availability including multi-source data fetching.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field

from ..logging_config import get_logger
from ..middleware.cache import clear_cache
from ..middleware.cache import get_cache_stats as get_response_cache_stats
from ..storage import get_storage
from ..utils.health_service import (
    AgentStats,
    APIKeyStatusInfo,
    APIQuotaInfo,
    CacheStats,
    CeleryWorkerStatus,
    CheckResult,
    DayBarFreshnessInfo,
    DiskUsageInfo,
    HealthCheckService,
    SourceHealthCheck,
    WatchlistStats,
)
from ..utils.health_workflows import WorkflowHealthInfo

logger = get_logger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


# Helper functions for status page enhancement
async def get_data_freshness_summary() -> dict[str, Any]:
    """Get summary of data freshness status from last check.

    Returns:
        Dict with last_check, tables_checked, fresh, stale, critical counts
    """
    storage = get_storage()

    try:
        # Query maintenance_log for recent check_all_data_freshness runs
        query = """
            SELECT summary, started_at, status
            FROM maintenance_log
            WHERE task_name = 'check_all_data_freshness'
            ORDER BY started_at DESC
            LIMIT 1
        """

        with storage.connection() as conn:
            result = conn.execute(query).fetchone()

        if not result:
            return {
                "last_check": None,
                "status": "no_data",
                "message": "No freshness checks have been run yet",
            }

        # Unpack result with proper types
        summary_json = result[0]  # Can be str, dict, or None
        started_at = result[1]  # Should be datetime or None
        status = result[2]  # Should be str

        # Parse summary JSON
        if isinstance(summary_json, str):
            summary = json.loads(summary_json)
        elif isinstance(summary_json, dict):
            summary = summary_json
        else:
            summary = {}

        return {
            "last_check": started_at.isoformat() if isinstance(started_at, datetime) else None,
            "status": str(status) if status else "unknown",
            "tables_checked": summary.get("tables_checked", 0),
            "fresh": summary.get("fresh", 0),
            "stale": summary.get("stale", 0),
            "critical": summary.get("critical", 0),
            "remediations_triggered": summary.get("remediations_triggered", 0),
        }

    except Exception as e:
        logger.error("get_data_freshness_summary_failed", error=str(e))
        return {"last_check": None, "status": "error", "error": str(e)}


async def get_recent_remediations(hours: int = 24) -> list[dict[str, Any]]:
    """Get recent auto-remediation actions.

    Args:
        hours: Time window in hours (default: 24)

    Returns:
        List of recent remediation events
    """
    storage = get_storage()

    try:
        # Query maintenance_log for remediation triggers (last N hours)
        # Note: Using f-string for INTERVAL as parameter binding doesn't work with INTERVAL multiplication
        query = f"""
            SELECT task_name, started_at, status, summary, error_message
            FROM maintenance_log
            WHERE task_name LIKE 'data_freshness_alert_%'
            AND started_at > NOW() - INTERVAL '{hours} hours'
            ORDER BY started_at DESC
            LIMIT 20
        """

        with storage.connection() as conn:
            result = conn.execute(query).fetchall()

        remediations = []
        for row in result:
            # Unpack row with explicit types
            task_name_val = row[0]  # str | int | float | None
            started_at_val = row[1]  # datetime or other DatabaseValue
            status_val = row[2]  # str | int | float | None
            summary_json_val = row[3]  # str | dict | None
            error_message_val = row[4]  # str | None

            # Extract table name from task_name (format: data_freshness_alert_TABLE_NAME)
            if isinstance(task_name_val, str):
                table_name = task_name_val.replace("data_freshness_alert_", "")
            else:
                table_name = "unknown"

            # Parse summary
            summary = {}
            if summary_json_val:
                if isinstance(summary_json_val, str):
                    try:
                        summary = json.loads(summary_json_val)
                    except json.JSONDecodeError:
                        summary = {}
                elif isinstance(summary_json_val, dict):
                    summary = summary_json_val

            remediations.append(
                {
                    "table_name": table_name,
                    "triggered_at": started_at_val.isoformat()
                    if isinstance(started_at_val, datetime)
                    else None,
                    "status": str(status_val) if status_val else "unknown",
                    "age_hours": summary.get("age_hours"),
                    "threshold_hours": summary.get("threshold_hours"),
                    "reason": summary.get("reason"),
                    "error_message": str(error_message_val) if error_message_val else None,
                }
            )

        return remediations

    except Exception as e:
        logger.error("get_recent_remediations_failed", error=str(e))
        return []


# API Response Models
class HealthCheckResponse(BaseModel):
    """Complete health check response."""

    status: Literal["healthy", "degraded", "down"]
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    version: str = "1.0.0"
    uptime_seconds: int
    checks: dict[str, CheckResult]
    sources: dict[str, SourceHealthCheck] = Field(default_factory=dict)
    services: dict[str, Any] = Field(
        default_factory=dict,
        description="Service process status (backend, hatchet worker, frontend, redis)",
    )
    cache_stats: CacheStats | None = None
    agent_stats: AgentStats | None = None
    watchlist_stats: WatchlistStats | None = None
    api_quotas: list[APIQuotaInfo] = Field(default_factory=list)
    workflow_health: WorkflowHealthInfo | None = None


class DetailedHealthCheckResponse(HealthCheckResponse):
    """Extended health check response with additional system details."""

    day_bars_freshness: list[DayBarFreshnessInfo] = Field(default_factory=list)
    celery_worker: CeleryWorkerStatus | None = None  # Backward compat field name
    api_keys: list[APIKeyStatusInfo] = Field(default_factory=list)
    disk_usage: DiskUsageInfo | None = None
    workflow_metrics: dict[str, Any] = Field(
        default_factory=dict,
        description="Workflow metrics for last 7 days",
    )
    data_freshness_status: dict[str, Any] = Field(
        default_factory=dict,
        description="Pipeline execution status from last freshness check",
    )
    recent_remediations: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Recent auto-remediation actions (last 24h)",
    )


class DeletionRate(BaseModel):
    """Deletion rate monitoring response."""

    status: Literal["ok", "warning", "critical"]
    time_window_hours: int
    deletions_by_table: dict[str, int]
    total_deletions: int
    alert_threshold_warning: int = 10
    alert_threshold_critical: int = 100
    message: str


class ResponseCacheStats(BaseModel):
    """Response cache statistics."""

    enabled: bool
    size: int
    max_size: int
    ttl_default: int
    hits: int
    misses: int
    hit_rate: float
    invalidations: int


class CacheClearResponse(BaseModel):
    """Response for cache clear operation."""

    status: str
    cleared_entries: int
    message: str


# Create singleton health check service instance
health_service = HealthCheckService()


@router.get("", response_model=HealthCheckResponse)
async def health_check(response: Response) -> HealthCheckResponse:
    """Comprehensive health check endpoint.

    Returns health status, uptime, and metrics for all system components including
    multi-source data fetching health (yfinance, polygon, etc).
    Returns HTTP 503 if database is down, HTTP 200 otherwise.
    """
    result = health_service.perform_health_check()

    # Set appropriate HTTP status code
    if result["status"] == "down":
        response.status_code = 503

    # Build source status summary for logging
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
    """Comprehensive health check endpoint with additional system details.

    Returns detailed health status including:
    - All standard health checks (database, sources, services, etc.)
    - Day bars data freshness per symbol
    - Hatchet worker status
    - API key configuration status
    - Disk usage statistics
    - Data freshness monitoring status (pipeline execution)
    - Recent auto-remediation activity

    Returns HTTP 503 if database is down, HTTP 200 otherwise.
    """
    result = health_service.perform_detailed_health_check()

    # Set appropriate HTTP status code
    if result["status"] == "down":
        response.status_code = 503

    # Add pipeline execution and remediation data
    result["data_freshness_status"] = await get_data_freshness_summary()
    result["recent_remediations"] = await get_recent_remediations()

    logger.info(
        "detailed_health_check_endpoint",
        status=result["status"],
        day_bars_symbols=len(result["day_bars_freshness"]),
        celery_active=result["celery_worker"].active if result["celery_worker"] else False,
        api_keys_configured=sum(1 for k in result["api_keys"] if k.configured),
        freshness_status=result["data_freshness_status"].get("status"),
        remediations_count=len(result["recent_remediations"]),
    )

    return DetailedHealthCheckResponse(**result)


@router.get("/simple")
async def simple_health_check() -> dict[str, str]:
    """Simple health check endpoint (legacy compatibility).

    Returns:
        Simple status dict
    """
    return {"status": "healthy"}


@router.get("/deletion-rate", response_model=DeletionRate)
async def get_deletion_rate(hours: int = 1) -> DeletionRate:
    """Monitor deletion rate for incident detection.

    Created: 2025-11-10 (Response to Nov 9 deletion incident)

    Tracks deletions from critical tables to detect mass deletion events
    that may indicate data loss incidents, migration issues, or bugs.

    Alert thresholds:
    - Warning: >10 deletions in time window
    - Critical: >100 deletions in time window

    Args:
        hours: Time window in hours (default: 1)

    Returns:
        Deletion rate summary with alert status
    """
    storage = get_storage()

    try:
        # Query deletion_audit table (requires migration 024)
        query = """
        SELECT
            table_name,
            COUNT(*) as deletion_count
        FROM deletion_audit
        WHERE deleted_at > NOW() - INTERVAL '1 hour' * ?
        GROUP BY table_name
        ORDER BY deletion_count DESC
        """

        with storage.connection() as conn:
            result = conn.execute(query, [hours]).pl()

        # Build deletion summary
        deletions_by_table = {}
        if not result.is_empty():
            for row in result.iter_rows(named=True):
                deletions_by_table[row["table_name"]] = row["deletion_count"]

        total_deletions = sum(deletions_by_table.values())

        # Determine alert status
        status: Literal["ok", "warning", "critical"]
        if total_deletions >= 100:
            status = "critical"
            message = f"🔴 CRITICAL: {total_deletions} deletions in last {hours}h (threshold: 100)"
        elif total_deletions >= 10:
            status = "warning"
            message = f"⚠️  WARNING: {total_deletions} deletions in last {hours}h (threshold: 10)"
        else:
            status = "ok"
            message = f"✅ OK: {total_deletions} deletions in last {hours}h"

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
        # If deletion_audit table doesn't exist (migration 024 not applied),
        # return OK status with explanation
        logger.warning("deletion_audit_check_failed", error=str(e))

        return DeletionRate(
            status="ok",
            time_window_hours=hours,
            deletions_by_table={},
            total_deletions=0,
            message=f"⚠️  Deletion auditing not enabled (migration 024 required): {e}",
        )


@router.get("/cache/stats", response_model=ResponseCacheStats)
async def get_cache_statistics() -> ResponseCacheStats:
    """Get response cache statistics.

    Returns cache size, hit rate, and other metrics for the response caching middleware.
    """
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
    """Clear all response cache entries.

    Clears the entire response cache, forcing fresh data fetches for all cached endpoints.
    Use this when you need to ensure all data is up-to-date.
    """
    cleared_count = clear_cache()

    logger.info(
        "cache_cleared",
        cleared_entries=cleared_count,
    )

    return CacheClearResponse(
        status="success",
        cleared_entries=cleared_count,
        message=f"Cleared {cleared_count} cache entries",
    )
