"""Service for monitoring file system resources.

Provides functions to monitor file cleanup directories, cache directories,
and calculate directory sizes for maintenance monitoring.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..api.maintenance.monitoring_types import (
    CacheDirectoryInfo,
    CacheStatusResponse,
    FileCleanupStatusResponse,
)


def calculate_dir_size(path: Path, pattern: str = "*") -> tuple[float, int]:
    """Calculate directory size and file count.

    Args:
        path: Directory path
        pattern: Glob pattern for files to count

    Returns:
        Tuple of (size_mb, file_count)
    """
    if not path.exists():
        return 0.0, 0

    total_bytes = 0
    file_count = 0

    for f in path.glob(pattern):
        if f.is_file() and not f.is_symlink():
            total_bytes += f.stat().st_size
            file_count += 1

    return round(total_bytes / (1024 * 1024), 2), file_count


def count_pycache_recursive(base_path: Path) -> tuple[float, int]:
    """Count all __pycache__ dirs under a path.

    Args:
        base_path: Root path to search recursively

    Returns:
        Tuple of (size_mb, file_count)
    """
    total_bytes = 0
    file_count = 0

    if not base_path.exists():
        return 0.0, 0

    for pycache_dir in base_path.rglob("__pycache__"):
        if pycache_dir.is_dir():
            for f in pycache_dir.iterdir():
                if f.is_file():
                    try:
                        total_bytes += f.stat().st_size
                        file_count += 1
                    except (OSError, FileNotFoundError):
                        pass

    return round(total_bytes / (1024 * 1024), 2), file_count


def get_cache_dir_info(path: Path, name: str, description: str) -> CacheDirectoryInfo:
    """Get info about a cache directory, handling recursive patterns.

    Args:
        path: Directory path
        name: Display name for the cache
        description: Description of the cache purpose

    Returns:
        CacheDirectoryInfo dict with size and count
    """
    if not path.exists():
        return {
            "name": name,
            "path": str(path),
            "size_mb": 0.0,
            "file_count": 0,
            "description": description,
        }

    total_bytes = 0
    file_count = 0

    for f in path.rglob("*"):
        if f.is_file() and not f.is_symlink():
            try:
                total_bytes += f.stat().st_size
                file_count += 1
            except (OSError, FileNotFoundError):
                pass  # Skip files we can't access

    return {
        "name": name,
        "path": str(path),
        "size_mb": round(total_bytes / (1024 * 1024), 2),
        "file_count": file_count,
        "description": description,
    }


def get_file_cleanup_status() -> FileCleanupStatusResponse:
    """Get sizes and retention info for file cleanup directories.

    Returns:
        FileCleanupStatusResponse with logs, backups, models, solution_state info

    Raises:
        Exception: If status retrieval fails
    """
    # Base paths
    project_root = Path(__file__).parent.parent.parent.parent
    backend_root = Path(__file__).parent.parent.parent

    # Logs directory
    logs_path = backend_root / "logs"
    logs_size, logs_count = calculate_dir_size(logs_path, "*.log*")

    # Backups directory
    backups_path = project_root / "backups"
    backups_sql_size, backups_sql_count = calculate_dir_size(backups_path, "*.sql")
    backups_gz_size, backups_gz_count = calculate_dir_size(backups_path, "*.sql.gz")
    backups_size = round(backups_sql_size + backups_gz_size, 2)
    backups_count = backups_sql_count + backups_gz_count

    # Models directory
    models_path = backend_root / "models"
    models_size, models_count = calculate_dir_size(models_path, "*.joblib")

    # Solution state directory
    solution_path = project_root / "solution_state"
    solution_size = 0.0
    solution_count = 0
    if solution_path.exists():
        timestamp_pattern = re.compile(r"^\d{8}-\d{6}$")
        for entry in solution_path.iterdir():
            if entry.is_dir() and timestamp_pattern.match(entry.name):
                for f in entry.rglob("*"):
                    if f.is_file():
                        solution_size += f.stat().st_size / (1024 * 1024)
                        solution_count += 1
        solution_size = round(solution_size, 2)

    total_size = round(logs_size + backups_size + models_size + solution_size, 2)

    return {
        "logs": {
            "path": str(logs_path),
            "size_mb": logs_size,
            "file_count": logs_count,
            "retention_policy": "Keep 7 days",
            "schedule": "Daily 02:00 UTC",
        },
        "backups": {
            "path": str(backups_path),
            "size_mb": backups_size,
            "file_count": backups_count,
            "retention_policy": "Keep 5 most recent",
            "schedule": "Weekly Sunday 04:45 UTC",
        },
        "models": {
            "path": str(models_path),
            "size_mb": models_size,
            "file_count": models_count,
            "retention_policy": "Keep 3 versions per model",
            "schedule": "Weekly Sunday 05:00 UTC",
        },
        "solution_state": {
            "path": str(solution_path),
            "size_mb": solution_size,
            "file_count": solution_count,
            "retention_policy": "Keep 14 days",
            "schedule": "Weekly Sunday 05:15 UTC",
        },
        "total_size_mb": total_size,
    }


def get_cache_status() -> CacheStatusResponse:
    """Get sizes for all cache directories that can be cleaned.

    These caches regenerate automatically and are safe to delete.

    Returns:
        CacheStatusResponse with cache directory info and totals

    Raises:
        Exception: If status retrieval fails
    """
    project_root = Path(__file__).parent.parent.parent.parent
    backend_root = Path(__file__).parent.parent.parent

    directories: list[CacheDirectoryInfo] = []

    # Python __pycache__ (backend)
    backend_pycache_size, backend_pycache_count = count_pycache_recursive(backend_root)
    directories.append(
        {
            "name": "Python Bytecode (backend)",
            "path": str(backend_root / "__pycache__"),
            "size_mb": backend_pycache_size,
            "file_count": backend_pycache_count,
            "description": "Compiled Python files, regenerate on import",
        }
    )

    # Python __pycache__ (services)
    services_path = project_root / "services"
    services_pycache_size, services_pycache_count = count_pycache_recursive(services_path)
    directories.append(
        {
            "name": "Python Bytecode (services)",
            "path": str(services_path / "__pycache__"),
            "size_mb": services_pycache_size,
            "file_count": services_pycache_count,
            "description": "Compiled Python files, regenerate on import",
        }
    )

    # Ruff cache
    ruff_path = backend_root / ".ruff_cache"
    directories.append(
        get_cache_dir_info(
            ruff_path, "Ruff Linter Cache", "Ruff analysis cache, regenerates on lint"
        )
    )

    # Pytest cache
    pytest_path = backend_root / ".pytest_cache"
    directories.append(
        get_cache_dir_info(
            pytest_path, "Pytest Cache", "Test execution cache, regenerates on test run"
        )
    )

    # Mypy cache
    mypy_path = backend_root / ".mypy_cache"
    directories.append(
        get_cache_dir_info(mypy_path, "Mypy Cache", "Type check cache, regenerates on mypy run")
    )

    # Next.js cache (only .next/cache, not server)
    nextjs_cache_path = project_root / "frontend" / ".next" / "cache"
    directories.append(
        get_cache_dir_info(
            nextjs_cache_path,
            "Next.js Build Cache",
            "Webpack/build cache, regenerates on build",
        )
    )

    # Claude memory backups
    claude_memory_path = project_root / ".claude" / "backups" / "memory"
    directories.append(
        get_cache_dir_info(
            claude_memory_path,
            "Claude Memory Backups",
            "Transient Claude memory, not essential",
        )
    )

    # Calculate totals
    total_size = sum(d["size_mb"] for d in directories)
    total_count = sum(d["file_count"] for d in directories)

    return {
        "directories": directories,
        "total_size_mb": round(total_size, 2),
        "total_file_count": total_count,
    }
