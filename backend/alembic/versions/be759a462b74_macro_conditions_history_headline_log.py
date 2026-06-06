"""macro_conditions_history headline log

Revision ID: be759a462b74
Revises: a1f4c7e9b2d3
Create Date: 2026-06-06 15:38:38.600494

Append-only log of the Today page headline numbers (Overall Caution, Tape
Pressure, Macro Stress) over time. ``signal_macro_snapshots`` only stores the
macro composite (one EOD row per day); the headline the user actually reacts to
— ``overall_caution = max(macro_stress, tape_pressure)`` — was recomputed per
request and thrown away, so there was no way to show what the number was or when
it moved. This table closes that gap and backs the single headline trend line.

``tape_available`` records whether the tape term was a live in-session reading.
Off-hours rows are macro-only (tape unavailable), so the trend line can render
them distinctly instead of implying a real intraday move.

Backfill: one macro-only row per existing snapshot (tape_available = false) so
the chart has an immediate ~history spine; tape/overall history before this
migration cannot be reconstructed because it was never stored. Additive.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "be759a462b74"
down_revision: str | Sequence[str] | None = "a1f4c7e9b2d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "macro_conditions_history",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("deployment_score", sa.Float(), nullable=True),
        sa.Column("macro_stress", sa.SmallInteger(), nullable=True),
        sa.Column("tape_pressure", sa.SmallInteger(), nullable=True),
        sa.Column("overall_caution", sa.SmallInteger(), nullable=True),
        sa.Column("overall_read", sa.Text(), nullable=True),
        sa.Column("primary_driver", sa.Text(), nullable=True),
        sa.Column("state", sa.Text(), nullable=True),
        sa.Column(
            "tape_available",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("market_session", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    # Trend read path: points in time order, optionally windowed by recorded_at.
    op.create_index(
        "idx_macro_conditions_history_recorded_at",
        "macro_conditions_history",
        ["recorded_at"],
    )

    # Macro-only backfill so the headline trend line has an immediate spine.
    # tape_available = false: these points are 100 - deployment_score, not the
    # live overall caution (tape was never logged before this migration).
    op.execute(
        sa.text(
            """
            INSERT INTO macro_conditions_history (
                recorded_at, snapshot_date, deployment_score,
                macro_stress, overall_caution, tape_pressure,
                overall_read, primary_driver, state,
                tape_available, market_session
            )
            SELECT
                COALESCE(computed_at, snapshot_date::timestamptz),
                snapshot_date,
                deployment_score,
                ROUND(GREATEST(0, LEAST(100, 100 - deployment_score)))::smallint,
                ROUND(GREATEST(0, LEAST(100, 100 - deployment_score)))::smallint,
                NULL, NULL, NULL, NULL,
                false,
                'backfill'
            FROM signal_macro_snapshots
            WHERE deployment_score IS NOT NULL
            ORDER BY snapshot_date ASC
            """
        )
    )


def downgrade() -> None:
    op.drop_index(
        "idx_macro_conditions_history_recorded_at",
        table_name="macro_conditions_history",
    )
    op.drop_table("macro_conditions_history")
