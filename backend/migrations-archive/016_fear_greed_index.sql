-- Migration 016: Fear & Greed Index Tables
-- Created: 2025-11-07
-- Description: Create tables for Fear & Greed Index data storage (5-signal version)
--
-- This migration creates 3 tables:
-- 1. fear_greed_inputs: Raw signal data (VIX, SPY momentum, RSI, Put/Call, HY spread)
-- 2. fear_greed_components: Percentile-ranked components (0-100 scale)
-- 3. fear_greed_daily: Final Fear & Greed score with regime label
--
-- Design decisions:
-- - 5 signals: VIX, Momentum (SPY vs SMA_200), RSI, Put/Call Ratio, Credit Spreads
-- - 252-day rolling window for percentile calculations (1 trading year)
-- - Daily computation at 03:30 UTC (after market close + data availability)
-- - Market breadth signal deferred to future version (data coverage insufficient)

BEGIN;

-- Table 1: Raw input data
CREATE TABLE IF NOT EXISTS fear_greed_inputs (
    as_of_date DATE PRIMARY KEY,
    -- Core signals (all required for 5-signal index)
    vix_close DOUBLE PRECISION,                -- CBOE VIX (volatility index)
    spy_close DOUBLE PRECISION,                -- SPY closing price
    spy_sma_200 DOUBLE PRECISION,              -- SPY 200-day moving average
    rsi_14 DOUBLE PRECISION,                   -- SPY 14-period RSI
    put_call_ratio DOUBLE PRECISION,           -- CBOE equity put/call ratio
    hy_spread DOUBLE PRECISION,                -- High-yield OAS (basis points)

    -- Optional future signal (NULL for 5-signal version)
    breadth_pct DOUBLE PRECISION,              -- % of S&P 500 > 50-day MA (future)

    -- Metadata
    source_map JSONB DEFAULT '{}'::jsonb,      -- Track data source for each signal
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for efficient date-based queries
CREATE INDEX IF NOT EXISTS idx_fng_inputs_date ON fear_greed_inputs(as_of_date DESC);

-- Comment on columns
COMMENT ON COLUMN fear_greed_inputs.vix_close IS 'CBOE VIX closing value - fear gauge (higher = more fear)';
COMMENT ON COLUMN fear_greed_inputs.spy_close IS 'SPY ETF closing price for momentum calculation';
COMMENT ON COLUMN fear_greed_inputs.spy_sma_200 IS 'SPY 200-day simple moving average - trend indicator';
COMMENT ON COLUMN fear_greed_inputs.rsi_14 IS 'SPY 14-period RSI - overbought/oversold indicator';
COMMENT ON COLUMN fear_greed_inputs.put_call_ratio IS 'CBOE equity put/call ratio - options sentiment (higher = more bearish)';
COMMENT ON COLUMN fear_greed_inputs.hy_spread IS 'High-yield bond OAS spread in basis points - credit risk indicator (higher = more fear)';
COMMENT ON COLUMN fear_greed_inputs.breadth_pct IS 'Percentage of S&P 500 stocks above 50-day MA - market breadth (future feature)';
COMMENT ON COLUMN fear_greed_inputs.source_map IS 'JSON map of signal names to data sources (e.g., {"vix": "FRED", "put_call": "CBOE"})';

-- Table 2: Percentile-ranked components
CREATE TABLE IF NOT EXISTS fear_greed_components (
    as_of_date DATE PRIMARY KEY,
    -- Component percentiles (0-100 scale, inverted where needed)
    vix_pct SMALLINT CHECK (vix_pct >= 0 AND vix_pct <= 100),               -- VIX percentile (inverted: low VIX = greed)
    momentum_pct SMALLINT CHECK (momentum_pct >= 0 AND momentum_pct <= 100), -- Momentum percentile (high = greed)
    rsi_pct SMALLINT CHECK (rsi_pct >= 0 AND rsi_pct <= 100),               -- RSI percentile (high = greed)
    pcr_pct SMALLINT CHECK (pcr_pct >= 0 AND pcr_pct <= 100),               -- Put/Call percentile (inverted: low P/C = greed)
    credit_pct SMALLINT CHECK (credit_pct >= 0 AND credit_pct <= 100),      -- Credit spread percentile (inverted: low spread = greed)

    -- Optional future component
    breadth_pct SMALLINT CHECK (breadth_pct IS NULL OR (breadth_pct >= 0 AND breadth_pct <= 100)),

    -- Calculation metadata
    window_days INT DEFAULT 252,                                             -- Lookback window for percentile calculation
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Comment on percentile methodology
COMMENT ON TABLE fear_greed_components IS 'Percentile-ranked Fear & Greed components (0=Extreme Fear, 100=Extreme Greed). Uses 252-day rolling window for historical context.';
COMMENT ON COLUMN fear_greed_components.vix_pct IS 'VIX percentile - INVERTED (low VIX = low fear = greed)';
COMMENT ON COLUMN fear_greed_components.momentum_pct IS 'SPY momentum vs SMA_200 - price above MA = greed';
COMMENT ON COLUMN fear_greed_components.rsi_pct IS 'RSI percentile - high RSI = overbought = greed';
COMMENT ON COLUMN fear_greed_components.pcr_pct IS 'Put/Call ratio percentile - INVERTED (low P/C = bullish = greed)';
COMMENT ON COLUMN fear_greed_components.credit_pct IS 'Credit spread percentile - INVERTED (low spread = low risk = greed)';
COMMENT ON COLUMN fear_greed_components.window_days IS 'Number of trading days used for percentile calculation (default 252 = 1 year)';

-- Table 3: Final Fear & Greed score
CREATE TABLE IF NOT EXISTS fear_greed_daily (
    as_of_date DATE PRIMARY KEY,
    score DOUBLE PRECISION NOT NULL CHECK (score >= 0 AND score <= 100),
    label TEXT NOT NULL CHECK (label IN ('Extreme Fear', 'Fear', 'Neutral', 'Greed', 'Extreme Greed')),
    previous_score DOUBLE PRECISION,           -- Yesterday's score for trend calculation
    score_change DOUBLE PRECISION,             -- Daily change (score - previous_score)
    signal_count SMALLINT DEFAULT 5,           -- Number of signals used (5 for current version, 6 if breadth added)
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for efficient date-based queries
CREATE INDEX IF NOT EXISTS idx_fng_daily_date ON fear_greed_daily(as_of_date DESC);

-- Comment on score ranges
COMMENT ON TABLE fear_greed_daily IS 'Final Fear & Greed Index scores with regime labels. Score ranges: 0-25=Extreme Fear, 25-45=Fear, 45-55=Neutral, 55-75=Greed, 75-100=Extreme Greed';
COMMENT ON COLUMN fear_greed_daily.score IS 'Composite Fear & Greed score (0-100, equal-weighted average of components)';
COMMENT ON COLUMN fear_greed_daily.label IS 'Regime label based on score thresholds';
COMMENT ON COLUMN fear_greed_daily.previous_score IS 'Previous trading day score for trend analysis';
COMMENT ON COLUMN fear_greed_daily.score_change IS 'Daily change in score (positive = trending toward greed)';
COMMENT ON COLUMN fear_greed_daily.signal_count IS 'Number of signals included in calculation (5 for current version)';

COMMIT;
