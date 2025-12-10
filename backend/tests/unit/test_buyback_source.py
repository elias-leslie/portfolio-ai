"""Unit tests for buyback data source.

Tests the buyback_source module for fetching share repurchase data
from yfinance cash flow statements.

FEAT-175: Share Buybacks
"""

from __future__ import annotations

import datetime as dt
from unittest.mock import MagicMock, Mock, patch

import pandas as pd
import pytest

from app.sources.buyback_source import (
    fetch_and_store_buybacks,
    fetch_buyback_data,
    store_buyback_data,
)


class TestFetchBuybackData:
    """Test fetch_buyback_data function."""

    @patch("app.sources.buyback_source.yf.Ticker")
    def test_fetch_buyback_data_happy_path(self, mock_ticker_class: MagicMock) -> None:
        """Test successful fetch with valid buyback data."""
        # Create mock cash flow DataFrame with repurchase data
        dates = [
            pd.Timestamp("2024-09-30"),
            pd.Timestamp("2024-06-30"),
            pd.Timestamp("2024-03-31"),
        ]
        # DataFrame has dates as columns, row names as index
        data = [
            [-5000000000, -4500000000, -3800000000],  # Repurchase row
            [100, 200, 300],  # Other row
        ]
        mock_cf = pd.DataFrame(
            data, index=["Repurchase Of Capital Stock", "Other Row"], columns=dates
        )

        mock_ticker = MagicMock()
        mock_ticker.quarterly_cashflow = mock_cf
        mock_ticker_class.return_value = mock_ticker

        result = fetch_buyback_data("AAPL")

        assert len(result) == 3
        assert result[0]["symbol"] == "AAPL"
        assert result[0]["action_type"] == "buyback"
        assert result[0]["action_date"] == dt.date(2024, 9, 30)
        assert result[0]["repurchase_amount"] == 5000000000
        assert result[0]["source"] == "yfinance"

        assert result[1]["action_date"] == dt.date(2024, 6, 30)
        assert result[1]["repurchase_amount"] == 4500000000

        assert result[2]["action_date"] == dt.date(2024, 3, 31)
        assert result[2]["repurchase_amount"] == 3800000000

    @patch("app.sources.buyback_source.yf.Ticker")
    def test_fetch_buyback_data_no_cashflow_data(self, mock_ticker_class: MagicMock) -> None:
        """Test when ticker has no cash flow data."""
        mock_ticker = MagicMock()
        mock_ticker.quarterly_cashflow = None
        mock_ticker_class.return_value = mock_ticker

        result = fetch_buyback_data("INVALID")

        assert result == []

    @patch("app.sources.buyback_source.yf.Ticker")
    def test_fetch_buyback_data_empty_cashflow(self, mock_ticker_class: MagicMock) -> None:
        """Test when cash flow DataFrame is empty."""
        mock_ticker = MagicMock()
        mock_ticker.quarterly_cashflow = pd.DataFrame()
        mock_ticker_class.return_value = mock_ticker

        result = fetch_buyback_data("SMALLCAP")

        assert result == []

    @patch("app.sources.buyback_source.yf.Ticker")
    def test_fetch_buyback_data_no_repurchase_row(self, mock_ticker_class: MagicMock) -> None:
        """Test when cash flow has no repurchase data."""
        dates = [pd.Timestamp("2024-09-30")]
        data = [
            [10000000000],  # Operating Cash Flow
            [-2000000000],  # Capital Expenditure
        ]
        mock_cf = pd.DataFrame(
            data, index=["Operating Cash Flow", "Capital Expenditure"], columns=dates
        )

        mock_ticker = MagicMock()
        mock_ticker.quarterly_cashflow = mock_cf
        mock_ticker_class.return_value = mock_ticker

        result = fetch_buyback_data("NOREPURCHASE")

        assert result == []

    @patch("app.sources.buyback_source.yf.Ticker")
    def test_fetch_buyback_data_filters_positive_values(self, mock_ticker_class: MagicMock) -> None:
        """Test that positive values (cash inflows) are filtered out."""
        dates = [
            pd.Timestamp("2024-09-30"),
            pd.Timestamp("2024-06-30"),
            pd.Timestamp("2024-03-31"),
        ]
        data = [
            [-5000000000, 100000, -3800000000],  # Repurchase row (mixed positive/negative)
        ]
        mock_cf = pd.DataFrame(data, index=["Repurchase Of Capital Stock"], columns=dates)

        mock_ticker = MagicMock()
        mock_ticker.quarterly_cashflow = mock_cf
        mock_ticker_class.return_value = mock_ticker

        result = fetch_buyback_data("MIXED")

        # Only negative values (actual repurchases) should be included
        assert len(result) == 2
        assert result[0]["action_date"] == dt.date(2024, 9, 30)
        assert result[1]["action_date"] == dt.date(2024, 3, 31)

    @patch("app.sources.buyback_source.yf.Ticker")
    def test_fetch_buyback_data_filters_null_values(self, mock_ticker_class: MagicMock) -> None:
        """Test that null values are filtered out."""
        dates = [
            pd.Timestamp("2024-09-30"),
            pd.Timestamp("2024-06-30"),
            pd.Timestamp("2024-03-31"),
        ]
        data = [
            [-5000000000, None, -3800000000],  # Repurchase row with null
        ]
        mock_cf = pd.DataFrame(data, index=["Repurchase Of Capital Stock"], columns=dates)

        mock_ticker = MagicMock()
        mock_ticker.quarterly_cashflow = mock_cf
        mock_ticker_class.return_value = mock_ticker

        result = fetch_buyback_data("NULLS")

        # Only non-null values should be included
        assert len(result) == 2
        assert result[0]["action_date"] == dt.date(2024, 9, 30)
        assert result[1]["action_date"] == dt.date(2024, 3, 31)

    @patch("app.sources.buyback_source.yf.Ticker")
    def test_fetch_buyback_data_case_insensitive_repurchase(
        self, mock_ticker_class: MagicMock
    ) -> None:
        """Test that repurchase row matching is case-insensitive."""
        dates = [pd.Timestamp("2024-09-30")]
        cf_data = {
            "REPURCHASE OF STOCK": [-5000000000],
        }
        mock_cf = pd.DataFrame(cf_data, index=["REPURCHASE OF STOCK"])
        mock_cf.columns = dates

        mock_ticker = MagicMock()
        mock_ticker.quarterly_cashflow = mock_cf
        mock_ticker_class.return_value = mock_ticker

        result = fetch_buyback_data("UPPERCASE")

        assert len(result) == 1
        assert result[0]["repurchase_amount"] == 5000000000

    @patch("app.sources.buyback_source.yf.Ticker")
    def test_fetch_buyback_data_api_error(self, mock_ticker_class: MagicMock) -> None:
        """Test graceful handling of API errors."""
        mock_ticker_class.side_effect = Exception("API rate limit exceeded")

        result = fetch_buyback_data("ERROR")

        assert result == []

    @patch("app.sources.buyback_source.yf.Ticker")
    def test_fetch_buyback_data_stores_as_positive(self, mock_ticker_class: MagicMock) -> None:
        """Test that negative cash flow values are stored as positive amounts."""
        dates = [pd.Timestamp("2024-09-30")]
        cf_data = {
            "Repurchase Of Capital Stock": [-1234567890],
        }
        mock_cf = pd.DataFrame(cf_data, index=["Repurchase Of Capital Stock"])
        mock_cf.columns = dates

        mock_ticker = MagicMock()
        mock_ticker.quarterly_cashflow = mock_cf
        mock_ticker_class.return_value = mock_ticker

        result = fetch_buyback_data("TEST")

        # Negative value should be stored as positive
        assert result[0]["repurchase_amount"] == 1234567890


