#!/usr/bin/env python3
"""Analyze health report and categorize issues by priority."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def analyze_health(report_path: str) -> dict:
    """Analyze health report and return categorized issues."""
    with open(report_path) as f:
        data = json.load(f)

    issues = {
        "P0_critical": [],
        "P1_high": [],
        "P2_medium": [],
        "P3_low": [],
        "P4_info": [],
    }

    # P0 - Critical (services down)
    main_health = data.get("main_health", {})
    if main_health.get("status") == "down":
        issues["P0_critical"].append(
            {
                "issue": "System Down",
                "details": "Database or critical service unreachable",
                "severity": "critical",
            }
        )

    services = data.get("service_status", {})
    for service, status in services.items():
        if status != "active" and service in ["backend", "celery_worker", "redis"]:
            issues["P0_critical"].append(
                {
                    "issue": f"{service} service down",
                    "details": f"Service status: {status}",
                    "severity": "critical",
                }
            )

    # P1 - High (data freshness)
    detailed = data.get("detailed_health", {})
    day_bars = detailed.get("day_bars_freshness", [])
    now = datetime.now(timezone.utc)

    stale_symbols = []
    for item in day_bars:
        last_updated_str = item["last_updated"]
        # Handle both with and without 'Z' suffix
        if last_updated_str.endswith("Z"):
            last_updated_str = last_updated_str[:-1] + "+00:00"
        elif "+" not in last_updated_str:
            last_updated_str += "+00:00"

        last_updated = datetime.fromisoformat(last_updated_str)
        age_days = (now - last_updated).days

        # Weekday: >3 days stale, Weekend: >5 days stale
        threshold = 5 if now.weekday() >= 5 else 3
        if age_days > threshold:
            stale_symbols.append((item["symbol"], age_days))

    if stale_symbols:
        issues["P1_high"].append(
            {
                "issue": "OHLCV Data Stale",
                "details": f"{len(stale_symbols)} symbols with data {stale_symbols[0][1]}+ days old",
                "symbols": stale_symbols[:5],  # Top 5
                "severity": "high",
            }
        )

    # P2 - Medium (data sources down)
    sources = main_health.get("sources", {})
    for source_name, source_data in sources.items():
        if source_data.get("status") == "down":
            last_success = source_data.get("last_success")
            issues["P2_medium"].append(
                {
                    "issue": f"{source_name} source DOWN",
                    "details": f"Last success: {last_success or 'Never'}",
                    "success_rate": source_data.get("success_rate", 0),
                    "severity": "medium",
                }
            )

    # P3 - Low (performance issues)
    cache_stats = main_health.get("cache_stats", {})
    # Add cache hit rate analysis if available

    for source_name, source_data in sources.items():
        latency = source_data.get("avg_latency_ms")
        if latency and latency > 2000:
            issues["P3_low"].append(
                {
                    "issue": f"{source_name} high latency",
                    "details": f"Average latency: {latency}ms",
                    "severity": "low",
                }
            )

    # P4 - Info (configuration)
    api_quotas = main_health.get("api_quotas", [])
    for quota in api_quotas:
        if not quota.get("configured"):
            issues["P4_info"].append(
                {
                    "issue": f"{quota['source_name']} not configured",
                    "details": "API key not set",
                    "severity": "info",
                }
            )

    return issues


def print_summary(issues: dict):
    """Print human-readable summary."""
    total = sum(len(v) for v in issues.values())

    print("\n=== SYSTEM HEALTH SUMMARY ===")
    print(f"Total Issues: {total}")
    print(f"  P0 Critical: {len(issues['P0_critical'])}")
    print(f"  P1 High: {len(issues['P1_high'])}")
    print(f"  P2 Medium: {len(issues['P2_medium'])}")
    print(f"  P3 Low: {len(issues['P3_low'])}")
    print(f"  P4 Info: {len(issues['P4_info'])}")

    for priority, issue_list in issues.items():
        if issue_list:
            print(f"\n--- {priority.replace('_', ' ').upper()} ---")
            for issue in issue_list:
                print(f"  • {issue['issue']}")
                print(f"    {issue['details']}")


if __name__ == "__main__":
    report_path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/health-report.json"

    if not Path(report_path).exists():
        print(f"Error: Health report not found: {report_path}", file=sys.stderr)
        sys.exit(1)

    issues = analyze_health(report_path)

    # Print summary
    print_summary(issues)

    # Save analyzed issues
    output_path = report_path.replace(".json", "-issues.json")
    with open(output_path, "w") as f:
        json.dump(issues, f, indent=2)

    print(f"\nDetailed issues saved to: {output_path}")

    # Exit code based on severity
    if issues["P0_critical"]:
        sys.exit(2)  # Critical
    elif issues["P1_high"]:
        sys.exit(1)  # High
    else:
        sys.exit(0)  # OK
