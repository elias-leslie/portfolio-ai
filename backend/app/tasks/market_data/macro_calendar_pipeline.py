"""Macro-calendar ingestion pipeline."""

from __future__ import annotations

import datetime as dt
from typing import Any

from app.services.macro_calendar_ingestion_service import ingest_macro_calendar


def ingest_macro_calendar_events(
    *,
    start_date: dt.date | None = None,
    horizon_days: int = 365,
) -> dict[str, Any]:
    """Fetch authoritative future macro release dates and upsert market_events."""
    return ingest_macro_calendar(start_date=start_date, horizon_days=horizon_days)
