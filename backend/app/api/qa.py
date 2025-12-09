"""QA router - endpoints for code quality issue tracking.

This module provides REST API endpoints for QA issues:
- GET /api/qa/issues - List/filter issues with pagination
- GET /api/qa/issues/{issue_id} - Get single issue detail
- PATCH /api/qa/issues/{issue_id}/resolve - Mark issue resolved
- PATCH /api/qa/issues/{issue_id}/false-positive - Mark false positive
- POST /api/qa/scan - Trigger QA scanner (calls QAScanner)
- GET /api/qa/summary - Get summary statistics
- GET /api/qa/trends - Get trend data for charts

Implements QA system for tracking:
- Dead code (unused functions, classes, imports)
- DRY violations (duplicated code blocks)
- Security issues (hardcoded secrets, SQL injection)
- Orphan files (no imports)
- Schema drift (DB inconsistencies)
- Stale data (outdated cache entries)
- Database bloat
- Test coverage gaps
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..logging_config import get_logger
from ..storage.connection import get_connection_manager

logger = get_logger(__name__)

router = APIRouter(prefix="/api/qa", tags=["qa"])


# Pydantic models for request/response
class QAIssueResponse(BaseModel):
    """Response model for a single QA issue."""

    id: int
    issue_id: str
    category: str
    severity: str
    file_path: str | None
    line_start: int | None
    line_end: int | None
    description: str
    detection_source: str | None
    first_detected_at: str
    last_detected_at: str
    resolved_at: str | None
    resolved_by: str | None
    resolution_notes: str | None
    false_positive: bool
    created_at: str
    updated_at: str


class QAIssuesListResponse(BaseModel):
    """Response model for list of issues."""

    issues: list[QAIssueResponse]
    total: int
    filtered: int


class QAIssueResolve(BaseModel):
    """Request model for resolving an issue."""

    resolved_by: str  # manual, claude, clean_it, auto
    resolution_notes: str | None = None


class QAIssueFalsePositive(BaseModel):
    """Request model for marking false positive."""

    false_positive: bool
    notes: str | None = None


class QASummaryResponse(BaseModel):
    """Response model for summary statistics."""

    total: int
    by_severity: dict[str, int]
    by_category: dict[str, int]
    trend: str  # improving, degrading, stable
    resolved_this_week: int
    added_this_week: int


class QATrendsResponse(BaseModel):
    """Response model for trend data."""

    snapshots: list[dict[str, Any]]


class QAScanRequest(BaseModel):
    """Request model for triggering a scan."""

    categories: list[str] | None = None  # Filter to specific categories


# Helper functions
def _row_to_issue_response(row: Any) -> QAIssueResponse:
    """Convert database row to QAIssueResponse."""
    return QAIssueResponse(
        id=row[0],
        issue_id=row[1],
        category=row[2],
        severity=row[3],
        file_path=row[4],
        line_start=row[5],
        line_end=row[6],
        description=row[7],
        detection_source=row[8],
        first_detected_at=row[9].isoformat() if row[9] else "",
        last_detected_at=row[10].isoformat() if row[10] else "",
        resolved_at=row[11].isoformat() if row[11] else None,
        resolved_by=row[12],
        resolution_notes=row[13],
        false_positive=row[14],
        created_at=row[15].isoformat() if row[15] else "",
        updated_at=row[16].isoformat() if row[16] else "",
    )


# Endpoints
@router.get("/issues", response_model=QAIssuesListResponse)
async def get_issues(
    category: str | None = Query(None, description="Filter by category"),
    severity: str | None = Query(None, description="Filter by severity"),
    resolved: bool | None = Query(None, description="Filter by resolved status"),
    false_positive: bool | None = Query(None, description="Filter by false positive"),
    limit: int = Query(50, ge=1, le=500, description="Results per page"),
    offset: int = Query(0, ge=0, description="Results offset"),
) -> QAIssuesListResponse:
    """Get paginated list of QA issues.

    Query params:
        - category: Filter by category (dead_code, dry_violation, etc.)
        - severity: Filter by severity (critical, high, medium, low)
        - resolved: Filter by resolved status (true/false/null for all)
        - false_positive: Filter by false positive status
        - limit: Results per page (default 50, max 500)
        - offset: Results offset for pagination
    """
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            # Build WHERE clause dynamically
            conditions = []
            params: list[Any] = []

            if category:
                conditions.append("category = %s")
                params.append(category)

            if severity:
                conditions.append("severity = %s")
                params.append(severity)

            if resolved is not None:
                if resolved:
                    conditions.append("resolved_at IS NOT NULL")
                else:
                    conditions.append("resolved_at IS NULL")

            if false_positive is not None:
                conditions.append("false_positive = %s")
                params.append(false_positive)

            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

            # Get total count
            count_query = f"SELECT COUNT(*) FROM qa_issues {where_clause}"
            total_row = conn.execute(count_query, params).fetchone()
            total = total_row[0] if total_row else 0

            # Get filtered count (same as total in this case)
            filtered = total

            # Get paginated results
            params.extend([limit, offset])
            query = f"""
                SELECT id, issue_id, category, severity, file_path, line_start, line_end,
                       description, detection_source, first_detected_at, last_detected_at,
                       resolved_at, resolved_by, resolution_notes, false_positive,
                       created_at, updated_at
                FROM qa_issues
                {where_clause}
                ORDER BY severity DESC, first_detected_at DESC
                LIMIT %s OFFSET %s
            """

            rows = conn.execute(query, params).fetchall()

            issues = [_row_to_issue_response(row) for row in rows]

            return QAIssuesListResponse(
                issues=issues,
                total=total,
                filtered=filtered,
            )

    except Exception as e:
        logger.error("get_issues_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/issues/{issue_id}", response_model=QAIssueResponse)
async def get_issue(issue_id: str) -> QAIssueResponse:
    """Get single issue by ID.

    Args:
        issue_id: Issue ID (e.g., QA-001)
    """
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            row = conn.execute(
                """
                SELECT id, issue_id, category, severity, file_path, line_start, line_end,
                       description, detection_source, first_detected_at, last_detected_at,
                       resolved_at, resolved_by, resolution_notes, false_positive,
                       created_at, updated_at
                FROM qa_issues
                WHERE issue_id = %s
                """,
                (issue_id,),
            ).fetchone()

            if not row:
                raise HTTPException(status_code=404, detail=f"Issue {issue_id} not found")

            return _row_to_issue_response(row)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_issue_failed", issue_id=issue_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.patch("/issues/{issue_id}/resolve", response_model=dict[str, Any])
async def resolve_issue(issue_id: str, update: QAIssueResolve) -> dict[str, Any]:
    """Mark an issue as resolved.

    Args:
        issue_id: Issue ID (e.g., QA-001)
        update: Resolution details (resolved_by, notes)
    """
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            result = conn.execute(
                """
                UPDATE qa_issues
                SET resolved_at = NOW(),
                    resolved_by = %s,
                    resolution_notes = %s,
                    updated_at = NOW()
                WHERE issue_id = %s
                RETURNING issue_id, resolved_at
                """,
                (update.resolved_by, update.resolution_notes, issue_id),
            ).fetchone()
            conn.commit()

            if not result:
                raise HTTPException(status_code=404, detail=f"Issue {issue_id} not found")

        logger.info(
            "issue_resolved",
            issue_id=issue_id,
            resolved_by=update.resolved_by,
        )

        return {
            "status": "resolved",
            "issue_id": result[0],
            "resolved_at": result[1].isoformat(),
            "resolved_by": update.resolved_by,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("resolve_issue_failed", issue_id=issue_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.patch("/issues/{issue_id}/false-positive", response_model=dict[str, Any])
async def mark_false_positive(
    issue_id: str, update: QAIssueFalsePositive
) -> dict[str, Any]:
    """Mark an issue as false positive.

    Args:
        issue_id: Issue ID (e.g., QA-001)
        update: False positive flag and notes
    """
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            # Update false_positive flag and optionally add notes
            if update.notes:
                result = conn.execute(
                    """
                    UPDATE qa_issues
                    SET false_positive = %s,
                        resolution_notes = %s,
                        updated_at = NOW()
                    WHERE issue_id = %s
                    RETURNING issue_id, false_positive
                    """,
                    (update.false_positive, update.notes, issue_id),
                ).fetchone()
            else:
                result = conn.execute(
                    """
                    UPDATE qa_issues
                    SET false_positive = %s,
                        updated_at = NOW()
                    WHERE issue_id = %s
                    RETURNING issue_id, false_positive
                    """,
                    (update.false_positive, issue_id),
                ).fetchone()
            conn.commit()

            if not result:
                raise HTTPException(status_code=404, detail=f"Issue {issue_id} not found")

        logger.info(
            "issue_false_positive_updated",
            issue_id=issue_id,
            false_positive=update.false_positive,
        )

        return {
            "status": "updated",
            "issue_id": result[0],
            "false_positive": result[1],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("mark_false_positive_failed", issue_id=issue_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/scan", response_model=dict[str, Any])
async def trigger_scan(
    categories: list[str] | None = Query(None, description="Filter to specific categories"),
) -> dict[str, Any]:
    """Trigger a QA scan.

    This queues the scan as a Celery task and returns immediately.

    Query params:
        - categories: Optional list of categories to scan (dead_code, dry_violation, etc.)
    """
    # Import here to avoid circular dependencies
    try:
        from ..tasks.qa_tasks import daily_qa_scan  # noqa: PLC0415

        # Queue the scan task
        task = daily_qa_scan.delay()

        logger.info("qa_scan_queued", task_id=task.id, categories=categories)

        return {
            "status": "queued",
            "task_id": task.id,
            "categories": categories or "all",
        }

    except ImportError:
        # Fallback if Celery task doesn't exist yet
        logger.warning("qa_scanner_task_not_found", categories=categories)
        return {
            "status": "error",
            "message": "QA scanner task not implemented yet",
            "categories": categories or "all",
        }
    except Exception as e:
        logger.error("trigger_scan_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/summary", response_model=QASummaryResponse)
async def get_summary() -> QASummaryResponse:
    """Get summary statistics for QA issues.

    Returns:
        - Total issue count
        - Breakdown by severity
        - Breakdown by category
        - Trend (improving/degrading/stable)
        - Issues resolved this week
        - Issues added this week
    """
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            # Get total count (excluding false positives and resolved issues)
            total_row = conn.execute(
                """
                SELECT COUNT(*)
                FROM qa_issues
                WHERE false_positive = false
                  AND resolved_at IS NULL
                """
            ).fetchone()
            total = total_row[0] if total_row else 0

            # Get by severity
            severity_rows = conn.execute(
                """
                SELECT severity, COUNT(*)
                FROM qa_issues
                WHERE false_positive = false
                  AND resolved_at IS NULL
                GROUP BY severity
                """
            ).fetchall()

            by_severity = {
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
            }
            for row in severity_rows:
                by_severity[row[0]] = row[1]

            # Get by category
            category_rows = conn.execute(
                """
                SELECT category, COUNT(*)
                FROM qa_issues
                WHERE false_positive = false
                  AND resolved_at IS NULL
                GROUP BY category
                """
            ).fetchall()

            by_category = {row[0]: row[1] for row in category_rows}

            # Get issues resolved this week
            week_ago = datetime.now() - timedelta(days=7)
            resolved_row = conn.execute(
                """
                SELECT COUNT(*)
                FROM qa_issues
                WHERE resolved_at >= %s
                """,
                (week_ago,),
            ).fetchone()
            resolved_this_week = resolved_row[0] if resolved_row else 0

            # Get issues added this week
            added_row = conn.execute(
                """
                SELECT COUNT(*)
                FROM qa_issues
                WHERE first_detected_at >= %s
                  AND false_positive = false
                """,
                (week_ago,),
            ).fetchone()
            added_this_week = added_row[0] if added_row else 0

            # Calculate trend (improving/degrading/stable)
            if resolved_this_week > added_this_week * 1.2:
                trend = "improving"
            elif added_this_week > resolved_this_week * 1.2:
                trend = "degrading"
            else:
                trend = "stable"

            return QASummaryResponse(
                total=total,
                by_severity=by_severity,
                by_category=by_category,
                trend=trend,
                resolved_this_week=resolved_this_week,
                added_this_week=added_this_week,
            )

    except Exception as e:
        logger.error("get_summary_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/trends", response_model=QATrendsResponse)
async def get_trends(
    days: int = Query(30, ge=7, le=365, description="Number of days to include"),
) -> QATrendsResponse:
    """Get trend data for charts.

    Query params:
        - days: Number of days to include (default 30, max 365)

    Returns:
        - List of daily snapshots with issue counts
    """
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            # Get snapshots from the last N days
            cutoff_date = date.today() - timedelta(days=days)

            rows = conn.execute(
                """
                SELECT snapshot_date, total_issues, critical_count, high_count,
                       medium_count, low_count, by_category, issues_added,
                       issues_resolved, lines_of_code, file_count, table_count
                FROM qa_snapshots
                WHERE snapshot_date >= %s
                ORDER BY snapshot_date ASC
                """,
                (cutoff_date,),
            ).fetchall()

            snapshots = [
                {
                    "date": row[0].isoformat(),
                    "total": row[1],
                    "critical": row[2],
                    "high": row[3],
                    "medium": row[4],
                    "low": row[5],
                    "by_category": row[6] if row[6] else {},
                    "added": row[7],
                    "resolved": row[8],
                    "lines_of_code": row[9],
                    "file_count": row[10],
                    "table_count": row[11],
                }
                for row in rows
            ]

            return QATrendsResponse(snapshots=snapshots)

    except Exception as e:
        logger.error("get_trends_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e
