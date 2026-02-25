-- Migration 015: SEC Filing Metadata
-- Add columns to news_cache for SEC EDGAR filing metadata

-- Filing type (8-K, 10-Q, 10-K, Form 4, etc.)
ALTER TABLE news_cache ADD COLUMN IF NOT EXISTS filing_type TEXT;

-- Material event flag (8-K items 1.01, 1.02, 2.01, 2.02, 4.02, 5.02, 8.01, or large Form 4 trades)
ALTER TABLE news_cache ADD COLUMN IF NOT EXISTS is_material_event BOOLEAN DEFAULT FALSE;

-- Plain language headline (user-friendly translation of filing types)
ALTER TABLE news_cache ADD COLUMN IF NOT EXISTS plain_language_headline TEXT;

-- Indexes for filtering and querying
CREATE INDEX IF NOT EXISTS idx_news_filing_type ON news_cache(filing_type) WHERE filing_type IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_news_material_events ON news_cache(is_material_event) WHERE is_material_event = TRUE;

-- Comments for documentation
COMMENT ON COLUMN news_cache.filing_type IS 'SEC filing type (8-K, 10-Q, 10-K, 4, 13F, etc.)';
COMMENT ON COLUMN news_cache.is_material_event IS 'True if filing represents material event (8-K items, large insider trades)';
COMMENT ON COLUMN news_cache.plain_language_headline IS 'Plain-language translation of filing (e.g., "Insider trading activity reported")';
