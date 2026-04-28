"""Market events service — CRUD for macro events (FOMC, CPI, NFP, etc.)."""

from __future__ import annotations

import datetime as dt
from typing import Any, cast

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
from ..utils.market_hours import NY_TZ

logger = get_logger(__name__)

MACRO_LOOKAHEAD_DAYS = 14
MACRO_CALENDAR_DEFAULT = {
    "freshness": "missing",
    "reason": "no_future_rows",
    "upcoming_event_count": 0,
    "next_event_date": None,
    "event_type_counts": {},
    "high_impact_event_count": 0,
    "next_high_impact_event": None,
}


def _flt(v: Any) -> float | None:
    return float(v) if v is not None else None


def _row_to_market_event(row: dict[str, Any]) -> MarketEvent:
    return MarketEvent(
        id=row["id"],
        event_type=row["event_type"],
        event_date=str(row["event_date"]),
        event_time=str(row["event_time"]) if row["event_time"] else None,
        title=row["title"],
        description=row.get("description"),
        expected_value=_flt(row.get("expected_value")),
        actual_value=_flt(row.get("actual_value")),
        prior_value=_flt(row.get("prior_value")),
        surprise_pct=_flt(row.get("surprise_pct")),
        impact_score=row["impact_score"],
        spy_change_1h=_flt(row.get("spy_change_1h")),
        spy_change_1d=_flt(row.get("spy_change_1d")),
        source=row["source"],
        created_at=str(row["created_at"]) if row.get("created_at") else None,
    )


def _compute_surprise_pct(actual: float | None, expected: float | None) -> float | None:
    return ((actual - expected) / abs(expected)) * 100 if actual is not None and expected else None


def _chart_event_dict(row: dict[str, Any]) -> dict[str, Any]:
    info = EVENT_TYPE_INFO.get(row["event_type"])
    return {
        "id": row["id"],
        "date": str(row["event_date"]),
        "time": str(row["event_time"]) if row["event_time"] else None,
        "type": row["event_type"],
        "title": row["title"],
        "label": info.short_label if info else row["event_type"],
        "color": info.color if info else "#6B7280",
        "impact_score": row["impact_score"],
        "actual_value": _flt(row["actual_value"]),
        "expected_value": _flt(row["expected_value"]),
        "surprise_pct": _flt(row["surprise_pct"]),
    }


def _coerce_event_date(value: Any) -> dt.date | None:  # noqa: PLR0911
    if isinstance(value, dt.datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=NY_TZ).date()
        return value.astimezone(NY_TZ).date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return dt.date.fromisoformat(text)
        except ValueError:
            pass
        normalized = f"{text[:-1]}+00:00" if text.endswith("Z") else text
        try:
            parsed = dt.datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=NY_TZ).date()
        return parsed.astimezone(NY_TZ).date()
    return None


def build_default_macro_calendar_cluster(existing: dict[str, Any] | None = None) -> dict[str, Any]:
    base = dict(existing) if isinstance(existing, dict) else {}
    return {**base, **MACRO_CALENDAR_DEFAULT}


