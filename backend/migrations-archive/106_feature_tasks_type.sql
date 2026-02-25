-- Migration 106: Add task_type column to feature_tasks
-- Created: 2025-12-10
-- Purpose: Explicit task type instead of inferring from task_id prefix
--
-- Task types:
--   - implementation: Simple inline work (default for existing tasks)
--   - fix: Bug fix tasks (same as current fix-* pattern)
--   - task_file: Complex work with linked .md file in tasks/ folder
--   - discovery: Scope exploration phase (Task 0)

-- Add task_type column with default for existing rows
ALTER TABLE feature_tasks
ADD COLUMN IF NOT EXISTS task_type TEXT NOT NULL DEFAULT 'implementation';

-- Add check constraint for valid types
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'feature_tasks_type_check'
    ) THEN
        ALTER TABLE feature_tasks
        ADD CONSTRAINT feature_tasks_type_check
        CHECK (task_type IN ('implementation', 'fix', 'task_file', 'discovery'));
    END IF;
END $$;

-- Migrate existing fix-* tasks to have task_type='fix'
UPDATE feature_tasks
SET task_type = 'fix'
WHERE task_id LIKE 'fix-%' AND task_type = 'implementation';

-- Migrate existing 0.x tasks to have task_type='discovery'
UPDATE feature_tasks
SET task_type = 'discovery'
WHERE task_id LIKE '0.%' AND task_type = 'implementation';

-- Add index for task_type queries
CREATE INDEX IF NOT EXISTS idx_feature_tasks_type ON feature_tasks(task_type);

-- Add comment
COMMENT ON COLUMN feature_tasks.task_type IS
'Task type: implementation (inline work), fix (bug fix), task_file (complex work with .md file), discovery (scope exploration)';
