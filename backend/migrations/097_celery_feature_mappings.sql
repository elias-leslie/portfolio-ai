-- Migration: 097_celery_feature_mappings.sql
-- Purpose: Junction table linking Celery tasks to features they power
-- Used by: Solution Map visualization, /audit_it connection audit

-- Create junction table
CREATE TABLE IF NOT EXISTS celery_feature_mappings (
    id SERIAL PRIMARY KEY,
    task_name TEXT NOT NULL,
    feature_id INTEGER NOT NULL REFERENCES feature_capabilities(id) ON DELETE CASCADE,
    relationship_type TEXT DEFAULT 'powers',  -- 'powers', 'supports', 'monitors'
    confidence TEXT DEFAULT 'high',           -- 'high', 'medium', 'low'
    reason TEXT,                               -- Why this mapping exists
    linked_at TIMESTAMPTZ DEFAULT NOW(),
    linked_by VARCHAR(50) DEFAULT 'migration', -- 'migration', 'audit_it', 'manual'
    UNIQUE (task_name, feature_id)
);

-- Add indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_celery_feature_task ON celery_feature_mappings(task_name);
CREATE INDEX IF NOT EXISTS idx_celery_feature_feature ON celery_feature_mappings(feature_id);
CREATE INDEX IF NOT EXISTS idx_celery_feature_confidence ON celery_feature_mappings(confidence);

-- Add comments
COMMENT ON TABLE celery_feature_mappings IS 'Links Celery scheduled tasks to the features they power';
COMMENT ON COLUMN celery_feature_mappings.relationship_type IS 'powers=primary driver, supports=secondary, monitors=health check';
COMMENT ON COLUMN celery_feature_mappings.confidence IS 'high=verified, medium=inferred, low=guess';
COMMENT ON COLUMN celery_feature_mappings.linked_by IS 'Who created this mapping: migration, audit_it, manual';
