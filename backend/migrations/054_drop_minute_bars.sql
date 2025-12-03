-- Migration: 054_drop_minute_bars
-- Description: Remove minute_bars table and registry entry
-- Created by: /scrub_it cleanup 2025-12-02
-- Reason: Table was defined in registry but never implemented (0 rows, no ingestion code)

-- Remove from table_registry
DELETE FROM table_registry WHERE table_name = 'minute_bars';

-- Drop the table if it exists
DROP TABLE IF EXISTS minute_bars;

-- Note: db_capabilities cleanup handled automatically by capabilities scan
