-- Migration 118: Create market_events table for macro event tracking
-- Date: 2025-12-15
-- Description: Track market-wide events (FOMC, CPI, NFP, etc.) for sentiment chart overlays

-- Create enum type for event types
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'market_event_type') THEN
        CREATE TYPE market_event_type AS ENUM (
            'fomc_decision',
            'cpi_release',
            'nfp_release',
            'fed_speech',
            'pce_release',
            'gdp_release'
        );
    END IF;
END$$;

-- Create market_events table
CREATE TABLE IF NOT EXISTS market_events (
    id SERIAL PRIMARY KEY,
    event_type market_event_type NOT NULL,
    event_date DATE NOT NULL,
    event_time TIME,  -- NULL if time not specified (e.g., all-day events)
    title VARCHAR(255) NOT NULL,
    description TEXT,
    -- Economic data values
    expected_value NUMERIC(12, 4),  -- Consensus estimate
    actual_value NUMERIC(12, 4),    -- Released actual value
    prior_value NUMERIC(12, 4),     -- Previous period value
    surprise_pct NUMERIC(8, 4),     -- (actual - expected) / expected * 100
    -- Impact assessment
    impact_score SMALLINT CHECK (impact_score >= -5 AND impact_score <= 5),
    -- Market reaction (SPY)
    spy_change_1h NUMERIC(8, 4),    -- SPY % change in first hour after event
    spy_change_1d NUMERIC(8, 4),    -- SPY % change end of day
    -- Metadata
    source VARCHAR(50) DEFAULT 'manual',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    -- Unique constraint to prevent duplicate events
    CONSTRAINT unique_event_date_type UNIQUE (event_type, event_date)
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_market_events_date ON market_events (event_date DESC);
CREATE INDEX IF NOT EXISTS idx_market_events_type ON market_events (event_type);
-- Note: Partial index with CURRENT_DATE not allowed (non-immutable function)

-- Add to table_registry
INSERT INTO table_registry (table_name, table_type, description)
VALUES ('market_events', 'data', 'Market-wide macro events (FOMC, CPI, NFP) for sentiment chart overlays')
ON CONFLICT (table_name) DO UPDATE SET
    table_type = EXCLUDED.table_type,
    description = EXCLUDED.description;

-- Create trigger for updated_at
CREATE OR REPLACE FUNCTION update_market_events_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS market_events_updated_at ON market_events;
CREATE TRIGGER market_events_updated_at
    BEFORE UPDATE ON market_events
    FOR EACH ROW
    EXECUTE FUNCTION update_market_events_updated_at();

-- Comments for documentation
COMMENT ON TABLE market_events IS 'Market-wide macro events for sentiment chart overlays';
COMMENT ON COLUMN market_events.event_type IS 'Event category: fomc_decision, cpi_release, nfp_release, fed_speech, pce_release, gdp_release';
COMMENT ON COLUMN market_events.impact_score IS 'Market impact from -5 (very bearish) to +5 (very bullish)';
COMMENT ON COLUMN market_events.surprise_pct IS 'Percentage surprise: (actual - expected) / expected * 100';