class TestStoreBuybackData:
    """Test store_buyback_data function."""

    def test_store_buyback_data_empty_list(self) -> None:
        """Test storing empty list returns 0."""
        mock_storage = MagicMock()

        result = store_buyback_data(mock_storage, [])

        assert result == 0
        mock_storage.connection.assert_not_called()

    def test_store_buyback_data_single_record(self) -> None:
        """Test storing single buyback record."""
        mock_conn = MagicMock()
        mock_storage = MagicMock()
        mock_storage.connection.return_value.__enter__.return_value = mock_conn

        buybacks = [
            {
                "symbol": "AAPL",
                "action_type": "buyback",
                "action_date": dt.date(2024, 9, 30),
                "repurchase_amount": 5000000000,
                "source": "yfinance",
            }
        ]

        result = store_buyback_data(mock_storage, buybacks)

        assert result == 1
        mock_conn.execute.assert_called_once()
        mock_conn.commit.assert_called_once()

        # Verify SQL contains UPSERT logic
        sql_call = mock_conn.execute.call_args[0][0]
        assert "INSERT INTO corporate_actions" in sql_call
        assert "ON CONFLICT" in sql_call
        assert "DO UPDATE SET" in sql_call

    def test_store_buyback_data_multiple_records(self) -> None:
        """Test storing multiple buyback records."""
        mock_conn = MagicMock()
        mock_storage = MagicMock()
        mock_storage.connection.return_value.__enter__.return_value = mock_conn

        buybacks = [
            {
                "symbol": "AAPL",
                "action_type": "buyback",
                "action_date": dt.date(2024, 9, 30),
                "repurchase_amount": 5000000000,
                "source": "yfinance",
            },
            {
                "symbol": "AAPL",
                "action_type": "buyback",
                "action_date": dt.date(2024, 6, 30),
                "repurchase_amount": 4500000000,
                "source": "yfinance",
            },
            {
                "symbol": "MSFT",
                "action_type": "buyback",
                "action_date": dt.date(2024, 9, 30),
                "repurchase_amount": 3000000000,
                "source": "yfinance",
            },
        ]

        result = store_buyback_data(mock_storage, buybacks)

        assert result == 3
        assert mock_conn.execute.call_count == 3
        mock_conn.commit.assert_called_once()

    def test_store_buyback_data_upsert_behavior(self) -> None:
        """Test that SQL uses ON CONFLICT for upsert behavior."""
        mock_conn = MagicMock()
        mock_storage = MagicMock()
        mock_storage.connection.return_value.__enter__.return_value = mock_conn

        buybacks = [
            {
                "symbol": "AAPL",
                "action_type": "buyback",
                "action_date": dt.date(2024, 9, 30),
                "repurchase_amount": 5000000000,
                "source": "yfinance",
            }
        ]

        store_buyback_data(mock_storage, buybacks)

        sql_call = mock_conn.execute.call_args[0][0]
        # Verify UPSERT structure
        assert "ON CONFLICT (symbol, action_type, action_date)" in sql_call
        assert "repurchase_amount = EXCLUDED.repurchase_amount" in sql_call
        assert "source = EXCLUDED.source" in sql_call
        assert "updated_at = NOW()" in sql_call

    def test_store_buyback_data_parameters(self) -> None:
        """Test that correct parameters are passed to SQL."""
        mock_conn = MagicMock()
        mock_storage = MagicMock()
        mock_storage.connection.return_value.__enter__.return_value = mock_conn

        buybacks = [
            {
                "symbol": "TSLA",
                "action_type": "buyback",
                "action_date": dt.date(2024, 12, 31),
                "repurchase_amount": 123456789,
                "source": "yfinance",
            }
        ]

        store_buyback_data(mock_storage, buybacks)

        # Verify parameters passed to execute
        call_params = mock_conn.execute.call_args[0][1]
        assert call_params[0] == "TSLA"
        assert call_params[1] == "buyback"
        assert call_params[2] == dt.date(2024, 12, 31)
        assert call_params[3] == 123456789
        assert call_params[4] == "yfinance"


