"""Unit tests for macro-calendar ingestion."""

from __future__ import annotations

import datetime as dt
from typing import Any

from app.services.macro_calendar_ingestion_service import (
    BEA_RELEASE_DATES_URL,
    BLS_MONTHLY_SCHEDULE_READER_URL_TEMPLATE,
    BLS_MONTHLY_SCHEDULE_URL_TEMPLATE,
    BLS_RELEASE_CALENDAR_URL,
    FED_FOMC_CALENDAR_URL,
    collect_macro_calendar_events,
    fetch_bea_release_events,
    fetch_bls_release_events,
    fetch_bls_release_events_from_monthly_pages,
    fetch_fomc_meeting_events,
    ingest_macro_calendar,
)
from app.services.market_events_service import get_macro_calendar_cluster


class _FakeRows:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def is_empty(self) -> bool:
        return not self._rows

    def iter_rows(self, *, named: bool = False):
        assert named is True
        return iter(self._rows)


class _FakeStorage:
    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows: dict[tuple[str, dt.date], dict[str, Any]] = {}
        self.executed: list[dict[str, Any]] = []
        self._next_id = 100
        for row in rows or []:
            event_date = row["event_date"]
            if isinstance(event_date, str):
                event_date = dt.date.fromisoformat(event_date)
            self.rows[(str(row["event_type"]), event_date)] = dict(row, event_date=event_date)

    def query(self, query: str, params: Any | None = None) -> _FakeRows:
        if "SELECT id" in query and "WHERE event_type" in query:
            assert params is not None
            key = (str(params["event_type"]), params["event_date"])
            existing = self.rows.get(key)
            return _FakeRows([{"id": existing["id"]}] if existing else [])
        return _FakeRows(
            sorted(
                [self._complete_row(row) for row in self.rows.values()],
                key=lambda row: (row["event_date"], row.get("event_time") or "", row["id"]),
            )
        )

    def execute(self, query: str, params: Any | None = None) -> None:
        assert params is not None
        self.executed.append(dict(params))
        key = (str(params["event_type"]), params["event_date"])
        existing = self.rows.get(key)
        if existing is None:
            self._next_id += 1
            self.rows[key] = self._complete_row(
                {
                    "id": self._next_id,
                    "event_type": params["event_type"],
                    "event_date": params["event_date"],
                    "event_time": params["event_time"],
                    "title": params["title"],
                    "description": params["description"],
                    "impact_score": params["impact_score"],
                    "source": params["source"],
                }
            )
            return
        existing["event_time"] = params["event_time"] or existing.get("event_time")
        existing["title"] = params["title"]
        existing["description"] = params["description"] or existing.get("description")
        existing["impact_score"] = params["impact_score"] or existing.get("impact_score")
        existing["source"] = params["source"]

    @staticmethod
    def _complete_row(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "event_type": row["event_type"],
            "event_date": row["event_date"],
            "event_time": row.get("event_time"),
            "title": row["title"],
            "description": row.get("description"),
            "expected_value": row.get("expected_value"),
            "actual_value": row.get("actual_value"),
            "prior_value": row.get("prior_value"),
            "surprise_pct": row.get("surprise_pct"),
            "impact_score": row.get("impact_score"),
            "spy_change_1h": row.get("spy_change_1h"),
            "spy_change_1d": row.get("spy_change_1d"),
            "source": row.get("source", "test"),
            "created_at": row.get("created_at"),
        }


def test_fetch_fomc_meeting_events_parses_official_calendar_rows() -> None:
    html = """
    <div class="panel panel-default"><div class="panel-heading"><h4>
    <a id="42828">2026 FOMC Meetings</a></h4></div>
    <div class="row fomc-meeting" ">
      <div class="fomc-meeting__month col-xs-5"><strong>April</strong></div>
      <div class="fomc-meeting__date col-xs-4">28-29</div>
    </div>
    <div class="fomc-meeting--shaded row fomc-meeting" ">
      <div class="fomc-meeting__month col-xs-5"><strong>June</strong></div>
      <div class="fomc-meeting__date col-xs-4">16-17*</div>
    </div>
    <div class="panel-footer">* Meeting associated with a Summary of Economic Projections.</div>
    <div class="panel panel-default"><div class="panel-heading"><h4>
    <a id="42827">2025 FOMC Meetings</a></h4></div>
    """

    events = fetch_fomc_meeting_events(
        start_date=dt.date(2026, 4, 24),
        end_date=dt.date(2026, 5, 1),
        text_fetcher=lambda url: html if url == FED_FOMC_CALENDAR_URL else "",
    )

    assert len(events) == 1
    assert events[0].event_type == "fomc_decision"
    assert events[0].event_date == dt.date(2026, 4, 29)
    assert events[0].event_time is None
    assert events[0].title == "FOMC Meeting: April 28-29, 2026"
    assert FED_FOMC_CALENDAR_URL in events[0].description


