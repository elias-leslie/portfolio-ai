-- Migration: 107_remove_passes_field.sql
-- Description: Remove passes field from feature_capabilities
--              Verification status is now calculated dynamically from:
--              - All tasks completed (completed_tasks == total_tasks)
--              - All acceptance criteria passed (criterion.passed == true)
-- Date: 2025-12-10

-- Drop dependent view first (will be recreated without passes)
DROP VIEW IF EXISTS feature_dependency_view CASCADE;

-- Drop the passes column (no longer needed)
ALTER TABLE feature_capabilities
DROP COLUMN IF EXISTS passes;

-- Recreate view without passes column
CREATE OR REPLACE VIEW feature_dependency_view AS
SELECT
    fc.id,
    fc.feature_id,
    fc.name,
    fc.category,
    fc.description,
    fc.layers,
    fc.layer_results,
    fc.priority,
    fc.acceptance_criteria,
    fc.vision_goals,
    fc.last_verified_at,
    fc.created_at,
    fc.updated_at,
    COALESCE(t.total_tasks, 0) as total_tasks,
    COALESCE(t.completed_tasks, 0) as completed_tasks,
    CASE
        WHEN COALESCE(t.total_tasks, 0) = 0 THEN 'orphaned'
        ELSE 'active'
    END as health_status
FROM feature_capabilities fc
LEFT JOIN (
    SELECT
        feature_id,
        COUNT(*) as total_tasks,
        COUNT(*) FILTER (WHERE completed = true) as completed_tasks
    FROM feature_tasks
    GROUP BY feature_id
) t ON t.feature_id = fc.id;

-- Add comment explaining new verification model
COMMENT ON TABLE feature_capabilities IS
'Feature registry. Verification status calculated dynamically from tasks + acceptance criteria, not stored.';
