-- Migration: 024_deletion_audit.sql
-- Type: SAFE - Creates new audit table
-- Impact: Adds deletion tracking, no existing data affected
-- Created: 2025-11-10 (Response to Nov 9 deletion incident)
-- Purpose: Track all deletions for forensic analysis and incident response

-- Create deletion audit table
CREATE TABLE IF NOT EXISTS deletion_audit (
    id              BIGSERIAL PRIMARY KEY,
    table_name      TEXT NOT NULL,
    record_id       TEXT NOT NULL,
    deleted_by      TEXT NOT NULL,      -- User, application, or 'migration:XXX'
    deleted_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deletion_reason TEXT,                -- 'user_action' | 'migration' | 'cascade' | 'cleanup'
    row_count       INTEGER DEFAULT 1,   -- For batch deletes
    metadata        JSONB,               -- Additional context (e.g., CASCADE chain)
    restored_at     TIMESTAMPTZ          -- If deletion was rolled back
);

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_deletion_audit_table_name
ON deletion_audit(table_name);

CREATE INDEX IF NOT EXISTS idx_deletion_audit_deleted_at
ON deletion_audit(deleted_at DESC);

CREATE INDEX IF NOT EXISTS idx_deletion_audit_deleted_by
ON deletion_audit(deleted_by);

-- Index for finding specific record deletions
CREATE INDEX IF NOT EXISTS idx_deletion_audit_record_id
ON deletion_audit(table_name, record_id);

-- Partial index for recent deletions (last 30 days) - fast monitoring
-- Note: Cannot use NOW() in WHERE clause (not IMMUTABLE)
-- Instead, rely on idx_deletion_audit_deleted_at for queries with date filters
-- CREATE INDEX IF NOT EXISTS idx_deletion_audit_recent
-- ON deletion_audit(deleted_at DESC)
-- WHERE deleted_at > NOW() - INTERVAL '30 days';

-- ============================================================================
-- TRIGGERS: Auto-track deletions from critical tables
-- ============================================================================

-- Function to log deletions
CREATE OR REPLACE FUNCTION log_deletion()
RETURNS TRIGGER AS $$
DECLARE
    v_record_id TEXT;
    v_symbol TEXT;
BEGIN
    -- Extract ID (handle tables with different primary key names)
    -- Try to get id column, fall back to 'unknown' if not available
    BEGIN
        v_record_id := (row_to_json(OLD)->'id')::TEXT;
    EXCEPTION WHEN OTHERS THEN
        v_record_id := 'bulk_operation';
    END;

    -- Try to get symbol column if it exists
    BEGIN
        v_symbol := (row_to_json(OLD)->'symbol')::TEXT;
        -- Remove quotes from JSON string
        v_symbol := REPLACE(v_symbol, '"', '');
    EXCEPTION WHEN OTHERS THEN
        v_symbol := 'N/A';
    END;

    INSERT INTO deletion_audit (
        table_name,
        record_id,
        deleted_by,
        deletion_reason,
        metadata
    ) VALUES (
        TG_TABLE_NAME,
        v_record_id,
        CURRENT_USER,                    -- PostgreSQL user (e.g., portfolio_ai_user)
        'trigger',                       -- Will be overridden by application if needed
        jsonb_build_object(
            'symbol', COALESCE(v_symbol, 'N/A'),
            'trigger_operation', TG_OP,
            'trigger_time', NOW()
        )
    );
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

-- Trigger for watchlist_items deletions
DROP TRIGGER IF EXISTS trigger_audit_watchlist_items_deletion ON watchlist_items;
CREATE TRIGGER trigger_audit_watchlist_items_deletion
BEFORE DELETE ON watchlist_items
FOR EACH ROW
EXECUTE FUNCTION log_deletion();

