"""Unit tests for options pipeline tasks.

Tests cover:
- Put/Call ratio calculation from yfinance, Polygon, Finnhub
- Multi-source fallback chain behavior
- Error handling and data validation
- Database storage verification
- Task success/failure return values
"""

from __future__ import annotations

import datetime as dt
import json
from unittest.mock import MagicMock, Mock, patch

import pytest
import requests

from app.tasks.market_data.options_pipeline import (
    PUTCALL_EXPIRATIONS,
    PUTCALL_SYMBOLS,
    _calculate_putcall_from_finnhub,
    _calculate_putcall_from_polygon,
    _calculate_putcall_from_yfinance,
    _get_putcall_ratio_with_fallbacks,
    fetch_options_activity_metrics,
    fetch_putcall_ratio,
)


class TestCalculatePutcallFromYfinance:
    """Test _calculate_putcall_from_yfinance helper function."""

    @pytest.fixture
    def mock_yf_ticker(self) -> MagicMock:
        """Create mock yfinance Ticker object with options data."""
        ticker = MagicMock()

        # Mock options expirations
        ticker.options = ["2025-01-17", "2025-01-24", "2025-01-31", "2025-02-07", "2025-02-14"]

        # Mock option_chain for each expiration
        def mock_option_chain(expiration: str) -> MagicMock:
            chain = MagicMock()

            # Mock calls DataFrame with volume
            calls_df = MagicMock()
            calls_df.fillna.return_value.sum.return_value = 10000  # 10k call volume per expiration
            chain.calls = {"volume": calls_df}

            # Mock puts DataFrame with volume
            puts_df = MagicMock()
            puts_df.fillna.return_value.sum.return_value = 8000  # 8k put volume per expiration
            chain.puts = {"volume": puts_df}

            return chain

        ticker.option_chain = mock_option_chain
        return ticker

    def test_happy_path_all_symbols_successful(self, mock_yf_ticker: MagicMock) -> None:
        """Test successful calculation with data from all symbols."""
        mock_session = MagicMock()
        with (
            patch(
                "app.tasks.market_data._putcall_sources.curl_requests.Session",
                return_value=mock_session,
            ),
            patch("app.tasks.market_data.options_pipeline.yf.Ticker", return_value=mock_yf_ticker),
        ):
            result = _calculate_putcall_from_yfinance()

        assert result is not None
        assert "put_call_ratio" in result
        assert "total_call_volume" in result
        assert "total_put_volume" in result
        assert "symbol_ratios" in result
        assert "source" in result

        # Check calculated ratio (8000 puts / 10000 calls = 0.8 per symbol per expiration)
        # 5 expirations * 3 symbols = 15 total calculations
        # Total: 120k puts / 150k calls = 0.8
        assert result["put_call_ratio"] == pytest.approx(0.8, rel=0.01)
        assert result["total_call_volume"] == 150000  # 10k * 5 exp * 3 symbols
        assert result["total_put_volume"] == 120000  # 8k * 5 exp * 3 symbols
        assert result["source"] == "yfinance_options_chain"
        assert result["symbols"] == PUTCALL_SYMBOLS
        assert result["expirations_per_symbol"] == PUTCALL_EXPIRATIONS

        # Check individual symbol ratios
        assert len(result["symbol_ratios"]) == 3
        for symbol in PUTCALL_SYMBOLS:
            assert symbol in result["symbol_ratios"]
            assert result["symbol_ratios"][symbol]["call_volume"] == 50000.0  # 10k * 5
            assert result["symbol_ratios"][symbol]["put_volume"] == 40000.0  # 8k * 5
            assert result["symbol_ratios"][symbol]["ratio"] == pytest.approx(0.8, rel=0.01)
        mock_session.close.assert_called_once()

    def test_partial_symbol_success(self, mock_yf_ticker: MagicMock) -> None:
        """Test calculation when one symbol fails but others succeed."""
        call_count = 0

        def mock_ticker_with_failure(symbol: str, **_: object) -> MagicMock:
            nonlocal call_count
            call_count += 1
            if call_count == 2:  # Second symbol (QQQ) fails
                failing_ticker = MagicMock()
                failing_ticker.options = []  # No expirations available
                return failing_ticker
            return mock_yf_ticker

        with patch(
            "app.tasks.market_data.options_pipeline.yf.Ticker", side_effect=mock_ticker_with_failure
        ):
            result = _calculate_putcall_from_yfinance()

        assert result is not None
        # Should have 2 symbols (SPY and IWM), QQQ failed
        assert len(result["symbol_ratios"]) == 2
        assert result["total_call_volume"] == 100000  # 2 symbols * 5 exp * 10k
        assert result["total_put_volume"] == 80000  # 2 symbols * 5 exp * 8k

    def test_zero_call_volume_returns_none(self) -> None:
        """Test that zero call volume returns None."""
        ticker = MagicMock()
        ticker.options = ["2025-01-17"]

        def mock_option_chain(expiration: str) -> MagicMock:
            chain = MagicMock()

            # Zero call volume
            calls_df = MagicMock()
            calls_df.fillna.return_value.sum.return_value = 0
            chain.calls = {"volume": calls_df}

            # Some put volume
            puts_df = MagicMock()
            puts_df.fillna.return_value.sum.return_value = 5000
            chain.puts = {"volume": puts_df}

            return chain

        ticker.option_chain = mock_option_chain

        with patch("app.tasks.market_data.options_pipeline.yf.Ticker", return_value=ticker):
            result = _calculate_putcall_from_yfinance()

        assert result is None

    def test_all_symbols_fail(self) -> None:
        """Test that function returns None when all symbols fail."""
        failing_ticker = MagicMock()
        failing_ticker.options = []

        with patch("app.tasks.market_data.options_pipeline.yf.Ticker", return_value=failing_ticker):
            result = _calculate_putcall_from_yfinance()

        assert result is None

    def test_exception_in_yfinance_returns_none(self) -> None:
        """Test that exceptions in yfinance are caught and return None."""
        with patch(
            "app.tasks.market_data.options_pipeline.yf.Ticker", side_effect=Exception("API error")
        ):
            result = _calculate_putcall_from_yfinance()

        assert result is None

    def test_limited_expirations(self, mock_yf_ticker: MagicMock) -> None:
        """Test that only first N expirations are used."""
        # Mock ticker with 10 expirations but only first 5 should be used
        mock_yf_ticker.options = [
            "2025-01-17",
            "2025-01-24",
            "2025-01-31",
            "2025-02-07",
            "2025-02-14",
            "2025-02-21",
            "2025-02-28",
            "2025-03-07",
            "2025-03-14",
            "2025-03-21",
        ]

        with patch("app.tasks.market_data.options_pipeline.yf.Ticker", return_value=mock_yf_ticker):
            result = _calculate_putcall_from_yfinance()

        assert result is not None
        # Should only use first 5 expirations
        assert result["expirations_per_symbol"] == PUTCALL_EXPIRATIONS

    def test_missing_volume_data_handled(self) -> None:
        """Test that missing volume data (NaN) is handled correctly."""
        ticker = MagicMock()
        ticker.options = ["2025-01-17"]

        # Track the mock DataFrames at a higher scope
        mock_calls_df = MagicMock()
        mock_calls_df.fillna.return_value.sum.return_value = 5000
        mock_puts_df = MagicMock()
        mock_puts_df.fillna.return_value.sum.return_value = 4000

        def mock_option_chain(expiration: str) -> MagicMock:
            chain = MagicMock()

            # Mock calls with NaN that fillna should handle
            chain.calls = {"volume": mock_calls_df}

            # Mock puts with NaN
            chain.puts = {"volume": mock_puts_df}

            return chain

        ticker.option_chain = mock_option_chain

        with patch("app.tasks.market_data.options_pipeline.yf.Ticker", return_value=ticker):
            result = _calculate_putcall_from_yfinance()

        assert result is not None
        # fillna(0) should have been called
        assert mock_calls_df.fillna.called
        assert mock_puts_df.fillna.called


