"""Ideas API router."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agents.discovery import DiscoveryAgent
from app.agents.portfolio_analyzer import PortfolioAnalyzerAgent
from app.agents.tools import AgentTools
from app.portfolio.analytics import PortfolioAnalytics
from app.portfolio.manager import PortfolioManager
from app.portfolio.price_fetcher import PriceDataFetcher
from app.sources.fred import FREDSource
from app.sources.news import GoogleNewsSource
from app.storage import get_storage

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
    agent_run_id: str
    num_ideas: int
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
    # Build query
    where_clauses = []
    params = []

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

    return IdeasListResponse(ideas=ideas, count=len(ideas))


@router.post("/generate", response_model=GenerateIdeasResponse)
async def generate_ideas(request: GenerateIdeasRequest) -> GenerateIdeasResponse:
    """Generate new investment ideas by running an agent."""
    # Initialize agent tools
    news_source = GoogleNewsSource()
    fred_source = FREDSource()
    price_fetcher = PriceDataFetcher(storage)
    portfolio_mgr = PortfolioManager(storage)
    analytics = PortfolioAnalytics()

    agent_tools = AgentTools(
        storage=storage,
        news_source=news_source,
        fred_source=fred_source,
        price_fetcher=price_fetcher,
        portfolio_mgr=portfolio_mgr,
        analytics=analytics,
    )

    # Create and run agent
    if request.agent_type == "discovery":
        agent = DiscoveryAgent(storage=storage, tools=agent_tools)
    elif request.agent_type == "portfolio_analyzer":
        agent = PortfolioAnalyzerAgent(storage=storage, tools=agent_tools)
    else:
        raise HTTPException(status_code=400, detail="Invalid agent type")

    # Run agent
    result = agent.run()

    if result["status"] != "completed":
        raise HTTPException(
            status_code=500,
            detail=f"Agent run failed: {result.get('error', 'Unknown error')}",
        )

    # Get run info from database
    with storage.connection() as conn:
        run_info = conn.execute(
            "SELECT id, num_ideas FROM agent_runs WHERE agent_type = ? ORDER BY started_at DESC LIMIT 1",
            [agent.agent_type],
        ).fetchone()

    return GenerateIdeasResponse(
        status="completed",
        agent_run_id=run_info[0],
        num_ideas=run_info[1],
        agent_type=request.agent_type,
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

    # Return updated idea
    with storage.connection() as conn:
        result = conn.execute("SELECT * FROM agent_ideas WHERE id = ?", [idea_id]).fetchone()

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
