"""Pair a charge with the credit that cancelled it, and net both out.

A reversed payroll deposit posts twice: the deposit on one day, the clawback on
the next. Nothing marks the two as one event, so the deposit lands in income and
the clawback lands in spend, and a month that saw no money at all reports both a
larger paycheque and a larger bill. July 2026 is the reference case -- a
$1,102.23 Pinellas deposit on the 9th and a $1,102.23 "COUNTREVERSAL" debit on
the 10th push July income to $3,857 and July Bills to $1,497 instead of ~$395.

Matching is deliberately strict. Same cents, opposite direction, a few days
apart, and a shared merchant word that is not banking boilerplate -- two
unrelated $50 charges a day apart must not annihilate each other.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any

# A reversal follows its charge closely; anything slower is a refund the household
# negotiated, which is real money moving and already handled as a refund row.
DEFAULT_REVERSAL_WINDOW_DAYS = 5

_INFLOW_FLOWS = {"income", "refund", "transfer_in", "credit", "deposit"}
_OUTFLOW_FLOWS = {"expense", "payment", "transfer_out", "debit", "withdrawal"}

# Words that appear on both sides of nearly every bank line and therefore prove
# nothing about the two rows being the same event.
_BOILERPLATE_TOKENS = frozenset(
    {
        "ach",
        "auto",
        "authorized",
        "bill",
        "card",
        "cash",
        "check",
        "co",
        "com",
        "corp",
        "credit",
        "debit",
        "deposit",
        "direct",
        "electronic",
        "from",
        "inc",
        "llc",
        "mobile",
        "online",
        "payment",
        "pending",
        "pmt",
        "pos",
        "purchase",
        "recurring",
        "refund",
        "return",
        "reversal",
        "reverse",
        "the",
        "transaction",
        "transfer",
        "usa",
        "withdrawal",
        "xfer",
    }
)

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Bank descriptions run words together ("COUPAYROLL", "COUNTREVERSAL"), so a
# shared prefix of this many characters counts as the same word.
_MIN_TOKEN_PREFIX = 5


@dataclass(frozen=True)
class ReversalPair:
    """One charge and the credit that cancelled it."""

    outflow_id: str
    inflow_id: str
    amount: float
    outflow_date: date
    inflow_date: date
    merchant_token: str

    def as_reason(self) -> str:
        first, second = sorted((self.outflow_date, self.inflow_date))
        return (
            f"Reversed: ${self.amount:,.2f} posted {first.isoformat()} and was "
            f"cancelled {second.isoformat()}"
        )


def _tokens(*parts: str | None) -> set[str]:
    words: set[str] = set()
    for part in parts:
        if not isinstance(part, str):
            continue
        for token in _TOKEN_RE.findall(part.lower()):
            if len(token) < 4 or token in _BOILERPLATE_TOKENS or token.isdigit():
                continue
            words.add(token)
    return words


def _shared_token(left: set[str], right: set[str]) -> str | None:
    shared = sorted(left & right, key=lambda token: (len(token), token))
    if shared:
        return shared[0]
    for left_token in sorted(left, key=lambda token: (-len(token), token)):
        if len(left_token) < _MIN_TOKEN_PREFIX:
            continue
        for right_token in sorted(right, key=lambda token: (-len(token), token)):
            if len(right_token) < _MIN_TOKEN_PREFIX:
                continue
            if left_token[:_MIN_TOKEN_PREFIX] == right_token[:_MIN_TOKEN_PREFIX]:
                return left_token[:_MIN_TOKEN_PREFIX]
    return None


def _direction(flow_type: str | None) -> str | None:
    normalized = (flow_type or "").strip().lower()
    if normalized in _INFLOW_FLOWS:
        return "in"
    if normalized in _OUTFLOW_FLOWS:
        return "out"
    return None


def find_reversal_pairs(
    rows: list[dict[str, Any]],
    *,
    window_days: int = DEFAULT_REVERSAL_WINDOW_DAYS,
) -> list[ReversalPair]:
    """Pair same-amount opposite-direction rows that name the same counterparty.

    Each row is used at most once: a genuine double reversal is two pairs, but a
    single credit cannot cancel two separate charges.
    """
    outflows: list[dict[str, Any]] = []
    inflows: list[dict[str, Any]] = []
    for row in rows:
        direction = _direction(row.get("flow_type"))
        if direction is None:
            continue
        amount = row.get("amount")
        try:
            magnitude = abs(float(amount))
        except (TypeError, ValueError):
            continue
        if magnitude <= 0:
            continue
        candidate = {
            "id": str(row.get("id")),
            "date": row.get("date"),
            "cents": round(magnitude * 100),
            "amount": round(magnitude, 2),
            "tokens": _tokens(row.get("merchant"), row.get("description")),
        }
        if not isinstance(candidate["date"], date):
            continue
        (outflows if direction == "out" else inflows).append(candidate)

    inflows_by_cents: dict[int, list[dict[str, Any]]] = {}
    for row in inflows:
        inflows_by_cents.setdefault(row["cents"], []).append(row)

    claimed: set[str] = set()
    pairs: list[ReversalPair] = []
    for outflow in sorted(outflows, key=lambda item: (item["date"], item["id"])):
        candidates = inflows_by_cents.get(outflow["cents"], [])
        best: tuple[int, dict[str, Any], str] | None = None
        for inflow in candidates:
            if inflow["id"] in claimed or inflow["id"] == outflow["id"]:
                continue
            gap = abs((inflow["date"] - outflow["date"]).days)
            if gap > window_days:
                continue
            token = _shared_token(outflow["tokens"], inflow["tokens"])
            if token is None:
                continue
            if best is None or gap < best[0]:
                best = (gap, inflow, token)
        if best is None:
            continue
        _, inflow, token = best
        claimed.add(inflow["id"])
        pairs.append(
            ReversalPair(
                outflow_id=outflow["id"],
                inflow_id=inflow["id"],
                amount=outflow["amount"],
                outflow_date=outflow["date"],
                inflow_date=inflow["date"],
                merchant_token=token,
            )
        )
    return pairs


def reversal_reasons_by_id(pairs: list[ReversalPair]) -> dict[str, str]:
    """Map every paired row id to the sentence that explains its removal."""
    reasons: dict[str, str] = {}
    for pair in pairs:
        reason = pair.as_reason()
        reasons[pair.outflow_id] = reason
        reasons[pair.inflow_id] = reason
    return reasons
