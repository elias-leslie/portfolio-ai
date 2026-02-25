-- Migration 026: Add user_article_feedback table for article quality feedback
-- Purpose: Store user thumbs up/down feedback on articles to train source personalization
--
-- Part of: News Source Quality Profiling System (Phase 1)
-- Created: 2025-11-11
-- Related: tasks-0049-news-source-quality-profiling.md

-- Create user_article_feedback table
CREATE TABLE IF NOT EXISTS user_article_feedback (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL DEFAULT 'default',
    article_url TEXT NOT NULL,
    article_hash VARCHAR(64) NOT NULL,
    vendor VARCHAR(100) NOT NULL,
    is_useful BOOLEAN NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT unique_user_article UNIQUE (user_id, article_hash)
);

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_user_article_feedback_vendor ON user_article_feedback(vendor);
CREATE INDEX IF NOT EXISTS idx_user_article_feedback_user_id ON user_article_feedback(user_id);
CREATE INDEX IF NOT EXISTS idx_user_article_feedback_article_hash ON user_article_feedback(article_hash);
CREATE INDEX IF NOT EXISTS idx_user_article_feedback_created_at ON user_article_feedback(created_at DESC);

-- Add foreign key constraint to user_preferences
ALTER TABLE user_article_feedback
    ADD CONSTRAINT fk_user_article_feedback_user
    FOREIGN KEY (user_id)
    REFERENCES user_preferences(id)
    ON DELETE CASCADE;

-- Add comments for documentation
COMMENT ON TABLE user_article_feedback IS 'User feedback (thumbs up/down) on news articles for quality training';
COMMENT ON COLUMN user_article_feedback.user_id IS 'User identifier (references user_preferences.id)';
COMMENT ON COLUMN user_article_feedback.article_url IS 'Full URL of the article';
COMMENT ON COLUMN user_article_feedback.article_hash IS 'Content hash for deduplication (from news_cache.content_hash)';
COMMENT ON COLUMN user_article_feedback.vendor IS 'News vendor/source that provided the article';
COMMENT ON COLUMN user_article_feedback.is_useful IS 'TRUE=thumbs up (useful), FALSE=thumbs down (not useful)';
COMMENT ON COLUMN user_article_feedback.created_at IS 'When feedback was submitted';