-- Trigger for watchlist_snapshots deletions (including CASCADE)
DROP TRIGGER IF EXISTS trigger_audit_watchlist_snapshots_deletion ON watchlist_snapshots;
CREATE TRIGGER trigger_audit_watchlist_snapshots_deletion
BEFORE DELETE ON watchlist_snapshots
FOR EACH ROW
EXECUTE FUNCTION log_deletion();

-- Trigger for portfolio_positions deletions
DROP TRIGGER IF EXISTS trigger_audit_portfolio_positions_deletion ON portfolio_positions;
CREATE TRIGGER trigger_audit_portfolio_positions_deletion
BEFORE DELETE ON portfolio_positions
FOR EACH ROW
EXECUTE FUNCTION log_deletion();

-- ============================================================================
-- HELPER FUNCTIONS: Manual audit logging for migrations/scripts
-- ============================================================================

-- Function for migration scripts to log bulk deletions
CREATE OR REPLACE FUNCTION log_migration_deletion(
    p_table_name TEXT,
    p_deleted_by TEXT,
    p_row_count INTEGER,
    p_reason TEXT DEFAULT 'migration'
)
RETURNS VOID AS $$
BEGIN
    INSERT INTO deletion_audit (
        table_name,
        record_id,
        deleted_by,
        deletion_reason,
        row_count,
        metadata
    ) VALUES (
        p_table_name,
        'bulk_operation',
        p_deleted_by,
        p_reason,
        p_row_count,
        jsonb_build_object(
            'operation', 'bulk_delete',
            'logged_at', NOW()
        )
    );
END;
$$ LANGUAGE plpgsql;

-- Example usage in migration:
-- BEGIN;
--   DELETE FROM old_table WHERE condition;
--   SELECT log_migration_deletion('old_table', 'migration:024', 1234, 'cleanup');
-- COMMIT;

-- ============================================================================
-- REPORTING FUNCTIONS: Query audit log
-- ============================================================================

