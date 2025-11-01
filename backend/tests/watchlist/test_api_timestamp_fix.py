"""Test for API timestamp fix - use snapshot fetched_at, not price cache timestamp."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from app.storage import get_storage


@pytest.fixture
def setup_test_data():
    """Create test data with stale price cache but fresh snapshot."""
    storage = get_storage()

    # Clean up test data
    with storage.connection() as conn:
        conn.execute("DELETE FROM watchlist_snapshots WHERE item_id = 'test_item_stale_price'")
        conn.execute("DELETE FROM watchlist_items WHERE id = 'test_item_stale_price'")
        conn.execute("DELETE FROM price_cache WHERE symbol = 'TEST'")
        conn.commit()

    # Ensure 'default' account exists in test database
    now = datetime.now(UTC)
    with storage.connection() as conn:
        # Check if account exists
        result = conn.execute("SELECT id FROM portfolio_accounts WHERE id = 'default'")
        if not result.fetchall():
            # Create default account
            conn.execute(
                """
                INSERT INTO portfolio_accounts (id, name, account_type, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                ["default", "Default Account", "paper", now.isoformat(), now.isoformat()],
            )
        conn.commit()

    # Create watchlist item (use 'default' account which now exists)
    with storage.connection() as conn:
        conn.execute(
            """
            INSERT INTO watchlist_items (id, account_id, symbol, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            ["test_item_stale_price", "default", "TEST", now.isoformat(), now.isoformat()],
        )
        conn.commit()

    # Simulate stale price cache (15 minutes ago)
    stale_time = now - timedelta(minutes=15)

    # Simulate fresh snapshot (2 minutes ago) but with raw_metrics containing stale timestamp
    fresh_time = now - timedelta(minutes=2)

    raw_metrics = {
        "price": {
            "score": 75.0,
            "weight": 0.5,
            "stale": False,
            "updated_at": stale_time.isoformat().replace("+00:00", "Z"),  # Stale timestamp
            "metadata": {
                "price": 150.0,
                "source": "yfinance",
                "cached_at": stale_time.isoformat(),  # Stale cached_at
                "beta": 1.2,
                "volatility": 0.3,
                "raw_change_pct": 0.02,
            },
        },
        "technical": {
            "score": 80.0,
            "weight": 0.5,
            "stale": False,
            "updated_at": fresh_time.isoformat().replace("+00:00", "Z"),
            "metadata": {},
        },
        "overall": 77.5,
    }

    with storage.connection() as conn:
        conn.execute(
            """
            INSERT INTO watchlist_snapshots
            (item_id, fetched_at, overall_score, technical_score, raw_metrics, is_stale)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                "test_item_stale_price",
                fresh_time,
                77.5,
                80.0,
                json.dumps(raw_metrics),
                False,
            ],
        )
        conn.commit()

    yield {
        "item_id": "test_item_stale_price",
        "account_id": "default",
        "symbol": "TEST",
        "stale_time": stale_time,
        "fresh_time": fresh_time,
    }

    # Cleanup
    with storage.connection() as conn:
        conn.execute("DELETE FROM watchlist_snapshots WHERE item_id = 'test_item_stale_price'")
        conn.execute("DELETE FROM watchlist_items WHERE id = 'test_item_stale_price'")
        conn.commit()


def test_api_returns_snapshot_timestamp_not_cache_timestamp(setup_test_data):
    """
    Test that API endpoint returns snapshot's fetched_at timestamp,
    not the stale cached_at timestamp from price_cache.

    BUG: API currently returns updated_at from raw_metrics.price (stale)
    FIX: API should return fetched_at from watchlist_snapshots (fresh)
    """
    from app.watchlist.service import WatchlistService

    storage = get_storage()
    service = WatchlistService(storage)

    test_data = setup_test_data
    items = service.get_items_with_scores(test_data["account_id"])

    assert len(items) == 1, "Should return one item"
    item = items[0]

    assert item["symbol"] == "TEST"
    assert item["score"] is not None
    assert "price" in item["score"]

    price_component = item["score"]["price"]
    assert "updated_at" in price_component

    # Parse timestamps
    returned_timestamp = datetime.fromisoformat(
        price_component["updated_at"].replace("Z", "+00:00")
    )
    fresh_time = test_data["fresh_time"]
    stale_time = test_data["stale_time"]

    # CRITICAL: API should return snapshot fetched_at (fresh), not price cached_at (stale)
    time_diff = abs((returned_timestamp - fresh_time).total_seconds())

    # Allow 1 second tolerance for timestamp comparison
    assert time_diff < 1.0, (
        f"API returned stale timestamp from price_cache! "
        f"Expected: {fresh_time} (snapshot fetched_at), "
        f"Got: {returned_timestamp} (price cached_at), "
        f"Difference: {time_diff:.2f} seconds"
    )

    # Should NOT match stale time
    stale_diff = abs((returned_timestamp - stale_time).total_seconds())
    assert stale_diff > 60, (
        f"API is returning stale cached_at timestamp instead of fresh fetched_at! "
        f"Stale time: {stale_time}, Returned: {returned_timestamp}"
    )
