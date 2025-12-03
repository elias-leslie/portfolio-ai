-- Migration 058: Create centralized symbols table
-- This provides a single source of truth for all symbol metadata
-- and enables future FK constraints for referential integrity.

-- Create the symbols table
CREATE TABLE IF NOT EXISTS symbols (
    symbol VARCHAR(20) PRIMARY KEY,
    company_name TEXT,
    sector VARCHAR(100),
    industry VARCHAR(150),
    exchange VARCHAR(20),
    security_type VARCHAR(20) DEFAULT 'equity',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_symbols_sector ON symbols(sector);
CREATE INDEX IF NOT EXISTS idx_symbols_exchange ON symbols(exchange);
CREATE INDEX IF NOT EXISTS idx_symbols_security_type ON symbols(security_type);
CREATE INDEX IF NOT EXISTS idx_symbols_is_active ON symbols(is_active);

-- Populate from all existing data sources (DISTINCT across all tables)
-- Using INSERT ... ON CONFLICT to handle duplicates gracefully
INSERT INTO symbols (symbol, security_type, created_at)
SELECT DISTINCT ticker,
    CASE
        WHEN ticker LIKE '^%' THEN 'index'
        WHEN ticker LIKE 'XL%' THEN 'etf'
        WHEN ticker = 'SPY' OR ticker = 'QQQ' OR ticker = 'IWM' THEN 'etf'
        WHEN ticker LIKE 'DX-Y%' THEN 'currency'
        ELSE 'equity'
    END as security_type,
    NOW()
FROM day_bars
WHERE ticker IS NOT NULL
ON CONFLICT (symbol) DO NOTHING;

-- Add symbols from watchlist_items
INSERT INTO symbols (symbol, security_type, created_at)
SELECT DISTINCT symbol,
    CASE
        WHEN symbol LIKE '^%' THEN 'index'
        WHEN symbol LIKE 'XL%' THEN 'etf'
        WHEN symbol = 'SPY' OR symbol = 'QQQ' OR symbol = 'IWM' THEN 'etf'
        WHEN symbol LIKE 'DX-Y%' THEN 'currency'
        ELSE 'equity'
    END as security_type,
    NOW()
FROM watchlist_items
WHERE symbol IS NOT NULL
ON CONFLICT (symbol) DO NOTHING;

-- Add symbols from news_cache
INSERT INTO symbols (symbol, security_type, created_at)
SELECT DISTINCT ticker,
    CASE
        WHEN ticker LIKE '^%' THEN 'index'
        WHEN ticker LIKE 'XL%' THEN 'etf'
        WHEN ticker = 'SPY' OR ticker = 'QQQ' OR ticker = 'IWM' THEN 'etf'
        WHEN ticker LIKE 'DX-Y%' THEN 'currency'
        ELSE 'equity'
    END as security_type,
    NOW()
FROM news_cache
WHERE ticker IS NOT NULL
ON CONFLICT (symbol) DO NOTHING;

-- Add symbols from portfolio_positions
INSERT INTO symbols (symbol, security_type, created_at)
SELECT DISTINCT symbol,
    CASE
        WHEN symbol LIKE '^%' THEN 'index'
        WHEN symbol LIKE 'XL%' THEN 'etf'
        WHEN symbol = 'SPY' OR symbol = 'QQQ' OR symbol = 'IWM' THEN 'etf'
        WHEN symbol LIKE 'DX-Y%' THEN 'currency'
        ELSE 'equity'
    END as security_type,
    NOW()
FROM portfolio_positions
WHERE symbol IS NOT NULL
ON CONFLICT (symbol) DO NOTHING;

-- Add symbols from backtest_runs
INSERT INTO symbols (symbol, security_type, created_at)
SELECT DISTINCT symbol,
    CASE
        WHEN symbol LIKE '^%' THEN 'index'
        WHEN symbol LIKE 'XL%' THEN 'etf'
        WHEN symbol = 'SPY' OR symbol = 'QQQ' OR symbol = 'IWM' THEN 'etf'
        WHEN symbol LIKE 'DX-Y%' THEN 'currency'
        ELSE 'equity'
    END as security_type,
    NOW()
FROM backtest_runs
WHERE symbol IS NOT NULL
ON CONFLICT (symbol) DO NOTHING;

-- Add symbols from paper_trade_transactions (using ticker column)
INSERT INTO symbols (symbol, security_type, created_at)
SELECT DISTINCT ticker,
    CASE
        WHEN ticker LIKE '^%' THEN 'index'
        WHEN ticker LIKE 'XL%' THEN 'etf'
        WHEN ticker = 'SPY' OR ticker = 'QQQ' OR ticker = 'IWM' THEN 'etf'
        WHEN ticker LIKE 'DX-Y%' THEN 'currency'
        ELSE 'equity'
    END as security_type,
    NOW()
FROM paper_trade_transactions
WHERE ticker IS NOT NULL
ON CONFLICT (symbol) DO NOTHING;

-- Add trigger to auto-update updated_at
CREATE OR REPLACE FUNCTION update_symbols_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS symbols_updated_at ON symbols;
CREATE TRIGGER symbols_updated_at
    BEFORE UPDATE ON symbols
    FOR EACH ROW
    EXECUTE FUNCTION update_symbols_updated_at();

-- Log the migration results
DO $$
DECLARE
    symbol_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO symbol_count FROM symbols;
    RAISE NOTICE 'Migration 058: Created symbols table with % symbols', symbol_count;
END $$;
