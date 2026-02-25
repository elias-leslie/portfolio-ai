-- Migration 116: Thesis System
-- Investment thesis tracking with dual AI validation (Claude + Gemini)
-- Captures core investment rationale, key catalysts, risks, and expected returns
-- Versioned history for tracking thesis evolution and invalidation

-- ============================================
-- 1. Main Thesis Table (1:1 with watchlist_items via symbol)
-- ============================================
CREATE TABLE IF NOT EXISTS watchlist_thesis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol VARCHAR(20) NOT NULL UNIQUE,
    version INTEGER NOT NULL DEFAULT 1,
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'invalidated', 'flagged_for_review')),
    action VARCHAR(10) NOT NULL CHECK (action IN ('BUY', 'HOLD', 'SELL')),

    -- Core investment thesis
    core_reasons JSONB NOT NULL,  -- [{reason: str, confidence: float}]
    key_catalysts JSONB NOT NULL,  -- [{catalyst: str, expected_date: str|null, impact: str}]
    risks JSONB NOT NULL,  -- [{risk: str, severity: "high"|"medium"|"low", mitigation: str|null}]

    -- Value analysis
    value_drivers JSONB,  -- {market_size: str, company_position: str, upside_potential: str, competitive_moat: str}
    expected_return_pct NUMERIC(5,2),
    expected_timeframe_days INTEGER,

    -- AI validation (Claude)
    claude_validation JSONB,  -- {approved: bool, confidence: float, review_summary: str, issues: [str]}

    -- AI validation (Gemini)
    gemini_validation JSONB,  -- {approved: bool, confidence: float, review_summary: str, issues: [str]}

    -- Cross-validation score (0.0 to 1.0 - measures agreement between validators)
    cross_validation_score NUMERIC(3,2) CHECK (cross_validation_score >= 0.0 AND cross_validation_score <= 1.0),

    -- Invalidation tracking
    invalidation_reason TEXT,
    invalidated_at TIMESTAMPTZ,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Foreign key to watchlist_items
    CONSTRAINT fk_watchlist_thesis_symbol
        FOREIGN KEY (symbol) REFERENCES watchlist_items(symbol)
        ON UPDATE CASCADE
        ON DELETE CASCADE
);

-- Indexes for watchlist_thesis
CREATE INDEX IF NOT EXISTS idx_watchlist_thesis_symbol ON watchlist_thesis(symbol);
CREATE INDEX IF NOT EXISTS idx_watchlist_thesis_status ON watchlist_thesis(status);
CREATE INDEX IF NOT EXISTS idx_watchlist_thesis_action ON watchlist_thesis(action);
CREATE INDEX IF NOT EXISTS idx_watchlist_thesis_created_at ON watchlist_thesis(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_watchlist_thesis_cross_validation ON watchlist_thesis(cross_validation_score)
    WHERE cross_validation_score IS NOT NULL;

-- ============================================
-- 2. Thesis Version History (append-only)
-- ============================================
CREATE TABLE IF NOT EXISTS thesis_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thesis_id UUID NOT NULL,
    version INTEGER NOT NULL,
    snapshot JSONB NOT NULL,  -- Full thesis state at that version
    change_reason VARCHAR(50) CHECK (change_reason IN ('created', 'updated', 'invalidated', 'superseded')),
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Foreign key to watchlist_thesis
    CONSTRAINT fk_thesis_versions_thesis_id
        FOREIGN KEY (thesis_id) REFERENCES watchlist_thesis(id)
        ON DELETE CASCADE,

    -- Unique constraint: one record per thesis per version
    CONSTRAINT uq_thesis_versions_thesis_version UNIQUE (thesis_id, version)
);

-- Indexes for thesis_versions
CREATE INDEX IF NOT EXISTS idx_thesis_versions_thesis_id ON thesis_versions(thesis_id, version DESC);
CREATE INDEX IF NOT EXISTS idx_thesis_versions_created_at ON thesis_versions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_thesis_versions_change_reason ON thesis_versions(change_reason);

-- ============================================
-- 3. Auto-update Trigger for updated_at
-- ============================================
CREATE OR REPLACE FUNCTION update_watchlist_thesis_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS watchlist_thesis_updated_at ON watchlist_thesis;
CREATE TRIGGER watchlist_thesis_updated_at
    BEFORE UPDATE ON watchlist_thesis
    FOR EACH ROW
    EXECUTE FUNCTION update_watchlist_thesis_updated_at();

