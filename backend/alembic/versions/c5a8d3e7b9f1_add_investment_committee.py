"""add investment committee tables + sector_targets

Revision ID: c5a8d3e7b9f1
Revises: c2512b1d46b7
Create Date: 2026-05-11 23:40:00.000000

Foundation for the Investment Committee feature described in
plans/sunny-puzzling-sprout.md. The tables back the multi-agent
`/portfolio/committee` page: a run record + append-only event log +
evidence ledger + user-input log + paper-trade tracker, plus a
configurable sector cap table that replaces the hardcoded 20%
fallback in `RiskManagementRules.max_sector_exposure_pct`.

Tables:
- committee_runs: one row per Trading Floor run. Stores the final
  decision, debate scores, and KPI totals. `parent_run_id` links a
  retro review back to the original run.
- committee_events: append-only SSE log. (run_id, seq) is unique so
  the stream replay endpoint can resume cleanly. `content` is a
  JSONB blob per event type (schema in the plan).
- committee_evidence: claim ledger collected across the run, side
  ∈ {bull,bear,neutral}. `event_id` links the claim to the event
  that produced it.
- committee_inputs: user feedback messages, one row per chat send,
  with `round` monotonic per run. `decision_shifted` is filled when
  the feedback round resolves.
- paper_trades: one tracked paper trade per approved run. The nightly
  Hatchet workflow updates `current_pnl` / `current_price` /
  `last_pnl_at` for open rows.
- sector_targets: configurable sector caps. `household_id IS NULL`
  rows are global defaults; per-household rows override. Seeded
  here with the defaults from the plan.

`household_id` is `String(64)` to match `retirement_scenarios`,
`portfolio_accounts`, and the rest of the household-scoped tables
in this codebase (no `households` FK target exists today).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c5a8d3e7b9f1"
down_revision: str | Sequence[str] | None = "c2512b1d46b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_GLOBAL_SECTOR_DEFAULTS: tuple[tuple[str, float], ...] = (
    ("Technology", 0.35),
    ("Finance", 0.25),
    ("Healthcare", 0.25),
    ("Industrials", 0.20),
    ("Energy", 0.15),
    ("Consumer Discretionary", 0.20),
    ("Consumer Staples", 0.20),
    ("Utilities", 0.15),
    ("Real Estate", 0.15),
    ("Materials", 0.15),
    ("Communication Services", 0.25),
    ("default", 0.20),
)


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "committee_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("household_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("decision_action", sa.String(length=8), nullable=True),
        sa.Column("decision_qty", sa.Numeric(18, 6), nullable=True),
        sa.Column("decision_pct_portfolio", sa.Numeric(8, 6), nullable=True),
        sa.Column("decision_price", sa.Numeric(18, 6), nullable=True),
        sa.Column("decision_horizon", sa.String(length=32), nullable=True),
        sa.Column("confidence", sa.Numeric(6, 4), nullable=True),
        sa.Column("bull_score", sa.Numeric(6, 4), nullable=True),
        sa.Column("bear_score", sa.Numeric(6, 4), nullable=True),
        sa.Column(
            "parent_run_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "graph_version",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'committee.v0.3.1'"),
        ),
        sa.Column("hatchet_workflow_run_id", sa.Text(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("aborted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "tokens_total",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "cost_usd",
            sa.Numeric(18, 6),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.ForeignKeyConstraint(
            ["parent_run_id"],
            ["committee_runs.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('pending','running','complete','approved','aborted','failed')",
            name="ck_committee_runs_status",
        ),
        sa.CheckConstraint(
            "decision_action IS NULL "
            "OR decision_action IN ('buy','sell','trim','add','hold')",
            name="ck_committee_runs_decision_action",
        ),
    )
    op.create_index(
        "idx_committee_runs_symbol_started",
        "committee_runs",
        ["symbol", sa.text("started_at DESC")],
    )
    op.create_index(
        "idx_committee_runs_household_started",
        "committee_runs",
        ["household_id", sa.text("started_at DESC")],
    )
    op.create_index(
        "idx_committee_runs_parent",
        "committee_runs",
        ["parent_run_id"],
    )

    op.create_table(
        "committee_events",
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(always=False),
            nullable=False,
        ),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column(
            "ts",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("stage", sa.String(length=32), nullable=True),
        sa.Column("agent_slug", sa.String(length=64), nullable=True),
        sa.Column("role", sa.String(length=32), nullable=True),
        sa.Column(
            "content",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("score", sa.Numeric(6, 4), nullable=True),
        sa.Column("tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["committee_runs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "seq", name="uq_committee_events_run_seq"),
    )
    op.create_index(
        "idx_committee_events_run_seq",
        "committee_events",
        ["run_id", "seq"],
    )

    op.create_table(
        "committee_evidence",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("claim", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column(
            "weight",
            sa.Numeric(6, 4),
            nullable=False,
            server_default=sa.text("1.0"),
        ),
        sa.Column("event_id", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["committee_runs.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["committee_events.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "side IN ('bull','bear','neutral')",
            name="ck_committee_evidence_side",
        ),
    )
    op.create_index(
        "idx_committee_evidence_run",
        "committee_evidence",
        ["run_id"],
    )

    op.create_table(
        "committee_inputs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("round", sa.Integer(), nullable=False),
        sa.Column("user_input", sa.Text(), nullable=False),
        sa.Column("triggered_event_id", sa.BigInteger(), nullable=True),
        sa.Column("decision_shifted", sa.Boolean(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["committee_runs.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["triggered_event_id"],
            ["committee_events.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_committee_inputs_run_round",
        "committee_inputs",
        ["run_id", "round"],
    )

    op.create_table(
        "paper_trades",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("household_id", sa.String(length=64), nullable=True),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("action", sa.String(length=8), nullable=False),
        sa.Column("qty", sa.Numeric(18, 6), nullable=False),
        sa.Column("price", sa.Numeric(18, 6), nullable=False),
        sa.Column(
            "executed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("tracked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_pnl", sa.Numeric(18, 4), nullable=True),
        sa.Column("current_price", sa.Numeric(18, 6), nullable=True),
        sa.Column("last_pnl_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["committee_runs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", name="uq_paper_trades_run"),
        sa.CheckConstraint(
            "action IN ('buy','sell','trim','add')",
            name="ck_paper_trades_action",
        ),
    )
    op.create_index(
        "idx_paper_trades_symbol_executed",
        "paper_trades",
        ["symbol", sa.text("executed_at DESC")],
    )
    op.create_index(
        "idx_paper_trades_household_executed",
        "paper_trades",
        ["household_id", sa.text("executed_at DESC")],
    )

    op.create_table(
        "sector_targets",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("household_id", sa.String(length=64), nullable=True),
        sa.Column("sector", sa.String(length=64), nullable=False),
        sa.Column("target_pct", sa.Numeric(6, 4), nullable=True),
        sa.Column("max_pct", sa.Numeric(6, 4), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "max_pct > 0 AND max_pct <= 1",
            name="ck_sector_targets_max_pct_range",
        ),
        sa.CheckConstraint(
            "target_pct IS NULL OR (target_pct >= 0 AND target_pct <= 1)",
            name="ck_sector_targets_target_pct_range",
        ),
    )
    # Partial unique indexes so that (NULL, sector) is treated as unique too
    # (Postgres regards NULL as distinct from NULL inside a plain unique).
    op.create_index(
        "uq_sector_targets_household_sector",
        "sector_targets",
        ["household_id", "sector"],
        unique=True,
        postgresql_where=sa.text("household_id IS NOT NULL"),
    )
    op.create_index(
        "uq_sector_targets_global_sector",
        "sector_targets",
        ["sector"],
        unique=True,
        postgresql_where=sa.text("household_id IS NULL"),
    )

    # Seed global defaults (household_id IS NULL).
    sector_targets = sa.table(
        "sector_targets",
        sa.column("household_id", sa.String()),
        sa.column("sector", sa.String()),
        sa.column("max_pct", sa.Numeric()),
    )
    op.bulk_insert(
        sector_targets,
        [
            {"household_id": None, "sector": sector, "max_pct": max_pct}
            for sector, max_pct in _GLOBAL_SECTOR_DEFAULTS
        ],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "uq_sector_targets_global_sector", table_name="sector_targets"
    )
    op.drop_index(
        "uq_sector_targets_household_sector", table_name="sector_targets"
    )
    op.drop_table("sector_targets")

    op.drop_index(
        "idx_paper_trades_household_executed", table_name="paper_trades"
    )
    op.drop_index(
        "idx_paper_trades_symbol_executed", table_name="paper_trades"
    )
    op.drop_table("paper_trades")

    op.drop_index(
        "idx_committee_inputs_run_round", table_name="committee_inputs"
    )
    op.drop_table("committee_inputs")

    op.drop_index("idx_committee_evidence_run", table_name="committee_evidence")
    op.drop_table("committee_evidence")

    op.drop_index("idx_committee_events_run_seq", table_name="committee_events")
    op.drop_table("committee_events")

    op.drop_index("idx_committee_runs_parent", table_name="committee_runs")
    op.drop_index(
        "idx_committee_runs_household_started", table_name="committee_runs"
    )
    op.drop_index(
        "idx_committee_runs_symbol_started", table_name="committee_runs"
    )
    op.drop_table("committee_runs")
