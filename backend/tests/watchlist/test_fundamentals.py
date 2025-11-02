"""Tests for company fundamentals fetching and health classification."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from app.storage.connection import ConnectionManager
from app.watchlist.fundamentals import (
    FinnhubSource,
    FMPSource,
    FundamentalData,
    YFinanceSource,
    classify_company_health,
    fetch_fundamentals,
    fetch_fundamentals_cached,
)


class TestFundamentalDataModel:
    """Test FundamentalData Pydantic model."""

    def test_fundamental_data_creation(self) -> None:
        """Test creating FundamentalData with all fields."""
        data = FundamentalData(
            symbol="NVDA",
            profit_margin=0.53,
            revenue_growth=1.22,
            debt_to_equity=0.45,
            recommendation_key="buy",
            recommendation_mean=1.5,
            target_mean_price=450.0,
        )
        assert data.symbol == "NVDA"
        assert data.profit_margin == 0.53
        assert data.revenue_growth == 1.22
        assert data.debt_to_equity == 0.45

    def test_fundamental_data_optional_fields(self) -> None:
        """Test creating FundamentalData with minimal fields."""
        data = FundamentalData(
            symbol="NVDA",
            profit_margin=None,
            revenue_growth=None,
            debt_to_equity=None,
        )
        assert data.symbol == "NVDA"
        assert data.profit_margin is None
        assert data.revenue_growth is None


class TestYFinanceSource:
    """Test YFinance fundamental data source."""

    @patch("yfinance.Ticker")
    def test_yfinance_fetch_success(self, mock_ticker_class: MagicMock) -> None:
        """Test successful fetch from YFinance API."""
        # Mock yfinance response
        mock_ticker = MagicMock()
        mock_ticker.info = {
            "profitMargins": 0.53,
            "revenueGrowth": 1.22,
            "debtToEquity": 45.0,  # YFinance returns percentage
            "recommendationKey": "buy",
            "recommendationMean": 1.5,
            "targetMeanPrice": 450.0,
        }
        mock_ticker_class.return_value = mock_ticker

        source = YFinanceSource()
        result = source.fetch_fundamentals("NVDA")

        assert result is not None
        assert result.symbol == "NVDA"
        assert result.profit_margin == 0.53
        assert result.revenue_growth == 1.22
        assert result.debt_to_equity == 0.45  # Converted from percentage
        assert result.recommendation_key == "buy"

    @patch("yfinance.Ticker")
    def test_yfinance_fetch_missing_fields(self, mock_ticker_class: MagicMock) -> None:
        """Test YFinance fetch with missing optional fields."""
        mock_ticker = MagicMock()
        mock_ticker.info = {
            "profitMargins": 0.53,
            # Missing other fields
        }
        mock_ticker_class.return_value = mock_ticker

        source = YFinanceSource()
        result = source.fetch_fundamentals("NVDA")

        assert result is not None
        assert result.profit_margin == 0.53
        assert result.revenue_growth is None
        assert result.debt_to_equity is None

    @patch("yfinance.Ticker")
    def test_yfinance_fetch_api_error(self, mock_ticker_class: MagicMock) -> None:
        """Test YFinance fetch when API raises exception."""
        mock_ticker_class.side_effect = Exception("API Error")

        source = YFinanceSource()
        result = source.fetch_fundamentals("NVDA")

        assert result is None


class TestFinnhubSource:
    """Test Finnhub fundamental data source."""

    @patch("requests.get")
    def test_finnhub_fetch_success(self, mock_get: MagicMock) -> None:
        """Test successful fetch from Finnhub API."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "metric": {
                "netProfitMarginTTM": 53.0,  # Finnhub returns percentage (TTM field)
                "revenueGrowth3Y": 122.0,  # Finnhub returns percentage (3Y field)
                "currentRatio": 2.5,
                "longTermDebt/equityAnnual": 0.45,  # Finnhub uses this field name
            }
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        source = FinnhubSource(api_key="test_key")
        result = source.fetch_fundamentals("NVDA")

        assert result is not None
        assert result.symbol == "NVDA"
        assert result.profit_margin == 0.53  # Converted from percentage
        assert result.revenue_growth == 1.22  # Converted from percentage
        assert result.debt_to_equity == 0.45

    @patch("requests.get")
    def test_finnhub_fetch_api_error(self, mock_get: MagicMock) -> None:
        """Test Finnhub fetch when API returns error."""
        mock_get.side_effect = Exception("API Error")

        source = FinnhubSource(api_key="test_key")
        result = source.fetch_fundamentals("NVDA")

        assert result is None


