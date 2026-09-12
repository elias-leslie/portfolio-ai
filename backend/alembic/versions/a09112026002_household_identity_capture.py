"""Household identity and provisional capture, without embedded identities."""

from alembic import op

revision = "a09112026002"
down_revision = "a09112026001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE household_members ADD COLUMN email TEXT")
    op.execute(
        "CREATE UNIQUE INDEX household_member_email_unique ON household_members (lower(email)) WHERE email IS NOT NULL"
    )
    op.execute("""CREATE TABLE household_captures (
        id UUID PRIMARY KEY, captured_by UUID REFERENCES household_members(id),
        client_id UUID NOT NULL, kind TEXT NOT NULL CHECK (kind IN ('receipt','shelf_tag')),
        filename TEXT NOT NULL, storage_key TEXT NOT NULL, content_type TEXT NOT NULL,
        content_sha256 TEXT NOT NULL, store_name TEXT NOT NULL DEFAULT '',
        note TEXT NOT NULL DEFAULT '', purchased_by UUID REFERENCES household_members(id),
        purchased_for UUID REFERENCES household_members(id),
        outcome TEXT NOT NULL DEFAULT 'unknown' CHECK (outcome IN ('unknown','purchased','not_purchased')),
        status TEXT NOT NULL DEFAULT 'pending_review' CHECK (status IN ('pending_review','in_review','verified','needs_correction')),
        document_id UUID REFERENCES household_documents(id) ON DELETE SET NULL,
        review_note TEXT NOT NULL DEFAULT '', reviewed_by UUID REFERENCES household_members(id),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE NULLS NOT DISTINCT (captured_by, client_id)
    )""")
    op.execute("""CREATE TABLE household_chat_sessions (
        session_id TEXT PRIMARY KEY, member_id UUID NOT NULL REFERENCES household_members(id),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )""")


def downgrade():
    op.drop_table("household_chat_sessions")
    op.drop_table("household_captures")
    op.drop_index("household_member_email_unique", "household_members")
    op.drop_column("household_members", "email")
