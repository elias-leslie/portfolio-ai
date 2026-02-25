-- Migration 064: Add bid/ask columns to price_cache (GAP-029)
-- Enables spread calculation and transaction cost modeling

ALTER TABLE price_cache
ADD COLUMN IF NOT EXISTS bid DOUBLE PRECISION,
ADD COLUMN IF NOT EXISTS ask DOUBLE PRECISION,
ADD COLUMN IF NOT EXISTS bid_size INTEGER,
ADD COLUMN IF NOT EXISTS ask_size INTEGER;

-- Spread calculated as derived column in queries: (ask - bid)
-- Not stored to avoid stale data issues

COMMENT ON COLUMN price_cache.bid IS 'Best bid price';
COMMENT ON COLUMN price_cache.ask IS 'Best ask price';
COMMENT ON COLUMN price_cache.bid_size IS 'Size at bid (shares)';
COMMENT ON COLUMN price_cache.ask_size IS 'Size at ask (shares)';
