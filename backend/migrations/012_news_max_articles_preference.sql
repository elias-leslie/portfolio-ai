-- Add configurable news max articles preference.
ALTER TABLE user_preferences
    ADD COLUMN IF NOT EXISTS news_max_articles INTEGER DEFAULT 10;

-- Ensure existing rows have the default value.
UPDATE user_preferences
SET news_max_articles = 10
WHERE news_max_articles IS NULL;
