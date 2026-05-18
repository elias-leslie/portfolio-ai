"""Tests for the per-symbol payload fetchers."""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest

from app.agents.committee import payloads

# ---------- in-memory connection fake ----------


class _FakeCursor:
    def __init__(self, rows_by_table: dict[str, Any]):
        self._rows_by_table = rows_by_table
        self._next: Any = None

    def execute(self, sql: str, _params: Any = None) -> _FakeCursor:
        sql_lower = sql.lower()
        if "from technical_indicators" in sql_lower:
            self._next = self._rows_by_table.get("technical_indicators")
        elif "from day_bars" in sql_lower:
            self._next = self._rows_by_table.get("day_bars")
        elif "from valuation_metrics" in sql_lower:
            self._next = self._rows_by_table.get("valuation_metrics")
        elif "from cash_flow_metrics" in sql_lower:
            self._next = self._rows_by_table.get("cash_flow_metrics")
        elif "from financial_health_scores" in sql_lower:
            self._next = self._rows_by_table.get("financial_health_scores")
        elif "from symbols" in sql_lower:
            # Disambiguate the sector-only lookup used by the portfolio
            # fetcher from the company-meta select in the fundamentals
            # fetcher: the former selects only `sector`.
            if "select sector" in sql_lower and "company_name" not in sql_lower:
                self._next = self._rows_by_table.get("symbols_sector_only")
            else:
                self._next = self._rows_by_table.get("symbols")
        elif "from earnings_surprises" in sql_lower:
            self._next = self._rows_by_table.get("earnings_surprises")
        elif "from watchlist_snapshots" in sql_lower:
            self._next = self._rows_by_table.get("watchlist_snapshots")
        elif "from news_cache" in sql_lower:
            self._next = self._rows_by_table.get("news_cache")
        elif "from portfolio_positions" in sql_lower:
            self._next = self._rows_by_table.get("portfolio_positions")
        elif "from portfolio_accounts" in sql_lower:
            self._next = self._rows_by_table.get("portfolio_accounts")
        else:
            raise AssertionError(f"unexpected query: {sql}")
        return self

    def fetchone(self) -> Any:
        rows = self._next
        if isinstance(rows, list):
            return rows[0] if rows else None
        return rows

    def fetchall(self) -> Any:
        rows = self._next
        if rows is None:
            return []
        if isinstance(rows, list):
            return rows
        return [rows]


class _FakeConn:
    def __init__(self, rows_by_table: dict[str, Any]):
        self._rows = rows_by_table

    def execute(self, sql: str, params: Any = None) -> _FakeCursor:
        cur = _FakeCursor(self._rows)
        return cur.execute(sql, params)


class _FakeConnCtx:
    def __init__(self, conn: _FakeConn):
        self._conn = conn

    def __enter__(self) -> _FakeConn:
        return self._conn

    def __exit__(self, *_exc: Any) -> bool:
        return False


class _FakeConnectionManager:
    def __init__(self, rows_by_table: dict[str, Any]):
        self._rows = rows_by_table

    def connection(self) -> _FakeConnCtx:
        return _FakeConnCtx(_FakeConn(self._rows))


def _install_fake_cm(
    monkeypatch: pytest.MonkeyPatch, rows_by_table: dict[str, Any]
) -> None:
    cm = _FakeConnectionManager(rows_by_table)
    monkeypatch.setattr(payloads, "get_connection_manager", lambda: cm)


# ---------- fixtures ----------


_LATEST_DATE = dt.date(2026, 5, 18)
_CALCULATED_AT = dt.datetime(2026, 5, 18, 21, 30, tzinfo=dt.UTC)


