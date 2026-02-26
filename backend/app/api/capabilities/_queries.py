"""SQL query helpers for capabilities router.

This module encapsulates all database query logic for capabilities endpoints,
keeping the router thin and focused on HTTP concerns.
"""

from __future__ import annotations

from typing import Any

from ..types import CapabilityDict, DependenciesDict, InsightDict, NoteDict
from .database import (
    capability_from_row,
    get_table_name,
    insight_from_row,
    note_from_row,
    transform_db_capability,
)

# System tables that should NEVER be included in cleanup candidates
SYSTEM_TABLES = {
    "capability_insights",
    "capability_notes",
    "db_capabilities",
    "celery_capabilities",
    "api_capabilities",
    "celery_taskmeta",
    "celery_tasksetmeta",
    "schema_migrations",
    "alembic_version",
    "source_credentials",
    "maintenance_log",
}

_CAP_TYPES = ("db", "hatchet", "api")

# ---------------------------------------------------------------------------
# Shared query builders
# ---------------------------------------------------------------------------


def _build_cap_select(cap_type: str, extra_where: list[str]) -> tuple[str, list[Any]]:
    """Build SELECT query for a single capability type with join counts.

    Returns the query string and initial params list ``[cap_type, cap_type]``.
    The caller must append filter params matching *extra_where* clauses.
    """
    table = get_table_name(cap_type)
    params: list[Any] = [cap_type, cap_type]
    query = f"""
        SELECT
            '{cap_type}' as capability_type,
            c.*,
            COALESCE(insights.count, 0) as insights_count,
            COALESCE(notes.count, 0) as notes_count
        FROM {table} c
        LEFT JOIN (
            SELECT capability_id, COUNT(*) as count
            FROM capability_insights
            WHERE capability_type = %s
            GROUP BY capability_id
        ) insights ON c.id = insights.capability_id
        LEFT JOIN (
            SELECT capability_id, COUNT(*) as count
            FROM capability_notes
            WHERE capability_type = %s
            GROUP BY capability_id
        ) notes ON c.id = notes.capability_id
    """
    if extra_where:
        query += " WHERE " + " AND ".join(extra_where)
    return query, params


def _fetch_capabilities(conn: Any, query: str, params: list[Any]) -> list[CapabilityDict]:
    """Execute a capability query and return transformed CapabilityDict list."""
    result = conn.execute(query, params)
    columns = [desc[0] for desc in result.description] if result.description else []
    rows = result.fetchall()
    caps = [capability_from_row(row, columns) for row in rows]
    return [transform_db_capability(cap) for cap in caps]


# ---------------------------------------------------------------------------
# get_capabilities query helpers
# ---------------------------------------------------------------------------


def query_all_capabilities(
    conn: Any,
    *,
    category: str | None,
    health_status: str | None,
    limit: int,
    offset: int,
) -> tuple[list[CapabilityDict], int]:
    """Query all capability types and apply pagination in Python."""
    all_caps: list[CapabilityDict] = []
    for cap_type in _CAP_TYPES:
        extra_where: list[str] = []
        filter_params: list[Any] = []
        if category:
            extra_where.append("c.category = %s")
            filter_params.append(category)
        if health_status:
            extra_where.append("c.health_status = %s")
            filter_params.append(health_status)

        query, base_params = _build_cap_select(cap_type, extra_where)
        query += " ORDER BY c.id"
        all_caps.extend(_fetch_capabilities(conn, query, base_params + filter_params))

    total = len(all_caps)
    return all_caps[offset : offset + limit], total


def query_single_type_capabilities(
    conn: Any,
    cap_type: str,
    *,
    category: str | None,
    status: str | None,
    health_status: str | None,
    limit: int,
    offset: int,
) -> tuple[list[CapabilityDict], int]:
    """Query a single capability type with server-side pagination."""
    extra_where: list[str] = []
    filter_params: list[Any] = []

    if category:
        extra_where.append("c.category = %s")
        filter_params.append(category)
    if status and cap_type == "db":
        extra_where.append("c.freshness_status = %s")
        filter_params.append(status)
    if health_status:
        extra_where.append("c.health_status = %s")
        filter_params.append(health_status)

    table = get_table_name(cap_type)
    count_query = f"SELECT COUNT(*) FROM {table} c"
    if extra_where:
        count_query += " WHERE " + " AND ".join(extra_where)
    count_result = conn.execute(count_query, filter_params).fetchone()
    total = int(count_result[0]) if count_result and isinstance(count_result[0], int) else 0

    query, base_params = _build_cap_select(cap_type, extra_where)
    query += " ORDER BY c.id LIMIT %s OFFSET %s"
    params = base_params + filter_params + [limit, offset]
    caps = _fetch_capabilities(conn, query, params)
    return caps, total


