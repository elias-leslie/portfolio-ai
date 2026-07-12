"""Helper utilities for artifact cleanup tasks.

Shared helper functions used by artifact_cleanup.py for:
- Backup file cleanup
- ML model version cleanup
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

from app.constants import SECONDS_PER_DAY
from app.logging_config import get_logger
from app.tasks.maintenance_logging import log_maintenance_complete

from .shared_helpers import (
    CleanupResult,
    build_cleanup_result,
    bytes_to_mb,
    record_cleanup_metric,
)

logger = get_logger(__name__)

# Type aliases
_DryRunEntry = dict[str, int | float | str]


def handle_missing_directory(
    task_id: str,
    dry_run: bool,
    directory_path: Path,
    task_name: str,
    log_id: int,
    counter_field_name: str = "files_deleted",
) -> CleanupResult | None:
    """Return an early result dict if directory doesn't exist, else None."""
    if directory_path.exists():
        return None
    logger.warning("directory_not_found", task_name=task_name, directory=str(directory_path))
    early_result: CleanupResult = {
        "task_id": task_id,
        "dry_run": dry_run,
        counter_field_name: 0,
        "bytes_freed": 0,
        "message": f"{task_name.replace('_', ' ').title()} directory not found",
        "success": True,
        "duration_seconds": 0.0,
    }
    log_maintenance_complete(log_id, task_name, True, early_result)
    return early_result


def group_model_files_by_name(models_dir: Path) -> dict[str, list[tuple[Path, str, int]]]:
    """Group model files by base name. Returns model_name -> [(Path, date_str, size)] map."""
    model_groups: dict[str, list[tuple[Path, str, int]]] = {}
    model_pattern = re.compile(r"^(.+)_v(\d{8})\.joblib$")
    for f in models_dir.glob("*.joblib"):
        if f.is_symlink():
            continue
        match = model_pattern.match(f.name)
        if not match:
            continue
        model_groups.setdefault(match.group(1), []).append((f, match.group(2), f.stat().st_size))
    return model_groups


def get_old_model_versions(
    model_groups: dict[str, list[tuple[Path, str, int]]], keep_count: int
) -> list[tuple[Path, str, str, int]]:
    """Return old model versions to delete (all beyond keep_count per model type)."""
    old_versions: list[tuple[Path, str, str, int]] = []
    for model_name, versions in model_groups.items():
        versions.sort(key=lambda x: x[1], reverse=True)
        old_versions.extend((fp, model_name, ds, fs) for fp, ds, fs in versions[keep_count:])
    return old_versions


def process_backup_file(
    file_path: Path, mtime: float, file_size: int, dry_run: bool, now: float,
    would_delete: list[_DryRunEntry],
) -> tuple[int, int]:
    """Process a single backup file for deletion. Returns (files_deleted, bytes_freed)."""
    try:
        age_days = (now - mtime) / SECONDS_PER_DAY
        if dry_run:
            would_delete.append({"file": str(file_path), "size_bytes": file_size, "age_days": round(age_days, 1)})
        else:
            file_path.unlink()
            logger.info("backup_file_deleted", file=str(file_path), size_bytes=file_size)
        return 1, file_size
    except Exception as file_error:
        logger.error("backup_deletion_failed", file=str(file_path), error=str(file_error), exc_info=True)
        return 0, 0


def process_model_file(
    file_path: Path, model_name: str, date_str: str, file_size: int, dry_run: bool,
    would_delete: list[_DryRunEntry],
) -> tuple[int, int]:
    """Process a single model file for deletion. Returns (files_deleted, bytes_freed)."""
    try:
        if dry_run:
            would_delete.append({"file": str(file_path), "model_name": model_name, "version_date": date_str, "size_bytes": file_size})
        else:
            file_path.unlink()
            logger.info("model_file_deleted", file=str(file_path), model_name=model_name, version_date=date_str, size_bytes=file_size)
        return 1, file_size
    except Exception as file_error:
        logger.error("model_deletion_failed", file=str(file_path), error=str(file_error), exc_info=True)
        return 0, 0


