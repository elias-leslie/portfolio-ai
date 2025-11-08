-- Migration 018: Remove account_id from watchlist_items
--
-- Purpose: Separate watchlist from portfolio accounts
-- - Watchlist = stocks you're MONITORING (global, user-level)
-- - Portfolio = stocks you OWN (account-specific)
--
-- This migration removes the account_id FK from watchlist_items to prevent
-- CASCADE delete data loss when deleting portfolio accounts.
--
-- Risk: If duplicate symbols exist across accounts, this will consolidate them.
-- Strategy: Keep the most recently updated watchlist_item per symbol.

-- Step 1: Handle duplicate symbols (if any exist)
-- Keep the most recently updated item, delete older duplicates
WITH ranked_items AS (
    SELECT
        id,
        symbol,
        ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY updated_at DESC) as rn
    FROM watchlist_items
)
DELETE FROM watchlist_items
WHERE id IN (
    SELECT id FROM ranked_items WHERE rn > 1
);

-- Step 2: Drop foreign key constraint
ALTER TABLE watchlist_items
DROP CONSTRAINT IF EXISTS watchlist_items_account_id_fkey;

-- Step 3: Drop unique constraint (account_id, symbol)
ALTER TABLE watchlist_items
DROP CONSTRAINT IF EXISTS watchlist_items_account_id_symbol_key;

-- Step 4: Drop account_id column
ALTER TABLE watchlist_items
DROP COLUMN IF EXISTS account_id;

-- Step 5: Add new unique constraint on symbol only
-- This prevents duplicate symbols in watchlist (global list)
-- Use DO block to add constraint only if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'watchlist_items_symbol_key'
    ) THEN
        ALTER TABLE watchlist_items
        ADD CONSTRAINT watchlist_items_symbol_key UNIQUE (symbol);
    END IF;
END $$;

-- Verification query (run after migration):
-- SELECT COUNT(*) as total_items, COUNT(DISTINCT symbol) as unique_symbols FROM watchlist_items;
-- Expected: total_items = unique_symbols (no duplicates)
