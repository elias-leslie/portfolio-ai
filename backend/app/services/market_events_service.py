"""Market events service for macro event tracking.

Provides CRUD operations for market-wide events (FOMC, CPI, NFP, etc.).
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from ..logging_config import get_logger
from ..models.market_events import (
    EVENT_TYPE_INFO,
    EventTypeInfo,
    MarketEvent,
    MarketEventCreate,
    MarketEventsResponse,
    MarketEventType,
    MarketEventUpdate,
)
from ..storage import get_storage

logger = get_logger(__name__)


def get_market_events(
    start_date: dt.date | None = None,
    end_date: dt.date | None = None,
    event_types: list[MarketEventType] | None = None,
    limit: int = 100,
) -> MarketEventsResponse:
    """Get market events with optional filtering.

    Args:
        start_date: Filter events from this date (inclusive)
        end_date: Filter events until this date (inclusive)
        event_types: Filter by event types
        limit: Maximum number of events to return

    Returns:
        MarketEventsResponse with list of events
    """
    storage = get_storage()

    # Build query
    conditions = []
    params: dict[str, Any] = {"limit": limit}

    if start_date:
        conditions.append("event_date >= %(start_date)s")
        params["start_date"] = start_date
    if end_date:
        conditions.append("event_date <= %(end_date)s")
        params["end_date"] = end_date
    if event_types:
        conditions.append("event_type = ANY(%(event_types)s)")
        params["event_types"] = event_types

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    query = f"""
        SELECT
            id, event_type::text, event_date, event_time::text,
            title, description,
            expected_value, actual_value, prior_value, surprise_pct,
            impact_score, spy_change_1h, spy_change_1d,
            source, created_at
        FROM market_events
        WHERE {where_clause}
        ORDER BY event_date DESC, event_time DESC NULLS LAST
        LIMIT %(limit)s
    """

    df = storage.query(query, params)  # type: ignore[arg-type]

    events = []
    for row in df.iter_rows(named=True):
        events.append(
            MarketEvent(
                id=row["id"],
                event_type=row["event_type"],
                event_date=str(row["event_date"]),
                event_time=str(row["event_time"]) if row["event_time"] else None,
                title=row["title"],
                description=row["description"],
                expected_value=float(row["expected_value"]) if row["expected_value"] else None,
                actual_value=float(row["actual_value"]) if row["actual_value"] else None,
                prior_value=float(row["prior_value"]) if row["prior_value"] else None,
                surprise_pct=float(row["surprise_pct"]) if row["surprise_pct"] else None,
                impact_score=row["impact_score"],
                spy_change_1h=float(row["spy_change_1h"]) if row["spy_change_1h"] else None,
                spy_change_1d=float(row["spy_change_1d"]) if row["spy_change_1d"] else None,
                source=row["source"],
                created_at=str(row["created_at"]) if row["created_at"] else None,
            )
        )

    return MarketEventsResponse(
        events=events,
        total=len(events),
        start_date=str(start_date) if start_date else None,
        end_date=str(end_date) if end_date else None,
    )


def get_events_for_chart(
    start_date: dt.date,
    end_date: dt.date,
) -> list[dict[str, Any]]:
    """Get events formatted for chart overlay.

    Args:
        start_date: Chart start date
        end_date: Chart end date

    Returns:
        List of events with UI metadata for chart display
    """
    storage = get_storage()

    query = """
        SELECT
            id, event_type::text, event_date, event_time::text,
            title, impact_score, actual_value, expected_value, surprise_pct
        FROM market_events
        WHERE event_date >= %(start_date)s AND event_date <= %(end_date)s
        ORDER BY event_date ASC, event_time ASC NULLS LAST
    """

    df = storage.query(query, {"start_date": start_date, "end_date": end_date})  # type: ignore[arg-type]

    events = []
    for row in df.iter_rows(named=True):
        event_type = row["event_type"]
        info = EVENT_TYPE_INFO.get(event_type)

        events.append(
            {
                "id": row["id"],
                "date": str(row["event_date"]),
                "time": str(row["event_time"]) if row["event_time"] else None,
                "type": event_type,
                "title": row["title"],
                "label": info.short_label if info else event_type,
                "color": info.color if info else "#6B7280",
                "impact_score": row["impact_score"],
                "actual_value": float(row["actual_value"]) if row["actual_value"] else None,
                "expected_value": float(row["expected_value"]) if row["expected_value"] else None,
                "surprise_pct": float(row["surprise_pct"]) if row["surprise_pct"] else None,
            }
        )

    return events


def create_market_event(event: MarketEventCreate) -> MarketEvent:
    """Create a new market event.

    Args:
        event: Event data to create

    Returns:
        Created MarketEvent with ID
    """
    storage = get_storage()

    # Calculate surprise_pct if both values provided
    surprise_pct = None
    if (
        event.actual_value is not None
        and event.expected_value is not None
        and event.expected_value != 0
    ):
        surprise_pct = (
            (event.actual_value - event.expected_value) / abs(event.expected_value)
        ) * 100

    query = """
        INSERT INTO market_events (
            event_type, event_date, event_time, title, description,
            expected_value, actual_value, prior_value, surprise_pct,
            impact_score, source
        ) VALUES (
            %(event_type)s::market_event_type, %(event_date)s, %(event_time)s,
            %(title)s, %(description)s,
            %(expected_value)s, %(actual_value)s, %(prior_value)s, %(surprise_pct)s,
            %(impact_score)s, %(source)s
        )
        RETURNING id, created_at
    """

    params = {
        "event_type": event.event_type,
        "event_date": event.event_date,
        "event_time": event.event_time,
        "title": event.title,
        "description": event.description,
        "expected_value": event.expected_value,
        "actual_value": event.actual_value,
        "prior_value": event.prior_value,
        "surprise_pct": surprise_pct,
        "impact_score": event.impact_score,
        "source": event.source,
    }

    result = storage.query(query, params)  # type: ignore[arg-type]
    row = result.row(0, named=True)

    logger.info(
        "market_event_created",
        event_id=row["id"],
        event_type=event.event_type,
        event_date=event.event_date,
    )

    return MarketEvent(
        id=row["id"],
        event_type=event.event_type,
        event_date=event.event_date,
        event_time=event.event_time,
        title=event.title,
        description=event.description,
        expected_value=event.expected_value,
        actual_value=event.actual_value,
        prior_value=event.prior_value,
        surprise_pct=surprise_pct,
        impact_score=event.impact_score,
        spy_change_1h=None,
        spy_change_1d=None,
        source=event.source,
        created_at=str(row["created_at"]),
    )


def update_market_event(event_id: int, update: MarketEventUpdate) -> MarketEvent | None:
    """Update an existing market event with actual values.

    Args:
        event_id: Event ID to update
        update: Update data

    Returns:
        Updated MarketEvent or None if not found
    """
    storage = get_storage()

    # Build SET clause dynamically from non-None fields
    set_parts = []
    params: dict[str, Any] = {"event_id": event_id}

    if update.actual_value is not None:
        set_parts.append("actual_value = %(actual_value)s")
        params["actual_value"] = update.actual_value
    if update.surprise_pct is not None:
        set_parts.append("surprise_pct = %(surprise_pct)s")
        params["surprise_pct"] = update.surprise_pct
    if update.impact_score is not None:
        set_parts.append("impact_score = %(impact_score)s")
        params["impact_score"] = update.impact_score
    if update.spy_change_1h is not None:
        set_parts.append("spy_change_1h = %(spy_change_1h)s")
        params["spy_change_1h"] = update.spy_change_1h
    if update.spy_change_1d is not None:
        set_parts.append("spy_change_1d = %(spy_change_1d)s")
        params["spy_change_1d"] = update.spy_change_1d

    if not set_parts:
        # Nothing to update
        return None

    query = f"""
        UPDATE market_events
        SET {", ".join(set_parts)}, updated_at = CURRENT_TIMESTAMP
        WHERE id = %(event_id)s
        RETURNING *
    """

    result = storage.query(query, params)  # type: ignore[arg-type]
    if result.is_empty():
        return None

    row = result.row(0, named=True)
    logger.info("market_event_updated", event_id=event_id)

    return MarketEvent(
        id=row["id"],
        event_type=row["event_type"],
        event_date=str(row["event_date"]),
        event_time=str(row["event_time"]) if row["event_time"] else None,
        title=row["title"],
        description=row["description"],
        expected_value=float(row["expected_value"]) if row["expected_value"] else None,
        actual_value=float(row["actual_value"]) if row["actual_value"] else None,
        prior_value=float(row["prior_value"]) if row["prior_value"] else None,
        surprise_pct=float(row["surprise_pct"]) if row["surprise_pct"] else None,
        impact_score=row["impact_score"],
        spy_change_1h=float(row["spy_change_1h"]) if row["spy_change_1h"] else None,
        spy_change_1d=float(row["spy_change_1d"]) if row["spy_change_1d"] else None,
        source=row["source"],
        created_at=str(row["created_at"]) if row["created_at"] else None,
    )


def get_event_type_info() -> list[EventTypeInfo]:
    """Get metadata for all event types."""
    return list(EVENT_TYPE_INFO.values())


def get_upcoming_events(days: int = 30) -> list[MarketEvent]:
    """Get upcoming events in the next N days.

    Args:
        days: Number of days to look ahead

    Returns:
        List of upcoming events
    """
    today = dt.date.today()
    end_date = today + dt.timedelta(days=days)

    response = get_market_events(start_date=today, end_date=end_date, limit=50)
    # Sort by date ascending for upcoming
    return sorted(response.events, key=lambda e: e.event_date)


def get_recent_events(days: int = 30) -> list[MarketEvent]:
    """Get recent events from the past N days.

    Args:
        days: Number of days to look back

    Returns:
        List of recent events
    """
    today = dt.date.today()
    start_date = today - dt.timedelta(days=days)

    response = get_market_events(start_date=start_date, end_date=today, limit=50)
    return response.events
