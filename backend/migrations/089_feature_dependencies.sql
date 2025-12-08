-- Migration: Feature dependencies table
-- Purpose: Track blocking/blocked-by relationships between features

CREATE TABLE IF NOT EXISTS feature_dependencies (
    id SERIAL PRIMARY KEY,

    -- The feature that has the dependency
    feature_id INTEGER NOT NULL REFERENCES feature_capabilities(id) ON DELETE CASCADE,

    -- The feature it depends on
    depends_on_id INTEGER NOT NULL REFERENCES feature_capabilities(id) ON DELETE CASCADE,

    -- Type of dependency
    -- blocks: Hard dependency - depends_on must complete first
    -- soft: Soft dependency - nice to have completed first
    -- related: Just related, no ordering requirement
    dependency_type TEXT NOT NULL DEFAULT 'blocks',

    -- Optional note explaining the dependency
    notes TEXT,

    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    -- Prevent duplicate dependencies
    UNIQUE(feature_id, depends_on_id)
);

-- Prevent self-referential dependencies
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'no_self_dependency'
    ) THEN
        ALTER TABLE feature_dependencies
        ADD CONSTRAINT no_self_dependency
        CHECK (feature_id != depends_on_id);
    END IF;
END $$;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_feature_deps_feature_id
ON feature_dependencies(feature_id);

CREATE INDEX IF NOT EXISTS idx_feature_deps_depends_on
ON feature_dependencies(depends_on_id);

-- Comments
COMMENT ON TABLE feature_dependencies IS
'Tracks blocking relationships between features. feature_id depends on depends_on_id.';

COMMENT ON COLUMN feature_dependencies.dependency_type IS
'blocks: Hard dependency, soft: Nice to have, related: Just connected';

-- View to easily see what blocks what
CREATE OR REPLACE VIEW feature_dependency_view AS
SELECT
    fd.id,
    f1.feature_id as feature,
    f1.name as feature_name,
    f2.feature_id as depends_on,
    f2.name as depends_on_name,
    f2.status as depends_on_status,
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
