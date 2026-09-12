"""Distinguish declining an entry from invalidating a thesis."""

from alembic import op

revision = "a09112026003"
down_revision = "a09112026002"
branch_labels = None
depends_on = None


def _constraints(include_passed: bool) -> None:
    stages = "'discover','thesis_ready','tracked','live','review_due','invalidated','exited'"
    if include_passed:
        stages += ",'passed'"
    for table, constraint, column in (
        ("symbol_workflows", "ck_symbol_workflows_stage", "current_stage"),
        ("symbol_workflow_events", "ck_symbol_workflow_events_to_stage", "to_stage"),
    ):
        op.drop_constraint(constraint, table, type_="check")
        op.create_check_constraint(constraint, table, f"{column} IN ({stages})")


def upgrade():
    _constraints(True)


def downgrade():
    # Preserve notes and outcome metadata even when an older reader lacks this stage.
    op.execute("UPDATE symbol_workflows SET current_stage = 'discover' WHERE current_stage = 'passed'")
    op.execute("UPDATE symbol_workflow_events SET to_stage = 'discover' WHERE to_stage = 'passed'")
    op.execute("UPDATE symbol_workflow_events SET from_stage = 'discover' WHERE from_stage = 'passed'")
    _constraints(False)
