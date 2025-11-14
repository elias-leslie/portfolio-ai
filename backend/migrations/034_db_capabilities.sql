-- Migration 034: Database Capabilities Table
-- Purpose: Track database table metadata for auto-discovery and monitoring
-- Part of: System Capabilities Registry (Task 0059, Phase 1)
-- Created: 2025-11-13
-- Related: tasks/tasks-0059-system-capabilities-registry.md

CREATE TABLE IF NOT EXISTS db_capabilities (
    id SERIAL PRIMARY KEY,
    table_name TEXT UNIQUE NOT NULL,
    category TEXT,  -- market_data, news, portfolio, analytics, infrastructure
    row_count INTEGER,
    total_columns INTEGER,
    columns JSONB,  -- Array of all column names
    columns_with_data JSONB,  -- Columns with non-NULL values (any row)
    columns_mostly_null JSONB,  -- Columns >80% NULL
    completeness_pct INTEGER,  -- (columns_with_data / total_columns) * 100
    date_range_start DATE,  -- MIN(created_at/updated_at/as_of_date)
    date_range_end DATE,    -- MAX(created_at/updated_at/as_of_date)
    expected_freshness TEXT,  -- From config: "daily", "hourly", "real-time", "on-demand"
    days_since_update INTEGER,  -- (TODAY - date_range_end)
    freshness_status TEXT,  -- "current", "acceptable", "stale", "critical"
    last_scanned_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

-- Indexes for query performance
CREATE INDEX IF NOT EXISTS idx_db_capabilities_category ON db_capabilities(category);
CREATE INDEX IF NOT EXISTS idx_db_capabilities_freshness_status ON db_capabilities(freshness_status);
CREATE INDEX IF NOT EXISTS idx_db_capabilities_completeness ON db_capabilities(completeness_pct);
CREATE INDEX IF NOT EXISTS idx_db_capabilities_scanned_at ON db_capabilities(last_scanned_at DESC);

-- Comments for documentation
COMMENT ON TABLE db_capabilities IS 'Registry of database tables with metadata for monitoring and auto-discovery';
COMMENT ON COLUMN db_capabilities.table_name IS 'Database table name (unique identifier)';
COMMENT ON COLUMN db_capabilities.category IS 'Business category: market_data, news, portfolio, analytics, infrastructure';
COMMENT ON COLUMN db_capabilities.row_count IS 'Total number of rows in table';
COMMENT ON COLUMN db_capabilities.columns IS 'JSON array of all column names';
COMMENT ON COLUMN db_capabilities.columns_with_data IS 'JSON array of columns that have non-NULL values in at least one row';
COMMENT ON COLUMN db_capabilities.columns_mostly_null IS 'JSON array of columns where >80% of rows are NULL';
COMMENT ON COLUMN db_capabilities.completeness_pct IS 'Percentage of columns with data (0-100)';
COMMENT ON COLUMN db_capabilities.date_range_start IS 'Earliest date from created_at/updated_at/as_of_date columns';
COMMENT ON COLUMN db_capabilities.date_range_end IS 'Latest date from created_at/updated_at/as_of_date columns';
COMMENT ON COLUMN db_capabilities.expected_freshness IS 'How often data should update (from config)';
COMMENT ON COLUMN db_capabilities.days_since_update IS 'Days since date_range_end (data staleness indicator)';
COMMENT ON COLUMN db_capabilities.freshness_status IS 'Freshness category: current, acceptable, stale, critical';
COMMENT ON COLUMN db_capabilities.last_scanned_at IS 'When this table was last scanned for metadata';
