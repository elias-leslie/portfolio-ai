"""Market events endpoints (FOMC, CPI, NFP, economic events)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Final, cast, get_args

from fastapi import APIRouter, HTTPException, Query, Request

from app.constants import CACHE_TTL_MEDIUM
from app.logging_config import get_logger
from app.middleware.cache import cache_response
from app.models.market_events import MarketEventCreate, MarketEventType, MarketEventUpdate
from app.services.market_events_service import (
    create_market_event as svc_create_event,
)
from app.services.market_events_service import (
    get_event_type_info,
    get_events_for_chart,
    get_upcoming_events,
)
from app.services.market_events_service import (
    get_market_events as svc_get_events,
)
from app.services.market_events_service import (
    update_market_event as svc_update_event,
)

router = APIRouter()
logger = get_logger(__name__)

# Valid market event types (derived from MarketEventType Literal)
VALID_EVENT_TYPES: Final[frozenset[str]] = frozenset(get_args(MarketEventType))


def _validate_event_type(event_type: str) -> MarketEventType:
    """Validate and cast event type string to MarketEventType.

    Args:
        event_type: Event type string to validate

    Returns:
        Validated MarketEventType

    Raises:
        HTTPException: If event_type is not in VALID_EVENT_TYPES
    """

    if event_type not in VALID_EVENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid event_type: {event_type}. Valid types: {', '.join(sorted(VALID_EVENT_TYPES))}",
        )
    return cast(MarketEventType, event_type)


# API endpoints
@router.get("/events")
async def get_market_events(
    start_date: date | None = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: date | None = Query(None, description="End date (YYYY-MM-DD)"),
    event_types: str | None = Query(None, description="Comma-separated event types"),
    limit: int = Query(100, ge=1, le=500),
) -> dict[str, Any]:
    """Get market events (FOMC, CPI, NFP, etc.) with optional filtering.

    Args:
        start_date: Filter events from this date (inclusive)
        end_date: Filter events until this date (inclusive)
        event_types: Comma-separated list of event types to filter
        limit: Maximum number of events to return

    Returns:
        MarketEventsResponse with list of events
    """
    # Parse and validate event types
    types_list: list[MarketEventType] | None = None
    if event_types:
        parsed_types = [t.strip() for t in event_types.split(",")]
        # Validate each type - raises HTTPException if any invalid
        types_list = [_validate_event_type(t) for t in parsed_types]

    response = svc_get_events(
        start_date=start_date,
        end_date=end_date,
        event_types=types_list,
        limit=limit,
    )

    return response.model_dump()


@router.get("/events/chart")
@cache_response(ttl=CACHE_TTL_MEDIUM)
async def get_market_events_for_chart(
    request: Request,
    days: int = Query(365, ge=7, le=730, description="Number of days of history"),
) -> dict[str, Any]:
    """Get market events formatted for chart overlay.

    Returns events with UI metadata (color, label) for display on sentiment charts.

    Args:
        days: Number of days of history to return

    Returns:
        List of events with UI metadata
    """
    end = date.today()
    start = end - timedelta(days=days)

    events = get_events_for_chart(start_date=start, end_date=end)

    return {
        "events": events,
        "total": len(events),
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
    }


@router.get("/events/types")
async def get_market_event_types() -> dict[str, Any]:
    """Get metadata for all market event types.

    Returns:
        List of event types with labels, colors, and frequency info
    """
    types = get_event_type_info()
    return {
        "types": [t.model_dump() for t in types],
    }


@router.get("/events/upcoming")
async def get_upcoming_market_events(
    days: int = Query(30, ge=1, le=90, description="Days to look ahead"),
) -> dict[str, Any]:
    """Get upcoming market events.

    Args:
        days: Number of days to look ahead

    Returns:
        List of upcoming events
    """
    events = get_upcoming_events(days=days)
    return {
        "events": [e.model_dump() for e in events],
        "total": len(events),
        "days_ahead": days,
    }


@router.post("/events")
async def create_market_event(
    event_type: str = Query(..., description="Event type"),
    event_date: date = Query(..., description="Event date (YYYY-MM-DD)"),
    title: str = Query(..., description="Event title"),
    event_time: str | None = Query(None, description="Event time (HH:MM:SS)"),
    description: str | None = Query(None, description="Event description"),
    expected_value: float | None = Query(None, description="Expected/consensus value"),
    actual_value: float | None = Query(None, description="Actual released value"),
    prior_value: float | None = Query(None, description="Prior period value"),
    impact_score: int | None = Query(None, ge=-5, le=5, description="Impact score"),
    source: str = Query("manual", description="Data source"),
) -> dict[str, Any]:
    """Create a new market event.

    Returns:
        Created event with ID
    """
    # Validate event type
    validated_type = _validate_event_type(event_type)

    event = MarketEventCreate(
        event_type=validated_type,
        event_date=event_date.isoformat(),
        event_time=event_time,
        title=title,
        description=description,
        expected_value=expected_value,
        actual_value=actual_value,
        prior_value=prior_value,
        impact_score=impact_score,
        source=source,
    )

    created = svc_create_event(event)
    return created.model_dump()


@router.patch("/events/{event_id}")
async def update_market_event(
    event_id: int,
    actual_value: float | None = Query(None, description="Actual released value"),
    surprise_pct: float | None = Query(None, description="Surprise percentage"),
    impact_score: int | None = Query(None, ge=-5, le=5, description="Impact score"),
    spy_change_1h: float | None = Query(None, description="SPY % change 1 hour after"),
    spy_change_1d: float | None = Query(None, description="SPY % change end of day"),
) -> dict[str, Any]:
    """Update a market event with actual values and market reaction.

    Returns:
        Updated event or 404 if not found
    """

    update = MarketEventUpdate(
        actual_value=actual_value,
        surprise_pct=surprise_pct,
        impact_score=impact_score,
        spy_change_1h=spy_change_1h,
        spy_change_1d=spy_change_1d,
    )

    updated = svc_update_event(event_id, update)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

    return updated.model_dump()
