"""Sitemap Service - Discovery and health monitoring for all endpoints.

This module provides:
- Discovery of backend API endpoints (via OpenAPI)
- Discovery of frontend pages (via crawling)
- Health checks (HTTP status, console errors/warnings)
- CRUD operations for sitemap entries
- Import from existing api_capabilities table
"""

from __future__ import annotations

import asyncio
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar

import httpx

from ..logging_config import get_logger
from ..storage.connection import get_connection_manager

logger = get_logger(__name__)

# Configuration
HTTP_TIMEOUT = 10  # seconds

# Network configuration
FRONTEND_HOST = "192.168.8.233"  # Network IP for SSR routing
BACKEND_HOST = "localhost"

# Endpoints to skip during health checks (even for GET requests)
# These endpoints either:
# - Trigger external API calls (expensive)
# - Do heavy computation
# - Have path parameters without safe test values
# - Could trigger side effects even on GET
SKIP_HEALTH_CHECK_PATTERNS: list[str] = [
    # Market data endpoints - trigger external API calls
    "/api/market/intelligence",  # Fetches live market data from yfinance/polygon
    "/api/market/prices",  # Fetches live prices
    "/api/market/movers",  # Fetches market movers
    "/api/market/status",  # May fetch external data
    # Symbol intelligence - potentially expensive
    "/api/symbols/{symbol}/intelligence",  # Heavy aggregation
    # Analytics endpoints with symbol params - expensive external fetches
    "/api/analytics/rvol/",  # Fetches historical data
    "/api/analytics/peers/",  # Fetches peer data
    "/api/analytics/short-interest/",  # Fetches short interest
    "/api/analytics/cash-flow/",  # Fetches financial data
    "/api/analytics/insider-transactions/",  # Fetches insider data
    "/api/analytics/institutional-holdings/",  # Fetches holdings data
    # News endpoints - may trigger external fetches
    "/api/news/intelligence",  # Fetches news from APIs
    # Valuation endpoints - expensive calculations
    "/api/valuation/metrics",
    # Health endpoints - avoid circular calls
    "/api/health/detailed",  # This endpoint does heavy checks
    "/health",  # Skip all health endpoints
    # Celery endpoints - may interact with worker
    "/api/celery/",  # Celery inspection can be slow
    # Backup endpoints - may trigger filesystem operations
    "/api/backup/status",
    "/api/backup/latest",
    # ML endpoints - expensive operations
    "/api/ml/",
    # Backtest endpoints - heavy computation
    "/api/backtest/run",
]

def should_skip_health_check(path: str) -> str | None:
    """Check if a path should be skipped during health checks.

    Supports both exact matches and pattern matching with path parameters.
    Pattern like '/api/symbols/{symbol}/intelligence' matches '/api/symbols/AAPL/intelligence'.

    Args:
        path: The endpoint path to check

    Returns:
        Skip reason string if should skip, None otherwise
    """
    for pattern in SKIP_HEALTH_CHECK_PATTERNS:
        # Check for exact match
        if path == pattern:
            return f"Skipped (expensive: {pattern})"

        # Check for prefix match (patterns ending with /)
        if pattern.endswith("/") and path.startswith(pattern):
            return f"Skipped (expensive: {pattern})"

        # Check for path parameter patterns like {symbol}
        if "{" in pattern:
            # Convert pattern to regex: /api/symbols/{symbol}/intelligence -> /api/symbols/[^/]+/intelligence
            regex_pattern = re.sub(r"\{[^}]+\}", r"[^/]+", pattern)
            if re.fullmatch(regex_pattern, path):
                return f"Skipped (expensive: {pattern})"

        # Simple prefix match for patterns without trailing /
        if not pattern.endswith("/") and path.startswith(pattern + "/"):
            return f"Skipped (expensive: {pattern})"

    return None


@dataclass
class DiscoveredPort:
    """A port discovered from systemd services or probing."""

    port: int
    service_name: str  # e.g., "portfolio-backend", "portfolio-frontend"
    service_type: str  # "backend", "frontend", "websocket", "unknown"
    source: str  # "systemd", "probe", "manual"
    description: str | None = None


