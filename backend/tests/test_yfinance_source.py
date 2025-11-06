"""Tests for YFinance news adapter."""

from __future__ import annotations

import datetime as dt

import polars as pl
import pytest

from app.sources.yfinance_source import YFinanceSource


@pytest.fixture()
def mock_ticker(monkeypatch):
    """Patch yfinance.Ticker for news calls and return accessor."""

    class DummyTicker:
        def __init__(self, symbol: str) -> None:
            self.symbol = symbol
            self._news: list[dict] = []

        def get_news(self):
            return self._news

    dummy_instances: dict[str, DummyTicker] = {}

    def ticker_factory(symbol: str) -> DummyTicker:
        if symbol not in dummy_instances:
            dummy_instances[symbol] = DummyTicker(symbol)
        return dummy_instances[symbol]

    monkeypatch.setattr("app.sources.yfinance_source.yf.Ticker", ticker_factory)

    def get_instance(symbol: str) -> DummyTicker:
        return ticker_factory(symbol)

    return get_instance


def test_yfinance_fetch_news_payload_ticker(mock_ticker):
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
    assert row["ticker"] == "AAPL"
    assert row["news_source_name"] == "ExampleWire"
    assert row["source"] == "yfinance"
    assert row["headline"] == "Apple unveils new product"


def test_yfinance_fetch_news_payload_market(mock_ticker):
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
    assert df["ticker"][0] == "__MARKET__"


def test_yfinance_fetch_news_payload_filters_time(mock_ticker):
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
