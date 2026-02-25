-- Migration 095: Add reads_from_tables and dependency_overrides to celery_capabilities
-- For Phase 1.5 of Workflow Visualization - intelligent dependency detection

-- Add reads_from_tables column (auto-detected by scanner via SQL SELECT/JOIN patterns)
ALTER TABLE celery_capabilities
ADD COLUMN IF NOT EXISTS reads_from_tables JSONB DEFAULT '[]'::jsonb;

-- Add dependency_overrides column (manual corrections for inferred dependencies)
-- Structure: {"add": ["task_a"], "remove": ["task_b"], "reason": "..."}
ALTER TABLE celery_capabilities
ADD COLUMN IF NOT EXISTS dependency_overrides JSONB DEFAULT '{}'::jsonb;

-- Add index for dependency queries (GIN for JSONB containment queries)
CREATE INDEX IF NOT EXISTS idx_celery_capabilities_reads
ON celery_capabilities USING GIN (reads_from_tables);

-- Add comments for documentation
COMMENT ON COLUMN celery_capabilities.reads_from_tables IS
'Tables this task reads from (auto-detected via SQL SELECT/JOIN patterns in source code)';

COMMENT ON COLUMN celery_capabilities.dependency_overrides IS
'Manual dependency corrections: {add: ["task1"], remove: ["task2"], reason: "explanation"}';