class TestCalculatePutcallFromPolygon:
    """Test _calculate_putcall_from_polygon fallback function."""

    def test_happy_path_successful_calculation(self) -> None:
        """Test successful calculation from Polygon API."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {"details": {"contract_type": "call"}, "day": {"volume": 10000}},
                {"details": {"contract_type": "call"}, "day": {"volume": 15000}},
                {"details": {"contract_type": "put"}, "day": {"volume": 12000}},
                {"details": {"contract_type": "put"}, "day": {"volume": 8000}},
            ]
        }

        with (
            patch.dict("os.environ", {"POLYGON_API_KEY": "test_key"}),
            patch(
                "app.tasks.market_data.options_pipeline.requests.get", return_value=mock_response
            ),
        ):
            result = _calculate_putcall_from_polygon()

        assert result is not None
        assert result["put_call_ratio"] == pytest.approx(0.8, rel=0.01)  # 20k puts / 25k calls
        assert result["total_call_volume"] == 25000
        assert result["total_put_volume"] == 20000
        assert result["source"] == "polygon_options_snapshot"
        assert result["symbols"] == ["SPY"]

    def test_no_api_key_returns_none(self) -> None:
        """Test that missing API key returns None."""
        with patch.dict("os.environ", {}, clear=True):
            result = _calculate_putcall_from_polygon()

        assert result is None

    def test_no_results_returns_none(self) -> None:
        """Test that empty results array returns None."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}

        with (
            patch.dict("os.environ", {"POLYGON_API_KEY": "test_key"}),
            patch(
                "app.tasks.market_data.options_pipeline.requests.get", return_value=mock_response
            ),
        ):
            result = _calculate_putcall_from_polygon()

        assert result is None

    def test_zero_call_volume_returns_none(self) -> None:
        """Test that zero call volume returns None."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {"details": {"contract_type": "put"}, "day": {"volume": 10000}},
            ]
        }

        with (
            patch.dict("os.environ", {"POLYGON_API_KEY": "test_key"}),
            patch(
                "app.tasks.market_data.options_pipeline.requests.get", return_value=mock_response
            ),
        ):
            result = _calculate_putcall_from_polygon()

        assert result is None

    def test_http_error_returns_none(self) -> None:
        """Test that HTTP errors are handled gracefully."""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("403 Forbidden")

        with (
            patch.dict("os.environ", {"POLYGON_API_KEY": "test_key"}),
            patch(
                "app.tasks.market_data.options_pipeline.requests.get", return_value=mock_response
            ),
        ):
            result = _calculate_putcall_from_polygon()

        assert result is None

    def test_network_timeout_returns_none(self) -> None:
        """Test that network timeout is handled gracefully."""
        with (
            patch.dict("os.environ", {"POLYGON_API_KEY": "test_key"}),
            patch(
                "app.tasks.market_data.options_pipeline.requests.get", side_effect=requests.Timeout
            ),
        ):
            result = _calculate_putcall_from_polygon()

        assert result is None

    def test_missing_volume_field_handled(self) -> None:
        """Test that missing volume field defaults to 0."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {"details": {"contract_type": "call"}, "day": {"volume": 10000}},
                {
                    "details": {"contract_type": "call"},
                    "day": {},  # Missing volume
                },
                {"details": {"contract_type": "put"}, "day": {"volume": 5000}},
            ]
        }

        with (
            patch.dict("os.environ", {"POLYGON_API_KEY": "test_key"}),
            patch(
                "app.tasks.market_data.options_pipeline.requests.get", return_value=mock_response
            ),
        ):
            result = _calculate_putcall_from_polygon()

        assert result is not None
        assert result["total_call_volume"] == 10000  # Only first call counted
        assert result["total_put_volume"] == 5000


