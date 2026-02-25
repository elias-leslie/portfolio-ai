-- Migration 022: Add source tracking to watchlist_items
--
-- Purpose: Track whether watchlist items are added manually or from portfolio
-- - 'manual': User explicitly added to watchlist
-- - 'portfolio': Auto-synced from portfolio positions
--
-- This enables:
-- 1. Portfolio-watchlist integration (auto-sync portfolio tickers)
-- 2. Visual indicators in watchlist (show which tickers are in portfolio)
-- 3. User control (can remove portfolio-sourced tickers)
--
-- Strategy: Additive only, no cascade deletes between portfolio and watchlist

-- Step 1: Add source column with default 'manual'
-- All existing items are considered manually added
ALTER TABLE watchlist_items
ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'manual';

-- Step 2: Add check constraint to ensure valid source values
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'watchlist_items_source_check'
    ) THEN
        ALTER TABLE watchlist_items
        ADD CONSTRAINT watchlist_items_source_check CHECK (source IN ('manual', 'portfolio'));
    END IF;
END $$;

-- Step 3: Create index for efficient filtering by source
-- Note: We don't need account_id in the index since watchlist is now global
CREATE INDEX IF NOT EXISTS idx_watchlist_items_source ON watchlist_items(source);

-- Verification query (run after migration):
-- SELECT source, COUNT(*) FROM watchlist_items GROUP BY source;
-- Expected: All existing items have source='manual'
