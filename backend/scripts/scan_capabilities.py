#!/usr/bin/env python3
"""
Scan system capabilities - auto-discover data sources, features, and infrastructure.

This script scans the codebase and running system to detect:
- Database tables and their coverage
- Hatchet scheduled tasks
- API endpoints that provide data
- Changes since last scan (NEW additions)

Usage:
    python backend/scripts/scan_capabilities.py
    python backend/scripts/scan_capabilities.py --output json
    python backend/scripts/scan_capabilities.py --diff  # Show only changes since last scan
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, inspect, text

from app.constants import DATABASE_URL

logger = logging.getLogger(__name__)


class Capability(TypedDict):
    """A single discovered system capability."""

    category: str
    name: str
    source_type: str
    source_location: str
    coverage: str
    metadata: dict[str, object]


ChangeSet = dict[str, list[Capability]]

_SCAN_FILE = Path(__file__).parent / ".capabilities_scan.json"


# ---------------------------------------------------------------------------
# Categorisation helpers
# ---------------------------------------------------------------------------


def _categorize_table(table_name: str) -> str:
    """Categorize database table by name."""
    if any(k in table_name for k in ("market_data", "ticker", "ohlcv")):
        return "market_data"
    if any(k in table_name for k in ("news", "article")):
        return "news"
    if any(k in table_name for k in ("portfolio", "holding", "watchlist")):
        return "portfolio"
    if any(k in table_name for k in ("user", "auth")):
        return "infrastructure"
    return "analytics"


def _categorize_api_endpoint(path: str) -> str:
    """Categorize API endpoint by path."""
    if any(k in path for k in ("/market", "/ticker", "/ohlcv")):
        return "market_data"
    if "/news" in path:
        return "news"
    if any(k in path for k in ("/portfolio", "/watchlist")):
        return "portfolio"
    if any(k in path for k in ("/fear", "/greed", "/sentiment")):
        return "analytics"
    return "infrastructure"


def _categorize_scheduled_task(name: str) -> str:
    """Categorize scheduled workflow names."""
    normalized = name.replace("portfolio-", "").replace("_", "-")
    if any(k in normalized for k in ("ohlcv", "indicator", "market", "risk", "earnings")):
        return "market_data"
    if any(k in normalized for k in ("news", "source", "sec-cik")):
        return "news"
    if any(k in normalized for k in ("portfolio", "watchlist", "jenny")):
        return "portfolio"
    if any(k in normalized for k in ("strategy", "signal", "paper-trade")):
        return "analytics"
    return "infrastructure"


# ---------------------------------------------------------------------------
# Scanners
# ---------------------------------------------------------------------------


def _table_date_range(conn: object, table_name: str, column_names: list[str]) -> str | None:
    """Return a date-range string for the first timestamp column found, or None."""
    timestamp_cols = ("created_at", "updated_at", "timestamp", "date")
    for col in timestamp_cols:
        if col not in column_names:
            continue
        try:
            result = conn.execute(  # type: ignore[union-attr]
                text(f"SELECT MIN({col}), MAX({col}) FROM {table_name} WHERE {col} IS NOT NULL")
            )
            row = result.first()
            if row is None:
                continue
            min_date, max_date = row
            if not (min_date and max_date):
                continue
            min_str = min_date.isoformat() if hasattr(min_date, "isoformat") else str(min_date)
            max_str = max_date.isoformat() if hasattr(max_date, "isoformat") else str(max_date)
            return f"{min_str} to {max_str}"
        except Exception as e:
            logger.warning("Failed to get date range for %s.%s: %s", table_name, col, e)
    return None


def scan_database_tables() -> list[Capability]:
    """Scan database tables and get metadata + row counts."""
    engine = create_engine(DATABASE_URL)
    inspector = inspect(engine)
    capabilities: list[Capability] = []

    with engine.connect() as conn:
        for table_name in inspector.get_table_names():
            row_count = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
            column_names = [col["name"] for col in inspector.get_columns(table_name)]
            date_range = _table_date_range(conn, table_name, column_names)
            coverage = f"{row_count:,} rows" + (f", {date_range}" if date_range else "")

            capabilities.append(
                {
                    "category": _categorize_table(table_name),
                    "name": f"{table_name.replace('_', ' ').title()} Table",
                    "source_type": "database_table",
                    "source_location": f"Database table: {table_name}",
                    "coverage": coverage,
                    "metadata": {
                        "table_name": table_name,
                        "columns": column_names,
                        "row_count": row_count,
                        "date_range": date_range,
                    },
                }
            )

    return capabilities


def scan_scheduled_tasks() -> list[Capability]:
    """Scan Hatchet task definitions from workflow modules."""
    workflows_dir = Path(__file__).parent.parent / "app" / "workflows"
    if not workflows_dir.exists():
        return []

    capabilities: list[Capability] = []
    task_pattern = re.compile(r"@hatchet\.task\((?P<args>.*?)\)\s*async def (?P<func>\w+)", re.S)
    name_pattern = re.compile(r'name\s*=\s*"([^"]+)"')
    crons_pattern = re.compile(r"on_crons\s*=\s*\[(?P<crons>[^\]]*)\]")

    for workflow_file in workflows_dir.glob("*.py"):
        if workflow_file.name.startswith("_"):
            continue
        content = workflow_file.read_text()
        for match in task_pattern.finditer(content):
            args_block = match.group("args")
            function_name = match.group("func")
            name_match = name_pattern.search(args_block)
            if not name_match:
                continue

            workflow_name = name_match.group(1)
            crons_match = crons_pattern.search(args_block)
            crons = re.findall(r'"([^"]+)"', crons_match.group("crons")) if crons_match else []
            coverage = (
                f"Cron: {', '.join(crons)}"
                if crons
                else "Manual or event-driven workflow"
            )

            capabilities.append(
                {
                    "category": _categorize_scheduled_task(workflow_name),
                    "name": f"Scheduled Task: {workflow_name.replace('portfolio-', '').replace('-', ' ').title()}",
                    "source_type": "scheduled_task",
                    "source_location": f"Hatchet task: {workflow_name}",
                    "coverage": coverage,
                    "metadata": {
                        "workflow_name": workflow_name,
                        "function_name": function_name,
                        "file": workflow_file.name,
                        "crons": crons,
                    },
                }
            )

    return capabilities


def scan_celery_tasks() -> list[Capability]:
    """Backward-compatible alias for scheduled task scanning."""
    return scan_scheduled_tasks()


def scan_api_endpoints() -> list[Capability]:
    """Scan FastAPI endpoints by reading route files (avoids loading full app)."""
    api_dir = Path(__file__).parent.parent / "app" / "api"
    if not api_dir.exists():
        return []

    capabilities: list[Capability] = []
    route_pattern = r'@router\.(get|post|put|delete)\(["\']([^"\']+)["\']\)'
    skip_paths = ("/health", "/docs", "/openapi")

    for route_file in api_dir.rglob("*.py"):
        if route_file.name.startswith("_") or "__pycache__" in route_file.parts:
            continue
        for method, path in re.findall(route_pattern, route_file.read_text()):
            if any(s in path for s in skip_paths) or method.upper() != "GET":
                continue
            capabilities.append(
                {
                    "category": _categorize_api_endpoint(path),
                    "name": f"API: {path}",
                    "source_type": "api_endpoint",
                    "source_location": f"GET {path} (in {route_file.relative_to(api_dir.parent)})",
                    "coverage": "REST API endpoint",
                    "metadata": {
                        "path": path,
                        "method": method,
                        "file": str(route_file.relative_to(api_dir.parent)),
                    },
                }
            )

    return capabilities


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def load_previous_scan() -> list[Capability] | None:
    """Load previous scan results from file."""
    if not _SCAN_FILE.exists():
        return None
    try:
        data: dict[str, object] = json.loads(_SCAN_FILE.read_text())
    except json.JSONDecodeError as e:
        logger.warning("Previous scan file contains invalid JSON, ignoring: %s", e)
        return None
    result = data.get("capabilities", [])
    return result if isinstance(result, list) else None


def save_scan(capabilities: list[Capability]) -> None:
    """Save scan results to file for next comparison."""
    _SCAN_FILE.write_text(
        json.dumps(
            {"scanned_at": datetime.now(UTC).isoformat(), "capabilities": capabilities},
            indent=2,
        )
    )


# ---------------------------------------------------------------------------
# Change detection
# ---------------------------------------------------------------------------


def detect_changes(current: list[Capability], previous: list[Capability]) -> ChangeSet:
    """Detect what's new, changed, or removed since last scan."""

    def make_key(item: Capability) -> str:
        return f"{item['source_type']}:{item['source_location']}"

    current_map = {make_key(i): i for i in current}
    previous_map = {make_key(i): i for i in previous}
    current_keys, previous_keys = set(current_map), set(previous_map)

    changed = [
        {"item": current_map[k], "old_coverage": previous_map[k]["coverage"], "new_coverage": current_map[k]["coverage"]}
        for k in current_keys & previous_keys
        if current_map[k]["coverage"] != previous_map[k]["coverage"]
    ]

    return {
        "new": [current_map[k] for k in current_keys - previous_keys],
        "removed": [previous_map[k] for k in previous_keys - current_keys],
        "changed": changed,
    }


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def _format_change_group(label: str, items: list[Capability]) -> list[str]:
    """Render a single group (NEW / REMOVED) within the changes section."""
    if not items:
        return []
    header = [f"\n{label} ({len(items)} items)", "-" * 80]
    body = [line for item in items for line in (f"  \u2022 {item['name']}", f"    {item['source_location']}", "")]
    return header + body


