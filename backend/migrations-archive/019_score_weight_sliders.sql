-- Migration 019: Score weight sliders for all sub-metrics
-- Add JSONB fields for detailed weight configuration

-- Main score weights (3-pillar: price/technical/fundamental)
ALTER TABLE user_preferences
ADD COLUMN IF NOT EXISTS watchlist_score_weights JSONB DEFAULT '{"price": 33, "technical": 33, "fundamental": 34}'::jsonb;

-- Price component sub-weights
ALTER TABLE user_preferences
ADD COLUMN IF NOT EXISTS price_sub_weights JSONB DEFAULT '{"change_pct": 100}'::jsonb;

-- Technical component sub-weights (RSI/Trend/MACD)
ALTER TABLE user_preferences
ADD COLUMN IF NOT EXISTS technical_sub_weights JSONB DEFAULT '{"rsi_14": 33, "trend": 34, "macd": 33}'::jsonb;

-- Fundamental component sub-weights (4-pillar: valuation/growth/health/sentiment)
ALTER TABLE user_preferences
ADD COLUMN IF NOT EXISTS fundamental_sub_weights JSONB DEFAULT '{"valuation": 30, "growth": 35, "health": 25, "sentiment": 10}'::jsonb;

-- Add comments
COMMENT ON COLUMN user_preferences.watchlist_score_weights IS 'Top-level weights: price, technical, fundamental (must sum to 100)';
COMMENT ON COLUMN user_preferences.price_sub_weights IS 'Price component sub-weights (currently only change_pct, future: beta, volatility)';
COMMENT ON COLUMN user_preferences.technical_sub_weights IS 'Technical component sub-weights: rsi_14, trend, macd (must sum to 100)';
COMMENT ON COLUMN user_preferences.fundamental_sub_weights IS 'Fundamental component sub-weights: valuation, growth, health, sentiment (must sum to 100)';
