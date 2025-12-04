"""Tests for Alpha Vantage source adapter."""

from __future__ import annotations

import datetime as dt
from unittest.mock import Mock, patch

import pytest

from app.sources.alphavantage_source import AlphaVantageClient, AlphaVantageSource
from app.sources.base import DatasetRequest


@pytest.fixture
def mock_av_client() -> Mock:
    client = Mock(spec=AlphaVantageClient)
    client.request_count = 0
    return client


@pytest.fixture
def av_source(mock_av_client: Mock) -> AlphaVantageSource:
    source = AlphaVantageSource.__new__(AlphaVantageSource)
    source.name = "alphavantage"
    source.priority = 30
    source.supports_day = True
    source.supports_reference = False
    source.supports_news = False
    source.client = mock_av_client
    return source


def test_alphavantage_source_initialization() -> None:
    with patch("app.sources.alphavantage_source.get_client") as mock_get_client:
        mock_client = Mock(spec=AlphaVantageClient)
        mock_get_client.return_value = mock_client
        source = AlphaVantageSource()
        assert source.name == "alphavantage"
        assert source.priority == 30


def test_alphavantage_fetch_day_bars_success(
    av_source: AlphaVantageSource, mock_av_client: Mock
) -> None:
    mock_response = {
        "Time Series (Daily)": {
            "2025-01-28": {
                "1. open": "184.35",
                "2. high": "186.50",
                "3. low": "183.80",
                "4. close": "185.25",
                "5. volume": "52478900",
            },
        },
    }
    mock_av_client.get_daily_time_series.return_value = mock_response
    request = DatasetRequest(
        dataset="day",
        profile=None,
        symbols=["AAPL"],
        start=dt.date(2025, 1, 28),
        end=dt.date(2025, 1, 28),
        timezone="UTC",
    )
    result = av_source.fetch_day_bars(request)
    assert result is not None
    assert len(result) == 1
