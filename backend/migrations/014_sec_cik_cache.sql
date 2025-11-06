-- Migration 014: SEC CIK (Central Index Key) Cache
-- Create table to store ticker→CIK mappings from SEC EDGAR

CREATE TABLE IF NOT EXISTS sec_cik_cache (
    ticker TEXT PRIMARY KEY NOT NULL,
    cik TEXT NOT NULL,
    company_name TEXT,
    last_updated TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Index for CIK lookups (reverse lookup)
CREATE INDEX IF NOT EXISTS idx_sec_cik_cache_cik ON sec_cik_cache(cik);

-- Index for last_updated (for finding stale entries)
CREATE INDEX IF NOT EXISTS idx_sec_cik_cache_updated ON sec_cik_cache(last_updated DESC);

-- Comments for documentation
COMMENT ON TABLE sec_cik_cache IS 'SEC EDGAR ticker to CIK mapping cache. CIK numbers are permanent (never recycled), so cached values remain valid forever.';
COMMENT ON COLUMN sec_cik_cache.ticker IS 'Stock ticker symbol (uppercase, e.g., NVDA)';
COMMENT ON COLUMN sec_cik_cache.cik IS 'SEC Central Index Key (10-digit zero-padded string, e.g., 0001045810)';
COMMENT ON COLUMN sec_cik_cache.company_name IS 'Company name from SEC (optional, for reference)';
COMMENT ON COLUMN sec_cik_cache.last_updated IS 'Last time this mapping was verified/updated';
COMMENT ON COLUMN sec_cik_cache.created_at IS 'When this mapping was first cached';
