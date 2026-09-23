"""Durable Agent Hub owner dispatch receipts."""

from alembic import op

revision = "a09232026001"
down_revision = "a09122026002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE automation_legacy_fences (
            workflow_key TEXT PRIMARY KEY,
            fenced BOOLEAN NOT NULL DEFAULT FALSE,
            fence_receipt TEXT UNIQUE,
            fenced_at TIMESTAMPTZ
        )
    """)
    op.execute("""
        INSERT INTO automation_legacy_fences (workflow_key) VALUES
        ('jenny_daily_household_maintenance'),
        ('jenny_daily_operator'),
        ('retrain_ml'),
        ('jenny_weekly_price_check')
    """)
    op.execute("""
        CREATE TABLE automation_owner_receipts (
            run_id TEXT PRIMARY KEY,
            profile_id TEXT NOT NULL,
            workflow_key TEXT NOT NULL,
            occurrence_key TEXT NOT NULL,
            trigger TEXT NOT NULL,
            status TEXT NOT NULL,
            receipt JSONB NOT NULL DEFAULT '{}'::jsonb,
            error TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            completed_at TIMESTAMPTZ
        )
    """)


def downgrade() -> None:
    op.drop_table("automation_owner_receipts")
    op.drop_table("automation_legacy_fences")