def build_macro_calendar_cluster(
    *,
    market_date: dt.date,
    latest_event_date: dt.date | None,
    upcoming_events: list[MarketEvent],
    existing: dict[str, Any] | None,
) -> dict[str, Any]:
    base = dict(existing) if isinstance(existing, dict) else {}
    if latest_event_date is not None and latest_event_date < market_date:
        freshness = "stale"
        reason = "stale_table"
    elif not upcoming_events:
        freshness = "missing"
        reason = "no_future_rows"
    else:
        freshness = "fresh"
        reason = "ok"

    event_type_counts: dict[str, int] = {}
    high_impact_candidates: list[tuple[dt.date, str | None, str, int, int, MarketEvent]] = []
    for event in upcoming_events:
        event_type = str(event.event_type).strip().lower() if getattr(event, "event_type", None) is not None else ""
        title = str(event.title).strip() if getattr(event, "title", None) is not None else ""
        event_date = _coerce_event_date(getattr(event, "event_date", None))
        if not event_type or not title or event_date is None:
            continue
        event_type_counts[event_type] = event_type_counts.get(event_type, 0) + 1
        impact_score = getattr(event, "impact_score", None)
        if isinstance(impact_score, (int, float)):
            impact_int = int(impact_score)
            if impact_int >= 4:
                raw_time = getattr(event, "event_time", None)
                event_time = str(raw_time).strip() if raw_time else None
                row_id = int(getattr(event, "id", 0)) if isinstance(getattr(event, "id", None), int) else 10**12
                high_impact_candidates.append((event_date, event_time, title, impact_int, row_id, event))

    high_impact_candidates.sort(
        key=lambda item: (
            item[0],
            item[1] is None,
            item[1] or "",
            item[2],
            item[4],
        )
    )
    next_high_impact_event = None
    if high_impact_candidates:
        _, _, _, impact_score, _, event = high_impact_candidates[0]
        next_high_impact_event = {
            "event_type": str(event.event_type).strip().lower(),
            "event_date": event.event_date,
            "event_time": event.event_time,
            "title": event.title,
            "impact_score": impact_score,
        }

    result = {
        **base,
        "freshness": freshness,
        "reason": reason,
        "upcoming_event_count": len(upcoming_events),
        "next_event_date": upcoming_events[0].event_date if upcoming_events else None,
        "event_type_counts": event_type_counts,
        "high_impact_event_count": len(high_impact_candidates),
        "next_high_impact_event": next_high_impact_event,
    }
    if upcoming_events or "upcoming_events" in base:
        result["upcoming_events"] = [event.model_dump() for event in upcoming_events]
    return result


def get_macro_calendar_cluster(
    *,
    market_date: dt.date,
    existing: dict[str, Any] | None = None,
    lookahead_days: int = MACRO_LOOKAHEAD_DAYS,
    storage: Any | None = None,
) -> dict[str, Any]:
    effective_storage = storage or get_storage()
    rows = effective_storage.query(
        """
        SELECT
            id,
            event_type::text,
            event_date,
            event_time::text,
            title,
            description,
            expected_value,
            actual_value,
            prior_value,
            surprise_pct,
            impact_score,
            spy_change_1h,
            spy_change_1d,
            source,
            created_at
        FROM market_events
        ORDER BY event_date ASC NULLS LAST, event_time ASC NULLS LAST, id ASC
        """
    )
    window_end = market_date + dt.timedelta(days=lookahead_days)
    latest_event_date: dt.date | None = None
    upcoming: list[tuple[dt.date, str | None, MarketEvent]] = []

    for row in rows.iter_rows(named=True):
        normalized_date = _coerce_event_date(row.get("event_date"))
        if normalized_date is None:
            continue
        if latest_event_date is None or normalized_date > latest_event_date:
            latest_event_date = normalized_date
        if not (market_date <= normalized_date <= window_end):
            continue
        event_row = dict(row)
        event_row["event_date"] = normalized_date.isoformat()
        try:
            event = _row_to_market_event(event_row)
        except Exception:
            logger.debug("market_event_row_skipped_for_macro_calendar", row=event_row, exc_info=True)
            continue
        upcoming.append((normalized_date, event.event_time, event))

    upcoming.sort(key=lambda item: (item[0], item[1] or "", item[2].title))
    return build_macro_calendar_cluster(
        market_date=market_date,
        latest_event_date=latest_event_date,
        upcoming_events=[event for _, _, event in upcoming],
        existing=existing,
    )


