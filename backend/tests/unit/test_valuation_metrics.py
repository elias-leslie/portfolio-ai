"""Unit tests for valuation metrics extraction from reference_cache.

Tests the parsing of JSON payloads and population of structured valuation columns.
"""

from __future__ import annotations

import json
from datetime import date

import pytest

from app.storage.connection import ConnectionManager
from app.tasks.reference_tasks import _extract_valuation_metrics, _update_valuation_metrics


class TestExtractValuationMetrics:
    """Tests for _extract_valuation_metrics function."""

    def test_extract_all_metrics(self) -> None:
        """Test extraction of all valuation metrics from payload."""
        payload = {
            "trailingPE": 53.24,
            "forwardPE": 45.35,
            "priceToSalesTrailing12Months": 27.54,
            "priceToBook": 45.43,
            "pegRatio": 2.15,
            "dividendYield": 0.02,
            "payoutRatio": 0.0114,
        }

        metrics = _extract_valuation_metrics(payload)

        assert metrics["pe_ratio_trailing"] == 53.24
        assert metrics["pe_ratio_forward"] == 45.35
        assert metrics["ps_ratio"] == 27.54
        assert metrics["pb_ratio"] == 45.43
        assert metrics["peg_ratio"] == 2.15
        assert metrics["dividend_yield"] == 0.02
        assert metrics["payout_ratio"] == 0.0114

    def test_extract_partial_metrics(self) -> None:
        """Test extraction when only some metrics are present."""
        payload = {
            "trailingPE": 53.24,
            "forwardPE": 45.35,
            # Missing other fields
        }

        metrics = _extract_valuation_metrics(payload)

        assert metrics["pe_ratio_trailing"] == 53.24
        assert metrics["pe_ratio_forward"] == 45.35
        assert metrics["ps_ratio"] is None
        assert metrics["pb_ratio"] is None
        assert metrics["peg_ratio"] is None
        assert metrics["dividend_yield"] is None
        assert metrics["payout_ratio"] is None

    def test_extract_empty_payload(self) -> None:
        """Test extraction with empty payload."""
        payload: dict = {}

        metrics = _extract_valuation_metrics(payload)

        # All metrics should be None
        assert all(v is None for v in metrics.values())

    def test_extract_with_none_values(self) -> None:
        """Test extraction when payload contains explicit None values."""
        payload = {
            "trailingPE": None,
            "forwardPE": 45.35,
            "pegRatio": None,
        }

        metrics = _extract_valuation_metrics(payload)

        assert metrics["pe_ratio_trailing"] is None
        assert metrics["pe_ratio_forward"] == 45.35
        assert metrics["peg_ratio"] is None

    def test_extract_with_zero_values(self) -> None:
        """Test extraction with zero values (valid metric values)."""
        payload = {
            "dividendYield": 0.0,
            "payoutRatio": 0.0,
            "trailingPE": 0.0,
        }

        metrics = _extract_valuation_metrics(payload)

        # Zero values should be preserved (they're valid metrics)
        assert metrics["dividend_yield"] == 0.0
        assert metrics["payout_ratio"] == 0.0
        assert metrics["pe_ratio_trailing"] == 0.0

    def test_extract_with_negative_values(self) -> None:
        """Test extraction with negative values (edge case)."""
        payload = {
            "trailingPE": -5.0,  # Negative P/E for loss-making company
            "dividendYield": -0.01,  # Edge case
        }

        metrics = _extract_valuation_metrics(payload)

        # Negative values should be preserved (it's extraction, not validation)
        assert metrics["pe_ratio_trailing"] == -5.0
        assert metrics["dividend_yield"] == -0.01

    def test_extract_with_extra_fields(self) -> None:
        """Test extraction ignores extra fields in payload."""
        payload = {
            "trailingPE": 53.24,
            "forwardPE": 45.35,
            "unknownField": "should be ignored",
            "symbol": "NVDA",
            "date": "2025-11-14",
        }

        metrics = _extract_valuation_metrics(payload)

        # Should extract only known fields
        assert metrics["pe_ratio_trailing"] == 53.24
        assert metrics["pe_ratio_forward"] == 45.35
        assert len(metrics) == 7  # Only 7 expected fields


