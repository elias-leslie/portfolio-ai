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
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from ..logging_config import get_logger
from ..storage.connection import get_connection_manager

logger = get_logger(__name__)

# Configuration
BROWSER_SCRIPTS_DIR = Path("/home/kasadis/portfolio-ai/.claude/skills/browser-automation/scripts")
CONSOLE_SCRIPT = BROWSER_SCRIPTS_DIR / "console.js"
CONSOLE_CAPTURE_TIMEOUT = 15  # seconds
HTTP_TIMEOUT = 10  # seconds

# Known ports and hosts
FRONTEND_PORT = 3000
BACKEND_PORT = 8000
FRONTEND_HOST = "192.168.8.233"  # Network IP for SSR routing
BACKEND_HOST = "localhost"


class SitemapService:
    """Discovers and monitors sitemap entries."""

    def __init__(self) -> None:
        self.conn_mgr = get_connection_manager()

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
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                response = await client.get(f"http://{BACKEND_HOST}:{BACKEND_PORT}/openapi.json")
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
                            "port": BACKEND_PORT,
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

        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
            while to_visit:
                path, depth = to_visit.pop(0)

                if path in visited or depth > max_depth:
                    continue
                visited.add(path)

                try:
                    url = f"http://{FRONTEND_HOST}:{FRONTEND_PORT}{path}"
                    response = await client.get(url)

                    if response.status_code == 200:
                        # Get page title from HTML
                        title = None
                        title_match = re.search(r"<title>([^<]+)</title>", response.text, re.IGNORECASE)
                        if title_match:
                            title = title_match.group(1).strip()

                        discovered.append({
                            "port": FRONTEND_PORT,
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
                    """, [BACKEND_PORT, endpoint_path, http_method, "api_endpoint", "api_scanner", function_name or category])
                    imported += 1
                except Exception as e:
                    logger.debug("sitemap_import_row_failed", path=endpoint_path, error=str(e))

            conn.commit()

        logger.info("sitemap_import_api_capabilities_complete", imported=imported)
        return imported

    async def run_discovery(self) -> dict[str, Any]:
        """Run full discovery: OpenAPI + frontend crawler + api_capabilities import.

        Returns:
            Summary of discovery results
        """
        logger.info("sitemap_full_discovery_start")

        # Run discoveries in parallel
        backend_task = asyncio.create_task(self.discover_backend_endpoints())
        frontend_task = asyncio.create_task(self.discover_frontend_pages())

        backend_entries = await backend_task
        frontend_entries = await frontend_task

        # Import from api_capabilities (sync)
        api_imported = self.import_from_api_capabilities()

        # Save discovered entries
        all_entries = backend_entries + frontend_entries
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
            "backend_discovered": len(backend_entries),
            "frontend_discovered": len(frontend_entries),
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
        entry_type = entry["entry_type"]

        # Build URL
        host = FRONTEND_HOST if port == FRONTEND_PORT else BACKEND_HOST
        url = f"http://{host}:{port}{path}"

        console_errors = 0
        console_warnings = 0
        http_status = None
        response_time_ms = None
        error_details: dict[str, Any] = {}
        last_error_message = None

        try:
            if entry_type == "frontend_page":
                # Use console.js script for frontend pages
                result = await self._capture_console(url)
                console_errors = result.get("errorCount", 0)
                console_warnings = result.get("warningCount", 0)
                http_status = result.get("httpStatus", 200)
                response_time_ms = result.get("responseTimeMs")

                if result.get("errors"):
                    error_details["errors"] = result["errors"][:10]  # Limit to 10
                    last_error_message = result["errors"][0].get("text", "")[:500]
                if result.get("warnings"):
                    error_details["warnings"] = result["warnings"][:5]

            else:
                # Simple HTTP fetch for API endpoints
                async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                    request_start = datetime.now(UTC)
                    response = await client.request(method, url)
                    response_time_ms = int((datetime.now(UTC) - request_start).total_seconds() * 1000)
                    http_status = response.status_code

                    if response.status_code >= 400:
                        console_errors = 1
                        last_error_message = f"HTTP {response.status_code}"

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

    async def _capture_console(self, url: str) -> dict[str, Any]:
        """Capture console errors/warnings using console.js script.

        Args:
            url: URL to check

        Returns:
            Dict with errorCount, warningCount, errors, warnings, httpStatus
        """
        if not CONSOLE_SCRIPT.exists():
            return {"errorCount": 0, "warningCount": 0, "httpStatus": None}

        try:
            proc = await asyncio.create_subprocess_exec(
                "node",
                str(CONSOLE_SCRIPT),
                url,
                str(CONSOLE_CAPTURE_TIMEOUT * 1000),  # ms
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, _ = await asyncio.wait_for(
                proc.communicate(),
                timeout=CONSOLE_CAPTURE_TIMEOUT + 5,
            )

            output = stdout.decode()

            # Parse JSON result from script output
            for line in output.split("\n"):
                if line.startswith("{") and "errorCount" in line:
                    return json.loads(line)

            return {"errorCount": 0, "warningCount": 0, "httpStatus": 200}

        except Exception as e:
            logger.debug("sitemap_console_capture_failed", url=url, error=str(e))
            return {"errorCount": 1, "warningCount": 0, "errors": [{"text": str(e)}]}

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
