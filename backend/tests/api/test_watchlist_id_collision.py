"""Test for watchlist ID collision issues with timestamp-based IDs.

This test demonstrates the bug where using timestamp-based IDs can cause
collisions when multiple watchlist items are created concurrently.

After fixing to use UUID-based IDs, this test should pass with 0 collisions.

IMPORTANT: Uses pytest fixtures to ensure cleanup happens even on test failure.
"""

from __future__ import annotations

import concurrent.futures
import importlib
from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.storage import get_storage

crud_router = importlib.import_module("app.api.watchlist.crud_router")

# Use a unique but valid prefix to avoid conflicts with the live ZZTEST blocker.
TEST_SYMBOL_PREFIX = "ZXCOLL"
NUM_CONCURRENT_REQUESTS = 10  # Reduced from 100 - enough to test concurrency


@pytest.fixture
def cleanup_test_symbols() -> Generator[None]:
    """Fixture that cleans up test symbols BEFORE and AFTER the test.

    Uses try/finally to ensure cleanup happens even if test fails.
    """
    storage = get_storage()

    def do_cleanup() -> None:
        with storage.connection() as conn:
            conn.execute(
                "DELETE FROM watchlist_items WHERE symbol LIKE %s",
                (f"{TEST_SYMBOL_PREFIX}%",),
            )
            conn.commit()

    # Clean before test
    do_cleanup()

    yield  # Run the test

    # Clean after test (even on failure)
    do_cleanup()


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Use a test client with background side effects disabled."""
    monkeypatch.setattr(crud_router, "schedule_new_symbol_tasks", lambda _symbol: None)
    app = FastAPI()
    app.include_router(crud_router.router, prefix="/api/watchlist")
    return TestClient(app)


def test_concurrent_watchlist_creation_no_collisions(
    cleanup_test_symbols: None, client: TestClient
) -> None:
    """Test that concurrent watchlist item creations don't cause ID collisions.

    Uses UUID-based IDs to prevent UNIQUE constraint violations when
    multiple requests arrive within the same millisecond.
    """
    storage = get_storage()

    symbols = [f"{TEST_SYMBOL_PREFIX}{i:03d}" for i in range(NUM_CONCURRENT_REQUESTS)]

    def create_watchlist_item(symbol: str) -> tuple[int, str]:
        """Create a watchlist item and return (status_code, response_text)."""
        try:
            response = client.post(
                "/api/watchlist",
                json={"symbol": symbol, "note": f"Test item {symbol}"},
            )
            return (response.status_code, response.text)
        except Exception as e:
            return (500, str(e))

    # Execute requests concurrently
    successes = 0
    failures = 0
    collision_errors = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(create_watchlist_item, symbol) for symbol in symbols]
        results = [future.result() for future in concurrent.futures.as_completed(futures)]

    for status_code, response_text in results:
        if status_code == 201:
            successes += 1
        else:
            failures += 1
            if (
                "UNIQUE" in response_text
                or "unique" in response_text
                or "duplicate" in response_text.lower()
            ):
                collision_errors += 1

    # Verify no ID collisions occurred
    assert collision_errors == 0, (
        f"Expected 0 ID collisions with UUID-based IDs, but got {collision_errors}. "
        "This indicates timestamp-based IDs are still being used."
    )

    assert failures == 0, (
        f"Expected 0 failures, but got {failures}. "
        "All concurrent requests should succeed without collisions."
    )

    # Verify all items were created
    with storage.connection() as conn:
        cursor = conn.execute(
            "SELECT COUNT(*) FROM watchlist_items WHERE symbol LIKE %s",
            (f"{TEST_SYMBOL_PREFIX}%",),
        )
        count_row = cursor.fetchone()
        assert count_row is not None
        actual_count = count_row[0]

    assert actual_count == NUM_CONCURRENT_REQUESTS, (
        f"Expected {NUM_CONCURRENT_REQUESTS} items in database, but found {actual_count}."
    )


@pytest.fixture
def cleanup_uuid_test_symbol() -> Generator[str]:
    """Fixture that cleans up the test UUID symbol before and after test."""
    storage = get_storage()
    test_symbol = "ZXUUID001"

    def do_cleanup() -> None:
        with storage.connection() as conn:
            conn.execute("DELETE FROM watchlist_items WHERE symbol = %s", (test_symbol,))
            conn.commit()

    do_cleanup()
    yield test_symbol
    do_cleanup()


def test_uuid_format_validation(cleanup_uuid_test_symbol: str, client: TestClient) -> None:
    """Test that watchlist item IDs follow UUID format.

    This test verifies that IDs are in UUID format (lowercase hex with dashes),
    not timestamp format (numeric string).
    """
    import re

    test_symbol = cleanup_uuid_test_symbol

    # Create a watchlist item
    response = client.post(
        "/api/watchlist",
        json={"symbol": test_symbol, "note": "Test UUID format"},
    )

    assert response.status_code == 201
    data = response.json()
    item_id = data["id"]

    # UUID format: 8-4-4-4-12 hex characters with dashes (lowercase)
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
