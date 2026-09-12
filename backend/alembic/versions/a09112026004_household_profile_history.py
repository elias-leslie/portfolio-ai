"""Retain exact changes to saved household assumptions."""

from alembic import op

revision = "a09112026004"
down_revision = "a09112026003"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE household_profile_changes (
            id UUID PRIMARY KEY,
            profile_id UUID NOT NULL REFERENCES household_profiles(id),
            source TEXT NOT NULL,
            changes JSONB NOT NULL,
            changed_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX ON household_profile_changes (changed_at DESC)")


def downgrade():
    op.drop_table("household_profile_changes")
