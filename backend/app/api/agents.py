"""Agent telemetry API endpoints.

Provides endpoints for:
- Telemetry summary (token usage, costs, latency)
- Run history with filtering and pagination
- Provider comparison metrics
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Query, Request

from ..logging_config import get_logger
from ..middleware.cache import cache_response
from ..services.agent_telemetry import (
    AgentRunDetail,
    AgentTelemetryService,
    ProviderMetrics,
    TelemetrySummary,
    TokenUsage,
)
from ..storage.connection import get_connection_manager

logger = get_logger(__name__)

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("/telemetry/summary", response_model=TelemetrySummary)
@cache_response(ttl=60)  # 1 minute cache for telemetry summary
async def get_telemetry_summary(
    request: Request,
    days: int = Query(default=7, ge=1, le=90, description="Number of days to include"),
) -> TelemetrySummary:
    """Get agent telemetry summary for the specified period.

    Returns aggregated metrics including:
    - Total runs, success/failure counts
    - Token usage by provider
    - Daily breakdown for charts
    - Cost estimates (effectively $0 for CLI)
    """
    conn_mgr = get_connection_manager()
    service = AgentTelemetryService(conn_mgr)
    return service.get_summary(days=days)


@router.get("/telemetry/history")
async def get_run_history(
    limit: int = Query(default=50, ge=1, le=200, description="Maximum runs to return"),
    offset: int = Query(default=0, ge=0, description="Number of runs to skip"),
    provider: str | None = Query(default=None, description="Filter by provider (gemini, claude)"),
    status: str | None = Query(default=None, description="Filter by status (completed, failed)"),
    agent_type: str | None = Query(default=None, description="Filter by agent type"),
) -> dict[str, list[AgentRunDetail] | int]:
    """Get paginated agent run history with filtering.

    Returns:
        - runs: List of agent run details
        - total: Total count matching filters
        - limit: Page size
        - offset: Current offset
    """
    conn_mgr = get_connection_manager()
    service = AgentTelemetryService(conn_mgr)
    runs, total = service.get_run_history(
        limit=limit,
        offset=offset,
        provider=provider,
        status=status,
        agent_type=agent_type,
    )
    return {
        "runs": runs,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/telemetry/providers", response_model=list[ProviderMetrics])
async def get_provider_comparison(
    days: int = Query(default=30, ge=1, le=90, description="Number of days to include"),
) -> list[ProviderMetrics]:
    """Get provider comparison metrics.

    Returns metrics for each LLM provider:
    - Run counts and success rates
    - Token usage and costs
    - Average duration
    """
    conn_mgr = get_connection_manager()
    service = AgentTelemetryService(conn_mgr)
    return service.get_provider_comparison(days=days)


@router.get("/runs/{run_id}", response_model=AgentRunDetail | None)
async def get_run_detail(run_id: str) -> AgentRunDetail | None:
    """Get details for a specific agent run.

    Args:
        run_id: UUID of the agent run

    Returns:
        Run details or None if not found
    """
    conn_mgr = get_connection_manager()

    # Get specific run by querying with the ID
    with conn_mgr.connection() as conn:
        result = conn.execute(
            """
            SELECT
                id, agent_type, started_at, completed_at, status,
                provider, model, duration_ms, token_usage, error_message
            FROM agent_runs
            WHERE id = %s
            """,
            [run_id],
        )
        row = result.fetchone()

        if not row:
            return None

        token_usage = None
        raw_token = row[8]
        if raw_token:
            try:
                tu = json.loads(raw_token) if isinstance(raw_token, str) else dict(raw_token)  # type: ignore[call-overload]
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
        started_at_val = row[2].isoformat() if hasattr(row[2], "isoformat") else ""  # type: ignore[union-attr]
        completed_at_val = row[3].isoformat() if hasattr(row[3], "isoformat") else None  # type: ignore[union-attr]
        status_val = str(row[4]) if row[4] else "unknown"
        provider_val = str(row[5]) if row[5] else None
        model_val = str(row[6]) if row[6] else None
        duration_val = int(row[7]) if row[7] else None
        error_val = str(row[9]) if row[9] else None

        return AgentRunDetail(
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
