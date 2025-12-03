"""Tests for institutional ownership scoring (GAP-008)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import polars as pl

from app.analytics.institutional_ownership import (
    calculate_ownership_score,
    get_ownership_from_cache,
    get_ownership_metrics_batch,
)


class TestCalculateOwnershipScore:
    """Tests for calculate_ownership_score function."""

    def test_high_institutional_high_insider(self) -> None:
        """High institutional + high insider = max score."""
        score = calculate_ownership_score(0.65, 0.12)
        assert score == 4  # 2 (inst) + 2 (insider)

    def test_high_institutional_medium_insider(self) -> None:
        """High institutional + medium insider."""
        score = calculate_ownership_score(0.60, 0.07)
        assert score == 3  # 2 (inst) + 1 (insider)

    def test_medium_institutional_high_insider(self) -> None:
        """Medium institutional + high insider."""
        score = calculate_ownership_score(0.35, 0.15)
        assert score == 3  # 1 (inst) + 2 (insider)

    def test_medium_institutional_no_insider(self) -> None:
        """Medium institutional only."""
        score = calculate_ownership_score(0.40, 0.02)
        assert score == 1  # 1 (inst) + 0 (insider)

    def test_very_low_institutional(self) -> None:
        """Very low institutional ownership gets penalty."""
        score = calculate_ownership_score(0.05, 0.02)
        assert score == 0  # -1 (low inst) clamped to 0

    def test_very_low_institutional_high_insider(self) -> None:
        """Very low institutional but high insider (founder company)."""
        score = calculate_ownership_score(0.08, 0.25)
        assert score == 1  # -1 (low inst) + 2 (high insider) = 1

    def test_none_values(self) -> None:
        """None values should not crash."""
        score = calculate_ownership_score(None, None)
        assert score == 0

    def test_institutional_only(self) -> None:
        """Only institutional data available."""
        score = calculate_ownership_score(0.55, None)
        assert score == 2

    def test_insider_only(self) -> None:
        """Only insider data available."""
        score = calculate_ownership_score(None, 0.08)
        assert score == 1

    def test_score_capped_at_5(self) -> None:
        """Score should never exceed 5."""
        # Even with max values, score = 2 + 2 = 4
        score = calculate_ownership_score(0.90, 0.50)
        assert score <= 5

    def test_score_min_zero(self) -> None:
        """Score should never go below 0."""
        score = calculate_ownership_score(0.02, 0.0)
        assert score >= 0


class TestGetOwnershipFromCache:
    """Tests for get_ownership_from_cache function."""

    def test_returns_metrics_when_found(self) -> None:
        """Should return OwnershipMetrics when data exists."""
        mock_storage = MagicMock()
        mock_df = pl.DataFrame({
            "payload": [json.dumps({"heldPercentInstitutions": 0.64, "heldPercentInsiders": 0.02})]
        })
        mock_storage.query.return_value = mock_df

        result = get_ownership_from_cache("AAPL", mock_storage)

        assert result is not None
        assert result.ticker == "AAPL"
        assert result.institutional_pct == 0.64
        assert result.insider_pct == 0.02
        assert result.ownership_score == 2  # High inst (2) + low insider (0)

    def test_returns_none_when_not_found(self) -> None:
        """Should return None when no data."""
        mock_storage = MagicMock()
        mock_storage.query.return_value = pl.DataFrame()

        result = get_ownership_from_cache("UNKNOWN", mock_storage)
        assert result is None

    def test_handles_json_decode_error(self) -> None:
        """Should handle invalid JSON gracefully."""
        mock_storage = MagicMock()
        mock_df = pl.DataFrame({"payload": ["invalid json"]})
        mock_storage.query.return_value = mock_df

        result = get_ownership_from_cache("BAD", mock_storage)
        assert result is None

    def test_handles_missing_fields(self) -> None:
        """Should handle missing ownership fields."""
        mock_storage = MagicMock()
        mock_df = pl.DataFrame({
            "payload": [json.dumps({"symbol": "TEST", "price": 100})]  # No ownership fields
        })
        mock_storage.query.return_value = mock_df

        result = get_ownership_from_cache("TEST", mock_storage)

        assert result is not None
        assert result.institutional_pct is None
        assert result.insider_pct is None
        assert result.ownership_score == 0


class TestGetOwnershipMetricsBatch:
    """Tests for get_ownership_metrics_batch function."""

    def test_returns_metrics_for_multiple_tickers(self) -> None:
        """Should return metrics for all found tickers."""
        mock_storage = MagicMock()
        mock_df = pl.DataFrame({
            "ticker": ["AAPL", "MSFT"],
            "payload": [
                json.dumps({"heldPercentInstitutions": 0.64, "heldPercentInsiders": 0.02}),
                json.dumps({"heldPercentInstitutions": 0.72, "heldPercentInsiders": 0.01}),
            ]
        })
        mock_storage.query.return_value = mock_df

        result = get_ownership_metrics_batch(["AAPL", "MSFT", "UNKNOWN"], mock_storage)

        assert len(result) == 2
        assert "AAPL" in result
        assert "MSFT" in result
        assert result["AAPL"].institutional_pct == 0.64
        assert result["MSFT"].institutional_pct == 0.72

    def test_empty_tickers_list(self) -> None:
        """Should return empty dict for empty input."""
        mock_storage = MagicMock()
        result = get_ownership_metrics_batch([], mock_storage)
        assert result == {}

    def test_skips_invalid_rows(self) -> None:
        """Should skip rows with invalid JSON."""
        mock_storage = MagicMock()
        mock_df = pl.DataFrame({
            "ticker": ["GOOD", "BAD"],
            "payload": [
                json.dumps({"heldPercentInstitutions": 0.50}),
                "invalid json",
            ]
        })
        mock_storage.query.return_value = mock_df

        result = get_ownership_metrics_batch(["GOOD", "BAD"], mock_storage)

        assert len(result) == 1
        assert "GOOD" in result
        assert "BAD" not in result
