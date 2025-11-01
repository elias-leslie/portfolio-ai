"""Test for watchlist ID collision issues with timestamp-based IDs.

This test demonstrates the bug where using timestamp-based IDs can cause
collisions when multiple watchlist items are created concurrently.

After fixing to use UUID-based IDs, this test should pass with 0 collisions.
"""

import concurrent.futures

from fastapi.testclient import TestClient

from app.main import app
from app.storage import get_storage


def test_concurrent_watchlist_creation_no_collisions() -> None:
    """Test that 100 concurrent watchlist item creations don't cause ID collisions.

    This test currently FAILS with timestamp-based IDs because multiple requests
    within the same millisecond will generate the same ID, causing UNIQUE
    constraint violations.

    After fixing to use UUID-based IDs, this test should PASS with 0 failures.
    """
    client = TestClient(app)
    account_id = "test_concurrent_user"

    # Create account first
    storage = get_storage()
    with storage.connection() as conn:
        # Delete existing account if any
        conn.execute("DELETE FROM watchlist_items WHERE account_id = %s", (account_id,))
        conn.execute("DELETE FROM portfolio_accounts WHERE id = %s", (account_id,))
        conn.commit()

        # Create account
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        conn.execute(
            "INSERT INTO portfolio_accounts (id, name, account_type, created_at, updated_at) VALUES (%s, %s, %s, %s, %s)",
            (account_id, "Test Concurrent User", "paper", now, now),
        )
        conn.commit()

    # Create 100 watchlist items concurrently
    num_requests = 100
    symbols = [f"TEST{i:03d}" for i in range(num_requests)]

    def create_watchlist_item(symbol: str) -> tuple[int, str]:
        """Create a watchlist item and return (status_code, response_text)."""
        try:
            response = client.post(
                "/api/watchlist",
                json={"account_id": account_id, "symbol": symbol, "note": f"Test item {symbol}"},
            )
            return (response.status_code, response.text)
        except Exception as e:
            return (500, str(e))

    # Execute requests concurrently using ThreadPoolExecutor
    successes = 0
    failures = 0
    collision_errors = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(create_watchlist_item, symbol) for symbol in symbols]
        results = [future.result() for future in concurrent.futures.as_completed(futures)]

    for status_code, response_text in results:
        if status_code == 201:
            successes += 1
        else:
            failures += 1
            # Check if it's a UNIQUE constraint violation (ID collision)
            if (
                "UNIQUE" in response_text
                or "unique" in response_text
                or "duplicate" in response_text.lower()
            ):
                collision_errors += 1

    # Verify results
    print("\n=== Concurrent Watchlist Creation Results ===")
    print(f"Total requests: {num_requests}")
    print(f"Successes: {successes}")
    print(f"Failures: {failures}")
    print(f"ID Collisions: {collision_errors}")

    # Query database to verify how many items were actually created
    with storage.connection() as conn:
        cursor = conn.execute(
            "SELECT COUNT(*) FROM watchlist_items WHERE account_id = %s", (account_id,)
        )
        actual_count = cursor.fetchone()[0]
        print(f"Actual items in database: {actual_count}")

    # With UUID-based IDs, we expect:
    # - 0 ID collisions (no UNIQUE constraint violations)
    # - All 100 requests succeed
    # - All 100 items created in database
    assert collision_errors == 0, (
        f"Expected 0 ID collisions with UUID-based IDs, but got {collision_errors}. "
        "This indicates timestamp-based IDs are still being used."
    )

    assert failures == 0, (
        f"Expected 0 failures with UUID-based IDs, but got {failures}. "
        "All concurrent requests should succeed without collisions."
    )

    assert actual_count == num_requests, (
        f"Expected {num_requests} items in database, but found {actual_count}. "
        "Some items may have been lost due to collisions."
    )

    # Clean up
    with storage.connection() as conn:
        conn.execute("DELETE FROM watchlist_items WHERE account_id = %s", (account_id,))
        conn.execute("DELETE FROM portfolio_accounts WHERE id = %s", (account_id,))
        conn.commit()


def test_uuid_format_validation() -> None:
    """Test that watchlist item IDs follow UUID format.

    This test verifies that IDs are in UUID format (lowercase hex with dashes),
    not timestamp format (numeric string).
    """
    client = TestClient(app)
    account_id = "test_uuid_format"

    # Create account first
    storage = get_storage()
    with storage.connection() as conn:
        # Delete existing if any
        conn.execute("DELETE FROM watchlist_items WHERE account_id = %s", (account_id,))
        conn.execute("DELETE FROM portfolio_accounts WHERE id = %s", (account_id,))
        conn.commit()

        # Create account
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        conn.execute(
            "INSERT INTO portfolio_accounts (id, name, account_type, created_at, updated_at) VALUES (%s, %s, %s, %s, %s)",
            (account_id, "Test UUID Format", "paper", now, now),
        )
        conn.commit()

    # Create a watchlist item
    response = client.post(
        "/api/watchlist",
        json={"account_id": account_id, "symbol": "AAPL", "note": "Test UUID format"},
    )

    assert response.status_code == 201
    data = response.json()
    item_id = data["id"]

    # UUID format: 8-4-4-4-12 hex characters with dashes (lowercase)
    import re

    uuid_pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"

    assert re.match(uuid_pattern, item_id), (
        f"Expected UUID format (e.g., '550e8400-e29b-41d4-a716-446655440000'), "
        f"but got '{item_id}'. This indicates timestamp-based IDs are still being used."
    )

    # Timestamp-based IDs look like: "1730482091.123456"
    timestamp_pattern = r"^\d+\.\d+$"
    assert not re.match(timestamp_pattern, item_id), (
        f"ID '{item_id}' is in timestamp format, not UUID format. "
        "This indicates the fix has not been applied."
    )

    # Clean up
    with storage.connection() as conn:
        conn.execute("DELETE FROM watchlist_items WHERE account_id = %s", (account_id,))
        conn.execute("DELETE FROM portfolio_accounts WHERE id = %s", (account_id,))
        conn.commit()
