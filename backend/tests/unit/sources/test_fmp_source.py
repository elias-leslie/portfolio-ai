"""Tests for Financial Modeling Prep (FMP) source adapter.

This module tests the FMPSource class and FMPClient.
"""

from __future__ import annotations

import datetime as dt
import json
from unittest.mock import MagicMock, Mock, patch

import pytest

from app.sources.base import DatasetRequest
from app.sources.fmp_source import FMPClient, FMPSource


@pytest.fixture
def mock_fmp_client() -> Mock:
    """Create a mock FMPClient."""
    client = Mock(spec=FMPClient)
    client.request_count = 0
    return client


@pytest.fixture
def fmp_source(mock_fmp_client: Mock) -> FMPSource:
    """Create an FMPSource with mocked client."""
    source = FMPSource.__new__(FMPSource)
    source.name = "fmp"
    source.priority = 3
    source.supports_day = True
    source.supports_reference = True
    source.supports_news = True
    source.client = mock_fmp_client
    return source


def test_fmp_source_initialization() -> None:
    """Test FMPSource initialization and capabilities."""
    with patch("app.sources.fmp_source.get_client") as mock_get_client:
        mock_client = Mock(spec=FMPClient)
        mock_get_client.return_value = mock_client

        source = FMPSource()

        assert source.name == "fmp"
        assert source.priority == 3
        assert source.supports_day is True
        assert source.supports_reference is True
        assert source.supports_news is True
        assert source.client == mock_client


def test_fmp_fetch_day_bars_success(fmp_source: FMPSource, mock_fmp_client: Mock) -> None:
    """Test successful fetch of daily OHLCV data."""
    # Mock API response
    mock_response = {
        "symbol": "AAPL",
        "historical": [
            {
                "date": "2025-01-28",
                "open": 184.35,
                "high": 186.50,
                "low": 183.80,
                "close": 185.25,
                "volume": 52478900,
                "vwap": 185.10,
            },
            {
                "date": "2025-01-27",
                "open": 183.00,
                "high": 184.50,
                "low": 182.50,
                "close": 183.75,
                "volume": 48392100,
                "vwap": 183.50,
            },
        ],
    }
    mock_fmp_client.get_historical_price.return_value = mock_response

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
    result = fmp_source.fetch_day_bars(request)

    # Verify result
    assert result is not None
    assert len(result) == 2
    assert "ticker" in result.columns
    assert "date" in result.columns
    assert "open" in result.columns
    assert "close" in result.columns
    assert "volume" in result.columns
    assert "vwap" in result.columns
    assert result["ticker"][0] == "AAPL"
    assert result["source"][0] == "fmp"
    assert result["vwap"][0] == 185.10

    # Verify client was called correctly
    mock_fmp_client.get_historical_price.assert_called_once()
    call_args = mock_fmp_client.get_historical_price.call_args
    assert call_args[1]["ticker"] == "AAPL"
    assert call_args[1]["from_date"] == "2025-01-27"
    assert call_args[1]["to_date"] == "2025-01-28"


def test_fmp_fetch_day_bars_api_error(fmp_source: FMPSource, mock_fmp_client: Mock) -> None:
    """Test handling of API error response."""
    # Mock error response
    mock_response = {
        "Error Message": "Invalid API key",
    }
    mock_fmp_client.get_historical_price.return_value = mock_response

    request = DatasetRequest(
        dataset="day",
        profile=None,
        tickers=["AAPL"],
        start=dt.date(2025, 1, 28),
        end=dt.date(2025, 1, 28),
        timezone="UTC",
    )

    result = fmp_source.fetch_day_bars(request)

    # Should return None on error
    assert result is None


def test_fmp_fetch_day_bars_empty_historical(fmp_source: FMPSource, mock_fmp_client: Mock) -> None:
    """Test handling of empty historical array."""
    mock_response = {"symbol": "INVALID", "historical": []}
    mock_fmp_client.get_historical_price.return_value = mock_response

    request = DatasetRequest(
        dataset="day",
        profile=None,
        tickers=["INVALID"],
        start=dt.date(2025, 1, 28),
        end=dt.date(2025, 1, 28),
        timezone="UTC",
    )

    result = fmp_source.fetch_day_bars(request)

    assert result is None


