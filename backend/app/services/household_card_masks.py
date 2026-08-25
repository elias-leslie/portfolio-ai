"""Resolve which account paid, when the card number has changed underneath it.

A card that is lost, expiring or reissued comes back with a new last four, and
every export that names the card names the number it carried that day. The
registry holds one mask per account -- the current one -- so a purchase made on
the same account a year ago looks like it was made on a card nobody owns, and an
item bought on it can never find its account.

The succession is data, not code. An account's ``metadata.prior_masks`` carries
the numbers it used to have, each with the window it was live for, declared
through ``scripts/household_declare_card_masks.py``. This repository is public;
card numbers are never written into it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

_MASK_PATTERN = re.compile(r"(?<!\d)(\d{4})(?!\d)")

# Amazon writes "Gift Certificate/Card and Visa - 1234" when points or a gift
# balance covered part of an order. The card still carries the rest, so the
# mask is the one that matters; the gift half never names an account.
_NON_CARD_LABELS = ("gift certificate", "gift card", "not available", "not applicable")


def extract_card_mask(label: object) -> str | None:
    """Last four from a payment label, or None when the label names no card.

    Handles the shapes the household's own sources actually print:
    ``Visa - 1234``, ``Visa Credit ****1234``, ``Chase Visa ending 1234``,
    ``CHASEVISA-1234``.
    """
    text = " ".join(str(label or "").strip().split())
    if not text:
        return None
    lowered = text.lower()
    if lowered in _NON_CARD_LABELS:
        return None
    masks = _MASK_PATTERN.findall(text)
    if not masks:
        return None
    # A label that names both a gift balance and a card names one number.
    return masks[-1]


def _coerce_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()[:10]
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


@dataclass(frozen=True)
class CardEra:
    """One number an account carried, and the window it carried it."""

    account_id: str
    account_label: str
    mask: str
    live_from: date | None
    live_through: date | None
    current: bool

    def covers(self, on_date: date | None) -> bool:
        if self.current and self.live_through is None:
            # The number in the registry is the one in the wallet today.
            return on_date is None or self.live_from is None or on_date >= self.live_from
        if on_date is None:
            return False
        if self.live_from is not None and on_date < self.live_from:
            return False
        return self.live_through is None or on_date <= self.live_through


@dataclass(frozen=True)
class CardMatch:
    account_id: str
    account_label: str
    mask: str
    reissued: bool


class CardMaskDirectory:
    """Every last four the household's accounts have carried, and when."""

    def __init__(self, eras: list[CardEra]) -> None:
        self._by_mask: dict[str, list[CardEra]] = {}
        for era in eras:
            self._by_mask.setdefault(era.mask, []).append(era)

    @classmethod
    def load(cls, conn: Any) -> CardMaskDirectory:
        rows = conn.execute(
            """
            SELECT id, canonical_label, account_mask, metadata
            FROM household_accounts
            WHERE archived_at IS NULL
            """
        ).fetchall()
        eras: list[CardEra] = []
        for row in rows:
            account_id = str(row[0])
            label = str(row[1] or "")
            current_mask = extract_card_mask(row[2])
            if current_mask:
                eras.append(
                    CardEra(
                        account_id=account_id,
                        account_label=label,
                        mask=current_mask,
                        live_from=None,
                        live_through=None,
                        current=True,
                    )
                )
            metadata = row[3] if isinstance(row[3], dict) else {}
            prior = metadata.get("prior_masks")
            if not isinstance(prior, list):
                continue
            for entry in prior:
                if not isinstance(entry, dict):
                    continue
                mask = extract_card_mask(entry.get("mask"))
                if not mask:
                    continue
                eras.append(
                    CardEra(
                        account_id=account_id,
                        account_label=label,
                        mask=mask,
                        live_from=_coerce_date(entry.get("from")),
                        live_through=_coerce_date(entry.get("through")),
                        current=False,
                    )
                )
        return cls(eras)

    def resolve(self, label: object, *, on_date: date | None = None) -> CardMatch | None:
        """The account a payment label names on a given date, or None.

        Ambiguity is not resolved by guessing: when two accounts claim the same
        four digits for the same day, nothing is returned.
        """
        mask = extract_card_mask(label)
        if not mask:
            return None
        candidates = [era for era in self._by_mask.get(mask, ()) if era.covers(on_date)]
        if not candidates:
            return None
        accounts = {era.account_id for era in candidates}
        if len(accounts) > 1:
            return None
        # A declared era outranks the registry's current mask: a number that was
        # reissued away is still the right answer for the days it was live.
        era = min(candidates, key=lambda item: (item.current, item.mask))
        return CardMatch(
            account_id=era.account_id,
            account_label=era.account_label,
            mask=mask,
            reissued=not era.current,
        )

    def explain(self, label: object, *, on_date: date | None = None) -> str:
        """Why a payment label did or did not name an account.

        A number the registry has never seen and a number that was already
        retired by the purchase date are different problems: the first is a card
        the household has not told us about, the second is a succession that
        needs one more entry.
        """
        mask = extract_card_mask(label)
        if not mask:
            return "no_card_named"
        eras = self._by_mask.get(mask, ())
        if not eras:
            return "unknown_card"
        covering = [era for era in eras if era.covers(on_date)]
        if not covering:
            return "outside_card_window"
        if len({era.account_id for era in covering}) > 1:
            return "ambiguous_card"
        return "resolved"

    def knows_mask(self, label: object) -> bool:
        mask = extract_card_mask(label)
        return bool(mask and mask in self._by_mask)
