"""Add a durable clock fence for Jenny's weekly learning run."""

from alembic import op

revision = "a09232026002"
down_revision = "a09232026001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO automation_legacy_fences (workflow_key)
        VALUES ('jenny_weekly_learning')
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM automation_legacy_fences
        WHERE workflow_key = 'jenny_weekly_learning'
    """)
