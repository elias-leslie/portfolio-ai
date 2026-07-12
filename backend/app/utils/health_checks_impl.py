"""Service health check functions (sources, workers, agents, watchlist)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel

from app.logging_config import get_logger
from app.services.worker_heartbeat import HeartbeatState, read_worker_heartbeat
from app.storage import PortfolioStorage
from app.utils.market_hours import get_market_aware_age_hours

logger = get_logger(__name__)


class SourceHealthCheck(BaseModel):
    """Health check for individual data source."""

    status: Literal["ok", "degraded", "down"]
    status_reason: str | None = None
    last_success: datetime | None = None
    success_rate: float | None = None
    avg_latency_ms: int | None = None
    rate_limit_hits: int = 0
    in_cooldown: bool = False
    cooldown_remaining_seconds: int = 0


class AgentStats(BaseModel):
    """Agent execution statistics."""

    total_runs: int
    completed_runs: int
    failed_runs: int
    avg_duration_s: float | None = None
    avg_cost_usd: float | None = None


class WatchlistStats(BaseModel):
    """Watchlist statistics."""

    total_items: int
    last_refresh: datetime | None = None
    refresh_age_minutes: float | None = None
    items_with_scores: int = 0


class WorkerInfo(BaseModel):
    """Worker status information."""

    active: bool
    heartbeat_state: HeartbeatState | None = None
    instance_id: str | None = None
    hostname: str | None = None
    pid: int | None = None
    started_at: datetime | None = None
    last_heartbeat_at: datetime | None = None
    heartbeat_age_seconds: float | None = None
    pool_size: int | None = None
    active_tasks: int | None = None
    message: str = ""


@dataclass(frozen=True)
class SourceHealthPolicy:
    """Freshness windows for a monitored source."""

    ok_window: timedelta = timedelta(hours=2)
    degraded_window: timedelta = timedelta(hours=24)
    monitoring_mode: Literal["continuous", "standby"] = "continuous"
    market_data: bool = False


@lru_cache(maxsize=1)
def _load_api_sources_registry() -> dict[str, Any]:
    """Load the provider capability registry."""
    config_path = Path(__file__).resolve().parent.parent / "config" / "api-sources-registry.yaml"
    with config_path.open(encoding="utf-8") as registry_file:
        loaded = yaml.safe_load(registry_file)
    return loaded if isinstance(loaded, dict) else {}


def _is_source_panel_capability(capabilities: dict[str, Any]) -> bool:
    """Return True when a provider belongs in the market/reference source panel."""
    return any(
        bool(capabilities.get(key))
        for key in ("ohlcv", "reference", "fundamentals", "options", "macro")
    )


def _get_source_health_policies() -> dict[str, SourceHealthPolicy]:
    """Return health policies for source rows that belong in the source panel.

    The source panel is scoped to market/reference providers. News-only vendors have a
    dedicated News Vendors section and should not appear here.
    """
    providers = _load_api_sources_registry().get("providers", {})
    policies: dict[str, SourceHealthPolicy] = {}

    if isinstance(providers, dict):
        for source_name, provider_config in providers.items():
            if not isinstance(source_name, str) or not isinstance(provider_config, dict):
                continue

            capabilities = provider_config.get("capabilities", {})
            if not isinstance(capabilities, dict) or not _is_source_panel_capability(capabilities):
                continue

            monitoring_mode = provider_config.get("health_monitoring", "continuous")
            if monitoring_mode not in {"continuous", "standby"}:
                monitoring_mode = "continuous"
            policies[source_name] = SourceHealthPolicy(
                monitoring_mode=monitoring_mode,
            )

    if "cboe_most_active" in policies:
        policies["cboe_most_active"] = SourceHealthPolicy(
            ok_window=timedelta(hours=30),
            degraded_window=timedelta(hours=48),
            market_data=True,
            monitoring_mode=policies["cboe_most_active"].monitoring_mode,
        )
    return policies


def _calculate_source_metrics(
    success_count: int, failure_count: int, total_latency_ms: int
) -> tuple[float, int | None]:
    """Calculate success rate and average latency for a source."""
    total_requests = success_count + failure_count
    success_rate = (success_count / total_requests * 100) if total_requests > 0 else 0.0
    avg_latency_ms = int(total_latency_ms / success_count) if success_count > 0 else None
    return success_rate, avg_latency_ms


def _format_window(window: timedelta) -> str:
    """Format a freshness window for concise status reasons."""
    total_seconds = int(window.total_seconds())
    if total_seconds % 3600 == 0:
        return f"{total_seconds // 3600}h"
    if total_seconds % 60 == 0:
        return f"{total_seconds // 60}m"
    return f"{total_seconds}s"


def _status_from_success_rate(success_rate: float) -> Literal["ok", "degraded", "down"]:
    """Map request success rate to a provider health status."""
    if success_rate >= 80:
        return "ok"
    if success_rate >= 50:
        return "degraded"
    return "down"


def _determine_source_status(
    last_success_at: datetime | None,
    success_rate: float,
    *,
    policy: SourceHealthPolicy | None = None,
) -> Literal["ok", "degraded", "down"]:
    """Determine source status based on last success time and success rate.

    Thresholds vary by source cadence.
    """
    if not last_success_at:
        return "down"  # Never succeeded

    active_policy = policy or SourceHealthPolicy()
    if active_policy.monitoring_mode == "standby":
        return _status_from_success_rate(success_rate)

    age = _source_age(last_success_at, active_policy)
    time_since_success = timedelta(hours=age)

    if time_since_success < active_policy.ok_window:
        return _status_from_success_rate(success_rate)
    if time_since_success < active_policy.degraded_window:
        return "degraded"
    return "down"


def _build_source_status_reason(
    last_success_at: datetime | None,
    success_rate: float,
    status: Literal["ok", "degraded", "down"],
    *,
    policy: SourceHealthPolicy,
) -> str | None:
    """Explain non-OK source status using the same policy that sets status."""
    if policy.monitoring_mode == "standby":
        if not last_success_at:
            return "No successful fetch recorded."
        if status == "ok":
            return "Backup-only source; freshness is checked on demand."
        if success_rate < 50:
            return "Backup-only source request success rate is below 50%."
        if success_rate < 80:
            return "Backup-only source request success rate is below 80%."
        return "Backup-only source health needs review."

    reason: str | None = None
    if status != "ok":
        if not last_success_at:
            reason = "No successful fetch recorded."
        else:
            time_since_success = timedelta(hours=_source_age(last_success_at, policy))
            if time_since_success >= policy.degraded_window:
                reason = (
                    f"Last good update is older than {_format_window(policy.degraded_window)}."
                )
            elif time_since_success >= policy.ok_window:
                reason = f"Last good update is older than {_format_window(policy.ok_window)}."
            elif success_rate < 50:
                reason = "Request success rate is below 50%."
            elif success_rate < 80:
                reason = "Request success rate is below 80%."
            else:
                reason = "Source health needs review."
    return reason


def _source_age(last_success_at: datetime, policy: SourceHealthPolicy) -> float:
    return get_market_aware_age_hours(
        last_update=last_success_at,
        now=datetime.now(UTC),
        is_market_data=policy.market_data,
    )


def _build_source_health_check(row: dict[str, Any], policy: SourceHealthPolicy) -> SourceHealthCheck:
    """Build a SourceHealthCheck from a performance row and its policy."""
    success_count = row["success_count"] or 0
    failure_count = row["failure_count"] or 0
    total_latency_ms = row["total_latency_ms"] or 0
    rate_limit_hits = row["rate_limit_hits"] or 0
    last_success_at = row.get("last_success_at")

    success_rate, avg_latency_ms = _calculate_source_metrics(
        success_count, failure_count, total_latency_ms
    )
    status = _determine_source_status(last_success_at, success_rate, policy=policy)
    status_reason = _build_source_status_reason(
        last_success_at,
        success_rate,
        status,
        policy=policy,
    )

    return SourceHealthCheck(
        status=status,
        status_reason=status_reason,
        last_success=last_success_at,
        success_rate=round(success_rate, 1),
        avg_latency_ms=avg_latency_ms,
        rate_limit_hits=rate_limit_hits,
        in_cooldown=False,
        cooldown_remaining_seconds=0,
    )


def check_sources(storage: PortfolioStorage) -> dict[str, SourceHealthCheck]:
    """Check health of monitored market/reference data sources."""
    sources: dict[str, SourceHealthCheck] = {}

    try:
        source_policies = _get_source_health_policies()

        df = storage.query(
            """
            SELECT source_name, success_count, failure_count, total_latency_ms,
                   rate_limit_hits, last_success_at
            FROM source_performance
            """,
            [],
        )

        if df.is_empty():
            return sources

        for row in df.iter_rows(named=True):
            source_name = row["source_name"]
            policy = source_policies.get(source_name)
            if policy is None:
                continue
            sources[source_name] = _build_source_health_check(row, policy)

    except Exception as e:
        logger.error("check_sources_failed", error=str(e), exc_info=True)

    return sources


def _query_agent_stats_row(storage: PortfolioStorage) -> dict[str, Any] | None:
    """Run the agent_runs aggregate query and return the first row, or None if empty."""
    df = storage.query(
        """
        SELECT
            COUNT(*) as total_runs,
            SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_runs,
            SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_runs,
            AVG(CASE
                WHEN status = 'completed' AND completed_at IS NOT NULL
                THEN EXTRACT(EPOCH FROM (completed_at - started_at))
                ELSE NULL
            END) as avg_duration_s,
            AVG(cost_usd) as avg_cost_usd
        FROM agent_runs
        """
    )
    return df.to_dicts()[0] if not df.is_empty() else None


def _empty_agent_stats() -> AgentStats:
    return AgentStats(total_runs=0, completed_runs=0, failed_runs=0)


def get_agent_stats(storage: PortfolioStorage) -> AgentStats:
    """Get agent execution statistics."""
    try:
        row = _query_agent_stats_row(storage)
        if row is None:
            return _empty_agent_stats()

        return AgentStats(
            total_runs=row["total_runs"] or 0,
            completed_runs=row["completed_runs"] or 0,
            failed_runs=row["failed_runs"] or 0,
            avg_duration_s=round(row["avg_duration_s"], 2) if row["avg_duration_s"] else None,
            avg_cost_usd=round(row["avg_cost_usd"], 4) if row["avg_cost_usd"] else None,
        )

    except Exception as e:
        logger.error("get_agent_stats_failed", error=str(e), exc_info=True)
        return _empty_agent_stats()


def _query_watchlist_snapshots(storage: PortfolioStorage) -> dict[str, Any] | None:
    """Query watchlist snapshot aggregates; returns first row or None."""
    df = storage.query(
        """
        SELECT
            MAX(fetched_at) as last_refresh,
            COUNT(DISTINCT item_id) as items_with_scores
        FROM watchlist_snapshots_v
        """
    )
    return df.to_dicts()[0] if not df.is_empty() else None


def get_watchlist_stats(storage: PortfolioStorage) -> WatchlistStats:
    """Get watchlist statistics."""
    try:
        items_df = storage.query("SELECT COUNT(*) as total FROM watchlist_items")
        total_items = items_df.to_dicts()[0]["total"] if not items_df.is_empty() else 0

        row = _query_watchlist_snapshots(storage)
        if row is None:
            return WatchlistStats(total_items=total_items, items_with_scores=0)

        last_refresh = row.get("last_refresh")
        items_with_scores = row.get("items_with_scores") or 0
        refresh_age_minutes = None
        if last_refresh:
            refresh_age_minutes = (datetime.now(UTC) - last_refresh).total_seconds() / 60

        return WatchlistStats(
            total_items=total_items,
            last_refresh=last_refresh,
            refresh_age_minutes=refresh_age_minutes,
            items_with_scores=items_with_scores,
        )

    except Exception as e:
        logger.error("get_watchlist_stats_failed", error=str(e), exc_info=True)
        return WatchlistStats(total_items=0)


def get_worker_info(storage: PortfolioStorage) -> WorkerInfo:
    """Get Hatchet worker status from its cross-process durable heartbeat."""
    heartbeat = read_worker_heartbeat(storage)
    return WorkerInfo(
        active=heartbeat.active,
        heartbeat_state=heartbeat.state,
        instance_id=str(heartbeat.instance_id) if heartbeat.instance_id else None,
        hostname=heartbeat.hostname,
        pid=heartbeat.pid,
        started_at=heartbeat.started_at,
        last_heartbeat_at=heartbeat.last_seen_at,
        heartbeat_age_seconds=heartbeat.age_seconds,
        message=heartbeat.message,
    )
