#!/usr/bin/env python3
"""Seed or inspect obligations that predate every automated feed.

An annual bill paid before the feeds began is invisible to the app and drags the
matching sinking fund's monthly target down by a twelfth of itself. Recording it
by hand is the only way to make the average honest.

Amounts and dates are supplied at the call site, never stored in this file --
this repository is public.

Usage:
    cd ~/portfolio-ai/backend
    .venv/bin/python scripts/household_seed_obligation.py list
    .venv/bin/python scripts/household_seed_obligation.py add \
        --description "Pinellas County property tax" \
        --amount 2144.48 --paid-on 2025-11-25 --category Bills
    .venv/bin/python scripts/household_seed_obligation.py remove <transaction-id>
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.household_finance_service import HouseholdFinanceService
from app.services.household_known_obligation_service import HouseholdKnownObligationService


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="Show every hand-seeded obligation")

    add_cmd = sub.add_parser("add", help="Record a known past payment")
    add_cmd.add_argument("--description", required=True)
    add_cmd.add_argument("--amount", type=float, required=True)
    add_cmd.add_argument("--paid-on", required=True, help="ISO date the payment was made")
    add_cmd.add_argument("--category", required=True)
    add_cmd.add_argument("--essentiality", default="essential")
    add_cmd.add_argument("--merchant", default=None)
    add_cmd.add_argument("--note", default=None)

    remove_cmd = sub.add_parser("remove", help="Retract a seeded obligation")
    remove_cmd.add_argument("transaction_id")

    args = parser.parse_args()
    service = HouseholdFinanceService()
    obligations = HouseholdKnownObligationService()

    if args.command == "list":
        rows = obligations.list_obligations(service)
        if not rows:
            print("no seeded obligations")
        for row in rows:
            state = " (removed)" if row["removed"] else ""
            print(
                f"{row['id']}  {row['paid_on']}  {row['amount']:>10,.2f}  "
                f"{row['category']:<12}  {row['description']}{state}"
            )
        return 0

    if args.command == "add":
        print(
            obligations.seed_obligation(
                service,
                description=args.description,
                amount=args.amount,
                paid_on=date.fromisoformat(args.paid_on),
                category=args.category,
                essentiality=args.essentiality,
                merchant=args.merchant,
                note=args.note,
            )
        )
        return 0

    print(obligations.remove_obligation(service, transaction_id=args.transaction_id))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