class TestUpdateValuationMetrics:
    """Tests for _update_valuation_metrics function."""

    @pytest.fixture(autouse=True)
    def setup_test_data(self, clean_database: None) -> None:
        """Set up test data before each test."""
        # Insert test cache entry
        cm = ConnectionManager()
        with cm.connection() as conn:
            conn.execute(
                """
                INSERT INTO reference_cache
                  (ticker, source, as_of_date, payload, pe_ratio_trailing)
                VALUES (%s, %s, %s, %s, %s)
                """,
                [
                    "NVDA",
                    "fundamentals",
                    date.today(),
                    json.dumps({"symbol": "NVDA"}),
                    None,
                ],
            )
            conn.commit()

    def test_update_metrics_with_complete_payload(self, clean_database: None) -> None:
        """Test updating metrics with complete valuation data."""
        payload = {
            "symbol": "NVDA",
            "trailingPE": 53.24,
            "forwardPE": 45.35,
            "priceToSalesTrailing12Months": 27.54,
            "priceToBook": 45.43,
            "pegRatio": 2.15,
            "dividendYield": 0.02,
            "payoutRatio": 0.0114,
        }

        _update_valuation_metrics("NVDA", "fundamentals", payload)

        # Verify the update
        cm = ConnectionManager()
        with cm.connection() as conn:
            result = conn.execute(
                """
                SELECT
                    pe_ratio_trailing,
                    pe_ratio_forward,
                    ps_ratio,
                    pb_ratio,
                    peg_ratio,
                    dividend_yield,
                    payout_ratio
                FROM reference_cache
                WHERE ticker = %s AND source = %s
                """,
                ["NVDA", "fundamentals"],
            ).fetchone()

        assert result is not None
        assert result[0] == 53.24  # pe_ratio_trailing
        assert result[1] == 45.35  # pe_ratio_forward
        assert result[2] == 27.54  # ps_ratio
        assert result[3] == 45.43  # pb_ratio
        assert result[4] == 2.15  # peg_ratio
        assert result[5] == 0.02  # dividend_yield
        assert result[6] == 0.0114  # payout_ratio

    def test_update_metrics_with_partial_payload(self, clean_database: None) -> None:
        """Test updating metrics when payload has only some fields."""
        payload = {
            "symbol": "NVDA",
            "trailingPE": 53.24,
            "forwardPE": 45.35,
        }

        _update_valuation_metrics("NVDA", "fundamentals", payload)

        # Verify the update
        cm = ConnectionManager()
        with cm.connection() as conn:
            result = conn.execute(
                """
                SELECT
                    pe_ratio_trailing,
                    pe_ratio_forward,
                    ps_ratio,
                    pb_ratio
                FROM reference_cache
                WHERE ticker = %s AND source = %s
                """,
                ["NVDA", "fundamentals"],
            ).fetchone()

        assert result is not None
        assert result[0] == 53.24  # pe_ratio_trailing
        assert result[1] == 45.35  # pe_ratio_forward
        assert result[2] is None  # ps_ratio (not in payload)
        assert result[3] is None  # pb_ratio (not in payload)

    def test_update_metrics_nonexistent_ticker(self) -> None:
        """Test update gracefully handles nonexistent ticker."""
        payload = {"trailingPE": 53.24}

        # Should not raise exception
        _update_valuation_metrics("NONEXIST", "fundamentals", payload)

    def test_update_metrics_empty_payload(self, clean_database: None) -> None:
        """Test update with empty payload (no metrics to extract)."""
        payload: dict = {}

        _update_valuation_metrics("NVDA", "fundamentals", payload)

        # Verify no update occurred (all metrics should still be None)
        cm = ConnectionManager()
        with cm.connection() as conn:
            result = conn.execute(
                """
                SELECT pe_ratio_trailing, pe_ratio_forward
                FROM reference_cache
                WHERE ticker = %s AND source = %s
                """,
                ["NVDA", "fundamentals"],
            ).fetchone()

        assert result is not None
        assert result[0] is None  # pe_ratio_trailing
        assert result[1] is None  # pe_ratio_forward


class TestValuationMetricsIntegration:
    """Integration tests for valuation metrics workflow."""

    @pytest.mark.parametrize(
        "ticker,pe_ratio,ps_ratio,dividend_yield",
        [
            ("AAPL", 29.5, 7.2, 0.004),
            ("MSFT", 35.2, 9.1, 0.0085),
            ("NVDA", 53.24, 27.54, 0.02),
            ("VTI", 22.5, 2.3, 0.016),
        ],
    )
    def test_extract_multiple_ticker_metrics(
        self,
        ticker: str,
        pe_ratio: float,
        ps_ratio: float,
        dividend_yield: float,
    ) -> None:
        """Test extraction with multiple tickers and various metrics."""
        payload = {
            "trailingPE": pe_ratio,
            "priceToSalesTrailing12Months": ps_ratio,
            "dividendYield": dividend_yield,
        }

        metrics = _extract_valuation_metrics(payload)

        assert metrics["pe_ratio_trailing"] == pe_ratio
        assert metrics["ps_ratio"] == ps_ratio
        assert metrics["dividend_yield"] == dividend_yield
