-- Migration 045: Extend Maintenance System
-- Purpose: Add support for new maintenance tasks and statistics tracking
-- Created: 2025-11-16

-- Extend maintenance_log table to support all maintenance task types
ALTER TABLE maintenance_log DROP CONSTRAINT IF EXISTS maintenance_log_task_name_check;

ALTER TABLE maintenance_log ADD CONSTRAINT maintenance_log_task_name_check
    CHECK (task_name IN (
        'cleanup_news',
        'vacuum_database',
        'validate_integrity',
        'cleanup_old_news',
        'cleanup_old_agent_runs',
        'cleanup_orphaned_data',
        'rotate_logs',
        'cleanup_old_logs',
        'cleanup_temp_files',
        'check_disk_space'
    ));

-- Create maintenance_stats table for tracking metrics over time
CREATE TABLE IF NOT EXISTS maintenance_stats (
    id SERIAL PRIMARY KEY,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metric_name TEXT NOT NULL,
    metric_value NUMERIC NOT NULL,
    metric_unit TEXT,  -- bytes, count, percentage, etc.
    metadata JSONB,  -- Additional context (e.g., table name, file path)
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for maintenance_stats
CREATE INDEX IF NOT EXISTS idx_maintenance_stats_recorded_at ON maintenance_stats(recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_maintenance_stats_metric_name ON maintenance_stats(metric_name);
CREATE INDEX IF NOT EXISTS idx_maintenance_stats_metric_recorded ON maintenance_stats(metric_name, recorded_at DESC);

-- Add comment for documentation
COMMENT ON TABLE maintenance_stats IS 'Tracks maintenance metrics over time (database size, disk space, cleanup counts, etc.)';
COMMENT ON COLUMN maintenance_stats.metric_name IS 'Name of metric (e.g., database_size_bytes, disk_space_used_percentage, news_cleaned_count)';
COMMENT ON COLUMN maintenance_stats.metric_value IS 'Numeric value of metric';
COMMENT ON COLUMN maintenance_stats.metric_unit IS 'Unit of measurement (bytes, count, percentage, seconds, etc.)';
COMMENT ON COLUMN maintenance_stats.metadata IS 'Additional context (e.g., {"table": "news_cache", "partition": "/"})';
