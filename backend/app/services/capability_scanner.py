"""System capability scanner for auto-discovery of data sources.

This module scans the system to discover:
- Database tables (row counts, columns, completeness, freshness)
- Celery scheduled tasks (schedules, success rates, dependencies)
- API endpoints (paths, methods, dependencies)

Stores results in capability registry tables for monitoring and AI analysis.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy import create_engine, inspect

from ..constants import DATABASE_URL
from ..logging_config import get_logger
from .config_loader import (
    categorize_by_name,
    get_expected_freshness,
    get_freshness_thresholds,
    load_capabilities_config,
)

if TYPE_CHECKING:
    from ..storage.connection import ConnectionManager

logger = get_logger(__name__)


class DatabaseScanner:
    """Scans database tables to auto-discover capabilities.

    Detects table metadata including row counts, columns, field completeness,
    date ranges, and calculates freshness status based on config rules.
    """

    def __init__(
        self,
        connection_mgr: ConnectionManager,
        config: dict[str, Any] | None = None,
    ) -> None:
        """Initialize database scanner.

        Args:
            connection_mgr: ConnectionManager instance for database access
            config: Optional config dict (loads from file if not provided)
        """
        self.conn_mgr = connection_mgr
        self.config = config or load_capabilities_config()
        self.db_config = self.config["scan_config"]["targets"]["database"]

    def scan(self) -> list[dict[str, Any]]:
        """Scan all database tables and return capability metadata.

        Returns:
            List of dicts with table metadata:
                - table_name: str
                - category: str
                - row_count: int
                - total_columns: int
                - columns: list[str]
                - columns_with_data: list[str]
                - columns_mostly_null: list[str]
                - completeness_pct: int
                - date_range_start: date | None
                - date_range_end: date | None
                - expected_freshness: str
                - days_since_update: int | None
                - freshness_status: str
        """
        if not self.db_config["enabled"]:
            logger.info("database_scan_disabled")
            return []

        logger.info("scanning_database_tables")

        # Create SQLAlchemy engine for table introspection
        engine = create_engine(DATABASE_URL)
        inspector = inspect(engine)

        capabilities = []

        with engine.connect() as raw_conn:
            for table_name in inspector.get_table_names():
                try:
                    capability = self._scan_single_table(table_name, raw_conn, inspector)
                    capabilities.append(capability)
                except Exception as e:
                    logger.error(
                        "table_scan_failed",
                        table=table_name,
                        error=str(e),
                    )

        logger.info(
            "database_scan_complete",
            tables_scanned=len(capabilities),
        )

        return capabilities

    def _scan_single_table(
        self,
        table_name: str,
        conn: Any,
        inspector: Any,
    ) -> dict[str, Any]:
        """Scan a single table for metadata.

        Args:
            table_name: Name of table to scan
            conn: SQLAlchemy connection
            inspector: SQLAlchemy inspector

        Returns:
            Dict with table metadata
        """
        # Get row count
        # Note: table_name is from database introspection, not user input
        result = conn.execute(f"SELECT COUNT(*) FROM {table_name}")
        row_count = result.scalar()

        # Get columns
        columns = inspector.get_columns(table_name)
        column_names = [col["name"] for col in columns]
        total_columns = len(column_names)

        # Detect columns with data and mostly null columns
        columns_with_data = []
        columns_mostly_null = []

        if self.db_config["track_field_completeness"] and row_count > 0:
            null_threshold = self.db_config["null_threshold_pct"]

            for col_name in column_names:
                try:
                    # Count non-NULL values
                    # Note: col_name from introspection, not user input
                    result = conn.execute(f"SELECT COUNT({col_name}) as cnt FROM {table_name}")
                    non_null_count = result.scalar()

                    if non_null_count > 0:
                        columns_with_data.append(col_name)

                    # Calculate NULL percentage
                    null_pct = ((row_count - non_null_count) / row_count) * 100

                    if null_pct > null_threshold:
                        columns_mostly_null.append(col_name)

                except Exception:
                    # Skip columns that cause errors (e.g., incompatible types)
                    continue

        # Calculate completeness percentage
        completeness_pct = (
            int((len(columns_with_data) / total_columns) * 100) if total_columns > 0 else 0
        )

        # Detect date range
        date_range_start = None
        date_range_end = None

        if self.db_config["track_freshness"]:
            date_range_start, date_range_end = self._detect_date_range(
                table_name, conn, column_names
            )

        # Get expected freshness and calculate status
        expected_freshness = get_expected_freshness(table_name)
        days_since_update = None
        freshness_status = "unknown"

        if date_range_end:
            days_since_update = (datetime.now(UTC).date() - date_range_end).days
            freshness_status = self._calculate_freshness_status(
                expected_freshness,
                days_since_update,
            )

        # Categorize table
        category = categorize_by_name(table_name)

        return {
            "table_name": table_name,
            "category": category,
            "row_count": row_count,
            "total_columns": total_columns,
            "columns": column_names,
            "columns_with_data": columns_with_data,
            "columns_mostly_null": columns_mostly_null,
            "completeness_pct": completeness_pct,
            "date_range_start": date_range_start,
            "date_range_end": date_range_end,
            "expected_freshness": expected_freshness,
            "days_since_update": days_since_update,
            "freshness_status": freshness_status,
        }

    def _detect_date_range(
        self,
        table_name: str,
        conn: Any,
        column_names: list[str],
    ) -> tuple[Any | None, Any | None]:
        """Detect date range for a table by finding MIN/MAX of timestamp columns.

        Args:
            table_name: Name of table
            conn: SQLAlchemy connection
            column_names: List of column names in table

        Returns:
            Tuple of (min_date, max_date) or (None, None) if no date columns found
        """
        # Try common timestamp column names in order of preference
        date_columns = ["created_at", "updated_at", "as_of_date", "date", "timestamp"]

        for col_name in date_columns:
            if col_name in column_names:
                try:
                    # Note: col_name validated from column_names list, not user input
                    result = conn.execute(
                        f"SELECT MIN({col_name}), MAX({col_name}) FROM {table_name} WHERE {col_name} IS NOT NULL"
                    )
                    min_date, max_date = result.first()

                    if min_date and max_date:
                        # Convert to date if timestamp
                        if hasattr(min_date, "date"):
                            min_date = min_date.date()
                        if hasattr(max_date, "date"):
                            max_date = max_date.date()

                        return min_date, max_date

                except Exception:
                    # Skip if column causes errors
                    continue

        return None, None

    def _calculate_freshness_status(
        self,
        expected_freshness: str,
        days_since_update: int,
    ) -> str:
        """Calculate freshness status based on expected freshness and days since update.

        Args:
            expected_freshness: Expected freshness string (e.g., "daily", "hourly")
            days_since_update: Days since last update

        Returns:
            Freshness status: "current", "acceptable", "stale", or "critical"
        """
        thresholds = get_freshness_thresholds(expected_freshness)

        if days_since_update <= thresholds["current"]:
            return "current"
        if days_since_update <= thresholds["acceptable"]:
            return "acceptable"
        if days_since_update <= thresholds["stale"]:
            return "stale"
        return "critical"

    def save_capabilities(self, capabilities: list[dict[str, Any]]) -> int:
        """Save scanned capabilities to db_capabilities table.

        Uses UPSERT logic (INSERT ... ON CONFLICT DO UPDATE) to update existing records.

        Args:
            capabilities: List of capability dicts from scan()

        Returns:
            Number of rows inserted/updated
        """
        if not capabilities:
            logger.info("no_db_capabilities_to_save")
            return 0

        logger.info("saving_db_capabilities", count=len(capabilities))

        with self.conn_mgr.connection() as conn:
            for cap in capabilities:
                # Convert lists to JSON strings for JSONB columns
                columns_json = _to_json_string(cap["columns"])
                columns_with_data_json = _to_json_string(cap["columns_with_data"])
                columns_mostly_null_json = _to_json_string(cap["columns_mostly_null"])

                # UPSERT query
                conn.execute(
                    """
                    INSERT INTO db_capabilities (
                        table_name, category, row_count, total_columns,
                        columns, columns_with_data, columns_mostly_null,
                        completeness_pct, date_range_start, date_range_end,
                        expected_freshness, days_since_update, freshness_status,
                        last_scanned_at, created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (table_name) DO UPDATE SET
                        category = EXCLUDED.category,
                        row_count = EXCLUDED.row_count,
                        total_columns = EXCLUDED.total_columns,
                        columns = EXCLUDED.columns,
                        columns_with_data = EXCLUDED.columns_with_data,
                        columns_mostly_null = EXCLUDED.columns_mostly_null,
                        completeness_pct = EXCLUDED.completeness_pct,
                        date_range_start = EXCLUDED.date_range_start,
                        date_range_end = EXCLUDED.date_range_end,
                        expected_freshness = EXCLUDED.expected_freshness,
                        days_since_update = EXCLUDED.days_since_update,
                        freshness_status = EXCLUDED.freshness_status,
                        last_scanned_at = EXCLUDED.last_scanned_at,
                        updated_at = EXCLUDED.updated_at
                    """,
                    [
                        cap["table_name"],
                        cap["category"],
                        cap["row_count"],
                        cap["total_columns"],
                        columns_json,
                        columns_with_data_json,
                        columns_mostly_null_json,
                        cap["completeness_pct"],
                        cap["date_range_start"],
                        cap["date_range_end"],
                        cap["expected_freshness"],
                        cap["days_since_update"],
                        cap["freshness_status"],
                        datetime.now(UTC),  # last_scanned_at
                        datetime.now(UTC),  # created_at
                        datetime.now(UTC),  # updated_at
                    ],
                )
                conn.commit()

        logger.info("db_capabilities_saved", count=len(capabilities))
        return len(capabilities)


class CeleryScanner:
    """Scans Celery beat schedule to auto-discover scheduled tasks.

    Detects task metadata including schedules, success rates, dependencies.
    """

    def __init__(
        self,
        connection_mgr: ConnectionManager,
        config: dict[str, Any] | None = None,
    ) -> None:
        """Initialize Celery scanner.

        Args:
            connection_mgr: ConnectionManager instance for database access
            config: Optional config dict (loads from file if not provided)
        """
        self.conn_mgr = connection_mgr
        self.config = config or load_capabilities_config()
        self.celery_config = self.config["scan_config"]["targets"]["celery"]

    def scan(self) -> list[dict[str, Any]]:
        """Scan Celery beat schedule and return task metadata.

        Returns:
            List of dicts with task metadata:
                - task_name: str
                - category: str
                - task_path: str
                - function_name: str
                - schedule_description: str
                - schedule_crontab: str | None
                - schedule_interval_seconds: int | None
                - last_run_at: datetime | None
                - next_run_at: datetime | None
                - success_count_7d: int
                - failure_count_7d: int
                - success_rate_pct: int | None
                - avg_duration_ms: int | None
                - max_duration_ms: int | None
                - populates_tables: list[str]
                - depends_on_tasks: list[str]
        """
        if not self.celery_config["enabled"]:
            logger.info("celery_scan_disabled")
            return []

        logger.info("scanning_celery_tasks")

        # Import celery_app to access beat_schedule
        from ..celery_app import celery_app  # noqa: PLC0415

        capabilities = []
        beat_schedule = celery_app.conf.beat_schedule

        for task_name, task_config in beat_schedule.items():
            try:
                capability = self._scan_single_task(task_name, task_config)
                capabilities.append(capability)
            except Exception as e:
                logger.error(
                    "task_scan_failed",
                    task=task_name,
                    error=str(e),
                )

        logger.info(
            "celery_scan_complete",
            tasks_scanned=len(capabilities),
        )

        return capabilities

    def _scan_single_task(
        self,
        task_name: str,
        task_config: dict[str, Any],
    ) -> dict[str, Any]:
        """Scan a single Celery task for metadata.

        Args:
            task_name: Name of task (beat_schedule key)
            task_config: Task configuration dict from beat_schedule

        Returns:
            Dict with task metadata
        """
        task_path = task_config["task"]
        function_name = task_path.split(".")[-1] if "." in task_path else task_path

        # Parse schedule
        schedule_obj = task_config["schedule"]
        schedule_description, schedule_crontab, schedule_interval_seconds = self._parse_schedule(
            schedule_obj
        )

        # Get task execution metadata (if celery_taskmeta table available)
        (
            last_run_at,
            next_run_at,
            success_count,
            failure_count,
            success_rate,
            avg_duration,
            max_duration,
        ) = self._get_task_metadata(task_path)

        # Detect populated tables (basic regex scan of task file)
        populates_tables = self._detect_populates_tables(task_path)

        # Categorize task
        category = categorize_by_name(task_name)

        return {
            "task_name": task_name,
            "category": category,
            "task_path": task_path,
            "function_name": function_name,
            "schedule_description": schedule_description,
            "schedule_crontab": schedule_crontab,
            "schedule_interval_seconds": schedule_interval_seconds,
            "last_run_at": last_run_at,
            "next_run_at": next_run_at,
            "success_count_7d": success_count,
            "failure_count_7d": failure_count,
            "success_rate_pct": success_rate,
            "avg_duration_ms": avg_duration,
            "max_duration_ms": max_duration,
            "populates_tables": populates_tables,
            "depends_on_tasks": [],  # TODO: Implement dependency detection
        }

    def _parse_schedule(
        self,
        schedule_obj: Any,
    ) -> tuple[str, str | None, int | None]:
        """Parse Celery schedule object into human-readable format.

        Args:
            schedule_obj: Celery schedule object (crontab or interval)

        Returns:
            Tuple of (description, crontab_string, interval_seconds)
        """
        from celery.schedules import crontab  # type: ignore[import-untyped]  # noqa: PLC0415

        schedule_str = str(schedule_obj)

        # Try to parse crontab
        if isinstance(schedule_obj, crontab):
            # Human-readable description
            hour = schedule_obj._orig_hour if hasattr(schedule_obj, "_orig_hour") else "*"
            minute = schedule_obj._orig_minute if hasattr(schedule_obj, "_orig_minute") else "*"

            if hour != "*" and minute != "*":
                description = f"Daily at {hour:02d}:{minute:02d} UTC"
                crontab_str = f"{minute} {hour} * * *"
            else:
                description = f"Crontab: {schedule_str}"
                crontab_str = schedule_str

            # Estimate interval in seconds for daily tasks
            interval_seconds = 86400 if hour != "*" else None

        elif isinstance(schedule_obj, (int, float)):
            # Interval in seconds
            interval_seconds = int(schedule_obj)

            if interval_seconds < 60:
                description = f"Every {interval_seconds} seconds"
            elif interval_seconds < 3600:
                description = f"Every {interval_seconds // 60} minutes"
            elif interval_seconds < 86400:
                description = f"Every {interval_seconds // 3600} hours"
            else:
                description = f"Every {interval_seconds // 86400} days"

            crontab_str = None

        else:
            # Unknown schedule type
            description = f"Schedule: {schedule_str}"
            crontab_str = None
            interval_seconds = None

        return description, crontab_str, interval_seconds

    def _get_task_metadata(
        self,
        task_path: str,
    ) -> tuple[Any | None, Any | None, int, int, int | None, int | None, int | None]:
        """Get task execution metadata from celery_taskmeta table.

        Args:
            task_path: Task import path

        Returns:
            Tuple of (last_run_at, next_run_at, success_count_7d, failure_count_7d,
                     success_rate_pct, avg_duration_ms, max_duration_ms)
        """
        if not self.celery_config["track_success_rate"]:
            return None, None, 0, 0, None, None, None

        try:
            with self.conn_mgr.connection() as conn:
                # Check if celery_taskmeta table exists
                check_table = conn.execute(
                    """
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_name = 'celery_taskmeta'
                    )
                    """
                )
                table_exists = check_table.scalar()

                if not table_exists:
                    return None, None, 0, 0, None, None, None

                # Query last 7 days of task execution
                lookback_days = self.celery_config["lookback_days"]

                result = conn.execute(
                    f"""
                    SELECT
                        MAX(date_done) as last_run,
                        COUNT(*) FILTER (WHERE status = 'SUCCESS') as success_count,
                        COUNT(*) FILTER (WHERE status = 'FAILURE') as failure_count
                    FROM celery_taskmeta
                    WHERE task_name = %s
                    AND date_done >= NOW() - INTERVAL '{lookback_days} days'
                    """,
                    [task_path],
                )

                row = result.first()

                if row:
                    last_run = row[0]
                    success_count = row[1] or 0
                    failure_count = row[2] or 0

                    # Calculate success rate
                    total = success_count + failure_count
                    success_rate = int((success_count / total) * 100) if total > 0 else None

                    # TODO: Calculate duration metrics (requires parsing result JSONB)
                    avg_duration = None
                    max_duration = None

                    return (
                        last_run,
                        None,  # next_run_at (requires celerybeat schedule tracking)
                        success_count,
                        failure_count,
                        success_rate,
                        avg_duration,
                        max_duration,
                    )

        except Exception as e:
            logger.warning("failed_to_query_task_metadata", task=task_path, error=str(e))

        return None, None, 0, 0, None, None, None

    def _detect_populates_tables(self, task_path: str) -> list[str]:
        """Detect which tables a task populates by scanning task file.

        Uses basic regex to find INSERT INTO and UPDATE statements.

        Args:
            task_path: Task import path (e.g., app.tasks.market_data_tasks.fetch_prices)

        Returns:
            List of table names this task writes to
        """
        try:
            # Convert import path to file path
            # app.tasks.market_data_tasks.fetch_prices -> backend/app/tasks/market_data_tasks.py
            path_parts = task_path.split(".")
            if len(path_parts) < 2:
                return []

            # Remove function name
            module_parts = path_parts[:-1]

            # Build file path
            file_path = Path(__file__).parent.parent / "/".join(module_parts[1:])
            file_path = file_path.with_suffix(".py")

            if not file_path.exists():
                return []

            # Read file and search for SQL statements
            content = file_path.read_text()

            # Regex patterns for INSERT/UPDATE
            patterns = [
                r"INSERT\s+INTO\s+([a-z_][a-z0-9_]*)",
                r"UPDATE\s+([a-z_][a-z0-9_]*)",
            ]

            tables = set()
            for pattern in patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                tables.update(matches)

            return sorted(tables)

        except Exception as e:
            logger.debug("failed_to_detect_populated_tables", task=task_path, error=str(e))
            return []

    def save_capabilities(self, capabilities: list[dict[str, Any]]) -> int:
        """Save scanned Celery capabilities to celery_capabilities table.

        Uses UPSERT logic (INSERT ... ON CONFLICT DO UPDATE) to update existing records.

        Args:
            capabilities: List of capability dicts from scan()

        Returns:
            Number of rows inserted/updated
        """
        if not capabilities:
            logger.info("no_celery_capabilities_to_save")
            return 0

        logger.info("saving_celery_capabilities", count=len(capabilities))

        with self.conn_mgr.connection() as conn:
            for cap in capabilities:
                # Convert lists to JSON strings for JSONB columns
                populates_tables_json = _to_json_string(cap["populates_tables"])
                depends_on_tasks_json = _to_json_string(cap["depends_on_tasks"])

                # UPSERT query
                conn.execute(
                    """
                    INSERT INTO celery_capabilities (
                        task_name, category, task_path, function_name,
                        schedule_description, schedule_crontab, schedule_interval_seconds,
                        last_run_at, next_run_at,
                        success_count_7d, failure_count_7d, success_rate_pct,
                        avg_duration_ms, max_duration_ms,
                        populates_tables, depends_on_tasks,
                        last_scanned_at, created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (task_name) DO UPDATE SET
                        category = EXCLUDED.category,
                        task_path = EXCLUDED.task_path,
                        function_name = EXCLUDED.function_name,
                        schedule_description = EXCLUDED.schedule_description,
                        schedule_crontab = EXCLUDED.schedule_crontab,
                        schedule_interval_seconds = EXCLUDED.schedule_interval_seconds,
                        last_run_at = EXCLUDED.last_run_at,
                        next_run_at = EXCLUDED.next_run_at,
                        success_count_7d = EXCLUDED.success_count_7d,
                        failure_count_7d = EXCLUDED.failure_count_7d,
                        success_rate_pct = EXCLUDED.success_rate_pct,
                        avg_duration_ms = EXCLUDED.avg_duration_ms,
                        max_duration_ms = EXCLUDED.max_duration_ms,
                        populates_tables = EXCLUDED.populates_tables,
                        depends_on_tasks = EXCLUDED.depends_on_tasks,
                        last_scanned_at = EXCLUDED.last_scanned_at,
                        updated_at = EXCLUDED.updated_at
                    """,
                    [
                        cap["task_name"],
                        cap["category"],
                        cap["task_path"],
                        cap["function_name"],
                        cap["schedule_description"],
                        cap["schedule_crontab"],
                        cap["schedule_interval_seconds"],
                        cap["last_run_at"],
                        cap["next_run_at"],
                        cap["success_count_7d"],
                        cap["failure_count_7d"],
                        cap["success_rate_pct"],
                        cap["avg_duration_ms"],
                        cap["max_duration_ms"],
                        populates_tables_json,
                        depends_on_tasks_json,
                        datetime.now(UTC),  # last_scanned_at
                        datetime.now(UTC),  # created_at
                        datetime.now(UTC),  # updated_at
                    ],
                )
                conn.commit()

        logger.info("celery_capabilities_saved", count=len(capabilities))
        return len(capabilities)


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

            endpoints.append(
                {
                    "endpoint_path": path,
                    "http_method": method.upper(),
                    "category": category,
                    "route_file": str(route_file.name),
                    "function_name": function_name or "unknown",
                    "depends_on_tables": depends_on_tables,
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
                        depends_on_tables,
                        avg_response_time_ms, p95_response_time_ms, p99_response_time_ms,
                        error_rate_pct, last_7d_request_count,
                        last_scanned_at, created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (endpoint_path, http_method) DO UPDATE SET
                        category = EXCLUDED.category,
                        route_file = EXCLUDED.route_file,
                        function_name = EXCLUDED.function_name,
                        depends_on_tables = EXCLUDED.depends_on_tables,
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


def _to_json_string(value: list[Any] | None) -> str:
    """Convert Python list to JSON string for JSONB column.

    Args:
        value: List to convert or None

    Returns:
        JSON string representation
    """
    import json  # noqa: PLC0415

    return json.dumps(value) if value else "[]"
