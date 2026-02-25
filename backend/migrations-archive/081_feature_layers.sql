-- Migration: Add layers and test tracking to feature_capabilities
-- Layers track which verification types apply to each feature

-- Verification Layers:
-- - Frontend: Frontend code exists, correct imports, no errors
-- - Backend: Backend code exists, wired correctly, not a stub
-- - UI: Renders correctly, no visual bugs (overlays, dark mode, colors)
-- - API: Endpoint returns correct data structure
-- - DB: Data exists in database when expected
-- - Tasks: Celery task registered and runs successfully

-- Add layers column as TEXT[] array
ALTER TABLE feature_capabilities
ADD COLUMN IF NOT EXISTS layers TEXT[] DEFAULT '{}';

-- Add layer_results column to track verification status per layer
-- Format: {"Frontend": {"passed": true, "evidence": "file.tsx:45"}, "UI": {"passed": false, "evidence": "dark mode color issue"}}
ALTER TABLE feature_capabilities
ADD COLUMN IF NOT EXISTS layer_results JSONB DEFAULT '{}';

-- Add test_count column to track number of tests for this feature
ALTER TABLE feature_capabilities
ADD COLUMN IF NOT EXISTS test_count INTEGER DEFAULT 0;

-- Comments
COMMENT ON COLUMN feature_capabilities.layers IS 'Verification layers: Frontend, Backend, UI, API, DB, Tasks';
COMMENT ON COLUMN feature_capabilities.layer_results IS 'Per-layer verification: {"UI": {"passed": true, "evidence": "..."}}';
COMMENT ON COLUMN feature_capabilities.test_count IS 'Number of tests covering this feature';

-- Create index for querying by layers
CREATE INDEX IF NOT EXISTS idx_feature_capabilities_layers
ON feature_capabilities USING GIN (layers);

-- Update existing features with default layers based on category
-- Most features have Frontend + Backend + UI (user-facing with code)
UPDATE feature_capabilities
SET layers = ARRAY['Frontend', 'Backend', 'UI']
WHERE layers = '{}' OR layers IS NULL;

-- Architecture/Infrastructure features - Backend only (no UI)
UPDATE feature_capabilities
SET layers = ARRAY['Backend']
WHERE category IN ('Architecture', 'Infrastructure');

-- Status features - all layers (full system monitoring)
UPDATE feature_capabilities
SET layers = ARRAY['Frontend', 'Backend', 'UI', 'API', 'DB', 'Tasks']
WHERE category = 'Status';

-- Capabilities features - Frontend + Backend + UI + API + DB
UPDATE feature_capabilities
SET layers = ARRAY['Frontend', 'Backend', 'UI', 'API', 'DB']
WHERE category = 'Capabilities';

-- Agents features - all layers
UPDATE feature_capabilities
SET layers = ARRAY['Frontend', 'Backend', 'UI', 'API', 'DB', 'Tasks']
WHERE category = 'Agents';

-- Data-driven features (Watchlist, Portfolio, Trading, etc.) - add API + DB
UPDATE feature_capabilities
SET layers = ARRAY['Frontend', 'Backend', 'UI', 'API', 'DB']
WHERE category IN ('Watchlist', 'Portfolio', 'Paper Trading', 'Strategies', 'Backtest', 'Settings');