def _format_changes_section(changes: ChangeSet) -> list[str]:
    """Render the CHANGES block as lines."""
    lines: list[str] = ["\n" + "=" * 80, "CHANGES SINCE LAST SCAN", "=" * 80]
    lines.extend(_format_change_group("NEW", changes["new"]))
    lines.extend(_format_change_group("REMOVED", changes["removed"]))

    if changes["changed"]:
        lines += [f"\nCHANGED ({len(changes['changed'])} items)", "-" * 80]
        for change in changes["changed"]:
            item = change["item"]
            lines += [f"  \u2022 {item['name']}", f"    Old: {change['old_coverage']}", f"    New: {change['new_coverage']}", ""]

    if not any(changes[k] for k in ("new", "removed", "changed")):
        lines.append("\nNo changes detected")

    return lines


def format_text_output(capabilities: list[Capability], changes: ChangeSet | None = None) -> str:
    """Format capabilities as human-readable text."""
    lines: list[str] = [
        "=" * 80,
        "SYSTEM CAPABILITIES SCAN",
        f"Scanned at: {datetime.now(UTC).isoformat()}",
        f"Total capabilities: {len(capabilities)}",
        "=" * 80,
        "",
    ]

    by_category: dict[str, list[Capability]] = {}
    for cap in capabilities:
        by_category.setdefault(str(cap["category"]), []).append(cap)

    for category, items in sorted(by_category.items()):
        lines.append(f"\n{category.upper()} ({len(items)} items)")
        lines.append("-" * 80)
        for item in items:
            lines += [f"  \u2022 {item['name']}", f"    Source: {item['source_location']}", f"    Coverage: {item['coverage']}", ""]

    if changes:
        lines.extend(_format_changes_section(changes))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Diff-only output
