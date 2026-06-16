from __future__ import annotations

import json
from datetime import date
from typing import Any

from app.workflows import catalysts


class _Response:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.content = ("\ufeff" + json.dumps(payload)).encode()

    def raise_for_status(self) -> None:
        return None


class _Connection:
    def __init__(self) -> None:
        self.params: list[list[Any]] = []
        self.committed = False

    def execute(self, _query: str, params: list[Any]) -> None:
        self.params.append(params)

    def commit(self) -> None:
        self.committed = True

    def __enter__(self) -> _Connection:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


class _Storage:
    def __init__(self) -> None:
        self.conn = _Connection()

    def connection(self) -> _Connection:
        return self.conn


def test_refresh_fomc_meetings_accepts_fed_json_with_utf8_bom(monkeypatch) -> None:
    storage = _Storage()
    payload = {
        "events": [
            {
                "title": "FOMC Meeting",
                "month": "2026-06",
                "days": "17",
                "type": "FOMC",
            },
        ],
    }

    monkeypatch.setattr(catalysts.requests, "get", lambda *_args, **_kwargs: _Response(payload))

    inserted = catalysts._refresh_fomc_meetings(storage, date(2026, 6, 1))

    assert inserted == 1
    assert storage.conn.committed is True
    assert storage.conn.params == [[date(2026, 6, 17), "regular", "federalreserve.gov"]]


def test_parse_calendar_entry_date_uses_last_day_from_fed_days_range() -> None:
    assert catalysts._parse_calendar_entry_date({"month": "2026-06", "days": "16-17"}) == date(
        2026, 6, 17
    )
