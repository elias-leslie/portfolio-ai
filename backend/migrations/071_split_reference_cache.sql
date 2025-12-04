-- Migration 071: Split reference_cache into normalized tables
-- Created: 2025-12-04
-- Purpose: Normalize reference_cache data into dedicated tables

-- ============================================================================
-- 1. Valuation Metrics Table
-- ============================================================================
CREATE TABLE IF NOT EXISTS valuation_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol VARCHAR(20) NOT NULL,
    as_of_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    pe_ratio_trailing NUMERIC(12, 2),
    pe_ratio_forward NUMERIC(12, 2),
    ps_ratio NUMERIC(12, 2),
    pb_ratio NUMERIC(12, 2),
    peg_ratio NUMERIC(12, 2),
    dividend_yield NUMERIC(8, 4),
    payout_ratio NUMERIC(8, 4),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_valuation_metrics_symbol
        FOREIGN KEY (symbol) REFERENCES symbols(symbol) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_valuation_metrics_symbol_date
    ON valuation_metrics(symbol, as_of_date);

CREATE INDEX IF NOT EXISTS idx_valuation_metrics_symbol
    ON valuation_metrics(symbol);

-- ============================================================================
-- 2. Financial Health Scores Table
-- ============================================================================
CREATE TABLE IF NOT EXISTS financial_health_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol VARCHAR(20) NOT NULL,
    as_of_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    f_score INTEGER CHECK (f_score >= 0 AND f_score <= 9),
    f_score_components JSONB,
    z_score NUMERIC(12, 4),
    z_score_zone VARCHAR(20),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_financial_health_scores_symbol
        FOREIGN KEY (symbol) REFERENCES symbols(symbol) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_financial_health_symbol_date
    ON financial_health_scores(symbol, as_of_date);

CREATE INDEX IF NOT EXISTS idx_financial_health_symbol
    ON financial_health_scores(symbol);

-- ============================================================================
-- 3. Short Interest Summary Table
-- ============================================================================
CREATE TABLE IF NOT EXISTS short_interest_summary (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol VARCHAR(20) NOT NULL,
    as_of_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    shares_short BIGINT,
    short_ratio NUMERIC(12, 4),
    short_percent_of_float NUMERIC(8, 4),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_short_interest_summary_symbol
        FOREIGN KEY (symbol) REFERENCES symbols(symbol) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_short_interest_symbol_date
    ON short_interest_summary(symbol, as_of_date);

CREATE INDEX IF NOT EXISTS idx_short_interest_symbol
    ON short_interest_summary(symbol);

-- ============================================================================
-- Comments
-- ============================================================================
COMMENT ON TABLE valuation_metrics IS 'Normalized valuation ratios from reference_cache';
COMMENT ON TABLE financial_health_scores IS 'Normalized financial health scores (F-score, Z-score)';
COMMENT ON TABLE short_interest_summary IS 'Normalized short interest data';

DO $$
BEGIN
    RAISE NOTICE 'Migration 071: Created 3 normalized tables';
END $$;
