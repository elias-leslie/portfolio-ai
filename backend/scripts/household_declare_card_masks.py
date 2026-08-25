#!/usr/bin/env python3
"""Declare the numbers a card used to carry, so old purchases find their account.

A card that is lost, expiring or reissued comes back with a new last four. Every
export that names the card names the number it carried that day, while the
account registry holds only the current one -- so a purchase made a year ago on
the same account looks like it was made on a card nobody owns.

Card numbers are supplied at the call site, never stored in this file: this
repository is public. They are written to the account's metadata as
``prior_masks``, each with the window it was live for.

Usage:
    cd ~/portfolio-ai/backend
    .venv/bin/python scripts/household_declare_card_masks.py list
    .venv/bin/python scripts/household_declare_card_masks.py set \
        --account-mask <last four now> --prior <last four before> \
        --from <first day it was used> --through <last day it was used> \
        --reason "reissued; export shows no overlap with the next number"
    .venv/bin/python scripts/household_declare_card_masks.py clear \
        --account-mask <last four now>
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.household_card_masks import extract_card_mask
from app.storage import get_storage


def _accounts(conn):
    return conn.execute(
        """
        SELECT id, canonical_label, account_mask, metadata
        FROM household_accounts
        WHERE archived_at IS NULL AND account_mask IS NOT NULL
        ORDER BY canonical_label
        """
    ).fetchall()


def _find(conn, account_mask: str):
    wanted = extract_card_mask(account_mask)
    matches = [row for row in _accounts(conn) if extract_card_mask(row[2]) == wanted]
    if not matches:
        raise SystemExit(f"no live account carries mask {account_mask}")
    if len(matches) > 1:
        raise SystemExit(f"{len(matches)} accounts carry mask {account_mask}; ambiguous")
    return matches[0]


def _write(conn, account_id: str, metadata: dict) -> None:
    conn.execute(
        "UPDATE household_accounts SET metadata = %s::jsonb, updated_at = %s WHERE id = %s",
        [json.dumps(metadata), datetime.now(UTC).isoformat(), account_id],
    )
    conn.commit()


def command_list(conn, _args) -> int:
    for _account_id, label, mask, raw_metadata in _accounts(conn):
        metadata = raw_metadata if isinstance(raw_metadata, dict) else {}
        prior = metadata.get("prior_masks") or []
        current = extract_card_mask(mask)
        if not current and not prior:
            continue
        print(f"{label}  (now ...{current})")
        for entry in prior:
            window = f"{entry.get('from') or '?'} .. {entry.get('through') or '?'}"
            print(f"    ...{entry.get('mask')}   {window}   {entry.get('reason') or ''}")
    return 0


def command_set(conn, args) -> int:
    prior_mask = extract_card_mask(args.prior)
    if not prior_mask:
        raise SystemExit(f"{args.prior!r} does not name a last four")
    account_id, label, mask, metadata = _find(conn, args.account_mask)
    if prior_mask == extract_card_mask(mask):
        raise SystemExit("the prior number is the number the account carries today")
    metadata = dict(metadata) if isinstance(metadata, dict) else {}
    prior = [
        entry
        for entry in (metadata.get("prior_masks") or [])
        if isinstance(entry, dict) and extract_card_mask(entry.get("mask")) != prior_mask
    ]
    prior.append(
        {
            "mask": prior_mask,
            "from": args.date_from.isoformat() if args.date_from else None,
            "through": args.through.isoformat() if args.through else None,
            "reason": args.reason,
            "declared_at": datetime.now(UTC).isoformat(),
        }
    )
    prior.sort(key=lambda entry: entry.get("from") or "")
    metadata["prior_masks"] = prior
    _write(conn, str(account_id), metadata)
    print(f"{label}: ...{prior_mask} declared for {args.date_from} .. {args.through}")
    return 0


def command_clear(conn, args) -> int:
    account_id, label, _mask, metadata = _find(conn, args.account_mask)
    metadata = dict(metadata) if isinstance(metadata, dict) else {}
    if not metadata.pop("prior_masks", None):
        print(f"{label}: nothing declared")
        return 0
    _write(conn, str(account_id), metadata)
    print(f"{label}: prior numbers cleared")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="Show every declared prior number")

    set_cmd = sub.add_parser("set", help="Declare a number an account used to carry")
    set_cmd.add_argument("--account-mask", required=True, help="the account's number today")
    set_cmd.add_argument("--prior", required=True, help="the number it carried before")
    set_cmd.add_argument("--from", dest="date_from", type=date.fromisoformat, required=True)
    set_cmd.add_argument("--through", type=date.fromisoformat, required=True)
    set_cmd.add_argument("--reason", required=True)

    clear_cmd = sub.add_parser("clear", help="Drop every declared prior number for an account")
    clear_cmd.add_argument("--account-mask", required=True)

    args = parser.parse_args()
    handlers = {"list": command_list, "set": command_set, "clear": command_clear}
    with get_storage().connection() as conn:
        return handlers[args.command](conn, args)


if __name__ == "__main__":
    raise SystemExit(main())
