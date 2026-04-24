"""Ingest authoritative macro calendar events into market_events."""

from __future__ import annotations

import datetime as dt
import json
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from html import unescape
from typing import Any, Final, cast

import httpx

from app.constants import DEFAULT_HTTP_TIMEOUT
from app.logging_config import get_logger
from app.models.market_events import MarketEventType
from app.storage import get_storage
from app.utils.market_hours import NY_TZ

logger = get_logger(__name__)

BEA_RELEASE_DATES_URL: Final = "https://apps.bea.gov/API/signup/release_dates.json"
BLS_RELEASE_CALENDAR_URL: Final = "https://www.bls.gov/schedule/news_release/bls.ics"
FED_FOMC_CALENDAR_URL: Final = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"

REQUEST_HEADERS: Final = {
    "User-Agent": "portfolio-ai macro-calendar-ingestion/1.0",
    "Accept": "text/html,application/json,text/calendar,text/plain,*/*",
}

SOURCE_PROVENANCE: Final = {
    "federal_reserve_fomc": {
        "url": FED_FOMC_CALENDAR_URL,
        "availability": "Federal Reserve public FOMC meeting calendar HTML, updated by the Board.",
        "event_types": ["fomc_decision"],
    },
    "bea_release_dates": {
        "url": BEA_RELEASE_DATES_URL,
        "availability": "BEA machine-readable release-date JSON advertised from its release schedule.",
        "event_types": ["gdp_release", "pce_release"],
    },
    "bls_release_calendar": {
        "url": BLS_RELEASE_CALENDAR_URL,
        "availability": "BLS public iCalendar release calendar for national-office releases.",
        "event_types": ["cpi_release", "nfp_release"],
    },
}

BEA_RELEASE_TYPES: Final[dict[str, tuple[MarketEventType, int]]] = {
    "Gross Domestic Product": ("gdp_release", 4),
    "Personal Income and Outlays": ("pce_release", 4),
}

BLS_RELEASE_TYPES: Final[dict[str, tuple[MarketEventType, int]]] = {
    "Consumer Price Index": ("cpi_release", 5),
    "Employment Situation": ("nfp_release", 5),
}

MONTHS: Final = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

TextFetcher = Callable[[str], str]
JsonFetcher = Callable[[str], Any]


@dataclass(frozen=True)
class MacroCalendarEvent:
    event_type: MarketEventType
    event_date: dt.date
    event_time: dt.time | None
    title: str
    source: str
    description: str
    impact_score: int

    @property
    def event_time_text(self) -> str | None:
        if self.event_time is None:
            return None
        return self.event_time.replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class MacroCalendarCollection:
    events: list[MacroCalendarEvent]
    source_statuses: dict[str, dict[str, Any]]
    errors: list[dict[str, str]]


def _http_get_text(url: str) -> str:
    with httpx.Client(
        timeout=DEFAULT_HTTP_TIMEOUT,
        headers=REQUEST_HEADERS,
        follow_redirects=True,
    ) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.text


def _http_get_json(url: str) -> Any:
    return json.loads(_http_get_text(url))


def _in_window(event_date: dt.date, start_date: dt.date, end_date: dt.date) -> bool:
    return start_date <= event_date <= end_date


def _parse_iso_datetime_to_ny(value: str) -> dt.datetime | None:
    text = value.strip()
    if not text:
        return None
    try:
        parsed = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=NY_TZ)
    return parsed.astimezone(NY_TZ)


def _event_description(*, source_name: str, source_url: str, detail: str) -> str:
    return f"{detail}; provenance={source_name}; source_url={source_url}"


def fetch_bea_release_events(
    *,
    start_date: dt.date,
    end_date: dt.date,
    json_fetcher: JsonFetcher = _http_get_json,
) -> list[MacroCalendarEvent]:
    raw = json_fetcher(BEA_RELEASE_DATES_URL)
    if not isinstance(raw, dict):
        raise ValueError("BEA release-date payload is not an object")

    events: list[MacroCalendarEvent] = []
    for release_name, (event_type, impact_score) in BEA_RELEASE_TYPES.items():
        section = raw.get(release_name)
        if not isinstance(section, dict):
            continue
        release_dates = section.get("release_dates")
        if not isinstance(release_dates, list):
            continue
        rescheduled = {
            value for value in section.get("to_be_rescheduled", []) if isinstance(value, str)
        }
        for release_value in release_dates:
            if not isinstance(release_value, str) or release_value in rescheduled:
                continue
            release_dt = _parse_iso_datetime_to_ny(release_value)
            if release_dt is None or not _in_window(release_dt.date(), start_date, end_date):
                continue
            events.append(
                MacroCalendarEvent(
                    event_type=event_type,
                    event_date=release_dt.date(),
                    event_time=release_dt.timetz().replace(tzinfo=None),
                    title=release_name,
                    source="bea_release_dates",
                    description=_event_description(
                        source_name="BEA release-date JSON",
                        source_url=BEA_RELEASE_DATES_URL,
                        detail=f"{release_name} release schedule",
                    ),
                    impact_score=impact_score,
                )
            )
    return events


