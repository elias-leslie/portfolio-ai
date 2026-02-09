"""Integration tests for valuation metrics API endpoints."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.storage import get_storage
from app.storage.connection import ConnectionManager

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_before_test() -> Iterator[None]:
    """Clean database before each test and set up test data."""
    # Clean tables manually (mimic clean_database fixture)
    cm = ConnectionManager()
    tables_to_clean = [
        "agent_tool_calls",
        "agent_ideas",
        "agent_runs",
        "idea_outcomes",
        "portfolio_positions",
        "portfolio_accounts",
        "watchlist_snapshots",
        "watchlist_items",
        "day_bars",
        "technical_indicators",
        "price_cache",
        "reference_cache",
        "news_cache",
        "news_summary_log",
        "source_performance",
        "validation_results",
        "user_preferences",
    ]

    with cm.connection() as conn:
        try:
            table_list = ", ".join(tables_to_clean)
            conn.execute(f"TRUNCATE TABLE {table_list} CASCADE")
            conn.commit()
        except Exception:
            conn.rollback()

    # Now set up test data
    storage = get_storage()
    with storage.connection() as conn:
        # Insert test data for multiple symbols
        test_data = [
            {
                "symbol": "NVDA",
                "source": "fundamentals",
                "as_of_date": date.today(),
                "pe_trailing": 53.24,
                "pe_forward": 45.35,
                "ps_ratio": 27.54,
                "pb_ratio": 45.43,
                "peg_ratio": 2.15,
                "dividend_yield": 0.02,
                "payout_ratio": 0.0114,
            },
            {
                "symbol": "AAPL",
                "source": "fundamentals",
                "as_of_date": date.today(),
                "pe_trailing": 29.5,
                "pe_forward": 26.3,
                "ps_ratio": 7.2,
                "pb_ratio": 48.5,
                "peg_ratio": 2.8,
                "dividend_yield": 0.004,
                "payout_ratio": 0.16,
            },
            {
                "symbol": "MSFT",
                "source": "fundamentals",
                "as_of_date": date.today(),
                "pe_trailing": 35.2,
                "pe_forward": 31.5,
                "ps_ratio": 9.1,
                "pb_ratio": 55.2,
                "peg_ratio": 3.1,
                "dividend_yield": 0.0085,
                "payout_ratio": 0.25,
            },
        ]

        for data in test_data:
            conn.execute(
                """
                INSERT INTO reference_cache
                  (symbol, source, as_of_date, payload,
                   pe_ratio_trailing, pe_ratio_forward, ps_ratio, pb_ratio,
                   peg_ratio, dividend_yield, payout_ratio)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    data["symbol"],
                    data["source"],
                    data["as_of_date"],
                    json.dumps({"symbol": data["symbol"]}),
                    data["pe_trailing"],
                    data["pe_forward"],
                    data["ps_ratio"],
                    data["pb_ratio"],
                    data["peg_ratio"],
                    data["dividend_yield"],
                    data["payout_ratio"],
                ],
            )
        conn.commit()

    yield


class TestValuationAPI:
    """Tests for valuation metrics API endpoints."""

    def test_get_single_ticker_valuation(self) -> None:
        """Test retrieving valuation metrics for a single symbol."""
        response = client.get("/api/valuation/NVDA")

        assert response.status_code == 200
        data = response.json()

        assert data["symbol"] == "NVDA"
        assert data["pe_ratio_trailing"] == 53.24
        assert data["pe_ratio_forward"] == 45.35
        assert data["ps_ratio"] == 27.54
        assert data["pb_ratio"] == 45.43
        assert data["peg_ratio"] == 2.15
        assert data["dividend_yield"] == 0.02
        assert data["payout_ratio"] == 0.0114
        assert data["as_of_date"] is not None

    def test_get_single_ticker_case_insensitive(self) -> None:
        """Test that symbol lookup is case-insensitive."""
        response = client.get("/api/valuation/nvda")

        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "NVDA"

    def test_get_ticker_not_found(self) -> None:
        """Test error handling for non-existent symbol."""
        response = client.get("/api/valuation/NONEXIST")

        assert response.status_code == 404
        assert "No valuation metrics found" in response.json()["detail"]

    def test_get_batch_valuation_metrics(self) -> None:
        """Test retrieving valuation metrics for multiple symbols."""
        response = client.get("/api/valuation?symbols=NVDA,AAPL,MSFT")

        assert response.status_code == 200
        data = response.json()

        assert data["count"] == 3
        assert len(data["symbols"]) == 3

        # Verify each symbol is present
        symbols = {t["symbol"] for t in data["symbols"]}
        assert symbols == {"NVDA", "AAPL", "MSFT"}

        # Verify data integrity
        nvda_data = next(t for t in data["symbols"] if t["symbol"] == "NVDA")
        assert nvda_data["pe_ratio_trailing"] == 53.24

    def test_get_batch_with_spaces(self) -> None:
        """Test that batch endpoint handles whitespace in symbol list."""
        response = client.get("/api/valuation?symbols=NVDA, AAPL , MSFT")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 3

    def test_get_batch_no_tickers(self) -> None:
        """Test batch endpoint error when no symbols provided."""
        response = client.get("/api/valuation?symbols=")

        assert response.status_code == 400
        assert "No symbols provided" in response.json()["detail"]

    def test_get_batch_partial_match(self) -> None:
        """Test batch endpoint with some symbols not found."""
        response = client.get("/api/valuation?symbols=NVDA,NONEXIST,AAPL")

        # Should still return data for found symbols (NVDA and AAPL)
        assert response.status_code == 200
        data = response.json()
        # We only get the found ones
        assert data["count"] == 2
        symbols = {t["symbol"] for t in data["symbols"]}
        assert "NONEXIST" not in symbols
        assert "NVDA" in symbols
        assert "AAPL" in symbols

    def test_get_batch_mixed_case(self) -> None:
        """Test batch endpoint with mixed case symbols."""
        response = client.get("/api/valuation?symbols=nvda,AaPl,MsF t")

        assert response.status_code == 200
        data = response.json()
        # MSFT has space so might not match, but NVDA and AAPL should
        # Actually the space will cause it to not match
        assert data["count"] >= 2

    def test_get_with_null_metrics(self) -> None:
        """Test endpoint returns correctly when some metrics are null."""
        # Insert test data with some null metrics
        cm = ConnectionManager()
        with cm.connection() as conn:
            conn.execute(
                """
                INSERT INTO reference_cache
                  (symbol, source, as_of_date, payload,
                   pe_ratio_trailing, pe_ratio_forward)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                [
                    "TEST",
                    "fundamentals",
                    date.today(),
                    json.dumps({"symbol": "TEST"}),
                    25.5,
                    None,
                ],
            )
            conn.commit()

        response = client.get("/api/valuation/TEST")

        assert response.status_code == 200
        data = response.json()

        assert data["pe_ratio_trailing"] == 25.5
        assert data["pe_ratio_forward"] is None
        assert data["ps_ratio"] is None

    def test_response_contains_as_of_date(self) -> None:
        """Test that response includes as_of_date field."""
        response = client.get("/api/valuation/NVDA")

        assert response.status_code == 200
        data = response.json()

        assert "as_of_date" in data
        assert data["as_of_date"] is not None
        # Should be a date string
        assert len(data["as_of_date"]) > 0

    def test_batch_endpoint_default_empty_query(self) -> None:
        """Test batch endpoint without query parameter returns error."""
        response = client.get("/api/valuation")

        # Should get 400 or 422 (validation error) for missing parameter
        assert response.status_code in (400, 422)
