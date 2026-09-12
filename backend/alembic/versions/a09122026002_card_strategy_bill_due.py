"""Preserve the expected first bill charge across recurring-calendar updates."""
from alembic import op

revision = "a09122026002"
down_revision = "a09122026001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE card_strategy_bill_moves ADD COLUMN IF NOT EXISTS first_charge_due_on DATE")


def downgrade():
    op.drop_column("card_strategy_bill_moves", "first_charge_due_on")
