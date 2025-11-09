-- Migration 020: Add fundamental_cache table
-- Created: 2025-11-08
-- Description: Create fundamental_cache table to store cached company fundamental data

-- Create fundamental_cache table
CREATE TABLE IF NOT EXISTS fundamental_cache (
    symbol TEXT NOT NULL,

    -- Raw fundamental data
    profit_margin DOUBLE PRECISION,
    revenue_growth DOUBLE PRECISION,
    debt_to_equity DOUBLE PRECISION,
    recommendation_key TEXT,
    recommendation_mean DOUBLE PRECISION,
    target_mean_price DOUBLE PRECISION,

    -- Calculated scores (0-100)
    fundamental_score DOUBLE PRECISION,
    valuation_score DOUBLE PRECISION,
    growth_score DOUBLE PRECISION,
    health_score DOUBLE PRECISION,
    sentiment_score DOUBLE PRECISION,

    -- Cache metadata
    cached_at TIMESTAMP WITH TIME ZONE NOT NULL,
    source TEXT NOT NULL,
    error TEXT,

    PRIMARY KEY (symbol, cached_at)
);

-- Create index for efficient lookups (latest cache entry per symbol)
CREATE INDEX IF NOT EXISTS idx_fundamental_cache_symbol
ON fundamental_cache (symbol, cached_at DESC);

-- Add comment
COMMENT ON TABLE fundamental_cache IS 'Cached company fundamental data with 4-pillar scores (valuation, growth, health, sentiment)';
