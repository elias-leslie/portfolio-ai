-- Migration 027: Extend user_preferences for source quality weights and filters
-- Purpose: Add user-adjustable weights and filtering preferences for news quality
--
-- Part of: News Source Quality Profiling System (Phase 1)
-- Created: 2025-11-11
-- Related: tasks-0049-news-source-quality-profiling.md

-- Add source quality weight columns (normalized to 0.0-1.0, but allow user to set raw values)
ALTER TABLE user_preferences
    ADD COLUMN IF NOT EXISTS source_duplicate_weight DOUBLE PRECISION DEFAULT 0.30 CHECK (source_duplicate_weight >= 0.0),
    ADD COLUMN IF NOT EXISTS source_diversity_weight DOUBLE PRECISION DEFAULT 0.25 CHECK (source_diversity_weight >= 0.0),
    ADD COLUMN IF NOT EXISTS source_confidence_weight DOUBLE PRECISION DEFAULT 0.20 CHECK (source_confidence_weight >= 0.0),
    ADD COLUMN IF NOT EXISTS source_freshness_weight DOUBLE PRECISION DEFAULT 0.15 CHECK (source_freshness_weight >= 0.0),
    ADD COLUMN IF NOT EXISTS source_feedback_weight DOUBLE PRECISION DEFAULT 0.10 CHECK (source_feedback_weight >= 0.0);

-- Add neutral article filter toggle
ALTER TABLE user_preferences
    ADD COLUMN IF NOT EXISTS filter_neutral_articles BOOLEAN DEFAULT FALSE;

-- Add profiling interval preference (in hours)
ALTER TABLE user_preferences
    ADD COLUMN IF NOT EXISTS news_profiling_interval_hours INTEGER DEFAULT 12 CHECK (news_profiling_interval_hours > 0);

-- Add comments for documentation
COMMENT ON COLUMN user_preferences.source_duplicate_weight IS 'Weight for duplicate penalty in quality score (0-1, normalized on use)';
COMMENT ON COLUMN user_preferences.source_diversity_weight IS 'Weight for headline diversity in quality score (0-1, normalized on use)';
COMMENT ON COLUMN user_preferences.source_confidence_weight IS 'Weight for sentiment confidence in quality score (0-1, normalized on use)';
COMMENT ON COLUMN user_preferences.source_freshness_weight IS 'Weight for article freshness in quality score (0-1, normalized on use)';
COMMENT ON COLUMN user_preferences.source_feedback_weight IS 'Weight for user feedback in quality score (0-1, normalized on use)';
COMMENT ON COLUMN user_preferences.filter_neutral_articles IS 'If TRUE, hide neutral articles (sentiment between ±0.2)';
COMMENT ON COLUMN user_preferences.news_profiling_interval_hours IS 'How often to run source quality profiling (in hours, default 12)';
