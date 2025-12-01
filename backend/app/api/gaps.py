"""Trading Intelligence Gap Detection API.

Endpoints:
- GET /api/gaps/summary - System-wide gap summary with coverage %
- GET /api/gaps/by-analysis - Gaps grouped by analysis type
- GET /api/gaps/by-ticker/{ticker} - Per-ticker gap analysis
- GET /api/gaps/watchlist - Gaps affecting current watchlist
- POST /api/gaps/generate-task-list - Generate task list to fill specific gaps
"""

from __future__ import annotations

from typing import Any, TypedDict, cast

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..logging_config import get_logger
from ..services.gap_detection import GapDetector
from ..storage.connection import ConnectionManager

logger = get_logger(__name__)

router = APIRouter(prefix="/api/gaps", tags=["gaps"])


# ========================================================================
# TypedDict Definitions for Response Data
# ========================================================================


class CoverageResult(TypedDict, total=False):
    """Coverage analysis result for an analysis type."""

    coverage_pct: float
    gaps: list[dict[str, str | int | float]]  # GapInfo dicts
    maturity_level: str


class MVPWeek(TypedDict, total=False):
    """Single week in the MVP roadmap."""

    phase: str
    focus: str
    gaps: list[str]
    deliverable: str
    expected_edge: str  # Only present in week_4


class MVPRoadmap(TypedDict, total=False):
    """MVP roadmap data."""

    goal: str
    week_1: MVPWeek
    week_2: MVPWeek
    week_3: MVPWeek
    week_4: MVPWeek


class DataAvailability(TypedDict):
    """Data availability status for a table."""

    available: bool
    row_count: int


class TickerCoverageByAnalysis(TypedDict):
    """Coverage percentage by analysis type for a ticker."""

    technical: float
    fundamental: float
    sentiment: float
    risk: float
    execution: float
    macro: float
    ml: float
    compliance: float


class AggregateGap(TypedDict):
    """Gap affecting multiple tickers."""

    gap_id: str
    description: str
    affected_tickers: int
    priority: str


class GapSummaryDict(TypedDict):
    """Gap summary response data."""

    total_gaps: int
    p0_gaps: int
    p1_gaps: int
    p2_gaps: int
    p3_gaps: int
    analysis_types: dict[str, CoverageResult]
    avg_coverage_pct: float
    top_10_priorities: list[dict[str, Any]]
    mvp_roadmap: MVPRoadmap


class GapsByAnalysisDict(TypedDict):
    """Gaps by analysis type response."""

    analysis_types: dict[str, CoverageResult]


class TickerGapsDict(TypedDict):
    """Per-ticker gap analysis response."""

    ticker: str
    readiness_score: float
    confidence_level: str
    coverage_by_analysis: TickerCoverageByAnalysis
    missing_capabilities: list[str]
    data_availability: dict[str, DataAvailability]


class WatchlistGapsDict(TypedDict):
    """Watchlist gap analysis response."""

    watchlist_tickers: list[str]
    ticker_coverage: dict[str, TickerGapsDict]
    aggregate_gaps: list[AggregateGap]


class TaskListGeneratedDict(TypedDict):
    """Task list generation response."""

    gap_ids: list[str]
    task_file: str
    message: str


# ========================================================================
# Request Models
# ========================================================================


class GenerateTaskListRequest(BaseModel):
    """Request to generate task list for specific gaps."""

    gap_ids: list[str] = Field(
        ...,
        description="List of gap IDs to fill (e.g., ['GAP-001', 'GAP-012'])",
        min_length=1,
    )
    priority: str | None = Field(
        None,
        description="Task priority (HIGH, MEDIUM, LOW)",
    )


# ========================================================================
# Response Models
# ========================================================================


class GapSummaryResponse(BaseModel):
    """Summary of all gaps across the system."""

    timestamp: str
    total_gaps: int
    p0_gaps: int
    p1_gaps: int
    p2_gaps: int
    p3_gaps: int
    analysis_types: dict[str, Any]  # analysis_type → CoverageResult (complex nested)
    avg_coverage_pct: float
    top_10_priorities: list[dict[str, Any]]  # GapInfo with nested structures
    mvp_roadmap: dict[str, Any]  # Complex nested week structure


class GapsByAnalysisResponse(BaseModel):
    """Gaps grouped by analysis type."""

    analysis_types: dict[str, Any]  # analysis_type → CoverageResult (complex nested)


class TickerGapsResponse(BaseModel):
    """Per-ticker gap analysis."""

    ticker: str
    readiness_score: float  # 0-100% overall readiness
    confidence_level: str  # LOW/MEDIUM/HIGH
    coverage_by_analysis: dict[str, float]  # analysis_type → coverage %
    missing_capabilities: list[str]  # Top 10 missing capabilities
    data_availability: dict[str, DataAvailability]  # table → availability status


class WatchlistGapsResponse(BaseModel):
    """Gaps affecting current watchlist."""

    watchlist_tickers: list[str]
    ticker_coverage: dict[str, TickerCoverageByAnalysis]  # ticker → coverage by analysis
    aggregate_gaps: list[AggregateGap]  # Gaps affecting multiple tickers


class TaskListGeneratedResponse(BaseModel):
    """Task list generation result."""

    gap_ids: list[str]
    task_file: str
    message: str


# ========================================================================
# Endpoints
# ========================================================================


