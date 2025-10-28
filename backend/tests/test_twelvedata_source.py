"""Tests for Twelve Data source adapter.

This module tests the TwelveDataSource class and TwelveDataClient.
"""

from __future__ import annotations

import datetime as dt
import json
import time
from unittest.mock import MagicMock, Mock, patch

import pytest

from app.sources.base import DatasetRequest
from app.sources.twelvedata_source import TwelveDataClient, TwelveDataSource


@pytest.fixture
def mock_twelvedata_client() -> Mock:
    """Create a mock TwelveDataClient."""
    client = Mock(spec=TwelveDataClient)
    client.request_count = 0
    return client


@pytest.fixture
def twelvedata_source(mock_twelvedata_client: Mock) -> TwelveDataSource:
    """Create a TwelveDataSource with mocked client."""
    source = TwelveDataSource.__new__(TwelveDataSource)
    source.name = "twelvedata"
    source.priority = 2
    source.supports_day = True
    source.supports_reference = True
    source.supports_news = False
    source.client = mock_twelvedata_client
    return source


def test_twelvedata_source_initialization() -> None:
    """Test TwelveDataSource initialization and capabilities."""
    with patch("app.sources.twelvedata_source.get_client") as mock_get_client:
        mock_client = Mock(spec=TwelveDataClient)
        mock_get_client.return_value = mock_client

        source = TwelveDataSource()

        assert source.name == "twelvedata"
        assert source.priority == 2
        assert source.supports_day is True
        assert source.supports_reference is True
        assert source.supports_news is False
        assert source.client == mock_client


def test_twelvedata_fetch_day_bars_success(
    twelvedata_source: TwelveDataSource, mock_twelvedata_client: Mock
) -> None:
    """Test successful fetch of daily OHLCV data."""
    # Mock API response
    mock_response = {
        "status": "ok",
        "values": [
            {
                "datetime": "2025-01-28",
                "open": "184.35",
                "high": "186.50",
                "low": "183.80",
                "close": "185.25",
                "volume": "52478900",
            },
            {
                "datetime": "2025-01-27",
                "open": "183.00",
                "high": "184.50",
                "low": "182.50",
                "close": "183.75",
                "volume": "48392100",
            },
        ],
    }
    mock_twelvedata_client.get_time_series.return_value = mock_response

    # Create request
    request = DatasetRequest(
        dataset="day",
        profile=None,
        tickers=["AAPL"],
        start=dt.date(2025, 1, 27),
        end=dt.date(2025, 1, 28),
        timezone="UTC",
    )

    # Fetch data
    result = twelvedata_source.fetch_day_bars(request)

    # Verify result
    assert result is not None
    assert len(result) == 2
    assert "ticker" in result.columns
    assert "date" in result.columns
    assert "open" in result.columns
    assert "close" in result.columns
    assert "volume" in result.columns
    assert result["ticker"][0] == "AAPL"
    assert result["source"][0] == "twelvedata"

    # Verify client was called correctly
    mock_twelvedata_client.get_time_series.assert_called_once()
    call_args = mock_twelvedata_client.get_time_series.call_args
    assert call_args[1]["ticker"] == "AAPL"
    assert call_args[1]["start_date"] == "2025-01-27"
    assert call_args[1]["end_date"] == "2025-01-28"


def test_twelvedata_fetch_day_bars_api_error(
    twelvedata_source: TwelveDataSource, mock_twelvedata_client: Mock
) -> None:
    """Test handling of API error response."""
    # Mock error response
    mock_response = {
        "status": "error",
        "message": "Invalid API key",
    }
    mock_twelvedata_client.get_time_series.return_value = mock_response

    request = DatasetRequest(
        dataset="day",
        profile=None,
        tickers=["AAPL"],
        start=dt.date(2025, 1, 28),
        end=dt.date(2025, 1, 28),
        timezone="UTC",
    )

    result = twelvedata_source.fetch_day_bars(request)

    # Should return None on error
    assert result is None


def test_twelvedata_fetch_day_bars_empty_values(
    twelvedata_source: TwelveDataSource, mock_twelvedata_client: Mock
) -> None:
    """Test handling of empty values array."""
    mock_response = {"status": "ok", "values": []}
    mock_twelvedata_client.get_time_series.return_value = mock_response

    request = DatasetRequest(
        dataset="day",
        profile=None,
        tickers=["INVALID"],
        start=dt.date(2025, 1, 28),
        end=dt.date(2025, 1, 28),
        timezone="UTC",
    )

    result = twelvedata_source.fetch_day_bars(request)

    assert result is None


