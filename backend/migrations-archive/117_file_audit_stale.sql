-- Add stale file detection columns to file_audit
-- Part of: Files tab stale file detection feature (portfolio-ai-087)

-- Git commit age tracking
ALTER TABLE file_audit ADD COLUMN IF NOT EXISTS last_commit_days INTEGER;

-- Reference tracking (how many files import/reference this file)
ALTER TABLE file_audit ADD COLUMN IF NOT EXISTS reference_count INTEGER DEFAULT 0;

-- Stale status: 'fresh', 'stale', 'orphan' (stale + no references)
ALTER TABLE file_audit ADD COLUMN IF NOT EXISTS stale_status TEXT;

-- Indexes for filtering
CREATE INDEX IF NOT EXISTS idx_file_audit_stale_status
    ON file_audit(stale_status) WHERE stale_status IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_file_audit_last_commit_days
    ON file_audit(last_commit_days) WHERE last_commit_days IS NOT NULL;
