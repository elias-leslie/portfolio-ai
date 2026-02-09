"""Maintenance API module.

This module combines all maintenance-related routers:
- scripts_router: Script-based maintenance operations (cleanup, vacuum, validate)
- history_router: Maintenance execution history and logging
- tasks_router: Task management (trigger, status)
- monitoring_router: System monitoring (disk space, database size, stats, schedule)
"""

from __future__ import annotations

from fastapi import APIRouter

from .history_router import router as history_router
from .monitoring_router import router as monitoring_router
from .scripts_router import router as scripts_router
from .tasks_router import router as tasks_router

# Create main router that combines all sub-routers
router = APIRouter()

# Include all sub-routers
router.include_router(scripts_router)
router.include_router(history_router)
router.include_router(tasks_router)
router.include_router(monitoring_router)

__all__ = ["router"]
