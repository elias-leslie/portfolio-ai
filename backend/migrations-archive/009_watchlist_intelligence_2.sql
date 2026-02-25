-- Migration 009: Watchlist Intelligence 2.0 - Volume, Timeframes, Percentiles, User Preferences
-- Created: 2025-11-02
-- Description: Adds volume confirmation, multi-timeframe alignment, percentile context, and user-configurable scoring
-- Dependencies: Migration 008 (Narrative Intelligence)

-- ============================================================================
-- Part 1: watchlist_snapshots - Add volume, timeframe, and percentile columns
-- ============================================================================

ALTER TABLE watchlist_snapshots
ADD COLUMN IF NOT EXISTS volume_relative DOUBLE PRECISION;

COMMENT ON COLUMN watchlist_snapshots.volume_relative IS 'Current volume / 50-day average volume (e.g., 2.3 = 2.3x above average)';

ALTER TABLE watchlist_snapshots
ADD COLUMN IF NOT EXISTS timeframe_short_aligned BOOLEAN DEFAULT FALSE;

COMMENT ON COLUMN watchlist_snapshots.timeframe_short_aligned IS 'Short-term alignment: price > SMA_20 > SMA_50 (bullish short-term setup)';

ALTER TABLE watchlist_snapshots
ADD COLUMN IF NOT EXISTS timeframe_long_aligned BOOLEAN DEFAULT FALSE;

COMMENT ON COLUMN watchlist_snapshots.timeframe_long_aligned IS 'Long-term alignment: SMA_50 > SMA_200 (bullish long-term trend)';

ALTER TABLE watchlist_snapshots
ADD COLUMN IF NOT EXISTS percentile_rank_30d DOUBLE PRECISION;

COMMENT ON COLUMN watchlist_snapshots.percentile_rank_30d IS 'Overall score percentile rank vs 30-day history (0-100)';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'check_percentile_rank_30d_range'
        AND conrelid = 'watchlist_snapshots'::regclass
    ) THEN
        ALTER TABLE watchlist_snapshots
        ADD CONSTRAINT check_percentile_rank_30d_range
        CHECK (percentile_rank_30d IS NULL OR (percentile_rank_30d >= 0 AND percentile_rank_30d <= 100));
    END IF;
END $$;

-- ============================================================================
-- Part 2: technical_indicators - Add SMA_5 for AVOID signal detection
-- ============================================================================

ALTER TABLE technical_indicators
ADD COLUMN IF NOT EXISTS sma_5 DOUBLE PRECISION;

COMMENT ON COLUMN technical_indicators.sma_5 IS '5-day simple moving average (used for declining trend detection in AVOID signals)';

-- ============================================================================
-- Part 3: user_preferences - Add user-configurable watchlist scoring preferences
-- ============================================================================

ALTER TABLE user_preferences
ADD COLUMN IF NOT EXISTS watchlist_score_weights JSONB DEFAULT '{"price": 33, "technical": 33, "fundamental": 34}'::jsonb;

COMMENT ON COLUMN user_preferences.watchlist_score_weights IS 'User-defined weights for overall score calculation (price/technical/fundamental, sum must be 100)';

ALTER TABLE user_preferences
ADD COLUMN IF NOT EXISTS watchlist_avoid_threshold INTEGER DEFAULT 2;

COMMENT ON COLUMN user_preferences.watchlist_avoid_threshold IS 'Number of declining indicators needed to trigger AVOID signal (1-4, default 2)';

ALTER TABLE user_preferences
ADD COLUMN IF NOT EXISTS watchlist_volume_surge_multiplier DOUBLE PRECISION DEFAULT 1.5;

COMMENT ON COLUMN user_preferences.watchlist_volume_surge_multiplier IS 'Multiplier above average volume to consider it a surge (default 1.5 = 1.5x average)';

-- Add constraints for user preferences
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'check_avoid_threshold_range'
        AND conrelid = 'user_preferences'::regclass
    ) THEN
        ALTER TABLE user_preferences
        ADD CONSTRAINT check_avoid_threshold_range
        CHECK (watchlist_avoid_threshold BETWEEN 1 AND 4);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'check_volume_surge_multiplier_range'
        AND conrelid = 'user_preferences'::regclass
    ) THEN
        ALTER TABLE user_preferences
        ADD CONSTRAINT check_volume_surge_multiplier_range
        CHECK (watchlist_volume_surge_multiplier BETWEEN 1.0 AND 3.0);
    END IF;
END $$;

-- ============================================================================
-- Part 4: Performance indexes
-- ============================================================================

-- Index for percentile queries (fetch last 30 days of snapshots per item)
CREATE INDEX IF NOT EXISTS idx_watchlist_snapshots_item_fetched
ON watchlist_snapshots(item_id, fetched_at DESC);

-- ============================================================================
-- ROLLBACK SCRIPT (commented out - run manually if needed)
-- ============================================================================

-- ALTER TABLE watchlist_snapshots DROP COLUMN IF EXISTS volume_relative;
-- ALTER TABLE watchlist_snapshots DROP COLUMN IF EXISTS timeframe_short_aligned;
-- ALTER TABLE watchlist_snapshots DROP COLUMN IF EXISTS timeframe_long_aligned;
-- ALTER TABLE watchlist_snapshots DROP COLUMN IF EXISTS percentile_rank_30d;
-- ALTER TABLE watchlist_snapshots DROP CONSTRAINT IF EXISTS check_percentile_rank_30d_range;
-- ALTER TABLE technical_indicators DROP COLUMN IF EXISTS sma_5;
-- ALTER TABLE user_preferences DROP COLUMN IF EXISTS watchlist_score_weights;
-- ALTER TABLE user_preferences DROP COLUMN IF EXISTS watchlist_avoid_threshold;
-- ALTER TABLE user_preferences DROP COLUMN IF EXISTS watchlist_volume_surge_multiplier;
-- ALTER TABLE user_preferences DROP CONSTRAINT IF EXISTS check_avoid_threshold_range;
-- ALTER TABLE user_preferences DROP CONSTRAINT IF EXISTS check_volume_surge_multiplier_range;
-- DROP INDEX IF EXISTS idx_watchlist_snapshots_item_fetched;
