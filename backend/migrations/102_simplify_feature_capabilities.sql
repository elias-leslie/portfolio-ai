-- Migration 102: Simplify feature_capabilities
-- Drop implementation-tracking columns (keep outcome-focused fields)
-- Date: 2025-12-09

-- Step 1: Drop dependent view that uses 'status' column
DROP VIEW IF EXISTS feature_dependency_view;

-- Step 2: Drop unused columns
ALTER TABLE feature_capabilities
    DROP COLUMN IF EXISTS task_file,
    DROP COLUMN IF EXISTS task_section,
    DROP COLUMN IF EXISTS health_status,
    DROP COLUMN IF EXISTS test_count,
    DROP COLUMN IF EXISTS diagram,
    DROP COLUMN IF EXISTS implementation_notes,
    DROP COLUMN IF EXISTS status,
    DROP COLUMN IF EXISTS effort,
    DROP COLUMN IF EXISTS source,
    DROP COLUMN IF EXISTS verified_by;

-- Step 3: Recreate the view without 'status' column
CREATE OR REPLACE VIEW feature_dependency_view AS
SELECT
    fd.id,
    f1.feature_id as feature,
    f1.name as feature_name,
    f2.feature_id as depends_on,
    f2.name as depends_on_name,
    f2.passes as depends_on_passes,
    fd.dependency_type,
    fd.notes,
    -- Is this dependency satisfied?
    CASE
        WHEN fd.dependency_type = 'blocks' AND f2.passes = true THEN true
        WHEN fd.dependency_type = 'soft' THEN true
        WHEN fd.dependency_type = 'related' THEN true
        ELSE false
    END as is_satisfied
FROM feature_dependencies fd
JOIN feature_capabilities f1 ON fd.feature_id = f1.id
JOIN feature_capabilities f2 ON fd.depends_on_id = f2.id;

COMMENT ON VIEW feature_dependency_view IS
'Shows feature dependencies with satisfaction status';
