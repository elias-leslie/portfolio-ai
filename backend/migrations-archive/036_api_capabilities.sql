-- Migration 036: API Endpoint Capabilities Table
-- Purpose: Track API endpoints for auto-discovery and monitoring
-- Part of: System Capabilities Registry (Task 0059, Phase 1)
-- Created: 2025-11-13
-- Related: tasks/tasks-0059-system-capabilities-registry.md

CREATE TABLE IF NOT EXISTS api_capabilities (
    id SERIAL PRIMARY KEY,
    endpoint_path TEXT NOT NULL,
    http_method TEXT NOT NULL,  -- GET, POST, PUT, DELETE
    category TEXT,  -- market_data, news, portfolio, analytics, infrastructure
    route_file TEXT,  -- File path: app/routes/watchlist.py
    function_name TEXT,  -- Python function name
    depends_on_tables JSONB,  -- Tables this endpoint reads from
    avg_response_time_ms INTEGER,
    p95_response_time_ms INTEGER,
    p99_response_time_ms INTEGER,
    error_rate_pct DECIMAL(5,2),
    last_7d_request_count INTEGER,
    last_scanned_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT unique_endpoint UNIQUE(endpoint_path, http_method)
);

-- Indexes for query performance
CREATE INDEX IF NOT EXISTS idx_api_capabilities_category ON api_capabilities(category);
CREATE INDEX IF NOT EXISTS idx_api_capabilities_method ON api_capabilities(http_method);
CREATE INDEX IF NOT EXISTS idx_api_capabilities_error_rate ON api_capabilities(error_rate_pct);

-- Comments for documentation
COMMENT ON TABLE api_capabilities IS 'Registry of API endpoints with performance and dependency metadata';
COMMENT ON COLUMN api_capabilities.endpoint_path IS 'API endpoint path (e.g., /api/watchlist/items)';
COMMENT ON COLUMN api_capabilities.http_method IS 'HTTP method: GET, POST, PUT, DELETE';
COMMENT ON COLUMN api_capabilities.category IS 'Business category: market_data, news, portfolio, analytics, infrastructure';
COMMENT ON COLUMN api_capabilities.route_file IS 'Source file path (e.g., app/routes/watchlist.py)';
COMMENT ON COLUMN api_capabilities.function_name IS 'Python function name implementing this endpoint';
COMMENT ON COLUMN api_capabilities.depends_on_tables IS 'JSON array of database tables this endpoint queries';
COMMENT ON COLUMN api_capabilities.avg_response_time_ms IS 'Average response time in milliseconds (last 7 days)';
COMMENT ON COLUMN api_capabilities.p95_response_time_ms IS '95th percentile response time in milliseconds';
COMMENT ON COLUMN api_capabilities.p99_response_time_ms IS '99th percentile response time in milliseconds';
COMMENT ON COLUMN api_capabilities.error_rate_pct IS 'Error rate percentage (0-100)';
COMMENT ON COLUMN api_capabilities.last_7d_request_count IS 'Total requests in last 7 days';
