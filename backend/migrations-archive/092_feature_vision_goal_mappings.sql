-- Migration 092: Create feature_vision_goal_mappings junction table
-- Replaces TEXT[] array in feature_capabilities with proper normalized junction table
-- Enables FK constraint enforcement and better query performance

-- Create junction table for feature <-> vision goal relationships
CREATE TABLE IF NOT EXISTS feature_vision_goal_mappings (
    id SERIAL PRIMARY KEY,
    feature_id INT NOT NULL REFERENCES feature_capabilities(id) ON DELETE CASCADE,
    vision_code TEXT NOT NULL REFERENCES vision_goals(code) ON DELETE CASCADE,
    linked_at TIMESTAMPTZ DEFAULT NOW(),
    linked_by VARCHAR(50),         -- 'task_it', 'manual', 'audit_it', 'migration'
    UNIQUE (feature_id, vision_code)
);

-- Add comments for documentation
COMMENT ON TABLE feature_vision_goal_mappings IS 'Junction table linking features to vision goals. Replaces TEXT[] array for proper FK enforcement.';
COMMENT ON COLUMN feature_vision_goal_mappings.feature_id IS 'FK to feature_capabilities.id';
COMMENT ON COLUMN feature_vision_goal_mappings.vision_code IS 'FK to vision_goals.code (VG-INTEL, VG-AUTO, etc.)';
COMMENT ON COLUMN feature_vision_goal_mappings.linked_by IS 'What created this link: task_it, manual, audit_it, migration';

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_fvgm_feature_id ON feature_vision_goal_mappings(feature_id);
CREATE INDEX IF NOT EXISTS idx_fvgm_vision_code ON feature_vision_goal_mappings(vision_code);

-- First, add any missing vision goals found in feature_capabilities to vision_goals table
-- This ensures FK constraint won't fail during migration
INSERT INTO vision_goals (code, name, description, category)
SELECT DISTINCT
    code,
    code || ' (auto-created)',  -- Placeholder name
    'Vision goal auto-created during migration from feature_capabilities.vision_goals array',
    'other'
FROM (
    SELECT unnest(vision_goals) as code
    FROM feature_capabilities
    WHERE vision_goals IS NOT NULL
      AND array_length(vision_goals, 1) > 0
) codes
WHERE code NOT IN (SELECT code FROM vision_goals)
ON CONFLICT (code) DO NOTHING;

-- Migrate existing data from vision_goals[] array to junction table
INSERT INTO feature_vision_goal_mappings (feature_id, vision_code, linked_by)
SELECT
    fc.id,
    unnest(fc.vision_goals),
    'migration'
FROM feature_capabilities fc
WHERE fc.vision_goals IS NOT NULL
  AND array_length(fc.vision_goals, 1) > 0
ON CONFLICT (feature_id, vision_code) DO NOTHING;

-- Verify migration: count should match
-- SELECT
--     (SELECT COUNT(*) FROM feature_vision_goal_mappings) as junction_count,
--     (SELECT SUM(array_length(vision_goals, 1)) FROM feature_capabilities WHERE vision_goals IS NOT NULL) as array_count;

-- Note: The vision_goals[] column in feature_capabilities is kept for backwards compatibility
-- A future migration (094+) can drop it after API/UI are updated to use junction table exclusively
