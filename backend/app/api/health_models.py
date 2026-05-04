"""Shared health endpoint models, constants, and coercion helpers."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.utils.health_service import (
    AgentStats,
    APIKeyStatus,
    APIQuotaInfo,
    CacheStats,
    CheckResult,
    DayBarFreshness,
    DiskUsageInfo,
    SourceHealthCheck,
    WatchlistStats,
    WorkerInfo,
)
from app.utils.health_workflows import WorkflowHealthInfo

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
    decision_data_health: dict[str, Any] = Field(default_factory=dict)
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


def _read_field(obj: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(obj, dict) and name in obj:
            return obj[name]
        if hasattr(obj, name):
            return getattr(obj, name)
    return default


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _as_bool(value: Any) -> bool:
    return bool(value)


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        normalized = f"{value[:-1]}+00:00" if value.endswith("Z") else value
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return None


def _format_any_datetime(value: Any) -> str | None:
    parsed = _parse_datetime(value)
    return parsed.isoformat() if parsed else None


def _format_table_count(count: int, label: str) -> str:
    return f"{count} table{'s' if count != 1 else ''} {label}"
