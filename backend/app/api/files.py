"""API endpoints for file audit."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Query
from starlette.concurrency import run_in_threadpool

from app.services.file_scanner import FileScanner

router = APIRouter(prefix="/api/files", tags=["files"])


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
