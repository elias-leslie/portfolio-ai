"""QA issue scanner service."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.logging_config import get_logger

if TYPE_CHECKING:
    from app.storage.connection import ConnectionManager

logger = get_logger(__name__)


@dataclass
class QAIssue:
    """QA issue dataclass."""

    issue_id: str
    category: str
    severity: str
    description: str
    file_path: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    detection_source: str = "custom_scanner"


class QAScanner:
    """Unified QA issue detection.

    Scans codebase and database for quality issues including dead code,
    orphan files, DRY violations, security issues, schema drift, stale data,
    bloat, and test gaps.
    """

    def __init__(self, connection_mgr: ConnectionManager | None = None) -> None:
        """Initialize QA scanner.

        Args:
            connection_mgr: ConnectionManager instance for database access.
                          If None, uses get_connection_manager() to get default.
        """
        if connection_mgr is None:
            from app.storage.connection import get_connection_manager

            connection_mgr = get_connection_manager()
        self.conn_mgr = connection_mgr
        self.project_root = Path(__file__).parent.parent.parent.parent

    def scan_all(self) -> list[QAIssue]:
        """Run all scanners and return list of QA issues.

        Returns:
            List of QAIssue dataclasses
        """
        logger.info("qa_scan_started")
        issues = []

        try:
            issues += self.scan_dead_code()
        except Exception as e:
            logger.error("dead_code_scan_failed", error=str(e))

        try:
            issues += self.scan_orphan_files()
        except Exception as e:
            logger.error("orphan_files_scan_failed", error=str(e))

        try:
            issues += self.scan_dry_violations()
        except Exception as e:
            logger.error("dry_violations_scan_failed", error=str(e))

        try:
            issues += self.scan_security()
        except Exception as e:
            logger.error("security_scan_failed", error=str(e))

        try:
            issues += self.scan_schema_drift()
        except Exception as e:
            logger.error("schema_drift_scan_failed", error=str(e))

        try:
            issues += self.scan_stale_data()
        except Exception as e:
            logger.error("stale_data_scan_failed", error=str(e))

        try:
            issues += self.scan_bloat()
        except Exception as e:
            logger.error("bloat_scan_failed", error=str(e))

        try:
            issues += self.scan_test_gaps()
        except Exception as e:
            logger.error("test_gaps_scan_failed", error=str(e))

        logger.info("qa_scan_complete", total_issues=len(issues))
        return issues

    def scan_dead_code(self) -> list[QAIssue]:
        """Run ruff with F401, F841 rules to detect dead code.

        Returns:
            List of QAIssue objects for unused imports and variables
        """
        logger.info("scanning_dead_code")
        issues: list[QAIssue] = []

        backend_path = self.project_root / "backend" / "app"
        if not backend_path.exists():
            logger.warning("backend_path_not_found", path=str(backend_path))
            return issues

        try:
            result = subprocess.run(
                [
                    "ruff",
                    "check",
                    str(backend_path),
                    "--select",
                    "F401,F841",
                    "--output-format",
                    "json",
                ],
                capture_output=True,
                text=True,
                cwd=str(self.project_root),
                timeout=60,
                check=False,
            )

            if result.stdout:
                ruff_results = json.loads(result.stdout)
                for item in ruff_results:
                    file_path = item.get("filename", "")
                    location = item.get("location", {})
                    rule_code = item.get("code", "")
                    message = item.get("message", "")

                    category = "dead_code"
                    if rule_code == "F401":
                        description = f"Unused import: {message}"
                    elif rule_code == "F841":
                        description = f"Unused variable: {message}"
                    else:
                        description = message

                    issue_id = self._generate_temp_id(issues)
                    issues.append(
                        QAIssue(
                            issue_id=issue_id,
                            category=category,
                            severity="medium",
                            description=description,
                            file_path=file_path,
                            line_start=location.get("row"),
                            line_end=location.get("row"),
                            detection_source="ruff",
                        )
                    )

        except subprocess.TimeoutExpired:
            logger.error("ruff_scan_timeout")
        except json.JSONDecodeError as e:
            logger.error("ruff_json_parse_failed", error=str(e))
        except Exception as e:
            logger.error("ruff_scan_failed", error=str(e))

        logger.info("dead_code_scan_complete", count=len(issues))
        return issues

    def scan_orphan_files(self) -> list[QAIssue]:
        """Find .py files not imported anywhere.

        Returns:
            List of QAIssue objects for orphan files
        """
        logger.info("scanning_orphan_files")
        issues: list[QAIssue] = []

        backend_path = self.project_root / "backend" / "app"
        if not backend_path.exists():
            logger.warning("backend_path_not_found", path=str(backend_path))
            return issues

        # Known entry points that don't need to be imported
        entry_points = {
            "main.py",
            "__init__.py",
            "celery_app.py",
            "celery_config.py",
            "constants.py",
            "logging_config.py",
        }

        try:
            # Get all Python files
            all_files = set(backend_path.rglob("*.py"))

            # Build set of imported modules by scanning all files
            imported = set()
            for py_file in all_files:
                try:
                    content = py_file.read_text()
                    # Simple import detection (not AST-based, basic version)
                    for raw_line in content.split("\n"):
                        line = raw_line.strip()
                        if line.startswith("from ") or line.startswith("import "):
                            # Extract module references
                            parts = line.split()
                            if len(parts) > 1:
                                module = parts[1].replace(".", "/")
                                imported.add(module)
                except Exception:
                    continue

            # Find orphans
            for py_file in all_files:
                relative = py_file.relative_to(backend_path)
                if relative.name in entry_points:
                    continue

                # Check if this file's path appears in imports
                file_module = str(relative.with_suffix("")).replace(os.sep, "/")
                is_imported = any(file_module in imp for imp in imported)

                if not is_imported:
                    issue_id = self._generate_temp_id(issues)
                    issues.append(
                        QAIssue(
                            issue_id=issue_id,
                            category="orphan_file",
                            severity="high",
                            description=f"File not imported anywhere: {relative}",
                            file_path=str(py_file),
                            detection_source="custom_scanner",
                        )
                    )

        except Exception as e:
            logger.error("orphan_files_scan_failed", error=str(e))

        logger.info("orphan_files_scan_complete", count=len(issues))
        return issues

    def scan_dry_violations(self) -> list[QAIssue]:
        """Find duplicate code blocks.

        Placeholder for future jscpd integration.

        Returns:
            Empty list (not implemented yet)
        """
        logger.info("scanning_dry_violations")
        # Placeholder for future jscpd integration
        return []

    def scan_security(self) -> list[QAIssue]:
        """Check for security issues.

        Returns:
            List of QAIssue objects for security findings
        """
        logger.info("scanning_security")
        issues: list[QAIssue] = []

        security_script = self.project_root / "scripts" / "check-security.sh"
        if not security_script.exists():
            logger.info("security_script_not_found", path=str(security_script))
            return issues

        try:
            result = subprocess.run(
                ["bash", str(security_script)],
                capture_output=True,
                text=True,
                cwd=str(self.project_root),
                timeout=120,
                check=False,
            )

            if result.returncode != 0 and result.stderr:
                issue_id = self._generate_temp_id(issues)
                issues.append(
                    QAIssue(
                        issue_id=issue_id,
                        category="security",
                        severity="critical",
                        description=f"Security check failed: {result.stderr[:500]}",
                        detection_source="check-security.sh",
                    )
                )

        except subprocess.TimeoutExpired:
            logger.error("security_scan_timeout")
        except Exception as e:
            logger.error("security_scan_failed", error=str(e))

        logger.info("security_scan_complete", count=len(issues))
        return issues

    def scan_schema_drift(self) -> list[QAIssue]:
        """Query db_capabilities for orphaned tables.

        Returns:
            List of QAIssue objects for schema drift issues
        """
        logger.info("scanning_schema_drift")
        issues: list[QAIssue] = []

        try:
            with self.conn_mgr.connection() as conn:
                # Find tables with legacy or orphaned health status
                result = conn.execute(
                    """
                    SELECT table_name, health_status, row_count
                    FROM db_capabilities
                    WHERE health_status IN ('legacy', 'orphaned')
                    ORDER BY table_name
                    """
                )
                rows = result.fetchall()

                for row in rows:
                    table_name = row[0]
                    health_status = row[1]
                    row_count = row[2]

                    issue_id = self._generate_temp_id(issues)
                    description = (
                        f"Table '{table_name}' has {health_status} status with {row_count} rows"
                    )

                    issues.append(
                        QAIssue(
                            issue_id=issue_id,
                            category="schema_drift",
                            severity="high",
                            description=description,
                            detection_source="db_capabilities",
                        )
                    )

        except Exception as e:
            logger.error("schema_drift_scan_failed", error=str(e))

        logger.info("schema_drift_scan_complete", count=len(issues))
        return issues

    def scan_stale_data(self) -> list[QAIssue]:
        """Query db_capabilities for stale freshness_status.

        Returns:
            List of QAIssue objects for stale data issues
        """
        logger.info("scanning_stale_data")
        issues: list[QAIssue] = []

        try:
            with self.conn_mgr.connection() as conn:
                result = conn.execute(
                    """
                    SELECT table_name, freshness_status, days_since_update
                    FROM db_capabilities
                    WHERE freshness_status IN ('stale', 'critical')
                    AND health_status = 'active'
                    ORDER BY days_since_update DESC
                    """
                )
                rows = result.fetchall()

                for row in rows:
                    table_name = row[0]
                    freshness_status = row[1]
                    days_since_update = row[2]

                    issue_id = self._generate_temp_id(issues)
                    description = (
                        f"Table '{table_name}' has {freshness_status} data "
                        f"({days_since_update} days old)"
                    )

                    issues.append(
                        QAIssue(
                            issue_id=issue_id,
                            category="stale_data",
                            severity="medium",
                            description=description,
                            detection_source="db_capabilities",
                        )
                    )

        except Exception as e:
            logger.error("stale_data_scan_failed", error=str(e))

        logger.info("stale_data_scan_complete", count=len(issues))
        return issues

    def scan_bloat(self) -> list[QAIssue]:
        """Check file sizes > 500 lines and functions > 50 lines.

        Returns:
            List of QAIssue objects for bloat issues
        """
        logger.info("scanning_bloat")
        issues: list[QAIssue] = []

        backend_path = self.project_root / "backend" / "app"
        if not backend_path.exists():
            logger.warning("backend_path_not_found", path=str(backend_path))
            return issues

        try:
            for py_file in backend_path.rglob("*.py"):
                try:
                    lines = py_file.read_text().split("\n")
                    line_count = len(lines)

                    if line_count > 500:
                        issue_id = self._generate_temp_id(issues)
                        issues.append(
                            QAIssue(
                                issue_id=issue_id,
                                category="bloat",
                                severity="low",
                                description=f"File exceeds 500 lines ({line_count} lines)",
                                file_path=str(py_file),
                                detection_source="custom_scanner",
                            )
                        )

                except Exception:
                    continue

        except Exception as e:
            logger.error("bloat_scan_failed", error=str(e))

        logger.info("bloat_scan_complete", count=len(issues))
        return issues

    def scan_test_gaps(self) -> list[QAIssue]:
        """Query feature_capabilities for features with test_count=0 and verified status.

        Verified = tasks complete (0 incomplete) AND all criteria passed.
        acceptance_criteria is JSONB array in feature_capabilities table.

        Returns:
            List of QAIssue objects for test gap issues
        """
        logger.info("scanning_test_gaps")
        issues: list[QAIssue] = []

        try:
            with self.conn_mgr.connection() as conn:
                # Verified features: 0 incomplete tasks AND all criteria passed (JSONB)
                result = conn.execute(
                    """
                    SELECT fc.feature_id, fc.name
                    FROM feature_capabilities fc
                    WHERE COALESCE(fc.test_count, 0) = 0
                      AND NOT EXISTS (
                          SELECT 1 FROM feature_tasks ft
                          WHERE ft.feature_id = fc.id AND ft.completed = false
                      )
                      AND jsonb_array_length(COALESCE(fc.acceptance_criteria, '[]'::jsonb)) > 0
                      AND NOT EXISTS (
                          SELECT 1 FROM jsonb_array_elements(COALESCE(fc.acceptance_criteria, '[]'::jsonb)) elem
                          WHERE (elem->>'passed')::boolean IS DISTINCT FROM true
                      )
                    ORDER BY fc.feature_id
                    """
                )
                rows = result.fetchall()

                for row in rows:
                    feature_id = row[0]
                    feature_name = row[1]

                    issue_id = self._generate_temp_id(issues)
                    description = (
                        f"Feature '{feature_id}' ({feature_name}) "
                        f"marked as passing but has no tests"
                    )

                    issues.append(
                        QAIssue(
                            issue_id=issue_id,
                            category="test_gap",
                            severity="high",
                            description=description,
                            detection_source="feature_capabilities",
                        )
                    )

        except Exception as e:
            logger.error("test_gaps_scan_failed", error=str(e))

        logger.info("test_gaps_scan_complete", count=len(issues))
        return issues

    def upsert_issues(self, issues: list[QAIssue]) -> int:
        """Insert new issues or update last_detected_at for existing.

        Args:
            issues: List of QAIssue objects to upsert

        Returns:
            Number of issues inserted/updated
        """
        if not issues:
            logger.info("no_qa_issues_to_upsert")
            return 0

        logger.info("upserting_qa_issues", count=len(issues))

        # Generate proper issue IDs
        issues_with_ids = []
        for issue in issues:
            if issue.issue_id.startswith("TEMP-"):
                issue.issue_id = self._generate_issue_id()
            issues_with_ids.append(issue)

        with self.conn_mgr.connection() as conn:
            upserted = 0
            for issue in issues_with_ids:
                # Check if issue exists by file_path + line_start + category
                result = conn.execute(
                    """
                    SELECT issue_id FROM qa_issues
                    WHERE file_path = %s
                    AND line_start = %s
                    AND category = %s
                    AND resolved_at IS NULL
                    """,
                    [issue.file_path, issue.line_start, issue.category],
                )
                existing = result.fetchone()

                if existing:
                    # Update last_detected_at
                    conn.execute(
                        """
                        UPDATE qa_issues
                        SET last_detected_at = %s, updated_at = %s
                        WHERE issue_id = %s
                        """,
                        [datetime.now(UTC), datetime.now(UTC), existing[0]],
                    )
                else:
                    # Insert new issue
                    conn.execute(
                        """
                        INSERT INTO qa_issues (
                            issue_id, category, severity, file_path,
                            line_start, line_end, description, detection_source,
                            first_detected_at, last_detected_at, created_at, updated_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        [
                            issue.issue_id,
                            issue.category,
                            issue.severity,
                            issue.file_path,
                            issue.line_start,
                            issue.line_end,
                            issue.description,
                            issue.detection_source,
                            datetime.now(UTC),
                            datetime.now(UTC),
                            datetime.now(UTC),
                            datetime.now(UTC),
                        ],
                    )
                conn.commit()
                upserted += 1

        logger.info("qa_issues_upserted", count=upserted)
        return upserted

    def auto_resolve_missing(self, detected_issues: list[QAIssue]) -> int:
        """Mark issues as resolved if no longer detected.

        Args:
            detected_issues: List of issues found in current scan

        Returns:
            Number of issues auto-resolved
        """
        logger.info("auto_resolving_missing_issues")

        # Build set of current issue signatures
        current_signatures = {
            (issue.file_path, issue.line_start, issue.category) for issue in detected_issues
        }

        with self.conn_mgr.connection() as conn:
            # Get all unresolved issues
            result = conn.execute(
                """
                SELECT issue_id, file_path, line_start, category
                FROM qa_issues
                WHERE resolved_at IS NULL
                """
            )
            unresolved = result.fetchall()

            resolved_count = 0
            for row in unresolved:
                issue_id = row[0]
                file_path = row[1]
                line_start = row[2]
                category = row[3]

                signature = (file_path, line_start, category)
                if signature not in current_signatures:
                    # Issue no longer detected, mark as resolved
                    conn.execute(
                        """
                        UPDATE qa_issues
                        SET resolved_at = %s,
                            resolved_by = 'auto',
                            resolution_notes = 'Auto-resolved (no longer detected)',
                            updated_at = %s
                        WHERE issue_id = %s
                        """,
                        [datetime.now(UTC), datetime.now(UTC), issue_id],
                    )
                    conn.commit()
                    resolved_count += 1

        logger.info("auto_resolved_issues", count=resolved_count)
        return resolved_count

    def take_snapshot(self) -> dict[str, Any]:
        """Create daily snapshot for trend tracking.

        Returns:
            Dict with snapshot statistics
        """
        logger.info("taking_qa_snapshot")

        with self.conn_mgr.connection() as conn:
            # Get current stats
            result = conn.execute(
                """
                SELECT
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE severity = 'critical') as critical,
                    COUNT(*) FILTER (WHERE severity = 'high') as high,
                    COUNT(*) FILTER (WHERE severity = 'medium') as medium,
                    COUNT(*) FILTER (WHERE severity = 'low') as low
                FROM qa_issues
                WHERE resolved_at IS NULL
                """
            )
            row = result.fetchone()
            total = row[0] if row else 0
            critical = row[1] if row else 0
            high = row[2] if row else 0
            medium = row[3] if row else 0
            low = row[4] if row else 0

            # Get by category
            result = conn.execute(
                """
                SELECT category, COUNT(*) as count
                FROM qa_issues
                WHERE resolved_at IS NULL
                GROUP BY category
                """
            )
            by_category = {row[0]: row[1] for row in result.fetchall()}

            # Count issues added today
            result = conn.execute(
                """
                SELECT COUNT(*) FROM qa_issues
                WHERE DATE(first_detected_at) = CURRENT_DATE
                """
            )
            row = result.fetchone()
            issues_added = row[0] if row else 0

            # Count issues resolved today
            result = conn.execute(
                """
                SELECT COUNT(*) FROM qa_issues
                WHERE DATE(resolved_at) = CURRENT_DATE
                """
            )
            row = result.fetchone()
            issues_resolved = row[0] if row else 0

            # Get codebase metrics
            backend_path = self.project_root / "backend" / "app"
            lines_of_code = 0
            file_count = 0
            if backend_path.exists():
                for py_file in backend_path.rglob("*.py"):
                    try:
                        lines_of_code += len(py_file.read_text().split("\n"))
                        file_count += 1
                    except Exception:
                        continue

            # Get table count
            result = conn.execute("SELECT COUNT(*) FROM db_capabilities")
            row = result.fetchone()
            table_count = row[0] if row else 0

            # Insert snapshot
            conn.execute(
                """
                INSERT INTO qa_snapshots (
                    snapshot_date, total_issues, critical_count, high_count,
                    medium_count, low_count, by_category, issues_added,
                    issues_resolved, lines_of_code, file_count, table_count,
                    created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (snapshot_date) DO UPDATE SET
                    total_issues = EXCLUDED.total_issues,
                    critical_count = EXCLUDED.critical_count,
                    high_count = EXCLUDED.high_count,
                    medium_count = EXCLUDED.medium_count,
                    low_count = EXCLUDED.low_count,
                    by_category = EXCLUDED.by_category,
                    issues_added = EXCLUDED.issues_added,
                    issues_resolved = EXCLUDED.issues_resolved,
                    lines_of_code = EXCLUDED.lines_of_code,
                    file_count = EXCLUDED.file_count,
                    table_count = EXCLUDED.table_count
                """,
                [
                    datetime.now(UTC).date().isoformat(),
                    total,
                    critical,
                    high,
                    medium,
                    low,
                    json.dumps(by_category),
                    issues_added,
                    issues_resolved,
                    lines_of_code,
                    file_count,
                    table_count,
                    datetime.now(UTC),
                ],
            )
            conn.commit()

        snapshot_data = {
            "total": total,
            "critical": critical,
            "high": high,
            "medium": medium,
            "low": low,
            "by_category": by_category,
            "issues_added": issues_added,
            "issues_resolved": issues_resolved,
            "lines_of_code": lines_of_code,
            "file_count": file_count,
            "table_count": table_count,
        }

        logger.info("qa_snapshot_complete", **snapshot_data)
        return snapshot_data

    def _generate_temp_id(self, existing_issues: list[QAIssue]) -> str:
        """Generate temporary issue ID for in-memory use.

        Args:
            existing_issues: List of existing issues in current batch

        Returns:
            Temporary issue ID like TEMP-001
        """
        return f"TEMP-{len(existing_issues) + 1:03d}"

    def _generate_issue_id(self) -> str:
        """Generate next issue ID by querying max from database.

        Returns:
            Issue ID like QA-001, QA-002, etc.
        """
        with self.conn_mgr.connection() as conn:
            result = conn.execute(
                """
                SELECT issue_id FROM qa_issues
                ORDER BY id DESC
                LIMIT 1
                """
            )
            row = result.fetchone()

            if row and row[0]:
                last_id = row[0]
                # Parse number from QA-XXX
                try:
                    if isinstance(last_id, str):
                        num = int(last_id.split("-")[1])
                        next_num = num + 1
                    else:
                        next_num = 1
                except (IndexError, ValueError):
                    next_num = 1
            else:
                next_num = 1

            return f"QA-{next_num:03d}"