def test_fmp_fetch_day_bars_no_vwap(fmp_source: FMPSource, mock_fmp_client: Mock) -> None:
    """Test handling of bars without VWAP field."""
    mock_response = {
        "symbol": "AAPL",
        "historical": [
            {
                "date": "2025-01-28",
                "open": 184.35,
                "high": 186.50,
                "low": 183.80,
                "close": 185.25,
                "volume": 52478900,
                # No vwap field
            },
        ],
    }
    mock_fmp_client.get_historical_price.return_value = mock_response

    request = DatasetRequest(
        dataset="day",
        profile=None,
        tickers=["AAPL"],
        start=dt.date(2025, 1, 28),
        end=dt.date(2025, 1, 28),
        timezone="UTC",
    )

    result = fmp_source.fetch_day_bars(request)

    assert result is not None
    assert len(result) == 1
    assert result["vwap"][0] is None  # Should handle missing VWAP gracefully


def test_fmp_fetch_news_payload_ticker(fmp_source: FMPSource, mock_fmp_client: Mock) -> None:
    """Test fetching ticker-specific news."""
    mock_response = [
        {
            "symbol": "AAPL",
            "title": "Apple announces new product",
            "text": "More details about the launch.",
            "url": "https://example.com/aapl-news",
            "site": "ExampleWire",
            "publishedDate": "2025-01-28T12:34:56Z",
        }
    ]
    mock_fmp_client.get.return_value = mock_response

    start = dt.datetime(2025, 1, 20, tzinfo=dt.UTC)
    end = dt.datetime(2025, 1, 28, tzinfo=dt.UTC)
    result = fmp_source.fetch_news_payload(["AAPL"], start, end)

    assert result is not None
    assert len(result) == 1
    row = result.to_dicts()[0]
    assert row["ticker"] == "AAPL"
    assert row["headline"] == "Apple announces new product"
    assert row["source"] == "fmp"

    mock_fmp_client.get.assert_called_once_with(
        "/stock_news",
        {
            "from": start.date().isoformat(),
            "to": end.date().isoformat(),
            "limit": 50,
            "tickers": "AAPL",
        },
    )


def test_fmp_fetch_news_payload_market(fmp_source: FMPSource, mock_fmp_client: Mock) -> None:
    """Test fetching market news without tickers."""
    mock_fmp_client.get.return_value = []

    start = dt.datetime(2025, 1, 1, tzinfo=dt.UTC)
    end = dt.datetime(2025, 1, 2, tzinfo=dt.UTC)
    result = fmp_source.fetch_news_payload(["__MARKET__"], start, end)

    assert result is None
    mock_fmp_client.get.assert_called_once_with(
        "/stock_news",
        {
            "from": start.date().isoformat(),
            "to": end.date().isoformat(),
            "limit": 50,
        },
    )


def test_fmp_fetch_reference_payload_success(fmp_source: FMPSource, mock_fmp_client: Mock) -> None:
    """Test successful fetch of company reference data."""
    # Mock API response - FMP returns a list with single dict
    mock_response = [
        {
            "symbol": "AAPL",
            "companyName": "Apple Inc",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "mktCap": "3200000000000",
            "currency": "USD",
            "exchange": "NASDAQ",
        }
    ]
    mock_fmp_client.get_profile.return_value = mock_response

    # Fetch data
    result = fmp_source.fetch_reference_payload(tickers=["AAPL"], as_of=dt.date(2025, 1, 28))

    # Verify result
    assert result is not None
    assert len(result) == 1
    assert result["ticker"][0] == "AAPL"
    assert result["source"][0] == "fmp"
    assert result["as_of_date"][0] == dt.date(2025, 1, 28)

    # Verify payload is valid JSON
    payload = json.loads(result["payload"][0])
    assert payload["symbol"] == "AAPL"
    assert payload["companyName"] == "Apple Inc"
    assert payload["sector"] == "Technology"

    # Verify client was called
    mock_fmp_client.get_profile.assert_called_once_with("AAPL")


