#!/usr/bin/env python3
"""Seed default data for Portfolio AI Platform.

Creates:
- Default portfolio account (id: "default")
- Default user preferences (id: "default-user")

Run this after database migrations to ensure the application has required seed data.
"""

from datetime import UTC, datetime

from app.storage import get_storage


def seed_default_data() -> None:
    """Create default account and preferences if they don't exist."""
    storage = get_storage()

    # Insert default account
    with storage.connection() as conn:
        conn.execute(
            """
            INSERT INTO portfolio_accounts (id, name, account_type, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (id) DO NOTHING
            """,
            ["default", "Default Account", "Taxable", datetime.now(UTC), datetime.now(UTC)],
        )
        conn.commit()

    print("✅ Default account created/verified")

    # Insert default user preferences
    with storage.connection() as conn:
        conn.execute(
            """
            INSERT INTO user_preferences (
                id, risk_tolerance, allow_long, allow_short, allow_options,
                allow_crypto, allow_futures, max_position_size_pct,
                watchlist_refresh_minutes, watchlist_auto_expand,
                watchlist_price_weight, watchlist_technical_weight,
                created_at, updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
            ON CONFLICT (id) DO NOTHING
            """,
            [
                "default-user",
                5,  # risk_tolerance (1-10 scale)
                True,  # allow_long
                False,  # allow_short
                False,  # allow_options
                False,  # allow_crypto
                False,  # allow_futures
                10.0,  # max_position_size_pct
                15,  # watchlist_refresh_minutes
                False,  # watchlist_auto_expand
                50.0,  # watchlist_price_weight
                50.0,  # watchlist_technical_weight
                datetime.now(UTC),
                datetime.now(UTC),
            ],
        )
        conn.commit()

    print("✅ Default preferences created/verified")

    # Verify
    result = storage.query("SELECT id, name FROM portfolio_accounts")
    print(f"\nPortfolio accounts: {len(result.to_dicts())}")
    for account in result.to_dicts():
        print(f"  - {account['id']}: {account['name']}")


if __name__ == "__main__":
    seed_default_data()
