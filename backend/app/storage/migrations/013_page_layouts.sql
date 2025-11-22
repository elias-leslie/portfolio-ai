-- Migration 013: Customizable Page Layouts
-- Purpose: Store user-customizable dashboard layouts
-- Created: 2025-11-22

CREATE TABLE IF NOT EXISTS page_layouts (
    id TEXT PRIMARY KEY,
    page_name VARCHAR(50) NOT NULL UNIQUE,
    layout_config JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Index for fast page lookups
CREATE INDEX IF NOT EXISTS idx_page_layouts_page ON page_layouts(page_name);

-- Add to table registry
INSERT INTO table_registry (table_name, description)
VALUES (
    'page_layouts',
    'Customizable dashboard layouts (drag/drop/resize)'
)
ON CONFLICT (table_name) DO NOTHING;