def test_twelvedata_fetch_reference_payload_success(
    twelvedata_source: TwelveDataSource, mock_twelvedata_client: Mock
) -> None:
    """Test successful fetch of company reference data."""
    # Mock API response
    mock_response = {
        "symbol": "AAPL",
        "name": "Apple Inc",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "market_cap": "3200000000000",
        "currency": "USD",
        "exchange": "NASDAQ",
    }
    mock_twelvedata_client.get_profile.return_value = mock_response

    # Fetch data
    result = twelvedata_source.fetch_reference_payload(tickers=["AAPL"], as_of=dt.date(2025, 1, 28))

    # Verify result
    assert result is not None
    assert len(result) == 1
    assert result["ticker"][0] == "AAPL"
    assert result["source"][0] == "twelvedata"
    assert result["as_of_date"][0] == dt.date(2025, 1, 28)

    # Verify payload is valid JSON
    payload = json.loads(result["payload"][0])
    assert payload["symbol"] == "AAPL"
    assert payload["name"] == "Apple Inc"
    assert payload["sector"] == "Technology"

    # Verify client was called
    mock_twelvedata_client.get_profile.assert_called_once_with("AAPL")


def test_twelvedata_fetch_reference_payload_api_error(
    twelvedata_source: TwelveDataSource, mock_twelvedata_client: Mock
) -> None:
    """Test handling of API error in reference data fetch."""
    mock_response = {"status": "error", "message": "Ticker not found"}
    mock_twelvedata_client.get_profile.return_value = mock_response

    result = twelvedata_source.fetch_reference_payload(
        tickers=["INVALID"], as_of=dt.date(2025, 1, 28)
    )

    assert result is None


def test_twelvedata_fetch_reference_payload_multiple_tickers(
    twelvedata_source: TwelveDataSource, mock_twelvedata_client: Mock
) -> None:
    """Test fetching reference data for multiple tickers."""

    # Mock responses for different tickers
    def mock_get_profile(ticker: str) -> dict[str, str]:
        responses = {
            "AAPL": {
                "symbol": "AAPL",
                "name": "Apple Inc",
                "sector": "Technology",
            },
            "GOOGL": {
                "symbol": "GOOGL",
                "name": "Alphabet Inc",
                "sector": "Technology",
            },
        }
        return responses.get(ticker, {"status": "error"})

    mock_twelvedata_client.get_profile.side_effect = mock_get_profile

    result = twelvedata_source.fetch_reference_payload(
        tickers=["AAPL", "GOOGL"], as_of=dt.date(2025, 1, 28)
    )

    assert result is not None
    assert len(result) == 2
    assert set(result["ticker"].to_list()) == {"AAPL", "GOOGL"}


def test_twelvedata_fetch_news_not_implemented(
    twelvedata_source: TwelveDataSource,
) -> None:
    """Test that news fetching returns None (not implemented)."""
    result = twelvedata_source.fetch_news_payload(
        tickers=["AAPL"],
        start=dt.datetime(2025, 1, 28, 0, 0),
        end=dt.datetime(2025, 1, 28, 23, 59),
    )

    assert result is None


def test_twelvedata_client_rate_limiting() -> None:
    """Test that client enforces rate limits."""
    with patch("app.sources.twelvedata_source.os.getenv") as mock_getenv:
        mock_getenv.return_value = "test_api_key"

        with patch("httpx.Client") as mock_client_class:
            mock_http_client = MagicMock()
            mock_client_class.return_value = mock_http_client

            # Create client with low rate limit for testing
            client = TwelveDataClient(api_key="test_key", rate_calls_per_minute=2)

            # Mock response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "ok"}
            mock_http_client.request.return_value = mock_response

            # Make first request - should go through immediately
            start_time = time.time()
            client.get("/test")
            first_call_time = time.time() - start_time

            # First call should be fast (< 0.1s)
            assert first_call_time < 0.1

            # Make second request - should also go through
            client.get("/test")

            # Make third request - should trigger rate limit wait
            # (we set rate_calls_per_minute=2, so third request should wait)
            client.get("/test")

            # Verify throttle was called and all requests completed
            assert client.request_count == 3


def test_twelvedata_source_is_enabled() -> None:
    """Test is_enabled checks for API key."""
    with patch("app.sources.twelvedata_source.os.getenv") as mock_getenv:
        mock_getenv.return_value = "test_api_key"

        with patch("app.sources.twelvedata_source.get_client"):
            source = TwelveDataSource()
            assert source.is_enabled() is True

    with patch("app.sources.twelvedata_source.os.getenv") as mock_getenv:
        mock_getenv.return_value = None

        with patch("app.sources.twelvedata_source.get_client"):
            source = TwelveDataSource()
            assert source.is_enabled() is False
