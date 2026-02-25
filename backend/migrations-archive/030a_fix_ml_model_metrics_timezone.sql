-- Migration 030a: Fix ML Model Metrics Timezone-Aware Timestamps
-- Fixes naive datetime issue causing table freshness error
-- Created: 2025-11-11

-- Alter trained_at to timezone-aware
ALTER TABLE ml_model_metrics
ALTER COLUMN trained_at TYPE TIMESTAMP WITH TIME ZONE
USING trained_at AT TIME ZONE 'UTC';

-- Alter created_at to timezone-aware
ALTER TABLE ml_model_metrics
ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE
USING created_at AT TIME ZONE 'UTC';

-- Update default for future inserts
ALTER TABLE ml_model_metrics
ALTER COLUMN trained_at SET DEFAULT NOW();

ALTER TABLE ml_model_metrics
ALTER COLUMN created_at SET DEFAULT NOW();

COMMENT ON COLUMN ml_model_metrics.trained_at IS 'Timestamp when model was trained (timezone-aware)';
COMMENT ON COLUMN ml_model_metrics.created_at IS 'Timestamp when record was created (timezone-aware)';
