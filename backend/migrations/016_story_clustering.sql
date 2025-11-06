-- Migration 016: Story clustering fields for semantic news deduplication
-- Phase 2: Plain Language UI

-- Add story clustering fields to news_cache
ALTER TABLE news_cache
  ADD COLUMN IF NOT EXISTS story_id TEXT,
  ADD COLUMN IF NOT EXISTS is_primary_article BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS coverage_count INT DEFAULT 1;

-- Create index for story clustering queries
CREATE INDEX IF NOT EXISTS idx_news_story_id
  ON news_cache(story_id)
  WHERE story_id IS NOT NULL;

-- Create index for primary article queries
CREATE INDEX IF NOT EXISTS idx_news_primary_articles
  ON news_cache(ticker, is_primary_article, published_at DESC)
  WHERE is_primary_article = TRUE;

-- Add comment for documentation
COMMENT ON COLUMN news_cache.story_id IS
  'UUID linking articles about the same story/event (semantic clustering)';

COMMENT ON COLUMN news_cache.is_primary_article IS
  'True if this is the primary article for a clustered story (highest priority source)';

COMMENT ON COLUMN news_cache.coverage_count IS
  'Number of sources that covered this story (indicates importance)';
