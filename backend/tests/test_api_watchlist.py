"""Integration tests for Watchlist API endpoints."""

from __future__ import annotations

import json
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import polars as pl
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.portfolio.models import PriceData
from app.storage import DuckDBStorage


@pytest.fixture
def test_storage() -> DuckDBStorage:
    """Create a DuckDBStorage instance with a temporary database."""
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test_api_watchlist.duckdb"

    # Create fresh storage instance (bypass singleton)
    from app.storage.connection import ConnectionManager
    from app.storage.ingestion import IngestionManager
    from app.storage.metadata import MetadataManager
    from app.storage.queries import QueryManager
    from app.storage.schema import SchemaManager

    storage_inst = DuckDBStorage.__new__(DuckDBStorage)
    storage_inst.connection_mgr = ConnectionManager()
    storage_inst.schema_mgr = SchemaManager(storage_inst.connection_mgr)
    storage_inst.metadata_mgr = MetadataManager(storage_inst.connection_mgr)
    storage_inst.ingestion_mgr = IngestionManager(
        storage_inst.connection_mgr, storage_inst.metadata_mgr
    )
    storage_inst.query_mgr = QueryManager(storage_inst.connection_mgr)
    storage_inst.schema_mgr.ensure_schema()

    # Insert test account
    with storage_inst.connection() as conn:
        conn.execute(
            """
            INSERT INTO portfolio_accounts (id, name, account_type)
            VALUES (?, ?, ?)
            """,
            ["test-account", "Test Account", "Taxable"],
        )

    # Insert user preferences with watchlist settings
    with storage_inst.connection() as conn:
        conn.execute(
            """
            INSERT INTO user_preferences (
                id, risk_tolerance, allow_long, allow_short, allow_options,
                allow_crypto, allow_futures, max_position_size_pct,
                watchlist_refresh_minutes, watchlist_auto_expand,
                watchlist_price_weight, watchlist_technical_weight,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "test-user",
                5,
                True,
                False,
                False,
                False,
                False,
                10.0,
                15,
                False,
                50.0,
                50.0,
                datetime.now(UTC),
                datetime.now(UTC),
            ],
        )

    yield storage_inst

    # Cleanup
    if db_path.exists():
        db_path.unlink()
    Path(temp_dir).rmdir()


@pytest.fixture
def client(test_storage: DuckDBStorage) -> TestClient:
    """Create a test client with patched storage."""
    # Patch storage at multiple import points
    with (
        patch("app.api.watchlist.storage", test_storage),
        patch("app.api.watchlist.get_storage", return_value=test_storage),
        patch("app.api.watchlist.watchlist_service.storage", test_storage),
    ):
        yield TestClient(app)


def _insert_day_bars(storage: DuckDBStorage, symbol: str, closes: list[float]) -> None:
    """Helper to insert historical price data."""
    start_date = datetime.now(UTC) - timedelta(days=len(closes) + 5)
    rows = []
    for idx, close in enumerate(closes):
        current_date = (start_date + timedelta(days=idx)).date()
        rows.append(
            {
                "ticker": symbol,
                "date": current_date,
                "open": close,
                "high": close * 1.02,
                "low": close * 0.98,
                "close": close,
                "volume": 1_000_000,
                "vwap": close,
                "source": "test",
                "ingest_run_id": None,
            }
        )

    storage.insert_dataframe("day_bars", pl.DataFrame(rows), mode="append")


def _insert_technical(storage: DuckDBStorage, symbol: str, rsi: float = 50.0) -> None:
    """Helper to insert technical indicator data."""
    storage.insert_dataframe(
        "technical_indicators",
        pl.DataFrame(
            [
                {
                    "ticker": symbol,
                    "date": datetime.now(UTC).date(),
                    "rsi_14": rsi,
                    "macd": 2.5,
                    "macd_signal": 2.0,
                    "macd_histogram": 0.5,
                    "bb_upper": None,
                    "bb_middle": None,
                    "bb_lower": None,
                    "sma_20": 150.0,
                    "sma_50": 148.0,
                    "sma_200": 145.0,
                    "ema_20": None,
                    "ema_50": None,
                    "ema_200": None,
                    "atr_14": 3.5,
                    "stoch_k": None,
                    "stoch_d": None,
                    "calculated_at": datetime.now(UTC),
                }
            ]
        ),
        mode="append",
    )


# CRUD Tests


def test_list_watchlist_items_empty(client: TestClient) -> None:
    """Test GET /api/watchlist returns empty list when no items exist."""
    response = client.get("/api/watchlist?account_id=test-account")

    assert response.status_code == 200
    data = response.json()

    assert data["items"] == []
    assert data["total_count"] == 0


def test_create_watchlist_item_success(client: TestClient, test_storage: DuckDBStorage) -> None:
    """Test POST /api/watchlist successfully creates a watchlist item."""
    request_data = {
        "account_id": "test-account",
        "symbol": "AAPL",
        "note": "Apple is a great company",
    }

    response = client.post("/api/watchlist", json=request_data)

    assert response.status_code == 201
    data = response.json()

    assert data["account_id"] == "test-account"
    assert data["symbol"] == "AAPL"
    assert data["note"] == "Apple is a great company"
    assert data["id"] is not None
    assert data["created_at"] is not None
    assert data["updated_at"] is not None
    assert data["current_score"] is None  # No price data yet

    # Verify persisted to database
    with test_storage.connection() as conn:
        result = conn.execute(
            "SELECT symbol, note FROM watchlist_items WHERE account_id = ?",
            ["test-account"],
        ).fetchone()
        assert result[0] == "AAPL"
        assert result[1] == "Apple is a great company"


def test_create_watchlist_item_normalizes_symbol(
    client: TestClient, test_storage: DuckDBStorage
) -> None:
    """Test POST /api/watchlist normalizes symbol to uppercase."""
    request_data = {
        "account_id": "test-account",
        "symbol": "  tsla  ",  # Lowercase with whitespace
        "note": None,
    }

    response = client.post("/api/watchlist", json=request_data)

    assert response.status_code == 201
    data = response.json()

    assert data["symbol"] == "TSLA"  # Should be uppercase and trimmed

    # Verify in database
    with test_storage.connection() as conn:
        result = conn.execute(
            "SELECT symbol FROM watchlist_items WHERE account_id = ?",
            ["test-account"],
        ).fetchone()
        assert result[0] == "TSLA"


def test_create_watchlist_item_empty_symbol_fails(client: TestClient) -> None:
    """Test POST /api/watchlist rejects empty symbol."""
    request_data = {
        "account_id": "test-account",
        "symbol": "   ",  # Empty after trim
        "note": None,
    }

    response = client.post("/api/watchlist", json=request_data)

    assert response.status_code == 400
    assert "Symbol cannot be empty" in response.json()["detail"]


def test_create_watchlist_item_duplicate_fails(
    client: TestClient, test_storage: DuckDBStorage
) -> None:
    """Test POST /api/watchlist rejects duplicate symbol for same account."""
    # Create first item
    request_data = {
        "account_id": "test-account",
        "symbol": "AAPL",
        "note": "First entry",
    }
    response = client.post("/api/watchlist", json=request_data)
    assert response.status_code == 201

    # Try to create duplicate
    duplicate_data = {
        "account_id": "test-account",
        "symbol": "AAPL",  # Same symbol
        "note": "Duplicate entry",
    }
    response = client.post("/api/watchlist", json=duplicate_data)

    assert response.status_code == 409
    assert "already in watchlist" in response.json()["detail"]


def test_get_watchlist_item_success(client: TestClient, test_storage: DuckDBStorage) -> None:
    """Test GET /api/watchlist/{item_id} returns item details."""
    # Create an item first
    create_response = client.post(
        "/api/watchlist",
        json={
            "account_id": "test-account",
            "symbol": "MSFT",
            "note": "Microsoft test",
        },
    )
    item_id = create_response.json()["id"]

    # Fetch the item
    response = client.get(f"/api/watchlist/{item_id}")

    assert response.status_code == 200
    data = response.json()

    assert data["id"] == item_id
    assert data["symbol"] == "MSFT"
    assert data["note"] == "Microsoft test"


def test_get_watchlist_item_not_found(client: TestClient) -> None:
    """Test GET /api/watchlist/{item_id} returns 404 for missing item."""
    response = client.get("/api/watchlist/nonexistent-id")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_update_watchlist_item_note(client: TestClient, test_storage: DuckDBStorage) -> None:
    """Test PATCH /api/watchlist/{item_id} updates note field."""
    # Create an item
    create_response = client.post(
        "/api/watchlist",
        json={
            "account_id": "test-account",
            "symbol": "GOOGL",
            "note": "Original note",
        },
    )
    item_id = create_response.json()["id"]

    # Update the note
    update_response = client.patch(
        f"/api/watchlist/{item_id}",
        json={"note": "Updated note"},
    )

    assert update_response.status_code == 200
    data = update_response.json()

    assert data["id"] == item_id
    assert data["symbol"] == "GOOGL"
    assert data["note"] == "Updated note"

    # Verify persisted
    with test_storage.connection() as conn:
        result = conn.execute(
            "SELECT note FROM watchlist_items WHERE id = ?",
            [item_id],
        ).fetchone()
        assert result[0] == "Updated note"


def test_update_watchlist_item_not_found(client: TestClient) -> None:
    """Test PATCH /api/watchlist/{item_id} returns 404 for missing item."""
    response = client.patch(
        "/api/watchlist/nonexistent-id",
        json={"note": "New note"},
    )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_delete_watchlist_item_success(client: TestClient, test_storage: DuckDBStorage) -> None:
    """Test DELETE /api/watchlist/{item_id} removes item and snapshots."""
    # Create an item
    create_response = client.post(
        "/api/watchlist",
        json={
            "account_id": "test-account",
            "symbol": "NVDA",
            "note": "To be deleted",
        },
    )
    item_id = create_response.json()["id"]

    # Insert a snapshot for the item
    with test_storage.connection() as conn:
        conn.execute(
            """
            INSERT INTO watchlist_snapshots (
                item_id, fetched_at, price, change_pct, beta, volatility,
                overall_score, technical_score, raw_metrics
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                item_id,
                datetime.now(UTC),
                150.0,
                2.5,
                1.2,
                0.25,
                75.0,
                70.0,
                json.dumps({}),
            ],
        )

    # Delete the item
    delete_response = client.delete(f"/api/watchlist/{item_id}")

    assert delete_response.status_code == 204

    # Verify item is gone
    with test_storage.connection() as conn:
        result = conn.execute(
            "SELECT COUNT(*) FROM watchlist_items WHERE id = ?",
            [item_id],
        ).fetchone()
        assert result[0] == 0

    # Verify snapshots are also deleted
    with test_storage.connection() as conn:
        result = conn.execute(
            "SELECT COUNT(*) FROM watchlist_snapshots WHERE item_id = ?",
            [item_id],
        ).fetchone()
        assert result[0] == 0


