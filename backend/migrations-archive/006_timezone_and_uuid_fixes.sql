-- Migration 006: Timezone Standardization and UUID-based IDs
-- Description: Convert all timestamp columns to TIMESTAMPTZ (UTC) and migrate
--              watchlist item IDs from timestamp-based to UUID-based format
-- Date: 2025-11-01
-- Related: PRD 0020 Foundational Fixes (FR-1: Timezone, FR-5: UUID IDs)

-- ============================================================================
-- PART 1: TIMEZONE CONVERSION
-- Convert all timestamp columns from TIMESTAMP to TIMESTAMPTZ (UTC-aware)
-- ============================================================================

-- watchlist_snapshots table
DO $$
BEGIN
    -- Check if column needs conversion
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'watchlist_snapshots'
        AND column_name = 'fetched_at'
        AND data_type = 'timestamp without time zone'
    ) THEN
        ALTER TABLE watchlist_snapshots
        ALTER COLUMN fetched_at TYPE TIMESTAMPTZ USING fetched_at AT TIME ZONE 'UTC';
    END IF;
END $$;

-- user_preferences table
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'user_preferences'
        AND column_name = 'created_at'
        AND data_type = 'timestamp without time zone'
    ) THEN
        ALTER TABLE user_preferences
        ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC',
        ALTER COLUMN updated_at TYPE TIMESTAMPTZ USING updated_at AT TIME ZONE 'UTC';
    END IF;
END $$;

-- portfolio_accounts table
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'portfolio_accounts'
        AND column_name = 'created_at'
        AND data_type = 'timestamp without time zone'
    ) THEN
        ALTER TABLE portfolio_accounts
        ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC',
        ALTER COLUMN updated_at TYPE TIMESTAMPTZ USING updated_at AT TIME ZONE 'UTC';
    END IF;
END $$;

-- portfolio_positions table
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'portfolio_positions'
        AND column_name = 'created_at'
        AND data_type = 'timestamp without time zone'
    ) THEN
        ALTER TABLE portfolio_positions
        ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC',
        ALTER COLUMN updated_at TYPE TIMESTAMPTZ USING updated_at AT TIME ZONE 'UTC';
    END IF;
END $$;

-- agent_runs table
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'agent_runs'
        AND column_name = 'created_at'
        AND data_type = 'timestamp without time zone'
    ) THEN
        ALTER TABLE agent_runs
        ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC';
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'agent_runs'
        AND column_name = 'completed_at'
        AND data_type = 'timestamp without time zone'
    ) THEN
        ALTER TABLE agent_runs
        ALTER COLUMN completed_at TYPE TIMESTAMPTZ USING completed_at AT TIME ZONE 'UTC';
    END IF;
END $$;

-- price_cache table
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'price_cache'
        AND column_name = 'cached_at'
        AND data_type = 'timestamp without time zone'
    ) THEN
        ALTER TABLE price_cache
        ALTER COLUMN cached_at TYPE TIMESTAMPTZ USING cached_at AT TIME ZONE 'UTC';
    END IF;
END $$;

-- reference_cache table
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'reference_cache'
        AND column_name = 'cached_at'
        AND data_type = 'timestamp without time zone'
    ) THEN
        ALTER TABLE reference_cache
        ALTER COLUMN cached_at TYPE TIMESTAMPTZ USING cached_at AT TIME ZONE 'UTC';
    END IF;
END $$;

-- paper_trades table
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'paper_trades'
        AND column_name = 'executed_at'
        AND data_type = 'timestamp without time zone'
    ) THEN
        ALTER TABLE paper_trades
        ALTER COLUMN executed_at TYPE TIMESTAMPTZ USING executed_at AT TIME ZONE 'UTC';
    END IF;
END $$;

-- agent_ideas table
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'agent_ideas'
        AND column_name = 'created_at'
        AND data_type = 'timestamp without time zone'
    ) THEN
        ALTER TABLE agent_ideas
        ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC',
        ALTER COLUMN updated_at TYPE TIMESTAMPTZ USING updated_at AT TIME ZONE 'UTC';
    END IF;
END $$;