class PortDiscovery:
    """Discovers ports from systemd user services."""

    # Patterns to extract port from ExecStart command
    PORT_PATTERNS: ClassVar[list[str]] = [
        r"--port[=\s]+(\d+)",  # --port 8000 or --port=8000
        r"-p[=\s]+(\d+)",  # -p 8000 or -p=8000
        r":(\d+)$",  # localhost:8000
    ]

    # Service type mapping based on service name or command
    SERVICE_TYPE_HINTS: ClassVar[dict[str, str]] = {
        "backend": "backend",
        "frontend": "frontend",
        "celery": "worker",
        "beat": "scheduler",
        "redis": "cache",
        "companion": "websocket",
    }

    # Common ports to probe if systemd discovery fails
    PROBE_PORTS: ClassVar[list[int]] = [80, 443, 3000, 8000, 8080, 9999]

    def __init__(self) -> None:
        self._systemd_dir = Path.home() / ".config" / "systemd" / "user"
        self._cached_ports: dict[int, DiscoveredPort] | None = None

    def discover_from_systemd(self) -> list[DiscoveredPort]:
        """Parse systemd user services to find portfolio-* services and their ports.

        Returns:
            List of discovered ports with metadata
        """
        discovered = []

        try:
            # List portfolio-* services
            result = subprocess.run(
                ["systemctl", "--user", "list-units", "--type=service", "--all", "--no-pager"],
                check=False, capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode != 0:
                logger.warning("systemd_list_failed", stderr=result.stderr)
                return discovered

            # Find portfolio-* services
            service_names = []
            for line in result.stdout.splitlines():
                if "portfolio-" in line and ".service" in line:
                    # Extract service name
                    parts = line.split()
                    if parts:
                        service_name = parts[0].replace(".service", "")
                        service_names.append(service_name)

            logger.info("systemd_services_found", count=len(service_names), services=service_names)

            # Get details for each service
            for service_name in service_names:
                port_info = self._parse_service_file(service_name)
                if port_info:
                    discovered.append(port_info)

        except subprocess.TimeoutExpired:
            logger.warning("systemd_command_timeout")
        except Exception as e:
            logger.error("systemd_discovery_failed", error=str(e))

        return discovered

    def _parse_service_file(self, service_name: str) -> DiscoveredPort | None:
        """Parse a systemd service file to extract port configuration.

        Args:
            service_name: Name of the systemd service (without .service suffix)

        Returns:
            DiscoveredPort if port found, None otherwise
        """
        service_file = self._systemd_dir / f"{service_name}.service"

        # Resolve symlink if needed
        if service_file.is_symlink():
            service_file = service_file.resolve()

        if not service_file.exists():
            return None

        try:
            content = service_file.read_text()
        except Exception as e:
            logger.debug("service_file_read_failed", service=service_name, error=str(e))
            return None

        port = None
        description = None

        # Extract Description
        desc_match = re.search(r"^Description=(.+)$", content, re.MULTILINE)
        if desc_match:
            description = desc_match.group(1).strip()

        # Try to extract port from Environment=PORT=XXXX
        env_match = re.search(r"Environment=[\"']?PORT=(\d+)[\"']?", content)
        if env_match:
            port = int(env_match.group(1))

        # Try to extract port from ExecStart command
        if not port:
            exec_match = re.search(r"^ExecStart=(.+)$", content, re.MULTILINE)
            if exec_match:
                exec_cmd = exec_match.group(1)
                for pattern in self.PORT_PATTERNS:
                    port_match = re.search(pattern, exec_cmd)
                    if port_match:
                        port = int(port_match.group(1))
                        break

        if not port:
            return None

        # Determine service type
        service_type = "unknown"
        name_lower = service_name.lower()
        for hint, stype in self.SERVICE_TYPE_HINTS.items():
            if hint in name_lower:
                service_type = stype
                break

        return DiscoveredPort(
            port=port,
            service_name=service_name,
            service_type=service_type,
            source="systemd",
            description=description,
        )

    async def probe_ports(self, ports: list[int] | None = None) -> list[DiscoveredPort]:
        """Probe common ports to discover running services.

        Args:
            ports: List of ports to probe, defaults to PROBE_PORTS

        Returns:
            List of discovered ports that respond to HTTP
        """
        if ports is None:
            ports = self.PROBE_PORTS

        discovered = []

        async with httpx.AsyncClient(timeout=2) as client:
            for port in ports:
                try:
                    # Try localhost first
                    response = await client.get(f"http://localhost:{port}/")
                    if response.status_code < 500:
                        discovered.append(
                            DiscoveredPort(
                                port=port,
                                service_name=f"unknown-{port}",
                                service_type="unknown",
                                source="probe",
                                description=f"HTTP service on port {port}",
                            )
                        )
                except Exception:
                    pass  # Port not responding

        return discovered

    def get_all_ports(self) -> dict[int, DiscoveredPort]:
        """Get all discovered ports, combining systemd and cached results.

        Returns:
            Dict mapping port number to DiscoveredPort info
        """
        if self._cached_ports is not None:
            return self._cached_ports

        ports = {}

        # Discover from systemd
        for port_info in self.discover_from_systemd():
            ports[port_info.port] = port_info

        self._cached_ports = ports
        return ports

    def clear_cache(self) -> None:
        """Clear the cached port discovery results."""
        self._cached_ports = None


# Global port discovery instance
_port_discovery = PortDiscovery()


def get_discovered_ports() -> dict[int, DiscoveredPort]:
    """Get all discovered ports from systemd services."""
    return _port_discovery.get_all_ports()


def get_port_for_service(service_type: str) -> int | None:
    """Get port for a specific service type.

    Args:
        service_type: One of "backend", "frontend", "websocket"

    Returns:
        Port number or None if not found
    """
    ports = get_discovered_ports()
    for port, info in ports.items():
        if info.service_type == service_type:
            return port

    # Fallback to defaults if discovery fails
    defaults = {"backend": 8000, "frontend": 3000, "websocket": 9999}
    return defaults.get(service_type)


class SitemapService:
    """Discovers and monitors sitemap entries."""

    def __init__(self) -> None:
        self.conn_mgr = get_connection_manager()
        self._port_discovery = PortDiscovery()

    @property
    def backend_port(self) -> int:
        """Get the backend port (dynamically discovered or fallback)."""
        return get_port_for_service("backend") or 8000

    @property
    def frontend_port(self) -> int:
        """Get the frontend port (dynamically discovered or fallback)."""
        return get_port_for_service("frontend") or 3000

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
    # Discovery Methods
    # =========================================================================

    async def discover_backend_endpoints(self) -> list[dict[str, Any]]:
        """Parse /openapi.json to discover backend API endpoints.

        Returns:
            List of discovered endpoint dicts
        """
        logger.info("sitemap_discover_backend_start")
        discovered = []

        try:
            backend_port = self.backend_port
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                response = await client.get(f"http://{BACKEND_HOST}:{backend_port}/openapi.json")
                response.raise_for_status()
                openapi = response.json()

            paths = openapi.get("paths", {})
            for path, methods in paths.items():
                for method, details in methods.items():
                    if method.upper() in ("GET", "POST", "PUT", "DELETE", "PATCH"):
                        # Skip health/docs endpoints
                        if any(x in path for x in ["/health", "/docs", "/openapi", "/redoc"]):
                            continue

                        discovered.append({
                            "port": backend_port,
                            "path": path,
                            "method": method.upper(),
                            "entry_type": "api_endpoint",
                            "source": "openapi",
                            "title": details.get("summary") or details.get("operationId"),
                        })

            logger.info("sitemap_discover_backend_complete", count=len(discovered))

        except Exception as e:
            logger.error("sitemap_discover_backend_failed", error=str(e))

        return discovered

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
            p for p in ports.values()
            if p.service_type in ("backend", "websocket", "unknown")
        ]

        logger.info("sitemap_openapi_candidates", count=len(openapi_candidates),
                    ports=[p.port for p in openapi_candidates])

        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            for port_info in openapi_candidates:
                port = port_info.port
                try:
                    response = await client.get(f"http://{BACKEND_HOST}:{port}/openapi.json")
                    if response.status_code != 200:
                        continue

                    openapi = response.json()
                    paths = openapi.get("paths", {})

                    port_discovered = 0
                    for path, methods in paths.items():
                        for method, details in methods.items():
                            if method.upper() in ("GET", "POST", "PUT", "DELETE", "PATCH"):
                                # Skip health/docs endpoints
                                if any(x in path for x in ["/health", "/docs", "/openapi", "/redoc"]):
                                    continue

                                all_discovered.append({
                                    "port": port,
                                    "path": path,
                                    "method": method.upper(),
                                    "entry_type": "api_endpoint",
                                    "source": "openapi",
                                    "title": details.get("summary") or details.get("operationId"),
                                    "service_name": port_info.service_name,
                                })
                                port_discovered += 1

                    logger.info("sitemap_openapi_port_complete",
                               port=port, service=port_info.service_name, count=port_discovered)

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
            p for p in ports.values()
            if p.service_type in ("websocket", "backend", "unknown")
        ]

        # Common WebSocket paths to probe
        ws_paths = ["/ws", "/ws/{session_id}", "/socket.io"]

        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            for port_info in ws_candidates:
                port = port_info.port

                # Try WebSocket upgrade on common paths
                for ws_path in ws_paths:
                    try:
                        # Check if endpoint exists (even without upgrade)
                        # FastAPI WebSocket endpoints return 403 for non-WS requests
                        test_path = ws_path.replace("{session_id}", "test")
                        response = await client.get(
                            f"http://{BACKEND_HOST}:{port}{test_path}",
                            headers={"Upgrade": "websocket", "Connection": "Upgrade"},
                        )

                        # 403 or 426 indicates WebSocket endpoint exists
                        if response.status_code in (403, 426, 400):
                            discovered.append({
                                "port": port,
                                "path": ws_path,
                                "method": "WS",
                                "entry_type": "websocket",
                                "source": "probe",
                                "title": f"WebSocket - {port_info.service_name}",
                                "service_name": port_info.service_name,
                            })
                            logger.info("sitemap_websocket_found",
                                       port=port, path=ws_path, service=port_info.service_name)

                    except Exception as e:
                        logger.debug("sitemap_websocket_probe_failed",
                                    port=port, path=ws_path, error=str(e))

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
                        # Get page title from HTML
                        title = None
                        title_match = re.search(r"<title>([^<]+)</title>", response.text, re.IGNORECASE)
                        if title_match:
                            title = title_match.group(1).strip()

                        discovered.append({
                            "port": frontend_port,
                            "path": path,
                            "method": "GET",
                            "entry_type": "frontend_page",
                            "source": "crawler",
                            "title": title,
                        })

                        # Extract internal links for crawling
                        if depth < max_depth:
                            links = re.findall(r'href=["\']([^"\']+)["\']', response.text)
                            for link in links:
                                # Only follow internal links, skip static assets and API calls
                                skip_patterns = ["/api/", "/_next/", "/static/", ".js", ".css", ".png", ".jpg"]
                                if (
                                    link.startswith("/")
                                    and not link.startswith("//")
                                    and not any(x in link for x in skip_patterns)
                                ):
                                    clean_path = link.split("?")[0].split("#")[0]
                                    if clean_path not in visited:
                                        to_visit.append((clean_path, depth + 1))

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
        discovered = []

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
                discovered.append({
                    "port": self.frontend_port,
                    "path": route,
                    "method": "GET",
                    "entry_type": "frontend_page",
                    "source": "nextjs_app",
                    "title": title,
                    "has_dynamic_segment": "{" in route,
                })

                # Add tab variations as separate entries
                for tab in tab_values:
                    discovered.append({
                        "port": self.frontend_port,
                        "path": f"{route}?tab={tab}",
                        "method": "GET",
                        "entry_type": "frontend_page",
                        "source": "nextjs_app",
                        "title": f"{title} - {tab.title()}" if title else tab.title(),
                        "parent_path": route,
                    })

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
            metadata_match = re.search(r'title:\s*["\']([^"\']+)["\']', content)
            if metadata_match:
                return metadata_match.group(1)

            # Look for PageHeader title prop
            # <PageHeader title="Watchlist"
            header_match = re.search(r'<PageHeader[^>]*title=["\']([^"\']+)["\']', content)
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
        tabs = []
        try:
            content = page_file.read_text()

            # Check if page uses tabs
            if "useSearchParams" not in content and "searchParams" not in content:
                return tabs

            # Look for TabValue type definition (e.g. type TabValue = "x" | "y")
            tabvalue_match = re.search(r'type\s+TabValue\s*=\s*([^;]+);', content)
            if tabvalue_match:
                values_str = tabvalue_match.group(1)
                # Extract quoted strings
                tabs = re.findall(r'["\']([^"\']+)["\']', values_str)
                return tabs

            # Look for TabsTrigger values
            # <TabsTrigger value="workflows">
            trigger_matches = re.findall(r'<TabsTrigger[^>]*value=["\']([^"\']+)["\']', content)
            if trigger_matches:
                return list(set(trigger_matches))

        except Exception:
            pass

        return tabs

    def import_from_api_capabilities(self) -> int:
        """Import existing API capabilities into sitemap_entries.

        Returns:
            Number of entries imported
        """
        logger.info("sitemap_import_api_capabilities_start")

        with self.conn_mgr.connection() as conn:
            # Get existing API capabilities
            result = conn.execute("""
                SELECT endpoint_path, http_method, category, function_name
                FROM api_capabilities
            """)
            api_caps = result.fetchall()

            imported = 0
            for row in api_caps:
                endpoint_path, http_method, category, function_name = row
                try:
                    conn.execute("""
                        INSERT INTO sitemap_entries (port, path, method, entry_type, source, title)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (port, path, method) DO UPDATE SET
                            title = EXCLUDED.title,
                            updated_at = NOW()
                    """, [self.backend_port, endpoint_path, http_method, "api_endpoint", "api_scanner", function_name or category])
                    imported += 1
                except Exception as e:
                    logger.debug("sitemap_import_row_failed", path=endpoint_path, error=str(e))

            conn.commit()

        logger.info("sitemap_import_api_capabilities_complete", imported=imported)
        return imported

    async def run_discovery(self) -> dict[str, Any]:
        """Run comprehensive discovery across all service types.

        Discovery methods:
        - OpenAPI: All ports with /openapi.json (backend, dev-companion, etc.)
        - Frontend: Crawl pages and parse Next.js app directory
        - WebSocket: Probe for WS endpoints on applicable ports
        - API capabilities: Import from legacy api_capabilities table

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
        api_imported = self.import_from_api_capabilities()

        # Combine all entries
        all_entries = all_openapi_entries + frontend_entries + websocket_entries + nextjs_entries
        saved = 0

        with self.conn_mgr.connection() as conn:
            for entry in all_entries:
                try:
                    conn.execute("""
                        INSERT INTO sitemap_entries (port, path, method, entry_type, source, title, discovered_at)
                        VALUES (%s, %s, %s, %s, %s, %s, NOW())
                        ON CONFLICT (port, path, method) DO UPDATE SET
                            title = COALESCE(EXCLUDED.title, sitemap_entries.title),
                            source = EXCLUDED.source,
                            updated_at = NOW()
                    """, [
                        entry["port"],
                        entry["path"],
                        entry["method"],
                        entry["entry_type"],
                        entry["source"],
                        entry.get("title"),
                    ])
                    saved += 1
                except Exception as e:
                    logger.debug("sitemap_save_entry_failed", path=entry["path"], error=str(e))

            conn.commit()

        result = {
            "openapi_discovered": len(all_openapi_entries),
            "frontend_discovered": len(frontend_entries),
            "websocket_discovered": len(websocket_entries),
            "nextjs_discovered": len(nextjs_entries),
            "api_imported": api_imported,
            "total_saved": saved,
        }

        logger.info("sitemap_full_discovery_complete", **result)
        return result

    # =========================================================================
    # Health Check Methods
    # =========================================================================

    async def check_entry_health(self, entry_id: int) -> dict[str, Any]:
        """Check health of a single sitemap entry.

        For frontend pages: HTTP fetch + console capture
        For API endpoints: HTTP fetch only

        Args:
            entry_id: ID of sitemap entry to check

        Returns:
            Health check result dict
        """
        # Get entry details
        entry = self.get_entry(entry_id)
        if not entry:
            return {"success": False, "error": "Entry not found"}

        port = entry["port"]
        path = entry["path"]
        method = entry["method"]

        # Build URL - substitute path parameters with test values
        test_path = path
        if "{symbol}" in path:
            test_path = path.replace("{symbol}", "SPY")

        host = FRONTEND_HOST if port == self.frontend_port else BACKEND_HOST
        url = f"http://{host}:{port}{test_path}"

        console_errors = 0
        console_warnings = 0
        http_status = None
        response_time_ms = None
        error_details: dict[str, Any] = {}
        last_error_message = None

        # Skip streaming endpoints (SSE, WebSocket) - they never complete
        # Also skip POST/PUT/DELETE - they may trigger side effects
        # Also skip expensive GET endpoints that trigger external API calls
        is_streaming = "/stream" in path or "/ws" in path.lower() or method == "WS"
        is_mutating = method in ("POST", "PUT", "DELETE", "PATCH")
        expensive_skip_reason = should_skip_health_check(path)

        if is_streaming or is_mutating or expensive_skip_reason:
            health_status = "healthy"
            http_status = 0  # Indicates skipped, not actually checked
            if is_streaming:
                skip_reason = "Skipped (streaming)"
            elif is_mutating:
                skip_reason = "Skipped (mutating method)"
            else:
                skip_reason = expensive_skip_reason
            # Update entry and return early
            with self.conn_mgr.connection() as conn:
                conn.execute("""
                    UPDATE sitemap_entries SET
                        health_status = %s,
                        http_status = %s,
                        last_error_message = %s,
                        last_checked_at = NOW(),
                        updated_at = NOW()
                    WHERE id = %s
                """, [health_status, http_status, skip_reason, entry_id])
                conn.commit()
            return {
                "success": True,
                "entry_id": entry_id,
                "health_status": health_status,
                "console_errors": 0,
                "console_warnings": 0,
                "http_status": http_status,
                "response_time_ms": None,
                "error": None,
            }

        try:
            # HTTP-only health check for GET endpoints
            # Console error capture is done separately via evidence gathering
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                request_start = datetime.now(UTC)
                response = await client.request(method, url)
                response_time_ms = int((datetime.now(UTC) - request_start).total_seconds() * 1000)
                http_status = response.status_code

                # Only true errors are:
                # - 5xx (server error)
                # - 404 with generic "Not Found" (route doesn't exist)
                # Other 4xx codes (400, 405, 422) mean route exists but needs proper input
                # 404 with specific message = route exists but no data for this param
                is_error = False
                if response.status_code >= 500:
                    is_error = True
                    last_error_message = f"HTTP {response.status_code}"
                elif response.status_code == 404:
                    # Check if this is a real "route not found" vs "data not found"
                    try:
                        body = response.json()
                        # Generic FastAPI 404 = route doesn't exist
                        if body.get("detail") == "Not Found":
                            is_error = True
                            last_error_message = "Route not found"
                        # Specific message = route exists, just no data
                    except Exception:
                        is_error = True
                        last_error_message = "HTTP 404"

                if is_error:
                    console_errors = 1

        except Exception as e:
            console_errors = 1
            last_error_message = str(e)[:500]
            error_details["exception"] = str(e)

        # Determine health status
        if console_errors > 0:
            health_status = "error"
        elif console_warnings > 0:
            health_status = "warning"
        else:
            health_status = "healthy"

        # Update sitemap_entries
        with self.conn_mgr.connection() as conn:
            conn.execute("""
                UPDATE sitemap_entries SET
                    health_status = %s,
                    console_errors = %s,
                    console_warnings = %s,
                    http_status = %s,
                    response_time_ms = %s,
                    last_error_message = %s,
                    last_checked_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
            """, [
                health_status,
                console_errors,
                console_warnings,
                http_status,
                response_time_ms,
                last_error_message,
                entry_id,
            ])

            # Insert into history
            conn.execute("""
                INSERT INTO sitemap_health_history
                    (sitemap_entry_id, checked_at, health_status, console_errors, console_warnings,
                     http_status, response_time_ms, error_details)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, [
                entry_id,
                datetime.now(UTC),
                health_status,
                console_errors,
                console_warnings,
                http_status,
                response_time_ms,
                json.dumps(error_details) if error_details else None,
            ])

            conn.commit()

        return {
            "success": True,
            "entry_id": entry_id,
            "health_status": health_status,
            "console_errors": console_errors,
            "console_warnings": console_warnings,
            "http_status": http_status,
            "response_time_ms": response_time_ms,
        }

    async def check_all_health(self) -> dict[str, Any]:
        """Check health of all sitemap entries.

        Returns:
            Summary of health check results
        """
        logger.info("sitemap_check_all_health_start")

        # Get all entries
        entries, _total = self.get_entries(limit=1000)

        checked = 0
        healthy = 0
        warnings = 0
        errors = 0

        for entry in entries:
            result = await self.check_entry_health(entry["id"])
            checked += 1

            if result.get("health_status") == "healthy":
                healthy += 1
            elif result.get("health_status") == "warning":
                warnings += 1
            else:
                errors += 1

        result = {
            "checked": checked,
            "healthy": healthy,
            "warnings": warnings,
            "errors": errors,
        }

        logger.info("sitemap_check_all_health_complete", **result)
        return result

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    def get_entries(
        self,
        port: int | None = None,
        health_status: str | None = None,
        entry_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """Get sitemap entries with filtering.

        Args:
            port: Filter by port
            health_status: Filter by health status
            entry_type: Filter by entry type
            limit: Max results
            offset: Pagination offset

        Returns:
            Tuple of (entries list, total count)
        """
        conditions = []
        params: list[Any] = []

        if port is not None:
            conditions.append("port = %s")
            params.append(port)
        if health_status:
            conditions.append("health_status = %s")
            params.append(health_status)
        if entry_type:
            conditions.append("entry_type = %s")
            params.append(entry_type)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        with self.conn_mgr.connection() as conn:
            # Get total count
            count_result = conn.execute(
                f"SELECT COUNT(*) FROM sitemap_entries WHERE {where_clause}",
                params,
            )
            total = count_result.fetchone()[0]

            # Get entries
            result = conn.execute(
                f"""
                SELECT id, port, path, method, entry_type, source, title, parent_path,
                       health_status, console_errors, console_warnings, http_status,
                       response_time_ms, last_error_message, artifact_id,
                       last_checked_at, discovered_at
                FROM sitemap_entries
                WHERE {where_clause}
                ORDER BY port, path
                LIMIT %s OFFSET %s
                """,
                [*params, limit, offset],
            )

            entries = []
            for row in result.fetchall():
                entries.append({
                    "id": row[0],
                    "port": row[1],
                    "path": row[2],
                    "method": row[3],
                    "entry_type": row[4],
                    "source": row[5],
                    "title": row[6],
                    "parent_path": row[7],
                    "health_status": row[8],
                    "console_errors": row[9],
                    "console_warnings": row[10],
                    "http_status": row[11],
                    "response_time_ms": row[12],
                    "last_error_message": row[13],
                    "artifact_id": row[14],
                    "last_checked_at": row[15].isoformat() if row[15] else None,
                    "discovered_at": row[16].isoformat() if row[16] else None,
                })

            return entries, total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        """Get single entry by ID.

        Args:
            entry_id: Entry ID

        Returns:
            Entry dict or None
        """
        with self.conn_mgr.connection() as conn:
            result = conn.execute("""
                SELECT id, port, path, method, entry_type, source, title, parent_path,
                       health_status, console_errors, console_warnings, http_status,
                       response_time_ms, last_error_message, artifact_id,
                       last_checked_at, discovered_at
                FROM sitemap_entries
                WHERE id = %s
            """, [entry_id])

            row = result.fetchone()
            if not row:
                return None

            return {
                "id": row[0],
                "port": row[1],
                "path": row[2],
                "method": row[3],
                "entry_type": row[4],
                "source": row[5],
                "title": row[6],
                "parent_path": row[7],
                "health_status": row[8],
                "console_errors": row[9],
                "console_warnings": row[10],
                "http_status": row[11],
                "response_time_ms": row[12],
                "last_error_message": row[13],
                "artifact_id": row[14],
                "last_checked_at": row[15].isoformat() if row[15] else None,
                "discovered_at": row[16].isoformat() if row[16] else None,
            }

    def get_health_summary(self) -> dict[str, Any]:
        """Get aggregate health statistics.

        Returns:
            Dict with total, healthy, warning, error, unknown counts
        """
        with self.conn_mgr.connection() as conn:
            result = conn.execute("""
                SELECT
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE health_status = 'healthy') as healthy,
                    COUNT(*) FILTER (WHERE health_status = 'warning') as warning,
                    COUNT(*) FILTER (WHERE health_status = 'error') as error,
                    COUNT(*) FILTER (WHERE health_status = 'unknown' OR health_status IS NULL) as unknown
                FROM sitemap_entries
            """)
            row = result.fetchone()

            # Get counts by port
            port_result = conn.execute("""
                SELECT port,
                    COUNT(*) FILTER (WHERE health_status = 'healthy') as healthy,
                    COUNT(*) FILTER (WHERE health_status = 'warning') as warning,
                    COUNT(*) FILTER (WHERE health_status = 'error') as error,
                    COUNT(*) FILTER (WHERE health_status = 'unknown' OR health_status IS NULL) as unknown
                FROM sitemap_entries
                GROUP BY port
            """)

            by_port = {}
            for port_row in port_result.fetchall():
                by_port[str(port_row[0])] = {
                    "healthy": port_row[1],
                    "warning": port_row[2],
                    "error": port_row[3],
                    "unknown": port_row[4],
                }

            return {
                "total": row[0],
                "healthy": row[1],
                "warning": row[2],
                "error": row[3],
                "unknown": row[4],
                "by_port": by_port,
            }

    def register_entry(
        self,
        port: int,
        path: str,
        method: str = "GET",
        entry_type: str = "manual",
        title: str | None = None,
    ) -> dict[str, Any]:
        """Manually register a new sitemap entry.

        Args:
            port: Port number
            path: URL path
            method: HTTP method
            entry_type: Entry type
            title: Optional title

        Returns:
            Created entry dict
        """
        with self.conn_mgr.connection() as conn:
            result = conn.execute("""
                INSERT INTO sitemap_entries (port, path, method, entry_type, source, title)
                VALUES (%s, %s, %s, %s, 'manual', %s)
                RETURNING id
            """, [port, path, method, entry_type, title])

            entry_id = result.fetchone()[0]
            conn.commit()

        return self.get_entry(entry_id)  # type: ignore

    def delete_entry(self, entry_id: int) -> bool:
        """Remove a sitemap entry.

        Args:
            entry_id: Entry ID to delete

        Returns:
            True if deleted, False if not found
        """
        with self.conn_mgr.connection() as conn:
            result = conn.execute(
                "DELETE FROM sitemap_entries WHERE id = %s RETURNING id",
                [entry_id],
            )
            deleted = result.fetchone() is not None
            conn.commit()
            return deleted

    # =========================================================================
    # Maintenance
    # =========================================================================

    def cleanup_old_history(self, days: int = 7) -> int:
        """Delete health history older than specified days.

        Args:
            days: Number of days to keep

        Returns:
            Number of rows deleted
        """
        with self.conn_mgr.connection() as conn:
            result = conn.execute("""
                DELETE FROM sitemap_health_history
                WHERE checked_at < NOW() - INTERVAL '%s days'
                RETURNING id
            """, [days])
            deleted = len(result.fetchall())
            conn.commit()

        logger.info("sitemap_cleanup_history", deleted=deleted, retention_days=days)
        return deleted

    def get_history_stats(self) -> dict[str, Any]:
        """Get health history statistics for maintenance UI.

        Returns:
            Dict with total_rows, oldest_entry, storage_estimate
        """
        with self.conn_mgr.connection() as conn:
            result = conn.execute("""
                SELECT
                    COUNT(*) as total_rows,
                    MIN(checked_at) as oldest_entry,
                    pg_size_pretty(pg_total_relation_size('sitemap_health_history')) as storage_size
                FROM sitemap_health_history
            """)
            row = result.fetchone()

            return {
                "total_rows": row[0],
                "oldest_entry": row[1].isoformat() if row[1] else None,
                "storage_size": row[2],
            }