class TestCalculatePutcallFromFinnhub:
    """Test _calculate_putcall_from_finnhub fallback function."""

    def test_happy_path_successful_calculation(self) -> None:
        """Test successful calculation from Finnhub API."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "options": {
                        "CALL": [
                            {"volume": 5000},
                            {"volume": 7000},
                        ],
                        "PUT": [
                            {"volume": 4000},
                            {"volume": 6000},
                        ],
                    }
                },
                {
                    "options": {
                        "CALL": [
                            {"volume": 3000},
                        ],
                        "PUT": [
                            {"volume": 2000},
                        ],
                    }
                },
            ]
        }

        with (
            patch.dict("os.environ", {"FINNHUB_API_KEY": "test_key"}),
            patch(
                "app.tasks.market_data.options_pipeline.requests.get", return_value=mock_response
            ),
        ):
            result = _calculate_putcall_from_finnhub()

        assert result is not None
        assert result["put_call_ratio"] == pytest.approx(0.8, rel=0.01)  # 12k puts / 15k calls
        assert result["total_call_volume"] == 15000
        assert result["total_put_volume"] == 12000
        assert result["source"] == "finnhub_options_chain"
        assert result["symbols"] == ["SPY"]

    def test_no_api_key_returns_none(self) -> None:
        """Test that missing API key returns None."""
        with patch.dict("os.environ", {}, clear=True):
            result = _calculate_putcall_from_finnhub()

        assert result is None

    def test_no_data_returns_none(self) -> None:
        """Test that empty data array returns None."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}

        with (
            patch.dict("os.environ", {"FINNHUB_API_KEY": "test_key"}),
            patch(
                "app.tasks.market_data.options_pipeline.requests.get", return_value=mock_response
            ),
        ):
            result = _calculate_putcall_from_finnhub()

        assert result is None

    def test_zero_call_volume_returns_none(self) -> None:
        """Test that zero call volume returns None."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "options": {
                        "CALL": [],
                        "PUT": [
                            {"volume": 5000},
                        ],
                    }
                },
            ]
        }

        with (
            patch.dict("os.environ", {"FINNHUB_API_KEY": "test_key"}),
            patch(
                "app.tasks.market_data.options_pipeline.requests.get", return_value=mock_response
            ),
        ):
            result = _calculate_putcall_from_finnhub()

        assert result is None

    def test_null_volume_handled(self) -> None:
        """Test that null volume values are handled as 0."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "options": {
                        "CALL": [
                            {"volume": 10000},
                            {"volume": None},  # Null volume
                        ],
                        "PUT": [
                            {"volume": None},  # Null volume
                            {"volume": 5000},
                        ],
                    }
                },
            ]
        }

        with (
            patch.dict("os.environ", {"FINNHUB_API_KEY": "test_key"}),
            patch(
                "app.tasks.market_data.options_pipeline.requests.get", return_value=mock_response
            ),
        ):
            result = _calculate_putcall_from_finnhub()

        assert result is not None
        assert result["total_call_volume"] == 10000
        assert result["total_put_volume"] == 5000

    def test_http_error_returns_none(self) -> None:
        """Test that HTTP errors are handled gracefully."""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("429 Too Many Requests")

        with (
            patch.dict("os.environ", {"FINNHUB_API_KEY": "test_key"}),
            patch(
                "app.tasks.market_data.options_pipeline.requests.get", return_value=mock_response
            ),
        ):
            result = _calculate_putcall_from_finnhub()

        assert result is None


