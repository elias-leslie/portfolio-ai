"""Tests for multi-source price fetcher with all 6 sources.

Tests source initialization, API key detection, and failover behavior.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from app.portfolio.price_fetcher import PriceDataFetcher
from app.sources.alphavantage_source import AlphaVantageSource
from app.sources.finnhub_source import FinnhubSource
from app.sources.fmp_source import FMPSource
from app.sources.polygon_source import PolygonSource
from app.sources.twelvedata_source import TwelveDataSource
from app.sources.yfinance_source import YFinanceSource
from app.storage import DuckDBStorage


@pytest.fixture
def mock_storage() -> MagicMock:
    """Create a mock storage instance."""
    return MagicMock(spec=DuckDBStorage)


class TestSourceInitialization:
    """Test PriceDataFetcher source initialization logic."""

    def test_initializes_yfinance_only_without_api_keys(self, mock_storage: MagicMock) -> None:
        """Test that PriceDataFetcher initializes with YFinance only when no API keys available."""
        with patch.dict(os.environ, {}, clear=True):
            fetcher = PriceDataFetcher(mock_storage)

            # Should have exactly 1 source (YFinance)
            assert len(fetcher.multi_source_fetcher.sources) == 1
            assert isinstance(fetcher.multi_source_fetcher.sources[0], YFinanceSource)

    def test_initializes_all_sources_with_api_keys(self, mock_storage: MagicMock) -> None:
        """Test that PriceDataFetcher initializes all 6 sources when API keys are available."""
        env = {
            "TWELVEDATA_API_KEY": "test_twelvedata_key",
            "FMP_API_KEY": "test_fmp_key",
            "POLYGON_API_KEY": "test_polygon_key",
            "FINNHUB_API_KEY": "test_finnhub_key",
            "ALPHAVANTAGE_API_KEY": "test_alphavantage_key",
        }

        with patch.dict(os.environ, env, clear=True):
            fetcher = PriceDataFetcher(mock_storage)

            # Should have exactly 6 sources
            assert len(fetcher.multi_source_fetcher.sources) == 6

            # Check source types (order matters - should match priority)
            source_types = [type(s) for s in fetcher.multi_source_fetcher.sources]
            assert source_types == [
                YFinanceSource,
                TwelveDataSource,
                FMPSource,
                PolygonSource,
                FinnhubSource,
                AlphaVantageSource,
            ]

    def test_initializes_partial_sources_with_some_api_keys(self, mock_storage: MagicMock) -> None:
        """Test that PriceDataFetcher initializes only sources with available API keys."""
        env = {
            "POLYGON_API_KEY": "test_polygon_key",
            "FINNHUB_API_KEY": "test_finnhub_key",
        }

        with patch.dict(os.environ, env, clear=True):
            fetcher = PriceDataFetcher(mock_storage)

            # Should have YFinance + 2 sources with keys = 3 total
            assert len(fetcher.multi_source_fetcher.sources) == 3

            source_types = [type(s) for s in fetcher.multi_source_fetcher.sources]
            assert YFinanceSource in source_types
            assert PolygonSource in source_types
            assert FinnhubSource in source_types

    def test_has_api_key_returns_true_for_existing_key(self, mock_storage: MagicMock) -> None:
        """Test _has_api_key returns True when API key exists and is non-empty."""
        env = {"POLYGON_API_KEY": "test_key_value"}

        with patch.dict(os.environ, env, clear=True):
            fetcher = PriceDataFetcher(mock_storage)
            assert fetcher._has_api_key("POLYGON_API_KEY") is True

    def test_has_api_key_returns_false_for_missing_key(self, mock_storage: MagicMock) -> None:
        """Test _has_api_key returns False when API key does not exist."""
        with patch.dict(os.environ, {}, clear=True):
            fetcher = PriceDataFetcher(mock_storage)
            assert fetcher._has_api_key("POLYGON_API_KEY") is False

    def test_has_api_key_returns_false_for_empty_key(self, mock_storage: MagicMock) -> None:
        """Test _has_api_key returns False when API key is empty string."""
        env = {"POLYGON_API_KEY": ""}

        with patch.dict(os.environ, env, clear=True):
            fetcher = PriceDataFetcher(mock_storage)
            assert fetcher._has_api_key("POLYGON_API_KEY") is False