def test_fetch_bea_release_events_parses_gdp_and_pce_json_and_skips_rescheduled() -> None:
    payload = {
        "Gross Domestic Product": {
            "release_dates": [
                "2026-04-09T12:30:00+00:00",
                "2026-04-30T12:30:00+00:00",
            ],
            "to_be_rescheduled": ["2026-04-09T12:30:00+00:00"],
        },
        "Personal Income and Outlays": {
            "release_dates": ["2026-04-30T12:30:00+00:00"],
        },
    }

    events = fetch_bea_release_events(
        start_date=dt.date(2026, 4, 24),
        end_date=dt.date(2026, 5, 1),
        json_fetcher=lambda url: payload if url == BEA_RELEASE_DATES_URL else {},
    )

    assert [(event.event_type, event.event_date, event.event_time, event.title) for event in events] == [
        ("gdp_release", dt.date(2026, 4, 30), dt.time(8, 30), "Gross Domestic Product"),
        ("pce_release", dt.date(2026, 4, 30), dt.time(8, 30), "Personal Income and Outlays"),
    ]


def test_fetch_bls_release_events_parses_key_bls_market_movers_ics() -> None:
    calendar = """
BEGIN:VCALENDAR
BEGIN:VEVENT
DTSTART;TZID=America/New_York:20260508T083000
SUMMARY:Employment Situation
END:VEVENT
BEGIN:VEVENT
DTSTART;TZID=America/New_York:20260512T083000
SUMMARY:Consumer Price Index
END:VEVENT
BEGIN:VEVENT
DTSTART;TZID=America/New_York:20260513T083000
SUMMARY:Producer Price Index
END:VEVENT
END:VCALENDAR
"""

    events = fetch_bls_release_events(
        start_date=dt.date(2026, 5, 1),
        end_date=dt.date(2026, 5, 31),
        text_fetcher=lambda url: calendar if url == BLS_RELEASE_CALENDAR_URL else "",
    )

    assert [(event.event_type, event.event_date, event.event_time, event.title) for event in events] == [
        ("nfp_release", dt.date(2026, 5, 8), dt.time(8, 30), "Employment Situation"),
        ("cpi_release", dt.date(2026, 5, 12), dt.time(8, 30), "Consumer Price Index"),
        ("ppi_release", dt.date(2026, 5, 13), dt.time(8, 30), "Producer Price Index"),
    ]


def test_fetch_bls_release_events_falls_back_to_official_monthly_schedule_reader() -> None:
    monthly_page = """
| Date | Time | Release |
| --- | --- | --- |
| Friday, May 08, 2026 | 08:30 AM | **Employment Situation** for April 2026 |
| Tuesday, May 12, 2026 | 08:30 AM | **Consumer Price Index** for April 2026 |
| Wednesday, May 13, 2026 | 08:30 AM | **Producer Price Index** for April 2026 |
"""

    def text_fetcher(url: str) -> str:
        if url == BLS_RELEASE_CALENDAR_URL:
            raise RuntimeError("403 forbidden")
        expected_url = BLS_MONTHLY_SCHEDULE_READER_URL_TEMPLATE.format(year=2026, month=5)
        assert url == expected_url
        return monthly_page

    events = fetch_bls_release_events(
        start_date=dt.date(2026, 5, 1),
        end_date=dt.date(2026, 5, 31),
        text_fetcher=text_fetcher,
    )

    assert [(event.event_type, event.event_date, event.event_time, event.title) for event in events] == [
        ("nfp_release", dt.date(2026, 5, 8), dt.time(8, 30), "Employment Situation"),
        ("cpi_release", dt.date(2026, 5, 12), dt.time(8, 30), "Consumer Price Index"),
        ("ppi_release", dt.date(2026, 5, 13), dt.time(8, 30), "Producer Price Index"),
    ]
    assert all("BLS monthly release schedule" in str(event.description) for event in events)
    assert all(BLS_MONTHLY_SCHEDULE_URL_TEMPLATE.format(year=2026, month=5) in str(event.description) for event in events)


