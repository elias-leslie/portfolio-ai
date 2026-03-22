"""Cleanup task modules - log rotation, temp files, artifacts, and disk monitoring.

This package provides domain-specific cleanup modules:
- log_cleanup: Log file rotation and cleanup
- temp_cleanup: Temporary files and cache directory cleanup
- artifact_cleanup: Old backups and models cleanup
- disk_monitoring: Disk space monitoring and alerting
"""

from app.tasks.cleanup.artifact_cleanup import (
    cleanup_old_backups_task,
    cleanup_old_models_task,
)
from app.tasks.cleanup.disk_monitoring import check_disk_space_task
from app.tasks.cleanup.log_cleanup import cleanup_old_logs_task, rotate_logs_task
from app.tasks.cleanup.temp_cleanup import (
    cleanup_cache_directories_task,
    cleanup_temp_files_task,
)

__all__ = [
    "check_disk_space_task",
    "cleanup_cache_directories_task",
    "cleanup_old_backups_task",
    "cleanup_old_logs_task",
    "cleanup_old_models_task",
    "cleanup_temp_files_task",
    "rotate_logs_task",
]
