-- Migration 032: Add ML quality prediction fields to news_cache
-- Created: 2025-11-11
-- Purpose: Store ML model predictions for article quality

-- Add quality prediction fields to news_cache
ALTER TABLE news_cache
ADD COLUMN IF NOT EXISTS quality_prediction BOOLEAN DEFAULT NULL,
ADD COLUMN IF NOT EXISTS quality_confidence REAL DEFAULT NULL;

-- Add index for filtering high-quality articles
CREATE INDEX IF NOT EXISTS idx_news_cache_quality ON news_cache(quality_prediction, quality_confidence)
WHERE quality_prediction IS NOT NULL;

-- Add comment
COMMENT ON COLUMN news_cache.quality_prediction IS 'ML model prediction: true=useful, false=not useful, null=not scored';
COMMENT ON COLUMN news_cache.quality_confidence IS 'ML model confidence score (0.0-1.0)';
