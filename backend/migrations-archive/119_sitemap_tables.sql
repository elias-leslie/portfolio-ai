-- Migration: 119_sitemap_tables.sql
-- Description: Create sitemap_entries and sitemap_health_history tables for dynamic endpoint monitoring
-- Created: 2025-12-15

-- Main sitemap entries table
CREATE TABLE IF NOT EXISTS sitemap_entries (
    id SERIAL PRIMARY KEY,

    -- Endpoint identification
    port INTEGER NOT NULL,                       -- 3000, 8000, etc.
    path TEXT NOT NULL,                          -- /watchlist, /api/symbols, etc.
    method VARCHAR(10) DEFAULT 'GET',            -- GET, POST, PUT, DELETE
    entry_type VARCHAR(20) NOT NULL,             -- 'frontend_page', 'api_endpoint', 'manual'

    -- Discovery metadata
    source VARCHAR(50),                          -- 'openapi', 'crawler', 'api_scanner', 'manual'
    title TEXT,                                  -- Page title or endpoint description
    parent_path TEXT,                            -- Parent page for hierarchy

    -- Health status (real-time from polling)
    health_status VARCHAR(20) DEFAULT 'unknown', -- 'healthy', 'warning', 'error', 'unknown'
    console_errors INTEGER DEFAULT 0,
    console_warnings INTEGER DEFAULT 0,
    http_status INTEGER,                         -- Last HTTP status code
    response_time_ms INTEGER,                    -- Last response time
    last_error_message TEXT,                     -- Truncated to 500 chars

    -- Evidence integration (FK to artifacts table)
    artifact_id INTEGER REFERENCES artifacts(id) ON DELETE SET NULL,
    last_evidence_captured_at TIMESTAMPTZ,

    -- Timestamps
    last_checked_at TIMESTAMPTZ,
    discovered_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Unique constraint: port + path + method
    CONSTRAINT sitemap_entries_unique UNIQUE (port, path, method)
);

-- Indexes for common queries
CREATE INDEX idx_sitemap_port ON sitemap_entries(port);
CREATE INDEX idx_sitemap_health ON sitemap_entries(health_status);
CREATE INDEX idx_sitemap_entry_type ON sitemap_entries(entry_type);
CREATE INDEX idx_sitemap_parent ON sitemap_entries(parent_path);
CREATE INDEX idx_sitemap_last_checked ON sitemap_entries(last_checked_at);
CREATE INDEX idx_sitemap_artifact ON sitemap_entries(artifact_id) WHERE artifact_id IS NOT NULL;

-- Comments
COMMENT ON TABLE sitemap_entries IS 'Registry of all discoverable endpoints for health monitoring';
COMMENT ON COLUMN sitemap_entries.health_status IS 'Based on console errors: healthy(0), warning(warnings only), error(errors)';
COMMENT ON COLUMN sitemap_entries.entry_type IS 'frontend_page = Next.js pages, api_endpoint = FastAPI routes, manual = user-added';

-- Updated_at trigger
CREATE OR REPLACE FUNCTION update_sitemap_entries_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_sitemap_entries_updated_at
    BEFORE UPDATE ON sitemap_entries
    FOR EACH ROW
    EXECUTE FUNCTION update_sitemap_entries_updated_at();


-- Health history table (7-day retention for detailed logs)
CREATE TABLE IF NOT EXISTS sitemap_health_history (
    id SERIAL PRIMARY KEY,
    sitemap_entry_id INTEGER NOT NULL REFERENCES sitemap_entries(id) ON DELETE CASCADE,
    checked_at TIMESTAMPTZ NOT NULL,
    health_status VARCHAR(20),
    console_errors INTEGER DEFAULT 0,
    console_warnings INTEGER DEFAULT 0,
    http_status INTEGER,
    response_time_ms INTEGER,
    error_details JSONB,                         -- Full console output, max 10 errors
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for history queries
CREATE INDEX idx_health_history_entry ON sitemap_health_history(sitemap_entry_id);
CREATE INDEX idx_health_history_checked ON sitemap_health_history(checked_at);
-- Note: Cleanup queries use idx_health_history_checked - no partial index needed

-- Comments
COMMENT ON TABLE sitemap_health_history IS 'Historical health check results with 7-day retention';
COMMENT ON COLUMN sitemap_health_history.error_details IS 'JSONB with console errors/warnings, truncated to 10 entries';
