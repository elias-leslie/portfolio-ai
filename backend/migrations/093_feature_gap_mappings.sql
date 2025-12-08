-- Migration 093: Create feature_gap_mappings table for feature <-> trading gap relationships
-- Links features to trading gaps they resolve, are blocked by, or are related to
-- Enables bidirectional tracking of gap resolution progress

-- Create junction table for feature <-> trading gap relationships
CREATE TABLE IF NOT EXISTS feature_gap_mappings (
    id SERIAL PRIMARY KEY,
    feature_id INT NOT NULL REFERENCES feature_capabilities(id) ON DELETE CASCADE,
    gap_id TEXT NOT NULL REFERENCES trading_gaps(gap_id) ON DELETE CASCADE,
    relationship_type TEXT NOT NULL DEFAULT 'resolves',  -- 'resolves', 'blocked_by', 'related'
    notes TEXT,                                          -- Optional context
    linked_at TIMESTAMPTZ DEFAULT NOW(),
    linked_by VARCHAR(50),                               -- 'task_it', 'manual', 'audit_it'
    UNIQUE (feature_id, gap_id)
);

-- Add comments for documentation
COMMENT ON TABLE feature_gap_mappings IS 'Junction table linking features to trading gaps. Enables bidirectional gap resolution tracking.';
COMMENT ON COLUMN feature_gap_mappings.feature_id IS 'FK to feature_capabilities.id';
COMMENT ON COLUMN feature_gap_mappings.gap_id IS 'FK to trading_gaps.gap_id (GAP-001, etc.)';
COMMENT ON COLUMN feature_gap_mappings.relationship_type IS 'Type of relationship: resolves (feature fixes gap), blocked_by (feature waiting on gap), related (informational)';
COMMENT ON COLUMN feature_gap_mappings.notes IS 'Optional context about the relationship';
COMMENT ON COLUMN feature_gap_mappings.linked_by IS 'What created this link: task_it, manual, audit_it';

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_fgm_feature_id ON feature_gap_mappings(feature_id);
CREATE INDEX IF NOT EXISTS idx_fgm_gap_id ON feature_gap_mappings(gap_id);
CREATE INDEX IF NOT EXISTS idx_fgm_relationship_type ON feature_gap_mappings(relationship_type);

-- Add constraint for valid relationship types
ALTER TABLE feature_gap_mappings
ADD CONSTRAINT chk_relationship_type
CHECK (relationship_type IN ('resolves', 'blocked_by', 'related'));

-- Create view for easy querying of features with gap stats
CREATE OR REPLACE VIEW feature_gap_summary AS
SELECT
    fc.id,
    fc.feature_id,
    fc.name,
    COUNT(fgm.id) FILTER (WHERE fgm.relationship_type = 'resolves') as resolves_count,
    COUNT(fgm.id) FILTER (WHERE fgm.relationship_type = 'blocked_by') as blocked_by_count,
    ARRAY_AGG(DISTINCT fgm.gap_id) FILTER (WHERE fgm.gap_id IS NOT NULL) as gap_ids
FROM feature_capabilities fc
LEFT JOIN feature_gap_mappings fgm ON fc.id = fgm.feature_id
GROUP BY fc.id, fc.feature_id, fc.name;

-- Create view for gap resolution progress
CREATE OR REPLACE VIEW gap_resolution_summary AS
SELECT
    tg.gap_id,
    tg.capability,
    tg.criticality,
    tg.severity,
    tg.resolved_at IS NOT NULL as is_resolved,
    COUNT(fgm.id) FILTER (WHERE fgm.relationship_type = 'resolves') as feature_count,
    COUNT(fgm.id) FILTER (WHERE fgm.relationship_type = 'resolves' AND fc.passes = true) as completed_feature_count,
    ARRAY_AGG(DISTINCT fc.feature_id) FILTER (WHERE fgm.relationship_type = 'resolves') as feature_ids
FROM trading_gaps tg
LEFT JOIN feature_gap_mappings fgm ON tg.gap_id = fgm.gap_id
LEFT JOIN feature_capabilities fc ON fgm.feature_id = fc.id
GROUP BY tg.gap_id, tg.capability, tg.criticality, tg.severity, tg.resolved_at;
