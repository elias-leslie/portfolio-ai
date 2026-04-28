"""Health check endpoints for portfolio-ai."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app.services.household_finance_service import HouseholdFinanceService
from app.services.market_prediction_committee_service import MarketPredictionCommitteeService

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


DecisionDomainStatus = Literal[
    "current",
    "aging",
    "stale",
    "missing",
    "disabled",
    "quota_limited",
    "degraded",
    "unknown",
]
DecisionDomainSeverity = Literal["healthy", "warning", "critical", "unknown"]


class DecisionDataDomain(BaseModel):
    key: str
    label: str
    status: DecisionDomainStatus
    severity: DecisionDomainSeverity
    message: str
    last_updated: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)


class DecisionDataHealth(BaseModel):
    status: Literal["healthy", "degraded", "critical", "unknown"]
    message: str
    domains: list[DecisionDataDomain] = Field(default_factory=list)


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
        "details": summary.get("details", []),
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


def _decision_domain(
    *,
    key: str,
    label: str,
    status: DecisionDomainStatus,
    severity: DecisionDomainSeverity,
    message: str,
    last_updated: Any = None,
    evidence: dict[str, Any] | None = None,
) -> DecisionDataDomain:
    return DecisionDataDomain(
        key=key,
        label=label,
        status=status,
        severity=severity,
        message=message,
        last_updated=_format_any_datetime(last_updated),
        evidence=evidence or {},
    )


def _build_market_data_decision_domain(
    freshness_status: dict[str, Any] | None,
) -> DecisionDataDomain:
    freshness_status = freshness_status or {}
    status = str(freshness_status.get("status") or STATUS_UNKNOWN)
    details = freshness_status.get("details")
    decision_symbol_detail = None
    if isinstance(details, list):
        decision_symbol_detail = next(
            (
                detail
                for detail in details
                if isinstance(detail, dict) and detail.get("table_name") == "decision_symbol_day_bars"
            ),
            None,
        )
    evidence = {
        "fresh": _as_int(freshness_status.get("fresh")),
        "stale": _as_int(freshness_status.get("stale")),
        "critical": _as_int(freshness_status.get("critical")),
        "tables_checked": _as_int(freshness_status.get("tables_checked")),
        "check_status": freshness_status.get("check_status"),
    }
    if isinstance(decision_symbol_detail, dict):
        evidence["decision_symbol_day_bars"] = decision_symbol_detail
    if status == STATUS_SUCCESS:
        return _decision_domain(
            key="market_data",
            label="Market Data",
            status="current",
            severity="healthy",
            message=str(freshness_status.get("message") or "Market data tables are current."),
            last_updated=freshness_status.get("last_check"),
            evidence=evidence,
        )
    if status == STATUS_WARNING:
        return _decision_domain(
            key="market_data",
            label="Market Data",
            status="aging",
            severity="warning",
            message=str(freshness_status.get("message") or "Some market data tables are getting old."),
            last_updated=freshness_status.get("last_check"),
            evidence=evidence,
        )
    if status in {STATUS_CRITICAL, STATUS_NO_DATA}:
        return _decision_domain(
            key="market_data",
            label="Market Data",
            status="stale" if status == STATUS_CRITICAL else "missing",
            severity="critical",
            message=str(freshness_status.get("message") or "Market data freshness is not usable."),
            last_updated=freshness_status.get("last_check"),
            evidence=evidence,
        )
    return _decision_domain(
        key="market_data",
        label="Market Data",
        status="degraded" if status == STATUS_ERROR else "unknown",
        severity="critical" if status == STATUS_ERROR else "unknown",
        message=str(
            freshness_status.get("error")
            or freshness_status.get("message")
            or "Market data freshness check is unavailable."
        ),
        last_updated=freshness_status.get("last_check"),
        evidence=evidence,
    )


def _find_prediction_macro_cluster(freshness_summary: Any) -> Any:
    clusters = _read_field(freshness_summary, "critical_clusters", "criticalClusters", default=[]) or []
    for cluster in clusters:
        if str(_read_field(cluster, "cluster", default="")).lower() == "macro_calendar":
            return cluster
    return None


def _build_prediction_macro_decision_domain(snapshot: Any | None) -> DecisionDataDomain:
    label = "Prediction Macro"
    if snapshot is None:
        return _decision_domain(
            key="prediction_macro",
            label=label,
            status="missing",
            severity="critical",
            message="No market-prediction committee snapshot is available.",
        )

    freshness_summary = _read_field(snapshot, "freshness_summary", "freshnessSummary")
    generated_at = _read_field(snapshot, "generated_at", "generatedAt")
    if freshness_summary is None:
        return _decision_domain(
            key="prediction_macro",
            label=label,
            status="unknown",
            severity="unknown",
            message="Committee snapshot has no freshness summary.",
            last_updated=generated_at,
        )

    macro_cluster = _find_prediction_macro_cluster(freshness_summary)
    macro_freshness = str(_read_field(macro_cluster, "freshness", default="unknown") or "unknown")
    macro_detail = _read_field(macro_cluster, "detail")
    state = str(_read_field(freshness_summary, "state", default="unknown") or "unknown")
    invalidated = bool(_read_field(freshness_summary, "invalidated", default=False))
    summary = str(_read_field(freshness_summary, "summary", default="") or "")
    evidence = {
        "state": state,
        "invalidated": invalidated,
        "macro_freshness": macro_freshness,
        "reason_codes": _read_field(freshness_summary, "reason_codes", "reasonCodes", default=[]),
    }

    if macro_freshness == "missing":
        domain_status: DecisionDomainStatus = "missing"
        severity: DecisionDomainSeverity = "critical"
        message = str(macro_detail or "Macro calendar evidence is missing.")
    elif macro_freshness == "stale":
        domain_status = "stale"
        severity = "warning"
        message = str(macro_detail or "Macro calendar evidence is stale.")
    elif invalidated or state == "invalid":
        domain_status = "stale"
        severity = "critical"
        message = summary or "Prediction snapshot is outside its valid refresh window."
    elif state in {"stale", "aging"}:
        domain_status = "stale" if state == "stale" else "aging"
        severity = "warning"
        message = summary or "Prediction snapshot needs review soon."
    elif state == "degraded":
        domain_status = "degraded"
        severity = "critical"
        message = summary or "Prediction snapshot is degraded."
    elif state == "fresh" and macro_freshness == "fresh":
        domain_status = "current"
        severity = "healthy"
        message = summary or "Prediction macro evidence is current."
    else:
        domain_status = "unknown"
        severity = "unknown"
        message = summary or "Prediction macro freshness is unknown."

    return _decision_domain(
        key="prediction_macro",
        label=label,
        status=domain_status,
        severity=severity,
        message=message,
        last_updated=generated_at,
        evidence=evidence,
    )


def _build_household_decision_domain(dashboard: Any | None) -> DecisionDataDomain:
    if dashboard is None:
        return _decision_domain(
            key="household_evidence",
            label="Household Evidence",
            status="missing",
            severity="critical",
            message="Household finance dashboard is unavailable.",
        )

    overview = _read_field(dashboard, "overview")
    monthly_status = str(_read_field(overview, "monthly_spend_status", "monthlySpendStatus", default="unknown"))
    net_worth_status = str(_read_field(overview, "net_worth_status", "netWorthStatus", default="unknown"))
    needs_refresh_count = _as_int(_read_field(overview, "needs_refresh_count", "needsRefreshCount"))
    gap_count = _as_int(_read_field(overview, "gap_count", "gapCount"))
    inbox_count = _as_int(_read_field(overview, "inbox_count", "inboxCount"))
    monthly_detail = str(_read_field(overview, "monthly_spend_detail", "monthlySpendDetail", default="") or "")
    net_worth_detail = str(_read_field(overview, "net_worth_detail", "netWorthDetail", default="") or "")
    evidence = {
        "monthly_spend_status": monthly_status,
        "net_worth_status": net_worth_status,
        "needs_refresh_count": needs_refresh_count,
        "gap_count": gap_count,
        "inbox_count": inbox_count,
        "coverage_months": _as_int(_read_field(overview, "coverage_months", "coverageMonths")),
        "last_transaction_date": _read_field(overview, "last_transaction_date", "lastTransactionDate"),
    }
    last_updated = _read_field(dashboard, "generated_at", "generatedAt")

    if monthly_status in {"unavailable", "missing"}:
        return _decision_domain(
            key="household_evidence",
            label="Household Evidence",
            status="missing",
            severity="critical",
            message=monthly_detail or "Household spending evidence is missing.",
            last_updated=last_updated,
            evidence=evidence,
        )
    if "stale" in {monthly_status, net_worth_status}:
        return _decision_domain(
            key="household_evidence",
            label="Household Evidence",
            status="stale",
            severity="critical",
            message=monthly_detail or net_worth_detail or "Household evidence is stale.",
            last_updated=last_updated,
            evidence=evidence,
        )
    if monthly_status != "current" or net_worth_status != "current" or needs_refresh_count > 0 or gap_count > 0:
        return _decision_domain(
            key="household_evidence",
            label="Household Evidence",
            status="aging",
            severity="warning",
            message=monthly_detail or net_worth_detail or "Household evidence needs review.",
            last_updated=last_updated,
            evidence=evidence,
        )
    return _decision_domain(
        key="household_evidence",
        label="Household Evidence",
        status="current",
        severity="healthy",
        message=monthly_detail or "Household evidence is current.",
        last_updated=last_updated,
        evidence=evidence,
    )


def _build_automation_decision_domain(
    workflow_health: Any | None,
    *,
    now: datetime | None = None,
) -> DecisionDataDomain:
    key = "automation_recency"
    label = "Automation Recency"
    if workflow_health is None:
        return _decision_domain(
            key=key,
            label=label,
            status="missing",
            severity="critical",
            message="Automation health is unavailable.",
        )

    now = now or datetime.now(UTC)
    total_workflows = _as_int(_read_field(workflow_health, "total_workflows_24h", "totalWorkflows24h", "totalWorkflows24H"))
    successful_workflows = _as_int(_read_field(workflow_health, "successful_workflows", "successfulWorkflows"))
    failed_workflows = _as_int(_read_field(workflow_health, "failed_workflows", "failedWorkflows"))
    blocked_workflows = _as_int(_read_field(workflow_health, "blocked_workflows", "blockedWorkflows"))
    status = str(_read_field(workflow_health, "status", default=STATUS_UNKNOWN) or STATUS_UNKNOWN)
    last_success = _parse_datetime(
        _read_field(workflow_health, "last_successful_workflow", "lastSuccessfulWorkflow")
    )
    evidence = {
        "status": status,
        "total_workflows_24h": total_workflows,
        "successful_workflows": successful_workflows,
        "failed_workflows": failed_workflows,
        "blocked_workflows": blocked_workflows,
        "last_successful_type": _read_field(workflow_health, "last_successful_type", "lastSuccessfulType"),
    }

    if total_workflows == 0 and last_success is None:
        domain_status: DecisionDomainStatus = "missing"
        severity: DecisionDomainSeverity = "critical"
        message = "No automation runs or successful automation history are recorded."
    elif status == STATUS_CRITICAL:
        domain_status = "degraded"
        severity = "critical"
        message = f"{failed_workflows} automation runs failed and {blocked_workflows} are stuck."
    elif status == STATUS_WARNING or failed_workflows > 0 or blocked_workflows > 0:
        domain_status = "aging"
        severity = "warning"
        message = f"{failed_workflows} automation runs failed and {blocked_workflows} are stuck."
    elif last_success is not None and (now - last_success).total_seconds() > DEFAULT_HOURS_WINDOW * 3600:
        domain_status = "stale"
        severity = "warning"
        message = "Latest successful automation run is older than 24h."
    elif total_workflows == 0:
        domain_status = "aging"
        severity = "warning"
        message = "No automation runs finished in the last 24h."
    else:
        domain_status = "current"
        severity = "healthy"
        message = f"{successful_workflows} automation runs completed in the last 24h."

    return _decision_domain(
        key=key,
        label=label,
        status=domain_status,
        severity=severity,
        message=message,
        last_updated=last_success,
        evidence=evidence,
    )


def _build_source_decision_domain(
    sources: dict[str, Any] | None,
    api_quotas: list[Any] | None,
) -> DecisionDataDomain:
    key = "source_connectivity"
    label = "Source Connectivity"
    sources = sources or {}
    api_quotas = api_quotas or []
    down_sources: list[str] = []
    degraded_sources: list[str] = []
    quota_limited_sources: list[str] = []
    stale_sources: list[str] = []
    for source_name, source in sources.items():
        source_status = str(_read_field(source, "status", default=STATUS_UNKNOWN) or STATUS_UNKNOWN)
        reason = str(_read_field(source, "status_reason", "statusReason", default="") or "")
        if source_status == STATUS_DOWN:
            down_sources.append(source_name)
        elif source_status == "degraded":
            degraded_sources.append(source_name)
        if _as_int(_read_field(source, "rate_limit_hits", "rateLimitHits")) > 0 or _as_bool(
            _read_field(source, "in_cooldown", "inCooldown")
        ):
            quota_limited_sources.append(source_name)
        if source_status in {STATUS_DOWN, "degraded"} and (
            "older" in reason.lower() or _read_field(source, "last_success", "lastSuccess") is None
        ):
            stale_sources.append(source_name)

    disabled_sources = [
        str(_read_field(quota, "source_name", "sourceName", default="unknown"))
        for quota in api_quotas
        if not bool(_read_field(quota, "configured", default=False))
    ]
    connected_source_count = sum(1 for quota in api_quotas if bool(_read_field(quota, "configured", default=False)))
    evidence = {
        "checked_sources": len(sources),
        "connected_sources": connected_source_count,
        "disabled_sources": disabled_sources,
        "down_sources": down_sources,
        "degraded_sources": degraded_sources,
        "quota_limited_sources": quota_limited_sources,
        "stale_sources": stale_sources,
    }

    if not sources and not api_quotas:
        domain_status: DecisionDomainStatus = "missing"
        severity: DecisionDomainSeverity = "critical"
        message = "No source connectivity or quota metadata is available."
    elif quota_limited_sources:
        domain_status = "quota_limited"
        severity = "warning"
        message = f"{len(quota_limited_sources)} source{'s' if len(quota_limited_sources) != 1 else ''} hit quota limits."
    elif down_sources or stale_sources:
        severity: DecisionDomainSeverity = (
            "critical" if sources and len(down_sources) == len(sources) else "warning"
        )
        domain_status = "stale"
        affected_count = len(down_sources) or len(stale_sources)
        message = (
            f"{affected_count} source{'s' if affected_count != 1 else ''} "
            "need fresh successful fetches."
        )
    elif degraded_sources:
        domain_status = "degraded"
        severity = "warning"
        message = f"{len(degraded_sources)} source{'s' if len(degraded_sources) != 1 else ''} are degraded."
    elif disabled_sources:
        domain_status = "disabled"
        severity = "warning"
        message = f"{len(disabled_sources)} provider{'s' if len(disabled_sources) != 1 else ''} are disabled or missing keys."
    else:
        domain_status = "current"
        severity = "healthy"
        message = "Configured decision-data sources are connected."

    return _decision_domain(
        key=key,
        label=label,
        status=domain_status,
        severity=severity,
        message=message,
        evidence=evidence,
    )


def _summarize_decision_data_domains(domains: list[DecisionDataDomain]) -> DecisionDataHealth:
    severity_rank = {"healthy": 0, "warning": 1, "unknown": 1, "critical": 2}
    worst_rank = max((severity_rank.get(domain.severity, 1) for domain in domains), default=1)
    if worst_rank >= 2:
        status: Literal["healthy", "degraded", "critical", "unknown"] = "critical"
    elif worst_rank == 1:
        status = "degraded"
    else:
        status = "healthy"

    issue_count = sum(1 for domain in domains if domain.severity != "healthy")
    if not domains:
        message = "Decision-data health is unavailable."
        status = "unknown"
    elif issue_count == 0:
        message = "All decision-data domains are current."
    else:
        message = f"{issue_count} of {len(domains)} decision-data domains need review."
    return DecisionDataHealth(status=status, message=message, domains=domains)


def _prediction_macro_domain_from_service() -> DecisionDataDomain:
    snapshot = MarketPredictionCommitteeService().get_committee_snapshot(
        window_days=3,
        generate_if_missing=False,
    )
    return _build_prediction_macro_decision_domain(snapshot)


def _household_domain_from_service() -> DecisionDataDomain:
    return _build_household_decision_domain(HouseholdFinanceService().get_dashboard())


async def get_decision_data_health(
    *,
    health_result: dict[str, Any],
    data_freshness_status: dict[str, Any],
) -> dict[str, Any]:
    domains = [
        _build_market_data_decision_domain(data_freshness_status),
        _build_automation_decision_domain(health_result.get("workflow_health")),
        _build_source_decision_domain(
            health_result.get("sources"),
            health_result.get("api_quotas"),
        ),
    ]
    try:
        domains.append(await run_in_threadpool(_prediction_macro_domain_from_service))
    except Exception as exc:
        logger.warning("prediction_macro_health_failed", error=str(exc), exc_info=True)
        domains.append(
            _decision_domain(
                key="prediction_macro",
                label="Prediction Macro",
                status="degraded",
                severity="critical",
                message="Prediction macro health check failed.",
                evidence={"error": str(exc)},
            )
        )
    try:
        domains.append(await run_in_threadpool(_household_domain_from_service))
    except Exception as exc:
        logger.warning("household_health_failed", error=str(exc), exc_info=True)
        domains.append(
            _decision_domain(
                key="household_evidence",
                label="Household Evidence",
                status="degraded",
                severity="critical",
                message="Household evidence health check failed.",
                evidence={"error": str(exc)},
            )
        )
    domains.sort(key=lambda domain: domain.key)
    return _summarize_decision_data_domains(domains).model_dump(mode="json")


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