-- Get recent deletions (last 24 hours)
CREATE OR REPLACE FUNCTION get_recent_deletions(hours_ago INTEGER DEFAULT 24)
RETURNS TABLE (
    table_name TEXT,
    record_id TEXT,
    deleted_by TEXT,
    deleted_at TIMESTAMPTZ,
    deletion_reason TEXT,
    row_count INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        da.table_name,
        da.record_id,
        da.deleted_by,
        da.deleted_at,
        da.deletion_reason,
        da.row_count
    FROM deletion_audit da
    WHERE da.deleted_at > NOW() - (hours_ago || ' hours')::INTERVAL
    ORDER BY da.deleted_at DESC;
END;
$$ LANGUAGE plpgsql;

-- Get deletion summary by table (for monitoring)
CREATE OR REPLACE FUNCTION get_deletion_summary(hours_ago INTEGER DEFAULT 24)
RETURNS TABLE (
    table_name TEXT,
    total_deletions BIGINT,
    first_deletion TIMESTAMPTZ,
    last_deletion TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        da.table_name,
        COUNT(*)::BIGINT AS total_deletions,
        MIN(da.deleted_at) AS first_deletion,
        MAX(da.deleted_at) AS last_deletion
    FROM deletion_audit da
    WHERE da.deleted_at > NOW() - (hours_ago || ' hours')::INTERVAL
    GROUP BY da.table_name
    ORDER BY total_deletions DESC;
END;
$$ LANGUAGE plpgsql;

-- Detect mass deletions (potential incident)
CREATE OR REPLACE FUNCTION detect_mass_deletions(
    threshold INTEGER DEFAULT 100,
    time_window_minutes INTEGER DEFAULT 60
)
RETURNS TABLE (
    table_name TEXT,
    deletion_count BIGINT,
    time_window TEXT,
    deleted_by TEXT[]
) AS $$
BEGIN
    RETURN QUERY
    WITH deletion_windows AS (
        SELECT
            da.table_name,
            date_trunc('minute', da.deleted_at) AS minute_window,
            COUNT(*) AS deletions_in_minute,
            array_agg(DISTINCT da.deleted_by) AS users
        FROM deletion_audit da
        WHERE da.deleted_at > NOW() - (time_window_minutes || ' minutes')::INTERVAL
        GROUP BY da.table_name, date_trunc('minute', da.deleted_at)
    )
    SELECT
        dw.table_name,
        SUM(dw.deletions_in_minute)::BIGINT AS deletion_count,
        MIN(dw.minute_window)::TEXT || ' to ' || MAX(dw.minute_window)::TEXT AS time_window,
        array_agg(DISTINCT u)::TEXT[] AS deleted_by
    FROM deletion_windows dw,
         LATERAL unnest(dw.users) AS u
    WHERE dw.deletions_in_minute > threshold
    GROUP BY dw.table_name
    HAVING SUM(dw.deletions_in_minute) > threshold;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- MAINTENANCE: Cleanup old audit records
-- ============================================================================

-- Function to archive old audit records (call from cron job)
CREATE OR REPLACE FUNCTION cleanup_old_audit_records(days_to_keep INTEGER DEFAULT 90)
RETURNS TABLE (
    deleted_count BIGINT,
    oldest_remaining_date TIMESTAMPTZ
) AS $$
DECLARE
    v_deleted_count BIGINT;
    v_oldest_date TIMESTAMPTZ;
BEGIN
    -- Delete records older than retention period
    DELETE FROM deletion_audit
    WHERE deleted_at < NOW() - (days_to_keep || ' days')::INTERVAL;

    GET DIAGNOSTICS v_deleted_count = ROW_COUNT;

    -- Get oldest remaining record
    SELECT MIN(da.deleted_at) INTO v_oldest_date
    FROM deletion_audit da;

    RETURN QUERY
    SELECT v_deleted_count, v_oldest_date;
END;
$$ LANGUAGE plpgsql;

-- Example cron job (monthly cleanup):
-- SELECT * FROM cleanup_old_audit_records(90);

-- ============================================================================
-- VERIFICATION QUERIES (run post-migration)
-- ============================================================================

-- Verify table created
-- SELECT tablename FROM pg_tables WHERE tablename = 'deletion_audit';
-- Expected: 1 row

-- Verify triggers installed
-- SELECT tgname, tgrelid::regclass AS table_name
-- FROM pg_trigger
-- WHERE tgname LIKE 'trigger_audit%deletion';
-- Expected: 3 rows (watchlist_items, watchlist_snapshots, portfolio_positions)

-- Test trigger (creates audit record)
-- BEGIN;
--   INSERT INTO watchlist_items (id, symbol, user_id) VALUES (gen_random_uuid(), 'TEST', 'test_user');
--   DELETE FROM watchlist_items WHERE symbol = 'TEST';
--   SELECT * FROM deletion_audit WHERE table_name = 'watchlist_items' ORDER BY id DESC LIMIT 1;
-- ROLLBACK;
-- Expected: 1 audit record for TEST deletion

-- ============================================================================
-- ROLLBACK (if needed)
-- ============================================================================

-- To remove deletion auditing:
-- DROP TRIGGER IF EXISTS trigger_audit_watchlist_items_deletion ON watchlist_items;
-- DROP TRIGGER IF EXISTS trigger_audit_watchlist_snapshots_deletion ON watchlist_snapshots;
-- DROP TRIGGER IF EXISTS trigger_audit_portfolio_positions_deletion ON portfolio_positions;
-- DROP FUNCTION IF EXISTS log_deletion();
-- DROP FUNCTION IF EXISTS log_migration_deletion(TEXT, TEXT, INTEGER, TEXT);
-- DROP FUNCTION IF EXISTS get_recent_deletions(INTEGER);
-- DROP FUNCTION IF EXISTS get_deletion_summary(INTEGER);
-- DROP FUNCTION IF EXISTS detect_mass_deletions(INTEGER, INTEGER);
-- DROP FUNCTION IF EXISTS cleanup_old_audit_records(INTEGER);
-- DROP TABLE IF EXISTS deletion_audit;
