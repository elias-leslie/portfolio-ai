"""SQL query helpers for agent telemetry aggregation."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from ._telemetry_models import (
    AgentRunDetail,
    DailyTelemetry,
    ProviderMetrics,
    TokenUsage,
)


def _iso(obj: Any) -> str:
    """Convert a date/datetime object to ISO string, or empty string."""
    if obj is not None and hasattr(obj, "isoformat"):
        return obj.isoformat()
    return str(obj or "")


def _parse_token_usage(raw: Any) -> TokenUsage | None:
    """Parse raw token_usage column value into a TokenUsage dict."""
    if not raw:
        return None
    try:
        tu: dict[str, Any] = json.loads(raw) if isinstance(raw, str) else (raw if isinstance(raw, dict) else {})
        return TokenUsage(
            input_tokens=tu.get("input_tokens", 0),
            output_tokens=tu.get("output_tokens", 0),
            total_tokens=tu.get("total_tokens", 0),
        )
    except (json.JSONDecodeError, TypeError):
        return None


def fetch_overall_aggregates(conn: Any, start_date: datetime) -> tuple[int, int, int, float]:
    """Return (total_runs, successful_runs, failed_runs, avg_duration_ms)."""
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
        return 0, 0, 0, 0.0
    return (
        int(row[0] or 0),
        int(row[1] or 0),
        int(row[2] or 0),
        float(row[3]) if row[3] else 0.0,
    )


def fetch_token_aggregates(conn: Any, start_date: datetime) -> tuple[int, int, int]:
    """Return (total_input_tokens, total_output_tokens, total_tokens)."""
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
    row = result.fetchone()
    if not row:
        return 0, 0, 0
    return int(row[0] or 0), int(row[1] or 0), int(row[2] or 0)


def fetch_provider_metrics(conn: Any, start_date: datetime) -> list[ProviderMetrics]:
    """Return per-provider metrics for the given period."""
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
    metrics: list[ProviderMetrics] = []
    for row in result.fetchall():
        total = int(row[1] or 0)
        success = int(row[2] or 0)
        tokens = int(row[5] or 0)
        metrics.append(
            ProviderMetrics(
                provider=str(row[0]) if row[0] else "unknown",
                total_runs=total,
                successful_runs=success,
                failed_runs=int(row[3] or 0),
                success_rate=round((success / total * 100) if total > 0 else 0.0, 1),
                total_tokens=tokens,
                avg_tokens_per_run=round((tokens / total) if total > 0 else 0.0, 0),
                avg_duration_ms=round(float(row[4]) if row[4] else 0.0, 0),
                total_cost_usd=0.0,  # CLI execution is free
            )
        )
    return metrics


def fetch_daily_breakdown(conn: Any, start_date: datetime) -> list[DailyTelemetry]:
    """Return per-day telemetry for the given period."""
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
    daily: list[DailyTelemetry] = []
    for row in result.fetchall():
        daily.append(
            DailyTelemetry(
                date=_iso(row[0]),
                total_runs=int(row[1] or 0),
                successful_runs=int(row[2] or 0),
                failed_runs=int(row[3] or 0),
                total_input_tokens=int(row[4] or 0),
                total_output_tokens=int(row[5] or 0),
                total_tokens=int(row[6] or 0),
                avg_duration_ms=round(float(row[7]), 0) if row[7] else 0.0,
                estimated_cost_usd=0.0,  # CLI is free
            )
        )
    return daily


def fetch_run_history(
    conn: Any,
    where_clause: str,
    params: list[Any],
    limit: int,
    offset: int,
) -> tuple[list[AgentRunDetail], int]:
    """Return (runs, total_count) for the given filter parameters."""
    count_result = conn.execute(
        f"SELECT COUNT(*) FROM agent_runs {where_clause}",
        params,
    )
    count_row = count_result.fetchone()
    total_count = int(count_row[0]) if count_row else 0

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
        [*params, limit, offset],
    )

    runs: list[AgentRunDetail] = []
    for row in result.fetchall():
        completed_obj = row[3]
        runs.append(
            AgentRunDetail(
                id=str(row[0]),
                agent_type=str(row[1]) if row[1] else "unknown",
                started_at=_iso(row[2]),
                completed_at=_iso(completed_obj) if completed_obj is not None else None,
                status=str(row[4]) if row[4] else "unknown",
                provider=str(row[5]) if row[5] else None,
                model=str(row[6]) if row[6] else None,
                duration_ms=int(row[7]) if row[7] else None,
                token_usage=_parse_token_usage(row[8]),
                error=str(row[9]) if row[9] else None,
            )
        )
    return runs, total_count


def fetch_token_summary_by_group(conn: Any, start_date: datetime, group_col: str) -> dict[str, int]:
    """Return token totals grouped by the given column name."""
    result = conn.execute(
        f"""
        SELECT
            COALESCE({group_col}, 'unknown') as grp,
            COALESCE(SUM((token_usage->>'total_tokens')::int), 0) as total_tokens
        FROM agent_runs
        WHERE started_at >= %s AND token_usage IS NOT NULL
        GROUP BY {group_col}
        ORDER BY total_tokens DESC
        """,
        [start_date],
    )
    return {str(r[0]): int(r[1] or 0) for r in result.fetchall()}


__all__ = [
    "fetch_daily_breakdown",
    "fetch_overall_aggregates",
    "fetch_provider_metrics",
    "fetch_run_history",
    "fetch_token_aggregates",
    "fetch_token_summary_by_group",
]
