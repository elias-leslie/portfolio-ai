"""Tests for YFinance news adapter."""

from __future__ import annotations

import datetime as dt
from typing import Any

import polars as pl
import pytest

from app.sources.yfinance_fetchers import _to_yf_symbol
from app.sources.yfinance_source import YFinanceSource


def test_to_yf_symbol_translates_dotted_share_classes() -> None:
    """S&P 500 canonical form keeps dots (``BRK.B``); yfinance API needs
    the dashed form. Storage keeps the dotted canonical."""
    assert _to_yf_symbol("BRK.B") == "BRK-B"
    assert _to_yf_symbol("BF.B") == "BF-B"


def test_to_yf_symbol_passes_through_non_share_class_symbols() -> None:
    """Only the share-class dot is rewritten. Exchange-suffix dots
    (e.g. ``DX-Y.NYB`` — yfinance's actual canonical for ICE Dollar Index)
    and index symbols pass through verbatim."""
    assert _to_yf_symbol("AAPL") == "AAPL"
    assert _to_yf_symbol("^GSPC") == "^GSPC"
    assert _to_yf_symbol("DX-Y.NYB") == "DX-Y.NYB"


def test_yfinance_reference_fetch_closes_http_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reference fetches should not leave yfinance curl sessions open."""
    from app.sources import yfinance_fetchers

    sessions: list[Any] = []

    class DummySession:
        closed = False

        def close(self) -> None:
            self.closed = True

    class DummyTicker:
        def __init__(self, symbol: str, *, session: Any) -> None:
            assert session is sessions[-1]
            self.symbol = symbol
            self.info = {"regularMarketPrice": 123.45}

    def session_factory(**_: Any) -> DummySession:
        session = DummySession()
        sessions.append(session)
        return session

    monkeypatch.setattr(yfinance_fetchers.curl_requests, "Session", session_factory)
    monkeypatch.setattr(yfinance_fetchers.yf, "Ticker", DummyTicker)
    monkeypatch.setattr(
        yfinance_fetchers,
        "build_reference_payload",
        lambda symbol, info: {"symbol": symbol, "price": info["regularMarketPrice"]},
    )

    df = yfinance_fetchers.fetch_reference_payload(["AAPL"], dt.date(2026, 1, 2))

    assert df is not None
    assert df["symbol"].to_list() == ["AAPL"]
    assert sessions and sessions[0].closed


@pytest.fixture()
def mock_ticker(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Patch yfinance.Ticker for news calls and return accessor."""

    class DummyTicker:
        def __init__(self, symbol: str, **_: Any) -> None:
            self.symbol = symbol
            self._news: list[dict[str, Any]] = []

        def get_news(self) -> list[dict[str, Any]]:
            return self._news

    dummy_instances: dict[str, DummyTicker] = {}

    def ticker_factory(symbol: str, **kwargs: Any) -> DummyTicker:
        if symbol not in dummy_instances:
            dummy_instances[symbol] = DummyTicker(symbol, **kwargs)
        return dummy_instances[symbol]

    import yfinance as _yf

    monkeypatch.setattr(_yf, "Ticker", ticker_factory)

    def get_instance(symbol: str) -> DummyTicker:
        return ticker_factory(symbol)

    return get_instance


def test_yfinance_fetch_news_payload_ticker(mock_ticker: Any) -> None:
    source = YFinanceSource()
    dummy = mock_ticker("AAPL")
    published_ts = int(dt.datetime(2025, 11, 6, 14, 0, tzinfo=dt.UTC).timestamp())
    dummy._news = [
        {
            "title": "Apple unveils new product",
            "link": "https://example.com/aapl-news",
            "publisher": "ExampleWire",
            "providerPublishTime": published_ts,
            "summary": "Details about the product.",
        }
    ]

    start = dt.datetime(2025, 11, 6, 13, 0, tzinfo=dt.UTC)
    end = dt.datetime(2025, 11, 6, 15, 0, tzinfo=dt.UTC)

    df = source.fetch_news_payload(["AAPL"], start, end)

    assert df is not None
    assert isinstance(df, pl.DataFrame)
    assert len(df) == 1
    row = df.to_dicts()[0]
    assert row["symbol"] == "AAPL"
    assert row["news_source_name"] == "ExampleWire"
    assert row["source"] == "yfinance"
    assert row["headline"] == "Apple unveils new product"


def test_yfinance_fetch_news_payload_market(mock_ticker: Any) -> None:
    source = YFinanceSource()
    dummy = mock_ticker(source.MARKET_SYMBOL)
    published_ts = int(dt.datetime(2025, 11, 6, 10, 0, tzinfo=dt.UTC).timestamp())
    dummy._news = [
        {
            "title": "Market wrap",
            "link": "https://example.com/market-news",
            "publisher": "MarketWatch",
            "providerPublishTime": published_ts,
        }
    ]

    start = dt.datetime(2025, 11, 6, 9, 0, tzinfo=dt.UTC)
    end = dt.datetime(2025, 11, 6, 12, 0, tzinfo=dt.UTC)

    df = source.fetch_news_payload(["__MARKET__"], start, end)
    assert df is not None
    assert df["symbol"][0] == "__MARKET__"


def test_yfinance_fetch_news_payload_filters_time(mock_ticker: Any) -> None:
    source = YFinanceSource()
    dummy = mock_ticker("MSFT")
    early_ts = int(dt.datetime(2025, 11, 5, 0, 0, tzinfo=dt.UTC).timestamp())
    late_ts = int(dt.datetime(2025, 11, 7, 0, 0, tzinfo=dt.UTC).timestamp())
    dummy._news = [
        {"title": "Old", "link": "#", "publisher": "Foo", "providerPublishTime": early_ts},
        {"title": "New", "link": "#", "publisher": "Foo", "providerPublishTime": late_ts},
    ]

    start = dt.datetime(2025, 11, 6, 0, 0, tzinfo=dt.UTC)
    end = dt.datetime(2025, 11, 6, 23, 59, tzinfo=dt.UTC)

    df = source.fetch_news_payload(["MSFT"], start, end)
    assert df is None  # both outside window
