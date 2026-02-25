-- Migration: Enhanced subtask fields for task file replacement
-- Purpose: Add files, notes, status to subtasks for granular tracking

-- Files array - which files this subtask modifies
-- Example: ["backend/app/api/foo.py", "frontend/components/Bar.tsx"]
ALTER TABLE feature_tasks
ADD COLUMN IF NOT EXISTS files TEXT[] DEFAULT '{}';

-- Notes - free-form context for this subtask
-- Examples: "DEFERRED - optional", "Uses XYZ approach", "Depends on API being ready"
ALTER TABLE feature_tasks
ADD COLUMN IF NOT EXISTS notes TEXT;

-- Status enum (more granular than completed boolean)
-- pending: Not started
-- in_progress: Currently working
-- deferred: Intentionally skipped/postponed
-- blocked: Waiting on something
-- complete: Done
ALTER TABLE feature_tasks
ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'pending';

-- Effort per subtask (optional but useful for planning)
ALTER TABLE feature_tasks
ADD COLUMN IF NOT EXISTS effort TEXT;

-- Add comments
COMMENT ON COLUMN feature_tasks.files IS
'Array of file paths this subtask modifies. Example: ["backend/app/api/foo.py:45-89"]';

COMMENT ON COLUMN feature_tasks.notes IS
'Free-form notes: "DEFERRED - optional", implementation details, blockers';

COMMENT ON COLUMN feature_tasks.status IS
'Work status: pending, in_progress, deferred, blocked, complete';

COMMENT ON COLUMN feature_tasks.effort IS
'Effort estimate: trivial, low, medium, high';

-- Update completed based on status for consistency
-- If status is 'complete', completed should be true
-- This trigger keeps them in sync
CREATE OR REPLACE FUNCTION sync_task_completion()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status = 'complete' THEN
        NEW.completed := true;
    ELSIF NEW.status IN ('pending', 'in_progress', 'blocked') THEN
        NEW.completed := false;
    END IF;
    -- 'deferred' keeps existing completed value
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_sync_task_completion ON feature_tasks;
CREATE TRIGGER trigger_sync_task_completion
    BEFORE INSERT OR UPDATE OF status ON feature_tasks
    FOR EACH ROW
    EXECUTE FUNCTION sync_task_completion();
