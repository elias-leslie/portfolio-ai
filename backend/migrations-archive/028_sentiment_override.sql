-- Migration 028: Add sentiment_override column to user_article_feedback
-- Purpose: Allow users to correct incorrect sentiment scores for better quality metrics
--
-- Part of: Fix Plain Language Headline Transformation Bug (Phase 2)
-- Created: 2025-11-11
-- Related: tasks-0051-fix-headline-transformation-bug.md

-- Add sentiment_override column to user_article_feedback
-- Use IF NOT EXISTS to make migration idempotent
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'user_article_feedback'
        AND column_name = 'sentiment_override'
    ) THEN
        ALTER TABLE user_article_feedback
            ADD COLUMN sentiment_override FLOAT CHECK (sentiment_override >= -1.0 AND sentiment_override <= 1.0);
    END IF;
END $$;

-- Add comment for documentation
COMMENT ON COLUMN user_article_feedback.sentiment_override IS 'User-corrected sentiment score (-1.0 to 1.0), overrides original sentiment when provided';
