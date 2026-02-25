-- Migration 048: Remove task_name constraint from maintenance_log
-- Purpose: Allow dynamic task names for data freshness monitoring and other automated tasks
-- Created: 2025-12-01

-- Drop the CHECK constraint that limits task_name values
ALTER TABLE maintenance_log
DROP CONSTRAINT IF EXISTS maintenance_log_task_name_check;

-- Comment to explain the change
COMMENT ON COLUMN maintenance_log.task_name IS 'Task name (no constraint - allows dynamic task names for monitoring)';
