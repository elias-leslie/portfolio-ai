#!/usr/bin/env python3
"""Declare how often a merchant bills, when the feed cannot show it.

Cadence is normally inferred from two or more sightings. An annual obligation
cannot clear that bar inside six months of card coverage, so a bill the
household pays once a year is invisible to the recurring detector and drags the
matching sinking fund's monthly target down by a twelfth of itself.

Merchant names and reasons are supplied at the call site, never stored in this
file -- this repository is public.

Usage:
    cd ~/portfolio-ai/backend
    .venv/bin/python scripts/household_declare_cadence.py list
    .venv/bin/python scripts/household_declare_cadence.py set \
        --merchant "Some Association" --cadence annual \
        --reason "household states this is billed once a year"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.household_transaction_service import HouseholdTransactionService

CADENCES = ("weekly", "biweekly", "monthly", "quarterly", "annual")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="Show every declared cadence")

    set_cmd = sub.add_parser("set", help="Declare a merchant's cadence")
    set_cmd.add_argument("--merchant", required=True)
    set_cmd.add_argument("--cadence", required=True, choices=CADENCES)
    set_cmd.add_argument("--reason", default=None)

    args = parser.parse_args()
    service = HouseholdTransactionService()

    if args.command == "list":
        with service.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT canonical_name,
                       metadata -> 'cadence_override' ->> 'label',
                       metadata -> 'cadence_override' ->> 'reason'
                FROM household_merchants
                WHERE jsonb_exists(COALESCE(metadata, '{}'::jsonb), 'cadence_override')
                ORDER BY canonical_name
                """
            ).fetchall()
        if not rows:
            print("no declared cadences")
        for row in rows:
            print(f"{row[0]:<40} {row[1]:<10} {row[2] or ''}")
        return 0

    print(
        service.set_merchant_cadence(
            merchant=args.merchant,
            label=args.cadence,
            reason=args.reason,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
