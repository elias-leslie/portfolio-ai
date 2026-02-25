-- Migration 103: Claude progress log for session tracking
-- Replaces claude-progress.txt from Anthropic's agent harness model
-- Date: 2025-12-09

CREATE TABLE IF NOT EXISTS claude_progress_log (
    id SERIAL PRIMARY KEY,
    session_id TEXT,                          -- Group entries by session
    logged_at TIMESTAMPTZ DEFAULT NOW(),
    action TEXT NOT NULL,                     -- What was done
    action_type TEXT,                         -- category: implement, verify, fix, explore, etc.
    feature_id TEXT,                          -- Optional: linked FEAT-XXX
    task_file TEXT,                           -- Optional: linked task file path
    files_modified TEXT[],                    -- Files changed
    details JSONB,                            -- Additional context
    git_commit TEXT,                          -- Associated commit hash
    context_percent INTEGER                   -- Context usage at time of log
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_claude_progress_session ON claude_progress_log(session_id);
CREATE INDEX IF NOT EXISTS idx_claude_progress_logged_at ON claude_progress_log(logged_at DESC);
CREATE INDEX IF NOT EXISTS idx_claude_progress_feature ON claude_progress_log(feature_id);
CREATE INDEX IF NOT EXISTS idx_claude_progress_action_type ON claude_progress_log(action_type);

COMMENT ON TABLE claude_progress_log IS 'Session progress tracking for Claude Code sessions. Replaces text-based claude-progress.txt';
COMMENT ON COLUMN claude_progress_log.action_type IS 'Categories: start, progress, complete, verify, audit, pause, plan';
