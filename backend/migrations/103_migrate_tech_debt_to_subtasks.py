#!/usr/bin/env python3
"""Migration: Convert tech debt insights to feature subtasks.

This migration converts the separate tech debt system (capability_insights)
into [DEBT] prefixed subtasks on existing features, consolidating work
tracking into a single source of truth.

Mapping Strategy:
- Feature-specific debt → Subtask on owning feature
- Cross-cutting debt → New FEAT-DEBT-XXX feature
- Already fixed/dismissed → Skip

Run: cd ~/portfolio-ai/backend && .venv/bin/python migrations/103_migrate_tech_debt_to_subtasks.py
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

BASE_URL = "http://localhost:8000/api/capabilities"

# Mapping of tech debt items to features based on analysis
# Format: insight_id -> feature_id
DEBT_TO_FEATURE_MAPPING: dict[int, str | None] = {
    # financial_health_scores - maps to Piotroski F-Score feature
    298: "FEAT-GAP-008",  # financial_health_scores table empty
    249: "FEAT-GAP-008",  # financial_health_scores task never run
    243: "FEAT-GAP-008",  # financial_health_scores missing capability
    # Backtesting issues - maps to Backtest Runs List
    322: "FEAT-067",  # backtest_runs stale, no scheduled task
    285: "FEAT-067",  # backtesting data stale
    286: "FEAT-067",  # DELETE endpoint wrong dependencies
    # Portfolio - maps to Accounts with Positions
    276: "FEAT-048",  # portfolio account API stale data
    # Reference cache - maps to Valuation Ratios
    244: "FEAT-GAP-002",  # reference_cache 52% complete
    # User preferences - maps to Profile Management
    250: "FEAT-104",  # user_preferences 28 days stale
    # Strategy evolution - maps to Strategy Generation
    295: "FEAT-062",  # weekly-strategy-evolution never executed
    # Cross-cutting (no direct feature match) - will create FEAT-DEBT
    332: None,  # ingest-fundamental-data-weekly 75% success rate
    333: None,  # price_cache 58% complete, missing bid/ask
}

# Severity to effort mapping
SEVERITY_TO_EFFORT = {
    "critical": "high",
    "high": "medium",
    "medium": "low",
    "low": "low",
}


def get_pending_insights() -> list[dict[str, Any]]:
    """Fetch all pending tech debt insights."""
    resp = requests.get(f"{BASE_URL}/insights?limit=200", timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return [i for i in data.get("insights", []) if i["status"] == "pending"]


def get_feature(feature_id: str) -> dict[str, Any] | None:
    """Fetch a feature by ID."""
    resp = requests.get(f"{BASE_URL}/features/{feature_id}", timeout=30)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def create_debt_feature(insight: dict[str, Any], debt_id: str) -> dict[str, Any]:
    """Create a new FEAT-DEBT-XXX feature for cross-cutting debt."""
    feature_data = {
        "feature_id": f"FEAT-DEBT-{debt_id}",
        "name": f"[DEBT] {insight['finding'][:50]}",
        "category": "Tech Debt",
        "description": insight["finding"],
        "status": "pending",
        "effort": SEVERITY_TO_EFFORT.get(insight["severity"], "medium"),
        "source": "tech_debt",
    }
    resp = requests.post(f"{BASE_URL}/features/", json=feature_data, timeout=30)
    resp.raise_for_status()
    return resp.json()


def create_debt_subtask(
    feature_id: str,
    insight: dict[str, Any],
    db_feature_id: int | None = None,
) -> dict[str, Any]:
    """Create a [DEBT] subtask on an existing feature."""
    task_data = {
        "task_id": f"DEBT-{insight['id']}",
        "description": f"[DEBT] {insight['finding'][:100]}",
        "notes": (
            f"Severity: {insight['severity']}\n"
            f"Suggested fix: {insight['suggested_fix']}\n"
            f"Source: insight #{insight['id']}"
        ),
        "effort": SEVERITY_TO_EFFORT.get(insight["severity"], "medium"),
    }

    # Use db_feature_id if provided (for new FEAT-DEBT features), otherwise feature_id
    url = f"{BASE_URL}/features/{feature_id}/tasks"
    resp = requests.post(url, json=task_data, timeout=30)
    resp.raise_for_status()
    return resp.json()


def mark_insight_migrated(insight_id: int, feature_id: str) -> None:
    """Mark an insight as fixed/migrated."""
    review_data = {
        "status": "fixed",
        "status_reason": f"Migrated to feature {feature_id}",
        "reviewed_by": "migration_103",
    }
    resp = requests.post(
        f"{BASE_URL}/insights/{insight_id}/review",
        json=review_data,
        timeout=30,
    )
    resp.raise_for_status()


def migrate_insights() -> dict[str, int]:
    """Main migration function."""
    stats = {
        "total_pending": 0,
        "migrated_to_subtasks": 0,
        "created_debt_features": 0,
        "skipped_duplicates": 0,
        "errors": 0,
    }

    insights = get_pending_insights()
    stats["total_pending"] = len(insights)
    print(f"Found {len(insights)} pending tech debt insights")

    # Track created DEBT features to avoid duplicates
    debt_feature_counter = 1
    created_debt_features: dict[str, str] = {}  # table_name -> feature_id

    for insight in insights:
        insight_id = insight["id"]
        table_name = insight.get("table_name", "unknown")

        print(f"\nProcessing insight #{insight_id}: {table_name}")

        try:
            # Check if we have a mapping
            mapped_feature = DEBT_TO_FEATURE_MAPPING.get(insight_id)

            if mapped_feature:
                # Create subtask on existing feature
                feature = get_feature(mapped_feature)
                if feature:
                    print(f"  -> Creating subtask on {mapped_feature}")
                    create_debt_subtask(mapped_feature, insight)
                    mark_insight_migrated(insight_id, mapped_feature)
                    stats["migrated_to_subtasks"] += 1
                else:
                    print(f"  -> ERROR: Feature {mapped_feature} not found")
                    stats["errors"] += 1
            # Cross-cutting - check if we already created a DEBT feature for this table
            elif table_name in created_debt_features:
                feature_id = created_debt_features[table_name]
                print(f"  -> Adding to existing debt feature {feature_id}")
                create_debt_subtask(feature_id, insight)
                mark_insight_migrated(insight_id, feature_id)
                stats["skipped_duplicates"] += 1
            else:
                # Create new FEAT-DEBT feature
                debt_id = str(debt_feature_counter).zfill(3)
                print(f"  -> Creating FEAT-DEBT-{debt_id}")
                new_feature = create_debt_feature(insight, debt_id)
                feature_id = new_feature.get("feature_id", f"FEAT-DEBT-{debt_id}")
                created_debt_features[table_name] = feature_id
                debt_feature_counter += 1
                mark_insight_migrated(insight_id, feature_id)
                stats["created_debt_features"] += 1

        except requests.RequestException as e:
            print(f"  -> ERROR: {e}")
            stats["errors"] += 1

    return stats


def main() -> None:
    """Run the migration."""
    print("=" * 60)
    print("Tech Debt to Feature Subtasks Migration")
    print("=" * 60)
    print(f"Started at: {datetime.now().isoformat()}")
    print()

    try:
        stats = migrate_insights()
    except requests.RequestException as e:
        print(f"\nFATAL ERROR: Could not connect to API: {e}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("Migration Complete")
    print("=" * 60)
    print(f"Total pending insights: {stats['total_pending']}")
    print(f"Migrated to subtasks:   {stats['migrated_to_subtasks']}")
    print(f"Created DEBT features:  {stats['created_debt_features']}")
    print(f"Added to existing DEBT: {stats['skipped_duplicates']}")
    print(f"Errors:                 {stats['errors']}")
    print(f"\nFinished at: {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
