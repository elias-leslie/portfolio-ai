"""Tests for multi-source price fetcher with all 6 sources.

Tests source initialization, API key detection, and failover behavior.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

import app.sources as sources_module
import app.sources.alphavantage_source as alphavantage_module
import app.sources.finnhub_source as finnhub_module
import app.sources.fmp_source as fmp_module
import app.sources.polygon_client as polygon_client_module
import app.sources.twelvedata_source as twelvedata_module
from app.portfolio.price_fetcher import PriceDataFetcher
from app.sources.alphavantage_source import AlphaVantageSource
from app.sources.finnhub_source import FinnhubSource
from app.sources.fmp_source import FMPSource
from app.sources.polygon_source import PolygonSource
from app.sources.twelvedata_source import TwelveDataSource
from app.sources.yfinance_source import YFinanceSource
from app.storage import PortfolioStorage


@pytest.fixture(autouse=True)
def reset_sources_cache() -> Generator[None, None, None]:
    """Reset the module-level sources cache and source client singletons before each test.

    initialize_data_sources() caches results globally, and each source module
    has a singleton client that persists between tests. Both must be cleared
    so each test exercises fresh initialization with its own env vars.
    """
    # Reset global sources cache
    sources_module._cached_sources = None
    # Reset per-source client singletons to prevent API key bleed between tests
    fmp_module._ClientState.client = None
    finnhub_module._ClientState.client = None
    twelvedata_module._ClientState.client = None
    polygon_client_module._ClientState.client = None
    alphavantage_module._ClientState.client = None
    yield
    # Cleanup after test
    sources_module._cached_sources = None
    fmp_module._ClientState.client = None
    finnhub_module._ClientState.client = None
    twelvedata_module._ClientState.client = None
    polygon_client_module._ClientState.client = None
    alphavantage_module._ClientState.client = None


@pytest.fixture
def mock_storage() -> MagicMock:
    """Create a mock storage instance."""
    return MagicMock(spec=PortfolioStorage)


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
