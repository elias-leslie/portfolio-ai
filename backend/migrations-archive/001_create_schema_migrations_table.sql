-- Migration: 001_create_schema_migrations_table
-- Description: Create schema_migrations table for tracking applied migrations
-- This migration is idempotent and safe to run multiple times

CREATE TABLE IF NOT EXISTS schema_migrations (
    version         INTEGER PRIMARY KEY,
    description     TEXT NOT NULL,
    applied_at      TIMESTAMP NOT NULL,
    checksum        TEXT NOT NULL
);
