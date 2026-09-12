"""Dated card costs shared by rotation and its keep-one-card comparison."""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date

from app.models.credit_cards import CreditCardProduct, HouseholdCreditCard


def add_months(day: date, months: int) -> date:
    absolute = day.year * 12 + day.month - 1 + months
    year, month = divmod(absolute, 12)
    return date(year, month + 1, min(day.day, monthrange(year, month + 1)[1]))


def parse_day(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value[:10]) if value else None
    except ValueError:
        return None


@dataclass(frozen=True)
class HeldCard:
    player: str
    product: CreditCardProduct
    opened: date
    next_fee: date
    closes: date | None = None
    existing_id: str | None = None


def owned_lifecycle(cards: list[HouseholdCreditCard], start: date) -> tuple[list[HeldCard], list[str]]:
    held, warnings = [], []
    for card in cards:
        if card.product is None or card.status not in {"active", "inactive", "rotated_out"}:
            continue
        opened = parse_day(card.opened_date)
        renewal = parse_day(card.annual_fee_due_date)
        if renewal is None:
            if opened is None:
                # A missing date cannot make a known fee disappear. Reserve it
                # now, clearly marked as an estimate, until the date is supplied.
                renewal = start
                if card.product.annual_fee > 0:
                    warnings.append(f"{card.player}: {card.product.product_name} renewal date missing; fee reserved at plan start.")
            else:
                renewal = add_months(opened, 12)
        while renewal < start:
            renewal = add_months(renewal, 12)
        held.append(HeldCard(card.player, card.product, opened or start, renewal,
                             parse_day(card.closed_date), card.id))
    return held, warnings


def fee_events(held: list[HeldCard], start: date, end: date) -> list[dict[str, object]]:
    """Full fees on opening/renewal dates; never refund a fraction on close."""
    events: list[dict[str, object]] = []
    for card in held:
        due = card.next_fee
        while due < end:
            if start <= due and (card.closes is None or due < card.closes):
                events.append({
                    "date": due.isoformat(), "player": card.player,
                    "product_slug": card.product.slug, "product_name": card.product.product_name,
                    "kind": "opening_fee" if due == card.opened and card.existing_id is None else "renewal_fee",
                    "amount": -card.product.annual_fee,
                })
            due = add_months(due, 12)
        if card.closes is not None and start <= card.closes < end:
            events.append({"date": card.closes.isoformat(), "player": card.player,
                           "product_slug": card.product.slug, "product_name": card.product.product_name,
                           "kind": "planned_close", "amount": 0.0})
    return sorted(events, key=lambda event: (str(event["date"]), str(event["player"]), str(event["product_slug"])))


def total_fees(events: list[dict[str, object]]) -> float:
    return round(-sum(float(str(event["amount"])) for event in events if event["kind"] in {"opening_fee", "renewal_fee"}), 2)


def anniversary_events(held: list[HeldCard], start: date, end: date, point_values: dict[str, float]) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for card in held:
        points = card.product.issuer_rules.get("anniversary_points")
        if not isinstance(points, int) or points <= 0:
            continue
        due = add_months(card.opened, 12)
        while due < end:
            if due >= start and (card.closes is None or due < card.closes):
                events.append({"date": due.isoformat(), "player": card.player,
                    "product_slug": card.product.slug, "product_name": card.product.product_name,
                    "kind": "anniversary_reward", "amount": round(points*point_values.get(card.product.slug, 1)/100, 2)})
            due = add_months(due, 12)
    return events
