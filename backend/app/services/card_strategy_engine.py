"""Deterministic decisions from canonical household evidence; no model calls."""
from __future__ import annotations

import re
import statistics
from datetime import date, timedelta
from typing import Any

from app.models.card_strategy import (
    BillSuggestion,
    BonusTrack,
    CardCandidate,
    SpendingMonth,
    StrategyBaseline,
    StrategySettings,
)
from app.models.credit_cards import CreditCardProduct, HouseholdCreditCard
from app.services._card_issuer_rules import evaluate_open, welcome_eligible
from app.services._card_rotation_cashflows import add_months, parse_day
from app.services.card_rotation_engine import CardRotationEngine
from app.services.card_terms_review_service import fingerprint, issuer_source

_NON_PURCHASE = frozenset({"Cash", "Transfers", "Income", "Investments", "Taxes", "Debt"})


def merchant_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def eligible_purchase(row: dict[str, Any]) -> bool:
    return (row.get("category") not in _NON_PURCHASE
            and not row.get("needs_category_review")
            and not re.search(r"\b(annual membership fee|annual fee|interest charge|late fee|cash advance|balance transfer)\b",
                              str(row.get("merchant", "")) + " " + str(row.get("description", "")), re.I))


def _reserved(row: dict[str, Any], settings: StrategySettings) -> bool:
    merchant = merchant_key(str(row.get("merchant", "")))
    return ((settings.reserve_amazon and ("amazon" in merchant or merchant.startswith("amzn")))
            or (settings.reserve_costco and "costco" in merchant)
            or (settings.reserve_gas and row.get("category") == "Gas"))


def build_baseline(rows: list[dict[str, Any]], cards: list[HouseholdCreditCard],
                   dashboard: Any, settings: StrategySettings, today: date) -> StrategyBaseline:
    accounts = {c.household_account_id for c in cards if c.household_account_id}
    months = [add_months(today.replace(day=1), -i).strftime("%Y-%m") for i in (3, 2, 1)]
    ordinary = dict.fromkeys(months, 0.0)
    reserved = dict.fromkeys(months, 0.0)
    costco = dict.fromkeys(months, 0.0)
    seen: set[str] = set()
    for row in rows:
        month = row["date"].strftime("%Y-%m")
        if month not in ordinary or row.get("pending") or row.get("household_account_id") not in accounts:
            continue
        seen.add(month)
        if not eligible_purchase(row) or row.get("category") == "Travel":
            continue
        amount = float(row.get("signed_amount", row["amount"]))
        if _reserved(row, settings):
            reserved[month] += amount
            if "costco" in merchant_key(str(row.get("merchant", ""))):
                costco[month] += amount
        else:
            ordinary[month] += amount
    history = statistics.median(max(0, ordinary[m]) for m in seen) if seen else 0.0
    costco_shift = max(0, (settings.costco_monthly or 0) - statistics.median(costco.values())) if settings.reserve_costco else 0
    available = max(0, history - costco_shift) * 0.9
    if settings.monthly_cap is not None:
        available = min(available, settings.monthly_cap)
    income = dashboard.income_anchor
    affordability = dashboard.budget_snapshot.affordability
    if income.monthly_income is not None:
        available = min(available, max(0, income.monthly_income))
    warnings = []
    if len(seen) < 3:
        warnings.append("Fewer than three complete months contain recorded card purchases. The estimate may miss spending.")
    if income.monthly_income is None:
        warnings.append("Income is not established; check cash flow before committing to a bonus.")
    if income.profile_target_detail:
        warnings.append(income.profile_target_detail)
    if affordability is None:
        warnings.append("Cash affordability is unavailable.")
    else:
        warnings.extend("Cash-flow input missing: " + item.replace("_", " ") for item in affordability.missing_inputs)
    for account in dashboard.accounts:
        if account.household_account_id in accounts and account.transaction_freshness_status == "stale":
            warnings.append("Transactions need updating: " + account.label)
    reservations = []
    if settings.reserve_amazon:
        reservations.append("Amazon stays on its keeper card.")
    if settings.reserve_costco:
        reservations.append("Costco shopping stays outside the travel-bonus allowance.")
    if settings.reserve_gas:
        reservations.append("Gas stays outside the travel-bonus allowance.")
    if costco_shift:
        reservations.append("$" + f"{costco_shift:,.0f}/month reserved for additional Costco shopping replacing other groceries.")
    reservations.append("A 10% buffer reduces the historical allowance. Travel, fees and unobserved bank-to-card moves add nothing.")
    return StrategyBaseline(
        monthly_available=round(available, 2), historical_monthly=round(history, 2),
        months=[SpendingMonth(month=m, ordinary_card_spend=round(ordinary[m], 2), reserved_spend=round(reserved[m], 2)) for m in months],
        income_monthly=income.monthly_income, income_source=income.source_label,
        free_cash=affordability.free_to_spend if affordability else None,
        cash_status=affordability.status if affordability else "unknown",
        reservations=reservations, warnings=warnings,
    )


