"""API endpoints for file audit."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from starlette.concurrency import run_in_threadpool

from app.services.file_scanner import FileScanner

router = APIRouter(prefix="/api/files", tags=["files"])

# Project root for git operations (backend/app/api/files.py -> portfolio-ai/)
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


@router.get("")
async def list_files(
    path: str | None = Query(None, description="Filter by path prefix"),
    extension: str | None = Query(None, description="Filter by extension (e.g., .py)"),
    bloat: str | None = Query(None, description="Filter by bloat level (warning, critical)"),
    stale: str | None = Query(None, description="Filter by stale status (fresh, stale, orphan)"),
    is_directory: bool | None = Query(None, description="Filter files or directories"),
    sort: str = Query("path", description="Sort by: path, lines_of_code, size_bytes, last_commit_days, reference_count"),
    dir: str = Query("asc", description="Sort direction: asc, desc"),
    limit: int = Query(100, ge=1, le=500, description="Results per page"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
) -> dict[str, Any]:
    """List files with filtering, sorting, and pagination."""
    scanner = FileScanner()
    return await run_in_threadpool(
        scanner.search,
        path_prefix=path,
        extension=extension,
        bloat=bloat,
        stale=stale,
        is_directory=is_directory,
        sort_by=sort,
        sort_dir=dir,
        limit=limit,
        offset=offset,
    )


@router.get("/summary")
async def get_summary() -> dict[str, Any]:
    """Get aggregate statistics from file audit."""
    scanner = FileScanner()
    return await run_in_threadpool(scanner.get_summary)


@router.get("/tree")
async def get_tree(
    path: str = Query("", description="Path prefix to filter tree"),
    depth: int | None = Query(
        None, description="Set to 1 for lazy loading (immediate children only)"
    ),
) -> list[dict[str, Any]]:
    """Get hierarchical tree structure for UI."""
    scanner = FileScanner()
    return await run_in_threadpool(scanner.get_tree, path, depth)


@router.get("/children")
async def get_children(
    path: str = Query("", description="Parent path (empty for root)"),
    sort: str = Query("name", description="Sort by: name, loc, size, modified, files"),
    dir: str = Query("asc", description="Sort direction: asc, desc"),
    folders_first: bool = Query(True, description="Show folders before files"),
    include_files: bool = Query(True, description="Include files in response"),
) -> list[dict[str, Any]]:
    """Get immediate children (folders and files) for explorer view."""
    scanner = FileScanner()
    return await run_in_threadpool(
        scanner.get_children, path, sort, dir, folders_first, include_files
    )


@router.post("/scan")
async def trigger_scan(background_tasks: BackgroundTasks) -> dict[str, str]:
    """Trigger a file scan. Runs in background."""
    from app.tasks.file_scan import scan_files  # noqa: PLC0415

    scan_files.delay()
    return {"status": "queued", "message": "File scan started in background"}


def _get_git_history(file_path: str, limit: int = 10) -> dict[str, Any]:
    """Get git history for a file using git log --follow."""
    full_path = PROJECT_ROOT / file_path

    # Validate path exists and is within project
    try:
        full_path.resolve().relative_to(PROJECT_ROOT.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file path")

    if not full_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    # Get commit history with --follow to track renames
    # Format: hash|author|date|lines_added|lines_deleted|subject
    try:
        result = subprocess.run(
            [
                "git",
                "log",
                "--follow",
                f"-{limit}",
                "--format=%H|%an|%aI|%s",
                "--numstat",
                "--",
                str(full_path),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Git operation timed out")

    if result.returncode != 0:
        # File might not be tracked
        return {"commits": [], "total_commits": 0, "error": "File not tracked by git"}

    # Parse output
    commits = []
    lines = result.stdout.strip().split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        if "|" in line:
            # This is a commit line
            parts = line.split("|", 3)
            if len(parts) >= 4:
                commit_hash, author, date, subject = parts
                commit = {
                    "hash": commit_hash[:8],
                    "full_hash": commit_hash,
                    "author": author,
                    "date": date,
                    "subject": subject,
                    "lines_added": 0,
                    "lines_deleted": 0,
                }

                # Look for numstat on next line
                i += 1
                while i < len(lines) and lines[i].strip() and "|" not in lines[i]:
                    stat_line = lines[i].strip()
                    stat_parts = stat_line.split("\t")
                    if len(stat_parts) >= 2:
                        try:
                            added = int(stat_parts[0]) if stat_parts[0] != "-" else 0
                            deleted = int(stat_parts[1]) if stat_parts[1] != "-" else 0
                            commit["lines_added"] += added
                            commit["lines_deleted"] += deleted
                        except ValueError:
                            pass
                    i += 1

                commits.append(commit)
                continue

        i += 1

    # Get total commit count
    count_result = subprocess.run(
        ["git", "rev-list", "--count", "HEAD", "--", str(full_path)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=5,
    )
    total_commits = int(count_result.stdout.strip()) if count_result.returncode == 0 else len(commits)

    return {
        "commits": commits,
        "total_commits": total_commits,
        "file_path": file_path,
    }


@router.get("/history")
async def get_file_history(
    path: str = Query(..., description="File path relative to project root"),
    limit: int = Query(10, ge=1, le=50, description="Number of commits to return"),
) -> dict[str, Any]:
    """Get git commit history for a specific file."""
    return await run_in_threadpool(_get_git_history, path, limit)