def collect_backup_files(backup_dir: Path) -> list[tuple[Path, float, int]]:
    """Collect and sort backup files by modification time (newest first)."""
    backup_files: list[tuple[Path, float, int]] = []
    for pattern in (
        "portfolio_ai_complete_*.tar.gz",
        "*.sql",
        "*.sql.gz",
        "*.sql.bz2",
    ):
        for f in backup_dir.glob(pattern):
            if f.is_file():
                stat = f.stat()
                backup_files.append((f, stat.st_mtime, stat.st_size))
    backup_files.sort(key=lambda x: x[1], reverse=True)
    return backup_files


def delete_old_backups(
    backup_files: list[tuple[Path, float, int]], keep_count: int, dry_run: bool
) -> tuple[int, int, list[_DryRunEntry]]:
    """Delete backup files beyond keep_count. Returns (files_deleted, bytes_freed, would_delete)."""
    files_deleted, bytes_freed = 0, 0
    would_delete: list[_DryRunEntry] = []
    now = dt.datetime.now(dt.UTC).timestamp()
    for file_path, mtime, file_size in backup_files[keep_count:]:
        d, f = process_backup_file(file_path, mtime, file_size, dry_run, now, would_delete)
        files_deleted += d
        bytes_freed += f
    return files_deleted, bytes_freed, would_delete


def delete_old_model_versions(
    old_versions: list[tuple[Path, str, str, int]], dry_run: bool
) -> tuple[int, int, list[_DryRunEntry]]:
    """Delete old model version files. Returns (files_deleted, bytes_freed, would_delete)."""
    files_deleted, bytes_freed = 0, 0
    would_delete: list[_DryRunEntry] = []
    for file_path, model_name, date_str, file_size in old_versions:
        d, f = process_model_file(file_path, model_name, date_str, file_size, dry_run, would_delete)
        files_deleted += d
        bytes_freed += f
    return files_deleted, bytes_freed, would_delete


def run_backups_cleanup(task_id: str, dry_run: bool, keep_count: int, log_id: int) -> CleanupResult:
    """Execute backup cleanup core logic (directory scan, delete, build result)."""
    backup_dir = (
        Path(__file__).parent.parent.parent.parent.parent / "data" / "backups"
    )
    early_exit = handle_missing_directory(task_id, dry_run, backup_dir, "cleanup_old_backups_task", log_id)
    if early_exit:
        return early_exit
    backup_files = collect_backup_files(backup_dir)
    files_deleted, bytes_freed, would_delete = delete_old_backups(backup_files, keep_count, dry_run)
    record_cleanup_metric("backup_cleanup_bytes_freed", bytes_freed, dry_run)
    return build_cleanup_result(
        task_id=task_id, dry_run=dry_run, duration_seconds=0.0,
        task_specific_fields={"files_deleted": files_deleted, "bytes_freed": bytes_freed,
                              "bytes_freed_mb": bytes_to_mb(bytes_freed), "keep_count": keep_count,
                              "total_backups": len(backup_files)},
        would_action_list=would_delete if dry_run else None,
    )


def run_models_cleanup(task_id: str, dry_run: bool, keep_count: int, log_id: int) -> CleanupResult:
    """Execute model cleanup core logic (directory scan, delete, build result)."""
    models_dir = Path(__file__).parent.parent.parent.parent / "models"
    early_result = handle_missing_directory(task_id, dry_run, models_dir, "cleanup_old_models_task", log_id)
    if early_result:
        return early_result
    model_groups = group_model_files_by_name(models_dir)
    old_versions = get_old_model_versions(model_groups, keep_count)
    files_deleted, bytes_freed, would_delete = delete_old_model_versions(old_versions, dry_run)
    record_cleanup_metric("model_cleanup_bytes_freed", bytes_freed, dry_run)
    return build_cleanup_result(
        task_id=task_id, dry_run=dry_run, duration_seconds=0.0,
        task_specific_fields={"files_deleted": files_deleted, "bytes_freed": bytes_freed,
                              "bytes_freed_mb": bytes_to_mb(bytes_freed), "keep_count": keep_count,
                              "model_groups": len(model_groups)},
        would_action_list=would_delete if dry_run else None,
    )
