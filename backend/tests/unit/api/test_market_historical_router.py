"""Unit tests for historical market API helpers."""

from __future__ import annotations

from importlib import import_module
from types import SimpleNamespace

historical_router = import_module("app.api.market.historical_router")


def test_fear_greed_history_appends_live_proxy_when_daily_close_lags(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        historical_router,
        "fetch_core_market_data",
        lambda: SimpleNamespace(current_timestamp="2026-05-04T20:09:55+00:00"),
    )
    monkeypatch.setattr(
        historical_router,
        "build_intelligence_response_data",
        lambda *_: {
            "enriched_indicators": {
                "sp500": SimpleNamespace(value=7200.75, change_pct=-0.41),
                "vix": SimpleNamespace(value=18.33, change_pct=7.89),
                "tnx": SimpleNamespace(value=4.446, change_pct=1.55),
                "dxy": SimpleNamespace(value=98.43, change_pct=0.2),
                "putcall": SimpleNamespace(value=1.19),
            },
            "leading_sectors": [SimpleNamespace(change_pct=0.95)],
            "neutral_sectors": [SimpleNamespace(change_pct=-0.1)],
            "lagging_sectors": [SimpleNamespace(change_pct=-0.4)],
        },
    )

    dates, scores, labels, put_call_ratios, sources, latest_source, latest_as_of = (
        historical_router._append_live_mood_point(
            dates=["2026-05-01"],
            scores=[62.0],
            labels=["Greed"],
            put_call_ratios=[1.1891],
        )
    )

    assert dates == ["2026-05-01", "2026-05-04"]
    assert scores[-1] != 62.0
    assert labels[-1] == "Cautious"
    assert put_call_ratios[-1] == 1.19
    assert sources == ["daily_close", "live_proxy"]
    assert latest_source == "live_proxy"
    assert latest_as_of == "2026-05-04T20:09:55+00:00"


def test_current_quote_replaces_same_day_indicator_history_row() -> None:
    quote = SimpleNamespace(cached_at=historical_router.datetime(2026, 5, 22, 22, 7), price=16.7)

    rows = historical_router._append_current_quote_row(
        [(historical_router.date(2026, 5, 21), 16.76), (historical_router.date(2026, 5, 22), 16.9)],
        quote,
    )

    assert rows == [(historical_router.date(2026, 5, 21), 16.76), (historical_router.date(2026, 5, 22), 16.7)]
