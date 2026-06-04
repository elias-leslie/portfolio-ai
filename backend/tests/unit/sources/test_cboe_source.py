"""Tests for the CBOE delayed-quote source adapter."""

from __future__ import annotations

import datetime as dt
import json
from unittest.mock import patch

from app.sources.cboe_source import CboeSource

_SAMPLE_DATA = {
    "symbol": "^VIX",
    "current_price": 15.4,
    "last_trade_time": "2026-06-04T16:15:01",
    "prev_day_close": 16.06,
    "bid": 15.39,
    "ask": 15.41,
    "bid_size": 10,
    "ask_size": 12,
}


def test_serves_vix_with_provenance() -> None:
    with patch("app.sources.cboe_source._fetch_quote", return_value=_SAMPLE_DATA):
        df = CboeSource().fetch_reference_payload(["^VIX"], dt.date(2026, 6, 4))
    assert df is not None
    row = df.to_dicts()[0]
    assert row["symbol"] == "^VIX"
    assert row["source"] == "cboe"
    payload = json.loads(row["payload"])
    assert payload["price"] == 15.4
    assert payload["price_session"] == "delayed"
    # CBOE serves last_trade_time as naive US/Eastern wall-clock; it must be
    # stamped ET so downstream age math is not thrown off by the UTC offset.
    assert payload["quote_time"] == "2026-06-04T16:15:01-04:00"


def test_falls_through_for_non_index_symbols() -> None:
    # CBOE owns only index symbols; everything else must defer to the next source.
    with patch("app.sources.cboe_source._fetch_quote") as fetch:
        df = CboeSource().fetch_reference_payload(["AAPL"], dt.date(2026, 6, 4))
    assert df is None
    fetch.assert_not_called()


def test_returns_none_when_feed_unavailable() -> None:
    with patch("app.sources.cboe_source._fetch_quote", return_value=None):
        df = CboeSource().fetch_reference_payload(["^VIX"], dt.date(2026, 6, 4))
    assert df is None


def test_rejects_nonpositive_price() -> None:
    bad = dict(_SAMPLE_DATA, current_price=0)
    with patch("app.sources.cboe_source._fetch_quote", return_value=bad):
        df = CboeSource().fetch_reference_payload(["^VIX"], dt.date(2026, 6, 4))
    assert df is None
