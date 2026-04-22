"""Unit tests for market-events truth helpers."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from app.models.market_events import MarketEvent, MarketEventsResponse
from app.services.market_events_service import (
    build_macro_calendar_cluster,
    get_macro_calendar_cluster,
    get_upcoming_events,
)


class _FakeRows:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def iter_rows(self, *, named: bool = False):
        assert named is True
        return iter(self._rows)


class _FakeStorage:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def query(self, query: str, params: Any | None = None) -> _FakeRows:
        return _FakeRows(self.rows)


def _event_row(*, event_id: int, event_date: Any, title: str) -> dict[str, Any]:
    return {
        "id": event_id,
        "event_type": "cpi_release",
        "event_date": event_date,
        "event_time": None,
        "title": title,
        "description": None,
        "expected_value": None,
        "actual_value": None,
        "prior_value": None,
        "surprise_pct": None,
        "impact_score": None,
        "spy_change_1h": None,
        "spy_change_1d": None,
        "source": "test",
        "created_at": None,
    }


def _event(*, event_id: int, event_date: str, title: str) -> MarketEvent:
    return MarketEvent(
        id=event_id,
        event_type="cpi_release",
        event_date=event_date,
        event_time=None,
        title=title,
        description=None,
        expected_value=None,
        actual_value=None,
        prior_value=None,
        surprise_pct=None,
        impact_score=None,
        spy_change_1h=None,
        spy_change_1d=None,
        source="test",
        created_at=None,
    )


def test_get_macro_calendar_cluster_coerces_date_datetime_and_string_rows_to_ny_calendar_dates() -> None:
    storage = _FakeStorage(
        [
            _event_row(event_id=1, event_date=datetime(2026, 4, 22, 2, 30, tzinfo=UTC), title="Overnight UTC row"),
            _event_row(event_id=2, event_date="2026-04-23T01:30:00Z", title="ISO string row"),
            _event_row(event_id=3, event_date=datetime(2026, 4, 25, 9, 15), title="Naive NY row"),
            _event_row(event_id=4, event_date="not-a-date", title="Ignored row"),
        ]
    )

    result = get_macro_calendar_cluster(
        market_date=date(2026, 4, 21),
        existing={"legacy_flag": True},
        storage=storage,
    )

    assert result["legacy_flag"] is True
    assert result["freshness"] == "fresh"
    assert result["reason"] == "ok"
    assert result["upcoming_event_count"] == 3
    assert result["next_event_date"] == "2026-04-21"
    assert [event["event_date"] for event in result["upcoming_events"]] == [
        "2026-04-21",
        "2026-04-22",
        "2026-04-25",
    ]


def test_get_macro_calendar_cluster_marks_stale_table_from_latest_valid_row_even_with_invalid_rows() -> None:
    storage = _FakeStorage(
        [
            _event_row(event_id=1, event_date="bad-date", title="Ignored row"),
            _event_row(event_id=2, event_date="2026-04-18", title="Old row"),
        ]
    )

    result = get_macro_calendar_cluster(
        market_date=date(2026, 4, 21),
        storage=storage,
    )

    assert result == {
        "freshness": "stale",
        "reason": "stale_table",
        "upcoming_event_count": 0,
        "next_event_date": None,
    }


def test_build_macro_calendar_cluster_marks_no_future_rows_when_table_is_empty() -> None:
    result = build_macro_calendar_cluster(
        market_date=date(2026, 4, 21),
        latest_event_date=None,
        upcoming_events=[],
        existing=None,
    )

    assert result == {
        "freshness": "missing",
        "reason": "no_future_rows",
        "upcoming_event_count": 0,
        "next_event_date": None,
    }


def test_build_macro_calendar_cluster_marks_ok_and_reports_next_event_date() -> None:
    upcoming_events = [
        _event(event_id=1, event_date="2026-04-22", title="CPI"),
        _event(event_id=2, event_date="2026-04-25", title="GDP"),
    ]

    result = build_macro_calendar_cluster(
        market_date=date(2026, 4, 21),
        latest_event_date=date(2026, 4, 25),
        upcoming_events=upcoming_events,
        existing={"upcoming_events": [{"title": "old"}], "legacy_flag": True},
    )

    assert result["freshness"] == "fresh"
    assert result["reason"] == "ok"
    assert result["upcoming_event_count"] == 2
    assert result["next_event_date"] == "2026-04-22"
    assert result["legacy_flag"] is True
    assert result["upcoming_events"] == [event.model_dump() for event in upcoming_events]


def test_get_upcoming_events_uses_explicit_start_date(monkeypatch) -> None:
    captured: dict[str, object] = {}
    expected = [_event(event_id=3, event_date="2026-04-23", title="PCE")]

    def fake_get_market_events(*, start_date: date, end_date: date, limit: int):
        captured["start_date"] = start_date
        captured["end_date"] = end_date
        captured["limit"] = limit
        return MarketEventsResponse(
            events=expected,
            total=len(expected),
            start_date=str(start_date),
            end_date=str(end_date),
        )

    monkeypatch.setattr("app.services.market_events_service.get_market_events", fake_get_market_events)

    result = get_upcoming_events(days=14, start_date=date(2026, 4, 21))

    assert captured == {
        "start_date": date(2026, 4, 21),
        "end_date": date(2026, 5, 5),
        "limit": 50,
    }
    assert result == expected


def test_get_macro_calendar_cluster_respects_weekend_and_holiday_market_date_boundaries() -> None:
    boundary_cases = [
        (
            date(2026, 7, 4),
            [
                _event_row(event_id=1, event_date="2026-07-03", title="Observed holiday eve"),
                _event_row(event_id=2, event_date="2026-07-06", title="Next trading week"),
            ],
            "2026-07-06",
        ),
        (
            date(2026, 7, 3),
            [
                _event_row(event_id=3, event_date="2026-07-02", title="Pre-holiday table row"),
                _event_row(event_id=4, event_date="2026-07-06", title="Post-holiday row"),
            ],
            "2026-07-06",
        ),
    ]

    for market_date, rows, expected_next_date in boundary_cases:
        result = get_macro_calendar_cluster(
            market_date=market_date,
            storage=_FakeStorage(rows),
        )

        assert result["freshness"] == "fresh"
        assert result["reason"] == "ok"
        assert result["next_event_date"] == expected_next_date
        assert result["upcoming_event_count"] == len(result["upcoming_events"])
