"""Approved card strategies and evidenced recurring-bill moves."""
from alembic import op

revision = "a09122026001"
down_revision = "a09112026004"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE card_strategy_plans (
        id UUID PRIMARY KEY, fingerprint TEXT NOT NULL, snapshot JSONB NOT NULL,
        status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','approved','paused','superseded')),
        previous_plan_id UUID REFERENCES card_strategy_plans(id),
        actual_card_id UUID REFERENCES household_credit_cards(id),
        eligibility_confirmed BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(), approved_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )""")
    op.execute("CREATE UNIQUE INDEX card_strategy_one_current ON card_strategy_plans ((true)) WHERE status IN ('approved','paused')")
    op.execute("""CREATE TABLE card_strategy_bill_moves (
        plan_id UUID NOT NULL REFERENCES card_strategy_plans(id),
        merchant_key TEXT NOT NULL, status TEXT NOT NULL CHECK (status IN ('confirmed','skipped')),
        fee_per_charge NUMERIC NOT NULL DEFAULT 0 CHECK (fee_per_charge >= 0),
        lost_discount NUMERIC NOT NULL DEFAULT 0 CHECK (lost_discount >= 0),
        benefits_checked BOOLEAN NOT NULL DEFAULT FALSE,
        confirmed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (plan_id, merchant_key)
    )""")


def downgrade():
    op.drop_table("card_strategy_bill_moves")
    op.drop_table("card_strategy_plans")
