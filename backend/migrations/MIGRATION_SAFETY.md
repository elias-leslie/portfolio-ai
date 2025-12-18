# Migration Safety Guide

**Purpose**: Prevent data loss during database migrations through comprehensive safety protocols
**Created**: 2025-11-10 (Response to Nov 9 deletion incident)
**Required Reading**: All developers must review before creating or executing migrations

---

## Table of Contents

1. [Quick Reference](#quick-reference)
2. [Pre-Migration Checklist](#pre-migration-checklist)
3. [Safe vs Unsafe Migrations](#safe-vs-unsafe-migrations)
4. [Dry-Run Workflow](#dry-run-workflow)
5. [Backup and Rollback](#backup-and-rollback)
6. [CASCADE Analysis](#cascade-analysis)
7. [Migration Templates](#migration-templates)
8. [Testing Migrations](#testing-migrations)
9. [Production Deployment](#production-deployment)

---

## Quick Reference

### Migration Runner Commands

```bash
# 1. Dry-run (ALWAYS run this first)
python backend/scripts/migrate.py --dry-run

# 2. Analyze specific migration
python backend/scripts/migrate.py --dry-run --migration 018

# 3. Execute with safety checks
python backend/scripts/migrate.py --execute

# 4. Execute specific migration
python backend/scripts/migrate.py --execute --migration 018
```

### Safety Levels

- 🟢 **SAFE**: Schema changes with no data loss (ADD COLUMN, CREATE INDEX)
- 🟡 **CAUTION**: Data modifications (UPDATE, ALTER with defaults)
- 🔴 **DANGER**: Destructive operations (DROP, DELETE, CASCADE)

---

## Pre-Migration Checklist

**MANDATORY for all migrations - Complete before execution:**

### ✅ Phase 1: Analysis

- [ ] **Dry-run executed** and reviewed
  ```bash
  python backend/scripts/migrate.py --dry-run --migration <VERSION>
  ```
- [ ] **Impact analysis** shows expected changes:
  - Affected tables identified
  - Row counts verified
  - CASCADE effects analyzed
- [ ] **Migration type** classified (SAFE/CAUTION/DANGER)
- [ ] **Rollback plan** documented (see template below)

### ✅ Phase 2: Backup

- [ ] **Pre-migration backup** created:
  - Automatic via `--execute` for destructive migrations
  - Manual for production: `pg_dump -d portfolio_ai -f backup.sql`
- [ ] **Backup verified**:
  ```bash
  # Check file size is reasonable
  ls -lh backups/pre-migration-*.sql
  ```
- [ ] **Backup location** documented (committed to git or stored safely)

### ✅ Phase 3: Testing

- [ ] **Migration tested** in development environment first
- [ ] **Row counts verified** before/after match expectations
- [ ] **Application functionality** tested post-migration
- [ ] **Rollback tested** (restore from backup and verify)

### ✅ Phase 4: Review (for DANGER migrations only)

- [ ] **Peer review** obtained (another developer reviews SQL)
- [ ] **Frontend cache implications** considered:
  - Will cache show stale data?
  - Need to invalidate React Query cache?
- [ ] **Scheduled tasks implications** considered:
  - Will Celery tasks fail post-migration?
  - Need to restart services?

### ✅ Phase 5: Execution

- [ ] **Services stopped** (if structural changes):
  ```bash
  bash ~/portfolio-ai/scripts/shutdown.sh
  ```
- [ ] **Migration executed**:
  ```bash
  python backend/scripts/migrate.py --execute --migration <VERSION>
  ```
- [ ] **Success verified**:
  - Migration appears in `schema_migrations` table
  - Expected schema changes present
  - Row counts match expectations
- [ ] **Services restarted**:
  ```bash
  bash ~/portfolio-ai/scripts/start.sh
  ```
- [ ] **Smoke test** passed (basic functionality works)

---

## Safe vs Unsafe Migrations

### 🟢 SAFE Migrations (No Data Loss Risk)

**ADD COLUMN (with default):**
```sql
-- Safe: Adds column, defaults handled by PostgreSQL
ALTER TABLE watchlist_items
ADD COLUMN IF NOT EXISTS new_field TEXT DEFAULT '';
```

**CREATE TABLE:**
```sql
-- Safe: Creates new table, no existing data affected
CREATE TABLE IF NOT EXISTS new_feature (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    data TEXT
);
```

**CREATE INDEX:**
```sql
-- Safe: Improves performance, no data changes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_watchlist_symbol
ON watchlist_items(symbol);
```

**ADD CONSTRAINT (non-destructive):**
```sql
-- Safe: Adds validation for future inserts
ALTER TABLE watchlist_items
ADD CONSTRAINT check_symbol_format CHECK (symbol ~ '^[A-Z]{1,5}$');
```

### 🟡 CAUTION Migrations (Data Modification)

**UPDATE with WHERE clause:**
```sql
-- Caution: Modifies existing data
-- Document expected row count
UPDATE watchlist_items
SET status = 'active'
WHERE status IS NULL;
-- Expected: ~12 rows
```

**ALTER COLUMN (change type with USING):**
```sql
-- Caution: Transforms data
ALTER TABLE watchlist_items
ALTER COLUMN price TYPE NUMERIC(10,2)
USING price::NUMERIC(10,2);
```

**BACKFILL data:**
```sql
-- Caution: Inserts data into existing table
INSERT INTO market_metrics (date, value)
SELECT generate_series('2025-01-01'::date, '2025-12-31'::date, '1 day'), 0
ON CONFLICT DO NOTHING;
```

### 🔴 DANGER Migrations (Destructive)

**DROP TABLE:**
```sql
-- DANGER: Permanently deletes table and all data
-- REQUIRES: Full backup + peer review + production sign-off
DROP TABLE IF EXISTS old_deprecated_table;
```

**DELETE with CASCADE:**
```sql
-- DANGER: Can trigger cascading deletes to child tables
-- Nov 9 incident: DELETE from watchlist_items → nuked 246K snapshots
DELETE FROM watchlist_items WHERE condition;
```

**TRUNCATE:**
```sql
-- DANGER: Deletes all rows, cannot be rolled back in same transaction
TRUNCATE TABLE temp_data;
```

**DROP COLUMN:**
```sql
-- DANGER: Permanently deletes column data
-- NO ROLLBACK once committed
ALTER TABLE watchlist_items DROP COLUMN IF EXISTS old_field;
```

**ALTER FOREIGN KEY (ADD CASCADE):**
```sql
-- DANGER: Changes deletion behavior, can cause unexpected cascades
ALTER TABLE watchlist_snapshots
DROP CONSTRAINT fk_item_id,
ADD CONSTRAINT fk_item_id
    FOREIGN KEY (item_id)
    REFERENCES watchlist_items(id)
    ON DELETE CASCADE;  -- 🔴 CASCADE = DANGER
```

---

## Dry-Run Workflow

### Step 1: Run Dry-Run

```bash
python backend/scripts/migrate.py --dry-run --migration 018
```

**Output shows:**
- ✅ Affected tables
- ✅ Current row counts
- ✅ Operations (DROP, DELETE, etc.)
- ⚠️ CASCADE warnings
- 🔴 Critical table warnings

### Step 2: Analyze Output

**Example dry-run output:**
```
================================================================================
MIGRATION DRY-RUN (No changes will be made)
================================================================================

📋 Found 1 pending migration(s):

────────────────────────────────────────────────────────────────────────────────
Migration 018: remove_legacy_preferences_table
File: 018_remove_legacy_preferences_table.sql
────────────────────────────────────────────────────────────────────────────────

🔍 Impact Analysis:
  Destructive: YES ⚠️
  Has CASCADE: YES ⚠️
  Operations: DROP TABLE
  Affected tables: user_preferences, watchlist_items

📊 Current Row Counts:
    user_preferences: 0 rows
    watchlist_items: 612 rows

⚠️  WARNINGS:
    ⚠️  CASCADE detected - deletions may affect multiple tables
    🔴 CRITICAL: Destructive operation on watchlist_items

📝 SQL Preview (first 20 lines):
    -- Drop legacy user_preferences table
    DROP TABLE IF EXISTS user_preferences CASCADE;
    ...
```

### Step 3: Verify Expectations

**Questions to ask:**
1. ✅ Do row counts match what I expect?
2. ✅ Are all affected tables identified?
3. ✅ Do I understand the CASCADE implications?
4. ✅ Is there a rollback plan?

**RED FLAGS:**
- 🚨 "CRITICAL: Destructive operation on watchlist_items" → STOP, review carefully
- 🚨 Row count: 612 rows → Will this delete production data?
- 🚨 CASCADE detected → Will this trigger child table deletions?

---

## Backup and Rollback

### Automatic Backups

**For destructive migrations**, `migrate.py --execute` automatically creates backups:

```bash
# Execute creates backup before migration
python backend/scripts/migrate.py --execute --migration 018

# Output:
# 📦 Creating backup: backups/pre-migration-018-20251110_143022.sql
# ✅ Backup created: 1,234,567 bytes
```

Backup location: `portfolio-ai/backups/pre-migration-<version>-<timestamp>.sql`

### Manual Backups

**Full database:**
```bash
pg_dump -h localhost -U portfolio_app -d portfolio_ai \
  -f backups/full-backup-$(date +%Y%m%d).sql
```

**Specific tables only:**
```bash
pg_dump -h localhost -U portfolio_app -d portfolio_ai \
  -t watchlist_items -t watchlist_snapshots \
  -f backups/watchlist-backup-$(date +%Y%m%d).sql
```

**Verify backup:**
```bash
# Check file created and has reasonable size
ls -lh backups/*.sql

# Inspect first 50 lines
head -50 backups/pre-migration-018-*.sql
```

### Rollback Procedure

**If migration fails or causes issues:**

```bash
# 1. Stop services immediately
bash ~/portfolio-ai/scripts/shutdown.sh

# 2. Restore from backup
psql -h localhost -U portfolio_app -d portfolio_ai \
  -f backups/pre-migration-018-20251110_143022.sql

# 3. Verify restoration
psql -h localhost -U portfolio_app -d portfolio_ai -c \
  "SELECT COUNT(*) FROM watchlist_items;"

# 4. Remove failed migration from schema_migrations table
psql -h localhost -U portfolio_app -d portfolio_ai -c \
  "DELETE FROM schema_migrations WHERE version = 18;"

# 5. Restart services
bash ~/portfolio-ai/scripts/start.sh

# 6. Verify application functioning
curl http://localhost:8000/api/health
```

### Rollback SQL Template

**Create rollback SQL alongside migration:**

```sql
-- Migration: 018_remove_legacy_preferences_table.sql
-- FORWARD (applied by migration):
DROP TABLE IF EXISTS user_preferences CASCADE;

-- Rollback: 018_remove_legacy_preferences_table_ROLLBACK.sql
-- BACKWARD (apply manually if needed):
CREATE TABLE IF NOT EXISTS user_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    preferences JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Restore data from backup:
-- psql -d portfolio_ai -f backups/pre-migration-018-*.sql
```

---

## CASCADE Analysis

### Understanding CASCADE

**CASCADE effects** propagate deletions/updates to related tables via foreign keys.

**Example from Nov 9 incident:**

```sql
-- Foreign key with CASCADE
ALTER TABLE watchlist_snapshots
ADD CONSTRAINT fk_item_id
    FOREIGN KEY (item_id)
    REFERENCES watchlist_items(id)
    ON DELETE CASCADE;

-- When you delete from watchlist_items...
DELETE FROM watchlist_items WHERE id = 'abc-123';

-- CASCADE automatically deletes from watchlist_snapshots:
-- DELETE FROM watchlist_snapshots WHERE item_id = 'abc-123';
-- (This deleted 246,131 rows in the Nov 9 incident!)
```

### Analyzing CASCADE Chains

**Use EXPLAIN to see CASCADE impact:**

```sql
-- Check what would be deleted (doesn't actually delete)
EXPLAIN (ANALYZE, VERBOSE)
DELETE FROM watchlist_items WHERE symbol = 'TEST';
```

**Query foreign key CASCADE relationships:**

```sql
-- Find all tables that CASCADE from watchlist_items
SELECT
    tc.table_name AS child_table,
    kcu.column_name AS child_column,
    ccu.table_name AS parent_table,
    rc.delete_rule
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
    ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.referential_constraints rc
    ON tc.constraint_name = rc.constraint_name
JOIN information_schema.constraint_column_usage ccu
    ON rc.unique_constraint_name = ccu.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
    AND ccu.table_name = 'watchlist_items'
    AND rc.delete_rule = 'CASCADE';

-- Example output:
-- child_table          | child_column | parent_table    | delete_rule
-- watchlist_snapshots  | item_id      | watchlist_items | CASCADE
```

### Estimating CASCADE Impact

**Before deleting from parent table:**

```sql
-- Count related child records
SELECT
    (SELECT COUNT(*) FROM watchlist_items WHERE condition) AS parent_rows,
    (SELECT COUNT(*) FROM watchlist_snapshots
     WHERE item_id IN (SELECT id FROM watchlist_items WHERE condition)) AS child_rows;

-- Example output:
--  parent_rows | child_rows
--            5 |     12,456  ← 🔴 CASCADE will delete 12K rows!
```

### Safer Alternatives to CASCADE

**Option 1: Soft Delete**
```sql
-- Instead of DELETE, mark as deleted
ALTER TABLE watchlist_items ADD COLUMN deleted_at TIMESTAMPTZ;

UPDATE watchlist_items
SET deleted_at = NOW()
WHERE condition;

-- Query non-deleted:
SELECT * FROM watchlist_items WHERE deleted_at IS NULL;
```

**Option 2: Explicit Deletion**
```sql
-- Delete children first, then parent
BEGIN;

-- 1. Delete child records
DELETE FROM watchlist_snapshots
WHERE item_id IN (SELECT id FROM watchlist_items WHERE condition);

-- 2. Delete parent records
DELETE FROM watchlist_items WHERE condition;

COMMIT;
```

**Option 3: Archive Before Delete**
```sql
-- Move data to archive table before deleting
BEGIN;

-- 1. Archive items
INSERT INTO watchlist_items_archive
SELECT * FROM watchlist_items WHERE condition;

-- 2. Archive snapshots
INSERT INTO watchlist_snapshots_archive
SELECT * FROM watchlist_snapshots
WHERE item_id IN (SELECT id FROM watchlist_items WHERE condition);

-- 3. Now safe to delete (data preserved)
DELETE FROM watchlist_items WHERE condition;

COMMIT;
```

---

## Migration Templates

### Template: Add Column (SAFE)

```sql
-- Migration: 024_add_new_feature_field.sql
-- Type: SAFE
-- Impact: Adds column, no data loss
-- Rollback: See 024_add_new_feature_field_ROLLBACK.sql

-- Add new column with default
ALTER TABLE watchlist_items
ADD COLUMN IF NOT EXISTS new_feature TEXT DEFAULT 'default_value';

-- Add index if needed for queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_watchlist_new_feature
ON watchlist_items(new_feature);

-- Verification query (run post-migration):
-- SELECT COUNT(*) FROM watchlist_items WHERE new_feature IS NOT NULL;
-- Expected: ALL rows (same as total count)
```

**Rollback:**
```sql
-- Rollback: 024_add_new_feature_field_ROLLBACK.sql
ALTER TABLE watchlist_items DROP COLUMN IF EXISTS new_feature;
DROP INDEX IF EXISTS idx_watchlist_new_feature;
```

### Template: Drop Table (DANGER)

```sql
-- Migration: 025_drop_legacy_table.sql
-- Type: DANGER - Destructive
-- Impact: Permanently deletes table
-- Prerequisites:
--   - Table confirmed unused (grep codebase for references)
--   - Data archived or no longer needed
--   - Backup created
-- Rollback: Restore from backup

-- SAFETY CHECK: Verify table empty or has expected row count
DO $$
BEGIN
    IF (SELECT COUNT(*) FROM legacy_table) > 0 THEN
        RAISE EXCEPTION 'legacy_table still has data! Expected 0 rows.';
    END IF;
END $$;

-- Drop table (CASCADE if has foreign keys)
DROP TABLE IF EXISTS legacy_table CASCADE;

-- Verification query (should error - table shouldn't exist):
-- SELECT * FROM legacy_table LIMIT 1;
-- Expected: ERROR:  relation "legacy_table" does not exist
```

**Rollback:**
```sql
-- Rollback: Restore from backup
-- psql -d portfolio_ai -f backups/pre-migration-025-*.sql
```

### Template: Modify Foreign Key (DANGER)

```sql
-- Migration: 026_change_delete_behavior.sql
-- Type: DANGER - Changes CASCADE behavior
-- Impact: Modifies deletion behavior between tables
-- Rollback: See 026_change_delete_behavior_ROLLBACK.sql

BEGIN;

-- Remove existing foreign key
ALTER TABLE watchlist_snapshots
DROP CONSTRAINT IF EXISTS fk_item_id;

-- Add new foreign key with desired behavior
ALTER TABLE watchlist_snapshots
ADD CONSTRAINT fk_item_id
    FOREIGN KEY (item_id)
    REFERENCES watchlist_items(id)
    ON DELETE CASCADE      -- or NO ACTION, RESTRICT, SET NULL
    ON UPDATE CASCADE;

COMMIT;

-- Verification query:
-- SELECT rc.delete_rule, rc.update_rule
-- FROM information_schema.referential_constraints rc
-- WHERE rc.constraint_name = 'fk_item_id';
-- Expected: delete_rule = 'CASCADE', update_rule = 'CASCADE'
```

**Rollback:**
```sql
-- Rollback: 026_change_delete_behavior_ROLLBACK.sql
BEGIN;

ALTER TABLE watchlist_snapshots
DROP CONSTRAINT IF EXISTS fk_item_id;

ALTER TABLE watchlist_snapshots
ADD CONSTRAINT fk_item_id
    FOREIGN KEY (item_id)
    REFERENCES watchlist_items(id)
    ON DELETE NO ACTION;  -- Original behavior

COMMIT;
```

---

## Testing Migrations

### Test in Development First

**Never test migrations directly in production!**

```bash
# 1. Ensure you're in development environment
echo $DATABASE_URL
# Should point to localhost, NOT production

# 2. Create test data that mimics production
psql -d portfolio_ai -c "SELECT COUNT(*) FROM watchlist_items;"

# 3. Run dry-run
python backend/scripts/migrate.py --dry-run --migration 024

# 4. Execute migration
python backend/scripts/migrate.py --execute --migration 024

# 5. Verify results
psql -d portfolio_ai -c "SELECT * FROM watchlist_items LIMIT 5;"

# 6. Test rollback
psql -d portfolio_ai -f backups/pre-migration-024-*.sql
```

### Verify Row Counts

**Before and after migration:**

```bash
# Before migration
psql -d portfolio_ai << EOF
SELECT
    'watchlist_items' AS table_name,
    COUNT(*) AS row_count
FROM watchlist_items
UNION ALL
SELECT
    'watchlist_snapshots',
    COUNT(*)
FROM watchlist_snapshots;
EOF

# Run migration
python backend/scripts/migrate.py --execute --migration 024

# After migration
# (run same query, compare results)
```

### Test Application Functionality

**Post-migration smoke test:**

```bash
# 1. Restart services
bash ~/portfolio-ai/scripts/restart.sh

# 2. Check health endpoint
curl http://localhost:8000/api/health

# 3. Test affected features
curl http://localhost:8000/api/watchlist | jq '.'

# 4. Check logs for errors
tail -50 /var/log/portfolio-ai/backend-error.log
```

---

## Production Deployment

### Pre-Production Checklist

- [ ] Migration tested in development
- [ ] Rollback tested successfully
- [ ] Pre-migration checklist completed
- [ ] Peer review obtained (for DANGER migrations)
- [ ] Deployment window scheduled (off-peak hours)
- [ ] Stakeholders notified (if potential downtime)

### Production Execution Steps

```bash
# 1. Create full database backup
pg_dump -h <prod-host> -U portfolio_app -d portfolio_ai \
  -f backups/prod-full-backup-$(date +%Y%m%d-%H%M%S).sql

# 2. Stop services (if structural changes)
bash ~/portfolio-ai/scripts/shutdown.sh

# 3. Run dry-run one last time
python backend/scripts/migrate.py --dry-run --migration <VERSION>

# 4. Execute migration
python backend/scripts/migrate.py --execute --migration <VERSION>

# 5. Verify success
psql -h <prod-host> -U portfolio_app -d portfolio_ai \
  -c "SELECT version, description, applied_at FROM schema_migrations ORDER BY version DESC LIMIT 5;"

# 6. Restart services
bash ~/portfolio-ai/scripts/start.sh

# 7. Monitor logs for 5 minutes
tail -f /var/log/portfolio-ai/backend-error.log
tail -f /var/log/postgresql/postgresql-*.log

# 8. Smoke test
curl http://localhost:8000/api/health
# Check critical functionality
```

### Post-Production Verification

- [ ] Migration appears in `schema_migrations` table
- [ ] Row counts match expectations
- [ ] Application health check passes
- [ ] No errors in logs (backend + PostgreSQL)
- [ ] Frontend functionality working
- [ ] Backup retained for 30 days

---

## Related Documentation

- [PostgreSQL Logging](../../docs/operations/postgresql-logging.md) - Forensic logging setup
- [OPERATIONS.md](../../docs/core/OPERATIONS.md) - Database backup/restore procedures
- [DEVELOPMENT.md](../../docs/core/DEVELOPMENT.md) - Development workflows

---

## Changelog

- **2025-11-10**: Created migration safety guide (Task 7.2.3)

---

**Last Updated**: 2025-11-10
**Owner**: Development Team
**Review Frequency**: After any migration incident
