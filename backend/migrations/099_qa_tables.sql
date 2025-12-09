-- Migration: 099_qa_tables.sql
-- Description: Create QA system tables for issue tracking and trend analysis
-- Created: 2025-12-09

-- QA Issues table for tracking code quality and data integrity issues
-- Supports automated detection from ruff, custom scanners, and manual entries
CREATE TABLE IF NOT EXISTS qa_issues (
    id SERIAL PRIMARY KEY,
    issue_id VARCHAR(20) UNIQUE NOT NULL,  -- QA-001, QA-002, etc.
    category VARCHAR(50) NOT NULL,          -- dead_code, dry_violation, security, orphan_file, schema_drift, stale_data, bloat, test_gap
    severity VARCHAR(20) NOT NULL,          -- critical, high, medium, low
    file_path TEXT,                         -- File path for code issues (nullable for data issues)
    line_start INTEGER,                     -- Start line number (nullable)
    line_end INTEGER,                       -- End line number (nullable)
    description TEXT NOT NULL,              -- Human-readable issue description
    detection_source VARCHAR(50),           -- ruff, custom_scanner, manual, data_check

    -- Lifecycle tracking
    first_detected_at TIMESTAMPTZ DEFAULT NOW(),
    last_detected_at TIMESTAMPTZ DEFAULT NOW(),  -- Updated if issue re-detected after resolution
    resolved_at TIMESTAMPTZ,                     -- When issue was resolved
    resolved_by VARCHAR(100),                    -- auto, manual, claude, clean_it
    resolution_notes TEXT,                       -- How the issue was resolved

    -- False positive handling
    false_positive BOOLEAN DEFAULT false,   -- Mark issues that aren't real problems

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_qa_issues_category ON qa_issues(category);
CREATE INDEX IF NOT EXISTS idx_qa_issues_severity ON qa_issues(severity);
CREATE INDEX IF NOT EXISTS idx_qa_issues_resolved ON qa_issues(resolved_at);
CREATE INDEX IF NOT EXISTS idx_qa_issues_file_path ON qa_issues(file_path);
CREATE INDEX IF NOT EXISTS idx_qa_issues_detection_source ON qa_issues(detection_source);
CREATE INDEX IF NOT EXISTS idx_qa_issues_false_positive ON qa_issues(false_positive) WHERE false_positive = false;
CREATE INDEX IF NOT EXISTS idx_qa_issues_unresolved ON qa_issues(resolved_at) WHERE resolved_at IS NULL;

-- QA Snapshots table for tracking trends over time
-- Daily snapshots of issue counts, LOC, and other metrics
CREATE TABLE IF NOT EXISTS qa_snapshots (
    id SERIAL PRIMARY KEY,
    snapshot_date DATE UNIQUE NOT NULL,     -- One snapshot per day

    -- Issue counts by severity
    total_issues INTEGER NOT NULL,
    critical_count INTEGER DEFAULT 0,
    high_count INTEGER DEFAULT 0,
    medium_count INTEGER DEFAULT 0,
    low_count INTEGER DEFAULT 0,

    -- Issue counts by category
    by_category JSONB,                      -- {"dead_code": 5, "dry_violation": 12, ...}

    -- Delta tracking (changes since last snapshot)
    issues_added INTEGER DEFAULT 0,         -- New issues since last snapshot
    issues_resolved INTEGER DEFAULT 0,      -- Resolved since last snapshot

    -- Codebase metrics for trend analysis
    lines_of_code INTEGER,                  -- Total LOC for trend
    file_count INTEGER,                     -- Total files for trend
    table_count INTEGER,                    -- Total DB tables for trend

    -- Timestamp
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_qa_snapshots_date ON qa_snapshots(snapshot_date);
CREATE INDEX IF NOT EXISTS idx_qa_snapshots_created_at ON qa_snapshots(created_at);

-- Trigger to update updated_at timestamp on qa_issues
CREATE OR REPLACE FUNCTION update_qa_issues_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_qa_issues_updated_at ON qa_issues;
CREATE TRIGGER trigger_qa_issues_updated_at
    BEFORE UPDATE ON qa_issues
    FOR EACH ROW
    EXECUTE FUNCTION update_qa_issues_updated_at();

-- Record migration
INSERT INTO schema_migrations (version, description, applied_at, checksum)
VALUES (99, 'Create QA system tables for issue tracking and trend analysis', NOW(), md5('099_qa_tables'))
ON CONFLICT (version) DO NOTHING;
