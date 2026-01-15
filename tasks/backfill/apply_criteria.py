#!/usr/bin/env python3
"""Apply acceptance criteria to features via API."""

import json
import sys
from pathlib import Path

import requests

API_BASE = "http://localhost:8000/api/capabilities/features"


def load_criteria():
    """Load criteria from JSON file."""
    criteria_file = Path(__file__).parent / "generated-criteria.json"
    with open(criteria_file) as f:
        return json.load(f)


def get_features():
    """Get all features from API - keyed by numeric id."""
    resp = requests.get(f"{API_BASE}/?limit=200")
    resp.raise_for_status()
    # Return dict keyed by numeric id, with feature_id (FEAT-XXX) stored in each entry
    return {str(f["id"]): f for f in resp.json()["features"]}


def update_feature(feature_id: str, data: dict):
    """Update feature acceptance criteria via API.

    Args:
        feature_id: The FEAT-XXX format ID
        data: Dict with acceptance_criteria and optional vision_goals
    """
    # Update acceptance criteria
    payload = {"acceptance_criteria": data["acceptance_criteria"]}
    resp = requests.patch(f"{API_BASE}/{feature_id}/acceptance-criteria", json=payload)
    if resp.status_code != 200:
        print(f"  ERROR (criteria): {resp.status_code} - {resp.text[:200]}")
        return False

    # Update vision goals if present
    if data.get("vision_goals"):
        vg_payload = {"vision_goals": data["vision_goals"]}
        resp2 = requests.patch(f"{API_BASE}/{feature_id}/vision-goals", json=vg_payload)
        if resp2.status_code != 200:
            print(f"  WARN (vision_goals): {resp2.status_code} - {resp2.text[:100]}")

    return True


def main():
    """Apply all criteria to features."""
    criteria = load_criteria()
    features = get_features()

    print(f"Loaded {len(criteria)} criteria definitions")
    print(f"Found {len(features)} features in database")

    updated = 0
    skipped = 0
    errors = 0

    for numeric_id, data in criteria.items():
        if numeric_id not in features:
            print(f"  SKIP: Feature {numeric_id} not found in database")
            skipped += 1
            continue

        feature = features[numeric_id]
        existing = feature.get("acceptance_criteria", [])
        feat_id = feature["feature_id"]  # FEAT-XXX format

        if existing and len(existing) > 0:
            print(f"  SKIP: {feat_id} ({feature['name']}) already has {len(existing)} criteria")
            skipped += 1
            continue

        print(f"  UPDATE: {feat_id} ({feature['name']}) - adding {len(data['acceptance_criteria'])} criteria")
        if update_feature(feat_id, data):
            updated += 1
        else:
            errors += 1

    print("\nSummary:")
    print(f"  Updated: {updated}")
    print(f"  Skipped: {skipped}")
    print(f"  Errors: {errors}")

    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
