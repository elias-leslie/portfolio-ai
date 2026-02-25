-- Migration 068: Add tables for fundamental data gaps
-- GAP-004: Cash flow metrics
-- GAP-006: Insider trading
-- GAP-007: Institutional ownership
-- GAP-011: Short interest
-- GAP-034/035/036: Macro indicators (FRED)

-- ============================================
-- Cash Flow Metrics (GAP-004)
-- ============================================
CREATE TABLE IF NOT EXISTS cash_flow_metrics (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    as_of_date DATE NOT NULL,
    -- Operating cash flow
    operating_cash_flow DOUBLE PRECISION,
    free_cash_flow DOUBLE PRECISION,
    capital_expenditure DOUBLE PRECISION,
    -- Cash flow ratios
    fcf_yield DOUBLE PRECISION,  -- FCF / Market Cap
    cash_flow_margin DOUBLE PRECISION,  -- OCF / Revenue
    fcf_per_share DOUBLE PRECISION,
    -- Quality metrics
    cash_conversion_ratio DOUBLE PRECISION,  -- OCF / Net Income
    -- Metadata
    source VARCHAR(50) DEFAULT 'yfinance',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(symbol, as_of_date)
);

CREATE INDEX IF NOT EXISTS idx_cash_flow_metrics_symbol ON cash_flow_metrics(symbol);
CREATE INDEX IF NOT EXISTS idx_cash_flow_metrics_date ON cash_flow_metrics(as_of_date);

-- ============================================
-- Insider Transactions (GAP-006)
-- ============================================
CREATE TABLE IF NOT EXISTS insider_transactions (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    insider_name VARCHAR(255),
    insider_title VARCHAR(255),
    transaction_type VARCHAR(50),  -- 'Buy', 'Sell', 'Option Exercise'
    transaction_date DATE NOT NULL,
    shares DOUBLE PRECISION,
    value DOUBLE PRECISION,
    shares_owned_after DOUBLE PRECISION,
    -- Derived metrics
    insider_ownership_pct DOUBLE PRECISION,
    -- Metadata
    source VARCHAR(50) DEFAULT 'yfinance',
    raw_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(symbol, insider_name, transaction_date, transaction_type, shares)
);

CREATE INDEX IF NOT EXISTS idx_insider_transactions_symbol ON insider_transactions(symbol);
CREATE INDEX IF NOT EXISTS idx_insider_transactions_date ON insider_transactions(transaction_date DESC);
CREATE INDEX IF NOT EXISTS idx_insider_transactions_type ON insider_transactions(transaction_type);

-- ============================================
-- Institutional Holdings (GAP-007)
-- ============================================
CREATE TABLE IF NOT EXISTS institutional_holdings (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    holder_name VARCHAR(255) NOT NULL,
    shares DOUBLE PRECISION,
    value DOUBLE PRECISION,
    pct_held DOUBLE PRECISION,
    pct_change DOUBLE PRECISION,  -- Change from prior period
    report_date DATE,
    -- Metadata
    source VARCHAR(50) DEFAULT 'yfinance',
    raw_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(symbol, holder_name, report_date)
);

CREATE INDEX IF NOT EXISTS idx_institutional_holdings_symbol ON institutional_holdings(symbol);
CREATE INDEX IF NOT EXISTS idx_institutional_holdings_holder ON institutional_holdings(holder_name);

-- Aggregate institutional ownership per symbol
CREATE TABLE IF NOT EXISTS institutional_ownership_summary (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    as_of_date DATE NOT NULL,
    total_institutions INTEGER,
    total_shares_held DOUBLE PRECISION,
    pct_held_institutions DOUBLE PRECISION,
    pct_held_insiders DOUBLE PRECISION,
    -- Quarterly changes
    institutions_increased INTEGER,
    institutions_decreased INTEGER,
    institutions_new INTEGER,
    institutions_soldout INTEGER,
    -- Metadata
    source VARCHAR(50) DEFAULT 'yfinance',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(symbol, as_of_date)
);

CREATE INDEX IF NOT EXISTS idx_institutional_summary_symbol ON institutional_ownership_summary(symbol);

-- ============================================
-- Short Interest (GAP-011)
-- ============================================
CREATE TABLE IF NOT EXISTS short_interest (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    as_of_date DATE NOT NULL,
    -- Core metrics
    short_shares DOUBLE PRECISION,
    short_ratio DOUBLE PRECISION,  -- Days to cover
    short_percent_of_float DOUBLE PRECISION,
    short_percent_of_outstanding DOUBLE PRECISION,
    -- Changes
    short_prior_month DOUBLE PRECISION,
    short_pct_change DOUBLE PRECISION,
    -- Metadata
    source VARCHAR(50) DEFAULT 'yfinance',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(symbol, as_of_date)
);

CREATE INDEX IF NOT EXISTS idx_short_interest_symbol ON short_interest(symbol);
CREATE INDEX IF NOT EXISTS idx_short_interest_date ON short_interest(as_of_date DESC);
CREATE INDEX IF NOT EXISTS idx_short_interest_ratio ON short_interest(short_ratio) WHERE short_ratio IS NOT NULL;

-- ============================================
-- Macro Indicators (GAP-034/035/036)
-- ============================================
CREATE TABLE IF NOT EXISTS macro_indicators (
    id BIGSERIAL PRIMARY KEY,
    indicator_name VARCHAR(50) NOT NULL,  -- 'VIX', 'TNX', 'FEDFUNDS', 'CPI', etc.
    series_id VARCHAR(50),  -- FRED series ID
    observation_date DATE NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    -- Metadata
    source VARCHAR(50) DEFAULT 'fred',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(indicator_name, observation_date)
);

CREATE INDEX IF NOT EXISTS idx_macro_indicators_name ON macro_indicators(indicator_name);
CREATE INDEX IF NOT EXISTS idx_macro_indicators_date ON macro_indicators(observation_date DESC);

-- Yield curve specific table for GAP-034
CREATE TABLE IF NOT EXISTS yield_curve (
    id BIGSERIAL PRIMARY KEY,
    observation_date DATE NOT NULL,
    -- Treasury yields
    yield_3m DOUBLE PRECISION,  -- 3-month T-bill
    yield_2y DOUBLE PRECISION,  -- 2-year Treasury
    yield_5y DOUBLE PRECISION,  -- 5-year Treasury
    yield_10y DOUBLE PRECISION, -- 10-year Treasury
    yield_30y DOUBLE PRECISION, -- 30-year Treasury
    -- Spread calculations
    spread_10y_2y DOUBLE PRECISION,  -- 10Y - 2Y (inversion indicator)
    spread_10y_3m DOUBLE PRECISION,  -- 10Y - 3M
    -- Curve shape
    is_inverted BOOLEAN GENERATED ALWAYS AS (spread_10y_2y < 0) STORED,
    -- Metadata
    source VARCHAR(50) DEFAULT 'fred',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(observation_date)
);

CREATE INDEX IF NOT EXISTS idx_yield_curve_date ON yield_curve(observation_date DESC);
CREATE INDEX IF NOT EXISTS idx_yield_curve_inverted ON yield_curve(is_inverted) WHERE is_inverted = TRUE;

-- ============================================
-- Update reference_cache with additional fields
-- ============================================
ALTER TABLE reference_cache
    ADD COLUMN IF NOT EXISTS shares_short DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS short_ratio DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS short_percent_of_float DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS held_percent_institutions DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS held_percent_insiders DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS free_cash_flow DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS operating_cash_flow DOUBLE PRECISION;
