-- Migration: 005_refresh_controls
-- Description: Add comprehensive refresh control system with global defaults and per-feature overrides

BEGIN TRANSACTION;

-- Add global default refresh interval (applies to all features unless overridden)
ALTER TABLE user_preferences
    ADD COLUMN IF NOT EXISTS default_refresh_minutes INTEGER DEFAULT 15;

-- Add per-feature refresh overrides (NULL = use default_refresh_minutes)
ALTER TABLE user_preferences
    ADD COLUMN IF NOT EXISTS watchlist_refresh_override INTEGER DEFAULT NULL;

ALTER TABLE user_preferences
    ADD COLUMN IF NOT EXISTS portfolio_refresh_override INTEGER DEFAULT NULL;

ALTER TABLE user_preferences
    ADD COLUMN IF NOT EXISTS news_refresh_override INTEGER DEFAULT NULL;

-- Add frontend polling interval (fixed at 30 seconds for responsiveness)
ALTER TABLE user_preferences
    ADD COLUMN IF NOT EXISTS frontend_poll_interval INTEGER DEFAULT 30;

-- Migrate existing watchlist_refresh_minutes to default_refresh_minutes
-- This ensures backward compatibility for users who already have preferences set
UPDATE user_preferences
SET default_refresh_minutes = COALESCE(watchlist_refresh_minutes, 15)
WHERE default_refresh_minutes IS NULL OR default_refresh_minutes = 15;

-- Set watchlist_refresh_minutes to 15 for consistency (now acts as override if customized)
UPDATE user_preferences
SET watchlist_refresh_minutes = 15
WHERE watchlist_refresh_minutes IS NULL;

COMMIT;