class TestFetchAndStoreBuybacks:
    """Test fetch_and_store_buybacks function."""

    @patch("app.sources.buyback_source.fetch_buyback_data")
    @patch("app.sources.buyback_source.store_buyback_data")
    def test_fetch_and_store_single_symbol(
        self,
        mock_store: MagicMock,
        mock_fetch: MagicMock,
    ) -> None:
        """Test fetching and storing for single symbol."""
        mock_storage = MagicMock()
        mock_fetch.return_value = [
            {
                "symbol": "AAPL",
                "action_type": "buyback",
                "action_date": dt.date(2024, 9, 30),
                "repurchase_amount": 5000000000,
                "source": "yfinance",
            }
        ]
        mock_store.return_value = 1

        result = fetch_and_store_buybacks(mock_storage, ["AAPL"])

        assert result["symbols_processed"] == 1
        assert result["records_stored"] == 1
        assert result["failed_symbols"] == []
        mock_fetch.assert_called_once_with("AAPL")
        mock_store.assert_called_once()

    @patch("app.sources.buyback_source.fetch_buyback_data")
    @patch("app.sources.buyback_source.store_buyback_data")
    def test_fetch_and_store_multiple_symbols(
        self,
        mock_store: MagicMock,
        mock_fetch: MagicMock,
    ) -> None:
        """Test fetching and storing for multiple symbols."""
        mock_storage = MagicMock()
        mock_fetch.side_effect = [
            [
                {
                    "symbol": "AAPL",
                    "action_type": "buyback",
                    "action_date": dt.date(2024, 9, 30),
                    "repurchase_amount": 5000000000,
                    "source": "yfinance",
                }
            ],
            [
                {
                    "symbol": "MSFT",
                    "action_type": "buyback",
                    "action_date": dt.date(2024, 9, 30),
                    "repurchase_amount": 3000000000,
                    "source": "yfinance",
                }
            ],
            [
                {
                    "symbol": "GOOGL",
                    "action_type": "buyback",
                    "action_date": dt.date(2024, 9, 30),
                    "repurchase_amount": 2000000000,
                    "source": "yfinance",
                }
            ],
        ]
        mock_store.side_effect = [1, 1, 1]

        result = fetch_and_store_buybacks(mock_storage, ["AAPL", "MSFT", "GOOGL"])

        assert result["symbols_processed"] == 3
        assert result["records_stored"] == 3
        assert result["failed_symbols"] == []
        assert mock_fetch.call_count == 3
        assert mock_store.call_count == 3

    @patch("app.sources.buyback_source.fetch_buyback_data")
    @patch("app.sources.buyback_source.store_buyback_data")
    def test_fetch_and_store_no_data_for_symbol(
        self,
        mock_store: MagicMock,
        mock_fetch: MagicMock,
    ) -> None:
        """Test when symbol has no buyback data."""
        mock_storage = MagicMock()
        mock_fetch.return_value = []

        result = fetch_and_store_buybacks(mock_storage, ["NOBUYBACK"])

        assert result["symbols_processed"] == 1
        assert result["records_stored"] == 0
        assert result["failed_symbols"] == []
        mock_fetch.assert_called_once()
        mock_store.assert_not_called()

    @patch("app.sources.buyback_source.fetch_buyback_data")
    @patch("app.sources.buyback_source.store_buyback_data")
    def test_fetch_and_store_partial_failures(
        self,
        mock_store: MagicMock,
        mock_fetch: MagicMock,
    ) -> None:
        """Test handling of partial failures across multiple symbols."""
        mock_storage = MagicMock()
        mock_fetch.side_effect = [
            [
                {
                    "symbol": "AAPL",
                    "action_type": "buyback",
                    "action_date": dt.date(2024, 9, 30),
                    "repurchase_amount": 5000000000,
                    "source": "yfinance",
                }
            ],
            Exception("API error for FAIL1"),
            [
                {
                    "symbol": "MSFT",
                    "action_type": "buyback",
                    "action_date": dt.date(2024, 9, 30),
                    "repurchase_amount": 3000000000,
                    "source": "yfinance",
                }
            ],
            Exception("API error for FAIL2"),
        ]
        mock_store.side_effect = [1, 1]

        result = fetch_and_store_buybacks(mock_storage, ["AAPL", "FAIL1", "MSFT", "FAIL2"])

        assert result["symbols_processed"] == 4
        assert result["records_stored"] == 2
        assert len(result["failed_symbols"]) == 2
        assert "FAIL1" in result["failed_symbols"]
        assert "FAIL2" in result["failed_symbols"]

    @patch("app.sources.buyback_source.fetch_buyback_data")
    @patch("app.sources.buyback_source.store_buyback_data")
    def test_fetch_and_store_storage_error(
        self,
        mock_store: MagicMock,
        mock_fetch: MagicMock,
    ) -> None:
        """Test handling of storage errors."""
        mock_storage = MagicMock()
        mock_fetch.return_value = [
            {
                "symbol": "AAPL",
                "action_type": "buyback",
                "action_date": dt.date(2024, 9, 30),
                "repurchase_amount": 5000000000,
                "source": "yfinance",
            }
        ]
        mock_store.side_effect = Exception("Database connection error")

        result = fetch_and_store_buybacks(mock_storage, ["AAPL"])

        assert result["symbols_processed"] == 1
        assert result["records_stored"] == 0
        assert "AAPL" in result["failed_symbols"]

    @patch("app.sources.buyback_source.fetch_buyback_data")
    @patch("app.sources.buyback_source.store_buyback_data")
    def test_fetch_and_store_empty_symbols_list(
        self,
        mock_store: MagicMock,
        mock_fetch: MagicMock,
    ) -> None:
        """Test with empty symbols list."""
        mock_storage = MagicMock()

        result = fetch_and_store_buybacks(mock_storage, [])

        assert result["symbols_processed"] == 0
        assert result["records_stored"] == 0
        assert result["failed_symbols"] == []
        mock_fetch.assert_not_called()
        mock_store.assert_not_called()


