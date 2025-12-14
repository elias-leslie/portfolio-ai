"""File scanner for codebase complexity audit."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.logging_config import get_logger
from app.storage import get_storage

logger = get_logger(__name__)

# Directories to skip during scan
SKIP_DIRS = {
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".git",
    ".next",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "data",
    "solution_state",
    ".beads",
}

# File extensions to skip
SKIP_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".so",
    ".dll",
    ".exe",
    ".bin",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".svg",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".mp3",
    ".mp4",
    ".wav",
    ".pdf",
    ".zip",
    ".tar",
    ".gz",
    ".lock",
}

# Bloat thresholds by extension: (warning_loc, critical_loc)
BLOAT_THRESHOLDS: dict[str, tuple[int, int]] = {
    ".py": (500, 1000),
    ".ts": (400, 800),
    ".tsx": (300, 600),
    ".js": (400, 800),
    ".jsx": (300, 600),
    ".sql": (200, 500),
    ".md": (500, 1000),
    ".css": (400, 800),
    ".scss": (400, 800),
}


@dataclass
class FileStats:
    """Statistics for a single file or directory."""

    path: str
    is_directory: bool
    extension: str | None
    size_bytes: int
    lines_of_code: int
    file_count: int | None  # Only for directories
    total_loc: int | None  # Only for directories
    bloat_level: str | None  # null, 'warning', 'critical'
    last_modified: datetime


class FileScanner:
    """Scans codebase and produces file audit metrics."""

    def __init__(self, root_path: str = "/home/kasadis/portfolio-ai") -> None:
        self.root_path = Path(root_path)
        self.storage = get_storage()

    def scan(self) -> dict[str, Any]:
        """Scan the codebase and store results in database."""
        logger.info("file_scan_started", root=str(self.root_path))

        files: list[FileStats] = []
        dirs: dict[str, dict[str, Any]] = {}  # path -> {file_count, total_loc}

        for root, dirnames, filenames in os.walk(self.root_path):
            # Skip excluded directories
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]

            rel_root = Path(root).relative_to(self.root_path)

            for filename in filenames:
                file_path = Path(root) / filename
                rel_path = str(rel_root / filename)

                # Skip by extension
                ext = file_path.suffix.lower()
                if ext in SKIP_EXTENSIONS:
                    continue

                try:
                    stats = self._get_file_stats(file_path, rel_path, ext)
                    if stats:
                        files.append(stats)

                        # Aggregate to parent directories
                        self._aggregate_to_parents(rel_path, stats, dirs)
                except Exception as e:
                    logger.warning("file_scan_error", path=rel_path, error=str(e))

        # Convert directory aggregates to FileStats
        dir_stats = self._finalize_directories(dirs)

        # Store in database
        self._store_results(files, dir_stats)

        summary = {
            "total_files": len(files),
            "total_directories": len(dir_stats),
            "total_loc": sum(f.lines_of_code for f in files),
            "bloat_warnings": sum(1 for f in files if f.bloat_level == "warning"),
            "bloat_critical": sum(1 for f in files if f.bloat_level == "critical"),
            "scanned_at": datetime.now(UTC).isoformat(),
        }

        logger.info("file_scan_completed", **summary)
        return summary

    def _get_file_stats(self, file_path: Path, rel_path: str, ext: str) -> FileStats | None:
        """Get statistics for a single file."""
        try:
            stat = file_path.stat()
            size_bytes = stat.st_size
            last_modified = datetime.fromtimestamp(stat.st_mtime, tz=UTC)

            # Count lines of code
            try:
                with file_path.open(encoding="utf-8", errors="ignore") as f:
                    lines = sum(1 for _ in f)
            except Exception:
                lines = 0

            # Determine bloat level
            bloat_level = self._calculate_bloat(ext, lines)

            return FileStats(
                path=rel_path,
                is_directory=False,
                extension=ext if ext else None,
                size_bytes=size_bytes,
                lines_of_code=lines,
                file_count=None,
                total_loc=None,
                bloat_level=bloat_level,
                last_modified=last_modified,
            )
        except Exception:
            return None

    def _calculate_bloat(self, ext: str, lines: int) -> str | None:
        """Calculate bloat level based on file type and line count."""
        thresholds = BLOAT_THRESHOLDS.get(ext)
        if not thresholds:
            return None

        warning, critical = thresholds
        if lines >= critical:
            return "critical"
        if lines >= warning:
            return "warning"
        return None

    def _aggregate_to_parents(
        self, rel_path: str, stats: FileStats, dirs: dict[str, dict[str, Any]]
    ) -> None:
        """Aggregate file stats to all parent directories."""
        path_parts = Path(rel_path).parts[:-1]  # Exclude filename

        for i in range(len(path_parts)):
            dir_path = str(Path(*path_parts[: i + 1]))
            if dir_path not in dirs:
                dirs[dir_path] = {"file_count": 0, "total_loc": 0, "total_size": 0}
            dirs[dir_path]["file_count"] += 1
            dirs[dir_path]["total_loc"] += stats.lines_of_code
            dirs[dir_path]["total_size"] += stats.size_bytes

    def _finalize_directories(self, dirs: dict[str, dict[str, Any]]) -> list[FileStats]:
        """Convert directory aggregates to FileStats."""
        result = []
        now = datetime.now(UTC)

        for dir_path, data in dirs.items():
            file_count = data["file_count"]

            # No bloat indicators for directories - only files have meaningful bloat
            result.append(
                FileStats(
                    path=dir_path,
                    is_directory=True,
                    extension=None,
                    size_bytes=data.get("total_size", 0),
                    lines_of_code=0,
                    file_count=file_count,
                    total_loc=data["total_loc"],
                    bloat_level=None,
                    last_modified=now,
                )
            )

        return result

    def _store_results(self, files: list[FileStats], directories: list[FileStats]) -> None:
        """Store scan results in database."""
        all_stats = files + directories

        with self.storage.connection() as conn:
            # Clear existing data
            conn.execute("DELETE FROM file_audit")

            # Insert new data
            for stat in all_stats:
                conn.execute(
                    """
                    INSERT INTO file_audit (
                        path, is_directory, extension, size_bytes, lines_of_code,
                        file_count, total_loc, bloat_level, last_modified, scanned_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())
                    """,
                    [
                        stat.path,
                        stat.is_directory,
                        stat.extension,
                        stat.size_bytes,
                        stat.lines_of_code,
                        stat.file_count,
                        stat.total_loc,
                        stat.bloat_level,
                        stat.last_modified,
                    ],
                )
            conn.commit()

        logger.info(
            "file_audit_stored",
            files=len(files),
            directories=len(directories),
        )

    def get_summary(self) -> dict[str, Any]:
        """Get summary statistics from stored audit data."""
        with self.storage.connection() as conn:
            # Total counts
            totals = conn.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE NOT is_directory) as total_files,
                    COUNT(*) FILTER (WHERE is_directory) as total_directories,
                    SUM(lines_of_code) FILTER (WHERE NOT is_directory) as total_loc,
                    COUNT(*) FILTER (WHERE bloat_level = 'warning') as bloat_warnings,
                    COUNT(*) FILTER (WHERE bloat_level = 'critical') as bloat_critical,
                    MAX(scanned_at) as last_scan
                FROM file_audit
                """
            ).fetchone()

            # LOC by extension
            by_extension = conn.execute(
                """
                SELECT extension, COUNT(*) as count, SUM(lines_of_code) as loc
                FROM file_audit
                WHERE NOT is_directory AND extension IS NOT NULL
                GROUP BY extension
                ORDER BY loc DESC
                LIMIT 10
                """
            ).fetchall()

            return {
                "total_files": totals[0] or 0,
                "total_directories": totals[1] or 0,
                "total_loc": totals[2] or 0,
                "bloat_warnings": totals[3] or 0,
                "bloat_critical": totals[4] or 0,
                "last_scan": totals[5].isoformat() if totals[5] else None,
                "by_extension": [
                    {"extension": row[0], "count": row[1], "loc": row[2]} for row in by_extension
                ],
            }

    def search(
        self,
        path_prefix: str | None = None,
        extension: str | None = None,
        bloat: str | None = None,
        is_directory: bool | None = None,
        sort_by: str = "path",
        sort_dir: str = "asc",
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Search file audit data with filters."""
        conditions = []
        params: list[Any] = []
        param_idx = 1

        if path_prefix:
            conditions.append(f"path LIKE ${param_idx}")
            params.append(f"{path_prefix}%")
            param_idx += 1

        if extension:
            conditions.append(f"extension = ${param_idx}")
            params.append(extension if extension.startswith(".") else f".{extension}")
            param_idx += 1

        if bloat:
            conditions.append(f"bloat_level = ${param_idx}")
            params.append(bloat)
            param_idx += 1

        if is_directory is not None:
            conditions.append(f"is_directory = ${param_idx}")
            params.append(is_directory)
            param_idx += 1

        where_clause = " AND ".join(conditions) if conditions else "TRUE"

        # Validate sort column
        valid_sorts = {"path", "lines_of_code", "size_bytes", "file_count", "total_loc"}
        if sort_by not in valid_sorts:
            sort_by = "path"
        sort_order = "DESC" if sort_dir.lower() == "desc" else "ASC"

        with self.storage.connection() as conn:
            # Get total count
            count_result = conn.execute(
                f"SELECT COUNT(*) FROM file_audit WHERE {where_clause}", params
            ).fetchone()
            total = count_result[0] if count_result else 0

            # Get paginated results
            params.extend([limit, offset])
            results = conn.execute(
                f"""
                SELECT path, is_directory, extension, size_bytes, lines_of_code,
                       file_count, total_loc, bloat_level, last_modified, scanned_at
                FROM file_audit
                WHERE {where_clause}
                ORDER BY {sort_by} {sort_order}
                LIMIT ${param_idx} OFFSET ${param_idx + 1}
                """,
                params,
            ).fetchall()

            items = [
                {
                    "path": row[0],
                    "is_directory": row[1],
                    "extension": row[2],
                    "size_bytes": row[3],
                    "lines_of_code": row[4],
                    "file_count": row[5],
                    "total_loc": row[6],
                    "bloat_level": row[7],
                    "last_modified": row[8].isoformat() if row[8] else None,
                    "scanned_at": row[9].isoformat() if row[9] else None,
                }
                for row in results
            ]

            return {"items": items, "total": total, "limit": limit, "offset": offset}

    def get_tree(self, path_prefix: str = "", depth: int | None = None) -> list[dict[str, Any]]:
        """Get hierarchical tree structure for UI.

        Args:
            path_prefix: Filter to directories under this path
            depth: If set, only return immediate children (1 level deep)
        """
        with self.storage.connection() as conn:
            if depth == 1:
                # Lazy loading: return only immediate children
                if path_prefix:
                    # Children of a specific directory
                    # Match: path_prefix/child (no further slashes)
                    results = conn.execute(
                        """
                        SELECT path, file_count, total_loc, bloat_level
                        FROM file_audit
                        WHERE is_directory = TRUE
                          AND path LIKE $1
                          AND path NOT LIKE $2
                        ORDER BY path
                        """,
                        [f"{path_prefix}/%", f"{path_prefix}/%/%"],
                    ).fetchall()
                else:
                    # Root level only (no slashes in path)
                    results = conn.execute(
                        """
                        SELECT path, file_count, total_loc, bloat_level
                        FROM file_audit
                        WHERE is_directory = TRUE
                          AND path NOT LIKE '%/%'
                        ORDER BY path
                        """
                    ).fetchall()
            # Original behavior: return all matching directories
            elif path_prefix:
                results = conn.execute(
                    """
                        SELECT path, file_count, total_loc, bloat_level
                        FROM file_audit
                        WHERE is_directory = TRUE AND path LIKE $1
                        ORDER BY path
                        """,
                    [f"{path_prefix}%"],
                ).fetchall()
            else:
                results = conn.execute(
                    """
                        SELECT path, file_count, total_loc, bloat_level
                        FROM file_audit
                        WHERE is_directory = TRUE
                        ORDER BY path
                        """
                ).fetchall()

            # Count immediate subdirectories for each result
            subdir_counts: dict[str, int] = {}
            for row in results:
                path = row[0]
                count_result = conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM file_audit
                    WHERE is_directory = TRUE
                      AND path LIKE $1
                      AND path NOT LIKE $2
                    """,
                    [f"{path}/%", f"{path}/%/%"],
                ).fetchone()
                subdir_counts[path] = count_result[0] if count_result else 0

            return [
                {
                    "path": row[0],
                    "file_count": row[1],
                    "total_loc": row[2],
                    "bloat_level": row[3],
                    "subdir_count": subdir_counts.get(row[0], 0),
                }
                for row in results
            ]

    def get_children(
        self,
        path: str = "",
        sort_by: str = "name",
        sort_dir: str = "asc",
        folders_first: bool = True,
        include_files: bool = True,
    ) -> list[dict[str, Any]]:
        """Get immediate children (folders and files) for explorer view.

        Args:
            path: Parent path (empty for root)
            sort_by: Sort field (name, loc, size, modified)
            sort_dir: Sort direction (asc, desc)
            folders_first: Whether to show folders before files
            include_files: Whether to include files (False = folders only)
        """
        with self.storage.connection() as conn:
            # Build path matching conditions
            if path:
                # Children of a specific directory
                path_like = f"{path}/%"
                path_not_like = f"{path}/%/%"
            else:
                # Root level (no slashes)
                path_like = "%"
                path_not_like = "%/%"

            # Map sort field to column
            sort_map = {
                "name": "path",
                "loc": "COALESCE(total_loc, lines_of_code)",
                "size": "size_bytes",
                "modified": "last_modified",
                "files": "file_count",
            }
            sort_col = sort_map.get(sort_by, "path")
            sort_order = "DESC" if sort_dir.lower() == "desc" else "ASC"

            # Build ORDER BY clause
            if folders_first:
                order_by = f"is_directory DESC, {sort_col} {sort_order}"
            else:
                order_by = f"{sort_col} {sort_order}"

            # Query for children
            if path:
                query = f"""
                    SELECT path, is_directory, extension, size_bytes, lines_of_code,
                           file_count, total_loc, bloat_level, last_modified
                    FROM file_audit
                    WHERE path LIKE $1 AND path NOT LIKE $2
                    {"AND is_directory = TRUE" if not include_files else ""}
                    ORDER BY {order_by}
                """
                results = conn.execute(query, [path_like, path_not_like]).fetchall()
            else:
                query = f"""
                    SELECT path, is_directory, extension, size_bytes, lines_of_code,
                           file_count, total_loc, bloat_level, last_modified
                    FROM file_audit
                    WHERE path NOT LIKE $1
                    {"AND is_directory = TRUE" if not include_files else ""}
                    ORDER BY {order_by}
                """
                results = conn.execute(query, [path_not_like]).fetchall()

            # Get subdir counts for directories
            children = []
            for row in results:
                item_path = row[0]
                is_dir = row[1]
                name = item_path.split("/")[-1]

                item = {
                    "path": item_path,
                    "name": name,
                    "is_directory": is_dir,
                    "extension": row[2],
                    "size_bytes": row[3] or 0,
                    "lines_of_code": row[4] or 0,
                    "file_count": row[5],
                    "total_loc": row[6],
                    "bloat_level": row[7],
                    "last_modified": row[8].isoformat() if row[8] else None,
                }

                if is_dir:
                    # Count immediate subdirs and files
                    counts = conn.execute(
                        """
                        SELECT
                            COUNT(*) FILTER (WHERE is_directory) as subdir_count,
                            COUNT(*) FILTER (WHERE NOT is_directory) as file_count_direct
                        FROM file_audit
                        WHERE path LIKE $1 AND path NOT LIKE $2
                        """,
                        [f"{item_path}/%", f"{item_path}/%/%"],
                    ).fetchone()
                    item["subdir_count"] = counts[0] if counts else 0
                    item["direct_file_count"] = counts[1] if counts else 0
                    item["has_children"] = item["subdir_count"] > 0 or item["direct_file_count"] > 0
                else:
                    item["subdir_count"] = 0
                    item["direct_file_count"] = 0
                    item["has_children"] = False

                children.append(item)

            return children
