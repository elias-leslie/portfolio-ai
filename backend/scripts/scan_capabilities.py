#!/usr/bin/env python3
"""
Scan system capabilities - auto-discover data sources, features, and infrastructure.

This script scans the codebase and running system to detect:
- Database tables and their coverage
- Celery scheduled tasks
- API endpoints that provide data
- Changes since last scan (NEW additions)

Usage:
    python backend/scripts/scan_capabilities.py
    python backend/scripts/scan_capabilities.py --output json
    python backend/scripts/scan_capabilities.py --diff  # Show only changes since last scan
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, inspect, text

from app.celery_app import celery_app
from app.constants import DATABASE_URL


def scan_database_tables() -> list[dict[str, Any]]:
    """Scan database tables and get metadata + row counts."""
    engine = create_engine(DATABASE_URL)
    inspector = inspect(engine)

    capabilities = []

    with engine.connect() as conn:
        for table_name in inspector.get_table_names():
            # Get row count
            result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
            row_count = result.scalar()

            # Get columns
            columns = inspector.get_columns(table_name)
            column_names = [col["name"] for col in columns]

            # Detect date range if timestamp columns exist
            date_range = None
            for col in ["created_at", "updated_at", "timestamp", "date"]:
                if col in column_names:
                    try:
                        result = conn.execute(
                            text(
                                f"SELECT MIN({col}), MAX({col}) FROM {table_name} WHERE {col} IS NOT NULL"
                            )
                        )
                        min_date, max_date = result.first()
                        if min_date and max_date:
                            date_range = f"{min_date.date()} to {max_date.date()}"
                            break
                    except Exception:
                        pass

            capabilities.append(
                {
                    "category": _categorize_table(table_name),
                    "name": f"{table_name.replace('_', ' ').title()} Table",
                    "source_type": "database_table",
                    "source_location": f"Database table: {table_name}",
                    "coverage": f"{row_count:,} rows" + (f", {date_range}" if date_range else ""),
                    "metadata": {
                        "table_name": table_name,
                        "columns": column_names,
                        "row_count": row_count,
                        "date_range": date_range,
                    },
                }
            )

    return capabilities


def scan_celery_tasks() -> list[dict[str, Any]]:
    """Scan Celery beat schedule for scheduled tasks."""
    capabilities = []
    schedule = celery_app.conf.beat_schedule

    for task_name, config in schedule.items():
        task_path = config["task"]
        schedule_info = str(config["schedule"])

        capabilities.append(
            {
                "category": _categorize_celery_task(task_name),
                "name": f"Scheduled Task: {task_name.replace('-', ' ').replace('_', ' ').title()}",
                "source_type": "celery_task",
                "source_location": f"Celery task: {task_path}",
                "coverage": f"Runs {schedule_info}",
                "metadata": {
                    "task_name": task_name,
                    "task_path": task_path,
                    "schedule": schedule_info,
                },
            }
        )

    return capabilities


def scan_api_endpoints() -> list[dict[str, Any]]:
    """Scan FastAPI endpoints by reading route files (avoids loading full app)."""
    capabilities = []
    routes_dir = Path(__file__).parent.parent / "app" / "routes"

    if not routes_dir.exists():
        return []

    # Scan route files for @router decorators
    for route_file in routes_dir.glob("*.py"):
        if route_file.name.startswith("_"):
            continue

        content = route_file.read_text()

        # Find all route decorators: @router.get("/path")
        route_pattern = r'@router\.(get|post|put|delete)\(["\']([^"\']+)["\']\)'
        matches = re.findall(route_pattern, content)

        for method, path in matches:
            # Skip health/docs endpoints
            if any(x in path for x in ["/health", "/docs", "/openapi"]):
                continue

            # Only track GET endpoints (data retrieval)
            if method.upper() == "GET":
                capabilities.append(
                    {
                        "category": _categorize_api_endpoint(path),
                        "name": f"API: {path}",
                        "source_type": "api_endpoint",
                        "source_location": f"GET {path} (in {route_file.name})",
                        "coverage": "REST API endpoint",
                        "metadata": {
                            "path": path,
                            "method": method,
                            "file": route_file.name,
                        },
                    }
                )

    return capabilities


def _categorize_table(table_name: str) -> str:
    """Categorize database table by name."""
    if "market_data" in table_name or "ticker" in table_name or "ohlcv" in table_name:
        return "market_data"
    if "news" in table_name or "article" in table_name:
        return "news"
    if "portfolio" in table_name or "holding" in table_name or "watchlist" in table_name:
        return "portfolio"
    if "user" in table_name or "auth" in table_name:
        return "infrastructure"
    return "analytics"


def _categorize_celery_task(task_name: str) -> str:
    """Categorize Celery task by name."""
    if "market" in task_name or "price" in task_name or "ohlcv" in task_name:
        return "market_data"
    if "news" in task_name:
        return "news"
    if "fear" in task_name or "greed" in task_name or "sentiment" in task_name:
        return "analytics"
    return "infrastructure"


def _categorize_api_endpoint(path: str) -> str:
    """Categorize API endpoint by path."""
    if "/market" in path or "/ticker" in path or "/ohlcv" in path:
        return "market_data"
    if "/news" in path:
        return "news"
    if "/portfolio" in path or "/watchlist" in path:
        return "portfolio"
    if "/fear" in path or "/greed" in path or "/sentiment" in path:
        return "analytics"
    return "infrastructure"


def detect_changes(current: list[dict], previous: list[dict]) -> dict[str, list[dict]]:
    """Detect what's new, changed, or removed since last scan."""

    def make_key(item: dict) -> str:
        return f"{item['source_type']}:{item['source_location']}"

    current_map = {make_key(item): item for item in current}
    previous_map = {make_key(item): item for item in previous}

    current_keys = set(current_map.keys())
    previous_keys = set(previous_map.keys())

    new_items = [current_map[k] for k in current_keys - previous_keys]
    removed_items = [previous_map[k] for k in previous_keys - current_keys]

    # Detect changed items (coverage changed)
    changed_items = []
    for key in current_keys & previous_keys:
        if current_map[key]["coverage"] != previous_map[key]["coverage"]:
            changed_items.append(
                {
                    "item": current_map[key],
                    "old_coverage": previous_map[key]["coverage"],
                    "new_coverage": current_map[key]["coverage"],
                }
            )

    return {
        "new": new_items,
        "removed": removed_items,
        "changed": changed_items,
    }


