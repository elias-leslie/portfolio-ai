"""Ideas API router."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from celery.result import AsyncResult  # type: ignore[import-untyped]
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.analytics.agent_performance import get_agent_performance, get_agent_performance_summary
from app.celery_app import celery_app
from app.logging_config import get_logger
from app.storage import get_storage
from app.tasks.agent_tasks import run_discovery_agent, run_portfolio_analyzer

logger = get_logger(__name__)

router = APIRouter(prefix="/api/ideas", tags=["ideas"])

# Initialize services
storage = get_storage()


# Request/Response models
class GenerateIdeasRequest(BaseModel):
    """Request model for generating ideas."""

    agent_type: Literal["discovery", "portfolio_analyzer"] = Field(
        ..., description="Type of agent to run"
    )


class IdeaResponse(BaseModel):
    """Response model for a single idea."""

    id: str
    agent_run_id: str
    idea_type: str
    title: str
    thesis: str
    action: str
    confidence_score: float
    risk_level: str
    reward_estimate: str | None
    portfolio_impact: str | None
    data_needed: str | None
    risks: str | None
    status: str
    created_at: str
    updated_at: str


class IdeasListResponse(BaseModel):
    """Response model for list of ideas."""

    ideas: list[IdeaResponse]
    count: int


class GenerateIdeasResponse(BaseModel):
    """Response model for generate ideas."""

    status: str
    run_id: str | None = None
    task_id: str | None = None
    num_ideas: int | None = None
    agent_type: str


class UpdateIdeaStatusRequest(BaseModel):
    """Request model for updating idea status."""

    status: Literal["pending", "validated", "executed", "rejected"] = Field(
        ..., description="New status"
    )


@router.get("/", response_model=IdeasListResponse)
async def get_ideas(
    idea_type: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> IdeasListResponse:
    """Get investment ideas with optional filtering."""
    logger.info(
        "get_ideas_request",
        idea_type=idea_type,
        status=status,
        limit=limit,
    )

    # Build query
    where_clauses = []
    params: list[str | int] = []

    if idea_type:
        where_clauses.append("idea_type = ?")
        params.append(idea_type)

    if status:
        where_clauses.append("status = ?")
        params.append(status)

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    query = f"""
        SELECT *
        FROM agent_ideas
        {where_sql}
        ORDER BY confidence_score DESC, created_at DESC
        LIMIT ?
    """
    params.append(limit)

    with storage.connection() as conn:
        results = conn.execute(query, params).fetchall()

    ideas = []
    for row in results:
        ideas.append(
            IdeaResponse(
                id=row[0],
                agent_run_id=row[1],
                idea_type=row[2],
                title=row[3],
                thesis=row[4],
                action=row[5],
                confidence_score=row[6],
                risk_level=row[7],
                reward_estimate=row[8],
                portfolio_impact=row[9],
                data_needed=row[10],
                risks=row[11],
                status=row[12],
                created_at=row[13].isoformat(),
                updated_at=row[14].isoformat(),
            )
        )

    logger.info(
        "get_ideas_response",
        count=len(ideas),
        idea_type=idea_type,
        status=status,
    )

    return IdeasListResponse(ideas=ideas, count=len(ideas))


@router.post("/generate", response_model=GenerateIdeasResponse)
async def generate_ideas(request: GenerateIdeasRequest) -> GenerateIdeasResponse:
    """Generate new investment ideas by running an agent in the background."""
    logger.info(
        "generate_ideas_request",
        agent_type=request.agent_type,
    )

    try:
        # Dispatch task to Celery
        if request.agent_type == "discovery":
            task = run_discovery_agent.apply_async()
        elif request.agent_type == "portfolio_analyzer":
            task = run_portfolio_analyzer.apply_async()
        else:
            raise HTTPException(status_code=400, detail="Invalid agent type")

        logger.info(
            "generate_ideas_dispatched",
            agent_type=request.agent_type,
            task_id=task.id,
        )

        return GenerateIdeasResponse(
            status="running",
            task_id=task.id,
            agent_type=request.agent_type,
        )
    except Exception as e:
        logger.error(
            "generate_ideas_task_dispatch_failed",
            agent_type=request.agent_type,
            error=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to dispatch agent task: {e!s}",
        ) from e


class AgentRunStatusResponse(BaseModel):
    """Response model for agent run status."""

    status: Literal["PENDING", "STARTED", "SUCCESS", "FAILURE"]
    run_id: str | None = None
    num_ideas: int | None = None
    error: str | None = None


@router.get("/runs/{task_id}/status", response_model=AgentRunStatusResponse)
async def get_agent_run_status(task_id: str) -> AgentRunStatusResponse:
    """Get the status of a running agent task."""
    logger.debug(
        "get_agent_run_status_request",
        task_id=task_id,
    )

    # Get Celery task status
    task_result = AsyncResult(task_id, app=celery_app)

    logger.info(
        "agent_task_status",
        task_id=task_id,
        state=task_result.state,
    )

    if task_result.state == "PENDING":
        return AgentRunStatusResponse(status="PENDING")
    if task_result.state == "STARTED":
        return AgentRunStatusResponse(status="STARTED")
    if task_result.state == "SUCCESS":
        # Task completed - get run_id from result
        run_id = task_result.result

        # Query agent_runs for details
        with storage.connection() as conn:
            result = conn.execute(
                "SELECT num_ideas FROM agent_runs WHERE id = ?",
                [run_id],
            ).fetchone()

        if result:
            logger.info(
                "agent_run_completed",
                task_id=task_id,
                run_id=run_id,
                num_ideas=result[0],
            )
            return AgentRunStatusResponse(
                status="SUCCESS",
                run_id=run_id,
                num_ideas=result[0],
            )
        return AgentRunStatusResponse(
            status="SUCCESS",
            run_id=run_id,
        )
    if task_result.state == "FAILURE":
        error_msg = str(task_result.info) if task_result.info else "Unknown error"
        logger.error(
            "agent_task_failed",
            task_id=task_id,
            error=error_msg,
        )
        return AgentRunStatusResponse(
            status="FAILURE",
            error=error_msg,
        )
    return AgentRunStatusResponse(
        status="PENDING",
        error=f"Unknown task state: {task_result.state}",
    )


@router.get("/{idea_id}", response_model=IdeaResponse)
async def get_idea_details(idea_id: str) -> IdeaResponse:
    """Get detailed information about a specific idea."""
    with storage.connection() as conn:
        result = conn.execute("SELECT * FROM agent_ideas WHERE id = ?", [idea_id]).fetchone()

    if not result:
        raise HTTPException(status_code=404, detail="Idea not found")

    return IdeaResponse(
        id=result[0],
        agent_run_id=result[1],
        idea_type=result[2],
        title=result[3],
        thesis=result[4],
        action=result[5],
        confidence_score=result[6],
        risk_level=result[7],
        reward_estimate=result[8],
        portfolio_impact=result[9],
        data_needed=result[10],
        risks=result[11],
        status=result[12],
        created_at=result[13].isoformat(),
        updated_at=result[14].isoformat(),
    )


@router.patch("/{idea_id}/status")
async def update_idea_status(idea_id: str, request: UpdateIdeaStatusRequest) -> IdeaResponse:
    """Update the status of an investment idea."""
    # Check if idea exists
    with storage.connection() as conn:
        existing = conn.execute("SELECT * FROM agent_ideas WHERE id = ?", [idea_id]).fetchone()

    if not existing:
        raise HTTPException(status_code=404, detail="Idea not found")

    # Update status
    with storage.connection() as conn:
        conn.execute(
            "UPDATE agent_ideas SET status = ?, updated_at = ? WHERE id = ?",
            [request.status, datetime.now(), idea_id],
        )
        conn.commit()  # Commit the update

    # Return updated idea
    with storage.connection() as conn:
        result = conn.execute("SELECT * FROM agent_ideas WHERE id = ?", [idea_id]).fetchone()

    if result is None:
        raise HTTPException(status_code=404, detail=f"Idea {idea_id} not found")

    return IdeaResponse(
        id=result[0],
        agent_run_id=result[1],
        idea_type=result[2],
        title=result[3],
        thesis=result[4],
        action=result[5],
        confidence_score=result[6],
        risk_level=result[7],
        reward_estimate=result[8],
        portfolio_impact=result[9],
        data_needed=result[10],
        risks=result[11],
        status=result[12],
        created_at=result[13].isoformat(),
        updated_at=result[14].isoformat(),
    )


# Agent Performance Models
class BestWorstTradeModel(BaseModel):
    """Model for best/worst trade information."""

    ticker: str
    return_: float = Field(..., alias="return")
    entry_date: str | None
    exit_date: str | None
    holding_days: int | None

    class Config:
        """Pydantic config."""

        populate_by_name = True


class AgentPerformanceMetrics(BaseModel):
    """Model for agent performance metrics."""

    win_rate: float
    average_return: float
    average_winner: float
    average_loser: float
    win_loss_ratio: float | None
    total_ideas: int
    open_ideas: int
    closed_ideas: int
    best_trade: BestWorstTradeModel | None
    worst_trade: BestWorstTradeModel | None


class AgentPerformanceResponse(BaseModel):
    """Response model for agent performance."""

    agent_type: str
    period_days: int
    metrics: AgentPerformanceMetrics


class AgentSummaryMetrics(BaseModel):
    """Model for summarized agent metrics."""

    agent_type: str
    win_rate: float
    average_return: float
    average_winner: float
    average_loser: float
    win_loss_ratio: float | None
    total_ideas: int
    open_ideas: int
    closed_ideas: int
    best_trade: BestWorstTradeModel | None
    worst_trade: BestWorstTradeModel | None


class AgentPerformanceSummaryResponse(BaseModel):
    """Response model for all agents performance summary."""

    agents: list[AgentSummaryMetrics]
    period_days: int
    total_agents: int


@router.get("/agents/{agent_type}/performance", response_model=AgentPerformanceResponse)
async def get_agent_performance_endpoint(
    agent_type: str,
    days: int = 90,
) -> AgentPerformanceResponse:
    """Get performance metrics for a specific agent type.

    Analyzes paper trading outcomes to calculate win rate, average returns,
    and other key performance indicators for the specified agent over the
    given time period.

    Args:
        agent_type: Type of agent (e.g., "DiscoveryAgent", "PortfolioAnalyzerAgent")
        days: Number of days to look back for performance calculation (default: 90)

    Returns:
        Performance metrics including win rate, average returns, and best/worst trades

    Example:
        GET /api/ideas/agents/DiscoveryAgent/performance?days=90
    """
    logger.info(
        "get_agent_performance_request",
        agent_type=agent_type,
        days=days,
    )

    # Get performance metrics
    perf = get_agent_performance(storage, agent_type, days=days)

    logger.info(
        "get_agent_performance_response",
        agent_type=agent_type,
        days=days,
        win_rate=perf["metrics"]["win_rate"],
        total_ideas=perf["metrics"]["total_ideas"],
    )

    return AgentPerformanceResponse(**perf)


@router.get("/agents/performance/summary", response_model=AgentPerformanceSummaryResponse)
async def get_all_agents_performance(
    days: int = 30,
) -> AgentPerformanceSummaryResponse:
    """Get performance summary for all agent types.

    Returns performance metrics for all agents, enabling easy comparison
    of different agent strategies.

    Args:
        days: Number of days to look back (default: 30)

    Returns:
        List of agent performance metrics for comparison

    Example:
        GET /api/ideas/agents/performance/summary?days=30
    """
    logger.info(
        "get_all_agents_performance_request",
        days=days,
    )

    # Get summary for all agents
    summary = get_agent_performance_summary(storage, days=days)

    logger.info(
        "get_all_agents_performance_response",
        days=days,
        total_agents=summary["total_agents"],
    )

    return AgentPerformanceSummaryResponse(**summary)
