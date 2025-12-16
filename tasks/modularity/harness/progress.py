"""
Progress Tracking Utilities
===========================

Functions for tracking and displaying verification progress.
"""

import json
from pathlib import Path


def count_verified_items(project_dir: Path) -> tuple[int, int]:
    """
    Count verified and total items in verification_list.json.

    Args:
        project_dir: Directory containing verification_list.json

    Returns:
        (verified_count, total_count)
    """
    verification_file = project_dir / "verification_list.json"

    if not verification_file.exists():
        return 0, 0

    try:
        with open(verification_file, "r") as f:
            data = json.load(f)

        items = data.get("items", [])
        total = len(items)
        verified = sum(1 for item in items if item.get("status") == "verified")

        return verified, total
    except (json.JSONDecodeError, IOError):
        return 0, 0


def get_next_pending_item(project_dir: Path) -> dict | None:
    """
    Get the next pending verification item.

    Args:
        project_dir: Directory containing verification_list.json

    Returns:
        The next pending item dict, or None if all complete
    """
    verification_file = project_dir / "verification_list.json"

    if not verification_file.exists():
        return None

    try:
        with open(verification_file, "r") as f:
            data = json.load(f)

        items = data.get("items", [])
        for item in items:
            if item.get("status") == "pending":
                return item

        return None
    except (json.JSONDecodeError, IOError):
        return None


def print_session_header(session_num: int, is_initializer: bool) -> None:
    """Print a formatted header for the session."""
    session_type = "INITIALIZER" if is_initializer else "VERIFICATION AGENT"

    print("\n" + "=" * 70)
    print(f"  SESSION {session_num}: {session_type}")
    print("=" * 70)
    print()


def print_progress_summary(project_dir: Path) -> None:
    """Print a summary of current verification progress."""
    verified, total = count_verified_items(project_dir)

    if total > 0:
        percentage = (verified / total) * 100
        print(f"\nProgress: {verified}/{total} items verified ({percentage:.1f}%)")

        # Show categories breakdown
        verification_file = project_dir / "verification_list.json"
        if verification_file.exists():
            try:
                with open(verification_file, "r") as f:
                    data = json.load(f)

                items = data.get("items", [])
                categories = {}
                for item in items:
                    cat = item.get("category", "unknown")
                    if cat not in categories:
                        categories[cat] = {"verified": 0, "total": 0}
                    categories[cat]["total"] += 1
                    if item.get("status") == "verified":
                        categories[cat]["verified"] += 1

                print("\nBy category:")
                for cat, counts in sorted(categories.items()):
                    v, t = counts["verified"], counts["total"]
                    status = "DONE" if v == t else f"{v}/{t}"
                    print(f"  {cat}: {status}")

            except (json.JSONDecodeError, IOError):
                pass
    else:
        print("\nProgress: verification_list.json not yet created")


def update_item_status(
    project_dir: Path,
    item_id: str,
    status: str,
    evidence: str | None = None,
    notes: str | None = None,
    correction: str | None = None,
) -> bool:
    """
    Update the status of a verification item.

    Args:
        project_dir: Directory containing verification_list.json
        item_id: ID of the item to update
        status: New status ("pending", "verified", "needs_correction")
        evidence: Evidence supporting the verification
        notes: Additional notes
        correction: Correction if original was wrong

    Returns:
        True if update successful, False otherwise
    """
    verification_file = project_dir / "verification_list.json"

    if not verification_file.exists():
        return False

    try:
        with open(verification_file, "r") as f:
            data = json.load(f)

        items = data.get("items", [])
        for item in items:
            if item.get("id") == item_id:
                item["status"] = status
                if evidence:
                    item["evidence"] = evidence
                if notes:
                    item["notes"] = notes
                if correction:
                    item["correction"] = correction
                break

        with open(verification_file, "w") as f:
            json.dump(data, f, indent=2)

        return True
    except (json.JSONDecodeError, IOError):
        return False