def _strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", unescape(text)).strip()


def _fomc_year_sections(html: str) -> Iterable[tuple[int, str]]:
    pattern = re.compile(
        r"<div class=\"panel panel-default\"><div class=\"panel-heading\"><h4>\s*"
        r"<a[^>]*>(?P<year>\d{4}) FOMC Meetings</a></h4></div>(?P<body>.*?)"
        r"(?=<div class=\"panel panel-default\"><div class=\"panel-heading\"><h4>\s*<a|\Z)",
        re.DOTALL,
    )
    for match in pattern.finditer(html):
        yield int(match.group("year")), match.group("body")


def _resolve_fomc_month_and_day(
    *,
    year: int,
    month_label: str,
    date_label: str,
) -> tuple[dt.date, str] | None:
    if "notation vote" in date_label.lower():
        return None
    month_parts = [part.strip().lower() for part in month_label.split("/") if part.strip()]
    if not month_parts:
        return None
    day_values = [int(value) for value in re.findall(r"\d{1,2}", date_label)]
    if not day_values:
        return None

    start_day = day_values[0]
    end_day = day_values[-1]
    month_name = month_parts[-1] if len(month_parts) > 1 and end_day < start_day else month_parts[0]
    month = MONTHS.get(month_name)
    if month is None:
        return None
    decision_year = year + 1 if month == 1 and month_parts[0] == "december" else year
    try:
        return dt.date(decision_year, month, end_day), date_label
    except ValueError:
        return None


def fetch_fomc_meeting_events(
    *,
    start_date: dt.date,
    end_date: dt.date,
    text_fetcher: TextFetcher = _http_get_text,
) -> list[MacroCalendarEvent]:
    html = text_fetcher(FED_FOMC_CALENDAR_URL)
    row_pattern = re.compile(
        r"<div[^>]*class=\"[^\"]*fomc-meeting[^\"]*\"[^>]*>.*?"
        r"<div[^>]*fomc-meeting__month[^>]*>\s*<strong>(?P<month>.*?)</strong>.*?"
        r"<div[^>]*fomc-meeting__date[^>]*>(?P<date>.*?)</div>",
        re.DOTALL,
    )
    events: list[MacroCalendarEvent] = []
    for year, body in _fomc_year_sections(html):
        for match in row_pattern.finditer(body):
            month_label = _strip_html(match.group("month"))
            date_label = _strip_html(match.group("date")).replace("*", "").strip()
            resolved = _resolve_fomc_month_and_day(
                year=year,
                month_label=month_label,
                date_label=date_label,
            )
            if resolved is None:
                continue
            event_date, clean_date_label = resolved
            if not _in_window(event_date, start_date, end_date):
                continue
            events.append(
                MacroCalendarEvent(
                    event_type="fomc_decision",
                    event_date=event_date,
                    event_time=None,
                    title=f"FOMC Meeting: {month_label} {clean_date_label}, {year}",
                    source="federal_reserve_fomc",
                    description=_event_description(
                        source_name="Federal Reserve FOMC calendar",
                        source_url=FED_FOMC_CALENDAR_URL,
                        detail=f"FOMC meeting dates {month_label} {clean_date_label}, {year}",
                    ),
                    impact_score=5,
                )
            )
    return events


def _unfold_ics_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw_line in text.splitlines():
        if raw_line.startswith((" ", "\t")) and lines:
            lines[-1] += raw_line[1:]
        else:
            lines.append(raw_line.rstrip("\r"))
    return lines


