"""Agent telemetry API endpoints.

Provides endpoints for:
- Telemetry summary (token usage, costs, latency)
- Run history with filtering and pagination
- Provider comparison metrics
- Session tracking and conversation history (FEAT-223)
"""

from __future__ import annotations

import contextlib
import json
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

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


# FEAT-223: Session and conversation models
class ConversationMessage(BaseModel):
    """A single message in an agent conversation."""

    id: str
    sequence_num: int
    role: str
    content: str
    token_count: int | None = None
    created_at: str
    metadata: dict[str, Any] | None = None


class SessionInfo(BaseModel):
    """Agent session with derived type."""

    id: str
    agent_type: str
    run_type: str
    session_type: str  # Derived: user_single_agent, user_multi_agent, agent_agent_validation, agent_autonomous
    started_at: str
    completed_at: str | None = None
    status: str
    provider: str | None = None
    model: str | None = None
    token_count: int = 0
    parent_run_id: str | None = None
    summary: str | None = None  # Brief description of what the agent did


class DiscussRequest(BaseModel):
    """Request to start a discussion about a previous run."""

    original_run_id: str
    question: str
    target_agent: str | None = None  # Optional for multi-agent sessions


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


# FEAT-223: New endpoints for session tracking and conversation history


@router.get("/token-summary")
async def get_token_summary(
    days: int = Query(default=7, ge=1, le=90, description="Number of days (7, 14, or 30)"),
) -> dict[str, Any]:
    """Get token usage summary for the UI.

    Returns:
        - total_tokens: Total tokens used
        - by_provider: Breakdown by provider (gemini, claude)
        - by_agent: Breakdown by agent type
    """
    conn_mgr = get_connection_manager()
    service = AgentTelemetryService(conn_mgr)
    return service.get_token_summary(days=days)


@router.get("/runs/{run_id}/messages", response_model=list[ConversationMessage])
async def get_run_messages(run_id: str) -> list[ConversationMessage]:
    """Get full conversation history for an agent run.

    Args:
        run_id: UUID of the agent run

    Returns:
        List of conversation messages in order
    """
    conn_mgr = get_connection_manager()

    with conn_mgr.connection() as conn:
        # First verify the run exists
        run_check = conn.execute(
            "SELECT id FROM agent_runs WHERE id = %s",
            [run_id],
        )
        if not run_check.fetchone():
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

        # Get all messages for this run
        result = conn.execute(
            """
            SELECT id, sequence_num, role, content, token_count, created_at, metadata
            FROM agent_conversation_messages
            WHERE agent_run_id = %s
            ORDER BY sequence_num ASC
            """,
            [run_id],
        )

        messages = []
        for row in result.fetchall():
            metadata = None
            if row[6]:
                with contextlib.suppress(json.JSONDecodeError, TypeError):
                    if isinstance(row[6], str):
                        metadata = json.loads(row[6])
                    elif isinstance(row[6], dict):
                        metadata = row[6]

            # Safe int conversion for token_count
            token_count_val = None
            if row[4] is not None:
                with contextlib.suppress(ValueError, TypeError):
                    token_count_val = int(row[4])

            # Safe datetime formatting
            created_at_val = str(row[5]) if row[5] else ""
            if row[5] and hasattr(row[5], "isoformat"):
                created_at_val = row[5].isoformat()

            messages.append(
                ConversationMessage(
                    id=str(row[0]),
                    sequence_num=int(row[1]) if row[1] is not None else 0,
                    role=str(row[2]) if row[2] else "unknown",
                    content=str(row[3]) if row[3] else "",
                    token_count=token_count_val,
                    created_at=created_at_val,
                    metadata=metadata,
                )
            )

        return messages


def _derive_session_type(run_type: str, parent_run_id: str | None) -> str:
    """Derive session type from run_type and parent_run_id.

    Args:
        run_type: The run_type column value (automated, user_chat, cross_validation)
        parent_run_id: Parent run ID if this is a linked run

    Returns:
        Derived session type string
    """
    if run_type == "cross_validation":
        return "agent_agent_validation"
    if run_type == "user_chat":
        if parent_run_id:
            return "user_multi_agent"
        return "user_single_agent"
    return "agent_autonomous"


