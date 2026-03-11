"""drop legacy capability subsystem

Revision ID: 5f4a1c6d9e72
Revises: b2f9c40d0d5a
Create Date: 2026-03-11 11:45:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5f4a1c6d9e72"
down_revision: str | Sequence[str] | None = "b2f9c40d0d5a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _drop_table(name: str) -> None:
    op.execute(f"DROP TABLE IF EXISTS {name} CASCADE")


def upgrade() -> None:
    """Drop the retired capability and legacy feature-tracking schema."""
    # Drop tables with CASCADE so dependent legacy views disappear even when those
    # views were created under a different owner in older databases.
    _drop_table("feature_gap_mappings")
    _drop_table("feature_vision_goal_mappings")
    _drop_table("feature_dependencies")
    _drop_table("celery_feature_mappings")
    _drop_table("feature_tasks")
    _drop_table("feature_capabilities")

    _drop_table("capability_notes")
    _drop_table("capability_insights")
    _drop_table("api_capabilities")
    _drop_table("celery_capabilities")
    _drop_table("db_capabilities")

    op.execute("DROP FUNCTION IF EXISTS sync_task_completion()")
    op.execute("DROP FUNCTION IF EXISTS update_feature_tasks_updated_at()")
    op.execute("DROP FUNCTION IF EXISTS update_feature_capabilities_updated_at()")


def downgrade() -> None:
    """Downgrade schema."""
    raise RuntimeError(
        "Downgrade is not supported for the legacy capability subsystem removal migration."
    )
