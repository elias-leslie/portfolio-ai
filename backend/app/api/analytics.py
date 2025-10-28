"""Analytics API router for trading intelligence endpoints."""

from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel, Field

from app.analytics import (
    calculate_rvol,
    get_peer_comparison,
    get_peer_group_detail,
    get_sector_rotation,
)
from app.storage import get_storage

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

# Initialize storage
storage = get_storage()


# Response models
class RVOLResponse(BaseModel):
    """Response model for RVOL (Relative Volume) data."""

    ticker: str = Field(..., description="Stock ticker symbol")
    date: str = Field(..., description="Date for RVOL calculation (YYYY-MM-DD)")
    rvol: float = Field(..., description="Relative volume ratio (1.0 = normal volume)")
    interpretation: str = Field(..., description="Human-readable interpretation of RVOL value")


class SectorMomentumItem(BaseModel):
    """Individual sector momentum data."""

    sector: str = Field(..., description="Sector name")
    momentum_5d: float | None = Field(..., description="5-day momentum (%)")
    momentum_20d: float | None = Field(..., description="20-day momentum (%)")
    num_stocks: int = Field(..., description="Number of stocks in sector")
    avg_volume: float | None = Field(..., description="Average volume across sector stocks")


class SectorRotationResponse(BaseModel):
    """Response model for sector rotation analysis."""

    date: str = Field(..., description="Date for sector rotation (YYYY-MM-DD)")
    sectors: list[SectorMomentumItem] = Field(..., description="Sectors ranked by momentum")
    count: int = Field(..., description="Number of sectors returned")


class PeerComparisonResponse(BaseModel):
    """Response model for peer comparison analysis."""

    ticker: str = Field(..., description="Stock ticker symbol")
    sector: str = Field(..., description="Sector name")
    date: str = Field(..., description="Date for peer comparison (YYYY-MM-DD)")
    return_5d: float | None = Field(..., description="5-day return (%)")
    return_20d: float | None = Field(..., description="20-day return (%)")
    sector_avg_5d: float | None = Field(..., description="Sector average 5-day return (%)")
    sector_avg_20d: float | None = Field(..., description="Sector average 20-day return (%)")
    relative_perf_5d: float | None = Field(
        ..., description="Relative performance vs sector over 5 days (%)"
    )
    relative_perf_20d: float | None = Field(
        ..., description="Relative performance vs sector over 20 days (%)"
    )
    peer_rank: int | None = Field(..., description="Rank within peer group (1 = best)")
    peer_count: int = Field(..., description="Total number of peers")
    percentile: float | None = Field(..., description="Percentile rank (0-100, higher is better)")


class PeerDetailItem(BaseModel):
    """Individual peer performance data."""

    ticker: str = Field(..., description="Stock ticker symbol")
    sector: str = Field(..., description="Sector name")
    return_5d: float | None = Field(..., description="5-day return (%)")
    return_20d: float | None = Field(..., description="20-day return (%)")
    rank: int = Field(..., description="Rank within peer group")
    is_target: bool = Field(..., description="Whether this is the target ticker")


class PeerGroupDetailResponse(BaseModel):
    """Response model for peer group detail."""

    ticker: str = Field(..., description="Target ticker symbol")
    sector: str = Field(..., description="Sector name")
    date: str = Field(..., description="Date for peer comparison (YYYY-MM-DD)")
    peers: list[PeerDetailItem] = Field(..., description="All peers ranked by performance")
    count: int = Field(..., description="Number of peers")


# Endpoints


