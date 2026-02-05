#!/usr/bin/env python3
"""Fix features with empty/broken acceptance criteria."""

import json
from pathlib import Path

import requests

API_BASE = "http://localhost:8000/api/capabilities/features"


def main():
    """Apply fixed criteria to broken features."""
    fix_file = Path(__file__).parent / "fix-broken-criteria.json"
    with open(fix_file) as f:
        fixes = json.load(f)

    print(f"Fixing {len(fixes)} features with broken criteria...")

    for feature_id, data in fixes.items():
        payload = {"acceptance_criteria": data["acceptance_criteria"]}
        resp = requests.patch(
            f"{API_BASE}/{feature_id}/acceptance-criteria", json=payload
        )
        if resp.status_code == 200:
            print(f"  ✓ {feature_id}")
        else:
            print(f"  ✗ {feature_id}: {resp.status_code} - {resp.text[:100]}")

    print("\nDone!")


if __name__ == "__main__":
    main()
