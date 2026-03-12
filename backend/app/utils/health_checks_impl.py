"""Service health check functions (sources, workers, agents, watchlist)."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel

from app.logging_config import get_logger
from app.storage import PortfolioStorage

logger = get_logger(__name__)


class SourceHealthCheck(BaseModel):
    """Health check for individual data source."""

    status: Literal["ok", "degraded", "down"]
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
    pool_size: int | None = None
    active_tasks: int | None = None
    message: str = ""


@dataclass(frozen=True)
class SourceHealthPolicy:
    """Freshness windows for a monitored source."""

    ok_window: timedelta = timedelta(hours=2)
    degraded_window: timedelta = timedelta(hours=24)


@lru_cache(maxsize=1)
def _load_api_sources_registry() -> dict[str, Any]:
    """Load the provider capability registry."""
    config_path = Path(__file__).resolve().parent.parent / "config" / "api-sources-registry.yaml"
    with config_path.open() as registry_file:
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

            policies[source_name] = SourceHealthPolicy()

    if "cboe_most_active" in policies:
        policies["cboe_most_active"] = SourceHealthPolicy(
            ok_window=timedelta(hours=30),
            degraded_window=timedelta(hours=48),
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
    time_since_success = datetime.now(UTC) - last_success_at

    if time_since_success < active_policy.ok_window:
        # Recent success - status based on success rate
        if success_rate >= 80:
            return "ok"
        if success_rate >= 50:
            return "degraded"
        return "down"
    if time_since_success < active_policy.degraded_window:
        return "degraded"
    return "down"


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

            success_count = row["success_count"] or 0
            failure_count = row["failure_count"] or 0
            total_latency_ms = row["total_latency_ms"] or 0
            rate_limit_hits = row["rate_limit_hits"] or 0
            last_success_at = row.get("last_success_at")

            success_rate, avg_latency_ms = _calculate_source_metrics(
                success_count, failure_count, total_latency_ms
            )

            status = _determine_source_status(last_success_at, success_rate, policy=policy)

            sources[source_name] = SourceHealthCheck(
                status=status,
                last_success=last_success_at,
                success_rate=round(success_rate, 1),
                avg_latency_ms=avg_latency_ms,
                rate_limit_hits=rate_limit_hits,
                in_cooldown=False,
                cooldown_remaining_seconds=0,
            )

    except Exception as e:
        logger.error("check_sources_failed", error=str(e), exc_info=True)

    return sources


def get_agent_stats(storage: PortfolioStorage) -> AgentStats:
    """Get agent execution statistics.

    Args:
        storage: PortfolioStorage instance

    Returns:
        AgentStats with agent metrics
    """
    try:
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

        if df.is_empty():
            return AgentStats(
                total_runs=0,
                completed_runs=0,
                failed_runs=0,
            )

        row = df.to_dicts()[0]

        return AgentStats(
            total_runs=row["total_runs"] or 0,
            completed_runs=row["completed_runs"] or 0,
            failed_runs=row["failed_runs"] or 0,
            avg_duration_s=round(row["avg_duration_s"], 2) if row["avg_duration_s"] else None,
            avg_cost_usd=round(row["avg_cost_usd"], 4) if row["avg_cost_usd"] else None,
        )

    except Exception as e:
        logger.error("get_agent_stats_failed", error=str(e), exc_info=True)
        return AgentStats(
            total_runs=0,
            completed_runs=0,
            failed_runs=0,
        )


def get_watchlist_stats(storage: PortfolioStorage) -> WatchlistStats:
    """Get watchlist statistics.

    Args:
        storage: PortfolioStorage instance

    Returns:
        WatchlistStats with watchlist metrics
    """
    try:
        # Get total items
        items_df = storage.query("SELECT COUNT(*) as total FROM watchlist_items")
        total_items = items_df.to_dicts()[0]["total"] if not items_df.is_empty() else 0

        # Get last refresh timestamp and count items with scores
        snapshots_df = storage.query(
            """
            SELECT
                MAX(fetched_at) as last_refresh,
                COUNT(DISTINCT item_id) as items_with_scores
            FROM watchlist_snapshots_v
            """
        )

        if snapshots_df.is_empty():
            return WatchlistStats(
                total_items=total_items,
                items_with_scores=0,
            )

        row = snapshots_df.to_dicts()[0]
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


def get_worker_info() -> WorkerInfo:
    """Get Hatchet worker active status.

    Returns:
        WorkerInfo with worker status
    """
    try:
        result = subprocess.run(
            ["systemctl", "--user", "is-active", "portfolio-hatchet-worker"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        active = result.stdout.strip() == "active"
        return WorkerInfo(active=active, message="Hatchet worker active" if active else "Hatchet worker not active")
    except Exception as e:
        logger.error("get_worker_info_failed", error=str(e), exc_info=True)
        return WorkerInfo(active=False, message=f"Worker check failed: {e!s}")
