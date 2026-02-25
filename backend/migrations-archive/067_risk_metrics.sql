-- Migration 067: Add portfolio risk metrics table
-- GAP-027: VaR/CVaR (Value at Risk, Conditional VaR)
-- GAP-022: Long-window beta estimation

-- Create table for storing risk metrics per symbol
CREATE TABLE IF NOT EXISTS symbol_risk_metrics (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    as_of_date DATE NOT NULL,

    -- VaR/CVaR metrics (GAP-027)
    var_95 DECIMAL(10,6),        -- 95% Value at Risk (daily)
    var_99 DECIMAL(10,6),        -- 99% Value at Risk (daily)
    cvar_95 DECIMAL(10,6),       -- 95% Conditional VaR (Expected Shortfall)
    cvar_99 DECIMAL(10,6),       -- 99% Conditional VaR

    -- Extended beta metrics (GAP-022)
    beta_90d DECIMAL(8,4),       -- 90-day rolling beta
    beta_1y DECIMAL(8,4),        -- 1-year beta
    beta_2y DECIMAL(8,4),        -- 2-year beta
    r_squared_1y DECIMAL(6,4),   -- R-squared for 1-year regression

    -- Metadata
    observations INTEGER,        -- Number of observations used
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(symbol, as_of_date)
);

-- Create indexes for querying
CREATE INDEX IF NOT EXISTS idx_symbol_risk_metrics_symbol ON symbol_risk_metrics(symbol);
CREATE INDEX IF NOT EXISTS idx_symbol_risk_metrics_date ON symbol_risk_metrics(as_of_date);

-- Add comments
COMMENT ON TABLE symbol_risk_metrics IS 'Daily risk metrics per symbol: VaR, CVaR, multi-window betas';
COMMENT ON COLUMN symbol_risk_metrics.var_95 IS '95% daily VaR - max expected loss 95% of the time';
COMMENT ON COLUMN symbol_risk_metrics.cvar_95 IS 'Conditional VaR - average loss beyond VaR threshold';
COMMENT ON COLUMN symbol_risk_metrics.beta_1y IS '1-year beta vs SPY (less noisy than 90-day)';
