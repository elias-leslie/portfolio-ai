"""Unit tests for FRED source integration.

Tests the FREDSource class for fetching economic indicators from FRED API.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import httpx

from app.sources.fred import FREDSource


class TestFREDSource:
    """Test FRED source functionality."""

    def test_initialization_with_api_key(self) -> None:
        """Test FREDSource initialization with explicit API key."""
        source = FREDSource(api_key="test_key_123")
        assert source.api_key == "test_key_123"
        assert source.is_enabled() is True

    def test_initialization_without_api_key(self) -> None:
        """Test FREDSource initialization without API key."""
        with patch.dict("os.environ", {}, clear=True):
            source = FREDSource()
            assert source.api_key is None
            assert source.is_enabled() is False

    def test_initialization_with_env_var(self) -> None:
        """Test FREDSource reads API key from environment."""
        with patch.dict("os.environ", {"FRED_API_KEY": "env_key_456"}):
            source = FREDSource()
            assert source.api_key == "env_key_456"
            assert source.is_enabled() is True

    @patch("httpx.get")
    def test_fetch_latest_success(self, mock_get: MagicMock) -> None:
        """Test successful fetch of latest indicator value."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "observations": [{"date": "2024-11-14", "value": "4.25"}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        source = FREDSource(api_key="test_key")
        result = source.fetch_latest("HY_SPREAD")

        assert result is not None
        assert result["indicator"] == "HY_SPREAD"
        assert result["series_id"] == "BAMLH0A0HYM2"
        assert result["date"] == "2024-11-14"
        assert result["value"] == 4.25

    @patch("httpx.get")
    @patch.dict("os.environ", {}, clear=True)
    def test_fetch_latest_no_api_key(self, mock_get: MagicMock) -> None:
        """Test fetch_latest returns None without API key."""
        source = FREDSource(api_key=None)
        result = source.fetch_latest("HY_SPREAD")

        assert result is None
        mock_get.assert_not_called()

    @patch("httpx.get")
    def test_fetch_latest_unknown_indicator(self, mock_get: MagicMock) -> None:
        """Test fetch_latest returns None for unknown indicator."""
        source = FREDSource(api_key="test_key")
        result = source.fetch_latest("INVALID_INDICATOR")

        assert result is None
        mock_get.assert_not_called()

    @patch("httpx.get")
    def test_fetch_latest_http_error(self, mock_get: MagicMock) -> None:
        """Test fetch_latest handles HTTP errors gracefully."""
        mock_get.side_effect = httpx.HTTPError("API unavailable")

        source = FREDSource(api_key="test_key")
        result = source.fetch_latest("VIX")

        assert result is None

    @patch("httpx.get")
    def test_fetch_series_success(self, mock_get: MagicMock) -> None:
        """Test successful fetch of time series data."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "observations": [
                {"date": "2024-11-01", "value": "4.10"},
                {"date": "2024-11-04", "value": "4.15"},
                {"date": "2024-11-05", "value": "."},  # Missing value
                {"date": "2024-11-06", "value": "4.20"},
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        source = FREDSource(api_key="test_key")
        result = source.fetch_series("HY_SPREAD", "2024-11-01", "2024-11-06")

        assert len(result) == 3  # Missing value filtered out
        assert result[0] == (date(2024, 11, 1), 4.10)
        assert result[1] == (date(2024, 11, 4), 4.15)
        assert result[2] == (date(2024, 11, 6), 4.20)

    @patch("httpx.get")
    def test_fetch_series_with_date_objects(self, mock_get: MagicMock) -> None:
        """Test fetch_series with date objects instead of strings."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "observations": [{"date": "2024-11-01", "value": "4.10"}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        source = FREDSource(api_key="test_key")
        result = source.fetch_series(
            "HY_SPREAD",
            start_date=date(2024, 11, 1),
            end_date=date(2024, 11, 6),
        )

        assert len(result) == 1
        assert result[0] == (date(2024, 11, 1), 4.10)

        # Verify correct date format in API call
        call_args = mock_get.call_args
        params = call_args.kwargs["params"]
        assert params["observation_start"] == "2024-11-01"
        assert params["observation_end"] == "2024-11-06"

    @patch("httpx.get")
    def test_fetch_series_filters_missing_values(self, mock_get: MagicMock) -> None:
        """Test that fetch_series filters out missing values (.)."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "observations": [
                {"date": "2024-11-01", "value": "."},
                {"date": "2024-11-02", "value": ""},
                {"date": "2024-11-03", "value": "4.15"},
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        source = FREDSource(api_key="test_key")
        result = source.fetch_series("HY_SPREAD")

        assert len(result) == 1
        assert result[0] == (date(2024, 11, 3), 4.15)

    @patch("httpx.get")
    @patch.dict("os.environ", {}, clear=True)
    def test_fetch_series_no_api_key(self, mock_get: MagicMock) -> None:
        """Test fetch_series returns empty list without API key."""
        source = FREDSource(api_key=None)
        result = source.fetch_series("HY_SPREAD")

        assert result == []
        mock_get.assert_not_called()

    @patch("httpx.get")
    def test_fetch_series_http_error(self, mock_get: MagicMock) -> None:
        """Test fetch_series handles HTTP errors gracefully."""
        mock_get.side_effect = httpx.HTTPError("API unavailable")

        source = FREDSource(api_key="test_key")
        result = source.fetch_series("HY_SPREAD")

        assert result == []

    @patch("httpx.get")
    def test_get_latest_value_success(self, mock_get: MagicMock) -> None:
        """Test successful get_latest_value."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "observations": [{"date": "2024-11-14", "value": "4.25"}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        source = FREDSource(api_key="test_key")
        result = source.get_latest_value("HY_SPREAD")

        assert result is not None
        assert result[0] == date(2024, 11, 14)
        assert result[1] == 4.25

    @patch("httpx.get")
    def test_get_latest_value_no_data(self, mock_get: MagicMock) -> None:
        """Test get_latest_value returns None when no data available."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"observations": []}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

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

    @patch("httpx.get")
    def test_fetch_multiple_success(self, mock_get: MagicMock) -> None:
        """Test fetching multiple indicators."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "observations": [{"date": "2024-11-14", "value": "4.25"}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        source = FREDSource(api_key="test_key")
        result = source.fetch_multiple(["HY_SPREAD", "VIX"])

        assert len(result) == 2
        assert "HY_SPREAD" in result
        assert "VIX" in result
        assert mock_get.call_count == 2
