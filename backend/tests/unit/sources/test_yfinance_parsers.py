"""Tests for yfinance payload parsers — focus on session-aware price extraction."""

from __future__ import annotations

from app.sources.yfinance_parsers import (
    build_reference_payload,
    extract_price_from_info,
)


def test_extract_price_picks_post_market_when_freshest() -> None:
    info = {
        "regularMarketPrice": 100.0,
        "regularMarketTime": 1700000000,
        "preMarketPrice": 99.0,
        "preMarketTime": 1699990000,
        "postMarketPrice": 101.5,
        "postMarketTime": 1700010000,
    }
    price, session = extract_price_from_info(info)
    assert price == 101.5
    assert session == "post_market"


def test_extract_price_picks_pre_market_when_freshest() -> None:
    info = {
        "regularMarketPrice": 100.0,
        "regularMarketTime": 1699900000,
        "preMarketPrice": 99.5,
        "preMarketTime": 1700000000,
        "postMarketPrice": 0,
        "postMarketTime": 0,
    }
    price, session = extract_price_from_info(info)
    assert price == 99.5
    assert session == "pre_market"


def test_extract_price_picks_regular_when_no_extended_quotes() -> None:
    info = {
        "regularMarketPrice": 100.0,
        "regularMarketTime": 1700000000,
    }
    price, session = extract_price_from_info(info)
    assert price == 100.0
    assert session == "regular"


def test_extract_price_falls_back_to_current_then_previous() -> None:
    # No timestamped session quotes — fall back to currentPrice
    info_current: dict[str, object] = {"currentPrice": 50.0}
    price, session = extract_price_from_info(info_current)
    assert price == 50.0
    assert session == "current_price"

    # Only previousClose available
    info_prev: dict[str, object] = {"previousClose": 42.0}
    price, session = extract_price_from_info(info_prev)
    assert price == 42.0
    assert session == "previous_close"

    # Nothing available
    price, session = extract_price_from_info({})
    assert price is None
    assert session is None


def test_build_reference_payload_threads_session_label() -> None:
    info: dict[str, object] = {
        "regularMarketPrice": 100.0,
        "regularMarketTime": 1700000000,
        "postMarketPrice": 101.5,
        "postMarketTime": 1700010000,
    }
    payload = build_reference_payload("ABC", info)
    assert payload["price"] == 101.5
    assert payload["price_session"] == "post_market"
