"""drop celery tables

Revision ID: 217b5c166647
Revises: 98d4e5d9fce7
Create Date: 2026-02-09 09:28:25.155626

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '217b5c166647'
down_revision: str | Sequence[str] | None = '98d4e5d9fce7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Drop Celery result backend tables (migrated to Hatchet)."""
    op.execute(
        """
        DO $$
        DECLARE
            owner_name text;
        BEGIN
            SELECT tableowner
            INTO owner_name
            FROM pg_tables
            WHERE schemaname = 'public' AND tablename = 'celery_tasksetmeta';

            IF owner_name = current_user THEN
                EXECUTE 'DROP TABLE public.celery_tasksetmeta CASCADE';
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        DECLARE
            owner_name text;
        BEGIN
            SELECT tableowner
            INTO owner_name
            FROM pg_tables
            WHERE schemaname = 'public' AND tablename = 'celery_taskmeta';

            IF owner_name = current_user THEN
                EXECUTE 'DROP TABLE public.celery_taskmeta CASCADE';
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    """Recreate Celery result backend tables."""
    op.create_table(
        "celery_taskmeta",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("task_id", sa.String(155), unique=True),
        sa.Column("status", sa.String(50)),
        sa.Column("result", sa.LargeBinary()),
        sa.Column("date_done", sa.DateTime()),
        sa.Column("traceback", sa.Text()),
    )
    op.create_table(
        "celery_tasksetmeta",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("taskset_id", sa.String(155), unique=True),
        sa.Column("result", sa.LargeBinary()),
        sa.Column("date_done", sa.DateTime()),
    )
