"""Sitemap Discovery Service - Endpoint and route discovery.

This module provides:
- Discovery of backend API endpoints (via OpenAPI)
- Discovery of WebSocket endpoints (via probe)
- Discovery of frontend pages (via crawling)
- Discovery of Next.js routes (via filesystem parsing)
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import httpx

from ...logging_config import get_logger
from ...utils.port_discovery import (
    PortDiscovery,
    get_port_for_service,
)
from ...utils.url_helpers import substitute_path_params

logger = get_logger(__name__)

# Configuration
HTTP_TIMEOUT = 10  # seconds

# Compiled regex patterns for HTML/TSX parsing
HTML_TITLE_PATTERN = re.compile(r"<title>([^<]+)</title>", re.IGNORECASE)
HREF_PATTERN = re.compile(r'href=["\']([^"\']+)["\']')
METADATA_TITLE_PATTERN = re.compile(r'title:\s*["\']([^"\']+)["\']')
PAGE_HEADER_TITLE_PATTERN = re.compile(r'<PageHeader[^>]*title=["\']([^"\']+)["\']')
TAB_VALUE_TYPE_PATTERN = re.compile(r"type\s+TabValue\s*=\s*([^;]+);")
QUOTED_STRING_PATTERN = re.compile(r'["\']([^"\']+)["\']')
TABS_TRIGGER_PATTERN = re.compile(r'<TabsTrigger[^>]*value=["\']([^"\']+)["\']')

# Network configuration (from environment or fallback to defaults)
FRONTEND_HOST = os.getenv("FRONTEND_HOST", "192.168.8.233")  # Network IP for SSR routing
BACKEND_HOST = os.getenv("BACKEND_HOST", "localhost")

# Frontend crawl patterns to skip (static assets and API calls)
FRONTEND_CRAWL_SKIP_PATTERNS = [
    "/api/",
    "/_next/",
    "/static/",
    ".js",
    ".css",
    ".png",
    ".jpg",
]

# WebSocket probe paths to check
WEBSOCKET_PROBE_PATHS = ["/ws", "/ws/{session_id}", "/socket.io"]

# Status codes that indicate WebSocket endpoint exists
WS_ENDPOINT_STATUS_CODES = (403, 426, 400)


def _extract_openapi_endpoints(
    openapi: dict[str, Any], port: int, service_name: str | None = None
) -> list[dict[str, Any]]:
    """Extract endpoint entries from an OpenAPI specification.

    Args:
        openapi: Parsed OpenAPI JSON
        port: Port number for the endpoints
        service_name: Optional service name to include

    Returns:
        List of endpoint dicts ready for sitemap_entries
    """
    endpoints = []
    paths = openapi.get("paths", {})

    for path, methods in paths.items():
        for method, details in methods.items():
            if method.upper() not in ("GET", "POST", "PUT", "DELETE", "PATCH"):
                continue
            # Skip health/docs endpoints
            if any(x in path for x in ["/health", "/docs", "/openapi", "/redoc"]):
                continue

            entry = {
                "port": port,
                "path": path,
                "method": method.upper(),
                "entry_type": "api_endpoint",
                "source": "openapi",
                "title": details.get("summary") or details.get("operationId"),
            }
            if service_name:
                entry["service_name"] = service_name
            endpoints.append(entry)

    return endpoints


def _should_visit_link(link: str, visited: set[str]) -> bool:
    """Check if a link should be visited during frontend crawl.

    Filters out:
    - External links (// prefix)
    - Static assets (.js, .css, .png, .jpg)
    - API calls (/api/)
    - Next.js internals (/_next/)
    - Static directory (/static/)
    - Already visited links

    Args:
        link: The href value to check
        visited: Set of already visited paths

    Returns:
        True if link should be queued for crawling
    """
    if not link.startswith("/") or link.startswith("//"):
        return False
    if any(x in link for x in FRONTEND_CRAWL_SKIP_PATTERNS):
        return False
    # Extract clean path (remove query and fragments)
    clean_path = link.split("?")[0].split("#")[0]
    return clean_path not in visited


def _extract_page_metadata(response_text: str) -> dict[str, str | None]:
    """Extract page metadata from HTML response.

    Looks for page title in <title> tag.

    Args:
        response_text: The HTML response body

    Returns:
        Dict with 'title' key and extracted title or None
    """
    title = None
    title_match = HTML_TITLE_PATTERN.search(response_text)
    if title_match:
        title = title_match.group(1).strip()
    return {"title": title}


def _queue_internal_links(
    response_text: str,
    current_depth: int,
    max_depth: int,
    visited: set[str],
    to_visit: list[tuple[str, int]],
) -> None:
    """Extract internal links from HTML and queue them for crawling.

    Processes href attributes, filters out invalid links, and appends
    valid internal links to the to_visit queue for deeper crawling.

    Args:
        response_text: The HTML response body
        current_depth: Current crawl depth
        max_depth: Maximum allowed crawl depth
        visited: Set of already visited paths
        to_visit: Queue of (path, depth) tuples to visit
    """
    if current_depth >= max_depth:
        return

    links = HREF_PATTERN.findall(response_text)
    for link in links:
        if _should_visit_link(link, visited):
            clean_path = link.split("?")[0].split("#")[0]
            to_visit.append((clean_path, current_depth + 1))


class SitemapDiscoveryService:
    """Discovers sitemap entries from various sources."""

    def __init__(self) -> None:
        self._port_discovery = PortDiscovery()

    @property
    def frontend_port(self) -> int:
        """Get the frontend port (dynamically discovered or fallback)."""
        return get_port_for_service("frontend") or 3000

    async def discover_all_openapi_endpoints(self) -> list[dict[str, Any]]:
        """Discover API endpoints from ALL ports that have OpenAPI specs.

        Iterates through all discovered ports (from systemd) and checks each
        for an OpenAPI spec, extracting endpoints from any that have one.

        Returns:
            List of discovered endpoint dicts from all ports
        """
        logger.info("sitemap_discover_all_openapi_start")
        all_discovered = []

        # Get all discovered ports
        ports = self._port_discovery.get_all_ports()

        # Ports to check for OpenAPI (backend types and websocket services)
        openapi_candidates = [
            p for p in ports.values() if p.service_type in ("backend", "websocket", "unknown")
        ]

        logger.info(
            "sitemap_openapi_candidates",
            count=len(openapi_candidates),
            ports=[p.port for p in openapi_candidates],
        )

        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            for port_info in openapi_candidates:
                port = port_info.port
                try:
                    response = await client.get(f"http://{BACKEND_HOST}:{port}/openapi.json")
                    if response.status_code != 200:
                        continue

                    openapi = response.json()
                    port_endpoints = _extract_openapi_endpoints(
                        openapi, port, port_info.service_name
                    )
                    all_discovered.extend(port_endpoints)

                    logger.info(
                        "sitemap_openapi_port_complete",
                        port=port,
                        service=port_info.service_name,
                        count=len(port_endpoints),
                    )

                except Exception as e:
                    logger.debug("sitemap_openapi_port_failed", port=port, error=str(e))

        logger.info("sitemap_discover_all_openapi_complete", total=len(all_discovered))
        return all_discovered

    async def discover_websocket_endpoints(self) -> list[dict[str, Any]]:
        """Discover WebSocket endpoints from services.

        Checks known WebSocket paths (/ws, /ws/{id}) on ports that
        might have WebSocket support.

        Returns:
            List of discovered WebSocket endpoint dicts
        """
        logger.info("sitemap_discover_websocket_start")
        discovered = []

        # Get ports that might have WebSocket
        ports = self._port_discovery.get_all_ports()
        ws_candidates = [
            p for p in ports.values() if p.service_type in ("websocket", "backend", "unknown")
        ]

        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            for port_info in ws_candidates:
                port = port_info.port

                # Try WebSocket upgrade on common paths
                for ws_path in WEBSOCKET_PROBE_PATHS:
                    try:
                        # Check if endpoint exists (even without upgrade)
                        # FastAPI WebSocket endpoints return 403 for non-WS requests
                        test_path = substitute_path_params(ws_path, "test")
                        response = await client.get(
                            f"http://{BACKEND_HOST}:{port}{test_path}",
                            headers={"Upgrade": "websocket", "Connection": "Upgrade"},
                        )

                        # 403 or 426 indicates WebSocket endpoint exists
                        if response.status_code in WS_ENDPOINT_STATUS_CODES:
                            discovered.append(
                                {
                                    "port": port,
                                    "path": ws_path,
                                    "method": "WS",
                                    "entry_type": "websocket",
                                    "source": "probe",
                                    "title": f"WebSocket - {port_info.service_name}",
                                    "service_name": port_info.service_name,
                                }
                            )
                            logger.info(
                                "sitemap_websocket_found",
                                port=port,
                                path=ws_path,
                                service=port_info.service_name,
                            )

                    except Exception as e:
                        logger.debug(
                            "sitemap_websocket_probe_failed", port=port, path=ws_path, error=str(e)
                        )

        logger.info("sitemap_discover_websocket_complete", count=len(discovered))
        return discovered

    async def discover_frontend_pages(self, max_depth: int = 3) -> list[dict[str, Any]]:
        """Crawl frontend to discover pages by following links.

        Args:
            max_depth: Maximum crawl depth

        Returns:
            List of discovered page dicts
        """
        logger.info("sitemap_discover_frontend_start")
        discovered = []
        visited: set[str] = set()
        to_visit: list[tuple[str, int]] = [("/", 0)]  # (path, depth)

        frontend_port = self.frontend_port
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
            while to_visit:
                path, depth = to_visit.pop(0)

                if path in visited or depth > max_depth:
                    continue
                visited.add(path)

                try:
                    url = f"http://{FRONTEND_HOST}:{frontend_port}{path}"
                    response = await client.get(url)

                    if response.status_code == 200:
                        # Extract page metadata
                        metadata = _extract_page_metadata(response.text)

                        discovered.append(
                            {
                                "port": frontend_port,
                                "path": path,
                                "method": "GET",
                                "entry_type": "frontend_page",
                                "source": "crawler",
                                "title": metadata["title"],
                            }
                        )

                        # Queue internal links for crawling
                        _queue_internal_links(
                            response.text, depth, max_depth, visited, to_visit
                        )

                except Exception as e:
                    logger.debug("sitemap_crawl_page_failed", path=path, error=str(e))

        logger.info("sitemap_discover_frontend_complete", count=len(discovered))
        return discovered

    def discover_nextjs_routes(self, frontend_dir: str | None = None) -> list[dict[str, Any]]:
        """Parse Next.js app directory to discover all routes.

        This provides complete route discovery including:
        - Static routes (/watchlist, /portfolio)
        - Dynamic routes (/ideas/[id] -> /ideas/{id})
        - Tab variations detected from useSearchParams

        Args:
            frontend_dir: Path to frontend directory, defaults to ~/portfolio-ai/frontend

        Returns:
            List of discovered route dicts
        """
        logger.info("sitemap_discover_nextjs_start")
        discovered: list[dict[str, Any]] = []

        if frontend_dir is None:
            frontend_dir = str(Path.home() / "portfolio-ai" / "frontend")

        app_dir = Path(frontend_dir) / "app"
        if not app_dir.exists():
            logger.warning("sitemap_nextjs_app_dir_not_found", path=str(app_dir))
            return discovered

        # Find all page.tsx files
        page_files = list(app_dir.glob("**/page.tsx"))
        logger.info("sitemap_nextjs_pages_found", count=len(page_files))

        for page_file in page_files:
            try:
                # Convert file path to route
                # app/page.tsx -> /
                # app/watchlist/page.tsx -> /watchlist
                # app/ideas/[id]/page.tsx -> /ideas/{id}
                relative_path = page_file.relative_to(app_dir)
                route_parts = list(relative_path.parts[:-1])  # Remove page.tsx

                if not route_parts:
                    route = "/"
                else:
                    # Convert [param] to {param} for template notation
                    converted_parts = []
                    for part in route_parts:
                        if part.startswith("[") and part.endswith("]"):
                            # Dynamic segment: [id] -> {id}
                            param_name = part[1:-1]
                            converted_parts.append(f"{{{param_name}}}")
                        else:
                            converted_parts.append(part)
                    route = "/" + "/".join(converted_parts)

                # Get page title from file (look for metadata or component name)
                title = self._extract_page_title(page_file)

                # Check for tab variations
                tab_values = self._extract_tab_values(page_file)

                # Add base route
                discovered.append(
                    {
                        "port": self.frontend_port,
                        "path": route,
                        "method": "GET",
                        "entry_type": "frontend_page",
                        "source": "nextjs_app",
                        "title": title,
                        "has_dynamic_segment": "{" in route,
                    }
                )

                # Add tab variations as separate entries
                for tab in tab_values:
                    discovered.append(
                        {
                            "port": self.frontend_port,
                            "path": f"{route}?tab={tab}",
                            "method": "GET",
                            "entry_type": "frontend_page",
                            "source": "nextjs_app",
                            "title": f"{title} - {tab.title()}" if title else tab.title(),
                            "parent_path": route,
                        }
                    )

            except Exception as e:
                logger.debug("sitemap_nextjs_parse_failed", file=str(page_file), error=str(e))

        logger.info("sitemap_discover_nextjs_complete", count=len(discovered))
        return discovered

    def _extract_page_title(self, page_file: Path) -> str | None:
        """Extract page title from Next.js page file.

        Looks for:
        - metadata.title export
        - PageHeader title prop
        - Component function name

        Args:
            page_file: Path to page.tsx file

        Returns:
            Title string or None
        """
        try:
            content = page_file.read_text()

            # Look for metadata title
            # export const metadata = { title: "Watchlist" }
            metadata_match = METADATA_TITLE_PATTERN.search(content)
            if metadata_match:
                return metadata_match.group(1)

            # Look for PageHeader title prop
            # <PageHeader title="Watchlist"
            header_match = PAGE_HEADER_TITLE_PATTERN.search(content)
            if header_match:
                return header_match.group(1)

            # Fallback: derive from directory name
            parent_dir = page_file.parent.name
            if parent_dir != "app":
                # Convert kebab-case to Title Case
                return parent_dir.replace("-", " ").replace("_", " ").title()

            return "Home"

        except Exception:
            return None

    def _extract_tab_values(self, page_file: Path) -> list[str]:
        """Extract tab values from page that uses useSearchParams.

        Looks for:
        - TabValue type definitions
        - Tabs component with TabsTrigger values
        - searchParams.get("tab") usage

        Args:
            page_file: Path to page.tsx file

        Returns:
            List of tab value strings
        """
        tabs: list[str] = []
        try:
            content = page_file.read_text()

            # Check if page uses tabs
            if "useSearchParams" not in content and "searchParams" not in content:
                return tabs

            # Look for TabValue type definition (e.g. type TabValue = "x" | "y")
            tabvalue_match = TAB_VALUE_TYPE_PATTERN.search(content)
            if tabvalue_match:
                values_str = tabvalue_match.group(1)
                # Extract quoted strings
                tabs = QUOTED_STRING_PATTERN.findall(values_str)
                return tabs

            # Look for TabsTrigger values
            # <TabsTrigger value="workflows">
            trigger_matches = TABS_TRIGGER_PATTERN.findall(content)
            if trigger_matches:
                return list(set(trigger_matches))

        except Exception:
            pass

        return tabs
