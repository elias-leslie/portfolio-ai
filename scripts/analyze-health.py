#!/usr/bin/env python3
"""Analyze health report and categorize issues by priority."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Priority bucket keys
P0_CRITICAL = "P0_critical"
P1_HIGH = "P1_high"
P2_MEDIUM = "P2_medium"
P3_LOW = "P3_low"
P4_INFO = "P4_info"

PRIORITY_KEYS = [P0_CRITICAL, P1_HIGH, P2_MEDIUM, P3_LOW, P4_INFO]

# Status strings
STATUS_DOWN = "down"
STATUS_ACTIVE = "active"

# Critical services whose absence escalates to P0
CRITICAL_SERVICES = {"backend", "worker", "redis"}

# Staleness thresholds (days)
STALE_THRESHOLD_WEEKDAY = 3
STALE_THRESHOLD_WEEKEND = 5
WEEKEND_WEEKDAY_START = 5  # Saturday is weekday() == 5

# Performance threshold
HIGH_LATENCY_MS = 2000

# Top stale symbols to include in issue detail
TOP_STALE_SYMBOLS = 5

# Default report path
DEFAULT_REPORT_PATH = "/tmp/health-report.json"

# Exit codes
EXIT_OK = 0
EXIT_HIGH = 1
EXIT_CRITICAL = 2


# ---------------------------------------------------------------------------
# Issue-building helpers
# ---------------------------------------------------------------------------

def _empty_issues() -> dict:
    """Return an empty issues dict with all priority buckets."""
    return {key: [] for key in PRIORITY_KEYS}


def _check_main_service_down(data: dict, issues: dict) -> None:
    """P0: flag if the main health status reports the system as down."""
    main_health = data.get("main_health", {})
    if main_health.get("status") == STATUS_DOWN:
        issues[P0_CRITICAL].append(
            {
                "issue": "System Down",
                "details": "Database or critical service unreachable",
                "severity": "critical",
            }
        )


def _check_critical_services(data: dict, issues: dict) -> None:
    """P0: flag any critical service that is not active."""
    services = data.get("service_status", {})
    for service, status in services.items():
        if status != STATUS_ACTIVE and service in CRITICAL_SERVICES:
            issues[P0_CRITICAL].append(
                {
                    "issue": f"{service} service down",
                    "details": f"Service status: {status}",
                    "severity": "critical",
                }
            )


def _normalize_timestamp(ts: str) -> str:
    """Ensure an ISO-8601 timestamp string carries explicit UTC offset."""
    if ts.endswith("Z"):
        return ts[:-1] + "+00:00"
    if "+" not in ts:
        return ts + "+00:00"
    return ts


def _check_data_freshness(data: dict, issues: dict) -> None:
    """P1: flag symbols whose OHLCV data exceeds the staleness threshold."""
    detailed = data.get("detailed_health", {})
    day_bars = detailed.get("day_bars_freshness", [])
    now = datetime.now(timezone.utc)
    threshold = STALE_THRESHOLD_WEEKEND if now.weekday() >= WEEKEND_WEEKDAY_START else STALE_THRESHOLD_WEEKDAY

    stale_symbols = []
    for item in day_bars:
        last_updated = datetime.fromisoformat(_normalize_timestamp(item["last_updated"]))
        age_days = (now - last_updated).days
        if age_days > threshold:
            stale_symbols.append((item["symbol"], age_days))

    if stale_symbols:
        issues[P1_HIGH].append(
            {
                "issue": "OHLCV Data Stale",
                "details": f"{len(stale_symbols)} symbols with data {stale_symbols[0][1]}+ days old",
                "symbols": stale_symbols[:TOP_STALE_SYMBOLS],
                "severity": "high",
            }
        )


def _check_sources_down(sources: dict, issues: dict) -> None:
    """P2: flag data sources that are reported as down."""
    for source_name, source_data in sources.items():
        if source_data.get("status") == STATUS_DOWN:
            last_success = source_data.get("last_success")
            issues[P2_MEDIUM].append(
                {
                    "issue": f"{source_name} source DOWN",
                    "details": f"Last success: {last_success or 'Never'}",
                    "success_rate": source_data.get("success_rate", 0),
                    "severity": "medium",
                }
            )


def _check_high_latency(sources: dict, issues: dict) -> None:
    """P3: flag sources whose average latency exceeds the threshold."""
    for source_name, source_data in sources.items():
        latency = source_data.get("avg_latency_ms")
        if latency and latency > HIGH_LATENCY_MS:
            issues[P3_LOW].append(
                {
                    "issue": f"{source_name} high latency",
                    "details": f"Average latency: {latency}ms",
                    "severity": "low",
                }
            )


def _check_unconfigured_quotas(data: dict, issues: dict) -> None:
    """P4: flag API sources that have no key configured."""
    main_health = data.get("main_health", {})
    api_quotas = main_health.get("api_quotas", [])
    for quota in api_quotas:
        if not quota.get("configured"):
            issues[P4_INFO].append(
                {
                    "issue": f"{quota['source_name']} not configured",
                    "details": "API key not set",
                    "severity": "info",
                }
            )


# ---------------------------------------------------------------------------
# Main analysis entry-point
# ---------------------------------------------------------------------------

def analyze_health(report_path: str) -> dict:
    """Analyze health report and return categorized issues."""
    with open(report_path) as f:
        data = json.load(f)

    issues = _empty_issues()

    _check_main_service_down(data, issues)
    _check_critical_services(data, issues)
    _check_data_freshness(data, issues)

    sources = data.get("main_health", {}).get("sources", {})
    _check_sources_down(sources, issues)
    _check_high_latency(sources, issues)

    _check_unconfigured_quotas(data, issues)

    return issues


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def print_summary(issues: dict) -> None:
    """Print human-readable summary."""
    total = sum(len(v) for v in issues.values())

    print("\n=== SYSTEM HEALTH SUMMARY ===")
    print(f"Total Issues: {total}")
    print(f"  P0 Critical: {len(issues[P0_CRITICAL])}")
    print(f"  P1 High: {len(issues[P1_HIGH])}")
    print(f"  P2 Medium: {len(issues[P2_MEDIUM])}")
    print(f"  P3 Low: {len(issues[P3_LOW])}")
    print(f"  P4 Info: {len(issues[P4_INFO])}")

    for priority, issue_list in issues.items():
        if issue_list:
            print(f"\n--- {priority.replace('_', ' ').upper()} ---")
            for issue in issue_list:
                print(f"  \u2022 {issue['issue']}")
                print(f"    {issue['details']}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    report_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_REPORT_PATH

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
    if issues[P0_CRITICAL]:
        sys.exit(EXIT_CRITICAL)
    elif issues[P1_HIGH]:
        sys.exit(EXIT_HIGH)
    else:
        sys.exit(EXIT_OK)