def _parse_ics_datetime(value: str) -> dt.datetime | None:
    text = value.strip()
    if not text:
        return None
    formats = ["%Y%m%dT%H%M%SZ", "%Y%m%dT%H%M%S", "%Y%m%dT%H%M", "%Y%m%d"]
    for fmt in formats:
        try:
            parsed = dt.datetime.strptime(text, fmt)
        except ValueError:
            continue
        if text.endswith("Z"):
            return parsed.replace(tzinfo=dt.UTC).astimezone(NY_TZ)
        return parsed.replace(tzinfo=NY_TZ)
    return None


def fetch_bls_release_events(
    *,
    start_date: dt.date,
    end_date: dt.date,
    text_fetcher: TextFetcher = _http_get_text,
) -> list[MacroCalendarEvent]:
    calendar_text = text_fetcher(BLS_RELEASE_CALENDAR_URL)
    events: list[MacroCalendarEvent] = []
    current: dict[str, str] | None = None
    for line in _unfold_ics_lines(calendar_text):
        if line == "BEGIN:VEVENT":
            current = {}
            continue
        if line == "END:VEVENT":
            if current is not None:
                events.extend(_build_bls_event(current, start_date=start_date, end_date=end_date))
            current = None
            continue
        if current is None or ":" not in line:
            continue
        key, value = line.split(":", 1)
        current[key.split(";", 1)[0].upper()] = value.replace("\\,", ",").strip()
    return events


def _build_bls_event(
    current: dict[str, str],
    *,
    start_date: dt.date,
    end_date: dt.date,
) -> list[MacroCalendarEvent]:
    summary = current.get("SUMMARY", "").strip()
    if summary not in BLS_RELEASE_TYPES:
        return []
    release_dt = _parse_ics_datetime(current.get("DTSTART", ""))
    if release_dt is None or not _in_window(release_dt.date(), start_date, end_date):
        return []
    event_type, impact_score = BLS_RELEASE_TYPES[summary]
    return [
        MacroCalendarEvent(
            event_type=event_type,
            event_date=release_dt.date(),
            event_time=release_dt.timetz().replace(tzinfo=None),
            title=summary,
            source="bls_release_calendar",
            description=_event_description(
                source_name="BLS release calendar",
                source_url=BLS_RELEASE_CALENDAR_URL,
                detail=f"{summary} release calendar",
            ),
            impact_score=impact_score,
        )
    ]


def _source_fetchers(
    *,
    start_date: dt.date,
    end_date: dt.date,
    text_fetcher: TextFetcher,
    json_fetcher: JsonFetcher,
) -> dict[str, Callable[[], list[MacroCalendarEvent]]]:
    return {
        "federal_reserve_fomc": lambda: fetch_fomc_meeting_events(
            start_date=start_date,
            end_date=end_date,
            text_fetcher=text_fetcher,
        ),
        "bea_release_dates": lambda: fetch_bea_release_events(
            start_date=start_date,
            end_date=end_date,
            json_fetcher=json_fetcher,
        ),
        "bls_release_calendar": lambda: fetch_bls_release_events(
            start_date=start_date,
            end_date=end_date,
            text_fetcher=text_fetcher,
        ),
    }


def collect_macro_calendar_events(
    *,
    start_date: dt.date,
    horizon_days: int = 365,
    text_fetcher: TextFetcher = _http_get_text,
    json_fetcher: JsonFetcher = _http_get_json,
    sources: Iterable[str] | None = None,
) -> MacroCalendarCollection:
    end_date = start_date + dt.timedelta(days=horizon_days)
    fetchers = _source_fetchers(
        start_date=start_date,
        end_date=end_date,
        text_fetcher=text_fetcher,
        json_fetcher=json_fetcher,
    )
    requested_sources = list(sources) if sources is not None else list(fetchers)
    events: list[MacroCalendarEvent] = []
    source_statuses: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, str]] = []

    for source_name in requested_sources:
        fetcher = fetchers.get(source_name)
        if fetcher is None:
            source_statuses[source_name] = {"status": "unknown_source", "events": 0}
            errors.append({"source": source_name, "error": "unknown source"})
            continue
        try:
            source_events = fetcher()
        except Exception as exc:
            logger.warning(
                "macro_calendar_source_failed",
                source=source_name,
                error=str(exc),
            )
            source_statuses[source_name] = {"status": "error", "events": 0}
            errors.append({"source": source_name, "error": str(exc)})
            continue
        source_statuses[source_name] = {
            "status": "ok" if source_events else "empty",
            "events": len(source_events),
            "provenance": SOURCE_PROVENANCE.get(source_name, {}),
        }
        events.extend(source_events)

    return MacroCalendarCollection(
        events=_dedupe_macro_events(events),
        source_statuses=source_statuses,
        errors=errors,
    )