# ---------------------------------------------------------------------------
# get_health_summary helpers
# ---------------------------------------------------------------------------

_HEALTH_TABLES = {
    "database": "db_capabilities",
    "hatchet": "celery_capabilities",
    "api": "api_capabilities",
}


def query_health_counts(conn: Any, table: str) -> list[tuple[Any, ...]]:
    """Return (health_status, count) rows from *table*."""
    sql = f"""
        SELECT health_status, COUNT(*) as count
        FROM {table}
        WHERE health_status IS NOT NULL
        GROUP BY health_status
    """
    return conn.execute(sql).fetchall()  # type: ignore[no-any-return]


def accumulate_health_row(
    summary: dict[str, Any],
    type_key: str,
    row: tuple[Any, ...],
) -> None:
    """Update *summary* in-place with one health-count row."""
    health_status_val, count = row
    if not (isinstance(health_status_val, str) and isinstance(count, int)):
        return
    summary["by_type"][type_key][health_status_val] = count
    summary["by_status"][health_status_val] += count
    summary["total"] += count


def build_health_summary(conn: Any) -> dict[str, Any]:
    """Build the full health summary dict by querying all capability tables."""
    summary: dict[str, Any] = {
        "total": 0,
        "by_type": {
            "database": {"active": 0, "orphaned": 0, "legacy": 0, "suspect": 0},
            "hatchet": {"active": 0, "orphaned": 0, "legacy": 0, "suspect": 0},
            "api": {"active": 0, "orphaned": 0, "legacy": 0, "suspect": 0},
        },
        "by_status": {"active": 0, "orphaned": 0, "legacy": 0, "suspect": 0},
    }
    for type_key, table in _HEALTH_TABLES.items():
        for row in query_health_counts(conn, table):
            accumulate_health_row(summary, type_key, row)
    return summary


# ---------------------------------------------------------------------------
# get_capability_detail helpers
# ---------------------------------------------------------------------------


def fetch_capability_record(
    conn: Any, cap_type: str, cap_id: int
) -> CapabilityDict | None:
    """Fetch a single capability row; returns None when not found."""
    table = get_table_name(cap_type)
    result = conn.execute(f"SELECT * FROM {table} WHERE id = %s", [cap_id])
    columns = [desc[0] for desc in result.description] if result.description else []
    row = result.fetchone()
    if not row:
        return None
    cap = capability_from_row(row, columns)
    return transform_db_capability(cap)


def fetch_insights(conn: Any, cap_type: str, cap_id: int) -> list[InsightDict]:
    """Fetch all insights for a capability, most recent first."""
    sql = """
        SELECT * FROM capability_insights
        WHERE capability_type = %s AND capability_id = %s
        ORDER BY generated_at DESC
    """
    result = conn.execute(sql, [cap_type, cap_id])
    columns = [desc[0] for desc in result.description] if result.description else []
    return [insight_from_row(row, columns) for row in result.fetchall()]


def fetch_notes(conn: Any, cap_type: str, cap_id: int) -> list[NoteDict]:
    """Fetch all notes for a capability, most recent first."""
    sql = """
        SELECT * FROM capability_notes
        WHERE capability_type = %s AND capability_id = %s
        ORDER BY created_at DESC
    """
    result = conn.execute(sql, [cap_type, cap_id])
    columns = [desc[0] for desc in result.description] if result.description else []
    return [note_from_row(row, columns) for row in result.fetchall()]


def extract_dependencies(cap: CapabilityDict, cap_type: str) -> DependenciesDict:
    """Extract dependency info from JSONB fields based on capability type."""
    deps: DependenciesDict = {}
    if cap_type == "hatchet":
        populates = cap.get("populates_tables", [])
        depends_tasks = cap.get("depends_on_tasks", [])
        if isinstance(populates, list) and isinstance(depends_tasks, list):
            deps["populates_tables"] = populates
            deps["depends_on_tasks"] = depends_tasks
    elif cap_type == "api":
        depends_tables = cap.get("depends_on_tables", [])
        if isinstance(depends_tables, list):
            deps["depends_on_tables"] = depends_tables
    return deps


