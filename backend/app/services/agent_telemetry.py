"""Agent telemetry aggregation service.

Provides telemetry data aggregation and analysis for AI agent operations:
- Token usage by provider/model
- Performance metrics over time
- Cost estimation and tracking
- Error rate analysis

Zero API cost tracking - measures CLI execution metrics.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from ..logging_config import get_logger
from ..storage.connection import ConnectionManager
from ._telemetry_models import (
    COST_PER_MILLION_TOKENS,
    AgentRunDetail,
    DailyTelemetry,
    ProviderMetrics,
    TelemetrySummary,
    TokenUsage,
)
from ._telemetry_queries import (
    fetch_daily_breakdown,
    fetch_overall_aggregates,
    fetch_provider_metrics,
    fetch_run_history,
    fetch_token_aggregates,
    fetch_token_summary_by_group,
)

logger = get_logger(__name__)

__all__ = [
    "COST_PER_MILLION_TOKENS",
    "AgentRunDetail",
    "AgentTelemetryService",
    "DailyTelemetry",
    "ProviderMetrics",
    "TelemetrySummary",
    "TokenUsage",
]


class AgentTelemetryService:
    """Service for aggregating and analyzing agent telemetry data."""

    def __init__(self, conn_mgr: ConnectionManager) -> None:
        self.conn_mgr = conn_mgr

    def get_summary(self, days: int = 7) -> TelemetrySummary:
        """Get telemetry summary for the last N days."""
        now = datetime.now(UTC)
        start_date = now - timedelta(days=days)

        with self.conn_mgr.connection() as conn:
            total_runs, successful_runs, failed_runs, avg_duration_ms = fetch_overall_aggregates(conn, start_date)

            if total_runs == 0:
                return TelemetrySummary(
                    period_start=start_date.isoformat(),
                    period_end=now.isoformat(),
                    period_days=days,
                )

            total_input, total_output, total_tokens = fetch_token_aggregates(conn, start_date)
            success_rate = round(successful_runs / total_runs * 100, 1)
            avg_tokens = round(total_tokens / total_runs, 0)

            return TelemetrySummary(
                period_start=start_date.isoformat(),
                period_end=now.isoformat(),
                period_days=days,
                total_runs=total_runs,
                successful_runs=successful_runs,
                failed_runs=failed_runs,
                success_rate=success_rate,
                total_input_tokens=total_input,
                total_output_tokens=total_output,
                total_tokens=total_tokens,
                avg_tokens_per_run=avg_tokens,
                avg_duration_ms=round(avg_duration_ms, 0),
                total_cost_usd=0.0,  # CLI is free
                by_provider=fetch_provider_metrics(conn, start_date),
                daily_data=fetch_daily_breakdown(conn, start_date),
            )

    def get_run_history(
        self,
        limit: int = 50,
        offset: int = 0,
        provider: str | None = None,
        status: str | None = None,
        agent_type: str | None = None,
    ) -> tuple[list[AgentRunDetail], int]:
        """Get paginated agent run history."""
        conditions: list[str] = []
        params: list[Any] = []

        if provider:
            conditions.append("provider = %s")
            params.append(provider)
        if status:
            conditions.append("status = %s")
            params.append(status)
        if agent_type:
            conditions.append("agent_type = %s")
            params.append(agent_type)

        where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        with self.conn_mgr.connection() as conn:
            return fetch_run_history(conn, where_clause, params, limit, offset)

    def get_provider_comparison(self, days: int = 30) -> list[ProviderMetrics]:
        """Get detailed provider comparison metrics."""
        return self.get_summary(days=days).by_provider

    def get_token_summary(self, days: int = 7) -> dict[str, Any]:
        """Get token usage summary for the UI."""
        now = datetime.now(UTC)
        start_date = now - timedelta(days=days)

        with self.conn_mgr.connection() as conn:
            _, _, total_tokens = fetch_token_aggregates(conn, start_date)
            by_provider = fetch_token_summary_by_group(conn, start_date, "provider")
            by_agent = fetch_token_summary_by_group(conn, start_date, "agent_type")

        return {
            "total_tokens": total_tokens,
            "by_provider": by_provider,
            "by_agent": by_agent,
            "period_days": days,
            "period_start": start_date.isoformat(),
            "period_end": now.isoformat(),
        }
