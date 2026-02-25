-- Migration 001a: Fix Maintenance Log Timezone-Aware Timestamps
-- Preventive fix to avoid naive datetime issues
-- Created: 2025-11-11

-- Alter started_at to timezone-aware
ALTER TABLE maintenance_log
ALTER COLUMN started_at TYPE TIMESTAMP WITH TIME ZONE
USING started_at AT TIME ZONE 'UTC';

-- Alter completed_at to timezone-aware
ALTER TABLE maintenance_log
ALTER COLUMN completed_at TYPE TIMESTAMP WITH TIME ZONE
USING completed_at AT TIME ZONE 'UTC';

-- Update default for started_at
ALTER TABLE maintenance_log
ALTER COLUMN started_at SET DEFAULT CURRENT_TIMESTAMP;

COMMENT ON COLUMN maintenance_log.started_at IS 'Timestamp when task started (timezone-aware)';
COMMENT ON COLUMN maintenance_log.completed_at IS 'Timestamp when task completed (timezone-aware)';
