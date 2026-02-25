-- Migration 051: Earnings Surprises (GAP-003)
-- Stores earnings results with EPS estimate, actual, and surprise percentage

CREATE TABLE IF NOT EXISTS earnings_surprises (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    earnings_date DATE NOT NULL,
    fiscal_quarter VARCHAR(10),  -- e.g., 'Q3 2024'
    eps_estimate DECIMAL(10, 4),  -- Analyst consensus estimate
    eps_actual DECIMAL(10, 4),    -- Reported EPS
    surprise_pct DECIMAL(10, 4),  -- (actual - estimate) / |estimate| * 100
    surprise_direction VARCHAR(10),  -- 'beat', 'miss', 'inline'
    revenue_estimate DECIMAL(20, 2),  -- Revenue estimate (optional)
    revenue_actual DECIMAL(20, 2),    -- Reported revenue (optional)
    data_source VARCHAR(50) NOT NULL DEFAULT 'finnhub',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(ticker, earnings_date)
);

-- Index for ticker lookup (most common query pattern)
CREATE INDEX IF NOT EXISTS idx_earnings_surprises_ticker ON earnings_surprises(ticker);

-- Index for date-based queries (recent surprises)
CREATE INDEX IF NOT EXISTS idx_earnings_surprises_date ON earnings_surprises(earnings_date DESC);

-- Index for finding recent surprises per ticker
CREATE INDEX IF NOT EXISTS idx_earnings_surprises_ticker_date ON earnings_surprises(ticker, earnings_date DESC);

COMMENT ON TABLE earnings_surprises IS 'Stores historical earnings results with surprise metrics (GAP-003)';
COMMENT ON COLUMN earnings_surprises.surprise_pct IS 'Percentage surprise = (actual - estimate) / |estimate| * 100';
COMMENT ON COLUMN earnings_surprises.surprise_direction IS 'beat = positive surprise, miss = negative surprise, inline = within 2%';
