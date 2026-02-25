-- Add configurable news lookback window preference.
ALTER TABLE user_preferences
    ADD COLUMN IF NOT EXISTS news_lookback_hours INTEGER DEFAULT 6;

-- Ensure existing rows have the default value.
UPDATE user_preferences
SET news_lookback_hours = 6
WHERE news_lookback_hours IS NULL;
