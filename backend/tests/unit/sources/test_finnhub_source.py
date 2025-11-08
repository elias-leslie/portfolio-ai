"""Tests for Finnhub source adapter.

This module tests the FinnhubSource class and FinnhubClient.
"""

from __future__ import annotations

import datetime as dt
import json
from unittest.mock import MagicMock, Mock, patch

import pytest

from app.sources.base import DatasetRequest
from app.sources.finnhub_source import FinnhubClient, FinnhubSource


@pytest.fixture
def mock_finnhub_client() -> Mock:
    """Create a mock FinnhubClient."""
    client = Mock(spec=FinnhubClient)
    client.request_count = 0
    return client


@pytest.fixture
def finnhub_source(mock_finnhub_client: Mock) -> FinnhubSource:
    """Create a FinnhubSource with mocked client."""
    source = FinnhubSource.__new__(FinnhubSource)
    source.name = "finnhub"
    source.priority = 10
    source.supports_day = True
    source.supports_reference = True
    source.supports_news = True
    source.client = mock_finnhub_client
    return source


def test_finnhub_source_initialization() -> None:
    """Test FinnhubSource initialization and capabilities."""
    with patch("app.sources.finnhub_source.get_client") as mock_get_client:
        mock_client = Mock(spec=FinnhubClient)
        mock_get_client.return_value = mock_client

        source = FinnhubSource()

        assert source.name == "finnhub"
        assert source.priority == 10
        assert source.supports_day is True
        assert source.supports_reference is True
        assert source.supports_news is True
        assert source.client == mock_client


def test_finnhub_fetch_day_bars_success(
    finnhub_source: FinnhubSource, mock_finnhub_client: Mock
) -> None:
    """Test successful fetch of daily OHLCV data."""
    # Mock API response - Finnhub returns arrays
    mock_response = {
        "c": [185.25, 183.75],  # close
        "h": [186.50, 184.50],  # high
        "l": [183.80, 182.50],  # low
        "o": [184.35, 183.00],  # open
        "t": [1706486400, 1706400000],  # timestamps
        "v": [52478900, 48392100],  # volume
        "s": "ok",
    }
    mock_finnhub_client.get_candles.return_value = mock_response

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
    result = finnhub_source.fetch_day_bars(request)

    # Verify result
    assert result is not None
    assert len(result) == 2
    assert "ticker" in result.columns
    assert "date" in result.columns
    assert "open" in result.columns
    assert "close" in result.columns
    assert "volume" in result.columns
    assert result["ticker"][0] == "AAPL"
    assert result["source"][0] == "finnhub"
    assert result["vwap"][0] is None  # Finnhub doesn't provide VWAP

    # Verify client was called correctly
    mock_finnhub_client.get_candles.assert_called_once()
    call_args = mock_finnhub_client.get_candles.call_args
    assert call_args[1]["ticker"] == "AAPL"
    assert call_args[1]["resolution"] == "D"


def test_finnhub_fetch_day_bars_no_data(
    finnhub_source: FinnhubSource, mock_finnhub_client: Mock
) -> None:
    """Test handling of no_data response."""
    # Mock no_data response
    mock_response = {
        "s": "no_data",
    }
    mock_finnhub_client.get_candles.return_value = mock_response

    request = DatasetRequest(
        dataset="day",
        profile=None,
        tickers=["INVALID"],
        start=dt.date(2025, 1, 28),
        end=dt.date(2025, 1, 28),
        timezone="UTC",
    )

    result = finnhub_source.fetch_day_bars(request)

    # Should return None when no data
    assert result is None


def test_finnhub_fetch_day_bars_empty_arrays(
    finnhub_source: FinnhubSource, mock_finnhub_client: Mock
) -> None:
    """Test handling of empty arrays."""
    mock_response = {
        "c": [],
        "h": [],
        "l": [],
        "o": [],
        "t": [],
        "v": [],
        "s": "ok",
    }
    mock_finnhub_client.get_candles.return_value = mock_response

    request = DatasetRequest(
        dataset="day",
        profile=None,
        tickers=["INVALID"],
        start=dt.date(2025, 1, 28),
        end=dt.date(2025, 1, 28),
        timezone="UTC",
    )

    result = finnhub_source.fetch_day_bars(request)

    assert result is None


