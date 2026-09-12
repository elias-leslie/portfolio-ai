"""Keep proposed card terms separate from verified catalog values."""

from alembic import op

revision = "a09112026001"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE credit_card_products ADD COLUMN verified_terms JSONB NOT NULL DEFAULT '{}'::jsonb")
    op.execute("""CREATE TABLE card_term_proposals (
        id UUID PRIMARY KEY, product_slug TEXT NOT NULL, proposed_fields JSONB NOT NULL,
        previous_fields JSONB NOT NULL, evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
        fingerprint TEXT NOT NULL UNIQUE, status TEXT NOT NULL DEFAULT 'pending'
            CHECK (status IN ('pending','accepted','dismissed')),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(), reviewed_at TIMESTAMPTZ,
        review_source TEXT NOT NULL DEFAULT 'research'
    )""")


def downgrade():
    op.drop_table("card_term_proposals")
    op.drop_column("credit_card_products", "verified_terms")