def terms_evidence(product: CreditCardProduct, today: date) -> tuple[bool, list[str]]:
    required = ["annual_fee", "welcome_min_spend", "welcome_window_days"]
    required.append("welcome_bonus_points" if product.welcome_bonus_points else "welcome_bonus_cash")
    urls: set[str] = set()
    valid = True
    for field in required:
        proof = product.verified_terms.get(field)
        if not isinstance(proof, dict):
            valid = False
            continue
        checked = parse_day(str(proof.get("checked_at", ""))[:10])
        source = proof.get("source_url")
        excerpt = str(proof.get("excerpt") or "")
        value = getattr(product, field)
        numbers = [float(n.replace(",", "")) for n in re.findall(r"\d[\d,]*(?:\.\d+)?", excerpt)]
        supported = bool(excerpt) and (not value or value in numbers)
        if field == "welcome_window_days" and value:
            supported = supported or (value / 30 in numbers and "month" in excerpt.lower())
        if issuer_source(product.issuer, source):
            urls.add(str(source))
        if (not checked or not 0 <= (today-checked).days <= 30 or not issuer_source(product.issuer, source)
                or proof.get("value") != value or not supported):
            valid = False
    return valid, sorted(urls)


def rank_candidates(products: list[CreditCardProduct], cards: list[HouseholdCreditCard],
                    baseline: StrategyBaseline, progress: list[BonusTrack], today: date) -> list[CardCandidate]:
    if baseline.monthly_available <= 0 or baseline.cash_status in {"hold", "tight"}:
        return []
    unfinished = [p for p in progress if p.status not in {"received", "expired"}]
    if any(p.deadline is None for p in unfinished):
        return []
    dates = [parse_day(p.deadline) for p in unfinished]
    start = max([today, *(d + timedelta(days=7) for d in dates if d)])
    states = CardRotationEngine._history(cards, ["p1", "p2"], start)
    names = {p: next((c.account_owner for c in cards if c.player == p and c.account_owner), f"Person {i+1}")
             for i, p in enumerate(("p1", "p2"))}
    result = []
    for product in products:
        if product.card_kind != "personal" or not product.welcome_min_spend or not product.welcome_window_days:
            continue
        window = product.welcome_window_days
        if product.welcome_min_spend > baseline.monthly_available * max(0, window - 7) / 30.4375:
            continue
        verified, urls = terms_evidence(product, today)
        cents = min(product.est_point_value_cents or 1.0, 1.0)
        bonus = round(product.welcome_bonus_points * cents / 100 + product.welcome_bonus_cash, 2)
        best_owned_rate = max([0.02, *(float((c.product.reward_multipliers or {}).get("other", 1)) *
                                    min(c.product.est_point_value_cents or 1, 1) / 100 for c in cards
                                    if c.product and c.status == "active")])
        rate = float(product.reward_multipliers.get("other", 1)) * cents / 100
        net = round(bonus-product.annual_fee + product.welcome_min_spend * (rate-best_owned_rate), 2)
        if net <= 0:
            continue
        for player, state in states.items():
            if product.slug in state.held_products or not welcome_eligible(product, state):
                continue
            checks = evaluate_open(product, quarter_index=0, state=state)
            family_note = product.issuer_rules.get("bonus_family_description")
            if isinstance(family_note, str):
                checks.append(family_note)
            if not verified:
                checks.insert(0, "Verify the current bonus, spending window and annual fee against the issuer offer.")
            checks.append("Confirm this applicant's complete card history and personalized offer eligibility.")
            result.append(CardCandidate(
                key=product.id+":"+player, product_id=product.id, product_name=product.product_name,
                player=player, applicant=names[player], application_on=start.isoformat(),
                application_by=(start+timedelta(days=14)).isoformat(),
                minimum_spend=product.welcome_min_spend, window_days=window, bonus_value=bonus,
                annual_fee=product.annual_fee, incremental_value=net,
                monthly_required=round(product.welcome_min_spend / (window / 30.4375), 2),
                terms_fingerprint=fingerprint(product.model_dump(mode="json", exclude={"created_at", "updated_at", "last_verified_at", "verified_terms"})), terms_current=verified,
                source_urls=urls, checks=checks,
                rationale="About $" + f"{net:,.0f} above a conservative 2%-or-better baseline after the annual fee. "
                          "Points valued at 1 cent or less; conditional credits excluded. "
                          + ("Start after the existing welcome commitment." if unfinished else "The ordinary-spend allowance covers the offer with a time buffer."),
            ))
    result.sort(key=lambda c: (not c.terms_current, -c.incremental_value, len(c.checks),
                               sum(x.player == c.player and x.status != "candidate" for x in cards), c.key))
    return result[:8]


