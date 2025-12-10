-- Migration: 105_corporate_actions.sql
-- Description: Create corporate_actions table for buybacks, dividends, splits
-- Feature: FEAT-175 Share Buybacks

CREATE TABLE IF NOT EXISTS corporate_actions (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL REFERENCES symbols(symbol) ON DELETE CASCADE,
    action_type VARCHAR(50) NOT NULL,  -- 'buyback', 'dividend', 'split'
    action_date DATE NOT NULL,

    -- Buyback-specific fields
    repurchase_amount DECIMAL(20, 2),  -- Total $ repurchased
    shares_repurchased BIGINT,         -- Number of shares

    -- Dividend-specific fields
    dividend_amount DECIMAL(10, 4),
    dividend_yield DECIMAL(6, 4),
    ex_dividend_date DATE,

    -- Split-specific fields
    split_ratio VARCHAR(10),  -- e.g., "4:1"

    -- Metadata
    source VARCHAR(50) NOT NULL DEFAULT 'yfinance',
    raw_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(symbol, action_type, action_date)
);

-- Index for common queries
CREATE INDEX IF NOT EXISTS idx_corporate_actions_symbol ON corporate_actions(symbol);
CREATE INDEX IF NOT EXISTS idx_corporate_actions_type_date ON corporate_actions(action_type, action_date DESC);
CREATE INDEX IF NOT EXISTS idx_corporate_actions_date ON corporate_actions(action_date DESC);

-- Trigger for updated_at
CREATE OR REPLACE FUNCTION update_corporate_actions_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS corporate_actions_updated_at ON corporate_actions;
CREATE TRIGGER corporate_actions_updated_at
    BEFORE UPDATE ON corporate_actions
    FOR EACH ROW
    EXECUTE FUNCTION update_corporate_actions_timestamp();

-- Comment
COMMENT ON TABLE corporate_actions IS 'Corporate actions: buybacks, dividends, splits. FEAT-175';
