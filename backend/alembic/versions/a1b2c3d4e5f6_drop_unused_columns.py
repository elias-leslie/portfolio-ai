"""drop unused columns identified by clean_it

Revision ID: a1b2c3d4e5f6
Revises: 217b5c166647
Create Date: 2026-02-17 00:00:00.000000

All columns verified: zero Python reads/writes, no FK constraints, no raw SQL refs.
"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: str | Sequence[str] | None = '217b5c166647'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Drop unused columns from user_preferences, reference_cache, institutional_ownership_summary, insider_transactions."""
    # user_preferences: 5 unused columns (migrations 008 and 019, Nov 2025)
    # watchlist_price_clamp: never consumed by scorer or API
    # watchlist_show_fundamentals: not in PreferencesResponse model
    # price/technical/fundamental_sub_weights: watchlist_score_weights JSONB used instead
    op.execute("ALTER TABLE user_preferences DROP COLUMN IF EXISTS watchlist_price_clamp")
    op.execute("ALTER TABLE user_preferences DROP COLUMN IF EXISTS watchlist_show_fundamentals")
    op.execute("ALTER TABLE user_preferences DROP COLUMN IF EXISTS price_sub_weights")
    op.execute("ALTER TABLE user_preferences DROP COLUMN IF EXISTS technical_sub_weights")
    op.execute("ALTER TABLE user_preferences DROP COLUMN IF EXISTS fundamental_sub_weights")

    # reference_cache: 2 unused columns (migration 068, Dec 2025)
    # dedicated institutional_ownership_summary table used instead
    op.execute("ALTER TABLE reference_cache DROP COLUMN IF EXISTS held_percent_institutions")
    op.execute("ALTER TABLE reference_cache DROP COLUMN IF EXISTS held_percent_insiders")

    # institutional_ownership_summary: 2 unused columns (migration 068, Dec 2025)
    # not in InstitutionalSummary dataclass or SELECT queries
    op.execute("ALTER TABLE institutional_ownership_summary DROP COLUMN IF EXISTS institutions_new")
    op.execute("ALTER TABLE institutional_ownership_summary DROP COLUMN IF EXISTS institutions_soldout")

    # insider_transactions: 1 unused column (migration 068, Dec 2025)
    # not in InsiderTransaction dataclass or SELECT queries
    op.execute("ALTER TABLE insider_transactions DROP COLUMN IF EXISTS insider_ownership_pct")


def downgrade() -> None:
    """Re-add dropped columns (data will be NULL)."""
    op.execute("ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS watchlist_price_clamp INTEGER DEFAULT 20")
    op.execute("ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS watchlist_show_fundamentals BOOLEAN DEFAULT TRUE")
    op.execute("ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS price_sub_weights JSONB DEFAULT '{\"change_pct\": 100}'::jsonb")
    op.execute("ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS technical_sub_weights JSONB DEFAULT '{\"macd\": 33, \"trend\": 34, \"rsi_14\": 33}'::jsonb")
    op.execute("ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS fundamental_sub_weights JSONB DEFAULT '{\"growth\": 35, \"health\": 25, \"sentiment\": 10, \"valuation\": 30}'::jsonb")
    op.execute("ALTER TABLE reference_cache ADD COLUMN IF NOT EXISTS held_percent_institutions DOUBLE PRECISION")
    op.execute("ALTER TABLE reference_cache ADD COLUMN IF NOT EXISTS held_percent_insiders DOUBLE PRECISION")
    op.execute("ALTER TABLE institutional_ownership_summary ADD COLUMN IF NOT EXISTS institutions_new INTEGER")
    op.execute("ALTER TABLE institutional_ownership_summary ADD COLUMN IF NOT EXISTS institutions_soldout INTEGER")
    op.execute("ALTER TABLE insider_transactions ADD COLUMN IF NOT EXISTS insider_ownership_pct DOUBLE PRECISION")