def _make_indicator_row(
    *,
    date: dt.date,
    rsi_14: float = 60.0,
    macd: float = 1.5,
    sma_50: float = 200.0,
    sma_200: float = 180.0,
    atr_14: float = 4.2,
    bb_lower: float = 190.0,
    bb_upper: float = 210.0,
) -> tuple[Any, ...]:
    # Order must match payloads._TECHNICAL_COLUMNS exactly.
    return (
        date,
        _CALCULATED_AT,
        rsi_14,
        macd,
        macd - 0.2,  # macd_signal
        0.3,  # macd_histogram
        bb_upper,
        (bb_upper + bb_lower) / 2,
        bb_lower,
        201.0,  # sma_5
        199.0,  # sma_20
        sma_50,
        sma_200,
        198.0,  # ema_20
        197.0,  # ema_50
        185.0,  # ema_200
        atr_14,
        80.0,  # stoch_k
        78.0,  # stoch_d
    )


# ---------- tests ----------


def test_fetch_technical_indicators_returns_all_required_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The technical analyst prompt cites these by name; all must be present."""
    rows = [
        _make_indicator_row(date=_LATEST_DATE, sma_50=200.0, sma_200=180.0),
        _make_indicator_row(date=dt.date(2026, 5, 11), sma_50=190.0, sma_200=175.0),
    ]
    _install_fake_cm(
        monkeypatch,
        {"technical_indicators": rows, "day_bars": (205.0,)},
    )

    payload = payloads.fetch_technical_indicators("NVDA")
    assert payload is not None

    required = {
        "date",
        "calculated_at",
        "rsi_14",
        "macd",
        "macd_signal",
        "macd_histogram",
        "bb_upper",
        "bb_middle",
        "bb_lower",
        "sma_5",
        "sma_20",
        "sma_50",
        "sma_200",
        "ema_20",
        "ema_50",
        "ema_200",
        "atr_14",
        "stoch_k",
        "stoch_d",
        "latest_close",
        "ma_slope_50_pct",
        "ma_slope_200_pct",
        "price_vs_sma_50_pct",
        "price_vs_sma_200_pct",
        "rsi_zone",
        "bb_pct_b",
    }
    assert required.issubset(payload.keys()), required - payload.keys()


def test_fetch_technical_indicators_derives_slope_and_zone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [
        _make_indicator_row(date=_LATEST_DATE, sma_50=210.0, sma_200=180.0, rsi_14=75.0),
        _make_indicator_row(date=dt.date(2026, 5, 11), sma_50=200.0, sma_200=170.0),
    ]
    _install_fake_cm(
        monkeypatch,
        {"technical_indicators": rows, "day_bars": (220.0,)},
    )

    payload = payloads.fetch_technical_indicators("NVDA")
    assert payload is not None
    assert payload["ma_slope_50_pct"] == pytest.approx(5.0)
    assert payload["ma_slope_200_pct"] == pytest.approx((10 / 170) * 100)
    assert payload["price_vs_sma_50_pct"] == pytest.approx((10 / 210) * 100)
    assert payload["rsi_zone"] == "overbought"
    assert payload["bb_pct_b"] == pytest.approx(1.5)


def test_fetch_technical_indicators_returns_none_when_no_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_cm(monkeypatch, {"technical_indicators": [], "day_bars": None})
    assert payloads.fetch_technical_indicators("NVDA") is None


def test_fetch_technical_indicators_handles_missing_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [_make_indicator_row(date=_LATEST_DATE)]
    _install_fake_cm(
        monkeypatch,
        {"technical_indicators": rows, "day_bars": None},
    )
    payload = payloads.fetch_technical_indicators("NVDA")
    assert payload is not None
    assert payload["latest_close"] is None
    assert payload["price_vs_sma_50_pct"] is None
    assert payload["bb_pct_b"] is None


def test_fetch_technical_indicators_rsi_zone_oversold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [_make_indicator_row(date=_LATEST_DATE, rsi_14=22.0)]
    _install_fake_cm(
        monkeypatch,
        {"technical_indicators": rows, "day_bars": (180.0,)},
    )
    payload = payloads.fetch_technical_indicators("NVDA")
    assert payload is not None
    assert payload["rsi_zone"] == "oversold"


def test_fetch_technical_indicators_returns_none_on_query_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _ExplodingConn:
        def execute(self, *_a: Any, **_k: Any) -> Any:
            raise RuntimeError("db down")

    class _ExplodingCtx:
        def __enter__(self) -> _ExplodingConn:
            return _ExplodingConn()

        def __exit__(self, *_e: Any) -> bool:
            return False

    class _ExplodingCM:
        def connection(self) -> _ExplodingCtx:
            return _ExplodingCtx()

    exploder = _ExplodingCM()
    monkeypatch.setattr(payloads, "get_connection_manager", lambda: exploder)
    assert payloads.fetch_technical_indicators("NVDA") is None


def test_fetch_technical_indicators_empty_symbol_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(payloads, "get_connection_manager", lambda: None)
    assert payloads.fetch_technical_indicators("") is None
    assert payloads.fetch_technical_indicators("   ") is None


# ---------- fundamentals ----------


def _fundamentals_rows() -> dict[str, Any]:
    return {
        "valuation_metrics": (
            dt.datetime(2026, 5, 17, tzinfo=dt.UTC),  # as_of_date
            46.08,  # pe_ratio_trailing
            19.71,  # pe_ratio_forward
            25.27,  # ps_ratio
            34.81,  # pb_ratio
            0.75,  # peg_ratio
            0.02,  # dividend_yield
            0.0082,  # payout_ratio
        ),
        "cash_flow_metrics": (
            dt.date(2026, 5, 17),
            102_718_000_000,
            96_676_000_000,
            -6_042_000_000,
            0.0177,
            0.4757,
            3.9915,
            0.8555,
        ),
        "financial_health_scores": (
            dt.datetime(2026, 5, 17, tzinfo=dt.UTC),
            4,
            {"ocf_positive": 1, "roa_positive": 1},
            70.98,
            "safe",
        ),
        "symbols": ("NVIDIA Corp", "Technology", "Semiconductors", "NASDAQ"),
        "earnings_surprises": [
            (
                dt.date(2026, 2, 26),
                "Q4 FY25",
                4.50,
                5.20,
                15.6,
                "beat",
                32_000_000_000,
                35_100_000_000,
            )
        ],
        "watchlist_snapshots": (
            dt.datetime(2026, 5, 18, 12, tzinfo=dt.UTC),
            72.5,
            81.0,
            "strong",
            dt.date(2026, 5, 28),
            10,
            {"fundamental": {"summary": "best in class"}},
        ),
    }


def test_fetch_fundamental_snapshot_assembles_all_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_cm(monkeypatch, _fundamentals_rows())
    payload = payloads.fetch_fundamental_snapshot("NVDA")
    assert payload is not None
    # Every source surfaces under its named section.
    assert payload["company"]["sector"] == "Technology"
    assert payload["valuation"]["pe_ratio_trailing"] == 46.08
    assert payload["valuation"]["pe_ratio_forward"] == 19.71
    assert payload["cash_flow"]["free_cash_flow"] == 96_676_000_000
    assert payload["cash_flow"]["fcf_yield"] == 0.0177
    assert payload["health"]["f_score"] == 4
    assert payload["health"]["z_score_zone"] == "safe"
    assert payload["earnings_surprise_history"][0]["surprise_pct"] == 15.6
    assert payload["watchlist"]["fundamental_score"] == 72.5


def test_fetch_fundamental_snapshot_returns_none_when_all_sources_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_cm(
        monkeypatch,
        {
            "valuation_metrics": None,
            "cash_flow_metrics": None,
            "financial_health_scores": None,
            "symbols": None,
            "earnings_surprises": [],
            "watchlist_snapshots": None,
        },
    )
    assert payloads.fetch_fundamental_snapshot("NVDA") is None


def test_fetch_fundamental_snapshot_partial_coverage_still_ships(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = _fundamentals_rows()
    # Only valuation_metrics + symbols populated; rest empty.
    rows["cash_flow_metrics"] = None
    rows["financial_health_scores"] = None
    rows["earnings_surprises"] = []
    rows["watchlist_snapshots"] = None
    _install_fake_cm(monkeypatch, rows)
    payload = payloads.fetch_fundamental_snapshot("NVDA")
    assert payload is not None
    assert "valuation" in payload
    assert "company" in payload
    assert "cash_flow" not in payload
    assert "health" not in payload


# ---------- news ----------


def _news_row(
    *,
    headline: str,
    summary: str = "body",
    published_at: dt.datetime,
    sentiment_score: float = 0.3,
) -> tuple[Any, ...]:
    return (
        headline,
        summary,
        "https://example.com/x",
        "Bloomberg",
        published_at,
        sentiment_score,
        "positive",
        0.9,
        True,
        "impact summary",
        "actionable insight",
    )


def test_fetch_news_sentiment_returns_freshness_ordered_articles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = dt.datetime(2026, 5, 18, 14, tzinfo=dt.UTC)
    rows = [
        _news_row(headline="latest", published_at=base, sentiment_score=0.5),
        _news_row(
            headline="older",
            published_at=base - dt.timedelta(hours=12),
            sentiment_score=-0.2,
        ),
    ]
    _install_fake_cm(monkeypatch, {"news_cache": rows})
    payload = payloads.fetch_news_sentiment("NVDA")
    assert payload is not None
    assert payload["article_count"] == 2
    assert payload["articles"][0]["headline"] == "latest"
    assert payload["articles"][0]["summary"] == "body"
    # avg of 0.5 and -0.2 = 0.15
    assert payload["avg_sentiment_score"] == pytest.approx(0.15)


def test_fetch_news_sentiment_returns_none_when_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_cm(monkeypatch, {"news_cache": []})
    assert payloads.fetch_news_sentiment("NVDA") is None


# ---------- portfolio ----------


def _portfolio_rows(
    *,
    nvda_value: float = 80_000,
    aapl_value: float = 20_000,
    cash: float = 100_000,
) -> dict[str, Any]:
    # Row layout: (symbol, shares, avg_cost, price, value, sector)
    positions = [
        ("NVDA", 100.0, 600.0, 800.0, nvda_value, "Technology"),
        ("AAPL", 100.0, 150.0, 200.0, aapl_value, "Technology"),
        ("XOM", 200.0, 50.0, 60.0, 12_000.0, "Energy"),
    ]
    return {
        "portfolio_positions": positions,
        "portfolio_accounts": (cash,),
        "symbols": ("NVIDIA Corp", "Technology", "Semiconductors", "NASDAQ"),
    }


def test_fetch_portfolio_context_full_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_cm(monkeypatch, _portfolio_rows())
    payload = payloads.fetch_portfolio_context("NVDA")
    assert payload is not None
    assert payload["held"] is True
    assert payload["position_in_symbol"]["shares"] == 100.0
    assert payload["target_sector"] == "Technology"
    # NVDA(80k) + AAPL(20k) + XOM(12k) + cash(100k) = 212k → tech = 100/212
    assert payload["sector_exposure_pct"] == pytest.approx(
        (100_000 / 212_000) * 100.0, abs=0.1
    )
    assert payload["sector_breakdown"]["Energy"] == pytest.approx(
        (12_000 / 212_000) * 100.0, abs=0.1
    )
    assert payload["top_5_positions"][0]["symbol"] == "NVDA"
    assert payload["cash_pct"] == pytest.approx(
        (100_000 / 212_000) * 100.0, abs=0.1
    )
    assert payload["num_holdings"] == 3


def test_fetch_portfolio_context_no_holdings_returns_none_held(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_cm(
        monkeypatch,
        {
            "portfolio_positions": [],
            "portfolio_accounts": (50_000.0,),
            # Symbol exists in catalog even though we don't hold it. The
            # portfolio fetcher does a sector-only lookup.
            "symbols_sector_only": ("Technology",),
        },
    )
    payload = payloads.fetch_portfolio_context("MSFT")
    assert payload is not None
    assert payload["held"] is False
    # No holdings → sector_breakdown empty / None, but target_sector still
    # surfaces from the catalog lookup so the trader can size against it.
    assert payload["target_sector"] == "Technology"
    assert payload["num_holdings"] == 0