def test_delete_watchlist_item_not_found(client: TestClient) -> None:
    """Test DELETE /api/watchlist/{item_id} returns 404 for missing item."""
    response = client.delete("/api/watchlist/nonexistent-id")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_list_watchlist_items_with_scores(client: TestClient, test_storage: DuckDBStorage) -> None:
    """Test GET /api/watchlist returns items with current scores."""
    # Create an item
    create_response = client.post(
        "/api/watchlist",
        json={
            "account_id": "test-account",
            "symbol": "AAPL",
            "note": "Apple Inc.",
        },
    )
    item_id = create_response.json()["id"]

    # Insert price history and technical data
    _insert_day_bars(test_storage, "AAPL", [140.0, 145.0, 150.0, 148.0, 152.0])
    _insert_technical(test_storage, "AAPL", rsi=60.0)

    # Insert a snapshot with scores
    with test_storage.connection() as conn:
        conn.execute(
            """
            INSERT INTO watchlist_snapshots (
                item_id, fetched_at, price, change_pct, beta, volatility,
                overall_score, technical_score, raw_metrics
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                item_id,
                datetime.now(UTC),
                152.0,
                2.7,
                1.1,
                0.22,
                72.5,
                68.0,
                json.dumps(
                    {
                        "price": {
                            "score": 75.0,
                            "weight": 50.0,
                            "stale": False,
                            "updated_at": datetime.now(UTC).isoformat(),
                            "metadata": {},
                        },
                        "technical": {
                            "score": 70.0,
                            "weight": 50.0,
                            "stale": False,
                            "updated_at": datetime.now(UTC).isoformat(),
                            "metadata": {},
                        },
                    }
                ),
            ],
        )

    # Fetch watchlist
    response = client.get("/api/watchlist?account_id=test-account")

    assert response.status_code == 200
    data = response.json()

    assert data["total_count"] == 1
    assert len(data["items"]) == 1

    item = data["items"][0]
    assert item["symbol"] == "AAPL"
    assert item["current_score"] is not None
    assert item["current_score"]["overall"] == 72.5
    assert item["current_score"]["price"]["score"] == 75.0
    assert item["current_score"]["technical"]["score"] == 70.0
    assert item["score_alert"] is False  # No historical data for alert


# Refresh Tests


def test_refresh_watchlist_scores_empty_watchlist(client: TestClient) -> None:
    """Test POST /api/watchlist/refresh with no items returns success with 0 count."""
    response = client.post("/api/watchlist/refresh?account_id=test-account")

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "success"
    assert data["refreshed_count"] == 0
    assert "No items" in data["message"]


def test_refresh_watchlist_scores_success(client: TestClient, test_storage: DuckDBStorage) -> None:
    """Test POST /api/watchlist/refresh successfully refreshes scores."""
    # Create watchlist items
    create_response1 = client.post(
        "/api/watchlist",
        json={"account_id": "test-account", "symbol": "AAPL", "note": None},
    )
    create_response2 = client.post(
        "/api/watchlist",
        json={"account_id": "test-account", "symbol": "MSFT", "note": None},
    )

    item_id_1 = create_response1.json()["id"]
    item_id_2 = create_response2.json()["id"]

    # Insert historical price data and technical indicators
    _insert_day_bars(test_storage, "AAPL", [140.0, 145.0, 150.0, 148.0, 152.0])
    _insert_day_bars(test_storage, "MSFT", [300.0, 305.0, 310.0, 315.0, 320.0])
    _insert_technical(test_storage, "AAPL", rsi=65.0)
    _insert_technical(test_storage, "MSFT", rsi=55.0)

    # Mock the price fetcher
    mock_price_fetcher = MagicMock()
    mock_price_fetcher.fetch_price_data.return_value = {
        "AAPL": PriceData(symbol="AAPL", price=155.0, source="test"),
        "MSFT": PriceData(symbol="MSFT", price=325.0, source="test"),
    }

    with patch(
        "app.api.watchlist.watchlist_service.price_fetcher",
        mock_price_fetcher,
    ):
        response = client.post("/api/watchlist/refresh?account_id=test-account")

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "success"
    assert data["refreshed_count"] == 2
    assert "2 of 2" in data["message"]

    # Verify snapshots were created
    with test_storage.connection() as conn:
        result = conn.execute(
            "SELECT COUNT(*) FROM watchlist_snapshots WHERE item_id IN (?, ?)",
            [item_id_1, item_id_2],
        ).fetchone()
        assert result[0] == 2


def test_refresh_watchlist_scores_handles_partial_failure(
    client: TestClient, test_storage: DuckDBStorage
) -> None:
    """Test POST /api/watchlist/refresh continues when some items fail."""
    # Create watchlist items
    client.post(
        "/api/watchlist",
        json={"account_id": "test-account", "symbol": "AAPL", "note": None},
    )
    client.post(
        "/api/watchlist",
        json={"account_id": "test-account", "symbol": "INVALID", "note": None},
    )

    # Insert data only for AAPL
    _insert_day_bars(test_storage, "AAPL", [140.0, 145.0, 150.0])
    _insert_technical(test_storage, "AAPL", rsi=60.0)

    # Mock price fetcher - only returns AAPL, not INVALID
    mock_price_fetcher = MagicMock()
    mock_price_fetcher.fetch_price_data.return_value = {
        "AAPL": PriceData(symbol="AAPL", price=152.0, source="test"),
        # INVALID symbol returns no data
    }

    with patch(
        "app.api.watchlist.watchlist_service.price_fetcher",
        mock_price_fetcher,
    ):
        response = client.post("/api/watchlist/refresh?account_id=test-account")

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "success"
    assert data["refreshed_count"] == 1  # Only AAPL succeeded
    assert "1 of 2" in data["message"]


# Score Alert Tests


def test_score_alert_detection(client: TestClient, test_storage: DuckDBStorage) -> None:
    """Test score_alert flag is set when score changes >10 points in 7 days."""
    # Create watchlist item
    create_response = client.post(
        "/api/watchlist",
        json={"account_id": "test-account", "symbol": "AAPL", "note": None},
    )
    item_id = create_response.json()["id"]

    # Insert snapshot from 6 days ago with score 50 (within the 7-day window)
    week_ago = datetime.now(UTC) - timedelta(days=6)
    with test_storage.connection() as conn:
        conn.execute(
            """
            INSERT INTO watchlist_snapshots (
                item_id, fetched_at, price, overall_score, technical_score, raw_metrics
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            [item_id, week_ago, 100.0, 50.0, 50.0, json.dumps({})],
        )

    # Insert recent snapshot with score 75 (change of 25 points > 10)
    with test_storage.connection() as conn:
        conn.execute(
            """
            INSERT INTO watchlist_snapshots (
                item_id, fetched_at, price, overall_score, technical_score, raw_metrics
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                item_id,
                datetime.now(UTC),
                150.0,
                75.0,
                70.0,
                json.dumps(
                    {
                        "price": {
                            "score": 80.0,
                            "weight": 50.0,
                            "stale": False,
                        },
                        "technical": {
                            "score": 70.0,
                            "weight": 50.0,
                            "stale": False,
                        },
                    }
                ),
            ],
        )

    # Fetch watchlist
    response = client.get("/api/watchlist?account_id=test-account")

    assert response.status_code == 200
    data = response.json()

    assert len(data["items"]) == 1
    assert data["items"][0]["score_alert"] is True  # Should trigger alert


def test_score_alert_not_triggered_small_change(
    client: TestClient, test_storage: DuckDBStorage
) -> None:
    """Test score_alert is False when score changes <10 points."""
    # Create watchlist item
    create_response = client.post(
        "/api/watchlist",
        json={"account_id": "test-account", "symbol": "AAPL", "note": None},
    )
    item_id = create_response.json()["id"]

    # Insert snapshot from 6 days ago with score 50 (within the 7-day window)
    week_ago = datetime.now(UTC) - timedelta(days=6)
    with test_storage.connection() as conn:
        conn.execute(
            """
            INSERT INTO watchlist_snapshots (
                item_id, fetched_at, price, overall_score, technical_score, raw_metrics
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            [item_id, week_ago, 100.0, 50.0, 50.0, json.dumps({})],
        )

    # Insert recent snapshot with score 55 (change of 5 points < 10)
    with test_storage.connection() as conn:
        conn.execute(
            """
            INSERT INTO watchlist_snapshots (
                item_id, fetched_at, price, overall_score, technical_score, raw_metrics
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                item_id,
                datetime.now(UTC),
                105.0,
                55.0,
                52.0,
                json.dumps(
                    {
                        "price": {"score": 58.0, "weight": 50.0, "stale": False},
                        "technical": {"score": 52.0, "weight": 50.0, "stale": False},
                    }
                ),
            ],
        )

    # Fetch watchlist
    response = client.get("/api/watchlist?account_id=test-account")

    assert response.status_code == 200
    data = response.json()

    assert len(data["items"]) == 1
    assert data["items"][0]["score_alert"] is False  # Should not trigger


# Validation Tests


def test_create_watchlist_item_missing_account_id(client: TestClient) -> None:
    """Test POST /api/watchlist validates required account_id."""
    response = client.post(
        "/api/watchlist",
        json={"symbol": "AAPL"},  # Missing account_id
    )

    assert response.status_code == 422  # Validation error


def test_create_watchlist_item_missing_symbol(client: TestClient) -> None:
    """Test POST /api/watchlist validates required symbol."""
    response = client.post(
        "/api/watchlist",
        json={"account_id": "test-account"},  # Missing symbol
    )

    assert response.status_code == 422  # Validation error


def test_response_structure_matches_spec(client: TestClient, test_storage: DuckDBStorage) -> None:
    """Test all API responses match the expected schema."""
    # Create item
    create_response = client.post(
        "/api/watchlist",
        json={"account_id": "test-account", "symbol": "AAPL", "note": "Test"},
    )

    assert create_response.status_code == 201
    create_data = create_response.json()

    # Verify create response structure
    required_fields = ["id", "account_id", "symbol", "note", "created_at", "updated_at"]
    for field in required_fields:
        assert field in create_data, f"Missing field: {field}"

    # Verify list response structure
    list_response = client.get("/api/watchlist?account_id=test-account")
    list_data = list_response.json()

    assert "items" in list_data
    assert "total_count" in list_data
    assert isinstance(list_data["items"], list)
    assert isinstance(list_data["total_count"], int)
