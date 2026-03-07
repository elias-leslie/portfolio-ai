import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "eadedfee7cef"
down_revision: str | None = "9ea9667630c4"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Add outcome-linked Jenny scorecard breakdown fields."""
    op.add_column("jenny_agent_scorecards", sa.Column("entry_quality_score", sa.Float(), nullable=True))
    op.add_column("jenny_agent_scorecards", sa.Column("risk_judgment_score", sa.Float(), nullable=True))
    op.add_column("jenny_agent_scorecards", sa.Column("exit_timing_score", sa.Float(), nullable=True))
    op.add_column("jenny_agent_scorecards", sa.Column("alert_discipline_score", sa.Float(), nullable=True))


def downgrade() -> None:
    """Remove outcome-linked Jenny scorecard breakdown fields."""
    op.drop_column("jenny_agent_scorecards", "alert_discipline_score")
    op.drop_column("jenny_agent_scorecards", "exit_timing_score")
    op.drop_column("jenny_agent_scorecards", "risk_judgment_score")
    op.drop_column("jenny_agent_scorecards", "entry_quality_score")
