"""Sitemap Discovery Helpers - Constants, regex patterns, and utility functions.

This module is internal to the sitemap package and provides:
- Configuration constants (timeouts, hosts, patterns)
- Compiled regex patterns for HTML/TSX parsing
- Pure helper functions used by SitemapDiscoveryService
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

HTTP_TIMEOUT = 10  # seconds

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

# HTTP methods accepted from OpenAPI specs
OPENAPI_ACCEPTED_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH"}

# OpenAPI paths to skip (internal/docs endpoints)
OPENAPI_SKIP_PATH_SEGMENTS = ["/health", "/docs", "/openapi", "/redoc"]


# ---------------------------------------------------------------------------
# Compiled regex patterns for HTML/TSX parsing
# ---------------------------------------------------------------------------

HTML_TITLE_PATTERN = re.compile(r"<title>([^<]+)</title>", re.IGNORECASE)
HREF_PATTERN = re.compile(r'href=["\']([^"\']+)["\']')
METADATA_TITLE_PATTERN = re.compile(r'title:\s*["\']([^"\']+)["\']')
PAGE_HEADER_TITLE_PATTERN = re.compile(r'<PageHeader[^>]*title=["\']([^"\']+)["\']')
TAB_VALUE_TYPE_PATTERN = re.compile(r"type\s+TabValue\s*=\s*([^;]+);")
QUOTED_STRING_PATTERN = re.compile(r'["\']([^"\']+)["\']')
TABS_TRIGGER_PATTERN = re.compile(r'<TabsTrigger[^>]*value=["\']([^"\']+)["\']')


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def extract_openapi_endpoints(
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
    endpoints: list[dict[str, Any]] = []
    paths = openapi.get("paths", {})

    for path, methods in paths.items():
        if any(x in path for x in OPENAPI_SKIP_PATH_SEGMENTS):
            continue
        for method, details in methods.items():
            if method.upper() not in OPENAPI_ACCEPTED_METHODS:
                continue
            entry: dict[str, Any] = {
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


def should_visit_link(link: str, visited: set[str]) -> bool:
    """Check if a link should be visited during frontend crawl.

    Filters out external links, static assets, API calls, Next.js internals,
    and already visited links.

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
    clean_path = link.split("?", maxsplit=1)[0].split("#")[0]
    return clean_path not in visited


def extract_page_metadata(response_text: str) -> dict[str, str | None]:
    """Extract page metadata from HTML response.

    Looks for page title in <title> tag.

    Args:
        response_text: The HTML response body

    Returns:
        Dict with 'title' key and extracted title or None
    """
    title_match = HTML_TITLE_PATTERN.search(response_text)
    title = title_match.group(1).strip() if title_match else None
    return {"title": title}


def queue_internal_links(
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

    for link in HREF_PATTERN.findall(response_text):
        if should_visit_link(link, visited):
            clean_path = link.split("?")[0].split("#")[0]
            to_visit.append((clean_path, current_depth + 1))


def convert_nextjs_segment(part: str) -> str:
    """Convert a Next.js route segment to template notation.

    Converts dynamic segments like [id] to {id}.

    Args:
        part: A single route path segment

    Returns:
        The converted segment
    """
    if part.startswith("[") and part.endswith("]"):
        param_name = part[1:-1]
        return f"{{{param_name}}}"
    return part


def build_route_from_parts(route_parts: list[str]) -> str:
    """Build a URL route string from Next.js directory parts.

    Args:
        route_parts: List of path segments (excluding page.tsx)

    Returns:
        Route string starting with /
    """
    if not route_parts:
        return "/"
    converted = [convert_nextjs_segment(p) for p in route_parts]
    return "/" + "/".join(converted)


def extract_page_title(page_file: Path) -> str | None:
    """Extract page title from a Next.js page file.

    Looks for metadata.title export, PageHeader title prop, or derives
    from directory name.

    Args:
        page_file: Path to page.tsx file

    Returns:
        Title string or None
    """
    try:
        content = page_file.read_text()
        metadata_match = METADATA_TITLE_PATTERN.search(content)
        if metadata_match:
            return metadata_match.group(1)
        header_match = PAGE_HEADER_TITLE_PATTERN.search(content)
        if header_match:
            return header_match.group(1)
        parent_dir = page_file.parent.name
        if parent_dir != "app":
            return parent_dir.replace("-", " ").replace("_", " ").title()
        return "Home"
    except Exception:
        return None


def extract_tab_values(page_file: Path) -> list[str]:
    """Extract tab values from a Next.js page that uses useSearchParams.

    Looks for TabValue type definitions and TabsTrigger component values.

    Args:
        page_file: Path to page.tsx file

    Returns:
        List of tab value strings
    """
    try:
        content = page_file.read_text()
        if "useSearchParams" not in content and "searchParams" not in content:
            return []
        tabvalue_match = TAB_VALUE_TYPE_PATTERN.search(content)
        if tabvalue_match:
            return QUOTED_STRING_PATTERN.findall(tabvalue_match.group(1))
        trigger_matches = TABS_TRIGGER_PATTERN.findall(content)
        if trigger_matches:
            return list(set(trigger_matches))
    except Exception:
        pass
    return []
