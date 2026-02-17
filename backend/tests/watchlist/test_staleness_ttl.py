"""Test for staleness TTL calculation using new refresh interval columns."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest

from app.storage import PortfolioStorage, get_storage
from app.watchlist.data_loaders import load_stale_ttl_minutes


@pytest.fixture
def setup_preferences() -> Iterator[PortfolioStorage]:
    """Set up user preferences with new refresh interval columns."""
    storage = get_storage()

    # Ensure default account exists
    now = datetime.now(UTC)
    with storage.connection() as conn:
        result = conn.execute("SELECT id FROM portfolio_accounts WHERE id = 'default'")
        if not result.fetchall():
            conn.execute(
                """
                INSERT INTO portfolio_accounts (id, name, account_type, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                ["default", "Default Account", "paper", now.isoformat(), now.isoformat()],
            )
        conn.commit()

    # Set up test preferences with both old and new columns
    with storage.connection() as conn:
        # Delete existing preferences
        conn.execute("DELETE FROM user_preferences WHERE id = 'default'")

        # Insert test preferences (include required risk_tolerance column)
        conn.execute(
            """
            INSERT INTO user_preferences
            (id, risk_tolerance, watchlist_refresh_minutes, default_refresh_minutes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ["default", 5, 1, 15, now.isoformat(), now.isoformat()],
        )
        conn.commit()

    yield storage

    # Cleanup
    with storage.connection() as conn:
        conn.execute("DELETE FROM user_preferences WHERE id = 'default'")
        conn.commit()


def test_staleness_ttl_uses_new_column_not_old(setup_preferences: PortfolioStorage) -> None:
    """
    Test that staleness TTL is calculated from new default_refresh_minutes column,
    not the old watchlist_refresh_minutes column.

    BUG: Function reads old watchlist_refresh_minutes (1 min) instead of
         new default_refresh_minutes (15 min), causing incorrect staleness
    FIX: Use default_refresh_minutes with override fallback logic
    """
    storage = setup_preferences

    # Load staleness TTL
    ttl = load_stale_ttl_minutes(storage)

    # Should use default_refresh_minutes (15 min) * 3 = 45 minutes
    # NOT watchlist_refresh_minutes (1 min) * 3 = 3 minutes
    expected_ttl = 15 * 3  # 45 minutes

    assert ttl == expected_ttl, (
        f"Staleness TTL should use new default_refresh_minutes column! "
        f"Expected: {expected_ttl} min (15 min * 3), "
        f"Got: {ttl} min "
        f"(likely using old watchlist_refresh_minutes: 1 min * 3 = 3 min)"
    )


def test_staleness_ttl_respects_override(setup_preferences: PortfolioStorage) -> None:
    """
    Test that staleness TTL uses watchlist_refresh_override when set,
    falling back to default_refresh_minutes when override is NULL.
    """
    storage = setup_preferences

    # Set override to 5 minutes
    with storage.connection() as conn:
        conn.execute(
            """
            UPDATE user_preferences
            SET watchlist_refresh_override = 5
            WHERE id = 'default'
            """
        )
        conn.commit()

    # Should use override (5 min) * 3 = 15 minutes
    ttl_with_override = load_stale_ttl_minutes(storage)
    assert ttl_with_override == 15, (
        f"Should use watchlist_refresh_override when set! "
        f"Expected: 15 min (5 min * 3), Got: {ttl_with_override} min"
    )

    # Clear override
    with storage.connection() as conn:
        conn.execute(
            """
            UPDATE user_preferences
            SET watchlist_refresh_override = NULL
            WHERE id = 'default'
            """
        )
        conn.commit()

    # Should fall back to default (15 min) * 3 = 45 minutes
    ttl_without_override = load_stale_ttl_minutes(storage)
    assert ttl_without_override == 45, (
        f"Should use default_refresh_minutes when override is NULL! "
        f"Expected: 45 min (15 min * 3), Got: {ttl_without_override} min"
    )
