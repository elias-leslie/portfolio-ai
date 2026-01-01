"""Sitemap Service - Coordinator for discovery and health monitoring.

This module provides:
- Coordination of discovery and health check services
- CRUD operations (delegated to storage)
- Port discovery management
- Full discovery orchestration
"""

from __future__ import annotations

import asyncio
from typing import Any

from ...logging_config import get_logger
from ...storage.connection import get_connection_manager
from ...storage.sitemap_storage import get_sitemap_storage
from ...utils.port_discovery import PortDiscovery
from .discovery_service import SitemapDiscoveryService
from .health_check_service import SitemapHealthCheckService

logger = get_logger(__name__)


class SitemapService:
    """Discovers and monitors sitemap entries."""

    def __init__(self) -> None:
        self.conn_mgr = get_connection_manager()
        self._port_discovery = PortDiscovery()
        self._storage = get_sitemap_storage()
        self._discovery = SitemapDiscoveryService()
        self._health_check = SitemapHealthCheckService()

    @property
    def frontend_port(self) -> int:
        """Get the frontend port (dynamically discovered or fallback)."""
        return self._discovery.frontend_port

    def get_discovered_ports(self) -> list[dict[str, Any]]:
        """Get all discovered ports with their metadata.

        Returns:
            List of port info dicts
        """
        ports = self._port_discovery.get_all_ports()
        return [
            {
                "port": p.port,
                "service_name": p.service_name,
                "service_type": p.service_type,
                "source": p.source,
                "description": p.description,
            }
            for p in ports.values()
        ]

    def refresh_port_discovery(self) -> list[dict[str, Any]]:
        """Force refresh of port discovery cache.

        Returns:
            List of newly discovered port info dicts
        """
        self._port_discovery.clear_cache()
        return self.get_discovered_ports()

    # =========================================================================
    # Discovery Methods (delegated to discovery service)
    # =========================================================================

    async def discover_all_openapi_endpoints(self) -> list[dict[str, Any]]:
        """Discover API endpoints from ALL ports that have OpenAPI specs.

        Returns:
            List of discovered endpoint dicts from all ports
        """
        return await self._discovery.discover_all_openapi_endpoints()

    async def discover_websocket_endpoints(self) -> list[dict[str, Any]]:
        """Discover WebSocket endpoints from services.

        Returns:
            List of discovered WebSocket endpoint dicts
        """
        return await self._discovery.discover_websocket_endpoints()

    async def discover_frontend_pages(self, max_depth: int = 3) -> list[dict[str, Any]]:
        """Crawl frontend to discover pages by following links.

        Args:
            max_depth: Maximum crawl depth

        Returns:
            List of discovered page dicts
        """
        return await self._discovery.discover_frontend_pages(max_depth)

    def discover_nextjs_routes(self, frontend_dir: str | None = None) -> list[dict[str, Any]]:
        """Parse Next.js app directory to discover all routes.

        Args:
            frontend_dir: Path to frontend directory, defaults to ~/portfolio-ai/frontend

        Returns:
            List of discovered route dicts
        """
        return self._discovery.discover_nextjs_routes(frontend_dir)

    async def run_discovery(self) -> dict[str, Any]:
        """Run comprehensive discovery across all service types.

        Discovery methods:
        - OpenAPI: All ports with /openapi.json (backend, dev-companion, etc.)
        - Frontend: Crawl pages and parse Next.js app directory
        - WebSocket: Probe for WS endpoints on applicable ports

        Returns:
            Summary of discovery results
        """
        logger.info("sitemap_full_discovery_start")

        # Run async discoveries in parallel
        all_openapi_task = asyncio.create_task(self.discover_all_openapi_endpoints())
        frontend_task = asyncio.create_task(self.discover_frontend_pages())
        websocket_task = asyncio.create_task(self.discover_websocket_endpoints())

        all_openapi_entries = await all_openapi_task
        frontend_entries = await frontend_task
        websocket_entries = await websocket_task

        # Run sync discoveries
        nextjs_entries = self.discover_nextjs_routes()

        # Combine all entries
        all_entries = all_openapi_entries + frontend_entries + websocket_entries + nextjs_entries

        # Bulk save using storage layer
        saved = self._storage.bulk_save_discovered_entries(all_entries)

        result = {
            "openapi_discovered": len(all_openapi_entries),
            "frontend_discovered": len(frontend_entries),
            "websocket_discovered": len(websocket_entries),
            "nextjs_discovered": len(nextjs_entries),
            "total_saved": saved,
        }

        logger.info("sitemap_full_discovery_complete", **result)
        return result

    # =========================================================================
    # Health Check Methods (delegated to health check service)
    # =========================================================================

    async def check_entry_health(self, entry_id: int) -> dict[str, Any]:
        """Check health of a single sitemap entry.

        Args:
            entry_id: ID of sitemap entry to check

        Returns:
            Health check result dict
        """
        return await self._health_check.check_entry_health(entry_id)

    async def check_all_health(self) -> dict[str, Any]:
        """Check health of all sitemap entries.

        Returns:
            Summary of health check results
        """
        return await self._health_check.check_all_health()

    # =========================================================================
    # CRUD Operations (delegated to storage layer)
    # =========================================================================

    def get_entries(
        self,
        port: int | None = None,
        health_status: str | None = None,
        entry_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """Get sitemap entries with filtering. Delegates to storage layer."""
        return self._storage.get_entries(
            port=port,
            health_status=health_status,
            entry_type=entry_type,
            limit=limit,
            offset=offset,
        )

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        """Get single entry by ID. Delegates to storage layer."""
        return self._storage.get_entry(entry_id)

    def get_health_summary(self) -> dict[str, Any]:
        """Get aggregate health statistics. Delegates to storage layer."""
        return self._storage.get_health_summary()

    def register_entry(
        self,
        port: int,
        path: str,
        method: str = "GET",
        entry_type: str = "manual",
        title: str | None = None,
    ) -> dict[str, Any] | None:
        """Manually register a new sitemap entry. Delegates to storage layer."""
        return self._storage.register_entry(
            port=port,
            path=path,
            method=method,
            entry_type=entry_type,
            title=title,
        )

    def delete_entry(self, entry_id: int) -> bool:
        """Remove a sitemap entry. Delegates to storage layer."""
        return self._storage.delete_entry(entry_id)

    # =========================================================================
    # Maintenance (delegated to storage layer)
    # =========================================================================

    def cleanup_old_history(self, days: int = 7) -> int:
        """Delete health history older than specified days. Delegates to storage layer."""
        return self._storage.cleanup_old_history(days)

    def get_history_stats(self) -> dict[str, Any]:
        """Get health history statistics for maintenance UI. Delegates to storage layer."""
        return self._storage.get_history_stats()
