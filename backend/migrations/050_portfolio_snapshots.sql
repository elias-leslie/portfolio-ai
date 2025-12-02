-- Migration: 050_portfolio_snapshots
-- Purpose: GAP-023 - Portfolio drawdown tracking with daily snapshots
-- Created: 2025-12-01
--
-- This table stores daily portfolio equity snapshots for drawdown tracking.
-- Enables:
-- - Real-time drawdown calculation from peak
-- - Portfolio-level trading halt at -10% drawdown
-- - Historical equity curve analysis
-- - Underwater days tracking

-- Create portfolio_snapshots table
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id SERIAL PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES portfolio_accounts(id) ON DELETE CASCADE,
    snapshot_date DATE NOT NULL,
    equity DECIMAL(15, 2) NOT NULL,  -- Total portfolio value
    cash DECIMAL(15, 2) NOT NULL DEFAULT 0,  -- Cash portion
    position_value DECIMAL(15, 2) NOT NULL DEFAULT 0,  -- Position portion
    peak_equity DECIMAL(15, 2) NOT NULL,  -- Running peak for drawdown calc
    drawdown_pct DECIMAL(8, 4) NOT NULL DEFAULT 0,  -- Drawdown from peak (positive = down)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Composite unique constraint for upserts
    CONSTRAINT portfolio_snapshots_account_date_unique UNIQUE (account_id, snapshot_date)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_account_date
    ON portfolio_snapshots(account_id, snapshot_date DESC);

CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_drawdown
    ON portfolio_snapshots(account_id, drawdown_pct DESC)
    WHERE drawdown_pct > 0;

-- Index for peak equity queries
CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_equity
    ON portfolio_snapshots(account_id, equity DESC);

-- Add comment for documentation
COMMENT ON TABLE portfolio_snapshots IS 'Daily portfolio equity snapshots for drawdown tracking (GAP-023)';
COMMENT ON COLUMN portfolio_snapshots.drawdown_pct IS 'Drawdown from peak as positive percentage (10.0 = -10% from peak)';
COMMENT ON COLUMN portfolio_snapshots.peak_equity IS 'Running peak equity value for drawdown calculation';