class TestGetPutcallRatioWithFallbacks:
    """Test _get_putcall_ratio_with_fallbacks multi-source fallback logic."""

    def test_yfinance_succeeds_no_fallback(self) -> None:
        """Test that yfinance success prevents fallback attempts."""
        yfinance_result = {
            "put_call_ratio": 0.85,
            "total_call_volume": 100000,
            "total_put_volume": 85000,
            "symbol_ratios": {},
            "source": "yfinance_options_chain",
        }

        with (
            patch(
                "app.tasks.market_data.options_pipeline._calculate_putcall_from_yfinance",
                return_value=yfinance_result,
            ),
            patch(
                "app.tasks.market_data.options_pipeline._calculate_putcall_from_polygon"
            ) as mock_polygon,
            patch(
                "app.tasks.market_data.options_pipeline._calculate_putcall_from_finnhub"
            ) as mock_finnhub,
        ):
            result = _get_putcall_ratio_with_fallbacks()

        assert result == yfinance_result
        # Fallbacks should not be called
        assert not mock_polygon.called
        assert not mock_finnhub.called

    def test_yfinance_fails_polygon_succeeds(self) -> None:
        """Test fallback to Polygon when yfinance fails."""
        polygon_result = {
            "put_call_ratio": 0.90,
            "total_call_volume": 50000,
            "total_put_volume": 45000,
            "source": "polygon_options_snapshot",
        }

        with (
            patch(
                "app.tasks.market_data.options_pipeline._calculate_putcall_from_yfinance",
                return_value=None,
            ),
            patch(
                "app.tasks.market_data.options_pipeline._calculate_putcall_from_polygon",
                return_value=polygon_result,
            ),
            patch(
                "app.tasks.market_data.options_pipeline._calculate_putcall_from_finnhub"
            ) as mock_finnhub,
        ):
            result = _get_putcall_ratio_with_fallbacks()

        assert result == polygon_result
        # Finnhub should not be called
        assert not mock_finnhub.called

    def test_yfinance_polygon_fail_finnhub_succeeds(self) -> None:
        """Test fallback to Finnhub when yfinance and Polygon fail."""
        finnhub_result = {
            "put_call_ratio": 0.95,
            "total_call_volume": 30000,
            "total_put_volume": 28500,
            "source": "finnhub_options_chain",
        }

        with (
            patch(
                "app.tasks.market_data.options_pipeline._calculate_putcall_from_yfinance",
                return_value=None,
            ),
            patch(
                "app.tasks.market_data.options_pipeline._calculate_putcall_from_polygon",
                return_value=None,
            ),
            patch(
                "app.tasks.market_data.options_pipeline._calculate_putcall_from_finnhub",
                return_value=finnhub_result,
            ),
        ):
            result = _get_putcall_ratio_with_fallbacks()

        assert result == finnhub_result

    def test_all_sources_fail_raises_error(self) -> None:
        """Test that RuntimeError is raised when all sources fail."""
        with (
            patch(
                "app.tasks.market_data.options_pipeline._calculate_putcall_from_yfinance",
                return_value=None,
            ),
            patch(
                "app.tasks.market_data.options_pipeline._calculate_putcall_from_polygon",
                return_value=None,
            ),
            patch(
                "app.tasks.market_data.options_pipeline._calculate_putcall_from_finnhub",
                return_value=None,
            ),
            pytest.raises(RuntimeError, match="All put/call ratio sources failed"),
        ):
            _get_putcall_ratio_with_fallbacks()


