#!/usr/bin/env python3
"""Operator CLI for the household account registry.

The registry self-heals for identities its heuristics can recognise: a mask, a
name, an institution. It cannot resolve the ones only a person knows -- that two
labels are one closed account, that a balance moved between institutions and
kept nothing in common, that a row is leftover test data. This exposes those
decisions as explicit commands.

Nothing household-specific lives in this file. Targets are named by id at the
call site, which keeps account identifiers out of version control while leaving
the capability reusable.

Usage:
    cd ~/portfolio-ai/backend
    .venv/bin/python scripts/household_registry_admin.py list
    .venv/bin/python scripts/household_registry_admin.py list --archived
    .venv/bin/python scripts/household_registry_admin.py feed-status <id> closed
    .venv/bin/python scripts/household_registry_admin.py archive <id> --reason test_fixture
    .venv/bin/python scripts/household_registry_admin.py merge --winner <id> --loser <id>
    .venv/bin/python scripts/household_registry_admin.py restore <id>
    .venv/bin/python scripts/household_registry_admin.py refresh-coverage
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.household_account_registry_service import HouseholdAccountRegistryService
from app.services.household_finance_service import HouseholdFinanceService

_LIST_SQL = """
    SELECT a.id,
           a.canonical_label,
           a.institution_name,
           a.account_type,
           a.asset_group,
           a.feed_status,
           a.coverage_through,
           a.archive_reason,
           a.merged_into_account_id,
           (SELECT count(*) FROM household_transactions t
             WHERE t.household_account_id = a.id) AS txns,
           (SELECT count(*) FROM household_evidence_accounts e
             WHERE e.household_account_id = a.id) AS evidence
    FROM household_accounts AS a
    WHERE (%s OR a.archived_at IS NULL)
    ORDER BY a.feed_status, a.institution_name NULLS LAST, a.canonical_label
"""


def _list_accounts(service: HouseholdFinanceService, *, include_archived: bool) -> None:
    with service.storage.connection() as conn:
        rows = conn.execute(_LIST_SQL, [include_archived]).fetchall()
    header = f"{'id':38} {'status':9} {'through':11} {'txns':>5} {'evid':>5}  label"
    print(header)
    print("-" * len(header))
    for row in rows:
        (
            account_id,
            label,
            institution,
            _account_type,
            _asset_group,
            feed_status,
            coverage_through,
            archive_reason,
            merged_into,
            txns,
            evidence,
        ) = row
        name = f"{institution or '?'} / {label or '?'}"
        suffix = ""
        if archive_reason:
            suffix = f"  [archived: {archive_reason}]"
        if merged_into:
            suffix += f"  [merged into {merged_into}]"
        through = str(coverage_through) if coverage_through else "-"
        print(
            f"{account_id!s:38} {feed_status:9} {through:11} {txns:>5} {evidence:>5}  {name}{suffix}"
        )
    print(f"\n{len(rows)} account(s)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    list_cmd = sub.add_parser("list", help="Show registry rows with lifecycle state")
    list_cmd.add_argument(
        "--archived", action="store_true", help="Include archived rows in the listing"
    )

    archive_cmd = sub.add_parser("archive", help="Retire a row without deleting it")
    archive_cmd.add_argument("account_id")
    archive_cmd.add_argument(
        "--reason",
        required=True,
        choices=sorted(HouseholdAccountRegistryService.ARCHIVE_REASONS),
    )
    archive_cmd.add_argument(
        "--merged-into",
        default=None,
        help="Account this one was superseded by, when applicable",
    )

    restore_cmd = sub.add_parser("restore", help="Undo an archive")
    restore_cmd.add_argument("account_id")

    status_cmd = sub.add_parser("feed-status", help="Declare whether an account still reports")
    status_cmd.add_argument("account_id")
    status_cmd.add_argument(
        "feed_status", choices=sorted(HouseholdAccountRegistryService.FEED_STATUSES)
    )
    status_cmd.add_argument("--coverage-through", default=None, help="ISO date, optional")

    merge_cmd = sub.add_parser("merge", help="Repoint one row's data onto another, then drop it")
    merge_cmd.add_argument("--winner", required=True)
    merge_cmd.add_argument("--loser", required=True)

    classify_cmd = sub.add_parser(
        "classify", help="Pin asset group / account type against provider re-classification"
    )
    classify_cmd.add_argument("account_id")
    classify_cmd.add_argument("--asset-group", default=None)
    classify_cmd.add_argument("--account-type", default=None)
    classify_cmd.add_argument("--reason", default=None)

    sub.add_parser("refresh-coverage", help="Recompute coverage and status from transactions")

    args = parser.parse_args()
    service = HouseholdFinanceService()
    registry = service.account_registry_service

    handlers = {
        "list": lambda: _list_accounts(service, include_archived=args.archived),
        "archive": lambda: registry.archive_account(
            service,
            account_id=args.account_id,
            reason=args.reason,
            merged_into_account_id=args.merged_into,
        ),
        "restore": lambda: registry.restore_account(service, account_id=args.account_id),
        "feed-status": lambda: registry.set_feed_status(
            service,
            account_id=args.account_id,
            feed_status=args.feed_status,
            coverage_through=args.coverage_through,
        ),
        "classify": lambda: registry.set_account_classification(
            service,
            account_id=args.account_id,
            asset_group=args.asset_group,
            account_type=args.account_type,
            reason=args.reason,
        ),
        "merge": lambda: registry.merge_accounts(
            service, winner_id=args.winner, loser_id=args.loser
        ),
        "refresh-coverage": lambda: registry.refresh_coverage(service),
    }
    result = handlers[args.command]()
    if result is not None:
        print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