def test_fetch_bls_monthly_schedule_filters_to_supported_market_movers() -> None:
    monthly_page = """
| Date | Time | Release |
| --- | --- | --- |
| Tuesday, May 05, 2026 | 10:00 AM | **Job Openings and Labor Turnover Survey** for March 2026 |
| Friday, May 08, 2026 | 08:30 AM | **Employment Situation** for April 2026 |
| Tuesday, May 12, 2026 | 08:30 AM | **Consumer Price Index** for April 2026 |
| Wednesday, May 13, 2026 | 08:30 AM | **Producer Price Index** for April 2026 |
"""

    events = fetch_bls_release_events_from_monthly_pages(
        start_date=dt.date(2026, 5, 1),
        end_date=dt.date(2026, 5, 31),
        text_fetcher=lambda _url: monthly_page,
    )

    assert [event.event_type for event in events] == ["nfp_release", "cpi_release", "ppi_release"]


def test_ingest_macro_calendar_dedupes_and_upserts_without_overwriting_actuals() -> None:
    storage = _FakeStorage(
        [
            {
                "id": 1,
                "event_type": "gdp_release",
                "event_date": dt.date(2026, 4, 30),
                "event_time": "08:30:00",
                "title": "Old GDP",
                "actual_value": 2.1,
                "source": "manual",
            }
        ]
    )
    payload = {
        "Gross Domestic Product": {
            "release_dates": [
                "2026-04-30T12:30:00+00:00",
                "2026-04-30T12:30:00+00:00",
            ]
        }
    }

    result = ingest_macro_calendar(
        start_date=dt.date(2026, 4, 24),
        horizon_days=10,
        storage=storage,
        json_fetcher=lambda url: payload if url == BEA_RELEASE_DATES_URL else {},
        text_fetcher=lambda _url: "",
        sources=["bea_release_dates"],
    )

    assert result["status"] == "success"
    assert result["events_received"] == 1
    assert result["events_updated"] == 1
    row = storage.rows[("gdp_release", dt.date(2026, 4, 30))]
    assert row["title"] == "Gross Domestic Product"
    assert row["actual_value"] == 2.1
    assert row["source"] == "bea_release_dates"


def test_collect_macro_calendar_events_reports_empty_and_failed_sources() -> None:
    def failing_text_fetcher(url: str) -> str:
        raise RuntimeError(f"blocked {url}")

    collection = collect_macro_calendar_events(
        start_date=dt.date(2026, 4, 24),
        horizon_days=10,
        json_fetcher=lambda _url: {},
        text_fetcher=failing_text_fetcher,
        sources=["bea_release_dates", "bls_release_calendar"],
    )

    assert collection.events == []
    assert collection.source_statuses["bea_release_dates"]["status"] == "empty"
    assert collection.source_statuses["bls_release_calendar"]["status"] == "error"
    assert collection.errors == [
        {
            "source": "bls_release_calendar",
            "error": "blocked "
            + BLS_MONTHLY_SCHEDULE_READER_URL_TEMPLATE.format(year=2026, month=4),
        }
    ]


def test_ingested_events_make_macro_calendar_cluster_fresh() -> None:
    storage = _FakeStorage()
    storage.execute(
        "",
        {
            "event_type": "fomc_decision",
            "event_date": dt.date(2026, 4, 29),
            "event_time": None,
            "title": "FOMC Meeting: April 28-29, 2026",
            "description": "Federal Reserve FOMC calendar",
            "impact_score": 5,
            "source": "federal_reserve_fomc",
        },
    )
    storage.execute(
        "",
        {
            "event_type": "gdp_release",
            "event_date": dt.date(2026, 4, 30),
            "event_time": "08:30:00",
            "title": "Gross Domestic Product",
            "description": "BEA release-date JSON",
            "impact_score": 4,
            "source": "bea_release_dates",
        },
    )

    cluster = get_macro_calendar_cluster(market_date=dt.date(2026, 4, 24), storage=storage)

    assert cluster["freshness"] == "fresh"
    assert cluster["reason"] == "ok"
    assert cluster["upcoming_event_count"] == 2
    assert cluster["event_type_counts"] == {"fomc_decision": 1, "gdp_release": 1}
    assert cluster["next_high_impact_event"]["event_type"] == "fomc_decision"
