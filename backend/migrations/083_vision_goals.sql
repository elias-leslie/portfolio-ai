-- Migration 083: Create vision_goals lookup table
-- Normalizes vision goal codes to a reference table with descriptions
-- Enables better tracking and UI display of strategic goals

-- Create vision_goals lookup table
CREATE TABLE IF NOT EXISTS vision_goals (
    code TEXT PRIMARY KEY,           -- VG-INTEL, VG-AUTO, etc.
    name TEXT NOT NULL,              -- Human-readable name
    description TEXT,                -- Full description
    category TEXT,                   -- intelligence, automation, portfolio, validation, reliability, ux, quality
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Add comments for documentation
COMMENT ON TABLE vision_goals IS 'Lookup table for VISION.md strategic goals. Linked from feature_capabilities.vision_goals array.';
COMMENT ON COLUMN vision_goals.code IS 'Unique code like VG-INTEL, VG-AUTO. Used in feature_capabilities.vision_goals array.';
COMMENT ON COLUMN vision_goals.name IS 'Human-readable name like "Market Intelligence", "Autonomous Operation".';
COMMENT ON COLUMN vision_goals.description IS 'Full description of what this goal means and why it matters.';
COMMENT ON COLUMN vision_goals.category IS 'Grouping category for organization: intelligence, automation, portfolio, validation, reliability, ux, quality.';

-- Populate with initial values from VISION.md
INSERT INTO vision_goals (code, name, description, category) VALUES
    ('VG-INTEL', 'Market Intelligence', 'AI-driven market insights and analysis. Transform raw market data into actionable insights through signal fusion, confidence scoring, and style classification.', 'intelligence'),
    ('VG-AUTO', 'Autonomous Operation', 'Self-running trading and research agents. Use AI agents as analysts for market discovery, portfolio analysis, and strategy review.', 'automation'),
    ('VG-PORT', 'Portfolio Management', 'Position tracking, analytics, and optimization. Unified monitoring of owned and watched positions with real-time analytics.', 'portfolio'),
    ('VG-VALID', 'Strategy Validation', 'Backtesting, walk-forward analysis, and monte carlo simulation. Never recommend untested strategies.', 'validation'),
    ('VG-RELY', 'System Reliability', 'Monitoring, health checks, and data freshness. Production-grade reliability with zero single points of failure.', 'reliability'),
    ('VG-UX', 'User Experience', 'Professional, responsive, and delightful interface. Real-time updates, visual analytics, and mobile responsive design.', 'ux'),
    ('VG-QUAL', 'Code Quality', 'Testing, documentation, and coding standards. Maintainable, testable, high-quality codebase with comprehensive test coverage.', 'quality')
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    category = EXCLUDED.category,
    updated_at = NOW();

-- Create index for category-based queries
CREATE INDEX IF NOT EXISTS idx_vision_goals_category ON vision_goals(category);