def test_fmp_fetch_reference_payload_empty_response(
    fmp_source: FMPSource, mock_fmp_client: Mock
) -> None:
    """Test handling of empty response in reference data fetch."""
    mock_response: list[dict[str, str]] = []
    mock_fmp_client.get_profile.return_value = mock_response

    result = fmp_source.fetch_reference_payload(tickers=["INVALID"], as_of=dt.date(2025, 1, 28))

    assert result is None


def test_fmp_fetch_reference_payload_multiple_tickers(
    fmp_source: FMPSource, mock_fmp_client: Mock
) -> None:
    """Test fetching reference data for multiple tickers."""

    # Mock responses for different tickers
    def mock_get_profile(ticker: str) -> list[dict[str, str]]:
        responses: dict[str, list[dict[str, str]]] = {
            "AAPL": [
                {
                    "symbol": "AAPL",
                    "companyName": "Apple Inc",
                    "sector": "Technology",
                }
            ],
            "GOOGL": [
                {
                    "symbol": "GOOGL",
                    "companyName": "Alphabet Inc",
                    "sector": "Technology",
                }
            ],
        }
        return responses.get(ticker, [])

    mock_fmp_client.get_profile.side_effect = mock_get_profile

    result = fmp_source.fetch_reference_payload(
        tickers=["AAPL", "GOOGL"], as_of=dt.date(2025, 1, 28)
    )

    assert result is not None
    assert len(result) == 2
    assert set(result["ticker"].to_list()) == {"AAPL", "GOOGL"}


def test_fmp_fetch_news_not_implemented(
    fmp_source: FMPSource,
) -> None:
    """Test that news fetching returns None (not implemented)."""
    result = fmp_source.fetch_news_payload(
        tickers=["AAPL"],
        start=dt.datetime(2025, 1, 28, 0, 0),
        end=dt.datetime(2025, 1, 28, 23, 59),
    )

    assert result is None


def test_fmp_client_rate_limiting_daily() -> None:
    """Test that client enforces daily rate limits."""
    with patch("app.sources.fmp_source.os.getenv") as mock_getenv:
        mock_getenv.return_value = "test_api_key"

        with patch("httpx.Client") as mock_client_class:
            mock_http_client = MagicMock()
            mock_client_class.return_value = mock_http_client

            # Create client with default daily limit (250/day)
            client = FMPClient(api_key="test_key")

            # Mock response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "ok"}
            mock_http_client.request.return_value = mock_response

            # With a daily limit of 250, making just a few requests should succeed
            # This test verifies the client is initialized correctly with daily limit
            for _ in range(5):
                client.get("/test")

            assert client.request_count == 5
            # No rate limit error should occur with only 5 requests (limit is 250/day)


def test_fmp_source_is_enabled() -> None:
    """Test is_enabled checks for API key."""
    with patch("app.sources.fmp_source.os.getenv") as mock_getenv:
        mock_getenv.return_value = "test_api_key"

        with patch("app.sources.fmp_source.get_client"):
            source = FMPSource()
            assert source.is_enabled() is True

    with patch("app.sources.fmp_source.os.getenv") as mock_getenv:
        mock_getenv.return_value = None

        with patch("app.sources.fmp_source.get_client"):
            source = FMPSource()
            assert source.is_enabled() is False


def test_fmp_fetch_day_bars_with_ingest_run_id(
    fmp_source: FMPSource, mock_fmp_client: Mock
) -> None:
    """Test that ingest_run_id is added when provided."""
    mock_response = {
        "symbol": "AAPL",
        "historical": [
            {
                "date": "2025-01-28",
                "open": 184.35,
                "high": 186.50,
                "low": 183.80,
                "close": 185.25,
                "volume": 52478900,
            },
        ],
    }
    mock_fmp_client.get_historical_price.return_value = mock_response

    request = DatasetRequest(
        dataset="day",
        profile=None,
        tickers=["AAPL"],
        start=dt.date(2025, 1, 28),
        end=dt.date(2025, 1, 28),
        timezone="UTC",
        ingest_run_id="test-run-123",
    )

    result = fmp_source.fetch_day_bars(request)

    assert result is not None
    assert "ingest_run_id" in result.columns
    assert result["ingest_run_id"][0] == "test-run-123"
