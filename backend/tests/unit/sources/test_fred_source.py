"""Unit tests for FRED source integration.

Tests the FREDSource class for fetching economic indicators from FRED API.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import httpx

from app.sources.fred import FREDSource


class _CsvResponse:
    def __init__(self, text: str) -> None:
        self._text = text

    def __enter__(self) -> _CsvResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._text.encode()


class TestFREDSource:
    """Test FRED source functionality."""

    def test_initialization_with_api_key(self) -> None:
        """Test FREDSource initialization with explicit API key."""
        source = FREDSource(api_key="test_key_123")
        assert source._api_key == "test_key_123"
        assert source.is_enabled() is True

    def test_initialization_without_api_key(self) -> None:
        """Test FREDSource initialization without API key."""
        with patch.dict("os.environ", {}, clear=True):
            source = FREDSource()
            assert source._api_key is None
            assert source.is_enabled() is False

    def test_initialization_with_env_var(self) -> None:
        """Test FREDSource reads API key from environment."""
        with patch.dict("os.environ", {"FRED_API_KEY": "env_key_456"}):
            source = FREDSource()
            assert source._api_key == "env_key_456"
            assert source.is_enabled() is True

    @patch("app.sources.fred.get_fred_client")
    def test_fetch_latest_success(self, mock_get_client: MagicMock) -> None:
        """Test successful fetch of latest indicator value."""
        mock_client = MagicMock()
        mock_client.get.return_value = {"observations": [{"date": "2024-11-14", "value": "4.25"}]}
        mock_get_client.return_value = mock_client

        source = FREDSource(api_key="test_key")
        result = source.fetch_latest("HY_SPREAD")

        assert result is not None
        assert result["indicator"] == "HY_SPREAD"
        assert result["series_id"] == "BAMLH0A0HYM2"
        assert result["date"] == "2024-11-14"
        assert result["value"] == 4.25

    @patch("app.sources.fred.urllib.request.urlopen")
    @patch.dict("os.environ", {}, clear=True)
    def test_fetch_latest_no_api_key(self, mock_urlopen: MagicMock) -> None:
        """Test fetch_latest falls back to FRED graph CSV without API key."""
        mock_urlopen.return_value = _CsvResponse(
            "observation_date,BAMLH0A0HYM2\n"
            "2024-11-13,4.20\n"
            "2024-11-14,4.25\n"
        )
        source = FREDSource(api_key=None)
        result = source.fetch_latest("HY_SPREAD")

        assert result is not None
        assert result["date"] == "2024-11-14"
        assert result["value"] == 4.25
        mock_urlopen.assert_called_once()

    @patch("httpx.get")
    def test_fetch_latest_unknown_indicator(self, mock_get: MagicMock) -> None:
        """Test fetch_latest returns None for unknown indicator."""
        source = FREDSource(api_key="test_key")
        result = source.fetch_latest("INVALID_INDICATOR")

        assert result is None
        mock_get.assert_not_called()

    @patch("app.sources.fred.get_fred_client")
    def test_fetch_latest_http_error(self, mock_get_client: MagicMock) -> None:
        """Test fetch_latest handles HTTP errors gracefully."""
        mock_client = MagicMock()
        mock_client.get.side_effect = httpx.HTTPError("API unavailable")
        mock_get_client.return_value = mock_client

        source = FREDSource(api_key="test_key")
        result = source.fetch_latest("VIX")

        assert result is None

    @patch("app.sources.fred.get_fred_client")
    def test_fetch_series_success(self, mock_get_client: MagicMock) -> None:
        """Test successful fetch of time series data."""
        mock_client = MagicMock()
        mock_client.get.return_value = {
            "observations": [
                {"date": "2024-11-01", "value": "4.10"},
                {"date": "2024-11-04", "value": "4.15"},
                {"date": "2024-11-05", "value": "."},  # Missing value
                {"date": "2024-11-06", "value": "4.20"},
            ]
        }
        mock_get_client.return_value = mock_client

        source = FREDSource(api_key="test_key")
        result = source.fetch_series("HY_SPREAD", "2024-11-01", "2024-11-06")

        assert len(result) == 3  # Missing value filtered out
        assert result[0] == (date(2024, 11, 1), 4.10)
        assert result[1] == (date(2024, 11, 4), 4.15)
        assert result[2] == (date(2024, 11, 6), 4.20)

    @patch("app.sources.fred.get_fred_client")
    def test_fetch_series_with_date_objects(self, mock_get_client: MagicMock) -> None:
        """Test fetch_series with date objects instead of strings."""
        mock_client = MagicMock()
        mock_client.get.return_value = {"observations": [{"date": "2024-11-01", "value": "4.10"}]}
        mock_get_client.return_value = mock_client

        source = FREDSource(api_key="test_key")
        result = source.fetch_series(
            "HY_SPREAD",
            start_date=date(2024, 11, 1),
            end_date=date(2024, 11, 6),
        )

        assert len(result) == 1
        assert result[0] == (date(2024, 11, 1), 4.10)

        # Verify correct date format in API call
        call_args = mock_client.get.call_args
        # call_args is (args, kwargs) tuple - params is the second positional arg to get()
        params = call_args[0][1]  # First call, second argument to get()
        assert params["observation_start"] == "2024-11-01"
        assert params["observation_end"] == "2024-11-06"

    @patch("app.sources.fred.get_fred_client")
    def test_fetch_series_filters_missing_values(self, mock_get_client: MagicMock) -> None:
        """Test that fetch_series filters out missing values (.)."""
        mock_client = MagicMock()
        mock_client.get.return_value = {
            "observations": [
                {"date": "2024-11-01", "value": "."},
                {"date": "2024-11-02", "value": ""},
                {"date": "2024-11-03", "value": "4.15"},
            ]
        }
        mock_get_client.return_value = mock_client

        source = FREDSource(api_key="test_key")
        result = source.fetch_series("HY_SPREAD")

        assert len(result) == 1
        assert result[0] == (date(2024, 11, 3), 4.15)

    @patch("app.sources.fred.urllib.request.urlopen")
    @patch.dict("os.environ", {}, clear=True)
    def test_fetch_series_no_api_key(self, mock_urlopen: MagicMock) -> None:
        """Test fetch_series falls back to FRED graph CSV without API key."""
        mock_urlopen.return_value = _CsvResponse(
            "observation_date,BAMLH0A0HYM2\n"
            "2024-11-01,4.10\n"
            "2024-11-02,.\n"
            "2024-11-03,4.15\n"
        )
        source = FREDSource(api_key=None)
        result = source.fetch_series("HY_SPREAD", "2024-11-02", "2024-11-03")

        assert result == [(date(2024, 11, 3), 4.15)]
        mock_urlopen.assert_called_once()

    @patch("app.sources.fred.get_fred_client")
    def test_fetch_series_http_error(self, mock_get_client: MagicMock) -> None:
        """Test fetch_series handles HTTP errors gracefully."""
        mock_client = MagicMock()
        mock_client.get.side_effect = httpx.HTTPError("API unavailable")
        mock_get_client.return_value = mock_client

        source = FREDSource(api_key="test_key")
        result = source.fetch_series("HY_SPREAD")

        assert result == []

    @patch("app.sources.fred.get_fred_client")
    def test_get_latest_value_success(self, mock_get_client: MagicMock) -> None:
        """Test successful get_latest_value."""
        mock_client = MagicMock()
        mock_client.get.return_value = {"observations": [{"date": "2024-11-14", "value": "4.25"}]}
        mock_get_client.return_value = mock_client

        source = FREDSource(api_key="test_key")
        result = source.get_latest_value("HY_SPREAD")

        assert result is not None
        assert result[0] == date(2024, 11, 14)
        assert result[1] == 4.25

    @patch("app.sources.fred.get_fred_client")
    def test_get_latest_value_no_data(self, mock_get_client: MagicMock) -> None:
        """Test get_latest_value returns None when no data available."""
        mock_client = MagicMock()
        mock_client.get.return_value = {"observations": []}
        mock_get_client.return_value = mock_client

        source = FREDSource(api_key="test_key")
        result = source.get_latest_value("HY_SPREAD")

        assert result is None

    def test_all_indicators_defined(self) -> None:
        """Test that all expected indicators are defined."""
        expected_indicators = [
            "VIX",
            "DXY",
            "TNX",
            "FEDFUNDS",
            "CPI_YOY",
            "UNEMPLOYMENT",
            "HY_SPREAD",
        ]

        for indicator in expected_indicators:
            assert indicator in FREDSource.INDICATORS
            assert isinstance(FREDSource.INDICATORS[indicator], str)
            assert len(FREDSource.INDICATORS[indicator]) > 0

    def test_hy_spread_indicator_value(self) -> None:
        """Test that HY_SPREAD maps to correct FRED series."""
        assert FREDSource.INDICATORS["HY_SPREAD"] == "BAMLH0A0HYM2"

    @patch("app.sources.fred.get_fred_client")
    def test_fetch_multiple_success(self, mock_get_client: MagicMock) -> None:
        """Test fetching multiple indicators."""
        mock_client = MagicMock()
        mock_client.get.return_value = {"observations": [{"date": "2024-11-14", "value": "4.25"}]}
        mock_get_client.return_value = mock_client

        source = FREDSource(api_key="test_key")
        result = source.fetch_multiple(["HY_SPREAD", "VIX"])

        assert len(result) == 2
        assert "HY_SPREAD" in result
        assert "VIX" in result
        assert mock_client.get.call_count == 2
