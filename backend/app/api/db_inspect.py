"""Database inspection API for development/debugging.

Provides quick schema inspection without needing raw SQL.
"""

from typing import Any

from fastapi import APIRouter, Query

from app.storage import get_storage

router = APIRouter(prefix="/api/db", tags=["database"])


@router.get("/tables")
async def list_tables() -> dict[str, Any]:
    """List all tables with row counts."""
    storage = get_storage()
    with storage.connection() as conn:
        tables = conn.execute("""
            SELECT t.table_name,
                   (SELECT COUNT(*) FROM information_schema.columns c
                    WHERE c.table_name = t.table_name) as column_count
            FROM information_schema.tables t
            WHERE t.table_schema = 'public' AND t.table_type = 'BASE TABLE'
            ORDER BY t.table_name
        """).fetchall()

        result = []
        for table_name, col_count in tables:
            # Get row count (approximate for large tables)
            count_row = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
            result.append(
                {
                    "name": table_name,
                    "columns": col_count,
                    "rows": count_row[0] if count_row else 0,
                }
            )

    return {"tables": result, "count": len(result)}


@router.get("/schema/{table_name}")
async def get_table_schema(table_name: str) -> dict[str, Any]:
    """Get detailed schema for a specific table."""
    storage = get_storage()
    with storage.connection() as conn:
        # Get columns
        columns = conn.execute(
            """
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = %s
            ORDER BY ordinal_position
        """,
            (table_name,),
        ).fetchall()

        if not columns:
            return {"error": f"Table '{table_name}' not found"}

        # Get indexes
        indexes = conn.execute(
            """
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = %s
        """,
            (table_name,),
        ).fetchall()

        # Get foreign keys
        fks = conn.execute(
            """
            SELECT
                kcu.column_name,
                ccu.table_name AS foreign_table,
                ccu.column_name AS foreign_column
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage ccu
                ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
            AND tc.table_name = %s
        """,
            (table_name,),
        ).fetchall()

        # Get row count
        count_row = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
        count = count_row[0] if count_row else 0

    return {
        "table": table_name,
        "row_count": count,
        "columns": [
            {
                "name": c[0],
                "type": c[1],
                "nullable": c[2] == "YES",
                "default": c[3],
            }
            for c in columns
        ],
        "indexes": [{"name": i[0], "definition": i[1]} for i in indexes],
        "foreign_keys": [{"column": f[0], "references": f"{f[1]}.{f[2]}"} for f in fks],
    }


@router.get("/sample/{table_name}")
async def get_table_sample(
    table_name: str,
    limit: int = Query(default=5, le=20),
    columns: str | None = Query(default=None, description="Comma-separated column names"),
) -> dict[str, Any]:
    """Get sample rows from a table."""
    storage = get_storage()
    with storage.connection() as conn:
        # Validate table exists
        exists = conn.execute(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = %s
        """,
            (table_name,),
        ).fetchone()

        if not exists:
            return {"error": f"Table '{table_name}' not found"}

        # Build column list
        if columns:
            col_list = ", ".join(c.strip() for c in columns.split(","))
        else:
            col_list = "*"

        # Get sample (order by most recent if created_at exists)
        has_created_at = conn.execute(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_name = %s AND column_name = 'created_at'
        """,
            (table_name,),
        ).fetchone()

        order_clause = "ORDER BY created_at DESC" if has_created_at else ""

        rows = conn.execute(
            f"SELECT {col_list} FROM {table_name} {order_clause} LIMIT %s",
            (limit,),
        ).fetchall()

        # Get column names
        col_names = conn.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_name = %s ORDER BY ordinal_position
        """,
            (table_name,),
        ).fetchall()

        if columns:
            col_names = [(c.strip(),) for c in columns.split(",")]

    return {
        "table": table_name,
        "columns": [c[0] for c in col_names],
        "rows": [list(row) for row in rows],
        "count": len(rows),
    }


@router.get("/agent-tables")
async def get_agent_tables_overview() -> dict[str, Any]:
    """Quick overview of all agent-related tables for schema review."""
    storage = get_storage()
    agent_tables = [
        "agent_runs",
        "agent_messages",
        "agent_workflows",
        "strategy_reviews",
        "cross_validation_results",
    ]

    result = {}
    with storage.connection() as conn:
        for table in agent_tables:
            # Get schema
            columns = conn.execute(
                """
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = %s
                ORDER BY ordinal_position
            """,
                (table,),
            ).fetchall()

            # Get row count
            count_row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            count = count_row[0] if count_row else 0

            # Get FKs
            fks = conn.execute(
                """
                SELECT kcu.column_name, ccu.table_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                JOIN information_schema.constraint_column_usage ccu
                    ON ccu.constraint_name = tc.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_name = %s
            """,
                (table,),
            ).fetchall()

            result[table] = {
                "rows": count,
                "columns": [
                    {"name": c[0], "type": c[1], "nullable": c[2] == "YES"} for c in columns
                ],
                "foreign_keys": [{"column": f[0], "references": f[1]} for f in fks],
            }

    return result
