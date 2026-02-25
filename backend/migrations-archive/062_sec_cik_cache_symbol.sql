-- Migration 062: Rename sec_cik_cache.ticker to symbol for consistency
-- Completes the ticker→symbol standardization across all tables

-- Rename ticker → symbol
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'sec_cik_cache' AND column_name = 'ticker') THEN
        ALTER TABLE sec_cik_cache RENAME COLUMN ticker TO symbol;
    END IF;
END $$;

-- Update index name for consistency
DROP INDEX IF EXISTS idx_sec_cik_cache_ticker;
CREATE INDEX IF NOT EXISTS idx_sec_cik_cache_symbol ON sec_cik_cache(symbol);