class TestCeleryTask:
    """Test fetch_corporate_actions Celery task."""

    @patch("app.tasks.market_data.corporate_actions_pipeline._get_watchlist_symbols")
    @patch("app.tasks.market_data.corporate_actions_pipeline.fetch_and_store_buybacks")
    @patch("app.tasks.market_data.corporate_actions_pipeline.get_storage")
    def test_fetch_corporate_actions_with_symbols(
        self,
        mock_get_storage: MagicMock,
        mock_fetch_store: MagicMock,
        mock_get_watchlist: MagicMock,
    ) -> None:
        """Test task with explicit symbols list."""
        from app.tasks.market_data.corporate_actions_pipeline import fetch_corporate_actions

        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        mock_fetch_store.return_value = {
            "symbols_processed": 2,
            "records_stored": 5,
            "failed_symbols": [],
        }

        result = fetch_corporate_actions(symbols=["AAPL", "MSFT"])

        assert result["success"] is True
        assert result["symbols_processed"] == 2
        assert result["records_stored"] == 5
        assert "date" in result
        mock_get_watchlist.assert_not_called()
        mock_fetch_store.assert_called_once_with(mock_storage, ["AAPL", "MSFT"])

    @patch("app.tasks.market_data.corporate_actions_pipeline._get_watchlist_symbols")
    @patch("app.tasks.market_data.corporate_actions_pipeline.fetch_and_store_buybacks")
    @patch("app.tasks.market_data.corporate_actions_pipeline.get_storage")
    def test_fetch_corporate_actions_uses_watchlist(
        self,
        mock_get_storage: MagicMock,
        mock_fetch_store: MagicMock,
        mock_get_watchlist: MagicMock,
    ) -> None:
        """Test task uses watchlist when no symbols provided."""
        from app.tasks.market_data.corporate_actions_pipeline import fetch_corporate_actions

        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        mock_get_watchlist.return_value = ["AAPL", "MSFT", "GOOGL"]
        mock_fetch_store.return_value = {
            "symbols_processed": 3,
            "records_stored": 8,
            "failed_symbols": [],
        }

        result = fetch_corporate_actions(symbols=None)

        assert result["success"] is True
        assert result["symbols_processed"] == 3
        assert result["records_stored"] == 8
        mock_get_watchlist.assert_called_once()
        mock_fetch_store.assert_called_once_with(mock_storage, ["AAPL", "MSFT", "GOOGL"])

    @patch("app.tasks.market_data.corporate_actions_pipeline._get_watchlist_symbols")
    @patch("app.tasks.market_data.corporate_actions_pipeline.fetch_and_store_buybacks")
    @patch("app.tasks.market_data.corporate_actions_pipeline.get_storage")
    def test_fetch_corporate_actions_empty_symbols(
        self,
        mock_get_storage: MagicMock,
        mock_fetch_store: MagicMock,
        mock_get_watchlist: MagicMock,
    ) -> None:
        """Test task with empty symbols list."""
        from app.tasks.market_data.corporate_actions_pipeline import fetch_corporate_actions

        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        mock_get_watchlist.return_value = []

        result = fetch_corporate_actions(symbols=None)

        assert result["success"] is True
        assert result["message"] == "No symbols to process"
        assert result["records_stored"] == 0
        mock_fetch_store.assert_not_called()

    @patch("app.tasks.market_data.corporate_actions_pipeline._get_watchlist_symbols")
    @patch("app.tasks.market_data.corporate_actions_pipeline.fetch_and_store_buybacks")
    @patch("app.tasks.market_data.corporate_actions_pipeline.get_storage")
    def test_fetch_corporate_actions_with_failures(
        self,
        mock_get_storage: MagicMock,
        mock_fetch_store: MagicMock,
        mock_get_watchlist: MagicMock,
    ) -> None:
        """Test task reports partial failures correctly."""
        from app.tasks.market_data.corporate_actions_pipeline import fetch_corporate_actions

        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        mock_fetch_store.return_value = {
            "symbols_processed": 5,
            "records_stored": 8,
            "failed_symbols": ["FAIL1", "FAIL2"],
        }

        result = fetch_corporate_actions.__wrapped__(
            mock_task, ["AAPL", "FAIL1", "MSFT", "FAIL2", "GOOGL"]
        )

        assert result["success"] is True
        assert result["symbols_processed"] == 5
        assert result["records_stored"] == 8
        assert len(result["failed_symbols"]) == 2

    @patch("app.tasks.market_data.corporate_actions_pipeline._get_watchlist_symbols")
    @patch("app.tasks.market_data.corporate_actions_pipeline.fetch_and_store_buybacks")
    @patch("app.tasks.market_data.corporate_actions_pipeline.get_storage")
    def test_fetch_corporate_actions_exception_handling(
        self,
        mock_get_storage: MagicMock,
        mock_fetch_store: MagicMock,
        mock_get_watchlist: MagicMock,
    ) -> None:
        """Test task handles exceptions gracefully."""
        from app.tasks.market_data.corporate_actions_pipeline import fetch_corporate_actions

        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        mock_fetch_store.side_effect = Exception("Database connection failed")

        result = fetch_corporate_actions(symbols=["AAPL"])

        assert result["success"] is False
        assert "error" in result
        assert "Database connection failed" in result["error"]

    @patch("app.tasks.market_data.corporate_actions_pipeline._get_watchlist_symbols")
    @patch("app.tasks.market_data.corporate_actions_pipeline.get_storage")
    def test_fetch_corporate_actions_includes_date(
        self,
        mock_get_storage: MagicMock,
        mock_get_watchlist: MagicMock,
    ) -> None:
        """Test task result includes execution date."""
        from app.tasks.market_data.corporate_actions_pipeline import fetch_corporate_actions

        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        mock_get_watchlist.return_value = []

        with patch("app.tasks.market_data.corporate_actions_pipeline.dt.date") as mock_date:
            mock_date.today.return_value = dt.date(2024, 12, 10)
            result = fetch_corporate_actions(symbols=None)

        assert result["date"] == "2024-12-10"