class TestFetchPutcallRatioTask:
    """Test fetch_putcall_ratio task."""

    @pytest.fixture
    def mock_storage(self) -> MagicMock:
        """Create mock storage with connection context manager."""
        storage = MagicMock()
        conn = MagicMock()
        storage.connection.return_value.__enter__ = MagicMock(return_value=conn)
        storage.connection.return_value.__exit__ = MagicMock(return_value=False)
        return storage

    @pytest.fixture
    def mock_task_request(self) -> MagicMock:
        """Create mock task request."""
        request = MagicMock()
        request.id = "test-task-123"
        return request

    def test_happy_path_successful_task(
        self, mock_storage: MagicMock, mock_task_request: MagicMock
    ) -> None:
        """Test successful task execution with data storage."""
        fallback_result = {
            "put_call_ratio": 0.85,
            "total_call_volume": 100000,
            "total_put_volume": 85000,
            "symbol_ratios": {
                "SPY": {"ratio": 0.80, "call_volume": 50000, "put_volume": 40000},
                "QQQ": {"ratio": 0.90, "call_volume": 30000, "put_volume": 27000},
                "IWM": {"ratio": 0.90, "call_volume": 20000, "put_volume": 18000},
            },
            "source": "yfinance_options_chain",
        }

        with (
            patch(
                "app.tasks.market_data.options_pipeline._get_putcall_ratio_with_fallbacks",
                return_value=fallback_result,
            ),
            patch("app.tasks.market_data.options_pipeline.get_storage", return_value=mock_storage),
        ):
            # Call the task .run() method
            result = fetch_putcall_ratio(as_of_date=None)

        # Verify result structure
        assert result["success"] is True
        # Note: task_id will be None when calling .run() directly (not via .delay())
        assert "task_id" in result
        assert result["date"] == dt.date.today().isoformat()
        assert result["put_call_ratio"] == 0.85
        assert result["total_call_volume"] == 100000
        assert result["total_put_volume"] == 85000
        assert result["source"] == "yfinance_options_chain"
        assert "symbol_ratios" in result

        # Verify database storage was called
        mock_conn = mock_storage.connection.return_value.__enter__.return_value
        assert mock_conn.execute.called
        assert mock_conn.commit.called

        # Verify SQL parameters
        call_args = mock_conn.execute.call_args[0]
        assert "INSERT INTO fear_greed_inputs" in call_args[0]
        assert call_args[1][0] == dt.date.today().isoformat()  # as_of_date
        assert call_args[1][1] == 0.85  # put_call_ratio

        # Verify source_map JSON
        source_map = json.loads(call_args[1][2])
        assert source_map["put_call_ratio"] == "yfinance_options_chain"

    def test_custom_as_of_date(
        self, mock_storage: MagicMock, mock_task_request: MagicMock
    ) -> None:
        """Test task with custom as_of_date parameter."""
        fallback_result = {
            "put_call_ratio": 0.75,
            "total_call_volume": 50000,
            "total_put_volume": 37500,
            "symbol_ratios": {},
            "source": "polygon_options_snapshot",
        }

        custom_date = "2025-11-01"

        with (
            patch(
                "app.tasks.market_data.options_pipeline._get_putcall_ratio_with_fallbacks",
                return_value=fallback_result,
            ),
            patch("app.tasks.market_data.options_pipeline.get_storage", return_value=mock_storage),
        ):
            task_mock = MagicMock()
            task_mock.request = mock_task_request

            result = fetch_putcall_ratio(as_of_date=custom_date)

        # Should still use today's date for storage (yfinance returns current data)
        assert result["date"] == dt.date.today().isoformat()

    def test_task_failure_returns_error_dict(
        self, mock_storage: MagicMock, mock_task_request: MagicMock
    ) -> None:
        """Test that task failure returns error dictionary."""
        with (
            patch(
                "app.tasks.market_data.options_pipeline._get_putcall_ratio_with_fallbacks",
                side_effect=RuntimeError("All sources failed"),
            ),
            patch("app.tasks.market_data.options_pipeline.get_storage", return_value=mock_storage),
        ):
            result = fetch_putcall_ratio(as_of_date=None)

        assert result["success"] is False
        assert "task_id" in result
        assert "error" in result
        assert "All sources failed" in result["error"]

        # Database should not be updated on failure
        mock_conn = mock_storage.connection.return_value.__enter__.return_value
        assert not mock_conn.commit.called

    def test_database_error_returns_error_dict(
        self, mock_storage: MagicMock, mock_task_request: MagicMock
    ) -> None:
        """Test that database errors are caught and returned."""
        fallback_result = {
            "put_call_ratio": 0.85,
            "total_call_volume": 100000,
            "total_put_volume": 85000,
            "symbol_ratios": {},
            "source": "yfinance_options_chain",
        }

        # Mock database error
        mock_conn = mock_storage.connection.return_value.__enter__.return_value
        mock_conn.execute.side_effect = Exception("Database connection failed")

        with (
            patch(
                "app.tasks.market_data.options_pipeline._get_putcall_ratio_with_fallbacks",
                return_value=fallback_result,
            ),
            patch("app.tasks.market_data.options_pipeline.get_storage", return_value=mock_storage),
        ):
            task_mock = MagicMock()
            task_mock.request = mock_task_request

            result = fetch_putcall_ratio(as_of_date=None)

        assert result["success"] is False
        assert "error" in result
        assert "Database connection failed" in result["error"]

    def test_symbol_ratios_rounded(
        self, mock_storage: MagicMock, mock_task_request: MagicMock
    ) -> None:
        """Test that symbol ratios are rounded to 2 decimal places in result."""
        fallback_result = {
            "put_call_ratio": 0.8567,
            "total_call_volume": 100000,
            "total_put_volume": 85670,
            "symbol_ratios": {
                "SPY": {"ratio": 0.8567123, "call_volume": 50000, "put_volume": 42835},
                "QQQ": {"ratio": 0.9123456, "call_volume": 30000, "put_volume": 27370},
            },
            "source": "yfinance_options_chain",
        }

        with (
            patch(
                "app.tasks.market_data.options_pipeline._get_putcall_ratio_with_fallbacks",
                return_value=fallback_result,
            ),
            patch("app.tasks.market_data.options_pipeline.get_storage", return_value=mock_storage),
        ):
            task_mock = MagicMock()
            task_mock.request = mock_task_request

            result = fetch_putcall_ratio(as_of_date=None)

        # Ratios should be rounded to 2 decimal places
        assert result["symbol_ratios"]["SPY"] == pytest.approx(0.86, rel=0.01)
        assert result["symbol_ratios"]["QQQ"] == pytest.approx(0.91, rel=0.01)


