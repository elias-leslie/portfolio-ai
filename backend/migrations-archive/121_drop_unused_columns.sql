-- Migration 121: Drop unused columns identified by clean_it (2026-02-17)
-- All columns verified: zero Python reads/writes, no FK constraints, no raw SQL refs.

-- user_preferences: 5 unused columns from migrations 008 and 019
-- watchlist_price_clamp: added 2025-11-01, never consumed by any scorer or API
-- watchlist_show_fundamentals: added 2025-11-01, not in PreferencesResponse model
-- price_sub_weights: added 2025-11-08, watchlist_score_weights JSONB used instead
-- technical_sub_weights: added 2025-11-08, never wired into any scorer
-- fundamental_sub_weights: added 2025-11-08, never wired into any scorer
ALTER TABLE user_preferences DROP COLUMN IF EXISTS watchlist_price_clamp;
ALTER TABLE user_preferences DROP COLUMN IF EXISTS watchlist_show_fundamentals;
ALTER TABLE user_preferences DROP COLUMN IF EXISTS price_sub_weights;
ALTER TABLE user_preferences DROP COLUMN IF EXISTS technical_sub_weights;
ALTER TABLE user_preferences DROP COLUMN IF EXISTS fundamental_sub_weights;

-- reference_cache: 2 unused columns from migration 068
-- held_percent_institutions: dedicated institutional_ownership_summary table used instead
-- held_percent_insiders: same, dedicated tables used
ALTER TABLE reference_cache DROP COLUMN IF EXISTS held_percent_institutions;
ALTER TABLE reference_cache DROP COLUMN IF EXISTS held_percent_insiders;

-- institutional_ownership_summary: 2 unused columns from migration 068
-- institutions_new: not in InstitutionalSummary dataclass or SELECT queries
-- institutions_soldout: same
ALTER TABLE institutional_ownership_summary DROP COLUMN IF EXISTS institutions_new;
ALTER TABLE institutional_ownership_summary DROP COLUMN IF EXISTS institutions_soldout;

-- insider_transactions: 1 unused column from migration 068
-- insider_ownership_pct: not in InsiderTransaction dataclass or SELECT queries
ALTER TABLE insider_transactions DROP COLUMN IF EXISTS insider_ownership_pct;
