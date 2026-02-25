-- Migration 033: Options Market Metrics Table
-- Purpose: Store aggregated daily metrics from CBOE Most Active Options
-- Data Strategy: Aggregate metrics (not raw contracts) for 90-day trend analysis

-- Create options_market_metrics table
CREATE TABLE IF NOT EXISTS options_market_metrics (
    as_of_date DATE PRIMARY KEY,

    -- Sentiment: % of top 25 most active options that are calls
    -- Values: 0-100 (higher = more calls = bullish positioning)
    most_active_call_pct DECIMAL(5,2) NOT NULL CHECK (most_active_call_pct >= 0 AND most_active_call_pct <= 100),

    -- Time horizon: % of top 25 expiring within 30 days
    -- Values: 0-100 (higher = more near-term = event-driven positioning)
    near_term_pct DECIMAL(5,2) NOT NULL CHECK (near_term_pct >= 0 AND near_term_pct <= 100),

    -- Concentration: % of total volume in top 5 contracts vs all top 25
    -- Values: 0-100 (higher = more concentrated = focused positioning)
    concentration_pct DECIMAL(5,2) NOT NULL CHECK (concentration_pct >= 0 AND concentration_pct <= 100),

    -- Sector distribution of top 25 most active options
    -- Format: {"Technology": 45.2, "Financials": 25.8, "Healthcare": 15.3, ...}
    sector_weights JSONB NOT NULL,

    -- Original fetch timestamp from CBOE
    source_timestamp TIMESTAMPTZ NOT NULL,

    -- Record creation timestamp
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for efficient date-based queries (most recent first)
CREATE INDEX idx_options_metrics_date ON options_market_metrics(as_of_date DESC);

-- Index for timestamp-based queries
CREATE INDEX idx_options_metrics_timestamp ON options_market_metrics(source_timestamp DESC);

-- Add to table_registry for freshness monitoring
INSERT INTO table_registry (table_name, table_type, description)
VALUES (
    'options_market_metrics',
    'market_data',
    'CBOE Most Active Options aggregated metrics (refreshes daily at 21:15 UTC)'
)
ON CONFLICT (table_name) DO NOTHING;

-- Add comment for documentation
COMMENT ON TABLE options_market_metrics IS
'Aggregated daily metrics from CBOE Most Active Options.
Tracks sentiment (call/put mix), time horizon (near vs far-term),
concentration (focused vs dispersed), and sector distribution.
Data source: https://www.cboe.com/us/options/market_statistics/most_active/';

COMMENT ON COLUMN options_market_metrics.most_active_call_pct IS
'Percentage of top 25 most active options that are calls (0-100).
Higher values indicate bullish positioning.';

COMMENT ON COLUMN options_market_metrics.near_term_pct IS
'Percentage of top 25 options expiring within 30 days (0-100).
Higher values suggest event-driven or short-term positioning.';

COMMENT ON COLUMN options_market_metrics.concentration_pct IS
'Percentage of volume concentrated in top 5 vs all top 25 contracts (0-100).
Higher values indicate focused institutional positioning.';

COMMENT ON COLUMN options_market_metrics.sector_weights IS
'Distribution of top 25 options across sectors as JSON object.
Example: {"Technology": 45.2, "Financials": 25.8}';
