"""Tests for yfinance payload parsers — focus on session-aware price extraction."""

from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from app.sources.yfinance_parsers import (
    build_reference_payload,
    extract_price_from_info,
    parse_quarterly_fundamentals,
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
    price, session, quote_epoch = extract_price_from_info(info)
    assert price == 101.5
    assert session == "post_market"
    assert quote_epoch == 1700010000


def test_extract_price_picks_pre_market_when_freshest() -> None:
    info = {
        "regularMarketPrice": 100.0,
        "regularMarketTime": 1699900000,
        "preMarketPrice": 99.5,
        "preMarketTime": 1700000000,
        "postMarketPrice": 0,
        "postMarketTime": 0,
    }
    price, session, quote_epoch = extract_price_from_info(info)
    assert price == 99.5
    assert session == "pre_market"
    assert quote_epoch == 1700000000


def test_extract_price_picks_regular_when_no_extended_quotes() -> None:
    info = {
        "regularMarketPrice": 100.0,
        "regularMarketTime": 1700000000,
    }
    price, session, quote_epoch = extract_price_from_info(info)
    assert price == 100.0
    assert session == "regular"
    assert quote_epoch == 1700000000


def test_extract_price_falls_back_to_current_then_previous() -> None:
    # No timestamped session quotes — fall back to currentPrice (no vendor timestamp)
    info_current: dict[str, object] = {"currentPrice": 50.0}
    price, session, quote_epoch = extract_price_from_info(info_current)
    assert price == 50.0
    assert session == "current_price"
    assert quote_epoch is None

    # Only previousClose available — carried-forward close carries no live timestamp
    info_prev: dict[str, object] = {"previousClose": 42.0}
    price, session, quote_epoch = extract_price_from_info(info_prev)
    assert price == 42.0
    assert session == "previous_close"
    assert quote_epoch is None

    # Nothing available
    price, session, quote_epoch = extract_price_from_info({})
    assert price is None
    assert session is None
    assert quote_epoch is None


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
    # Vendor quote timestamp (regularMarketTime/postMarketTime) threaded through as ISO
    assert payload["quote_time"] == dt.datetime.fromtimestamp(1700010000, tz=dt.UTC).isoformat()


# ---------- parse_quarterly_fundamentals ----------


def _quarterly_frame(rows: dict[str, list[float | None]]) -> pd.DataFrame:
    """Build a yfinance-shaped quarterly frame with newest column first.

    yfinance returns one column per period (period-end date), one row per
    line item, with the newest period in column 0.
    """
    periods = [
        pd.Timestamp(dt.date(2026, 3, 31)),
        pd.Timestamp(dt.date(2025, 12, 31)),
        pd.Timestamp(dt.date(2025, 9, 30)),
        pd.Timestamp(dt.date(2025, 6, 30)),
        pd.Timestamp(dt.date(2025, 3, 31)),
        pd.Timestamp(dt.date(2024, 12, 31)),
        pd.Timestamp(dt.date(2024, 9, 30)),
        pd.Timestamp(dt.date(2024, 6, 30)),
    ]
    return pd.DataFrame(rows, index=periods).T  # rows are labels, cols are dates


def test_parse_quarterly_fundamentals_computes_margins_growth_and_leverage() -> None:
    income = _quarterly_frame({
        "Total Revenue": [1000, 950, 900, 850, 800, 750, 700, 650],
        "Gross Profit": [600, 570, 540, 510, 480, 450, 420, 390],
        "Operating Income": [300, 285, 270, 255, 240, 225, 210, 195],
        "Net Income": [200, 190, 180, 170, 160, 150, 140, 130],
        "EBIT": [310, 295, 280, 265, 250, 235, 220, 205],
        "EBITDA": [400, 380, 360, 340, 320, 300, 280, 260],
        "Tax Provision": [60, 57, 54, 51, 48, 45, 42, 39],
        "Diluted EPS": [2.0, 1.9, 1.8, 1.7, 1.6, 1.5, 1.4, 1.3],
    })
    balance = _quarterly_frame({
        "Total Debt": [500, 510, 520, 530, 540, 550, 560, 570],
        "Stockholders Equity": [2000, 1950, 1900, 1850, 1800, 1750, 1700, 1650],
        "Accounts Receivable": [300, 290, 280, 270, 260, 250, 240, 230],
    })
    cashflow = _quarterly_frame({
        "Operating Cash Flow": [250, 240, 230, 220, 210, 200, 190, 180],
        "Free Cash Flow": [200, 190, 180, 170, 160, 150, 140, 130],
        "Capital Expenditure": [-50, -50, -50, -50, -50, -50, -50, -50],
    })
    info = {"marketCap": 5_000_000_000, "enterpriseToEbitda": 12.5, "returnOnEquity": 0.10}

    out = parse_quarterly_fundamentals(
        symbol="DEMO",
        quarterly_income=income,
        quarterly_balance=balance,
        quarterly_cashflow=cashflow,
        info=info,
    )

    assert out["symbol"] == "DEMO"
    # Margins from latest quarter
    assert out["gross_margin"] == pytest.approx(0.6)
    assert out["operating_margin"] == pytest.approx(0.3)
    assert out["net_margin"] == pytest.approx(0.2)
    # ROE from info wins over derived
    assert out["roe"] == pytest.approx(0.10)
    # D/E = 500/2000
    assert out["debt_to_equity"] == pytest.approx(0.25)
    # Market cap + EV/EBITDA pass through
    assert out["market_cap"] == pytest.approx(5_000_000_000)
    assert out["ev_ebitda"] == pytest.approx(12.5)
    # YoY growth = (1000 / 800) - 1 = 0.25
    assert out["revenue_growth_yoy"] == pytest.approx(0.25)
    # EPS YoY = (2.0 / 1.6) - 1 = 0.25
    assert out["eps_growth_yoy"] == pytest.approx(0.25)
    # 4-quarter slices, newest first
    assert out["revenue_4q"] == [1000, 950, 900, 850]
    assert out["operating_cash_flow_4q"] == [250, 240, 230, 220]
    # TTM revenue = sum of last 4
    assert out["revenue_ttm"] == pytest.approx(3700)


def test_parse_quarterly_fundamentals_handles_empty_frames() -> None:
    out = parse_quarterly_fundamentals(
        symbol="EMPTY",
        quarterly_income=pd.DataFrame(),
        quarterly_balance=pd.DataFrame(),
        quarterly_cashflow=pd.DataFrame(),
        info={},
    )
    assert out["symbol"] == "EMPTY"
    assert out["gross_margin"] is None
    assert out["debt_to_equity"] is None
    assert out["revenue_growth_yoy"] is None
    assert out["revenue_4q"] == []
    assert out["revenue_ttm"] is None


def test_parse_quarterly_fundamentals_falls_back_to_derived_roe_when_info_missing() -> None:
    income = _quarterly_frame({
        "Total Revenue": [1000, 900, 800, 700, 600, 500, 400, 300],
        "Net Income": [200, 180, 160, 140, 120, 100, 80, 60],
    })
    balance = _quarterly_frame({
        "Stockholders Equity": [2000] * 8,
    })
    out = parse_quarterly_fundamentals(
        symbol="DEMO",
        quarterly_income=income,
        quarterly_balance=balance,
        quarterly_cashflow=pd.DataFrame(),
        info={"marketCap": 1_000_000_000},  # no returnOnEquity
    )
    # Derived ROE = latest_net_income / latest_equity = 200 / 2000 = 0.10
    assert out["roe"] == pytest.approx(0.10)