def _dedupe_macro_events(events: Iterable[MacroCalendarEvent]) -> list[MacroCalendarEvent]:
    unique: dict[tuple[str, dt.date, str | None, str, str], MacroCalendarEvent] = {}
    for event in events:
        key = (
            event.event_type,
            event.event_date,
            event.event_time_text,
            event.title.strip().lower(),
            event.source,
        )
        unique.setdefault(key, event)
    return sorted(
        unique.values(),
        key=lambda event: (
            event.event_date,
            event.event_time_text or "",
            event.event_type,
            event.title,
        ),
    )


def upsert_macro_calendar_events(
    events: Iterable[MacroCalendarEvent],
    *,
    storage: Any | None = None,
) -> dict[str, int]:
    event_list = list(events)
    unique_events = _dedupe_macro_events(event_list)
    effective_storage = storage or get_storage()
    inserted = 0
    updated = 0
    for event in unique_events:
        params = {
            "event_type": event.event_type,
            "event_date": event.event_date,
            "event_time": event.event_time_text,
            "title": event.title,
            "description": event.description,
            "impact_score": event.impact_score,
            "source": event.source,
        }
        existing = effective_storage.query(
            """
            SELECT id
            FROM market_events
            WHERE event_type = %(event_type)s::market_event_type
              AND event_date = %(event_date)s
            LIMIT 1
            """,
            params,
        )
        existed = not existing.is_empty()
        effective_storage.execute(
            """
            INSERT INTO market_events (
                event_type, event_date, event_time, title, description, impact_score, source
            ) VALUES (
                %(event_type)s::market_event_type, %(event_date)s, %(event_time)s,
                %(title)s, %(description)s, %(impact_score)s, %(source)s
            )
            ON CONFLICT (event_type, event_date)
            DO UPDATE SET
                event_time = COALESCE(EXCLUDED.event_time, market_events.event_time),
                title = EXCLUDED.title,
                description = COALESCE(EXCLUDED.description, market_events.description),
                impact_score = COALESCE(EXCLUDED.impact_score, market_events.impact_score),
                source = EXCLUDED.source,
                updated_at = CURRENT_TIMESTAMP
            """,
            params,
        )
        if existed:
            updated += 1
        else:
            inserted += 1

    return {
        "events_received": len(event_list),
        "events_deduped": len(unique_events),
        "events_inserted": inserted,
        "events_updated": updated,
        "events_skipped": len(event_list) - len(unique_events),
    }


def ingest_macro_calendar(
    *,
    start_date: dt.date | None = None,
    horizon_days: int = 365,
    storage: Any | None = None,
    text_fetcher: TextFetcher = _http_get_text,
    json_fetcher: JsonFetcher = _http_get_json,
    sources: Iterable[str] | None = None,
) -> dict[str, Any]:
    effective_start = start_date or dt.date.today()
    collection = collect_macro_calendar_events(
        start_date=effective_start,
        horizon_days=horizon_days,
        text_fetcher=text_fetcher,
        json_fetcher=json_fetcher,
        sources=sources,
    )
    upsert_stats = upsert_macro_calendar_events(collection.events, storage=storage)
    source_errors = collection.errors
    successful_sources = [
        name for name, status in collection.source_statuses.items() if status["status"] == "ok"
    ]
    if source_errors and collection.events:
        status = "partial"
    elif source_errors and not collection.events:
        status = "failed"
    elif not collection.events:
        status = "empty"
    else:
        status = "success"

    result = {
        "status": status,
        "window_start": effective_start.isoformat(),
        "window_end": (effective_start + dt.timedelta(days=horizon_days)).isoformat(),
        "sources_ok": successful_sources,
        "source_statuses": collection.source_statuses,
        "errors": source_errors,
        **upsert_stats,
    }
    logger.info(
        "macro_calendar_ingestion_completed",
        status=status,
        events_inserted=upsert_stats["events_inserted"],
        events_updated=upsert_stats["events_updated"],
        errors=len(source_errors),
    )
    return cast(dict[str, Any], result)
