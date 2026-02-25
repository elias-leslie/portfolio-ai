-- Migration: 002_watchlist_preferences
-- Description: Add watchlist-related preference columns with defaults

BEGIN TRANSACTION;

ALTER TABLE user_preferences
    ADD COLUMN IF NOT EXISTS watchlist_refresh_minutes INTEGER DEFAULT 5;

ALTER TABLE user_preferences
    ADD COLUMN IF NOT EXISTS watchlist_auto_expand BOOLEAN DEFAULT false;

ALTER TABLE user_preferences
    ADD COLUMN IF NOT EXISTS watchlist_price_weight DOUBLE DEFAULT 50.0;

ALTER TABLE user_preferences
    ADD COLUMN IF NOT EXISTS watchlist_technical_weight DOUBLE DEFAULT 50.0;

UPDATE user_preferences
SET
    watchlist_refresh_minutes = COALESCE(watchlist_refresh_minutes, 5),
    watchlist_auto_expand = COALESCE(watchlist_auto_expand, false),
    watchlist_price_weight = COALESCE(watchlist_price_weight, 50.0),
    watchlist_technical_weight = COALESCE(watchlist_technical_weight, 50.0);

COMMIT;
