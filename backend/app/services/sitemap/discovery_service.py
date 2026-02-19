"""Sitemap Discovery Service - Endpoint and route discovery.

This module provides:
- Discovery of backend API endpoints (via OpenAPI)
- Discovery of WebSocket endpoints (via probe)
- Discovery of frontend pages (via crawling)
- Discovery of Next.js routes (via filesystem parsing)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from ...logging_config import get_logger
from ...utils.port_discovery import (
    PortDiscovery,
    get_port_for_service,
)
from ...utils.url_helpers import substitute_path_params
from ._discovery_helpers import (
    BACKEND_HOST,
    FRONTEND_HOST,
    HTTP_TIMEOUT,
    WEBSOCKET_PROBE_PATHS,
    WS_ENDPOINT_STATUS_CODES,
    build_route_from_parts,
    extract_openapi_endpoints,
    extract_page_metadata,
    extract_page_title,
    extract_tab_values,
    queue_internal_links,
)

logger = get_logger(__name__)


class SitemapDiscoveryService:
    """Discovers sitemap entries from various sources."""

    def __init__(self) -> None:
        self._port_discovery = PortDiscovery()

    @property
    def frontend_port(self) -> int:
        """Get the frontend port (dynamically discovered or fallback)."""
        return get_port_for_service("frontend") or 3000

    async def _probe_openapi_port(
        self, client: httpx.AsyncClient, port_info: Any
    ) -> list[dict[str, Any]]:
        """Fetch OpenAPI spec from one port. Returns endpoint list or empty."""
        port = port_info.port
        try:
            response = await client.get(f"http://{BACKEND_HOST}:{port}/openapi.json")
            if response.status_code != 200:
                return []
            endpoints = extract_openapi_endpoints(response.json(), port, port_info.service_name)
            logger.info(
                "sitemap_openapi_port_complete",
                port=port,
                service=port_info.service_name,
                count=len(endpoints),
            )
            return endpoints
        except Exception as e:
            logger.debug("sitemap_openapi_port_failed", port=port, error=str(e))
            return []

    async def discover_all_openapi_endpoints(self) -> list[dict[str, Any]]:
        """Discover API endpoints from ALL ports that have OpenAPI specs."""
        logger.info("sitemap_discover_all_openapi_start")
        ports = self._port_discovery.get_all_ports()
        candidates = [
            p for p in ports.values() if p.service_type in ("backend", "websocket", "unknown")
        ]
        logger.info("sitemap_openapi_candidates", count=len(candidates), ports=[p.port for p in candidates])
        all_discovered: list[dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            for port_info in candidates:
                all_discovered.extend(await self._probe_openapi_port(client, port_info))
        logger.info("sitemap_discover_all_openapi_complete", total=len(all_discovered))
        return all_discovered

    async def _probe_ws_path(
        self, client: httpx.AsyncClient, port: int, service_name: str, ws_path: str
    ) -> dict[str, Any] | None:
        """Probe a single WebSocket path. Returns entry dict or None."""
        try:
            test_path = substitute_path_params(ws_path, "test")
            response = await client.get(
                f"http://{BACKEND_HOST}:{port}{test_path}",
                headers={"Upgrade": "websocket", "Connection": "Upgrade"},
            )
            if response.status_code not in WS_ENDPOINT_STATUS_CODES:
                return None
            logger.info("sitemap_websocket_found", port=port, path=ws_path, service=service_name)
            return {
                "port": port, "path": ws_path, "method": "WS",
                "entry_type": "websocket", "source": "probe",
                "title": f"WebSocket - {service_name}", "service_name": service_name,
            }
        except Exception as e:
            logger.debug("sitemap_websocket_probe_failed", port=port, path=ws_path, error=str(e))
            return None

    async def _probe_port_ws_paths(
        self, client: httpx.AsyncClient, port_info: Any
    ) -> list[dict[str, Any]]:
        """Probe all WebSocket paths for one port. Returns found entries."""
        results: list[dict[str, Any]] = []
        for ws_path in WEBSOCKET_PROBE_PATHS:
            entry = await self._probe_ws_path(client, port_info.port, port_info.service_name, ws_path)
            if entry:
                results.append(entry)
        return results

    async def discover_websocket_endpoints(self) -> list[dict[str, Any]]:
        """Discover WebSocket endpoints by probing known paths on candidate ports."""
        logger.info("sitemap_discover_websocket_start")
        ports = self._port_discovery.get_all_ports()
        ws_candidates = [
            p for p in ports.values() if p.service_type in ("websocket", "backend", "unknown")
        ]
        discovered: list[dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            for port_info in ws_candidates:
                discovered.extend(await self._probe_port_ws_paths(client, port_info))
        logger.info("sitemap_discover_websocket_complete", count=len(discovered))
        return discovered

    async def _fetch_page_entry(
        self,
        client: httpx.AsyncClient,
        path: str,
        depth: int,
        max_depth: int,
        visited: set[str],
        to_visit: list[tuple[str, int]],
        frontend_port: int,
    ) -> dict[str, Any] | None:
        """Fetch one crawl page, queue links, return entry or None on failure."""
        try:
            response = await client.get(f"http://{FRONTEND_HOST}:{frontend_port}{path}")
            if response.status_code != 200:
                return None
            metadata = extract_page_metadata(response.text)
            queue_internal_links(response.text, depth, max_depth, visited, to_visit)
            return {
                "port": frontend_port, "path": path,
                "method": "GET", "entry_type": "frontend_page",
                "source": "crawler", "title": metadata["title"],
            }
        except Exception as e:
            logger.debug("sitemap_crawl_page_failed", path=path, error=str(e))
            return None

    async def discover_frontend_pages(self, max_depth: int = 3) -> list[dict[str, Any]]:
        """Crawl frontend to discover pages by following links."""
        logger.info("sitemap_discover_frontend_start")
        discovered: list[dict[str, Any]] = []
        visited: set[str] = set()
        to_visit: list[tuple[str, int]] = [("/", 0)]
        frontend_port = self.frontend_port
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
            while to_visit:
                path, depth = to_visit.pop(0)
                if path in visited or depth > max_depth:
                    continue
                visited.add(path)
                entry = await self._fetch_page_entry(
                    client, path, depth, max_depth, visited, to_visit, frontend_port
                )
                if entry:
                    discovered.append(entry)
        logger.info("sitemap_discover_frontend_complete", count=len(discovered))
        return discovered

    def _build_page_entries(
        self, page_file: Path, app_dir: Path, frontend_port: int
    ) -> list[dict[str, Any]]:
        """Build route entry dicts for a single Next.js page file."""
        relative_path = page_file.relative_to(app_dir)
        route_parts = list(relative_path.parts[:-1])
        route = build_route_from_parts(route_parts)
        title = extract_page_title(page_file)
        tab_values = extract_tab_values(page_file)
        entries: list[dict[str, Any]] = [
            {
                "port": frontend_port, "path": route, "method": "GET",
                "entry_type": "frontend_page", "source": "nextjs_app",
                "title": title, "has_dynamic_segment": "{" in route,
            }
        ]
        for tab in tab_values:
            entries.append(
                {
                    "port": frontend_port, "path": f"{route}?tab={tab}", "method": "GET",
                    "entry_type": "frontend_page", "source": "nextjs_app",
                    "title": f"{title} - {tab.title()}" if title else tab.title(),
                    "parent_path": route,
                }
            )
        return entries

    def discover_nextjs_routes(self, frontend_dir: str | None = None) -> list[dict[str, Any]]:
        """Parse Next.js app directory to discover all routes."""
        logger.info("sitemap_discover_nextjs_start")
        discovered: list[dict[str, Any]] = []
        if frontend_dir is None:
            frontend_dir = str(Path.home() / "portfolio-ai" / "frontend")
        app_dir = Path(frontend_dir) / "app"
        if not app_dir.exists():
            logger.warning("sitemap_nextjs_app_dir_not_found", path=str(app_dir))
            return discovered
        page_files = list(app_dir.glob("**/page.tsx"))
        logger.info("sitemap_nextjs_pages_found", count=len(page_files))
        frontend_port = self.frontend_port
        for page_file in page_files:
            try:
                discovered.extend(self._build_page_entries(page_file, app_dir, frontend_port))
            except Exception as e:
                logger.debug("sitemap_nextjs_parse_failed", file=str(page_file), error=str(e))
        logger.info("sitemap_discover_nextjs_complete", count=len(discovered))
        return discovered
