-- Migration 104: Slippage Tracking for Paper Trading
-- Description: Add columns to track expected vs actual fill prices for slippage analysis
-- Date: 2025-12-10
-- Implements: FEAT-210 (Slippage Tracking)

-- ============================================================================
-- PART 1: Add Slippage Columns to paper_trade_transactions
-- ============================================================================

DO $$
BEGIN
    -- Add expected_price column (the price at order time before slippage)
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'paper_trade_transactions'
        AND column_name = 'expected_price'
    ) THEN
        ALTER TABLE paper_trade_transactions
        ADD COLUMN expected_price DOUBLE PRECISION;

        RAISE NOTICE 'Added expected_price column to paper_trade_transactions';
    END IF;

    -- Add slippage_amount column (actual - expected) * shares
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'paper_trade_transactions'
        AND column_name = 'slippage_amount'
    ) THEN
        ALTER TABLE paper_trade_transactions
        ADD COLUMN slippage_amount DOUBLE PRECISION DEFAULT 0.0;

        RAISE NOTICE 'Added slippage_amount column to paper_trade_transactions';
    END IF;

    -- Add slippage_bps column (slippage in basis points)
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'paper_trade_transactions'
        AND column_name = 'slippage_bps'
    ) THEN
        ALTER TABLE paper_trade_transactions
        ADD COLUMN slippage_bps DOUBLE PRECISION DEFAULT 0.0;

        RAISE NOTICE 'Added slippage_bps column to paper_trade_transactions';
    END IF;

    -- Add adv column (Average Daily Volume at time of trade for context)
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'paper_trade_transactions'
        AND column_name = 'adv'
    ) THEN
        ALTER TABLE paper_trade_transactions
        ADD COLUMN adv DOUBLE PRECISION;

        RAISE NOTICE 'Added adv column to paper_trade_transactions';
    END IF;

    -- Add slippage_model column (NONE, FIXED_PCT, DYNAMIC)
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'paper_trade_transactions'
        AND column_name = 'slippage_model'
    ) THEN
        ALTER TABLE paper_trade_transactions
        ADD COLUMN slippage_model TEXT DEFAULT 'NONE';

        RAISE NOTICE 'Added slippage_model column to paper_trade_transactions';
    END IF;
END $$;

-- ============================================================================
-- PART 2: Rename ticker to symbol (if not already migrated)
-- ============================================================================

DO $$
BEGIN
    -- Check if we need to rename ticker to symbol
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'paper_trade_transactions'
        AND column_name = 'ticker'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'paper_trade_transactions'
        AND column_name = 'symbol'
    ) THEN
        -- Rename the column
        ALTER TABLE paper_trade_transactions
        RENAME COLUMN ticker TO symbol;

        -- Rename the index
        ALTER INDEX IF EXISTS idx_paper_trade_transactions_ticker
        RENAME TO idx_paper_trade_transactions_symbol;

        RAISE NOTICE 'Renamed ticker to symbol in paper_trade_transactions';
    END IF;
END $$;

-- ============================================================================
-- PART 3: Add agent_run_id column for P3 audit trail
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'paper_trade_transactions'
        AND column_name = 'agent_run_id'
    ) THEN
        ALTER TABLE paper_trade_transactions
        ADD COLUMN agent_run_id TEXT;

        RAISE NOTICE 'Added agent_run_id column to paper_trade_transactions';
    END IF;
END $$;

-- ============================================================================
-- PART 4: Create View for Slippage Analysis
-- ============================================================================

CREATE OR REPLACE VIEW v_slippage_analysis AS
SELECT
    symbol,
    transaction_type,
    COUNT(*) as trade_count,
    AVG(slippage_bps) as avg_slippage_bps,
    MAX(slippage_bps) as max_slippage_bps,
    MIN(slippage_bps) as min_slippage_bps,
    SUM(slippage_amount) as total_slippage_cost,
    AVG(CASE WHEN adv > 0 THEN (shares::DOUBLE PRECISION / adv) * 100 ELSE NULL END) as avg_pct_of_adv
FROM paper_trade_transactions
WHERE slippage_bps IS NOT NULL
GROUP BY symbol, transaction_type;

-- ============================================================================
-- PART 5: Aggregate Slippage Stats (simplified without strategy_name)
-- ============================================================================

-- Note: agent_runs table doesn't have strategy_name column
-- Aggregate by agent_run_id presence (agent vs manual trades)
CREATE OR REPLACE VIEW v_slippage_by_source AS
SELECT
    CASE WHEN ptt.agent_run_id IS NOT NULL THEN 'Agent' ELSE 'Manual' END as trade_source,
    COUNT(DISTINCT ptt.trade_id) as trade_count,
    AVG(ptt.slippage_bps) as avg_slippage_bps,
    SUM(ptt.slippage_amount) as total_slippage_cost,
    SUM(CASE WHEN ptt.transaction_type = 'ENTRY' THEN ptt.slippage_amount ELSE 0 END) as entry_slippage_cost,
    SUM(CASE WHEN ptt.transaction_type = 'EXIT' THEN ptt.slippage_amount ELSE 0 END) as exit_slippage_cost
FROM paper_trade_transactions ptt
GROUP BY CASE WHEN ptt.agent_run_id IS NOT NULL THEN 'Agent' ELSE 'Manual' END;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
DECLARE
    has_expected_price BOOLEAN;
    has_slippage_amount BOOLEAN;
    has_slippage_bps BOOLEAN;
    has_adv BOOLEAN;
    has_slippage_model BOOLEAN;
    has_symbol BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'paper_trade_transactions' AND column_name = 'expected_price'
    ) INTO has_expected_price;

    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'paper_trade_transactions' AND column_name = 'slippage_amount'
    ) INTO has_slippage_amount;

    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'paper_trade_transactions' AND column_name = 'slippage_bps'
    ) INTO has_slippage_bps;

    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'paper_trade_transactions' AND column_name = 'adv'
    ) INTO has_adv;

    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'paper_trade_transactions' AND column_name = 'slippage_model'
    ) INTO has_slippage_model;

    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'paper_trade_transactions' AND column_name = 'symbol'
    ) INTO has_symbol;

    RAISE NOTICE '=== Migration 104 Verification ===';
    RAISE NOTICE 'expected_price column: %', has_expected_price;
    RAISE NOTICE 'slippage_amount column: %', has_slippage_amount;
    RAISE NOTICE 'slippage_bps column: %', has_slippage_bps;
    RAISE NOTICE 'adv column: %', has_adv;
    RAISE NOTICE 'slippage_model column: %', has_slippage_model;
    RAISE NOTICE 'symbol column (renamed from ticker): %', has_symbol;

    IF has_expected_price AND has_slippage_amount AND has_slippage_bps
       AND has_adv AND has_slippage_model AND has_symbol THEN
        RAISE NOTICE '✓ Migration 104 completed successfully';
    ELSE
        RAISE WARNING '✗ Migration 104 incomplete - check errors above';
    END IF;
END $$;
