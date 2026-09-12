"""Persistent bill preferences, independent of any individual card plan."""
from __future__ import annotations

from typing import Any

from app.models.card_strategy import BillPaymentPreference, BillSuggestion

_PREFIX = "card_bill_payment_preference:"


class CardBillPreferences:
    def __init__(self, storage: Any):
        self.storage = storage

    def apply(self, bills: list[BillSuggestion], conn: Any = None) -> None:
        if not bills:
            return
        if conn is None:
            with self.storage.connection() as connection:
                self.apply(bills, connection)
            return
        facts = dict(conn.execute(
            "SELECT fact_key,fact_value FROM household_confirmed_facts WHERE fact_key = ANY(%s)",
            [[_PREFIX + bill.key for bill in bills]],
        ).fetchall())
        for bill in bills:
            saved = facts.get(_PREFIX + bill.key)
            preference = BillPaymentPreference.model_validate_json(saved) if saved else BillPaymentPreference()
            bill.payment_preference = preference.preference
            bill.keep_current_payment = (preference.preference == "keep_current"
                or (preference.preference == "automatic" and bill.paid_from_cma))
            if preference.preference == "keep_current":
                bill.payment_reason = "You chose to keep this bill on its current payment method."
            elif preference.preference == "consider_card":
                bill.payment_reason = "Card consideration allowed; check fees and lost discounts before switching."
            elif bill.paid_from_cma:
                bill.payment_reason = "Paid from your CMA; kept here under your card-fee preference."
            else:
                bill.payment_reason = None
            if bill.status in {"suggested", "kept_in_place"}:
                bill.status = "kept_in_place" if bill.keep_current_payment else "suggested"

    def save(self, key: str, preference: BillPaymentPreference, conn: Any) -> None:
        if preference.preference == "automatic":
            conn.execute("DELETE FROM household_confirmed_facts WHERE fact_key=%s", [_PREFIX + key])
        else:
            conn.execute("""INSERT INTO household_confirmed_facts (fact_key,fact_value,confirmed_at)
                VALUES (%s,%s,now()) ON CONFLICT (fact_key) DO UPDATE
                SET fact_value=excluded.fact_value,confirmed_at=now()""", [_PREFIX + key, preference.model_dump_json()])
