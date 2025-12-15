"""Artifact Manager - Service for managing UI verification evidence artifacts.

This module provides functions to:
- Save and retrieve artifacts (screenshots + evidence.json)
- Track artifact versions
- Manage AI and user reviews
- Clean up old versions

Artifacts are stored at: data/artifacts/{feature_id}/{criterion_id}/v{n}/
Each version contains:
  - screenshot.png: Full page screenshot
  - evidence.json: Console, network, page state, performance data
"""

from __future__ import annotations

import asyncio
import json
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from ..logging_config import get_logger
from ..storage.connection import get_connection_manager

logger = get_logger(__name__)

# Configuration
ARTIFACTS_BASE_DIR = Path("/home/kasadis/portfolio-ai/data/artifacts")
BROWSER_SCRIPTS_DIR = Path("/home/kasadis/portfolio-ai/.claude/skills/browser-automation/scripts")
DEFAULT_EXPIRY_HOURS = 24
MAX_VERSIONS_TO_KEEP = 5
CAPTURE_TIMEOUT_SECONDS = 60


def generate_artifact_id(feature_id: str, criterion_id: str, version: int) -> str:
    """Generate a unique artifact ID."""
    return f"{feature_id}-{criterion_id}-v{version}"


async def capture_evidence(
    url: str,
    feature_id: str,
    criterion_id: str,
) -> dict[str, Any]:
    """Capture evidence for a UI criterion using the capture-evidence.js script.

    Args:
        url: The full URL to capture
        feature_id: Feature ID (e.g., FEAT-001)
        criterion_id: Criterion ID (e.g., ac-001)

    Returns:
        Dict with success, version, file_path, evidence data
    """
    script_path = BROWSER_SCRIPTS_DIR / "capture-evidence.js"

    if not script_path.exists():
        return {
            "success": False,
            "error": f"Capture script not found: {script_path}",
        }

    try:
        proc = await asyncio.create_subprocess_exec(
            "node",
            str(script_path),
            url,
            feature_id,
            criterion_id,
            str(ARTIFACTS_BASE_DIR),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, _stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=CAPTURE_TIMEOUT_SECONDS,
        )

        output = stdout.decode()

        # Parse JSON result from script output
        result_line = None
        for line in output.split("\n"):
            if line.startswith("{") and '"success"' in line:
                result_line = line
                break

        if result_line:
            parsed: dict[str, Any] = json.loads(result_line)
            return parsed

        return {
            "success": False,
            "error": f"Could not parse script output: {output[:500]}",
        }

    except TimeoutError:
        return {
            "success": False,
            "error": f"Capture timed out after {CAPTURE_TIMEOUT_SECONDS}s",
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


def save_artifact(
    feature_id: str,
    criterion_id: str,
    version: int,
    file_path: str,
    file_size_bytes: int | None = None,
    evidence_data: dict[str, Any] | None = None,
    expires_hours: int = DEFAULT_EXPIRY_HOURS,
) -> dict[str, Any]:
    """Save an artifact record to the database.

    Args:
        feature_id: Feature ID (e.g., FEAT-001)
        criterion_id: Criterion ID (e.g., ac-001)
        version: Version number
        file_path: Relative path to artifact directory
        file_size_bytes: Total size of files
        evidence_data: Parsed evidence.json data
        expires_hours: Hours until artifact expires

    Returns:
        Created artifact record
    """
    artifact_id = generate_artifact_id(feature_id, criterion_id, version)
    expires_at = datetime.now(UTC) + timedelta(hours=expires_hours)

    storage = get_connection_manager()

    with storage.connection() as conn:
        # Mark previous versions as not current
        conn.execute(
            """
            UPDATE artifacts
            SET is_current = FALSE, updated_at = NOW()
            WHERE feature_id = %s AND criterion_id = %s AND is_current = TRUE
            """,
            (feature_id, criterion_id),
        )

        # Insert new artifact
        result = conn.execute(
            """
            INSERT INTO artifacts (
                artifact_id, feature_id, criterion_id, artifact_type,
                file_path, file_size_bytes, version, is_current,
                captured_at, expires_at, quality_status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE, NOW(), %s, 'pending')
            RETURNING id, artifact_id, captured_at
            """,
            (
                artifact_id,
                feature_id,
                criterion_id,
                "evidence",
                file_path,
                file_size_bytes,
                version,
                expires_at,
            ),
        ).fetchone()

        conn.commit()

        if not result:
            raise RuntimeError("Failed to create artifact record")

        logger.info(
            "artifact_saved",
            artifact_id=artifact_id,
            feature_id=feature_id,
            criterion_id=criterion_id,
            version=version,
        )

        # Type narrowing: result[2] is DatabaseValue, need to cast to datetime
        from datetime import datetime as dt

        captured_ts = result[2]
        captured_iso: str | None = None
        if captured_ts is not None and isinstance(captured_ts, dt):
            captured_iso = captured_ts.isoformat()

        return {
            "id": result[0],
            "artifact_id": result[1],
            "captured_at": captured_iso,
            "version": version,
            "file_path": file_path,
        }


def get_artifact(
    feature_id: str,
    criterion_id: str,
    version: int | None = None,
) -> dict[str, Any] | None:
    """Get artifact metadata (current version or specific version).

    Args:
        feature_id: Feature ID
        criterion_id: Criterion ID
        version: Optional specific version (defaults to current)

    Returns:
        Artifact record or None
    """
    storage = get_connection_manager()

    with storage.connection() as conn:
        if version:
            row = conn.execute(
                """
                SELECT id, artifact_id, feature_id, criterion_id, artifact_type,
                       file_path, file_size_bytes, version, is_current,
                       captured_at, expires_at, quality_status, quality_issues,
                       confidence, ai_reviewed_at, ai_reviewed_by, ai_evidence,
                       user_reviewed_at, user_approved, user_notes
                FROM artifacts
                WHERE feature_id = %s AND criterion_id = %s AND version = %s
                """,
                (feature_id, criterion_id, version),
            ).fetchone()
        else:
            row = conn.execute(
                """
                SELECT id, artifact_id, feature_id, criterion_id, artifact_type,
                       file_path, file_size_bytes, version, is_current,
                       captured_at, expires_at, quality_status, quality_issues,
                       confidence, ai_reviewed_at, ai_reviewed_by, ai_evidence,
                       user_reviewed_at, user_approved, user_notes
                FROM artifacts
                WHERE feature_id = %s AND criterion_id = %s AND is_current = TRUE
                """,
                (feature_id, criterion_id),
            ).fetchone()

        if not row:
            return None

        return _row_to_artifact(row)


def get_latest_artifact() -> dict[str, Any] | None:
    """Get the most recently captured artifact.

    Returns:
        Most recent artifact record or None
    """
    storage = get_connection_manager()

    with storage.connection() as conn:
        row = conn.execute(
            """
            SELECT id, artifact_id, feature_id, criterion_id, artifact_type,
                   file_path, file_size_bytes, version, is_current,
                   captured_at, expires_at, quality_status, quality_issues,
                   confidence, ai_reviewed_at, ai_reviewed_by, ai_evidence,
                   user_reviewed_at, user_approved, user_notes
            FROM artifacts
            WHERE is_current = TRUE
            ORDER BY captured_at DESC
            LIMIT 1
            """,
        ).fetchone()

        if not row:
            return None

        return _row_to_artifact(row)


def get_next_version(feature_id: str, criterion_id: str) -> int:
    """Get the next version number for a feature/criterion pair.

    Returns:
        Next version number (1 if no existing versions)
    """
    storage = get_connection_manager()

    with storage.connection() as conn:
        row = conn.execute(
            """
            SELECT MAX(version) as max_version
            FROM artifacts
            WHERE feature_id = %s AND criterion_id = %s
            """,
            (feature_id, criterion_id),
        ).fetchone()

        if row and row[0]:
            return row[0] + 1
        return 1


def get_artifact_versions(
    feature_id: str,
    criterion_id: str,
) -> list[dict[str, Any]]:
    """Get all versions of an artifact.

    Returns:
        List of artifact records ordered by version desc
    """
    storage = get_connection_manager()

    with storage.connection() as conn:
        rows = conn.execute(
            """
            SELECT id, artifact_id, feature_id, criterion_id, artifact_type,
                   file_path, file_size_bytes, version, is_current,
                   captured_at, expires_at, quality_status, quality_issues,
                   confidence, ai_reviewed_at, ai_reviewed_by, ai_evidence,
                   user_reviewed_at, user_approved, user_notes
            FROM artifacts
            WHERE feature_id = %s AND criterion_id = %s
            ORDER BY version DESC
            """,
            (feature_id, criterion_id),
        ).fetchall()

        return [_row_to_artifact(row) for row in rows]


def get_pending_review(limit: int = 50) -> list[dict[str, Any]]:
    """Get artifacts pending AI review.

    Returns:
        List of artifacts with quality_status = 'pending'
    """
    storage = get_connection_manager()

    with storage.connection() as conn:
        rows = conn.execute(
            """
            SELECT id, artifact_id, feature_id, criterion_id, artifact_type,
                   file_path, file_size_bytes, version, is_current,
                   captured_at, expires_at, quality_status, quality_issues,
                   confidence, ai_reviewed_at, ai_reviewed_by, ai_evidence,
                   user_reviewed_at, user_approved, user_notes
            FROM artifacts
            WHERE quality_status = 'pending' AND is_current = TRUE
            ORDER BY captured_at DESC
            LIMIT %s
            """,
            (limit,),
        ).fetchall()

        return [_row_to_artifact(row) for row in rows]


def get_needs_user_review(limit: int = 50) -> list[dict[str, Any]]:
    """Get artifacts that need user review (low confidence or flagged).

    Returns:
        List of artifacts with quality_status = 'needs_review'
    """
    storage = get_connection_manager()

    with storage.connection() as conn:
        rows = conn.execute(
            """
            SELECT id, artifact_id, feature_id, criterion_id, artifact_type,
                   file_path, file_size_bytes, version, is_current,
                   captured_at, expires_at, quality_status, quality_issues,
                   confidence, ai_reviewed_at, ai_reviewed_by, ai_evidence,
                   user_reviewed_at, user_approved, user_notes
            FROM artifacts
            WHERE quality_status = 'needs_review' AND is_current = TRUE
            ORDER BY captured_at DESC
            LIMIT %s
            """,
            (limit,),
        ).fetchall()

        return [_row_to_artifact(row) for row in rows]


def get_with_user_notes(limit: int = 50) -> list[dict[str, Any]]:
    """Get artifacts that have user notes/feedback.

    Returns:
        List of artifacts with user_notes IS NOT NULL
    """
    storage = get_connection_manager()

    with storage.connection() as conn:
        rows = conn.execute(
            """
            SELECT id, artifact_id, feature_id, criterion_id, artifact_type,
                   file_path, file_size_bytes, version, is_current,
                   captured_at, expires_at, quality_status, quality_issues,
                   confidence, ai_reviewed_at, ai_reviewed_by, ai_evidence,
                   user_reviewed_at, user_approved, user_notes
            FROM artifacts
            WHERE user_notes IS NOT NULL AND is_current = TRUE
            ORDER BY user_reviewed_at DESC
            LIMIT %s
            """,
            (limit,),
        ).fetchall()

        return [_row_to_artifact(row) for row in rows]


def update_ai_review(
    artifact_id: str,
    quality_status: str,
    confidence: float,
    ai_evidence: str | None = None,
    quality_issues: list[str] | None = None,
    reviewed_by: str = "claude",
) -> bool:
    """Record AI review result for an artifact.

    Args:
        artifact_id: The artifact ID
        quality_status: New status ('passed', 'failed', 'needs_review')
        confidence: Confidence score 0.0-1.0
        ai_evidence: AI's reasoning/notes
        quality_issues: List of detected issues
        reviewed_by: Model/agent name

    Returns:
        True if updated successfully
    """
    storage = get_connection_manager()

    with storage.connection() as conn:
        result = conn.execute(
            """
            UPDATE artifacts
            SET quality_status = %s,
                confidence = %s,
                ai_evidence = %s,
                quality_issues = %s,
                ai_reviewed_at = NOW(),
                ai_reviewed_by = %s,
                updated_at = NOW()
            WHERE artifact_id = %s
            RETURNING id
            """,
            (
                quality_status,
                confidence,
                ai_evidence,
                json.dumps(quality_issues) if quality_issues else "[]",
                reviewed_by,
                artifact_id,
            ),
        ).fetchone()

        conn.commit()

        if result:
            logger.info(
                "ai_review_recorded",
                artifact_id=artifact_id,
                quality_status=quality_status,
                confidence=confidence,
            )
            return True

        return False


def update_user_review(
    artifact_id: str,
    approved: bool | None,
    notes: str | None = None,
) -> bool:
    """Record user review for an artifact.

    Args:
        artifact_id: The artifact ID
        approved: True=approved, False=rejected, None=pending
        notes: User feedback/notes

    Returns:
        True if updated successfully
    """
    storage = get_connection_manager()

    # Also update quality_status based on user decision
    new_status = None
    if approved is True:
        new_status = "passed"
    elif approved is False:
        new_status = "failed"

    with storage.connection() as conn:
        if new_status:
            result = conn.execute(
                """
                UPDATE artifacts
                SET user_approved = %s,
                    user_notes = %s,
                    user_reviewed_at = NOW(),
                    quality_status = %s,
                    updated_at = NOW()
                WHERE artifact_id = %s
                RETURNING id
                """,
                (approved, notes, new_status, artifact_id),
            ).fetchone()
        else:
            result = conn.execute(
                """
                UPDATE artifacts
                SET user_notes = %s,
                    user_reviewed_at = NOW(),
                    updated_at = NOW()
                WHERE artifact_id = %s
                RETURNING id
                """,
                (notes, artifact_id),
            ).fetchone()

        conn.commit()

        if result:
            logger.info(
                "user_review_recorded",
                artifact_id=artifact_id,
                approved=approved,
            )
            return True

        return False


def get_expired_artifacts() -> list[dict[str, Any]]:
    """Get artifacts that have expired and need refresh.

    Returns:
        List of expired current artifacts
    """
    storage = get_connection_manager()

    with storage.connection() as conn:
        rows = conn.execute(
            """
            SELECT id, artifact_id, feature_id, criterion_id, artifact_type,
                   file_path, file_size_bytes, version, is_current,
                   captured_at, expires_at, quality_status, quality_issues,
                   confidence, ai_reviewed_at, ai_reviewed_by, ai_evidence,
                   user_reviewed_at, user_approved, user_notes
            FROM artifacts
            WHERE expires_at < NOW() AND is_current = TRUE
            ORDER BY expires_at ASC
            """,
        ).fetchall()

        return [_row_to_artifact(row) for row in rows]


def cleanup_old_versions(
    feature_id: str | None = None,
    max_versions: int = MAX_VERSIONS_TO_KEEP,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Delete old artifact versions beyond retention limit.

    Args:
        feature_id: Optional filter by feature
        max_versions: Max versions to keep per criterion
        dry_run: If True, only report what would be deleted

    Returns:
        Summary of cleanup operation
    """
    storage = get_connection_manager()
    deleted_count = 0
    deleted_size = 0

    with storage.connection() as conn:
        # Get all feature/criterion pairs
        if feature_id:
            pairs = conn.execute(
                """
                SELECT DISTINCT feature_id, criterion_id
                FROM artifacts
                WHERE feature_id = %s
                """,
                (feature_id,),
            ).fetchall()
        else:
            pairs = conn.execute(
                """
                SELECT DISTINCT feature_id, criterion_id
                FROM artifacts
                """,
            ).fetchall()

        for feat_id, crit_id in pairs:
            # Get versions to delete (keep only max_versions)
            old_versions = conn.execute(
                """
                SELECT id, artifact_id, file_path, file_size_bytes, version
                FROM artifacts
                WHERE feature_id = %s AND criterion_id = %s
                ORDER BY version DESC
                OFFSET %s
                """,
                (feat_id, crit_id, max_versions),
            ).fetchall()

            for row in old_versions:
                art_id, _artifact_id, _file_path, size, version_val = row

                if not dry_run:
                    # Delete files - cast version_val to str for path construction
                    version_str = str(version_val) if version_val is not None else "0"
                    version_dir = (
                        ARTIFACTS_BASE_DIR / str(feat_id) / str(crit_id) / f"v{version_str}"
                    )
                    if version_dir.exists():
                        shutil.rmtree(version_dir)

                    # Delete database record
                    conn.execute(
                        "DELETE FROM artifacts WHERE id = %s",
                        (art_id,),
                    )

                deleted_count += 1
                # Cast size to int for addition
                if isinstance(size, (int, float)):
                    deleted_size += int(size)
                elif size is not None:
                    deleted_size += 0

        if not dry_run:
            conn.commit()

    logger.info(
        "cleanup_old_versions",
        deleted_count=deleted_count,
        deleted_size_bytes=deleted_size,
        dry_run=dry_run,
    )

    return {
        "deleted_count": deleted_count,
        "deleted_size_bytes": deleted_size,
        "dry_run": dry_run,
    }


def get_summary() -> dict[str, Any]:
    """Get summary statistics for artifacts.

    Returns:
        Dict with counts and breakdowns
    """
    storage = get_connection_manager()

    with storage.connection() as conn:
        # Total count
        total_row = conn.execute(
            "SELECT COUNT(*) FROM artifacts WHERE is_current = TRUE"
        ).fetchone()
        total = 0
        if total_row and isinstance(total_row[0], (int, float)):
            total = int(total_row[0])

        # By status
        status_rows = conn.execute(
            """
            SELECT quality_status, COUNT(*)
            FROM artifacts
            WHERE is_current = TRUE
            GROUP BY quality_status
            """,
        ).fetchall()
        by_status = {}
        for row in status_rows:
            if isinstance(row[1], (int, float)):
                by_status[str(row[0])] = int(row[1])

        # Expired count
        expired_row = conn.execute(
            """
            SELECT COUNT(*) FROM artifacts
            WHERE is_current = TRUE AND expires_at < NOW()
            """,
        ).fetchone()
        expired = 0
        if expired_row and isinstance(expired_row[0], (int, float)):
            expired = int(expired_row[0])

        # With user feedback
        notes_row = conn.execute(
            """
            SELECT COUNT(*) FROM artifacts
            WHERE is_current = TRUE AND user_notes IS NOT NULL
            """,
        ).fetchone()
        with_notes = 0
        if notes_row and isinstance(notes_row[0], (int, float)):
            with_notes = int(notes_row[0])

        # Total storage size
        size_row = conn.execute(
            """
            SELECT COALESCE(SUM(file_size_bytes), 0) FROM artifacts
            """
        ).fetchone()
        total_size = 0
        if size_row and isinstance(size_row[0], (int, float)):
            total_size = int(size_row[0])

        return {
            "total_current": total,
            "by_status": by_status,
            "expired_count": expired,
            "with_user_notes": with_notes,
            "total_storage_bytes": total_size,
        }


def read_evidence_file(
    feature_id: str,
    criterion_id: str,
    version: int | None = None,
) -> dict[str, Any] | None:
    """Read the evidence.json file for an artifact.

    Args:
        feature_id: Feature ID
        criterion_id: Criterion ID
        version: Optional version (defaults to current)

    Returns:
        Parsed evidence.json data or None
    """
    if version:
        evidence_path = (
            ARTIFACTS_BASE_DIR / feature_id / criterion_id / f"v{version}" / "evidence.json"
        )
    else:
        evidence_path = ARTIFACTS_BASE_DIR / feature_id / criterion_id / "current" / "evidence.json"

    if not evidence_path.exists():
        return None

    try:
        with evidence_path.open() as f:
            data: dict[str, Any] = json.load(f)
            return data
    except Exception as e:
        logger.error("read_evidence_failed", path=str(evidence_path), error=str(e))
        return None


def _row_to_artifact(row: tuple[Any, ...]) -> dict[str, Any]:
    """Convert database row to artifact dict."""
    return {
        "id": row[0],
        "artifact_id": row[1],
        "feature_id": row[2],
        "criterion_id": row[3],
        "artifact_type": row[4],
        "file_path": row[5],
        "file_size_bytes": row[6],
        "version": row[7],
        "is_current": row[8],
        "captured_at": row[9].isoformat() if row[9] else None,
        "expires_at": row[10].isoformat() if row[10] else None,
        "quality_status": row[11],
        "quality_issues": row[12] if row[12] else [],
        "confidence": row[13],
        "ai_reviewed_at": row[14].isoformat() if row[14] else None,
        "ai_reviewed_by": row[15],
        "ai_evidence": row[16],
        "user_reviewed_at": row[17].isoformat() if row[17] else None,
        "user_approved": row[18],
        "user_notes": row[19],
    }