@router.get("/rvol/{ticker}", response_model=RVOLResponse)
async def get_rvol(
    ticker: Annotated[str, Path(description="Stock ticker symbol (e.g., AAPL)")],
    date: Annotated[
        str | None,
        Query(description="Date for RVOL calculation (YYYY-MM-DD). Defaults to today."),
    ] = None,
    lookback_days: Annotated[
        int, Query(description="Lookback period for RVOL calculation", ge=5, le=60)
    ] = 20,
) -> RVOLResponse:
    """Get Relative Volume (RVOL) for a ticker.

    RVOL measures current trading volume relative to the average volume
    over a lookback period. Values > 1.0 indicate above-average volume.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL")
        date: Date for RVOL calculation (YYYY-MM-DD). Defaults to today.
        lookback_days: Number of trading days to average (default: 20)

    Returns:
        RVOLResponse with RVOL value and interpretation

    Raises:
        HTTPException: If ticker not found or insufficient data
    """
    # Default to today's date if not provided
    if date is None:
        target_date = dt.date.today()
    else:
        try:
            target_date = dt.datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid date format: {date}. Use YYYY-MM-DD format.",
            ) from None

    # Calculate RVOL
    rvol = calculate_rvol(storage, ticker.upper(), target_date, lookback_days)

    if rvol is None:
        raise HTTPException(
            status_code=404,
            detail=f"Could not calculate RVOL for {ticker} on {target_date}. "
            "Insufficient data available.",
        )

    # Interpret RVOL value
    if rvol >= 2.0:
        interpretation = "Very high volume (2x+ normal)"
    elif rvol >= 1.5:
        interpretation = "High volume (1.5-2x normal)"
    elif rvol >= 1.0:
        interpretation = "Above average volume"
    elif rvol >= 0.5:
        interpretation = "Below average volume"
    else:
        interpretation = "Very low volume (<0.5x normal)"

    return RVOLResponse(
        ticker=ticker.upper(),
        date=target_date.isoformat(),
        rvol=round(rvol, 2),
        interpretation=interpretation,
    )


@router.get("/sectors/rotation", response_model=SectorRotationResponse)
async def get_sectors_rotation(
    date: Annotated[
        str | None,
        Query(description="Date for sector rotation (YYYY-MM-DD). Defaults to today."),
    ] = None,
    lookback_days: Annotated[
        int, Query(description="Lookback period for momentum calculation", ge=10, le=60)
    ] = 20,
) -> SectorRotationResponse:
    """Get sector rotation analysis showing relative sector momentum.

    Analyzes performance across all sectors to identify sector rotation
    patterns and relative strength.

    Args:
        date: Date for sector rotation (YYYY-MM-DD). Defaults to today.
        lookback_days: Lookback period for momentum calculation (default: 20)

    Returns:
        SectorRotationResponse with sectors ranked by momentum

    Raises:
        HTTPException: If insufficient data available
    """
    # Default to today's date if not provided
    if date is None:
        target_date = dt.date.today()
    else:
        try:
            target_date = dt.datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid date format: {date}. Use YYYY-MM-DD format.",
            ) from None

    # Get sector rotation data
    rotation = get_sector_rotation(storage, target_date, lookback_days)

    if rotation is None or len(rotation) == 0:
        raise HTTPException(
            status_code=404,
            detail=f"Could not calculate sector rotation for {target_date}. "
            "Insufficient data available.",
        )

    # Convert to response model
    sectors = []
    for row in rotation.iter_rows(named=True):
        sectors.append(
            SectorMomentumItem(
                sector=row["sector"],
                momentum_5d=round(row["momentum_5d"], 2) if row["momentum_5d"] else None,
                momentum_20d=(round(row["momentum_20d"], 2) if row["momentum_20d"] else None),
                num_stocks=row["num_stocks"],
                avg_volume=row["avg_volume"],
            )
        )

    return SectorRotationResponse(
        date=target_date.isoformat(),
        sectors=sectors,
        count=len(sectors),
    )