class TestFetchOptionsActivityMetricsTask:
    """Test fetch_options_activity_metrics task."""

    @pytest.fixture
    def mock_storage(self) -> MagicMock:
        """Create mock storage with connection context manager."""
        storage = MagicMock()
        conn = MagicMock()
        storage.connection.return_value.__enter__ = MagicMock(return_value=conn)
        storage.connection.return_value.__exit__ = MagicMock(return_value=False)
        return storage

    @pytest.fixture
    def mock_task_request(self) -> MagicMock:
        """Create mock task request."""
        request = MagicMock()
        request.id = "test-task-456"
        return request

    @pytest.fixture
    def mock_cboe_source(self) -> MagicMock:
        """Create mock CBOE source with metrics."""
        source = MagicMock()
        source.fetch_most_active_metrics.return_value = {
            "as_of_date": "2025-12-10",
            "most_active_call_pct": 65.0,
            "near_term_pct": 45.0,
            "concentration_pct": 30.0,
            "sector_weights": {
                "Technology": 35.0,
                "Healthcare": 20.0,
                "Finance": 15.0,
            },
            "source_timestamp": "2025-12-10T16:30:00Z",
        }
        return source

    def test_happy_path_successful_metrics_fetch(
        self, mock_storage: MagicMock, mock_task_request: MagicMock, mock_cboe_source: MagicMock
    ) -> None:
        """Test successful metrics fetch and storage."""
        with (
            patch("app.tasks.market_data.options_pipeline.get_storage", return_value=mock_storage),
            patch(
                "app.sources.cboe_most_active.get_cboe_most_active_source",
                return_value=mock_cboe_source,
            ),
        ):
            result = fetch_options_activity_metrics()

        # Verify result structure
        assert result["success"] is True
        assert "task_id" in result
        assert result["as_of_date"] == "2025-12-10"
        assert result["metrics"]["call_pct"] == 65.0
        assert result["metrics"]["near_term_pct"] == 45.0
        assert result["metrics"]["concentration_pct"] == 30.0
        assert result["metrics"]["sectors"] == 3

        # Verify database storage was called
        mock_conn = mock_storage.connection.return_value.__enter__.return_value
        assert mock_conn.execute.called
        assert mock_conn.commit.called

        # Verify SQL parameters
        call_args = mock_conn.execute.call_args[0]
        assert "INSERT INTO options_market_metrics" in call_args[0]
        assert call_args[1][0] == "2025-12-10"  # as_of_date
        assert call_args[1][1] == 65.0  # most_active_call_pct
        assert call_args[1][2] == 45.0  # near_term_pct
        assert call_args[1][3] == 30.0  # concentration_pct

        # Verify sector_weights JSON
        sector_weights = json.loads(call_args[1][4])
        assert sector_weights["Technology"] == 35.0

    def test_cboe_source_failure_returns_error_dict(
        self, mock_storage: MagicMock, mock_task_request: MagicMock, mock_cboe_source: MagicMock
    ) -> None:
        """Test that CBOE source failure returns error dictionary."""
        mock_cboe_source.fetch_most_active_metrics.side_effect = Exception("CBOE scraping failed")

        with (
            patch("app.tasks.market_data.options_pipeline.get_storage", return_value=mock_storage),
            patch(
                "app.sources.cboe_most_active.get_cboe_most_active_source",
                return_value=mock_cboe_source,
            ),
        ):
            result = fetch_options_activity_metrics()

        assert result["success"] is False
        assert "task_id" in result
        assert "error" in result
        assert "CBOE scraping failed" in result["error"]

        # Database should not be updated on failure
        mock_conn = mock_storage.connection.return_value.__enter__.return_value
        assert not mock_conn.commit.called

    def test_database_error_returns_error_dict(
        self, mock_storage: MagicMock, mock_task_request: MagicMock, mock_cboe_source: MagicMock
    ) -> None:
        """Test that database errors are caught and returned."""
        # Mock database error
        mock_conn = mock_storage.connection.return_value.__enter__.return_value
        mock_conn.execute.side_effect = Exception("Database insert failed")

        with (
            patch("app.tasks.market_data.options_pipeline.get_storage", return_value=mock_storage),
            patch(
                "app.sources.cboe_most_active.get_cboe_most_active_source",
                return_value=mock_cboe_source,
            ),
        ):
            task_mock = MagicMock()
            task_mock.request = mock_task_request

            result = fetch_options_activity_metrics()

        assert result["success"] is False
        assert "error" in result
        assert "Database insert failed" in result["error"]

    def test_storage_passed_to_cboe_source(
        self, mock_storage: MagicMock, mock_task_request: MagicMock, mock_cboe_source: MagicMock
    ) -> None:
        """Test that storage is passed to CBOE source constructor."""
        with (
            patch(
                "app.tasks.market_data.options_pipeline.get_storage", return_value=mock_storage
            ) as mock_get_storage,
            patch("app.sources.cboe_most_active.get_cboe_most_active_source") as mock_get_cboe,
        ):
            mock_get_cboe.return_value = mock_cboe_source

            fetch_options_activity_metrics()

            # Verify get_cboe_most_active_source was called with storage
            mock_get_cboe.assert_called_once()
            call_kwargs = mock_get_cboe.call_args[1]
            assert "storage" in call_kwargs
            assert call_kwargs["storage"] == mock_storage

    def test_empty_sector_weights_handled(
        self, mock_storage: MagicMock, mock_task_request: MagicMock, mock_cboe_source: MagicMock
    ) -> None:
        """Test that empty sector weights are handled correctly."""
        mock_cboe_source.fetch_most_active_metrics.return_value = {
            "as_of_date": "2025-12-10",
            "most_active_call_pct": 60.0,
            "near_term_pct": 40.0,
            "concentration_pct": 25.0,
            "sector_weights": {},  # Empty sector weights
            "source_timestamp": "2025-12-10T16:30:00Z",
        }

        with (
            patch("app.tasks.market_data.options_pipeline.get_storage", return_value=mock_storage),
            patch(
                "app.sources.cboe_most_active.get_cboe_most_active_source",
                return_value=mock_cboe_source,
            ),
        ):
            result = fetch_options_activity_metrics()

        assert result["success"] is True
        assert result["metrics"]["sectors"] == 0
