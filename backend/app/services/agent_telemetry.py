"""Agent telemetry aggregation service.

Provides telemetry data aggregation and analysis for AI agent operations:
- Token usage by provider/model
- Performance metrics over time
- Cost estimation and tracking
- Error rate analysis

Zero API cost tracking - measures CLI execution metrics.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any, TypedDict

from pydantic import BaseModel, Field

from ..logging_config import get_logger
from ..storage.connection import ConnectionManager

logger = get_logger(__name__)


class TokenUsage(TypedDict):
    """Token usage breakdown."""

    input_tokens: int
    output_tokens: int
    total_tokens: int


class ProviderMetrics(BaseModel):
    """Metrics for a specific LLM provider."""

    provider: str
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    success_rate: float = 0.0
    total_tokens: int = 0
    avg_tokens_per_run: float = 0.0
    avg_duration_ms: float = 0.0
    total_cost_usd: float = 0.0


class DailyTelemetry(BaseModel):
    """Daily aggregated telemetry."""

    date: str
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    avg_duration_ms: float = 0.0
    estimated_cost_usd: float = 0.0


class TelemetrySummary(BaseModel):
    """Summary telemetry for a time period."""

    period_start: str
    period_end: str
    period_days: int
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    success_rate: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    avg_tokens_per_run: float = 0.0
    avg_duration_ms: float = 0.0
    total_cost_usd: float = 0.0
    by_provider: list[ProviderMetrics] = Field(default_factory=list)
    daily_data: list[DailyTelemetry] = Field(default_factory=list)


class AgentRunDetail(BaseModel):
    """Detailed agent run information."""

    id: str
    agent_type: str
    started_at: str
    completed_at: str | None = None
    status: str
    provider: str | None = None
    model: str | None = None
    duration_ms: int | None = None
    token_usage: TokenUsage | None = None
    error: str | None = None


# Cost per 1M tokens (estimates for CLI execution - effectively free)
# These are placeholder costs for tracking, actual CLI execution is $0
COST_PER_MILLION_TOKENS = {
    "gemini": {"input": 0.0, "output": 0.0},  # Free via CLI
    "claude": {"input": 0.0, "output": 0.0},  # Free via CLI
    "anthropic_api": {"input": 3.0, "output": 15.0},  # If using API directly
}


class AgentTelemetryService:
    """Service for aggregating and analyzing agent telemetry data."""

    def __init__(self, conn_mgr: ConnectionManager) -> None:
        """Initialize telemetry service.

        Args:
            conn_mgr: Database connection manager
        """
        self.conn_mgr = conn_mgr

    def get_summary(self, days: int = 7) -> TelemetrySummary:
        """Get telemetry summary for the last N days.

        Args:
            days: Number of days to include (default 7)

        Returns:
            TelemetrySummary with aggregated metrics
        """
        now = datetime.now(UTC)
        start_date = now - timedelta(days=days)

        with self.conn_mgr.connection() as conn:
            # Get overall aggregates
            result = conn.execute(
                """
                SELECT
                    COUNT(*) as total_runs,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as successful_runs,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_runs,
                    AVG(duration_ms) as avg_duration_ms
                FROM agent_runs
                WHERE started_at >= %s
                """,
                [start_date],
            )
            row = result.fetchone()
            if row is None:
                return TelemetrySummary(
                    period_start=start_date.isoformat(),
                    period_end=now.isoformat(),
                    period_days=days,
                )

            total_runs = int(row[0] or 0)
            successful_runs = int(row[1] or 0)
            failed_runs = int(row[2] or 0)
            avg_duration_ms = float(row[3]) if row[3] else 0.0
            success_rate = (successful_runs / total_runs * 100) if total_runs > 0 else 0.0

            # Get token aggregates
            result = conn.execute(
                """
                SELECT
                    COALESCE(SUM((token_usage->>'input_tokens')::int), 0) as input_tokens,
                    COALESCE(SUM((token_usage->>'output_tokens')::int), 0) as output_tokens,
                    COALESCE(SUM((token_usage->>'total_tokens')::int), 0) as total_tokens
                FROM agent_runs
                WHERE started_at >= %s AND token_usage IS NOT NULL
                """,
                [start_date],
            )
            token_row = result.fetchone()
            total_input_tokens = int(token_row[0] or 0) if token_row else 0
            total_output_tokens = int(token_row[1] or 0) if token_row else 0
            total_tokens = int(token_row[2] or 0) if token_row else 0
            avg_tokens = (total_tokens / total_runs) if total_runs > 0 else 0.0

            # Get per-provider metrics
            result = conn.execute(
                """
                SELECT
                    COALESCE(provider, 'unknown') as provider,
                    COUNT(*) as total_runs,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as successful_runs,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_runs,
                    AVG(duration_ms) as avg_duration_ms,
                    COALESCE(SUM((token_usage->>'total_tokens')::int), 0) as total_tokens
                FROM agent_runs
                WHERE started_at >= %s
                GROUP BY provider
                ORDER BY total_runs DESC
                """,
                [start_date],
            )

            by_provider: list[ProviderMetrics] = []
            for prow in result.fetchall():
                provider_name = str(prow[0]) if prow[0] else "unknown"
                provider_total = int(prow[1] or 0)
                provider_success = int(prow[2] or 0)
                provider_failed = int(prow[3] or 0)
                provider_avg_ms = float(prow[4]) if prow[4] else 0.0
                provider_tokens = int(prow[5] or 0)

                provider_success_rate = (
                    (provider_success / provider_total * 100) if provider_total > 0 else 0.0
                )
                provider_avg_tokens = (
                    (provider_tokens / provider_total) if provider_total > 0 else 0.0
                )

                # CLI execution is free (no API costs)
                provider_cost = 0.0

                by_provider.append(
                    ProviderMetrics(
                        provider=provider_name,
                        total_runs=provider_total,
                        successful_runs=provider_success,
                        failed_runs=provider_failed,
                        success_rate=round(provider_success_rate, 1),
                        total_tokens=provider_tokens,
                        avg_tokens_per_run=round(provider_avg_tokens, 0),
                        avg_duration_ms=round(provider_avg_ms, 0),
                        total_cost_usd=provider_cost,
                    )
                )

            # Get daily breakdown
            result = conn.execute(
                """
                SELECT
                    DATE(started_at AT TIME ZONE 'UTC') as date,
                    COUNT(*) as total_runs,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as successful_runs,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_runs,
                    COALESCE(SUM((token_usage->>'input_tokens')::int), 0) as input_tokens,
                    COALESCE(SUM((token_usage->>'output_tokens')::int), 0) as output_tokens,
                    COALESCE(SUM((token_usage->>'total_tokens')::int), 0) as total_tokens,
                    AVG(duration_ms) as avg_duration_ms
                FROM agent_runs
                WHERE started_at >= %s
                GROUP BY DATE(started_at AT TIME ZONE 'UTC')
                ORDER BY date DESC
                """,
                [start_date],
            )

            daily_data: list[DailyTelemetry] = []
            for drow in result.fetchall():
                # drow[0] is a date from PostgreSQL
                date_obj = drow[0]
                if date_obj is not None and hasattr(date_obj, "isoformat"):
                    date_val = date_obj.isoformat()
                else:
                    date_val = str(date_obj or "")
                daily_data.append(
                    DailyTelemetry(
                        date=date_val,
                        total_runs=int(drow[1] or 0),
                        successful_runs=int(drow[2] or 0),
                        failed_runs=int(drow[3] or 0),
                        total_input_tokens=int(drow[4] or 0),
                        total_output_tokens=int(drow[5] or 0),
                        total_tokens=int(drow[6] or 0),
                        avg_duration_ms=round(float(drow[7]), 0) if drow[7] else 0.0,
                        estimated_cost_usd=0.0,  # CLI is free
                    )
                )

            return TelemetrySummary(
                period_start=start_date.isoformat(),
                period_end=now.isoformat(),
                period_days=days,
                total_runs=total_runs,
                successful_runs=successful_runs,
                failed_runs=failed_runs,
                success_rate=round(success_rate, 1),
                total_input_tokens=total_input_tokens,
                total_output_tokens=total_output_tokens,
                total_tokens=total_tokens,
                avg_tokens_per_run=round(avg_tokens, 0),
                avg_duration_ms=round(avg_duration_ms, 0),
                total_cost_usd=0.0,  # CLI is free
                by_provider=by_provider,
                daily_data=daily_data,
            )

    def get_run_history(
        self,
        limit: int = 50,
        offset: int = 0,
        provider: str | None = None,
        status: str | None = None,
        agent_type: str | None = None,
    ) -> tuple[list[AgentRunDetail], int]:
        """Get paginated agent run history.

        Args:
            limit: Maximum number of runs to return
            offset: Number of runs to skip
            provider: Filter by provider (optional)
            status: Filter by status (optional)
            agent_type: Filter by agent type (optional)

        Returns:
            Tuple of (list of runs, total count)
        """
        with self.conn_mgr.connection() as conn:
            # Build WHERE clause
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

            where_clause = ""
            if conditions:
                where_clause = "WHERE " + " AND ".join(conditions)

            # Get total count
            count_result = conn.execute(
                f"SELECT COUNT(*) FROM agent_runs {where_clause}",
                params,
            )
            count_row = count_result.fetchone()
            total_count = int(count_row[0]) if count_row else 0  # type: ignore[arg-type]

            # Get paginated results
            params.extend([limit, offset])
            result = conn.execute(
                f"""
                SELECT
                    id, agent_type, started_at, completed_at, status,
                    provider, model, duration_ms, token_usage, error_message
                FROM agent_runs
                {where_clause}
                ORDER BY started_at DESC
                LIMIT %s OFFSET %s
                """,
                params,
            )

            runs: list[AgentRunDetail] = []
            for row in result.fetchall():
                token_usage = None
                raw_token = row[8]
                if raw_token:
                    try:
                        if isinstance(raw_token, str):
                            tu = json.loads(raw_token)
                        elif isinstance(raw_token, dict):
                            tu = raw_token
                        else:
                            tu = {}
                        token_usage = TokenUsage(
                            input_tokens=tu.get("input_tokens", 0),
                            output_tokens=tu.get("output_tokens", 0),
                            total_tokens=tu.get("total_tokens", 0),
                        )
                    except (json.JSONDecodeError, TypeError):
                        pass

                # Extract values with proper type casting
                run_id = str(row[0])
                agent_type_val = str(row[1]) if row[1] else "unknown"
                started_at_obj = row[2]
                started_at_val = (
                    started_at_obj.isoformat()
                    if started_at_obj is not None and hasattr(started_at_obj, "isoformat")
                    else ""
                )
                completed_at_obj = row[3]
                completed_at_val = (
                    completed_at_obj.isoformat()
                    if completed_at_obj is not None and hasattr(completed_at_obj, "isoformat")
                    else None
                )
                status_val = str(row[4]) if row[4] else "unknown"
                provider_val = str(row[5]) if row[5] else None
                model_val = str(row[6]) if row[6] else None
                duration_val = int(row[7]) if row[7] else None
                error_val = str(row[9]) if row[9] else None

                runs.append(
                    AgentRunDetail(
                        id=run_id,
                        agent_type=agent_type_val,
                        started_at=started_at_val,
                        completed_at=completed_at_val,
                        status=status_val,
                        provider=provider_val,
                        model=model_val,
                        duration_ms=duration_val,
                        token_usage=token_usage,
                        error=error_val,
                    )
                )

            return runs, total_count

    def get_provider_comparison(self, days: int = 30) -> list[ProviderMetrics]:
        """Get detailed provider comparison metrics.

        Args:
            days: Number of days to include

        Returns:
            List of ProviderMetrics for each provider
        """
        summary = self.get_summary(days=days)
        return summary.by_provider

    def get_token_summary(self, days: int = 7) -> dict[str, Any]:
        """Get token usage summary for the UI.

        Args:
            days: Number of days to include (7, 14, or 30)

        Returns:
            Dict with total_tokens, by_provider breakdown, by_agent breakdown
        """
        now = datetime.now(UTC)
        start_date = now - timedelta(days=days)

        with self.conn_mgr.connection() as conn:
            # Get total tokens
            result = conn.execute(
                """
                SELECT COALESCE(SUM((token_usage->>'total_tokens')::int), 0) as total_tokens
                FROM agent_runs
                WHERE started_at >= %s AND token_usage IS NOT NULL
                """,
                [start_date],
            )
            row = result.fetchone()
            total_tokens = int(row[0] or 0) if row else 0

            # Get by provider
            result = conn.execute(
                """
                SELECT
                    COALESCE(provider, 'unknown') as provider,
                    COALESCE(SUM((token_usage->>'total_tokens')::int), 0) as total_tokens
                FROM agent_runs
                WHERE started_at >= %s AND token_usage IS NOT NULL
                GROUP BY provider
                ORDER BY total_tokens DESC
                """,
                [start_date],
            )
            by_provider = {str(r[0]): int(r[1] or 0) for r in result.fetchall()}

            # Get by agent type
            result = conn.execute(
                """
                SELECT
                    COALESCE(agent_type, 'unknown') as agent_type,
                    COALESCE(SUM((token_usage->>'total_tokens')::int), 0) as total_tokens
                FROM agent_runs
                WHERE started_at >= %s AND token_usage IS NOT NULL
                GROUP BY agent_type
                ORDER BY total_tokens DESC
                """,
                [start_date],
            )
            by_agent = {str(r[0]): int(r[1] or 0) for r in result.fetchall()}

            return {
                "total_tokens": total_tokens,
                "by_provider": by_provider,
                "by_agent": by_agent,
                "period_days": days,
                "period_start": start_date.isoformat(),
                "period_end": now.isoformat(),
            }
