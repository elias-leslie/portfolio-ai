-- Migration 063: Fix capability_insights duplicate issue
-- The UPSERT was failing because there was no unique constraint

-- Step 1: Delete duplicates, keeping only the most recent (highest ID) for each table_name + insight_type combo
DELETE FROM capability_insights
WHERE id NOT IN (
    SELECT MAX(id)
    FROM capability_insights
    GROUP BY capability_type, table_name, insight_type
);

-- Step 2: Add unique constraint on the correct columns
-- Use table_name instead of capability_id since capability_id changes on rescan
CREATE UNIQUE INDEX IF NOT EXISTS idx_insights_unique_dedup
ON capability_insights (capability_type, table_name, insight_type);

-- Step 3: Also update insights for tables that now have data to "fixed" automatically
-- This catches cases where data was populated but insight wasn't updated
UPDATE capability_insights ci
SET status = 'auto_resolved',
    status_reason = 'Table now has data (detected by migration 063)',
    fixed_at = NOW()
FROM db_capabilities dc
WHERE ci.table_name = dc.table_name
  AND ci.insight_type IN ('missing_data', 'missing_capability')
  AND ci.status = 'pending'
  AND dc.row_count > 0
  AND ci.finding ILIKE '%empty%';
