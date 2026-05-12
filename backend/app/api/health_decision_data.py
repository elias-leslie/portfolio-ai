"""Decision-data health domain builders."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from time import monotonic
from typing import Any, Literal

from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app.logging_config import get_logger
from app.services.household_finance_service import HouseholdFinanceService

from .health_models import (
    DEFAULT_HOURS_WINDOW,
    STATUS_CRITICAL,
    STATUS_DOWN,
    STATUS_ERROR,
    STATUS_NO_DATA,
    STATUS_SUCCESS,
    STATUS_UNKNOWN,
    STATUS_WARNING,
    _as_bool,
    _as_int,
    _format_any_datetime,
    _parse_datetime,
    _read_field,
)

logger = get_logger(__name__)
_DOMAIN_CACHE_TTL_SECONDS = 30

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


_domain_cache: dict[str, tuple[float, DecisionDataDomain]] = {}


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
    evidence = {
        "fresh": _as_int(freshness_status.get("fresh")),
        "stale": _as_int(freshness_status.get("stale")),
        "critical": _as_int(freshness_status.get("critical")),
        "tables_checked": _as_int(freshness_status.get("tables_checked")),
        "check_status": freshness_status.get("check_status"),
    }
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
        severity = "critical" if sources and len(down_sources) == len(sources) else "warning"
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


def _household_domain_from_service() -> DecisionDataDomain:
    return _build_household_decision_domain(HouseholdFinanceService().get_dashboard())


def _cached_domain_from_service(
    cache_key: str,
    builder: Callable[[], DecisionDataDomain],
) -> DecisionDataDomain:
    cached = _domain_cache.get(cache_key)
    now = monotonic()
    if cached is not None and cached[0] > now:
        return cached[1]
    domain = builder()
    _domain_cache[cache_key] = (now + _DOMAIN_CACHE_TTL_SECONDS, domain)
    return domain


def _cached_household_domain_from_service() -> DecisionDataDomain:
    return _cached_domain_from_service(
        "household_evidence",
        _household_domain_from_service,
    )


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
        household_result: DecisionDataDomain | Exception = await run_in_threadpool(
            _cached_household_domain_from_service
        )
    except Exception as exc:
        household_result = exc
    if isinstance(household_result, Exception):
        logger.warning("household_health_failed", error=str(household_result), exc_info=True)
        domains.append(
            _decision_domain(
                key="household_evidence",
                label="Household Evidence",
                status="degraded",
                severity="critical",
                message="Household evidence health check failed.",
                evidence={"error": str(household_result)},
            )
        )
    else:
        domains.append(household_result)
    domains.sort(key=lambda domain: domain.key)
    return _summarize_decision_data_domains(domains).model_dump(mode="json")