@router.get("/sessions", response_model=list[SessionInfo])
async def get_sessions(
    limit: int = Query(default=50, ge=1, le=200, description="Maximum sessions to return"),
    offset: int = Query(default=0, ge=0, description="Number of sessions to skip"),
    run_type: str | None = Query(default=None, description="Filter by run type"),
    provider: str | None = Query(default=None, description="Filter by provider"),
) -> list[SessionInfo]:
    """Get agent sessions with derived session types.

    Returns sessions with:
    - Derived session type (user_single_agent, user_multi_agent, etc.)
    - Token counts
    - Summary of what the agent did
    """
    conn_mgr = get_connection_manager()

    with conn_mgr.connection() as conn:
        # Build WHERE clause
        conditions: list[str] = []
        params: list[Any] = []

        if run_type:
            conditions.append("run_type = %s")
            params.append(run_type)
        if provider:
            conditions.append("provider = %s")
            params.append(provider)

        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        params.extend([limit, offset])

        result = conn.execute(
            f"""
            SELECT
                id, agent_type, run_type, started_at, completed_at, status,
                provider, model, token_usage, parent_run_id, metadata
            FROM agent_runs
            {where_clause}
            ORDER BY started_at DESC
            LIMIT %s OFFSET %s
            """,
            params,
        )

        sessions = []
        for row in result.fetchall():
            # Extract token count from token_usage JSON
            token_count = 0
            if row[8]:
                try:
                    if isinstance(row[8], str):
                        tu = json.loads(row[8])
                    elif isinstance(row[8], dict):
                        tu = row[8]
                    else:
                        tu = {}
                    token_count = tu.get("total_tokens", 0)
                except (json.JSONDecodeError, TypeError):
                    pass

            # Extract summary from metadata if available
            summary = None
            if row[10]:
                try:
                    if isinstance(row[10], str):
                        meta = json.loads(row[10])
                    elif isinstance(row[10], dict):
                        meta = row[10]
                    else:
                        meta = {}
                    summary = meta.get("summary")
                except (json.JSONDecodeError, TypeError):
                    pass

            run_type_val = str(row[2]) if row[2] else "automated"
            parent_run_id_val = str(row[9]) if row[9] else None
            session_type = _derive_session_type(run_type_val, parent_run_id_val)

            # Safe datetime formatting
            started_at_val = str(row[3]) if row[3] else ""
            if row[3] and hasattr(row[3], "isoformat"):
                started_at_val = row[3].isoformat()

            completed_at_val = None
            if row[4] and hasattr(row[4], "isoformat"):
                completed_at_val = row[4].isoformat()

            sessions.append(
                SessionInfo(
                    id=str(row[0]),
                    agent_type=str(row[1]) if row[1] else "unknown",
                    run_type=run_type_val,
                    session_type=session_type,
                    started_at=started_at_val,
                    completed_at=completed_at_val,
                    status=str(row[5]) if row[5] else "unknown",
                    provider=str(row[6]) if row[6] else None,
                    model=str(row[7]) if row[7] else None,
                    token_count=token_count,
                    parent_run_id=parent_run_id_val,
                    summary=summary,
                )
            )

        return sessions


@router.post("/discuss")
async def start_discussion(request: DiscussRequest) -> dict[str, Any]:
    """Start a discussion about a previous agent run.

    This creates a new run linked to the original, allowing the user to
    ask follow-up questions with the original conversation as context.

    Note: This endpoint creates the run record. Actual chat implementation
    requires frontend WebSocket/streaming support.

    Args:
        request: DiscussRequest with original_run_id and question

    Returns:
        New run info with conversation context loaded
    """
    conn_mgr = get_connection_manager()

    with conn_mgr.connection() as conn:
        # Verify original run exists and get its info
        result = conn.execute(
            """
            SELECT id, agent_type, provider, model
            FROM agent_runs
            WHERE id = %s
            """,
            [request.original_run_id],
        )
        original = result.fetchone()
        if not original:
            raise HTTPException(
                status_code=404, detail=f"Original run {request.original_run_id} not found"
            )

        # Get conversation history from original run
        messages_result = conn.execute(
            """
            SELECT role, content
            FROM agent_conversation_messages
            WHERE agent_run_id = %s
            ORDER BY sequence_num ASC
            """,
            [request.original_run_id],
        )
        original_messages = [
            {"role": str(row[0]), "content": str(row[1])} for row in messages_result.fetchall()
        ]

        # For now, return the context that would be used
        # Full implementation requires agent execution (Phase 5 or separate PR)
        return {
            "status": "ready",
            "original_run_id": request.original_run_id,
            "original_agent_type": str(original[1]),
            "original_provider": str(original[2]) if original[2] else None,
            "original_model": str(original[3]) if original[3] else None,
            "original_messages_count": len(original_messages),
            "question": request.question,
            "message": "Discussion context prepared. Full chat implementation pending.",
        }