-- ============================================================================
-- PART 2: UUID MIGRATION FOR WATCHLIST ITEMS
-- Migrate existing timestamp-based IDs to UUID format
-- ============================================================================

-- NOTE: This section only runs if there are existing watchlist items with
-- timestamp-based IDs (numeric strings like "1730482091123456")
-- New items created after the code fix already use UUIDs

DO $$
DECLARE
    timestamp_id_count INTEGER;
BEGIN
    -- Check if there are any timestamp-based IDs (all numeric)
    SELECT COUNT(*)
    INTO timestamp_id_count
    FROM watchlist_items
    WHERE id ~ '^[0-9]+$';

    -- Only proceed if timestamp-based IDs exist
    IF timestamp_id_count > 0 THEN
        RAISE NOTICE 'Found % watchlist items with timestamp-based IDs, migrating to UUIDs...', timestamp_id_count;

        -- Create temporary mapping table
        CREATE TEMP TABLE IF NOT EXISTS watchlist_id_mapping (
            old_id TEXT PRIMARY KEY,
            new_id UUID
        );

        -- Generate new UUIDs for existing items
        INSERT INTO watchlist_id_mapping (old_id, new_id)
        SELECT id, gen_random_uuid()
        FROM watchlist_items
        WHERE id ~ '^[0-9]+$'
        ON CONFLICT (old_id) DO NOTHING;

        -- Update watchlist_snapshots to reference new UUIDs
        UPDATE watchlist_snapshots ws
        SET item_id = wim.new_id::TEXT
        FROM watchlist_id_mapping wim
        WHERE ws.item_id = wim.old_id;

        -- Update watchlist_items to use new UUIDs
        UPDATE watchlist_items wi
        SET id = wim.new_id::TEXT
        FROM watchlist_id_mapping wim
        WHERE wi.id = wim.old_id;

        -- Drop temporary mapping table
        DROP TABLE IF EXISTS watchlist_id_mapping;

        RAISE NOTICE 'Successfully migrated % watchlist items to UUID-based IDs', timestamp_id_count;
    ELSE
        RAISE NOTICE 'No timestamp-based IDs found, skipping UUID migration';
    END IF;
END $$;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

-- Verify timezone conversions
DO $$
DECLARE
    naive_count INTEGER := 0;
    rec RECORD;
BEGIN
    -- Check for remaining naive timestamps
    SELECT COUNT(*)
    INTO naive_count
    FROM information_schema.columns
    WHERE table_schema = 'public'
    AND data_type = 'timestamp without time zone'
    AND column_name IN ('created_at', 'updated_at', 'fetched_at', 'cached_at', 'executed_at', 'completed_at');

    IF naive_count > 0 THEN
        RAISE WARNING '% timestamp columns are still naive (not TIMESTAMPTZ)', naive_count;
        FOR rec IN
            SELECT c.table_name, c.column_name
            FROM information_schema.columns c
            WHERE c.table_schema = 'public'
            AND c.data_type = 'timestamp without time zone'
            AND c.column_name IN ('created_at', 'updated_at', 'fetched_at', 'cached_at', 'executed_at', 'completed_at')
        LOOP
            RAISE WARNING 'Naive timestamp: %.%', rec.table_name, rec.column_name;
        END LOOP;
    ELSE
        RAISE NOTICE 'All timestamp columns successfully converted to TIMESTAMPTZ';
    END IF;
END $$;

-- Verify UUID migration
DO $$
DECLARE
    uuid_count INTEGER;
    timestamp_id_count INTEGER;
BEGIN
    SELECT COUNT(*)
    INTO uuid_count
    FROM watchlist_items
    WHERE id ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$';

    SELECT COUNT(*)
    INTO timestamp_id_count
    FROM watchlist_items
    WHERE id ~ '^[0-9]+$';

    RAISE NOTICE 'Watchlist items with UUID IDs: %', uuid_count;
    RAISE NOTICE 'Watchlist items with timestamp IDs: %', timestamp_id_count;

    IF timestamp_id_count > 0 THEN
        RAISE WARNING 'Still have % watchlist items with timestamp-based IDs', timestamp_id_count;
    END IF;
END $$;
