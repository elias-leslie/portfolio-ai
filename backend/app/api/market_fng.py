"""Fear & Greed Index API endpoints."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from ..market.fear_greed_service import FearGreedService
from ..models.fear_greed import (
    FearGreedComponent,
    FearGreedReading,
    FearGreedResponse,
)
from ..storage import PortfolioStorage, get_storage

router = APIRouter(prefix="/api/market", tags=["market"])


def get_fear_greed_service(
    storage: PortfolioStorage = Depends(get_storage),
) -> FearGreedService:
    """Get Fear & Greed service instance."""
    return FearGreedService(storage)


@router.get("/fear-greed", response_model=FearGreedResponse)
def get_fear_greed(
    date_param: date | None = Query(
        None, alias="date", description="Specific date to retrieve (default: latest)"
    ),
    include_components: bool = Query(False, description="Include component percentile breakdown"),
    service: FearGreedService = Depends(get_fear_greed_service),
) -> FearGreedResponse:
    """Get Fear & Greed Index reading.

    Returns the latest reading by default, or a specific date if provided.
    Optionally includes component percentile breakdown.
    """
    # Fetch reading
    if date_param:
        reading_data = service.get_by_date(date_param)
        if not reading_data:
            raise HTTPException(
                status_code=404,
                detail=f"No Fear & Greed data found for date: {date_param}",
            )
    else:
        reading_data = service.get_latest()
        if not reading_data:
            raise HTTPException(status_code=404, detail="No Fear & Greed data available")

    reading = FearGreedReading(**reading_data)

    # Fetch components if requested
    components = None
    if include_components:
        component_data = service.get_components(reading.date)
        if component_data:
            components = FearGreedComponent(**component_data)

    return FearGreedResponse(reading=reading, components=components)


@router.get("/fear-greed/history", response_model=list[FearGreedReading])
def get_fear_greed_history(
    start: date = Query(..., description="Start date (inclusive)"),
    end: date = Query(..., description="End date (inclusive)"),
    service: FearGreedService = Depends(get_fear_greed_service),
) -> list[FearGreedReading]:
    """Get Fear & Greed Index history for a date range.

    Returns all readings between start and end dates (inclusive).
    """
    if start > end:
        raise HTTPException(
            status_code=400, detail="Start date must be before or equal to end date"
        )

    history_data = service.get_history(start, end)
    return [FearGreedReading(**item) for item in history_data]


@router.get("/fear-greed/components", response_model=FearGreedComponent)
def get_fear_greed_components(
    date_param: date | None = Query(
        None, alias="date", description="Specific date to retrieve (default: latest)"
    ),
    service: FearGreedService = Depends(get_fear_greed_service),
) -> FearGreedComponent:
    """Get Fear & Greed component percentiles.

    Returns component breakdown for the latest reading by default,
    or a specific date if provided.
    """
    # Determine target date
    if date_param:
        target_date = date_param
    else:
        latest = service.get_latest()
        if not latest:
            raise HTTPException(status_code=404, detail="No Fear & Greed data available")
        target_date = latest["date"]

    # Fetch components
    component_data = service.get_components(target_date)
    if not component_data:
        raise HTTPException(
            status_code=404,
            detail=f"No component data found for date: {target_date}",
        )

    return FearGreedComponent(**component_data)