# ---------------------------------------------------------------------------
# get_cleanup_candidates helpers
# ---------------------------------------------------------------------------


def _build_evidence(health: str, **kwargs: Any) -> list[str]:
    """Build evidence list for any cleanup candidate."""
    ev: list[str] = []
    if health == "orphaned":
        ev.append("Marked as orphaned (no active usage detected)")
    if health == "legacy":
        ev.append("Marked as legacy (outdated or inactive)")
    return ev


def fetch_db_cleanup_candidates(conn: Any) -> list[dict[str, Any]]:
    """Return orphaned/legacy DB table candidates, excluding system tables."""
    system_list = list(SYSTEM_TABLES)
    placeholders = ",".join(["%s"] * len(system_list))
    sql = f"""
        SELECT id, table_name, category, health_status, row_count,
               freshness_status, days_since_update, completeness_pct
        FROM db_capabilities
        WHERE health_status IN ('orphaned', 'legacy')
          AND table_name NOT IN ({placeholders})
        ORDER BY health_status, table_name
    """
    rows = conn.execute(sql, tuple(system_list)).fetchall()
    candidates: list[dict[str, Any]] = []
    for row in rows:
        (row_id, table_name, category, health, row_count,
         freshness_status, days_raw, completeness_pct) = row
        days: float | None = float(days_raw) if days_raw else None
        evidence = _build_evidence(health)
        if isinstance(row_count, int) and row_count == 0:
            evidence.append("Table is empty (0 rows)")
        if isinstance(days, (int, float)) and days > 30:
            evidence.append(f"No updates in {days:.0f} days")
        if isinstance(completeness_pct, (int, float)) and completeness_pct < 10:
            evidence.append(f"Very low completeness ({completeness_pct}%)")
        candidates.append({
            "id": row_id, "name": table_name, "category": category,
            "health_status": health, "row_count": row_count,
            "freshness_status": freshness_status, "days_since_update": days,
            "completeness_pct": completeness_pct, "evidence": evidence,
        })
    return candidates


def fetch_hatchet_cleanup_candidates(conn: Any) -> list[dict[str, Any]]:
    """Return orphaned/legacy Hatchet task candidates."""
    sql = """
        SELECT id, task_name, category, health_status,
               schedule_description, schedule_crontab,
               schedule_interval_seconds, success_rate_pct, populates_tables
        FROM celery_capabilities
        WHERE health_status IN ('orphaned', 'legacy')
        ORDER BY health_status, task_name
    """
    rows = conn.execute(sql).fetchall()
    candidates: list[dict[str, Any]] = []
    for row in rows:
        (task_id, task_name, category, health, schedule_desc,
         crontab, interval, success_rate, populates_raw) = row
        has_schedule = bool(crontab or interval)
        populates = populates_raw if populates_raw else []
        evidence = _build_evidence(health)
        if not has_schedule:
            evidence.append("Not scheduled (no crontab/interval)")
        if not populates:
            evidence.append("Does not populate any tables")
        if isinstance(success_rate, (int, float)) and success_rate < 50:
            evidence.append(f"Low success rate ({success_rate}%)")
        candidates.append({
            "id": task_id, "name": task_name, "category": category,
            "health_status": health, "schedule_description": schedule_desc,
            "has_schedule": has_schedule, "success_rate_pct": success_rate,
            "populates_tables": populates, "evidence": evidence,
        })
    return candidates


def fetch_api_cleanup_candidates(conn: Any) -> list[dict[str, Any]]:
    """Return orphaned/legacy API endpoint candidates."""
    sql = """
        SELECT id, endpoint_path, category, health_status,
               http_method, depends_on_tables
        FROM api_capabilities
        WHERE health_status IN ('orphaned', 'legacy')
        ORDER BY health_status, endpoint_path
    """
    rows = conn.execute(sql).fetchall()
    candidates: list[dict[str, Any]] = []
    for row in rows:
        api_id, endpoint_path, category, health, http_method, depends_raw = row
        depends = depends_raw if depends_raw else []
        evidence = _build_evidence(health)
        if not depends:
            evidence.append("No table dependencies detected")
        candidates.append({
            "id": api_id, "name": endpoint_path, "category": category,
            "health_status": health, "http_method": http_method,
            "path": endpoint_path, "depends_on_tables": depends,
            "evidence": evidence,
        })
    return candidates