@router.get("/summary", response_model=GapSummaryResponse)
async def get_gap_summary() -> GapSummaryDict:
    """Get system-wide gap summary with coverage % per analysis type.

    Returns complete gap analysis including:
    - Total gaps by criticality (P0/P1/P2/P3)
    - Coverage % per analysis type
    - TOP 10 priority gaps (ranked by impact x 1/effort)
    - MVP roadmap (4-week plan to achieve trading edge)

    Raises:
        HTTPException: 500 if analysis fails
    """
    logger.info("get_gap_summary_request")

    try:
        conn_mgr = ConnectionManager()
        detector = GapDetector(conn_mgr)

        result = detector.analyze_gaps()

        # Calculate average coverage across all analysis types
        coverage_values = [at["coverage_pct"] for at in result["analysis_types"].values()]
        avg_coverage = sum(coverage_values) / len(coverage_values) if coverage_values else 0.0

        response = {
            **result,
            "avg_coverage_pct": round(avg_coverage, 1),
        }

        logger.info(
            "gap_summary_returned",
            total_gaps=result["total_gaps"],
            p0_gaps=result["p0_gaps"],
            avg_coverage=round(avg_coverage, 1),
        )

        return cast(GapSummaryDict, response)

    except Exception as e:
        logger.error("gap_summary_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Gap analysis failed: {e!s}",
        ) from e


@router.get("/by-analysis", response_model=GapsByAnalysisResponse)
async def get_gaps_by_analysis() -> GapsByAnalysisDict:
    """Get gaps grouped by analysis type.

    Returns detailed breakdown per analysis type:
    - Technical Analysis: coverage %, gaps, maturity level
    - Fundamental Analysis: coverage %, gaps, maturity level
    - Sentiment Analysis: coverage %, gaps, maturity level
    - Risk Analysis: coverage %, gaps, maturity level
    - Execution Quality: coverage %, gaps, maturity level
    - Macro Analysis: coverage %, gaps, maturity level
    - ML Infrastructure: coverage %, gaps, maturity level
    - Compliance: coverage %, gaps, maturity level

    Raises:
        HTTPException: 500 if analysis fails
    """
    logger.info("get_gaps_by_analysis_request")

    try:
        conn_mgr = ConnectionManager()
        detector = GapDetector(conn_mgr)

        result = detector.analyze_gaps()

        response = {
            "analysis_types": result["analysis_types"],
        }

        logger.info(
            "gaps_by_analysis_returned",
            analysis_types=len(result["analysis_types"]),
        )

        return cast(GapsByAnalysisDict, response)

    except Exception as e:
        logger.error("gaps_by_analysis_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Gap analysis failed: {e!s}",
        ) from e


@router.get("/by-ticker/{ticker}", response_model=TickerGapsResponse)
async def get_ticker_gaps(ticker: str) -> TickerGapsDict:
    """Get per-ticker gap analysis.

    Analyzes data availability for a specific ticker across all analysis types.
    Useful for understanding: "Can I analyze NVDA fundamentally? What's missing?"

    Args:
        ticker: Stock ticker symbol (e.g., "NVDA", "AAPL")

    Returns:
        Ticker-specific coverage % and missing capabilities per analysis type

    Raises:
        HTTPException: 500 if analysis fails
    """
    logger.info("get_ticker_gaps_request", ticker=ticker)

    try:
        conn_mgr = ConnectionManager()
        detector = GapDetector(conn_mgr)

        result = detector.analyze_ticker_gaps(ticker.upper())

        logger.info(
            "ticker_gaps_returned",
            ticker=ticker,
        )

        return cast(TickerGapsDict, result)

    except Exception as e:
        logger.error("ticker_gaps_failed", ticker=ticker, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Ticker gap analysis failed: {e!s}",
        ) from e


@router.get("/watchlist", response_model=WatchlistGapsResponse)
async def get_watchlist_gaps() -> WatchlistGapsDict:
    """Get gaps affecting current watchlist.

    Analyzes data coverage for all tickers in the active watchlist.
    Identifies gaps that affect multiple tickers:
    - "8/12 watchlist tickers missing earnings data"
    - "All watchlist tickers missing options flow data"

    Returns:
        Per-ticker coverage matrix and aggregate gaps

    Raises:
        HTTPException: 500 if analysis fails
    """
    logger.info("get_watchlist_gaps_request")

    try:
        conn_mgr = ConnectionManager()
        detector = GapDetector(conn_mgr)

        result = detector.analyze_watchlist_gaps()

        logger.info("watchlist_gaps_returned")

        return cast(WatchlistGapsDict, result)

    except Exception as e:
        logger.error("watchlist_gaps_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Watchlist gap analysis failed: {e!s}",
        ) from e


@router.post("/generate-task-list", response_model=TaskListGeneratedResponse)
async def generate_task_list(request: GenerateTaskListRequest) -> TaskListGeneratedDict:
    """Generate task list to fill specific gaps.

    Creates a detailed task file (tasks-XXXX-fill-gaps.md) with:
    - Implementation steps per gap
    - Data sources to integrate
    - Estimated effort
    - Success criteria
    - Code references

    User can then run `/do_it tasks-XXXX-fill-gaps.md` to start implementation.

    Args:
        request: Gap IDs to fill + optional priority

    Returns:
        Task file path and summary

    Raises:
        HTTPException: 400 if invalid gap_ids
        HTTPException: 500 if generation fails
    """
    logger.info(
        "generate_task_list_request",
        gap_ids=request.gap_ids,
        priority=request.priority,
    )

    # Validate gap_ids format
    for gap_id in request.gap_ids:
        if not gap_id.startswith("GAP-"):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid gap_id format: {gap_id} (expected GAP-XXX)",
            )

    try:
        conn_mgr = ConnectionManager()
        detector = GapDetector(conn_mgr)

        result = detector.generate_task_list(request.gap_ids)

        logger.info(
            "task_list_generated",
            gap_ids=request.gap_ids,
        )

        return cast(TaskListGeneratedDict, result)

    except Exception as e:
        logger.error("task_list_generation_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Task list generation failed: {e!s}",
        ) from e