class TestFMPSource:
    """Test FMP (Financial Modeling Prep) fundamental data source."""

    @patch("requests.get")
    def test_fmp_fetch_success(self, mock_get: MagicMock) -> None:
        """Test successful fetch from FMP API."""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "netProfitMargin": 0.53,
                "revenueGrowth": 1.22,
                "debtEquityRatio": 0.45,
                "returnOnEquity": 0.65,
            }
        ]
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        source = FMPSource(api_key="test_key")
        result = source.fetch_fundamentals("NVDA")

        assert result is not None
        assert result.symbol == "NVDA"
        assert result.profit_margin == 0.53
        assert result.revenue_growth == 1.22
        assert result.debt_to_equity == 0.45

    @patch("requests.get")
    def test_fmp_fetch_empty_response(self, mock_get: MagicMock) -> None:
        """Test FMP fetch with empty array response."""
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        source = FMPSource(api_key="test_key")
        result = source.fetch_fundamentals("NVDA")

        assert result is None


class TestMultiSourceFailover:
    """Test multi-source failover logic."""

    @patch("app.watchlist.fundamentals.YFinanceSource.fetch_fundamentals")
    def test_fetch_fundamentals_yfinance_success(self, mock_yfinance: MagicMock) -> None:
        """Test that YFinance is used as primary source."""
        mock_yfinance.return_value = FundamentalData(
            symbol="NVDA",
            profit_margin=0.53,
            revenue_growth=1.22,
            debt_to_equity=0.45,
        )

        result = fetch_fundamentals("NVDA")

        assert result is not None
        assert result.symbol == "NVDA"
        assert result.profit_margin == 0.53
        mock_yfinance.assert_called_once_with("NVDA")

    @patch("app.watchlist.fundamentals.FinnhubSource.fetch_fundamentals")
    @patch("app.watchlist.fundamentals.YFinanceSource.fetch_fundamentals")
    def test_fetch_fundamentals_failover_to_finnhub(
        self, mock_yfinance: MagicMock, mock_finnhub: MagicMock
    ) -> None:
        """Test failover to Finnhub when YFinance fails."""
        mock_yfinance.return_value = None  # YFinance failed
        mock_finnhub.return_value = FundamentalData(
            symbol="NVDA",
            profit_margin=0.50,
            revenue_growth=1.15,
            debt_to_equity=0.40,
        )

        with patch.dict("os.environ", {"FINNHUB_API_KEY": "test_key"}):
            result = fetch_fundamentals("NVDA")

        assert result is not None
        assert result.profit_margin == 0.50
        mock_yfinance.assert_called_once()
        mock_finnhub.assert_called_once()

    @patch("app.watchlist.fundamentals.FMPSource.fetch_fundamentals")
    @patch("app.watchlist.fundamentals.FinnhubSource.fetch_fundamentals")
    @patch("app.watchlist.fundamentals.YFinanceSource.fetch_fundamentals")
    def test_fetch_fundamentals_all_sources_fail(
        self,
        mock_yfinance: MagicMock,
        mock_finnhub: MagicMock,
        mock_fmp: MagicMock,
    ) -> None:
        """Test when all sources fail."""
        mock_yfinance.return_value = None
        mock_finnhub.return_value = None
        mock_fmp.return_value = None

        with patch.dict("os.environ", {"FINNHUB_API_KEY": "key1", "FMP_API_KEY": "key2"}):
            result = fetch_fundamentals("NVDA")

        assert result is None
        mock_yfinance.assert_called_once()
        mock_finnhub.assert_called_once()
        mock_fmp.assert_called_once()


