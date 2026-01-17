#!/usr/bin/env python3
"""Migration 102: Migrate Trading Requirements to Features.

This script converts all 47 trading requirements from trading_requirements.yaml
into features in the feature_capabilities table, creating a single source of truth.

Mapping:
- gap_id → feature_id (e.g., GAP-003 → FEAT-GAP-003)
- capability → name
- desired_state → description
- criticality (P0-P3) → priority (1-5)
- effort → effort
- analysis_type → category (e.g., "Data - Technical")
- data_sources → implementation_notes.data_sources
- current_state + desired_state → acceptance_criteria
- analysis_type → vision_goals

Run with: python backend/migrations/102_migrate_trading_reqs_to_features.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

# Add backend to path for imports
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from app.storage.connection import get_connection_manager  # noqa: E402

# Analysis type to vision goal mapping
ANALYSIS_TYPE_TO_VISION_GOALS = {
    "technical_analysis": ["VG-INTEL"],
    "fundamental_analysis": ["VG-INTEL"],
    "sentiment_analysis": ["VG-INTEL"],
    "risk_analysis": ["VG-VALID", "VG-RELY"],
    "execution_quality": ["VG-RELY"],
    "macro_analysis": ["VG-INTEL"],
    "ml_infrastructure": ["VG-AUTO", "VG-RELY"],
    "compliance": ["VG-RELY"],
}

# Analysis type to category mapping
ANALYSIS_TYPE_TO_CATEGORY = {
    "technical_analysis": "Data - Technical",
    "fundamental_analysis": "Data - Fundamental",
    "sentiment_analysis": "Data - Sentiment",
    "risk_analysis": "Data - Risk",
    "execution_quality": "Data - Execution",
    "macro_analysis": "Data - Macro",
    "ml_infrastructure": "Data - ML",
    "compliance": "Data - Compliance",
}

# Criticality to priority mapping (P0 = highest priority = 1)
CRITICALITY_TO_PRIORITY = {
    "P0": 1,
    "P1": 2,
    "P2": 3,
    "P3": 4,
}


def load_trading_requirements() -> dict:
    """Load trading requirements from YAML file."""
    yaml_path = backend_path / "app" / "config" / "trading_requirements.yaml"
    with yaml_path.open() as f:
        return yaml.safe_load(f)


def generate_acceptance_criteria(req: dict) -> list[dict]:
    """Generate acceptance criteria from requirement current/desired state."""
    criteria = []
    criterion_num = 1

    # Main criterion: desired state achieved
    desired = req.get("desired_state", "")
    if desired:
        criteria.append(
            {
                "id": f"ac-{criterion_num:03d}",
                "criterion": desired,
                "verification": "Check database tables and data coverage",
                "type": "db",
                "passed": None,
            }
        )
        criterion_num += 1

    # Tables exist criterion
    tables = req.get("tables", [])
    for table in tables:
        if "(new table)" in table or table.endswith("(extend)"):
            table_name = table.replace(" (new table)", "").replace(" (extend)", "").strip()
            criteria.append(
                {
                    "id": f"ac-{criterion_num:03d}",
                    "criterion": f"Table {table_name} exists and is populated",
                    "verification": f"SELECT COUNT(*) FROM {table_name}",
                    "type": "db",
                    "passed": None,
                }
            )
            criterion_num += 1

    # Coverage requirement criterion
    coverage_req = req.get("coverage_requirement", "")
    if coverage_req:
        criteria.append(
            {
                "id": f"ac-{criterion_num:03d}",
                "criterion": f"Coverage: {coverage_req}",
                "verification": "Query data coverage percentage for watchlist",
                "type": "db",
                "passed": None,
            }
        )
        criterion_num += 1

    # Freshness requirement criterion
    freshness_req = req.get("freshness_requirement", "")
    if freshness_req:
        criteria.append(
            {
                "id": f"ac-{criterion_num:03d}",
                "criterion": f"Data freshness: {freshness_req}",
                "verification": "Check max(updated_at) against threshold",
                "type": "backend",
                "passed": None,
            }
        )
        criterion_num += 1

    return criteria


def convert_requirement_to_feature(
    gap_id: str,
    req: dict,
    analysis_type: str,
    requirement_level: str,  # required, recommended, optional
) -> dict:
    """Convert a single requirement to a feature dict."""
    # Determine if this requirement is implemented based on status field
    status_field = req.get("status", "")
    is_implemented = "IMPLEMENTED" in status_field

    # Map criticality to priority
    criticality = req.get("criticality", "P2")
    priority = CRITICALITY_TO_PRIORITY.get(criticality, 3)

    # Determine effort
    effort = req.get("effort", "MEDIUM")
    effort_map = {"LOW": "low", "MEDIUM": "medium", "HIGH": "high"}
    effort_normalized = effort_map.get(effort.upper(), "medium")

    # Build implementation notes
    implementation_notes = {
        "original_gap_id": gap_id,
        "analysis_type": analysis_type,
        "requirement_level": requirement_level,
        "data_sources": req.get("data_sources", []),
        "tables": req.get("tables", []),
        "current_state": req.get("current_state", ""),
        "context": req.get("why", ""),
    }

    # Get vision goals based on analysis type
    vision_goals = ANALYSIS_TYPE_TO_VISION_GOALS.get(analysis_type, ["VG-INTEL"])

    # Get category based on analysis type
    category = ANALYSIS_TYPE_TO_CATEGORY.get(analysis_type, "Data")

    # Generate acceptance criteria
    acceptance_criteria = generate_acceptance_criteria(req)

    # Build feature
    feature = {
        "feature_id": f"FEAT-{gap_id}",
        "name": req.get("capability", "Unknown").replace("_", " ").title(),
        "category": category,
        "description": req.get("desired_state", ""),
        "priority": priority,
        "effort": effort_normalized,
        "source": "trading_requirement",
        "status": "complete" if is_implemented else "pending",
        "passes": True if is_implemented else None,
        "vision_goals": vision_goals,
        "acceptance_criteria": acceptance_criteria,
        "implementation_notes": implementation_notes,
        "health_status": "active",
    }

    return feature


def extract_all_requirements(data: dict) -> list[dict]:
    """Extract all requirements from the trading_requirements.yaml structure."""
    features = []
    analysis_types = data.get("analysis_types", {})

    for analysis_type, analysis_data in analysis_types.items():
        if not analysis_data:
            continue

        # Process required capabilities
        for req in analysis_data.get("required", []) or []:
            gap_id = req.get("gap_id", "")
            if gap_id:
                feature = convert_requirement_to_feature(gap_id, req, analysis_type, "required")
                features.append(feature)

        # Process recommended capabilities
        for req in analysis_data.get("recommended", []) or []:
            gap_id = req.get("gap_id", "")
            if gap_id:
                feature = convert_requirement_to_feature(gap_id, req, analysis_type, "recommended")
                features.append(feature)

        # Process optional capabilities
        for req in analysis_data.get("optional", []) or []:
            gap_id = req.get("gap_id", "")
            if gap_id:
                feature = convert_requirement_to_feature(gap_id, req, analysis_type, "optional")
                features.append(feature)

    return features


def insert_feature(conn, feature: dict) -> bool:
    """Insert a feature into the database."""
    try:
        # Check if feature already exists
        existing = conn.execute(
            "SELECT feature_id FROM feature_capabilities WHERE feature_id = %s",
            (feature["feature_id"],),
        ).fetchone()

        if existing:
            print(f"  Feature {feature['feature_id']} already exists, skipping...")
            return False

        # Insert feature
        conn.execute(
            """
            INSERT INTO feature_capabilities (
                feature_id, name, category, description, priority, effort,
                source, status, passes, vision_goals, acceptance_criteria,
                implementation_notes, health_status, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, NOW(), NOW()
            )
            """,
            (
                feature["feature_id"],
                feature["name"],
                feature["category"],
                feature["description"],
                feature["priority"],
                feature["effort"],
                feature["source"],
                feature["status"],
                feature["passes"],
                feature["vision_goals"],
                json.dumps(feature["acceptance_criteria"]),
                json.dumps(feature["implementation_notes"]),
                feature["health_status"],
            ),
        )
        return True
    except Exception as e:
        print(f"  Error inserting {feature['feature_id']}: {e}")
        return False


def main():
    """Run the migration."""
    print("=" * 60)
    print("Migration 102: Trading Requirements → Features")
    print("=" * 60)

    # Load trading requirements
    print("\n1. Loading trading_requirements.yaml...")
    data = load_trading_requirements()
    metadata = data.get("metadata", {})
    print(f"   Total gaps in YAML: {metadata.get('total_gaps', 'unknown')}")

    # Extract all requirements
    print("\n2. Extracting requirements...")
    features = extract_all_requirements(data)
    print(f"   Extracted {len(features)} requirements")

    # Group by category for display
    by_category = {}
    for f in features:
        cat = f["category"]
        by_category.setdefault(cat, []).append(f)

    for cat, items in sorted(by_category.items()):
        print(f"   - {cat}: {len(items)} features")

    # Connect to database and insert
    print("\n3. Inserting features into database...")
    conn_mgr = get_connection_manager()

    inserted = 0
    skipped = 0

    with conn_mgr.connection() as conn:
        for feature in features:
            if insert_feature(conn, feature):
                print(f"   ✓ Created {feature['feature_id']}: {feature['name']}")
                inserted += 1
            else:
                skipped += 1

        conn.commit()

    print("\n4. Migration complete!")
    print(f"   - Inserted: {inserted}")
    print(f"   - Skipped (already exist): {skipped}")
    print(f"   - Total: {inserted + skipped}")

    # Verify
    print("\n5. Verifying migration...")
    with conn_mgr.connection() as conn:
        result = conn.execute(
            "SELECT COUNT(*) FROM feature_capabilities WHERE source = 'trading_requirement'"
        ).fetchone()
        count = result[0] if result else 0
        print(f"   Features with source='trading_requirement': {count}")

        # Show by category
        cat_result = conn.execute(
            """
            SELECT category, COUNT(*)
            FROM feature_capabilities
            WHERE source = 'trading_requirement'
            GROUP BY category
            ORDER BY category
            """
        ).fetchall()
        for row in cat_result:
            print(f"   - {row[0]}: {row[1]}")

    print("\n" + "=" * 60)
    print("Migration complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