# ---------------------------------------------------------------------------


def _print_diff_output(changes: ChangeSet) -> None:
    """Print diff-only view to stdout."""
    lines = ["CHANGES SINCE LAST SCAN", "=" * 80]

    if changes["new"]:
        lines.append(f"\nNEW ({len(changes['new'])} items)")
        lines.extend(f"  \u2022 {i['name']} - {i['source_location']}" for i in changes["new"])

    if changes["removed"]:
        lines.append(f"\nREMOVED ({len(changes['removed'])} items)")
        lines.extend(f"  \u2022 {i['name']} - {i['source_location']}" for i in changes["removed"])

    if changes["changed"]:
        lines.append(f"\nCHANGED ({len(changes['changed'])} items)")
        for change in changes["changed"]:
            lines += [f"  \u2022 {change['item']['name']}", f"    {change['old_coverage']} \u2192 {change['new_coverage']}"]

    if not any(changes[k] for k in ("new", "removed", "changed")):
        lines.append("No changes detected")

    print("\n".join(lines))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan system capabilities")
    parser.add_argument("--output", choices=["text", "json"], default="text", help="Output format (default: text)")
    parser.add_argument("--diff", action="store_true", help="Show only changes since last scan")
    args = parser.parse_args()

    print("Scanning system capabilities...", file=sys.stderr)

    capabilities: list[Capability] = sorted(
        [*scan_database_tables(), *scan_celery_tasks(), *scan_api_endpoints()],
        key=lambda x: (x["category"], x["name"]),
    )

    previous = load_previous_scan()
    changes = detect_changes(capabilities, previous) if previous else None
    if not args.diff:
        save_scan(capabilities)

    if args.output == "json":
        output_data: dict[str, object] = {
            "scanned_at": datetime.now(UTC).isoformat(),
            "total": len(capabilities),
            "capabilities": capabilities,
        }
        if changes:
            output_data["changes"] = changes
        print(json.dumps(output_data, indent=2))
    elif args.diff and changes:
        _print_diff_output(changes)
    else:
        print(format_text_output(capabilities, changes))


if __name__ == "__main__":
    main()
