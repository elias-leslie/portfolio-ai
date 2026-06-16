"""Catalyst pre-warm workflow (F4).

Runs once per morning to warm the ``reference_cache`` rows that
:class:`CatalystCalendarService` reads on every request, and to refresh
the ``fomc_meetings`` table from the Federal Reserve calendar JSON.

Pre-warming keeps ``/api/catalysts/upcoming`` (and ``st portfolio
catalysts``) fast during the trading day — without it, the first agent
call of the morning would block on yfinance for every portfolio
symbol.
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import UTC, date, datetime, timedelta
from typing import Any

import requests
from hatchet_sdk import ConcurrencyExpression, ConcurrencyLimitStrategy, Context

from ..constants import SHORT_HTTP_TIMEOUT
from ..hatchet_app import hatchet
from ..logging_config import get_logger
from .data_refresh_schedules import CATALYST_PREWARM_CRONS
from .models import EmptyInput

logger = get_logger(__name__)

# Federal Reserve publishes the FOMC calendar as JSON at this URL. The
# document is small (<10KB) and rarely changes, so a once-per-morning
# fetch is plenty.
FOMC_CALENDAR_URL = "https://www.federalreserve.gov/json/calendar.json"

# How far forward the prewarm refresh looks. The calendar always
# contains the next ~1y of meetings; we only persist what we'll use.
FOMC_LOOKAHEAD_DAYS = 400


def run_catalyst_prewarm(today: date | None = None) -> dict[str, Any]:
    """Pre-warm catalyst caches synchronously.

    Exposed at module level so tests can drive it without the Hatchet
    runtime; the Hatchet task body is a thin async shim.
    """
    from importlib import import_module

    storage = import_module("app.storage").get_storage()
    catalyst_mod = import_module("app.services.catalyst_calendar_service")
    earnings_mod = import_module("app.watchlist.earnings")

    anchor = today or date.today()
    service = catalyst_mod.CatalystCalendarService(storage)
    universe = service._resolve_symbol_universe(None, include_watchlist=True)

    earnings_warmed = 0
    exdiv_warmed = 0
    with storage.connection() as conn:
        for symbol in universe:
            try:
                if earnings_mod.fetch_earnings_date_cached(conn, symbol) is not None:
                    earnings_warmed += 1
                if (
                    earnings_mod.fetch_ex_dividend_date_cached(conn, symbol)
                    is not None
                ):
                    exdiv_warmed += 1
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning(
                    "catalyst_prewarm_symbol_failed",
                    symbol=symbol,
                    error=str(exc),
                )

    fomc_inserted = _refresh_fomc_meetings(storage, anchor)

    logger.info(
        "catalyst_prewarm_completed",
        anchor=anchor.isoformat(),
        symbols=len(universe),
        earnings_warmed=earnings_warmed,
        exdiv_warmed=exdiv_warmed,
        fomc_inserted=fomc_inserted,
    )
    return {
        "anchor": anchor.isoformat(),
        "symbols": len(universe),
        "earnings_warmed": earnings_warmed,
        "exdiv_warmed": exdiv_warmed,
        "fomc_inserted": fomc_inserted,
    }


def _refresh_fomc_meetings(storage: Any, anchor: date) -> int:
    """Pull the Fed calendar and upsert future meetings into our table.

    The Fed JSON shape is loosely documented; we only extract entries
    whose ``date`` parses to a future date within
    :data:`FOMC_LOOKAHEAD_DAYS` and are tagged with a recognizable
    meeting type. Older entries stay in our table so the calendar is
    a stable record.
    """
    cutoff = anchor + timedelta(days=FOMC_LOOKAHEAD_DAYS)
    try:
        resp = requests.get(FOMC_CALENDAR_URL, timeout=SHORT_HTTP_TIMEOUT)
        resp.raise_for_status()
        payload = json.loads(resp.content.decode("utf-8-sig"))
    except Exception as exc:
        logger.warning("fomc_calendar_fetch_failed", error=str(exc))
        return 0

    inserted = 0
    rows = _extract_fomc_rows(payload, anchor, cutoff)
    if not rows:
        return 0
    with storage.connection() as conn:
        for meeting_date, meeting_type in rows:
            conn.execute(
                """
                INSERT INTO fomc_meetings (meeting_date, meeting_type, source)
                VALUES (%s, %s, %s)
                ON CONFLICT (meeting_date) DO UPDATE SET
                    meeting_type = EXCLUDED.meeting_type,
                    source = EXCLUDED.source,
                    fetched_at = now()
                """,
                [meeting_date, meeting_type, "federalreserve.gov"],
            )
            inserted += 1
        conn.commit()
    return inserted


def _extract_fomc_rows(
    payload: Any, anchor: date, cutoff: date
) -> list[tuple[date, str]]:
    """Best-effort parser over the Fed calendar JSON."""
    out: list[tuple[date, str]] = []
    if not isinstance(payload, dict):
        return out
    events = payload.get("events") or payload.get("calendar") or []
    if not isinstance(events, list):
        return out
    for entry in events:
        if not isinstance(entry, dict):
            continue
        title = str(entry.get("title") or entry.get("name") or "").lower()
        if "fomc" not in title and "federal open market committee" not in title:
            continue
        meeting_type = "regular"
        if "press conference" in title:
            meeting_type = "press_conference"
        elif "minutes" in title:
            meeting_type = "minutes"
        meeting = _parse_calendar_entry_date(entry)
        if meeting is None or meeting < anchor or meeting > cutoff:
            continue
        out.append((meeting, meeting_type))
    return out


def _parse_calendar_entry_date(entry: dict[str, Any]) -> date | None:
    """Parse both ISO dates and the Fed calendar's month/days fields."""
    date_str = str(entry.get("date") or entry.get("start") or "")
    if parsed := _parse_iso_date(date_str):
        return parsed

    month = str(entry.get("month") or "")
    day_label = str(entry.get("day") or entry.get("days") or "")
    if not re.fullmatch(r"\d{4}-\d{2}", month):
        return None
    day_match = re.search(r"(\d{1,2})(?!.*\d)", day_label)
    if day_match is None:
        return None
    try:
        return date.fromisoformat(f"{month}-{int(day_match.group(1)):02d}")
    except ValueError:
        return None


def _parse_iso_date(raw: str) -> date | None:
    if not raw:
        return None
    try:
        # Accept "YYYY-MM-DD" or full ISO 8601 timestamps.
        if "T" in raw:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(UTC).date()
        return date.fromisoformat(raw)
    except ValueError:
        return None

@hatchet.task(
    name="portfolio-catalyst-prewarm",
    input_validator=EmptyInput,
    execution_timeout="900s",
    retries=2,
    backoff_factor=2.0,
    on_crons=CATALYST_PREWARM_CRONS,
    concurrency=ConcurrencyExpression(
        expression="'portfolio-catalyst-prewarm'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def portfolio_catalyst_prewarm_wf(
    input: EmptyInput, ctx: Context
) -> dict[str, Any]:
    del input, ctx
    return await asyncio.to_thread(run_catalyst_prewarm)
