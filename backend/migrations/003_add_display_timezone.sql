-- Migration: 003_add_display_timezone
-- Description: Add display_timezone column to user_preferences for timezone preference

BEGIN TRANSACTION;

-- Add display_timezone column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'user_preferences'
        AND column_name = 'display_timezone'
    ) THEN
        ALTER TABLE user_preferences
        ADD COLUMN display_timezone VARCHAR DEFAULT 'America/New_York';
    END IF;
END $$;

-- Update existing rows
UPDATE user_preferences
SET display_timezone = COALESCE(display_timezone, 'America/New_York');

-- Add CHECK constraint if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'check_display_timezone'
        AND table_name = 'user_preferences'
    ) THEN
        ALTER TABLE user_preferences
        ADD CONSTRAINT check_display_timezone
        CHECK (display_timezone IN (
            'America/New_York',
            'America/Chicago',
            'America/Denver',
            'America/Los_Angeles',
            'America/Anchorage',
            'Pacific/Honolulu'
        ));
    END IF;
END $$;

COMMIT;