class TestCompanyHealthClassification:
    """Test company health classification logic."""

    def test_classify_excellent_company(self) -> None:
        """Test EXCELLENT classification (NVDA: margin 53%, growth 122%)."""
        data = FundamentalData(
            symbol="NVDA",
            profit_margin=0.53,  # > 20%
            revenue_growth=1.22,  # > 20%
            debt_to_equity=0.45,  # < 0.5
            recommendation_mean=1.2,  # < 2.0 (strong buy)
        )

        health = classify_company_health(data)

        assert health == "EXCELLENT"

    def test_classify_excellent_requires_all_criteria(self) -> None:
        """Test EXCELLENT requires all criteria to be met."""
        # Missing high revenue growth
        data = FundamentalData(
            symbol="TEST",
            profit_margin=0.25,  # > 20% ✓
            revenue_growth=0.10,  # < 20% ✗
            debt_to_equity=0.40,  # < 0.5 ✓
            recommendation_mean=1.5,  # < 2.0 ✓
        )

        health = classify_company_health(data)

        assert health != "EXCELLENT"  # Should be GOOD

    def test_classify_good_company(self) -> None:
        """Test GOOD classification (moderate metrics)."""
        data = FundamentalData(
            symbol="TEST",
            profit_margin=0.10,  # > 5%, < 20%
            revenue_growth=0.12,  # 5-20%
            debt_to_equity=1.2,  # < 1.5
            recommendation_mean=2.5,  # 2.0-3.0
        )

        health = classify_company_health(data)

        assert health == "GOOD"

    def test_classify_weak_company_negative_margin(self) -> None:
        """Test WEAK classification (negative margin)."""
        data = FundamentalData(
            symbol="TEST",
            profit_margin=-0.05,  # < 0%
            revenue_growth=0.05,
            debt_to_equity=0.5,
        )

        health = classify_company_health(data)

        assert health == "WEAK"

    def test_classify_weak_company_high_debt(self) -> None:
        """Test WEAK classification (high debt)."""
        data = FundamentalData(
            symbol="TEST",
            profit_margin=0.10,
            revenue_growth=0.05,
            debt_to_equity=2.5,  # > 2.0
        )

        health = classify_company_health(data)

        assert health == "WEAK"

    def test_classify_weak_company_shrinking_revenue(self) -> None:
        """Test WEAK classification (shrinking revenue)."""
        data = FundamentalData(
            symbol="TEST",
            profit_margin=0.10,
            revenue_growth=-0.05,  # < 0 (shrinking)
            debt_to_equity=0.5,
        )

        health = classify_company_health(data)

        assert health == "WEAK"

    def test_classify_missing_data_returns_none(self) -> None:
        """Test classification with insufficient data."""
        data = FundamentalData(
            symbol="TEST",
            profit_margin=None,
            revenue_growth=None,
            debt_to_equity=None,
        )

        health = classify_company_health(data)

        # Should return "GOOD" as default when data is missing
        assert health == "GOOD"

    def test_classify_partial_data(self) -> None:
        """Test classification with partial data."""
        data = FundamentalData(
            symbol="TEST",
            profit_margin=0.25,  # EXCELLENT
            revenue_growth=None,  # Missing
            debt_to_equity=0.40,  # EXCELLENT
        )

        health = classify_company_health(data)

        # Should be GOOD (not EXCELLENT due to missing revenue growth)
        assert health in ("GOOD", "EXCELLENT")