-- ============================================
-- 4. Auto-versioning Trigger
-- ============================================
-- Automatically create version history on thesis creation/update
CREATE OR REPLACE FUNCTION create_thesis_version()
RETURNS TRIGGER AS $$
DECLARE
    change_type VARCHAR(50);
    snapshot_data JSONB;
BEGIN
    -- Determine change reason
    IF TG_OP = 'INSERT' THEN
        change_type := 'created';
    ELSIF NEW.status = 'invalidated' AND OLD.status != 'invalidated' THEN
        change_type := 'invalidated';
    ELSE
        change_type := 'updated';
    END IF;

    -- Build snapshot of current thesis state
    snapshot_data := jsonb_build_object(
        'symbol', NEW.symbol,
        'version', NEW.version,
        'status', NEW.status,
        'action', NEW.action,
        'core_reasons', NEW.core_reasons,
        'key_catalysts', NEW.key_catalysts,
        'risks', NEW.risks,
        'value_drivers', NEW.value_drivers,
        'expected_return_pct', NEW.expected_return_pct,
        'expected_timeframe_days', NEW.expected_timeframe_days,
        'claude_validation', NEW.claude_validation,
        'gemini_validation', NEW.gemini_validation,
        'cross_validation_score', NEW.cross_validation_score,
        'invalidation_reason', NEW.invalidation_reason,
        'invalidated_at', NEW.invalidated_at,
        'created_at', NEW.created_at,
        'updated_at', NEW.updated_at
    );

    -- Insert version history
    INSERT INTO thesis_versions (thesis_id, version, snapshot, change_reason)
    VALUES (NEW.id, NEW.version, snapshot_data, change_type);

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS thesis_versioning ON watchlist_thesis;
CREATE TRIGGER thesis_versioning
    AFTER INSERT OR UPDATE ON watchlist_thesis
    FOR EACH ROW
    EXECUTE FUNCTION create_thesis_version();

-- ============================================
-- 5. Table Comments
-- ============================================
COMMENT ON TABLE watchlist_thesis IS 'Investment theses for watchlist symbols with dual AI validation';
COMMENT ON TABLE thesis_versions IS 'Append-only version history for thesis changes';

COMMENT ON COLUMN watchlist_thesis.core_reasons IS 'Array of {reason: str, confidence: float} - core investment rationale';
COMMENT ON COLUMN watchlist_thesis.key_catalysts IS 'Array of {catalyst: str, expected_date: str|null, impact: str} - catalysts that will drive value';
COMMENT ON COLUMN watchlist_thesis.risks IS 'Array of {risk: str, severity: high|medium|low, mitigation: str|null} - key risks and mitigations';
COMMENT ON COLUMN watchlist_thesis.value_drivers IS 'JSON object describing market_size, company_position, upside_potential, competitive_moat';
COMMENT ON COLUMN watchlist_thesis.claude_validation IS 'Claude AI validation result: {approved: bool, confidence: float, review_summary: str, issues: [str]}';
COMMENT ON COLUMN watchlist_thesis.gemini_validation IS 'Gemini AI validation result: {approved: bool, confidence: float, review_summary: str, issues: [str]}';
COMMENT ON COLUMN watchlist_thesis.cross_validation_score IS 'Agreement score between Claude and Gemini validators (0.0-1.0)';

-- ============================================
-- 6. Migration Log
-- ============================================
DO $$
BEGIN
    RAISE NOTICE 'Migration 116: Created thesis system tables (watchlist_thesis, thesis_versions)';
    RAISE NOTICE '  - watchlist_thesis: Investment theses with dual AI validation';
    RAISE NOTICE '  - thesis_versions: Append-only version history';
    RAISE NOTICE '  - Auto-versioning trigger enabled';
    RAISE NOTICE '  - Foreign key to watchlist_items(symbol) with CASCADE';
END $$;

-- ============================================
-- ROLLBACK INSTRUCTIONS (for emergencies only)
-- ============================================
-- DROP TRIGGER IF EXISTS thesis_versioning ON watchlist_thesis;
-- DROP TRIGGER IF EXISTS watchlist_thesis_updated_at ON watchlist_thesis;
-- DROP FUNCTION IF EXISTS create_thesis_version();
-- DROP FUNCTION IF EXISTS update_watchlist_thesis_updated_at();
-- DROP TABLE IF EXISTS thesis_versions CASCADE;
-- DROP TABLE IF EXISTS watchlist_thesis CASCADE;