def track_bonuses(cards: list[HouseholdCreditCard], rows: list[dict[str, Any]],
                  baseline: StrategyBaseline, today: date) -> list[BonusTrack]:
    tracks = []
    remaining_allowance = baseline.monthly_available
    ordered = sorted((c for c in cards if c.role != "keeper" and c.status not in {"candidate", "closed"}),
                     key=lambda c: c.welcome_deadline or "9999")
    for card in ordered:
        opened = parse_day(card.opened_date)
        deadline = parse_day(card.welcome_deadline)
        required = card.product.welcome_min_spend if card.product else None
        selected = [r for r in rows if opened and opened <= r["date"] <= today
                    and (deadline is None or r["date"] <= deadline or float(r.get("signed_amount", r["amount"])) < 0) and card.household_account_id
                    and r.get("household_account_id") == card.household_account_id and eligible_purchase(r)]
        posted = round(sum(float(r.get("signed_amount", r["amount"])) for r in selected if not r.get("pending")), 2)
        pending = round(sum(float(r.get("signed_amount", r["amount"])) for r in selected if r.get("pending")), 2)
        left = max(0, required-posted) if required is not None else None
        days = (deadline-today).days if deadline else None
        forecast = posted + remaining_allowance * max(0, days or 0) / 30.4375 if days is not None else None
        if forecast is not None and required is not None:
            forecast = min(required, forecast)
        unknown = not opened or not card.household_account_id or required is None or deadline is None
        if card.welcome_status == "earned":
            status, explanation = "received", "Bonus received, as recorded in card history. Posted spending shows ledger coverage separately."
            left, forecast = None, None
        elif unknown:
            status, explanation = "needs_data", "Link the account and confirm the original offer, opening date and deadline."
            remaining_allowance = 0
        elif card.welcome_status == "spend_met" or left == 0:
            status, explanation = "awaiting_bonus", "Spending requirement met; the bonus is not yet recorded as received."
            if card.welcome_status == "spend_met":
                explanation += " Completion was confirmed by the household; posted spending shows ledger coverage separately."
                left, forecast = None, None
        elif days is not None and days < 0:
            status, explanation = "expired", "The recorded deadline passed. Check the issuer result."
        else:
            status = "on_track" if forecast is not None and required is not None and forecast >= required else "at_risk"
            explanation = "Forecast uses ordinary spending, excludes pending charges and reserves this allowance before later bonuses."
            pace = left * 30.4375 / max(1, days or 1) if left is not None else remaining_allowance
            remaining_allowance = max(0, remaining_allowance-pace)
        tracks.append(BonusTrack(card_id=card.id, label=card.account_label or (card.product.product_name if card.product else "Card"),
            applicant=card.account_owner or card.player, deadline=card.welcome_deadline, required=required,
            posted=posted, pending=pending, remaining=left, days_left=days, forecast=round(forecast, 2) if forecast is not None else None,
            status=status, explanation=explanation))
    return tracks


def suggest_bills(commitments: list[Any], rows: list[dict[str, Any]], cards: list[HouseholdCreditCard]) -> list[BillSuggestion]:
    card_accounts = {c.household_account_id for c in cards if c.household_account_id}
    result = []
    for bill in commitments:
        if bill.commitment_type not in {"bill", "subscription"} or bill.due_status == "lapsed":
            continue
        matches = [r for r in rows if merchant_key(str(r["merchant"])) == merchant_key(bill.merchant)
                   and not r.get("pending") and float(r.get("signed_amount", r["amount"])) > 0]
        latest = max(matches, key=lambda r: r["date"]) if matches else None
        result.append(BillSuggestion(key=merchant_key(bill.merchant), merchant=bill.merchant, amount=bill.average_amount,
            cadence=bill.cadence, next_expected=bill.next_expected, current_account=latest.get("account_label") if latest else None,
            already_card_spend=bool(latest and latest.get("household_account_id") in card_accounts),
            evidence=bill.evidence or "Recurring commitment recorded in Money."))
    return result