def load_previous_scan() -> list[dict] | None:
    """Load previous scan results from file."""
    scan_file = Path(__file__).parent / ".capabilities_scan.json"
    if scan_file.exists():
        with scan_file.open() as f:
            data = json.load(f)
            return data.get("capabilities", [])
    return None


def save_scan(capabilities: list[dict]) -> None:
    """Save scan results to file for next comparison."""
    scan_file = Path(__file__).parent / ".capabilities_scan.json"
    with scan_file.open("w") as f:
        json.dump(
            {
                "scanned_at": datetime.utcnow().isoformat(),
                "capabilities": capabilities,
            },
            f,
            indent=2,
        )


def format_text_output(capabilities: list[dict], changes: dict | None = None) -> str:
    """Format capabilities as human-readable text."""
    output = []

    output.append("=" * 80)
    output.append("SYSTEM CAPABILITIES SCAN")
    output.append(f"Scanned at: {datetime.utcnow().isoformat()}")
    output.append(f"Total capabilities: {len(capabilities)}")
    output.append("=" * 80)
    output.append("")

    # Group by category
    by_category: dict[str, list[dict]] = {}
    for cap in capabilities:
        category = cap["category"]
        if category not in by_category:
            by_category[category] = []
        by_category[category].append(cap)

    # Print by category
    for category, items in sorted(by_category.items()):
        output.append(f"\n{category.upper()} ({len(items)} items)")
        output.append("-" * 80)

        for item in items:
            output.append(f"  • {item['name']}")
            output.append(f"    Source: {item['source_location']}")
            output.append(f"    Coverage: {item['coverage']}")
            output.append("")

    # Print changes if available
    if changes:
        output.append("\n" + "=" * 80)
        output.append("CHANGES SINCE LAST SCAN")
        output.append("=" * 80)

        if changes["new"]:
            output.append(f"\n🆕 NEW ({len(changes['new'])} items)")
            output.append("-" * 80)
            for item in changes["new"]:
                output.append(f"  • {item['name']}")
                output.append(f"    {item['source_location']}")
                output.append("")

        if changes["removed"]:
            output.append(f"\n🗑️  REMOVED ({len(changes['removed'])} items)")
            output.append("-" * 80)
            for item in changes["removed"]:
                output.append(f"  • {item['name']}")
                output.append(f"    {item['source_location']}")
                output.append("")

        if changes["changed"]:
            output.append(f"\n📝 CHANGED ({len(changes['changed'])} items)")
            output.append("-" * 80)
            for change in changes["changed"]:
                item = change["item"]
                output.append(f"  • {item['name']}")
                output.append(f"    Old: {change['old_coverage']}")
                output.append(f"    New: {change['new_coverage']}")
                output.append("")

        if not changes["new"] and not changes["removed"] and not changes["changed"]:
            output.append("\n✅ No changes detected")

    return "\n".join(output)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan system capabilities")
    parser.add_argument(
        "--output", choices=["text", "json"], default="text", help="Output format (default: text)"
    )
    parser.add_argument("--diff", action="store_true", help="Show only changes since last scan")
    args = parser.parse_args()

    print("Scanning system capabilities...", file=sys.stderr)

    # Scan all sources
    capabilities = []
    capabilities.extend(scan_database_tables())
    capabilities.extend(scan_celery_tasks())
    capabilities.extend(scan_api_endpoints())

    # Sort by category, then name
    capabilities.sort(key=lambda x: (x["category"], x["name"]))

    # Detect changes
    previous = load_previous_scan()
    changes = detect_changes(capabilities, previous) if previous else None

    # Save current scan
    save_scan(capabilities)

    # Output
    if args.output == "json":
        output_data = {
            "scanned_at": datetime.utcnow().isoformat(),
            "total": len(capabilities),
            "capabilities": capabilities,
        }
        if changes:
            output_data["changes"] = changes
        print(json.dumps(output_data, indent=2))
    elif args.diff and changes:
        # Only show changes
        output = []
        output.append("CHANGES SINCE LAST SCAN")
        output.append("=" * 80)

        if changes["new"]:
            output.append(f"\n🆕 NEW ({len(changes['new'])} items)")
            for item in changes["new"]:
                output.append(f"  • {item['name']} - {item['source_location']}")

        if changes["removed"]:
            output.append(f"\n🗑️  REMOVED ({len(changes['removed'])} items)")
            for item in changes["removed"]:
                output.append(f"  • {item['name']} - {item['source_location']}")

        if changes["changed"]:
            output.append(f"\n📝 CHANGED ({len(changes['changed'])} items)")
            for change in changes["changed"]:
                output.append(f"  • {change['item']['name']}")
                output.append(f"    {change['old_coverage']} → {change['new_coverage']}")

        if not changes["new"] and not changes["removed"] and not changes["changed"]:
            output.append("✅ No changes detected")

        print("\n".join(output))
    else:
        print(format_text_output(capabilities, changes))


if __name__ == "__main__":
    main()
