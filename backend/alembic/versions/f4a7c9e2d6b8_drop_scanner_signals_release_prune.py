"""drop scanner signals release prune

Revision ID: f4a7c9e2d6b8
Revises: e6b4c2a9d8f1
Create Date: 2026-06-04 12:00:00.000000

Prune the no-longer-shipping scanner/signals subsystem. Fanout committee
runs are deleted first while their ``source`` tag still exists; the
remaining DDL then removes the redundant scanner state so manual
committee runs and current quote/portfolio data stay canonical.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "f4a7c9e2d6b8"
down_revision: str | Sequence[str] | None = "e6b4c2a9d8f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'committee_runs'
                  AND column_name = 'source'
            ) THEN
                DELETE FROM committee_runs WHERE source = 'scanner_fanout';
            END IF;
        END $$;
        """
    )

    op.execute("DROP INDEX IF EXISTS idx_candidate_fundamentals_symbol_fetched")
    op.execute("DROP TABLE IF EXISTS candidate_fundamentals_snapshots")

    op.execute("DROP INDEX IF EXISTS ix_signal_scanner_scores_rank")
    op.execute("DROP INDEX IF EXISTS ix_signal_scanner_scores_symbol")
    op.execute("DROP TABLE IF EXISTS signal_scanner_scores")
    op.execute("DROP INDEX IF EXISTS ix_signal_scanner_runs_date")
    op.execute("DROP TABLE IF EXISTS signal_scanner_runs")

    op.execute("DROP INDEX IF EXISTS idx_committee_runs_source_started")
    op.execute(
        """
        ALTER TABLE IF EXISTS committee_runs
            DROP COLUMN IF EXISTS blended_rank,
            DROP COLUMN IF EXISTS scanner_rank,
            DROP COLUMN IF EXISTS source
        """
    )
    op.execute(
        """
        ALTER TABLE IF EXISTS automation_preferences
            DROP COLUMN IF EXISTS scanner_fanout_cache_ttl_hours,
            DROP COLUMN IF EXISTS scanner_fanout_max_daily,
            DROP COLUMN IF EXISTS scanner_fanout_tier1_keep,
            DROP COLUMN IF EXISTS scanner_fanout_top_n,
            DROP COLUMN IF EXISTS scanner_fanout_enabled
        """
    )


def downgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS signal_scanner_runs (
            run_id UUID PRIMARY KEY,
            run_date DATE NOT NULL,
            gate_zone VARCHAR(16) NOT NULL,
            gate_score NUMERIC(6, 2),
            universe_size INTEGER NOT NULL DEFAULT 0,
            scored_count INTEGER NOT NULL DEFAULT 0,
            skip_reason VARCHAR(64),
            started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            completed_at TIMESTAMPTZ,
            CONSTRAINT signal_scanner_runs_zone_check
                CHECK (gate_zone IN ('FULL_DEPLOY', 'REDUCED', 'DEFENSIVE'))
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_signal_scanner_runs_date
            ON signal_scanner_runs (run_date)
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS signal_scanner_scores (
            run_id UUID NOT NULL REFERENCES signal_scanner_runs(run_id) ON DELETE CASCADE,
            symbol VARCHAR(16) NOT NULL,
            mom_xover NUMERIC(12, 6),
            vol_surge NUMERIC(12, 6),
            rs_vs_spy NUMERIC(12, 6),
            high_52w_proximity NUMERIC(12, 6),
            short_interest_decline NUMERIC(12, 6),
            mom_xover_pct NUMERIC(6, 2),
            vol_surge_pct NUMERIC(6, 2),
            rs_vs_spy_pct NUMERIC(6, 2),
            high_52w_proximity_pct NUMERIC(6, 2),
            short_interest_decline_pct NUMERIC(6, 2),
            composite_pct NUMERIC(6, 2) NOT NULL,
            rank INTEGER NOT NULL,
            factor_coverage NUMERIC(4, 2) NOT NULL,
            PRIMARY KEY (run_id, symbol)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_signal_scanner_scores_symbol
            ON signal_scanner_scores (symbol, run_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_signal_scanner_scores_rank
            ON signal_scanner_scores (run_id, rank)
        """
    )

    op.execute(
        """
        ALTER TABLE IF EXISTS committee_runs
            ADD COLUMN IF NOT EXISTS source VARCHAR(32),
            ADD COLUMN IF NOT EXISTS scanner_rank INTEGER,
            ADD COLUMN IF NOT EXISTS blended_rank NUMERIC(5, 2)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_committee_runs_source_started
            ON committee_runs (source, started_at DESC)
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS candidate_fundamentals_snapshots (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            symbol VARCHAR(16) NOT NULL,
            fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            source_run_id UUID,
            payload JSONB NOT NULL,
            yfinance_ok BOOLEAN NOT NULL DEFAULT true,
            error TEXT
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_candidate_fundamentals_symbol_fetched
            ON candidate_fundamentals_snapshots (symbol, fetched_at DESC)
        """
    )

    op.execute(
        """
        ALTER TABLE IF EXISTS automation_preferences
            ADD COLUMN IF NOT EXISTS scanner_fanout_enabled BOOLEAN,
            ADD COLUMN IF NOT EXISTS scanner_fanout_top_n INTEGER,
            ADD COLUMN IF NOT EXISTS scanner_fanout_tier1_keep INTEGER,
            ADD COLUMN IF NOT EXISTS scanner_fanout_max_daily INTEGER,
            ADD COLUMN IF NOT EXISTS scanner_fanout_cache_ttl_hours INTEGER
        """
    )
