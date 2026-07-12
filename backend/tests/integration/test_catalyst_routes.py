"""Integration test for the F4 catalyst calendar router.

Drives the FastAPI app through a TestClient with the cache helpers
patched to return deterministic dates so the response shape can be
asserted without yfinance / Postgres reads. The rest of the route
layer (param parsing, kinds filter, response shaping, detail
projection) is exercised end-to-end.
"""

from __future__ import annotations

from collections.abc import Generator
from datetime import date, datetime, timedelta
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def stub_universe_and_dates(monkeypatch: pytest.MonkeyPatch) -> Generator[None]:
    """Stub CatalystCalendarService so the router test stays sealed.

    The integration value is in proving routing + shaping; the per-row
    math is covered by tests/services/test_catalyst_calendar_service.
    """
    from app.services.catalyst_calendar_service import CatalystCalendarService

    today = date.today()
    earnings = {
        "AAPL": datetime.combine(today + timedelta(days=8), datetime.min.time()),
        "MSFT": datetime.combine(today + timedelta(days=12), datetime.min.time()),
    }
    exdiv = {
        "AAPL": datetime.combine(today + timedelta(days=4), datetime.min.time())
    }
    fomc = [(today + timedelta(days=6), "press_conference", "federalreserve.gov")]

    def fake_universe(self: CatalystCalendarService, symbols: Any, *, include_watchlist: bool) -> list[str]:
        del self, include_watchlist
        if symbols is not None:
            return [s.upper() for s in symbols if s.strip()]
        return ["AAPL", "MSFT"]

    def fake_fomc(self: CatalystCalendarService, anchor: date, cutoff: date) -> list[Any]:
        del self
        from app.portfolio.contracts.catalysts import Catalyst

        rows = []
        for meeting_date, meeting_type, source in fomc:
            if anchor <= meeting_date <= cutoff:
                rows.append(
                    Catalyst(
                        symbol="",
                        kind="fomc",
                        date=meeting_date,
                        days_until=(meeting_date - anchor).days,
                        confirmed=True,
                        source=source,
                        time_of_day=meeting_type,
                    )
                )
        return rows

    def fake_earnings(_conn: Any, symbol: str, ttl_days: int = 30) -> datetime | None:
        del ttl_days
        return earnings.get(symbol)

    def fake_exdiv(_conn: Any, symbol: str, ttl_days: int = 30) -> datetime | None:
        del ttl_days
        return exdiv.get(symbol)

    monkeypatch.setattr(
        CatalystCalendarService, "_resolve_symbol_universe", fake_universe
    )
    monkeypatch.setattr(CatalystCalendarService, "_fomc_catalysts", fake_fomc)
    with (
        patch(
            "app.services.catalyst_calendar_service.fetch_earnings_date_cached",
            side_effect=fake_earnings,
        ),
        patch(
            "app.services.catalyst_calendar_service.fetch_ex_dividend_date_cached",
            side_effect=fake_exdiv,
        ),
    ):
        yield


def test_get_upcoming_default_payload_is_compact(
    client: TestClient, stub_universe_and_dates: None
) -> None:
    del stub_universe_and_dates
    response = client.get(
        "/api/catalysts/upcoming",
        params={"days": 14},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["schema_version"] == 1
    assert body["days"] == 14
    assert body["limit"] == 20
    assert body["include_watchlist"] is True
    assert sorted(body["kinds"]) == ["earnings", "ex_dividend", "fomc"]
    rows = body["catalysts"]
    # Compact projection — none of the detail fields leak in by default.
    for row in rows:
        assert set(row.keys()) == {
            "schema_version",
            "symbol",
            "kind",
            "date",
            "days_until",
        }
    # Sorted by date ascending; AAPL ex-div must come before AAPL earnings.
    dates = [row["date"] for row in rows]
    assert dates == sorted(dates)


def test_get_upcoming_detail_includes_extra_fields(
    client: TestClient, stub_universe_and_dates: None
) -> None:
    del stub_universe_and_dates
    response = client.get(
        "/api/catalysts/upcoming",
        params={"days": 14, "detail": "true"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    fomc_rows = [row for row in body["catalysts"] if row["kind"] == "fomc"]
    assert fomc_rows, "FOMC row should appear with detail=true"
    fomc_row = fomc_rows[0]
    assert fomc_row.get("source") == "federalreserve.gov"
    assert fomc_row.get("confirmed") is True


def test_get_upcoming_kinds_filter_drops_other_rows(
    client: TestClient, stub_universe_and_dates: None
) -> None:
    del stub_universe_and_dates
    response = client.get(
        "/api/catalysts/upcoming",
        params={"days": 14, "kinds": "fomc"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    kinds = {row["kind"] for row in body["catalysts"]}
    assert kinds == {"fomc"}


def test_get_upcoming_explicit_symbols_overrides_universe(
    client: TestClient, stub_universe_and_dates: None
) -> None:
    del stub_universe_and_dates
    response = client.get(
        "/api/catalysts/upcoming",
        params={"days": 14, "symbols": "aapl"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    earnings_or_exdiv = [
        row for row in body["catalysts"] if row["kind"] in ("earnings", "ex_dividend")
    ]
    assert all(row["symbol"] == "AAPL" for row in earnings_or_exdiv)
    assert any(row["kind"] == "ex_dividend" for row in earnings_or_exdiv)


def test_get_upcoming_rejects_invalid_days(client: TestClient) -> None:
    response = client.get("/api/catalysts/upcoming", params={"days": -1})
    assert response.status_code == 422
