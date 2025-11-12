"""Status and monitoring endpoints for real-time service information.

This module aggregates status-related endpoints from specialized sub-modules:
- status_logs: Log viewing and management
- status_system: System resources and service management
- status_tasks: Celery task operations
- status_data: Data freshness and cache management
- status_ml: ML model metrics and status
"""

from __future__ import annotations

from fastapi import APIRouter

from . import status_data, status_logs, status_ml, status_system, status_tasks

# Main router that aggregates all status sub-routers
router = APIRouter()

# Include all status sub-routers
router.include_router(status_logs.router)
router.include_router(status_system.router)
router.include_router(status_tasks.router)
router.include_router(status_data.router)
router.include_router(status_ml.router)