@router.get("/peers/{ticker}", response_model=PeerComparisonResponse)
async def get_peer_comp(
    ticker: Annotated[str, Path(description="Stock ticker symbol (e.g., AAPL)")],
    date: Annotated[
        str | None,
        Query(description="Date for peer comparison (YYYY-MM-DD). Defaults to today."),
    ] = None,
    group_by: Annotated[
        str, Query(description='Grouping method: "sector" or "industry"')
    ] = "sector",
    lookback_days: Annotated[
        int, Query(description="Lookback period for momentum calculation", ge=10, le=60)
    ] = 20,
) -> PeerComparisonResponse:
    """Get peer comparison analysis for a ticker.

    Compares a ticker's performance against its sector or industry peers
    to identify relative strength and positioning.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL")
        date: Date for peer comparison (YYYY-MM-DD). Defaults to today.
        group_by: Grouping method - "sector" or "industry" (default: "sector")
        lookback_days: Lookback period for momentum calculation (default: 20)

    Returns:
        PeerComparisonResponse with peer rank and relative performance

    Raises:
        HTTPException: If ticker not found or insufficient data
    """
    # Default to today's date if not provided
    if date is None:
        target_date = dt.date.today()
    else:
        try:
            target_date = dt.datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid date format: {date}. Use YYYY-MM-DD format.",
            ) from None

    # Validate group_by parameter
    if group_by not in ["sector", "industry"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid group_by parameter: {group_by}. Use 'sector' or 'industry'.",
        )

    # Get peer comparison data
    comparison = get_peer_comparison(storage, ticker.upper(), target_date, lookback_days, group_by)

    if comparison is None or len(comparison) == 0:
        raise HTTPException(
            status_code=404,
            detail=f"Could not calculate peer comparison for {ticker} on {target_date}. "
            "Ticker not found or insufficient data available.",
        )

    # Extract data from DataFrame - access scalars directly
    return PeerComparisonResponse(
        ticker=ticker.upper(),
        sector=comparison[group_by][0],
        date=target_date.isoformat(),
        return_5d=(
            round(comparison["return_5d"][0], 2) if comparison["return_5d"][0] is not None else None
        ),
        return_20d=(
            round(comparison["return_20d"][0], 2)
            if comparison["return_20d"][0] is not None
            else None
        ),
        sector_avg_5d=(
            round(comparison["sector_avg_5d"][0], 2)
            if comparison["sector_avg_5d"][0] is not None
            else None
        ),
        sector_avg_20d=(
            round(comparison["sector_avg_20d"][0], 2)
            if comparison["sector_avg_20d"][0] is not None
            else None
        ),
        relative_perf_5d=(
            round(comparison["relative_perf_5d"][0], 2)
            if comparison["relative_perf_5d"][0] is not None
            else None
        ),
        relative_perf_20d=(
            round(comparison["relative_perf_20d"][0], 2)
            if comparison["relative_perf_20d"][0] is not None
            else None
        ),
        peer_rank=comparison["peer_rank"][0],
        peer_count=comparison["peer_count"][0],
        percentile=comparison["percentile"][0],
    )


@router.get("/peers/{ticker}/detail", response_model=PeerGroupDetailResponse)
async def get_peer_group_det(
    ticker: Annotated[str, Path(description="Stock ticker symbol (e.g., AAPL)")],
    date: Annotated[
        str | None,
        Query(description="Date for peer comparison (YYYY-MM-DD). Defaults to today."),
    ] = None,
    group_by: Annotated[
        str, Query(description='Grouping method: "sector" or "industry"')
    ] = "sector",
    lookback_days: Annotated[
        int, Query(description="Lookback period for momentum calculation", ge=10, le=60)
    ] = 20,
) -> PeerGroupDetailResponse:
    """Get detailed peer group rankings for a ticker.

    Returns ranked list of all stocks in the same sector or industry as the
    target ticker, showing their relative performance.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL")
        date: Date for peer comparison (YYYY-MM-DD). Defaults to today.
        group_by: Grouping method - "sector" or "industry" (default: "sector")
        lookback_days: Lookback period for momentum calculation (default: 20)

    Returns:
        PeerGroupDetailResponse with all peers ranked by performance

    Raises:
        HTTPException: If ticker not found or insufficient data
    """
    # Default to today's date if not provided
    if date is None:
        target_date = dt.date.today()
    else:
        try:
            target_date = dt.datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid date format: {date}. Use YYYY-MM-DD format.",
            ) from None

    # Validate group_by parameter
    if group_by not in ["sector", "industry"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid group_by parameter: {group_by}. Use 'sector' or 'industry'.",
        )

    # Get peer group detail
    peers = get_peer_group_detail(storage, ticker.upper(), target_date, lookback_days, group_by)

    if peers is None or len(peers) == 0:
        raise HTTPException(
            status_code=404,
            detail=f"Could not get peer group detail for {ticker} on {target_date}. "
            "Ticker not found or insufficient data available.",
        )

    # Get sector/industry name from first row
    sector_name = peers[group_by][0]

    # Convert to response model
    peer_items = []
    for row in peers.iter_rows(named=True):
        peer_items.append(
            PeerDetailItem(
                ticker=row["ticker"],
                sector=row[group_by],
                return_5d=round(row["return_5d"], 2) if row["return_5d"] else None,
                return_20d=round(row["return_20d"], 2) if row["return_20d"] else None,
                rank=row["rank"],
                is_target=row["is_target"],
            )
        )

    return PeerGroupDetailResponse(
        ticker=ticker.upper(),
        sector=sector_name,
        date=target_date.isoformat(),
        peers=peer_items,
        count=len(peer_items),
    )
