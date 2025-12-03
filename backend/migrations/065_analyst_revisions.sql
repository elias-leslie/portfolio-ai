-- Migration 065: Create analyst_revisions table (GAP-005)
-- Tracks EPS/Revenue estimate changes over time for momentum signals

CREATE TABLE IF NOT EXISTS analyst_revisions (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL REFERENCES symbols(symbol),
    metric VARCHAR(50) NOT NULL,  -- 'eps_current_qtr', 'eps_next_qtr', 'revenue_current_qtr', etc.
    period VARCHAR(20) NOT NULL,  -- 'Q1 2025', 'FY 2025', etc.
    current_estimate DECIMAL(15, 4),
    estimate_7d_ago DECIMAL(15, 4),
    estimate_30d_ago DECIMAL(15, 4),
    estimate_90d_ago DECIMAL(15, 4),
    revision_direction VARCHAR(10),  -- 'up', 'down', 'unchanged'
    revision_magnitude DECIMAL(8, 4),  -- percentage change (7d)
    num_analysts INTEGER,
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(symbol, metric, period)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_analyst_revisions_symbol ON analyst_revisions(symbol);
CREATE INDEX IF NOT EXISTS idx_analyst_revisions_fetched ON analyst_revisions(fetched_at);
CREATE INDEX IF NOT EXISTS idx_analyst_revisions_direction ON analyst_revisions(revision_direction);

COMMENT ON TABLE analyst_revisions IS 'Analyst estimate revisions for earnings momentum signals (GAP-005)';
