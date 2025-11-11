-- Migration: Settings Profiles
-- Description: Add support for saving, loading, and managing multiple settings profiles
-- Created: 2025-11-10

-- Settings Profiles Table
CREATE TABLE IF NOT EXISTS settings_profiles (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL DEFAULT 1,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT FALSE,

    -- Snapshot of preferences at time of save
    profile_data JSONB NOT NULL,

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT unique_profile_name_per_user UNIQUE(user_id, name),
    CONSTRAINT valid_profile_name CHECK (LENGTH(name) > 0 AND LENGTH(name) <= 255)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_settings_profiles_user_id ON settings_profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_settings_profiles_active ON settings_profiles(user_id, is_active) WHERE is_active = TRUE;

-- Trigger to ensure only one active profile per user
CREATE OR REPLACE FUNCTION ensure_single_active_profile()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.is_active = TRUE THEN
        -- Deactivate all other profiles for this user
        UPDATE settings_profiles
        SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
        WHERE user_id = NEW.user_id AND id != NEW.id AND is_active = TRUE;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_ensure_single_active_profile
    BEFORE INSERT OR UPDATE ON settings_profiles
    FOR EACH ROW
    WHEN (NEW.is_active = TRUE)
    EXECUTE FUNCTION ensure_single_active_profile();

-- Updated timestamp trigger function
CREATE OR REPLACE FUNCTION update_settings_profiles_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Updated timestamp trigger
CREATE TRIGGER update_settings_profiles_updated_at
    BEFORE UPDATE ON settings_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_settings_profiles_updated_at();

COMMENT ON TABLE settings_profiles IS 'Saved settings profiles for different trading strategies';
COMMENT ON COLUMN settings_profiles.profile_data IS 'Complete snapshot of user preferences as JSON';
COMMENT ON COLUMN settings_profiles.is_active IS 'Only one profile can be active per user at a time';
