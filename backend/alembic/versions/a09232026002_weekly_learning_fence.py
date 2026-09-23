"""Add a durable clock fence for Jenny's weekly learning run."""

from alembic import op

revision = "a09232026002"
down_revision = "a09232026001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Some existing databases reached the prior revision without retaining its
    # fence table. Restore it before adding the weekly workflow's fence row.
    op.execute("""
        CREATE TABLE IF NOT EXISTS automation_legacy_fences (
            workflow_key TEXT PRIMARY KEY,
            fenced BOOLEAN NOT NULL DEFAULT FALSE,
            fence_receipt TEXT UNIQUE,
            fenced_at TIMESTAMPTZ
        )
    """)
    op.execute("""
        INSERT INTO automation_legacy_fences (workflow_key)
        VALUES
            ('jenny_daily_household_maintenance'),
            ('jenny_daily_operator'),
            ('retrain_ml'),
            ('jenny_weekly_price_check'),
            ('jenny_weekly_learning')
        ON CONFLICT (workflow_key) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM automation_legacy_fences
        WHERE workflow_key = 'jenny_weekly_learning'
    """)
