-- File audit table for codebase complexity tracking
-- Part of: System Registry Files tab

CREATE TABLE file_audit (
    id SERIAL PRIMARY KEY,
    path TEXT NOT NULL UNIQUE,
    is_directory BOOLEAN DEFAULT FALSE,
    extension TEXT,
    size_bytes INTEGER,
    lines_of_code INTEGER,
    file_count INTEGER,        -- for directories only
    total_loc INTEGER,         -- for directories only
    bloat_level TEXT,          -- null, 'warning', 'critical'
    last_modified TIMESTAMPTZ,
    scanned_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX idx_file_audit_path ON file_audit(path);
CREATE INDEX idx_file_audit_extension ON file_audit(extension) WHERE extension IS NOT NULL;
CREATE INDEX idx_file_audit_bloat ON file_audit(bloat_level) WHERE bloat_level IS NOT NULL;
CREATE INDEX idx_file_audit_is_directory ON file_audit(is_directory) WHERE is_directory = TRUE;