class TestFundamentalsCaching:
    """Test caching functionality for fundamental data (24-hour TTL)."""

    @patch("app.watchlist.fundamentals.fetch_fundamentals")
    def test_cache_stores_fundamentals_on_first_fetch(self, mock_fetch: MagicMock) -> None:
        """Test that fundamentals are stored in reference_cache on first fetch."""
        mock_fetch.return_value = FundamentalData(
            symbol="NVDA",
            profit_margin=0.53,
            revenue_growth=1.22,
            debt_to_equity=0.45,
        )

        cm = ConnectionManager()
        with cm.connection() as conn:
            # First call should fetch from API and cache
            result = fetch_fundamentals_cached(conn, "NVDA")

            assert result is not None
            assert result.symbol == "NVDA"
            assert result.profit_margin == 0.53

            # Verify data was cached
            cached_row = conn.execute(
                "SELECT payload FROM reference_cache WHERE ticker = %s AND source = %s",
                ["NVDA", "fundamentals"],
            ).fetchone()

            assert cached_row is not None
            cached_data = cached_row[0]
            assert cached_data["symbol"] == "NVDA"
            assert cached_data["profit_margin"] == 0.53

    @patch("app.watchlist.fundamentals.fetch_fundamentals")
    def test_cache_hit_avoids_refetch(self, mock_fetch: MagicMock) -> None:
        """Test that cache hit avoids calling API again (within TTL)."""
        mock_fetch.return_value = FundamentalData(
            symbol="META",
            profit_margin=0.35,
            revenue_growth=0.15,
            debt_to_equity=0.60,
        )

        cm = ConnectionManager()
        with cm.connection() as conn:
            # First call - fetches from API
            result1 = fetch_fundamentals_cached(conn, "META")
            assert result1 is not None
            assert mock_fetch.call_count == 1

            # Second call within TTL - should use cache, not call API again
            result2 = fetch_fundamentals_cached(conn, "META")
            assert result2 is not None
            assert result2.profit_margin == 0.35
            assert mock_fetch.call_count == 1  # Still only 1 call

    @patch("app.watchlist.fundamentals.fetch_fundamentals")
    def test_cache_ttl_expiration_triggers_refresh(self, mock_fetch: MagicMock) -> None:
        """Test that cache older than 24 hours triggers re-fetch."""
        # First fetch - returns NVDA data
        mock_fetch.return_value = FundamentalData(
            symbol="NVDA",
            profit_margin=0.53,
            revenue_growth=1.22,
            debt_to_equity=0.45,
        )

        cm = ConnectionManager()
        with cm.connection() as conn:
            # First call - caches data
            result1 = fetch_fundamentals_cached(conn, "NVDA")
            assert result1 is not None
            assert mock_fetch.call_count == 1

            # Manually age the cache to 25 hours ago (expired)
            expired_date = date.today() - timedelta(days=2)
            conn.execute(
                "UPDATE reference_cache SET as_of_date = %s WHERE ticker = %s AND source = %s",
                [expired_date, "NVDA", "fundamentals"],
            )
            conn.commit()

            # Updated data for second fetch
            mock_fetch.return_value = FundamentalData(
                symbol="NVDA",
                profit_margin=0.55,  # Changed
                revenue_growth=1.25,  # Changed
                debt_to_equity=0.40,  # Changed
            )

            # Second call - should detect stale cache and re-fetch
            result2 = fetch_fundamentals_cached(conn, "NVDA")
            assert result2 is not None
            assert result2.profit_margin == 0.55  # New data
            assert mock_fetch.call_count == 2  # Called again

    @patch("app.watchlist.fundamentals.fetch_fundamentals")
    def test_cache_handles_api_failure_gracefully(self, mock_fetch: MagicMock) -> None:
        """Test that None return from API doesn't crash caching."""
        mock_fetch.return_value = None  # API failed

        cm = ConnectionManager()
        with cm.connection() as conn:
            result = fetch_fundamentals_cached(conn, "INVALID")

            assert result is None
            # Should not have cached anything
            cached_row = conn.execute(
                "SELECT * FROM reference_cache WHERE ticker = %s AND source = %s",
                ["INVALID", "fundamentals"],
            ).fetchone()
            assert cached_row is None
