-- Migration 082: Add acceptance criteria and priority to feature_capabilities
-- Enables spec-driven development: features have explicit, testable acceptance criteria
-- Priority allows intelligent ordering of work (auto-calculated or user override)

-- Add priority column (user override, NULL = auto-calculate)
ALTER TABLE feature_capabilities
ADD COLUMN IF NOT EXISTS priority INTEGER DEFAULT NULL;

-- Add acceptance_criteria column (JSONB array of criteria)
-- Format: [{"id": "ac-001", "criterion": "...", "verification": "...", "type": "api", "passed": null}]
ALTER TABLE feature_capabilities
ADD COLUMN IF NOT EXISTS acceptance_criteria JSONB DEFAULT '[]';

-- Add vision_goals column (links to VISION.md strategic goals)
-- Values: autonomous_analysis, plain_language, validate_before_execute, transparency,
--         reliability, portfolio_monitoring, strategy_validation
ALTER TABLE feature_capabilities
ADD COLUMN IF NOT EXISTS vision_goals TEXT[] DEFAULT '{}';

-- Comments for documentation
COMMENT ON COLUMN feature_capabilities.priority IS
'User override priority (1-5). NULL = auto-calculate from layer verification progress. 1=critical, 2=high, 3=medium, 4=low, 5=backlog';

COMMENT ON COLUMN feature_capabilities.acceptance_criteria IS
'Array of {id, criterion, verification, type, passed} objects defining "done". Types: api, ui, db, backend, quality, content';

COMMENT ON COLUMN feature_capabilities.vision_goals IS
'Which VISION.md strategic goals this feature supports. Used for alignment tracking.';

-- Create index for querying by priority
CREATE INDEX IF NOT EXISTS idx_feature_capabilities_priority
ON feature_capabilities(priority);

-- Create GIN index for JSONB acceptance_criteria queries
CREATE INDEX IF NOT EXISTS idx_feature_capabilities_acceptance_criteria
ON feature_capabilities USING GIN (acceptance_criteria);

-- Create GIN index for vision_goals array queries
CREATE INDEX IF NOT EXISTS idx_feature_capabilities_vision_goals
ON feature_capabilities USING GIN (vision_goals);
