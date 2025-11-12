-- Migration 001: Create maintenance_log table
-- Purpose: Track execution history and results for maintenance tasks
-- Created: 2025-11-11

CREATE TABLE IF NOT EXISTS maintenance_log (
    id SERIAL PRIMARY KEY,
    task_name TEXT NOT NULL CHECK (task_name IN ('cleanup_news', 'vacuum_database', 'validate_integrity')),
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    status TEXT NOT NULL CHECK (status IN ('running', 'success', 'error')),
    dry_run BOOLEAN NOT NULL DEFAULT false,
    summary JSONB,
    error_message TEXT
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_maintenance_log_task_name ON maintenance_log(task_name);
CREATE INDEX IF NOT EXISTS idx_maintenance_log_started_at ON maintenance_log(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_maintenance_log_status ON maintenance_log(status);

-- Composite index for last-run queries
CREATE INDEX IF NOT EXISTS idx_maintenance_log_task_started ON maintenance_log(task_name, started_at DESC);
