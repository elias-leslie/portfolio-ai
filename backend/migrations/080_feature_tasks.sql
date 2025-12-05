-- Migration 080: Feature Tasks Table
-- Created: 2025-12-05
-- Purpose: Store subtasks for features (all-in-DB approach for long-running agent patterns)
--
-- This table replaces markdown task file parsing with database-native task tracking.
-- Each feature can have multiple subtasks with completion status.
-- Progress is calculated as: COUNT(*) WHERE completed = true / COUNT(*)
--
-- Agent permissions:
--   - /task_it: Can INSERT subtasks when creating features
--   - /do_it: Can UPDATE completed field (toggle completion)
--   - Manual: Full access for corrections

-- Create feature_tasks table
CREATE TABLE IF NOT EXISTS feature_tasks (
    id SERIAL PRIMARY KEY,
    feature_id INTEGER NOT NULL REFERENCES feature_capabilities(id) ON DELETE CASCADE,
    task_id VARCHAR(20) NOT NULL,  -- e.g., "1.1", "2.0", "3.2"
    description TEXT NOT NULL,
    completed BOOLEAN NOT NULL DEFAULT false,
    order_num INTEGER NOT NULL DEFAULT 0,  -- For display ordering
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,  -- When task was marked complete
    completed_by VARCHAR(50),  -- Who completed it (manual/do_it/agent)

    -- Unique constraint: One task_id per feature
    CONSTRAINT feature_tasks_unique_task UNIQUE (feature_id, task_id)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_feature_tasks_feature_id ON feature_tasks(feature_id);
CREATE INDEX IF NOT EXISTS idx_feature_tasks_completed ON feature_tasks(completed);
CREATE INDEX IF NOT EXISTS idx_feature_tasks_order ON feature_tasks(feature_id, order_num);

-- Auto-update updated_at trigger
CREATE OR REPLACE FUNCTION update_feature_tasks_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    -- Set completed_at when task is marked complete
    IF NEW.completed = true AND (OLD.completed IS NULL OR OLD.completed = false) THEN
        NEW.completed_at = NOW();
    END IF;
    -- Clear completed_at when task is unmarked
    IF NEW.completed = false AND OLD.completed = true THEN
        NEW.completed_at = NULL;
        NEW.completed_by = NULL;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS feature_tasks_updated_at ON feature_tasks;
CREATE TRIGGER feature_tasks_updated_at
    BEFORE UPDATE ON feature_tasks
    FOR EACH ROW
    EXECUTE FUNCTION update_feature_tasks_updated_at();

-- Comments
COMMENT ON TABLE feature_tasks IS 'Subtasks for feature_capabilities - replaces markdown task file parsing';
COMMENT ON COLUMN feature_tasks.feature_id IS 'FK to feature_capabilities.id';
COMMENT ON COLUMN feature_tasks.task_id IS 'Task identifier within feature (e.g., 1.1, 2.0)';
COMMENT ON COLUMN feature_tasks.description IS 'What needs to be done';
COMMENT ON COLUMN feature_tasks.completed IS 'Whether task is done';
COMMENT ON COLUMN feature_tasks.order_num IS 'Display order (0-based)';
COMMENT ON COLUMN feature_tasks.completed_at IS 'When task was marked complete';
COMMENT ON COLUMN feature_tasks.completed_by IS 'Who/what completed it (manual/do_it/agent_name)';
