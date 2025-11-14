-- Migration 040: Trading Intelligence Gap Tracking
-- Created: 2025-11-13
-- Purpose: Add tables to track trading intelligence gaps and their resolution

-- ========================================================================
-- trading_gaps: Identified gaps preventing profitable trading edge
-- ========================================================================
CREATE TABLE IF NOT EXISTS trading_gaps (
    gap_id TEXT PRIMARY KEY,  -- e.g., "GAP-001", "GAP-012" (from gap_definition.md)
    capability TEXT NOT NULL,  -- e.g., "multi_horizon_momentum", "earnings_surprises"
    analysis_type TEXT NOT NULL,  -- e.g., "technical_analysis", "fundamental_analysis"
    criticality TEXT NOT NULL CHECK (criticality IN ('P0', 'P1', 'P2', 'P3')),
    severity TEXT NOT NULL CHECK (severity IN ('blocking', 'limiting', 'optional')),
    current_state TEXT NOT NULL,  -- What we have now
    desired_state TEXT NOT NULL,  -- What we need
    impact TEXT NOT NULL,  -- Why this matters (trading edge impact)
    data_sources JSONB,  -- Array of data sources (internal, polygon, fmp, etc.)
    effort TEXT CHECK (effort IN ('LOW', 'MEDIUM', 'HIGH')),
    blocks_strategies JSONB,  -- Array of strategies blocked by this gap
    recommendation TEXT NOT NULL,  -- Actionable step to fill gap
    detected_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    resolved_at TIMESTAMPTZ,  -- When gap was filled (NULL = still open)
    resolution_notes TEXT  -- How gap was filled
);

CREATE INDEX IF NOT EXISTS idx_trading_gaps_analysis_type ON trading_gaps(analysis_type);
CREATE INDEX IF NOT EXISTS idx_trading_gaps_criticality ON trading_gaps(criticality);
CREATE INDEX IF NOT EXISTS idx_trading_gaps_severity ON trading_gaps(severity);
CREATE INDEX IF NOT EXISTS idx_trading_gaps_resolved ON trading_gaps(resolved_at) WHERE resolved_at IS NULL;  -- Active gaps

COMMENT ON TABLE trading_gaps IS 'Identified gaps preventing profitable trading edge (source: gap_definition.md)';
COMMENT ON COLUMN trading_gaps.gap_id IS 'Unique gap identifier (GAP-001 through GAP-053)';
COMMENT ON COLUMN trading_gaps.criticality IS 'P0=Critical (blocking), P1=High (limiting), P2=Medium, P3=Low';
COMMENT ON COLUMN trading_gaps.severity IS 'blocking=Cannot trade, limiting=Reduced edge, optional=Nice to have';
COMMENT ON COLUMN trading_gaps.data_sources IS 'JSON array of data sources: [{internal: day_bars}, {polygon: 1-min bars}]';
COMMENT ON COLUMN trading_gaps.blocks_strategies IS 'JSON array of strategies: ["Momentum Trading", "Day Trading", etc.]';

-- ========================================================================
-- gap_resolutions: Track task lists and implementation progress per gap
-- ========================================================================
CREATE TABLE IF NOT EXISTS gap_resolutions (
    resolution_id SERIAL PRIMARY KEY,
    gap_id TEXT NOT NULL REFERENCES trading_gaps(gap_id) ON DELETE CASCADE,
    task_file TEXT,  -- e.g., "tasks-0064-intraday-data-ingestion.md"
    status TEXT NOT NULL CHECK (status IN ('planned', 'in_progress', 'completed', 'deferred')) DEFAULT 'planned',
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    notes TEXT,  -- Implementation notes, blockers, etc.
    created_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC')
);

CREATE INDEX IF NOT EXISTS idx_gap_resolutions_gap_id ON gap_resolutions(gap_id);
CREATE INDEX IF NOT EXISTS idx_gap_resolutions_status ON gap_resolutions(status);
CREATE INDEX IF NOT EXISTS idx_gap_resolutions_task_file ON gap_resolutions(task_file);

COMMENT ON TABLE gap_resolutions IS 'Track task lists and implementation progress for filling gaps';
COMMENT ON COLUMN gap_resolutions.task_file IS 'Task list file generated to fill this gap';
COMMENT ON COLUMN gap_resolutions.status IS 'planned → in_progress → completed OR deferred';

-- ========================================================================
-- gap_analysis_history: Snapshot gap analysis results over time
-- ========================================================================
CREATE TABLE IF NOT EXISTS gap_analysis_history (
    analysis_id SERIAL PRIMARY KEY,
    analysis_timestamp TIMESTAMPTZ NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    total_gaps INT NOT NULL,
    p0_gaps INT NOT NULL,
    p1_gaps INT NOT NULL,
    p2_gaps INT NOT NULL,
    p3_gaps INT NOT NULL,
    avg_coverage_pct NUMERIC(5, 2),  -- Average coverage across all analysis types
    analysis_results JSONB NOT NULL,  -- Full GapAnalysisResult from gap_detector.analyze_gaps()
    created_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC')
);

CREATE INDEX IF NOT EXISTS idx_gap_analysis_history_timestamp ON gap_analysis_history(analysis_timestamp DESC);

COMMENT ON TABLE gap_analysis_history IS 'Historical snapshots of gap analysis (trending over time)';
COMMENT ON COLUMN gap_analysis_history.analysis_results IS 'Full JSON result from gap_detector.analyze_gaps()';
COMMENT ON COLUMN gap_analysis_history.avg_coverage_pct IS 'Average coverage % across all analysis types (0-100)';

-- ========================================================================
-- watchlist_gap_coverage: Per-ticker gap coverage for watchlist
-- ========================================================================
CREATE TABLE IF NOT EXISTS watchlist_gap_coverage (
    ticker TEXT NOT NULL,
    analysis_type TEXT NOT NULL,
    coverage_pct NUMERIC(5, 2),  -- 0-100
    missing_capabilities JSONB,  -- Array of capability names missing for this ticker
    updated_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    PRIMARY KEY (ticker, analysis_type)
);

CREATE INDEX IF NOT EXISTS idx_watchlist_gap_coverage_ticker ON watchlist_gap_coverage(ticker);
CREATE INDEX IF NOT EXISTS idx_watchlist_gap_coverage_analysis_type ON watchlist_gap_coverage(analysis_type);
CREATE INDEX IF NOT EXISTS idx_watchlist_gap_coverage_pct ON watchlist_gap_coverage(coverage_pct);

COMMENT ON TABLE watchlist_gap_coverage IS 'Per-ticker gap coverage (e.g., NVDA has 85% technical coverage but 45% fundamental coverage)';
COMMENT ON COLUMN watchlist_gap_coverage.missing_capabilities IS 'JSON array: ["earnings_surprises", "insider_trading", etc.]';

-- ========================================================================
-- Update triggers for updated_at timestamps
-- ========================================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
   NEW.updated_at = NOW() AT TIME ZONE 'UTC';
   RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_trading_gaps_updated_at ON trading_gaps;
CREATE TRIGGER update_trading_gaps_updated_at BEFORE UPDATE ON trading_gaps
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_gap_resolutions_updated_at ON gap_resolutions;
CREATE TRIGGER update_gap_resolutions_updated_at BEFORE UPDATE ON gap_resolutions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_watchlist_gap_coverage_updated_at ON watchlist_gap_coverage;
CREATE TRIGGER update_watchlist_gap_coverage_updated_at BEFORE UPDATE ON watchlist_gap_coverage
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
