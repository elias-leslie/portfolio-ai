"""API endpoint capability scanner."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..logging_config import get_logger
from .capability_utils import _to_json_string
from .config_loader import categorize_by_name, load_capabilities_config

if TYPE_CHECKING:
    from ..storage.connection import ConnectionManager

logger = get_logger(__name__)


class APIScanner:
    """Scans FastAPI routes to auto-discover API endpoints.

    Detects endpoint metadata including paths, methods, dependencies.
    """

    def __init__(
        self,
        connection_mgr: ConnectionManager,
        config: dict[str, Any] | None = None,
    ) -> None:
        """Initialize API scanner.

        Args:
            connection_mgr: ConnectionManager instance for database access
            config: Optional config dict (loads from file if not provided)
        """
        self.conn_mgr = connection_mgr
        self.config = config or load_capabilities_config()
        self.api_config = self.config["scan_config"]["targets"]["api"]

    def scan(self) -> list[dict[str, Any]]:
        """Scan FastAPI route files and return endpoint metadata.

        Returns:
            List of dicts with endpoint metadata:
                - endpoint_path: str
                - http_method: str
                - category: str
                - route_file: str
                - function_name: str
                - depends_on_tables: list[str]
                - avg_response_time_ms: int | None
                - p95_response_time_ms: int | None
                - p99_response_time_ms: int | None
                - error_rate_pct: float | None
                - last_7d_request_count: int | None
        """
        if not self.api_config["enabled"]:
            logger.info("api_scan_disabled")
            return []

        logger.info("scanning_api_endpoints")

        capabilities = []

        # Find all API files (try both api/ and routes/ directories)
        api_dirs = [
            Path(__file__).parent.parent / "api",
            Path(__file__).parent.parent / "routes",
        ]

        route_files = []
        for api_dir in api_dirs:
            if api_dir.exists():
                route_files.extend([f for f in api_dir.glob("*.py") if not f.name.startswith("_")])

        if not route_files:
            logger.warning("no_api_files_found")
            return []

        for route_file in route_files:
            if route_file.name.startswith("_"):
                continue

            try:
                endpoints = self._scan_route_file(route_file)
                capabilities.extend(endpoints)
            except Exception as e:
                logger.error(
                    "route_file_scan_failed",
                    file=route_file.name,
                    error=str(e),
                )

        logger.info(
            "api_scan_complete",
            endpoints_scanned=len(capabilities),
        )

        return capabilities

    def _scan_route_file(self, route_file: Path) -> list[dict[str, Any]]:
        """Scan a single route file for API endpoints.

        Args:
            route_file: Path to route file

        Returns:
            List of endpoint dicts
        """
        content = route_file.read_text()
        endpoints = []

        # Regex pattern to find route decorators
        # Matches: @router.get("/path"), @router.post("/path/{id}"), etc.
        route_pattern = r'@router\.(get|post|put|delete|patch)\(["\']([^"\']+)["\']\)'
        matches = re.findall(route_pattern, content)

        for method, path in matches:
            # Skip health/docs/admin endpoints unless explicitly tracking them
            if any(x in path for x in ["/health", "/docs", "/openapi", "/redoc"]):
                continue

            # Detect function name (next line after decorator)
            function_name = self._extract_function_name(content, method, path)

            # Detect table dependencies (basic regex scan)
            depends_on_tables = self._detect_table_dependencies(content, function_name)

            # Categorize endpoint
            category = categorize_by_name(path)

            # Calculate health status
            health_status = self._calculate_api_health_status(
                depends_on_tables=depends_on_tables,
            )

            endpoints.append(
                {
                    "endpoint_path": path,
                    "http_method": method.upper(),
                    "category": category,
                    "route_file": str(route_file.name),
                    "function_name": function_name or "unknown",
                    "depends_on_tables": depends_on_tables,
                    "health_status": health_status,
                    # Performance metrics - NULL for Phase 1 (no middleware yet)
                    "avg_response_time_ms": None,
                    "p95_response_time_ms": None,
                    "p99_response_time_ms": None,
                    "error_rate_pct": None,
                    "last_7d_request_count": None,
                }
            )

        return endpoints

    def _extract_function_name(self, content: str, method: str, path: str) -> str | None:
        """Extract function name for a route decorator.

        Args:
            content: File content
            method: HTTP method
            path: Endpoint path

        Returns:
            Function name or None
        """
        try:
            # Find decorator line
            decorator_pattern = rf'@router\.{method}\(["\']' + re.escape(path) + r'["\']\)'
            decorator_match = re.search(decorator_pattern, content)

            if not decorator_match:
                return None

            # Find function definition on next lines
            remaining_content = content[decorator_match.end() :]
            func_pattern = r"^\s*(?:async\s+)?def\s+([a-z_][a-z0-9_]*)"
            func_match = re.search(func_pattern, remaining_content, re.MULTILINE)

            if func_match:
                return func_match.group(1)

        except Exception as e:
            logger.debug("failed_to_extract_function_name", error=str(e))

        return None

    def _calculate_api_health_status(
        self,
        depends_on_tables: list[str],
    ) -> str:
        """Calculate health status for API endpoint.

        Args:
            depends_on_tables: Tables this endpoint depends on

        Returns:
            Health status: "active", "orphaned", "legacy", or "suspect"

        API health logic:
        - orphaned: No table dependencies (isolated endpoint)
        - legacy: Not implemented yet (requires table health cross-reference)
        - suspect: Not implemented yet (requires table health cross-reference)
        - active: default

        NOTE: Full implementation requires querying db_capabilities to check
        if depends_on_tables are orphaned/legacy. This is Phase 2 work.
        """
        # Orphaned: No dependencies on any tables
        if not depends_on_tables:
            return "orphaned"

        # Default: Active (full logic requires cross-referencing db_capabilities)
        return "active"

    def _detect_table_dependencies(self, content: str, function_name: str | None) -> list[str]:
        """Detect which tables an endpoint depends on.

        Uses basic regex to find SELECT ... FROM statements.

        Args:
            content: File content
            function_name: Function name to scope search

        Returns:
            List of table names this endpoint reads from
        """
        try:
            tables = set()

            # Patterns for SQL queries
            patterns = [
                r"FROM\s+([a-z_][a-z0-9_]*)",
                r"JOIN\s+([a-z_][a-z0-9_]*)",
            ]

            for pattern in patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                tables.update(matches)

            # Filter out SQL keywords that might be matched
            sql_keywords = {"select", "where", "order", "group", "limit", "offset"}
            tables = {t for t in tables if t.lower() not in sql_keywords}

            return sorted(tables)

        except Exception as e:
            logger.debug("failed_to_detect_table_dependencies", error=str(e))
            return []

    def save_capabilities(self, capabilities: list[dict[str, Any]]) -> int:
        """Save scanned API capabilities to api_capabilities table.

        Uses UPSERT logic (INSERT ... ON CONFLICT DO UPDATE) to update existing records.

        Args:
            capabilities: List of capability dicts from scan()

        Returns:
            Number of rows inserted/updated
        """
        if not capabilities:
            logger.info("no_api_capabilities_to_save")
            return 0

        logger.info("saving_api_capabilities", count=len(capabilities))

        with self.conn_mgr.connection() as conn:
            for cap in capabilities:
                # Convert lists to JSON strings for JSONB columns
                depends_on_tables_json = _to_json_string(cap["depends_on_tables"])

                # UPSERT query
                conn.execute(
                    """
                    INSERT INTO api_capabilities (
                        endpoint_path, http_method, category, route_file, function_name,
                        depends_on_tables, health_status,
                        avg_response_time_ms, p95_response_time_ms, p99_response_time_ms,
                        error_rate_pct, last_7d_request_count,
                        last_scanned_at, created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (endpoint_path, http_method) DO UPDATE SET
                        category = EXCLUDED.category,
                        route_file = EXCLUDED.route_file,
                        function_name = EXCLUDED.function_name,
                        depends_on_tables = EXCLUDED.depends_on_tables,
                        health_status = EXCLUDED.health_status,
                        avg_response_time_ms = EXCLUDED.avg_response_time_ms,
                        p95_response_time_ms = EXCLUDED.p95_response_time_ms,
                        p99_response_time_ms = EXCLUDED.p99_response_time_ms,
                        error_rate_pct = EXCLUDED.error_rate_pct,
                        last_7d_request_count = EXCLUDED.last_7d_request_count,
                        last_scanned_at = EXCLUDED.last_scanned_at,
                        updated_at = EXCLUDED.updated_at
                    """,
                    [
                        cap["endpoint_path"],
                        cap["http_method"],
                        cap["category"],
                        cap["route_file"],
                        cap["function_name"],
                        depends_on_tables_json,
                        cap["health_status"],
                        cap["avg_response_time_ms"],
                        cap["p95_response_time_ms"],
                        cap["p99_response_time_ms"],
                        cap["error_rate_pct"],
                        cap["last_7d_request_count"],
                        datetime.now(UTC),  # last_scanned_at
                        datetime.now(UTC),  # created_at
                        datetime.now(UTC),  # updated_at
                    ],
                )
                conn.commit()

        logger.info("api_capabilities_saved", count=len(capabilities))
        return len(capabilities)
