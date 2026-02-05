"""Table and task dependency detection for Celery scanner."""

from __future__ import annotations

import re
from pathlib import Path

from ..logging_config import get_logger

logger = get_logger(__name__)


def detect_populates_tables(task_path: str) -> list[str]:
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


def detect_reads_from_tables(task_path: str) -> list[str]:
    """Detect tables this task reads from via SQL patterns.

    Searches for patterns like:
    - SELECT ... FROM table_name (inside SQL strings)
    - JOIN table_name (inside SQL strings)

    Only detects tables inside string literals (SQL queries).

    Args:
        task_path: Task import path

    Returns:
        Sorted list of table names read by this task (excludes tables it writes to)
    """
    try:
        # Convert import path to file path (same as detect_populates_tables)
        path_parts = task_path.split(".")
        if len(path_parts) < 2:
            return []

        module_parts = path_parts[:-1]
        file_path = Path(__file__).parent.parent / "/".join(module_parts[1:])
        file_path = file_path.with_suffix(".py")

        if not file_path.exists():
            return []

        content = file_path.read_text()
        tables = set()

        # Extract SQL string literals (triple-quoted and single-quoted)
        # Look for strings containing SQL keywords
        sql_string_pattern = r'(?:"""|\'\'\')(.*?)(?:"""|\'\'\')|(?:"([^"\\]*(?:\\.[^"\\]*)*)"|\'([^\'\\]*(?:\\.[^\'\\]*)*)\')'
        sql_strings = []

        for match in re.finditer(sql_string_pattern, content, re.DOTALL):
            s = match.group(1) or match.group(2) or match.group(3) or ""
            # Only consider strings that look like SQL (contain SELECT, INSERT, UPDATE, etc.)
            if re.search(r"\b(SELECT|INSERT|UPDATE|DELETE|WITH)\b", s, re.IGNORECASE):
                sql_strings.append(s)

        # Now search for table names only in SQL strings
        # Pattern: FROM table_name
        from_pattern = r"\bFROM\s+([a-z_][a-z0-9_]*)\b"
        # Pattern: JOIN table_name
        join_pattern = r"\bJOIN\s+([a-z_][a-z0-9_]*)\b"

        # SQL keywords and common false positives to filter out
        sql_keywords = {
            "select",
            "where",
            "and",
            "or",
            "not",
            "null",
            "true",
            "false",
            "dual",
            "information_schema",
            "lateral",
            "values",
            "unnest",
            "generate_series",
            "excluded",
            "returning",
            "case",
            "when",
            "then",
            "else",
            "end",
            "exists",
            "between",
            "like",
            "in",
            "is",
            "as",
            "on",
            "set",
            "into",
            "table",
        }

        for sql in sql_strings:
            for match in re.finditer(from_pattern, sql, re.IGNORECASE):
                table = match.group(1).lower()
                if table not in sql_keywords:
                    tables.add(table)

            for match in re.finditer(join_pattern, sql, re.IGNORECASE):
                table = match.group(1).lower()
                if table not in sql_keywords:
                    tables.add(table)

        # Remove tables that this task writes to (self-references)
        writes = {t.lower() for t in detect_populates_tables(task_path)}
        reads_only = tables - writes

        return sorted(reads_only)

    except Exception as e:
        logger.debug("failed_to_detect_reads_from_tables", task=task_path, error=str(e))
        return []


def detect_task_callers(task_name: str, task_path: str) -> list[str]:
    """Detect files/tasks that call this task.

    Searches for patterns like:
    - task_name.delay()
    - task_name.apply_async()
    - send_task('task_path')
    - celery_app.send_task('task_path')

    Args:
        task_name: Beat schedule name (e.g., "fetch-market-data-hourly")
        task_path: Task import path (e.g., "app.tasks.market_data_tasks.fetch_prices")

    Returns:
        List of file paths that call this task
    """
    try:
        callers = set()
        function_name = task_path.rsplit(".", maxsplit=1)[-1] if "." in task_path else task_path

        # Search patterns
        patterns = [
            rf"{function_name}\.delay\s*\(",
            rf"{function_name}\.apply_async\s*\(",
            rf"send_task\s*\(\s*['\"].*{function_name}['\"]",
            rf"send_task\s*\(\s*['\"].*{task_path}['\"]",
        ]

        # Search in backend app directory
        app_dir = Path(__file__).parent.parent
        for py_file in app_dir.glob("**/*.py"):
            # Skip the task's own file
            if function_name in py_file.name:
                continue

            try:
                content = py_file.read_text()
                for pattern in patterns:
                    if re.search(pattern, content):
                        # Get relative path from app/
                        rel_path = str(py_file.relative_to(app_dir))
                        callers.add(rel_path)
                        break
            except Exception:
                continue

        return sorted(callers)

    except Exception as e:
        logger.debug("failed_to_detect_task_callers", task=task_name, error=str(e))
        return []


def detect_task_dependencies(task_path: str) -> list[str]:
    """Detect tasks that this task calls (dependencies).

    Searches for patterns like:
    - other_task.delay()
    - send_task('other_task')

    Args:
        task_path: Task import path

    Returns:
        List of task names this task depends on
    """
    try:
        dependencies = set()

        # Convert import path to file path
        path_parts = task_path.split(".")
        if len(path_parts) < 2:
            return []

        module_parts = path_parts[:-1]
        file_path = Path(__file__).parent.parent / "/".join(module_parts[1:])
        file_path = file_path.with_suffix(".py")

        if not file_path.exists():
            return []

        content = file_path.read_text()

        # Find all .delay() and .apply_async() calls
        delay_pattern = r"(\w+)\.delay\s*\("
        async_pattern = r"(\w+)\.apply_async\s*\("
        send_pattern = r"send_task\s*\(\s*['\"]([^'\"]+)['\"]"

        for match in re.finditer(delay_pattern, content):
            task_var = match.group(1)
            # Filter out common non-task variables
            if task_var not in ["self", "cls", "result", "response", "data"]:
                dependencies.add(task_var)

        for match in re.finditer(async_pattern, content):
            task_var = match.group(1)
            if task_var not in ["self", "cls", "result", "response", "data"]:
                dependencies.add(task_var)

        for match in re.finditer(send_pattern, content):
            dependencies.add(match.group(1))

        return sorted(dependencies)

    except Exception as e:
        logger.debug("failed_to_detect_task_dependencies", task=task_path, error=str(e))
        return []
