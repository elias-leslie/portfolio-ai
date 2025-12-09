"""Trading Intelligence Gap Detection API.

**DEPRECATED**: Trading requirements have been migrated to Features.
Use the Features API at /api/capabilities/features/ with category filter "Data - *".

This API is maintained for backwards compatibility only.
Trading gaps are now tracked as features with source='trading_requirement'.

Legacy Endpoints (deprecated):
- GET /api/gaps/summary - System-wide gap summary with coverage %
- GET /api/gaps/by-analysis - Gaps grouped by analysis type
- GET /api/gaps/by-symbol/{symbol} - Per-symbol gap analysis
- GET /api/gaps/watchlist - Gaps affecting current watchlist
- POST /api/gaps/generate-task-list - Generate task list to fill specific gaps

Migration date: 2025-12-08
See: tasks/tasks-trading-reqs-to-features-migration.md
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
    """Coverage percentage by analysis type for a symbol."""

    technical: float
    fundamental: float
    sentiment: float
    risk: float
    execution: float
    macro: float
    ml: float
    compliance: float


class AggregateGap(TypedDict):
    """Gap affecting multiple symbols."""

    gap_id: str
    description: str
    affected_symbols: int
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
    """Per-symbol gap analysis response."""

    symbol: str
    readiness_score: float
    confidence_level: str
    coverage_by_analysis: TickerCoverageByAnalysis
    missing_capabilities: list[str]
    data_availability: dict[str, DataAvailability]


class WatchlistGapsDict(TypedDict):
    """Watchlist gap analysis response."""

    watchlist_symbols: list[str]
    symbol_coverage: dict[str, TickerGapsDict]
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
    total_gaps: int  # Pending gaps only (excludes resolved)
    resolved_count: int = 0  # Gaps marked as resolved
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
    """Per-symbol gap analysis."""

    symbol: str
    readiness_score: float  # 0-100% overall readiness
    confidence_level: str  # LOW/MEDIUM/HIGH
    coverage_by_analysis: dict[str, float]  # analysis_type → coverage %
    missing_capabilities: list[str]  # Top 10 missing capabilities
    data_availability: dict[str, DataAvailability]  # table → availability status


class WatchlistGapsResponse(BaseModel):
    """Gaps affecting current watchlist."""

    watchlist_symbols: list[str]
    symbol_coverage: dict[str, Any]  # symbol → full coverage analysis
    aggregate_gaps: list[dict[str, Any]]  # Gaps affecting multiple symbols


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
    - Total gaps by criticality (P0/P1/P2/P3) - EXCLUDES resolved gaps
    - Coverage % per analysis type (recalculated excluding resolved)
    - TOP 10 priority gaps (ranked by impact x 1/effort)
    - MVP roadmap (4-week plan to achieve trading edge)
    - Resolved count (gaps marked as done)

    Raises:
        HTTPException: 500 if analysis fails
    """
    logger.info("get_gap_summary_request")

    try:
        conn_mgr = ConnectionManager()
        detector = GapDetector(conn_mgr)

        result = detector.analyze_gaps()

        # Get resolved gap IDs to exclude from counts
        resolved_ids = get_resolved_gap_ids(conn_mgr)
        resolved_count = len(resolved_ids)

        # Weight mapping for coverage calculation
        weights = {"P0": 4.0, "P1": 2.0, "P2": 1.0, "P3": 0.5}

        # Filter resolved gaps from analysis_types and recalculate coverage
        filtered_analysis_types: dict[str, Any] = {}
        all_pending_gaps: list[dict[str, Any]] = []

        for analysis_type, type_data in result.get("analysis_types", {}).items():
            gaps_list = type_data.get("gaps", [])
            total_caps = type_data.get("total_capabilities", 0)

            # Filter to pending gaps only
            pending_gaps = [g for g in gaps_list if g.get("gap_id", "") not in resolved_ids]

            # Recalculate coverage % excluding resolved gaps
            # resolved gaps count as "available" now
            if total_caps > 0:
                # Calculate weighted points
                total_points = 0.0
                missing_points = 0.0
                for gap in gaps_list:
                    w = weights.get(gap.get("criticality", "P2"), 1.0)
                    total_points += w
                    if gap.get("gap_id", "") not in resolved_ids:
                        missing_points += w

                # Available = total - missing (resolved counts as available)
                available_points = total_points - missing_points
                new_coverage = (available_points / total_points) * 100 if total_points > 0 else 0.0
            else:
                new_coverage = type_data.get("coverage_pct", 0.0)

            # Update the analysis type data with filtered gaps
            filtered_type = {
                **type_data,
                "gaps": pending_gaps,
                "missing_capabilities": len(pending_gaps),
                "available_capabilities": total_caps - len(pending_gaps),
                "coverage_pct": round(new_coverage, 1),
            }
            filtered_analysis_types[analysis_type] = filtered_type
            all_pending_gaps.extend(pending_gaps)

        # Count by criticality
        p0 = sum(1 for g in all_pending_gaps if g.get("criticality") == "P0")
        p1 = sum(1 for g in all_pending_gaps if g.get("criticality") == "P1")
        p2 = sum(1 for g in all_pending_gaps if g.get("criticality") == "P2")
        p3 = sum(1 for g in all_pending_gaps if g.get("criticality") == "P3")

        # Calculate average coverage across all analysis types (now using filtered data)
        coverage_values = [at["coverage_pct"] for at in filtered_analysis_types.values()]
        avg_coverage = sum(coverage_values) / len(coverage_values) if coverage_values else 0.0

        # Filter top 10 priorities to only include pending gaps
        top_10 = result.get("top_10_priorities", [])
        filtered_top_10 = [g for g in top_10 if g.get("gap_id", "") not in resolved_ids][:10]

        response = {
            **result,
            "analysis_types": filtered_analysis_types,  # Use filtered version
            "total_gaps": len(all_pending_gaps),
            "p0_gaps": p0,
            "p1_gaps": p1,
            "p2_gaps": p2,
            "p3_gaps": p3,
            "resolved_count": resolved_count,
            "avg_coverage_pct": round(avg_coverage, 1),
            "top_10_priorities": filtered_top_10,
        }

        logger.info(
            "gap_summary_returned",
            total_gaps=len(all_pending_gaps),
            resolved=resolved_count,
            p0_gaps=p0,
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
    """Get gaps grouped by analysis type (excludes resolved gaps).

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

        # Get resolved gap IDs to exclude
        resolved_ids = get_resolved_gap_ids(conn_mgr)
        weights = {"P0": 4.0, "P1": 2.0, "P2": 1.0, "P3": 0.5}

        # Filter resolved gaps from each analysis type
        filtered_analysis_types: dict[str, Any] = {}
        for analysis_type, type_data in result.get("analysis_types", {}).items():
            gaps_list = type_data.get("gaps", [])
            total_caps = type_data.get("total_capabilities", 0)

            # Filter to pending gaps only
            pending_gaps = [g for g in gaps_list if g.get("gap_id", "") not in resolved_ids]

            # Recalculate coverage
            if total_caps > 0 and gaps_list:
                total_points = sum(weights.get(g.get("criticality", "P2"), 1.0) for g in gaps_list)
                missing_points = sum(
                    weights.get(g.get("criticality", "P2"), 1.0)
                    for g in gaps_list
                    if g.get("gap_id", "") not in resolved_ids
                )
                new_coverage = ((total_points - missing_points) / total_points) * 100
            else:
                new_coverage = type_data.get("coverage_pct", 0.0)

            filtered_type = {
                **type_data,
                "gaps": pending_gaps,
                "missing_capabilities": len(pending_gaps),
                "available_capabilities": total_caps - len(pending_gaps),
                "coverage_pct": round(new_coverage, 1),
            }
            filtered_analysis_types[analysis_type] = filtered_type

        response = {
            "analysis_types": filtered_analysis_types,
        }

        logger.info(
            "gaps_by_analysis_returned",
            analysis_types=len(filtered_analysis_types),
        )

        return cast(GapsByAnalysisDict, response)

    except Exception as e:
        logger.error("gaps_by_analysis_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Gap analysis failed: {e!s}",
        ) from e


@router.get("/by-symbol/{symbol}", response_model=TickerGapsResponse)
async def get_symbol_gaps(symbol: str) -> TickerGapsDict:
    """Get per-symbol gap analysis.

    Analyzes data availability for a specific symbol across all analysis types.
    Useful for understanding: "Can I analyze NVDA fundamentally? What's missing?"

    Args:
        symbol: Stock symbol (e.g., "NVDA", "AAPL")

    Returns:
        Symbol-specific coverage % and missing capabilities per analysis type

    Raises:
        HTTPException: 500 if analysis fails
    """
    logger.info("get_symbol_gaps_request", symbol=symbol)

    try:
        conn_mgr = ConnectionManager()
        detector = GapDetector(conn_mgr)

        result = detector.analyze_symbol_gaps(symbol.upper())

        logger.info(
            "symbol_gaps_returned",
            symbol=symbol,
        )

        return cast(TickerGapsDict, result)

    except Exception as e:
        logger.error("symbol_gaps_failed", symbol=symbol, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Symbol gap analysis failed: {e!s}",
        ) from e


@router.get("/watchlist", response_model=WatchlistGapsResponse)
async def get_watchlist_gaps() -> WatchlistGapsDict:
    """Get gaps affecting current watchlist.

    Analyzes data coverage for all symbols in the active watchlist.
    Identifies gaps that affect multiple symbols:
    - "8/12 watchlist symbols missing earnings data"
    - "All watchlist symbols missing options flow data"

    Returns:
        Per-symbol coverage matrix and aggregate gaps

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


# ========================================================================
# Gap Resolution Tracking (like a checklist - mark gaps as resolved)
# ========================================================================


class ResolveGapRequest(BaseModel):
    """Request to mark a gap as resolved."""

    resolution_notes: str | None = Field(
        default=None, description="Notes about how the gap was filled"
    )


class ResolveGapResponse(BaseModel):
    """Response after resolving a gap."""

    gap_id: str
    status: str
    message: str


@router.post("/{gap_id}/resolve", response_model=ResolveGapResponse)
async def resolve_gap(gap_id: str, request: ResolveGapRequest | None = None) -> dict[str, str]:
    """Mark a gap as resolved by setting passes=true on the corresponding feature.

    Use this after implementing a capability to mark the gap as filled.
    Resolved gaps won't appear in the gap summary counts.

    This updates the unified feature system (feature_capabilities table).

    Args:
        gap_id: Gap ID (e.g., GAP-020)
        request: Optional resolution notes

    Returns:
        Confirmation of resolution

    Raises:
        HTTPException: 400 if invalid gap_id format
        HTTPException: 404 if feature not found
        HTTPException: 500 if database operation fails
    """
    if not gap_id.startswith("GAP-"):
        raise HTTPException(status_code=400, detail=f"Invalid gap_id format: {gap_id}")

    notes = request.resolution_notes if request else None
    feature_id = f"FEAT-{gap_id}"

    logger.info("resolve_gap_request", gap_id=gap_id, feature_id=feature_id, notes=notes)

    try:
        conn_mgr = ConnectionManager()
        with conn_mgr.connection() as conn:
            # Update the corresponding feature's passes status
            result = conn.execute(
                """
                UPDATE feature_capabilities
                SET passes = true,
                    status = 'complete',
                    verified_by = 'gap_resolution',
                    last_verified_at = NOW(),
                    updated_at = NOW()
                WHERE feature_id = %s
                RETURNING feature_id
                """,
                (feature_id,),
            ).fetchone()

            if not result:
                # Feature doesn't exist - try legacy trading_gaps table as fallback
                conn.execute(
                    """
                    INSERT INTO trading_gaps (gap_id, capability, analysis_type, criticality,
                        severity, current_state, desired_state, impact, recommendation, resolved_at, resolution_notes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW() AT TIME ZONE 'UTC', %s)
                    ON CONFLICT (gap_id) DO UPDATE SET
                        resolved_at = NOW() AT TIME ZONE 'UTC',
                        resolution_notes = EXCLUDED.resolution_notes,
                        updated_at = NOW() AT TIME ZONE 'UTC'
                    """,
                    [gap_id, 'unknown', 'unknown', 'P1', 'limiting', '', '', '', 'Resolved', notes],
                )
                conn.commit()
                logger.info("gap_resolved_legacy", gap_id=gap_id)
                return {"gap_id": gap_id, "status": "resolved", "message": f"Gap {gap_id} marked as resolved (legacy)"}

            conn.commit()

        logger.info("gap_resolved", gap_id=gap_id, feature_id=feature_id)
        return {"gap_id": gap_id, "status": "resolved", "message": f"Gap {gap_id} resolved (feature {feature_id} passes=true)"}

    except Exception as e:
        logger.error("resolve_gap_failed", gap_id=gap_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to resolve gap: {e!s}") from e


@router.get("/resolutions")
async def get_gap_resolutions() -> dict[str, Any]:
    """Get list of resolved gaps from the unified feature system.

    Returns features with source='trading_requirement' and passes=true,
    converted back to gap format for compatibility.

    Returns:
        List of gap_ids that have been resolved and their resolution dates
    """
    try:
        conn_mgr = ConnectionManager()
        with conn_mgr.connection() as conn:
            # Query resolved gaps from features
            result = conn.execute(
                """
                SELECT
                    feature_id,
                    last_verified_at,
                    name,
                    category
                FROM feature_capabilities
                WHERE source = 'trading_requirement'
                  AND passes = true
                ORDER BY last_verified_at DESC NULLS LAST
                """
            ).fetchall()

        resolutions = [
            {
                "gap_id": str(row[0]).replace("FEAT-", "") if row[0] else None,
                "feature_id": row[0],
                "resolved_at": row[1].isoformat() if row[1] and hasattr(row[1], "isoformat") else None,
                "name": row[2],
                "category": row[3],
            }
            for row in result
        ]

        return {
            "resolved_count": len(resolutions),
            "resolutions": resolutions,
            "source": "feature_capabilities",
        }

    except Exception as e:
        logger.error("get_resolutions_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get resolutions: {e!s}") from e


def get_resolved_gap_ids(conn_mgr: ConnectionManager) -> set[str]:
    """Helper to get set of resolved gap IDs from features with passes=true.

    Uses the unified feature system: features with source='trading_requirement'
    and passes=true are considered resolved gaps.
    """
    try:
        with conn_mgr.connection() as conn:
            # Query features that represent resolved gaps
            # FEAT-GAP-003 → GAP-003
            result = conn.execute(
                """
                SELECT feature_id FROM feature_capabilities
                WHERE source = 'trading_requirement'
                  AND passes = true
                """
            ).fetchall()
            # Convert FEAT-GAP-003 → GAP-003
            return {
                str(row[0]).replace("FEAT-", "")
                for row in result
                if row[0] and str(row[0]).startswith("FEAT-GAP-")
            }
    except Exception:
        # Fallback to legacy trading_gaps table
        try:
            with conn_mgr.connection() as conn:
                result = conn.execute(
                    "SELECT gap_id FROM trading_gaps WHERE resolved_at IS NOT NULL"
                ).fetchall()
                return {str(row[0]) for row in result if row[0]}
        except Exception:
            return set()
