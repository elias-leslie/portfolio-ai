-- Migration 035: Celery Task Capabilities Table
-- Purpose: Track Celery scheduled tasks for auto-discovery and monitoring
-- Part of: System Capabilities Registry (Task 0059, Phase 1)
-- Created: 2025-11-13
-- Related: tasks/tasks-0059-system-capabilities-registry.md

CREATE TABLE IF NOT EXISTS celery_capabilities (
    id SERIAL PRIMARY KEY,
    task_name TEXT UNIQUE NOT NULL,
    category TEXT,  -- market_data, news, portfolio, analytics, infrastructure
    task_path TEXT,  -- File path: app.tasks.market_data_tasks.maintain_historical_market_data
    function_name TEXT,  -- Python function name
    schedule_description TEXT,  -- Human-readable: "Every 60 seconds", "Daily at 04:00 UTC"
    schedule_crontab TEXT,  -- Cron format: "0 4 * * *" or interval in seconds
    schedule_interval_seconds INTEGER,  -- Numeric interval for sorting
    last_run_at TIMESTAMP WITH TIME ZONE,
    next_run_at TIMESTAMP WITH TIME ZONE,
    success_count_7d INTEGER DEFAULT 0,
    failure_count_7d INTEGER DEFAULT 0,
    success_rate_pct INTEGER,  -- (success / (success + failure)) * 100
    avg_duration_ms INTEGER,
    max_duration_ms INTEGER,
    populates_tables JSONB,  -- Array of table names this task writes to
    depends_on_tasks JSONB,  -- Array of task names this depends on
    last_scanned_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

-- Indexes for query performance
CREATE INDEX IF NOT EXISTS idx_celery_capabilities_category ON celery_capabilities(category);
CREATE INDEX IF NOT EXISTS idx_celery_capabilities_success_rate ON celery_capabilities(success_rate_pct);
CREATE INDEX IF NOT EXISTS idx_celery_capabilities_interval ON celery_capabilities(schedule_interval_seconds);
CREATE INDEX IF NOT EXISTS idx_celery_capabilities_last_run ON celery_capabilities(last_run_at DESC);

-- Comments for documentation
COMMENT ON TABLE celery_capabilities IS 'Registry of Celery scheduled tasks with execution metadata';
COMMENT ON COLUMN celery_capabilities.task_name IS 'Celery task identifier (from beat_schedule key)';
COMMENT ON COLUMN celery_capabilities.category IS 'Business category: market_data, news, portfolio, analytics, infrastructure';
COMMENT ON COLUMN celery_capabilities.task_path IS 'Import path to Python function (e.g., app.tasks.market_data_tasks.fetch_prices)';
COMMENT ON COLUMN celery_capabilities.function_name IS 'Python function name extracted from task_path';
COMMENT ON COLUMN celery_capabilities.schedule_description IS 'Human-readable schedule description';
COMMENT ON COLUMN celery_capabilities.schedule_crontab IS 'Cron expression or interval in seconds (as string)';
COMMENT ON COLUMN celery_capabilities.schedule_interval_seconds IS 'Schedule converted to seconds for sorting and comparison';
COMMENT ON COLUMN celery_capabilities.last_run_at IS 'Timestamp of most recent task execution';
COMMENT ON COLUMN celery_capabilities.next_run_at IS 'Timestamp of next scheduled execution';
COMMENT ON COLUMN celery_capabilities.success_count_7d IS 'Successful executions in last 7 days';
COMMENT ON COLUMN celery_capabilities.failure_count_7d IS 'Failed executions in last 7 days';
COMMENT ON COLUMN celery_capabilities.success_rate_pct IS 'Success rate percentage (0-100)';
COMMENT ON COLUMN celery_capabilities.avg_duration_ms IS 'Average execution duration in milliseconds (last 7 days)';
COMMENT ON COLUMN celery_capabilities.max_duration_ms IS 'Maximum execution duration in milliseconds (last 7 days)';
COMMENT ON COLUMN celery_capabilities.populates_tables IS 'JSON array of database tables this task populates (detected via code scanning)';
COMMENT ON COLUMN celery_capabilities.depends_on_tasks IS 'JSON array of other Celery tasks this depends on';
