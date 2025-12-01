-- Migration 049: Portfolio Covariance Matrix
--
-- Creates infrastructure for proper portfolio risk calculation using
-- covariance matrix (GAP-020). Replaces incorrect weighted-average approach.
--
-- Correct formula: σ_portfolio = √(w' Σ w)
-- where w = weight vector, Σ = covariance matrix

-- Table to store pairwise covariance/correlation between assets
CREATE TABLE IF NOT EXISTS portfolio_covariance (
    ticker1 TEXT NOT NULL,
    ticker2 TEXT NOT NULL,
    covariance DOUBLE PRECISION NOT NULL,
    correlation DOUBLE PRECISION NOT NULL,
    -- Store individual volatilities for convenience
    volatility1 DOUBLE PRECISION NOT NULL,
    volatility2 DOUBLE PRECISION NOT NULL,
    -- Number of observations used in calculation
    observation_count INTEGER NOT NULL,
    -- Calculation metadata
    lookback_days INTEGER NOT NULL DEFAULT 252,
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (ticker1, ticker2)
);

-- Index for fast lookups of all pairs involving a specific ticker
CREATE INDEX IF NOT EXISTS idx_portfolio_covariance_ticker1
ON portfolio_covariance(ticker1);

CREATE INDEX IF NOT EXISTS idx_portfolio_covariance_ticker2
ON portfolio_covariance(ticker2);

-- Index for freshness checks
CREATE INDEX IF NOT EXISTS idx_portfolio_covariance_calculated_at
ON portfolio_covariance(calculated_at);

-- Table to cache portfolio-level volatility calculations
-- (since matrix calculation is expensive)
CREATE TABLE IF NOT EXISTS portfolio_volatility_cache (
    portfolio_id TEXT NOT NULL,  -- e.g., account_id or 'watchlist'
    -- Hash of position weights for cache invalidation
    weight_hash TEXT NOT NULL,
    -- Calculated values
    portfolio_volatility DOUBLE PRECISION NOT NULL,
    weighted_avg_volatility DOUBLE PRECISION NOT NULL,  -- For comparison
    diversification_benefit DOUBLE PRECISION NOT NULL,  -- 1 - (portfolio_vol / weighted_avg)
    -- Metadata
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (portfolio_id, weight_hash)
);

-- Index for cache cleanup
CREATE INDEX IF NOT EXISTS idx_portfolio_volatility_cache_calculated_at
ON portfolio_volatility_cache(calculated_at);

-- Comment explaining the table purpose
COMMENT ON TABLE portfolio_covariance IS
'Pairwise asset covariance matrix for correct portfolio risk calculation (GAP-020).
Uses 252-day lookback by default. Calculated from day_bars returns.';

COMMENT ON COLUMN portfolio_volatility_cache.diversification_benefit IS
'Shows how much lower portfolio vol is vs naive weighted average.
0.35 means 35% lower risk from diversification.';