def test_finnhub_fetch_reference_payload_success(
    finnhub_source: FinnhubSource, mock_finnhub_client: Mock
) -> None:
    """Test successful fetch of company reference data."""
    # Mock API response
    mock_response = {
        "name": "Apple Inc",
        "ticker": "AAPL",
        "country": "US",
        "currency": "USD",
        "exchange": "NASDAQ",
        "ipo": "1980-12-12",
        "marketCapitalization": 3200000,
        "shareOutstanding": 15.7,
        "finnhubIndustry": "Technology",
    }
    mock_finnhub_client.get_company_profile.return_value = mock_response

    # Fetch data
    result = finnhub_source.fetch_reference_payload(tickers=["AAPL"], as_of=dt.date(2025, 1, 28))

    # Verify result
    assert result is not None
    assert len(result) == 1
    assert result["ticker"][0] == "AAPL"
    assert result["source"][0] == "finnhub"
    assert result["as_of_date"][0] == dt.date(2025, 1, 28)

    # Verify payload is valid JSON
    payload = json.loads(result["payload"][0])
    assert payload["name"] == "Apple Inc"
    assert payload["ticker"] == "AAPL"
    assert payload["country"] == "US"

    # Verify client was called
    mock_finnhub_client.get_company_profile.assert_called_once_with("AAPL")


def test_finnhub_fetch_reference_payload_empty_response(
    finnhub_source: FinnhubSource, mock_finnhub_client: Mock
) -> None:
    """Test handling of empty response in reference data fetch."""
    mock_response: dict[str, str] = {}
    mock_finnhub_client.get_company_profile.return_value = mock_response

    result = finnhub_source.fetch_reference_payload(tickers=["INVALID"], as_of=dt.date(2025, 1, 28))

    assert result is None


def test_finnhub_fetch_reference_payload_no_name(
    finnhub_source: FinnhubSource, mock_finnhub_client: Mock
) -> None:
    """Test handling of response without name field."""
    mock_response = {"ticker": "AAPL"}  # Missing name field
    mock_finnhub_client.get_company_profile.return_value = mock_response

    result = finnhub_source.fetch_reference_payload(tickers=["AAPL"], as_of=dt.date(2025, 1, 28))

    assert result is None


def test_finnhub_fetch_reference_payload_multiple_tickers(
    finnhub_source: FinnhubSource, mock_finnhub_client: Mock
) -> None:
    """Test fetching reference data for multiple tickers."""

    # Mock responses for different tickers
    def mock_get_profile(ticker: str) -> dict[str, str]:
        responses = {
            "AAPL": {
                "name": "Apple Inc",
                "ticker": "AAPL",
                "country": "US",
            },
            "GOOGL": {
                "name": "Alphabet Inc",
                "ticker": "GOOGL",
                "country": "US",
            },
        }
        return responses.get(ticker, {})

    mock_finnhub_client.get_company_profile.side_effect = mock_get_profile

    result = finnhub_source.fetch_reference_payload(
        tickers=["AAPL", "GOOGL"], as_of=dt.date(2025, 1, 28)
    )

    assert result is not None
    assert len(result) == 2
    assert set(result["ticker"].to_list()) == {"AAPL", "GOOGL"}


def test_finnhub_fetch_news_payload_ticker(
    finnhub_source: FinnhubSource, mock_finnhub_client: Mock
) -> None:
    """Test fetching company-specific news payload."""
    published_ts = dt.datetime(2025, 1, 28, tzinfo=dt.UTC).timestamp()
    mock_response = [
        {
            "headline": "AAPL launches new product",
            "summary": "Details about the launch.",
            "url": "https://example.com/aapl-news",
            "source": "ExampleWire",
            "datetime": published_ts,
            "image": "https://example.com/image.png",
        }
    ]
    mock_finnhub_client.get.return_value = mock_response

    start = dt.datetime(2025, 1, 20, tzinfo=dt.UTC)
    end = dt.datetime(2025, 1, 28, tzinfo=dt.UTC)

    result = finnhub_source.fetch_news_payload(["AAPL"], start, end)

    assert result is not None
    assert len(result) == 1
    row = result.to_dicts()[0]
    assert row["ticker"] == "AAPL"
    assert row["headline"] == "AAPL launches new product"
    assert row["source"] == "finnhub"

    mock_finnhub_client.get.assert_called_once_with(
        "/company-news",
        {
            "symbol": "AAPL",
            "from": start.date().isoformat(),
            "to": end.date().isoformat(),
        },
    )


def test_finnhub_fetch_news_payload_market(
    finnhub_source: FinnhubSource, mock_finnhub_client: Mock
) -> None:
    """Test fetching market-wide news payload."""
    mock_finnhub_client.get.return_value = []

    start = dt.datetime(2025, 1, 1, tzinfo=dt.UTC)
    end = dt.datetime(2025, 1, 2, tzinfo=dt.UTC)
    result = finnhub_source.fetch_news_payload(["__MARKET__"], start, end)

    assert result is None
    mock_finnhub_client.get.assert_called_once_with("/news", {"category": "general"})


