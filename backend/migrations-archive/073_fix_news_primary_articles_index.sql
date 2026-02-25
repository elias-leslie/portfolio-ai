-- Migration 073: Fix orphaned idx_news_primary_articles index
-- Created: 2025-12-04
-- Purpose: Migration 016 created this index on 'ticker' column, but Migration 059
--          renamed the column to 'symbol'. This fixes the index to use correct column.

-- Drop the old index that references non-existent 'ticker' column
DROP INDEX IF EXISTS idx_news_primary_articles;

-- Recreate with correct column name
CREATE INDEX IF NOT EXISTS idx_news_primary_articles
  ON news_cache(symbol, is_primary_article, published_at DESC)
  WHERE is_primary_article = TRUE;
