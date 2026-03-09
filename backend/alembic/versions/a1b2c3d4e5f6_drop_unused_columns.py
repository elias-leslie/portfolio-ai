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


def _execute_if_owned(table_name: str, statement: str) -> None:
    op.execute(
        f"""
        DO $$
        DECLARE
            owner_name text;
        BEGIN
            SELECT tableowner
            INTO owner_name
            FROM pg_tables
            WHERE schemaname = 'public' AND tablename = '{table_name}';

            IF owner_name = current_user THEN
                EXECUTE '{statement}';
            END IF;
        END $$;
        """
    )


def upgrade() -> None:
    """Drop unused columns from user_preferences, reference_cache, institutional_ownership_summary, insider_transactions."""
    # user_preferences: 5 unused columns (migrations 008 and 019, Nov 2025)
    # watchlist_price_clamp: never consumed by scorer or API
    # watchlist_show_fundamentals: not in PreferencesResponse model
    # price/technical/fundamental_sub_weights: watchlist_score_weights JSONB used instead
    _execute_if_owned("user_preferences", "ALTER TABLE public.user_preferences DROP COLUMN IF EXISTS watchlist_price_clamp")
    _execute_if_owned("user_preferences", "ALTER TABLE public.user_preferences DROP COLUMN IF EXISTS watchlist_show_fundamentals")
    _execute_if_owned("user_preferences", "ALTER TABLE public.user_preferences DROP COLUMN IF EXISTS price_sub_weights")
    _execute_if_owned("user_preferences", "ALTER TABLE public.user_preferences DROP COLUMN IF EXISTS technical_sub_weights")
    _execute_if_owned("user_preferences", "ALTER TABLE public.user_preferences DROP COLUMN IF EXISTS fundamental_sub_weights")

    # reference_cache: 2 unused columns (migration 068, Dec 2025)
    # dedicated institutional_ownership_summary table used instead
    _execute_if_owned("reference_cache", "ALTER TABLE public.reference_cache DROP COLUMN IF EXISTS held_percent_institutions")
    _execute_if_owned("reference_cache", "ALTER TABLE public.reference_cache DROP COLUMN IF EXISTS held_percent_insiders")

    # institutional_ownership_summary: 2 unused columns (migration 068, Dec 2025)
    # not in InstitutionalSummary dataclass or SELECT queries
    _execute_if_owned("institutional_ownership_summary", "ALTER TABLE public.institutional_ownership_summary DROP COLUMN IF EXISTS institutions_new")
    _execute_if_owned("institutional_ownership_summary", "ALTER TABLE public.institutional_ownership_summary DROP COLUMN IF EXISTS institutions_soldout")

    # insider_transactions: 1 unused column (migration 068, Dec 2025)
    # not in InsiderTransaction dataclass or SELECT queries
    _execute_if_owned("insider_transactions", "ALTER TABLE public.insider_transactions DROP COLUMN IF EXISTS insider_ownership_pct")


def downgrade() -> None:
    """Re-add dropped columns (data will be NULL)."""
    _execute_if_owned("user_preferences", "ALTER TABLE public.user_preferences ADD COLUMN IF NOT EXISTS watchlist_price_clamp INTEGER DEFAULT 20")
    _execute_if_owned("user_preferences", "ALTER TABLE public.user_preferences ADD COLUMN IF NOT EXISTS watchlist_show_fundamentals BOOLEAN DEFAULT TRUE")
    _execute_if_owned("user_preferences", "ALTER TABLE public.user_preferences ADD COLUMN IF NOT EXISTS price_sub_weights JSONB DEFAULT ''{\"\"change_pct\"\": 100}''::jsonb")
    _execute_if_owned("user_preferences", "ALTER TABLE public.user_preferences ADD COLUMN IF NOT EXISTS technical_sub_weights JSONB DEFAULT ''{\"\"macd\"\": 33, \"\"trend\"\": 34, \"\"rsi_14\"\": 33}''::jsonb")
    _execute_if_owned("user_preferences", "ALTER TABLE public.user_preferences ADD COLUMN IF NOT EXISTS fundamental_sub_weights JSONB DEFAULT ''{\"\"growth\"\": 35, \"\"health\"\": 25, \"\"sentiment\"\": 10, \"\"valuation\"\": 30}''::jsonb")
    _execute_if_owned("reference_cache", "ALTER TABLE public.reference_cache ADD COLUMN IF NOT EXISTS held_percent_institutions DOUBLE PRECISION")
    _execute_if_owned("reference_cache", "ALTER TABLE public.reference_cache ADD COLUMN IF NOT EXISTS held_percent_insiders DOUBLE PRECISION")
    _execute_if_owned("institutional_ownership_summary", "ALTER TABLE public.institutional_ownership_summary ADD COLUMN IF NOT EXISTS institutions_new INTEGER")
    _execute_if_owned("institutional_ownership_summary", "ALTER TABLE public.institutional_ownership_summary ADD COLUMN IF NOT EXISTS institutions_soldout INTEGER")
    _execute_if_owned("insider_transactions", "ALTER TABLE public.insider_transactions ADD COLUMN IF NOT EXISTS insider_ownership_pct DOUBLE PRECISION")
