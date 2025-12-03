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

            # Detect frontend usage (is this endpoint called from frontend?)
            frontend_callers = self._detect_frontend_usage(path)

            # Categorize endpoint
            category = categorize_by_name(path)

            # Calculate health status
            health_status = self._calculate_api_health_status(
                depends_on_tables=depends_on_tables,
                frontend_callers=frontend_callers,
            )

            endpoints.append(
                {
                    "endpoint_path": path,
                    "http_method": method.upper(),
                    "category": category,
                    "route_file": str(route_file.name),
                    "function_name": function_name or "unknown",
                    "depends_on_tables": depends_on_tables,
                    "frontend_callers": frontend_callers,  # NEW: frontend files calling this endpoint
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
        frontend_callers: list[str] | None = None,
    ) -> str:
        """Calculate health status for API endpoint.

        Args:
            depends_on_tables: Tables this endpoint depends on
            frontend_callers: Frontend files that call this endpoint

        Returns:
            Health status: "active", "orphaned", "legacy", or "suspect"

        API health logic:
        - active: Has frontend callers OR has table dependencies
        - orphaned: No table dependencies AND no frontend callers (isolated endpoint)
        - legacy: Not implemented yet (requires table health cross-reference)
        - suspect: Not implemented yet (requires table health cross-reference)

        NOTE: Full implementation requires querying db_capabilities to check
        if depends_on_tables are orphaned/legacy. This is Phase 2 work.
        """
        # If frontend calls this endpoint, it's active (even without table deps)
        if frontend_callers:
            return "active"

        # Orphaned: No dependencies on any tables AND no frontend callers
        if not depends_on_tables:
            return "orphaned"

        # Default: Active (full logic requires cross-referencing db_capabilities)
        return "active"

    def _detect_frontend_usage(self, endpoint_path: str) -> list[str]:
        """Detect frontend files that call this API endpoint.

        Searches for API call patterns in frontend code:
        - fetch('/api/path')
        - axios.get('/api/path')
        - api.get('/path')
        - useSWR('/api/path')

        Args:
            endpoint_path: API endpoint path (e.g., "/watchlist/items")

        Returns:
            List of frontend file paths that call this endpoint
        """
        try:
            callers = set()

            # Build search patterns
            # Remove leading slash for more flexible matching
            path_no_slash = endpoint_path.lstrip("/")

            # Handle path parameters like {id} or :id
            # Convert /items/{id} to regex pattern /items/[^/'"]+
            path_pattern = re.sub(r"\{[^}]+\}", r"[^/'\"]+", path_no_slash)
            path_pattern = re.sub(r":[a-zA-Z_]+", r"[^/'\"]+", path_pattern)

            patterns = [
                # Direct API calls
                rf"['\"`]/api/{path_pattern}['\"`]",
                rf"['\"`]/{path_pattern}['\"`]",
                # Template literals with backticks
                rf"`/api/{path_pattern}`",
                rf"`/{path_pattern}`",
                # API client patterns
                rf"api\.(get|post|put|delete|patch)\s*\(\s*['\"`]/?{path_pattern}",
            ]

            # Search in frontend directory
            frontend_dir = Path(__file__).parent.parent.parent.parent / "frontend"
            if not frontend_dir.exists():
                return []

            # Search .ts, .tsx, .js, .jsx files
            for pattern_glob in ["**/*.ts", "**/*.tsx", "**/*.js", "**/*.jsx"]:
                for frontend_file in frontend_dir.glob(pattern_glob):
                    # Skip node_modules and build directories
                    if "node_modules" in str(frontend_file) or ".next" in str(frontend_file):
                        continue

                    try:
                        content = frontend_file.read_text()
                        for pattern in patterns:
                            if re.search(pattern, content, re.IGNORECASE):
                                # Get relative path from frontend/
                                rel_path = str(frontend_file.relative_to(frontend_dir))
                                callers.add(rel_path)
                                break
                    except Exception:
                        continue

            return sorted(callers)

        except Exception as e:
            logger.debug("failed_to_detect_frontend_usage", endpoint=endpoint_path, error=str(e))
            return []

    def _detect_table_dependencies(self, content: str, function_name: str | None) -> list[str]:
        """Detect which tables an endpoint depends on.

        Uses regex to find SELECT ... FROM / JOIN statements in SQL strings only.
        Filters out Python imports which share similar syntax (from X import).

        Args:
            content: File content
            function_name: Function name to scope search

        Returns:
            List of table names this endpoint reads from
        """
        try:
            tables = set()

            # Extract only SQL string content (inside quotes)
            # This avoids matching Python import statements like "from typing import"
            sql_string_patterns = [
                r'"""([^"]*?)"""',  # Triple-quoted strings
                r"'''([^']*?)'''",  # Triple single-quoted strings
                r'"([^"\n]*?)"',  # Double-quoted strings (single line)
                r"'([^'\n]*?)'",  # Single-quoted strings (single line)
            ]

            sql_content = ""
            for pattern in sql_string_patterns:
                matches = re.findall(pattern, content, re.DOTALL)
                sql_content += " ".join(matches) + " "

            # Now search for table references ONLY in the extracted SQL strings
            table_patterns = [
                r"FROM\s+([a-z_][a-z0-9_]*)",
                r"JOIN\s+([a-z_][a-z0-9_]*)",
                r"INTO\s+([a-z_][a-z0-9_]*)",
                r"UPDATE\s+([a-z_][a-z0-9_]*)",
            ]

            for pattern in table_patterns:
                matches = re.findall(pattern, sql_content, re.IGNORECASE)
                tables.update(matches)

            # Filter out SQL keywords and common Python module names
            exclude_names = {
                # SQL keywords
                "select",
                "where",
                "order",
                "group",
                "limit",
                "offset",
                "values",
                # Python modules that might slip through
                "__future__",
                "typing",
                "datetime",
                "pydantic",
                "fastapi",
                "app",
                "decimal",
                "json",
                "re",
                "os",
                "sys",
                "pathlib",
                "logging",
            }
            tables = {t for t in tables if t.lower() not in exclude_names}

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
