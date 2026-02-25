-- Migration: 004_add_is_stale_column
-- Description: Add is_stale BOOLEAN column to watchlist_snapshots for market hours-aware staleness

BEGIN TRANSACTION;

-- Add is_stale column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'watchlist_snapshots'
        AND column_name = 'is_stale'
    ) THEN
        ALTER TABLE watchlist_snapshots
        ADD COLUMN is_stale BOOLEAN DEFAULT FALSE NOT NULL;
    END IF;
END $$;

-- Set default to FALSE for existing rows (can be recalculated on next refresh)
UPDATE watchlist_snapshots
SET is_stale = COALESCE(is_stale, FALSE)
WHERE is_stale IS NULL;

COMMIT;
