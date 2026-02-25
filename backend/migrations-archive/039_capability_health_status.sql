-- Migration 039: Add health_status column to capability tables
-- Purpose: Track health status for capabilities (active, orphaned, legacy, suspect)
-- Part of: System Capabilities Registry (Task 0059, Phase 2)
-- Created: 2025-11-13
-- Related: tasks/tasks-0059-system-capabilities-registry.md

-- Add health_status column to db_capabilities
ALTER TABLE db_capabilities
ADD COLUMN IF NOT EXISTS health_status TEXT DEFAULT 'active';

-- Add health_status column to celery_capabilities
ALTER TABLE celery_capabilities
ADD COLUMN IF NOT EXISTS health_status TEXT DEFAULT 'active';

-- Add health_status column to api_capabilities
ALTER TABLE api_capabilities
ADD COLUMN IF NOT EXISTS health_status TEXT DEFAULT 'active';

-- Create indexes for health_status queries
CREATE INDEX IF NOT EXISTS idx_db_capabilities_health ON db_capabilities(health_status);
CREATE INDEX IF NOT EXISTS idx_celery_capabilities_health ON celery_capabilities(health_status);
CREATE INDEX IF NOT EXISTS idx_api_capabilities_health ON api_capabilities(health_status);

-- Comments for documentation
COMMENT ON COLUMN db_capabilities.health_status IS 'Health status: active (healthy), orphaned (unused), legacy (stale/broken), suspect (problematic)';
COMMENT ON COLUMN celery_capabilities.health_status IS 'Health status: active (healthy), orphaned (unused), legacy (never run/failing), suspect (low success rate)';
COMMENT ON COLUMN api_capabilities.health_status IS 'Health status: active (healthy), orphaned (no dependencies), legacy (broken dependencies), suspect (mixed dependencies)';