def get_market_events(
    start_date: dt.date | None = None,
    end_date: dt.date | None = None,
    event_types: list[MarketEventType] | None = None,
    limit: int = 100,
) -> MarketEventsResponse:
    """Get market events with optional filtering."""
    storage = get_storage()
    conditions: list[str] = []
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
    where = " AND ".join(conditions) if conditions else "1=1"
    query = f"""
        SELECT id, event_type::text, event_date, event_time::text,
               title, description, expected_value, actual_value, prior_value,
               surprise_pct, impact_score, spy_change_1h, spy_change_1d,
               source, created_at
        FROM market_events
        WHERE {where}
        ORDER BY event_date DESC, event_time DESC NULLS LAST
        LIMIT %(limit)s
    """
    events = [_row_to_market_event(r) for r in storage.query(query, params).iter_rows(named=True)]
    return MarketEventsResponse(
        events=events,
        total=len(events),
        start_date=str(start_date) if start_date else None,
        end_date=str(end_date) if end_date else None,
    )


def get_events_for_chart(start_date: dt.date, end_date: dt.date) -> list[dict[str, Any]]:
    """Get events formatted for chart overlay."""
    storage = get_storage()
    query = """
        SELECT id, event_type::text, event_date, event_time::text,
               title, impact_score, actual_value, expected_value, surprise_pct
        FROM market_events
        WHERE event_date >= %(start_date)s AND event_date <= %(end_date)s
        ORDER BY event_date ASC, event_time ASC NULLS LAST
    """
    df = storage.query(query, {"start_date": start_date, "end_date": end_date})
    return [_chart_event_dict(cast(dict[str, Any], row)) for row in df.iter_rows(named=True)]


def create_market_event(event: MarketEventCreate) -> MarketEvent:
    """Create a new market event."""
    storage = get_storage()
    event_data = event.model_dump()
    surprise_pct = _compute_surprise_pct(event.actual_value, event.expected_value)
    query = """
        INSERT INTO market_events (
            event_type, event_date, event_time, title, description,
            expected_value, actual_value, prior_value, surprise_pct, impact_score, source
        ) VALUES (
            %(event_type)s::market_event_type, %(event_date)s, %(event_time)s,
            %(title)s, %(description)s,
            %(expected_value)s, %(actual_value)s, %(prior_value)s,
            %(surprise_pct)s, %(impact_score)s, %(source)s
        )
        RETURNING id, created_at
    """
    params = {**event_data, "surprise_pct": surprise_pct}
    row = storage.query(query, params).row(0, named=True)
    logger.info(
        "market_event_created",
        event_id=row["id"],
        event_type=event.event_type,
        event_date=event.event_date,
    )
    return _row_to_market_event(
        {
            **event_data,
            "id": row["id"],
            "surprise_pct": surprise_pct,
            "spy_change_1h": None,
            "spy_change_1d": None,
            "created_at": row["created_at"],
        }
    )


def update_market_event(event_id: int, update: MarketEventUpdate) -> MarketEvent | None:
    """Update an existing market event with actual values."""
    storage = get_storage()
    set_parts: list[str] = []
    params: dict[str, Any] = {"event_id": event_id}
    for field in ("actual_value", "surprise_pct", "impact_score", "spy_change_1h", "spy_change_1d"):
        value = getattr(update, field)
        if value is not None:
            set_parts.append(f"{field} = %({field})s")
            params[field] = value
    if not set_parts:
        return None
    query = f"""
        UPDATE market_events
        SET {", ".join(set_parts)}, updated_at = CURRENT_TIMESTAMP
        WHERE id = %(event_id)s
        RETURNING *
    """
    result = storage.query(query, params)
    if result.is_empty():
        return None
    logger.info("market_event_updated", event_id=event_id)
    return _row_to_market_event(result.row(0, named=True))


def get_event_type_info() -> list[EventTypeInfo]:
    return list(EVENT_TYPE_INFO.values())


def get_upcoming_events(days: int = 30, *, start_date: dt.date | None = None) -> list[MarketEvent]:
    """Get upcoming events in the next N days."""
    today = start_date or dt.date.today()
    r = get_market_events(start_date=today, end_date=today + dt.timedelta(days=days), limit=50)
    return sorted(r.events, key=lambda e: e.event_date)


def get_recent_events(days: int = 30) -> list[MarketEvent]:
    """Get recent events from the past N days."""
    today = dt.date.today()
    r = get_market_events(start_date=today - dt.timedelta(days=days), end_date=today, limit=50)
    return r.events