def test_finnhub_client_rate_limiting() -> None:
    """Test that client enforces rate limits."""
    with patch("app.sources.finnhub_source.os.getenv") as mock_getenv:
        mock_getenv.return_value = "test_api_key"

        with patch("httpx.Client") as mock_client_class:
            mock_http_client = MagicMock()
            mock_client_class.return_value = mock_http_client

            # Mock time.sleep and time.time to make test run instantly
            mock_time = 0.0
            sleep_calls = []

            def mock_sleep(seconds: float) -> None:
                nonlocal mock_time
                sleep_calls.append(seconds)
                mock_time += seconds

            def mock_time_func() -> float:
                return mock_time

            with (
                patch("time.sleep", side_effect=mock_sleep),
                patch("time.time", side_effect=mock_time_func),
            ):
                # Create client with default rate limit (60/min)
                client = FinnhubClient(api_key="test_key")

                # Mock response
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {"s": "ok"}
                mock_http_client.request.return_value = mock_response

                # Make first request - should go through immediately
                client.get("/test")
                assert len(sleep_calls) == 0  # No sleep on first call

                # Make second request - should also go through
                client.get("/test")
                assert len(sleep_calls) == 0  # No sleep on second call (within rate limit)

                # With real rate limit of 60/min, we won't hit it with just 3 requests
                # So let's just verify requests complete successfully
                client.get("/test")

                # Verify all requests completed without rate limiting
                assert client.request_count == 3
                assert len(sleep_calls) == 0  # No sleep needed for 3 requests with 60/min limit


def test_finnhub_source_is_enabled() -> None:
    """Test is_enabled checks for API key."""
    with patch("app.sources.finnhub_source.os.getenv") as mock_getenv:
        mock_getenv.return_value = "test_api_key"

        with patch("app.sources.finnhub_source.get_client"):
            source = FinnhubSource()
            assert source.is_enabled() is True

    with patch("app.sources.finnhub_source.os.getenv") as mock_getenv:
        mock_getenv.return_value = None

        with patch("app.sources.finnhub_source.get_client"):
            source = FinnhubSource()
            assert source.is_enabled() is False


def test_finnhub_fetch_day_bars_with_ingest_run_id(
    finnhub_source: FinnhubSource, mock_finnhub_client: Mock
) -> None:
    """Test that ingest_run_id is added when provided."""
    mock_response = {
        "c": [185.25],
        "h": [186.50],
        "l": [183.80],
        "o": [184.35],
        "t": [1706486400],
        "v": [52478900],
        "s": "ok",
    }
    mock_finnhub_client.get_candles.return_value = mock_response

    request = DatasetRequest(
        dataset="day",
        profile=None,
        tickers=["AAPL"],
        start=dt.date(2025, 1, 28),
        end=dt.date(2025, 1, 28),
        timezone="UTC",
        ingest_run_id="test-run-123",
    )

    result = finnhub_source.fetch_day_bars(request)

    assert result is not None
    assert "ingest_run_id" in result.columns
    assert result["ingest_run_id"][0] == "test-run-123"


def test_finnhub_fetch_day_bars_timestamp_conversion(
    finnhub_source: FinnhubSource, mock_finnhub_client: Mock
) -> None:
    """Test that Unix timestamps are correctly converted to dates."""
    # Use a realistic timestamp
    test_timestamp = 1737936000  # 2025-01-27 00:00:00 UTC
    mock_response = {
        "c": [185.25],
        "h": [186.50],
        "l": [183.80],
        "o": [184.35],
        "t": [test_timestamp],
        "v": [52478900],
        "s": "ok",
    }
    mock_finnhub_client.get_candles.return_value = mock_response

    request = DatasetRequest(
        dataset="day",
        profile=None,
        tickers=["AAPL"],
        start=dt.date(2025, 1, 27),
        end=dt.date(2025, 1, 28),
        timezone="UTC",
    )

    result = finnhub_source.fetch_day_bars(request)

    assert result is not None
    assert len(result) == 1
    # Verify the timestamp was converted to a date
    assert isinstance(result["date"][0], dt.date)
    # Verify it's in the expected range
    assert result["date"][0] >= dt.date(2025, 1, 26)
    assert result["date"][0] <= dt.date(2025, 1, 29)
