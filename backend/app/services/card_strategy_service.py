"""One saved strategy lifecycle shared by Cards, research and header Actions."""
from __future__ import annotations

import re
import uuid
from datetime import date, timedelta
from typing import Any

from app.models.card_strategy import (
    BillDecision,
    BillPaymentPreference,
    ProposeStrategy,
    SavedStrategy,
    StrategyDecision,
    StrategySettings,
    StrategySnapshot,
    StrategyView,
)
from app.services._card_rotation_cashflows import add_months, parse_day
from app.services.card_bill_preferences import CardBillPreferences
from app.services.card_management_service import CardManagementService
from app.services.card_strategy_engine import (
    build_baseline,
    merchant_key,
    rank_candidates,
    suggest_bills,
    track_bonuses,
)
from app.services.card_terms_review_service import fingerprint
from app.services.household_finance_service import HouseholdFinanceService
from app.storage import get_storage

SETTINGS_KEY = "card_strategy_settings"
_LOCK = 781947010


class CardStrategyService:
    def __init__(self, storage: Any = None, household: Any = None):
        self.storage = storage or get_storage()
        self.cards = CardManagementService(self.storage)
        self.bill_preferences = CardBillPreferences(self.storage)
        self.household = household or HouseholdFinanceService()

    def settings(self) -> StrategySettings:
        with self.storage.connection() as conn:
            facts = dict(conn.execute("SELECT fact_key,fact_value FROM household_confirmed_facts WHERE fact_key = ANY(%s)",
                                     [[SETTINGS_KEY, "costco_membership"]]).fetchall())
        if facts.get(SETTINGS_KEY):
            return StrategySettings.model_validate_json(str(facts[SETTINGS_KEY]))
        # Initialize from the user's existing declaration, not a fabricated budget.
        amounts = re.findall(r"\$([\d,]+)", str(facts.get("costco_membership", "")))
        costco = sum(float(x.replace(",", "")) for x in amounts) / len(amounts) if amounts else None
        return StrategySettings(costco_monthly=costco)

    def save_settings(self, settings: StrategySettings) -> StrategySettings:
        with self.storage.connection() as conn:
            conn.execute("""INSERT INTO household_confirmed_facts (fact_key,fact_value,confirmed_at)
                VALUES (%s,%s,now()) ON CONFLICT (fact_key) DO UPDATE
                SET fact_value=excluded.fact_value,confirmed_at=now()""", [SETTINGS_KEY, settings.model_dump_json()])
            conn.commit()
        return settings

    def _context(self, today: date):
        cards = self.cards.list_owned_cards()
        settings = self.settings()
        rows = self.household.transaction_service._spend_rows_between(start_date=None, end_date=today)
        household = self.household.get_dashboard()
        baseline = build_baseline(rows, cards, household, settings, today)
        progress = track_bonuses(cards, rows, baseline, today)
        candidates = rank_candidates(self.cards.get_catalog(), cards, baseline, progress, today)
        bills = suggest_bills(household.recurring_commitments, rows, cards, household.accounts)
        return cards, settings, rows, baseline, progress, candidates, bills

    def _plans(self) -> list[SavedStrategy]:
        with self.storage.connection() as conn:
            rows = conn.execute("""SELECT id::text,fingerprint,status,snapshot,actual_card_id::text,
                created_at::text,approved_at::text,eligibility_confirmed FROM card_strategy_plans
                WHERE status IN ('approved','paused','draft') OR id IN
                    (SELECT id FROM card_strategy_plans ORDER BY created_at DESC LIMIT 50)
                ORDER BY created_at DESC""").fetchall()
        return [SavedStrategy(**dict(zip(("id","fingerprint","status","snapshot","actual_card_id","created_at","approved_at","eligibility_confirmed"), row, strict=True))) for row in rows]

    def view(self) -> StrategyView:
        today = date.today()
        cards, settings, rows, baseline, progress, candidates, bills = self._context(today)
        plans = self._plans()
        active = next((p for p in plans if p.status in {"approved", "paused"}), None)
        draft = next((p for p in plans if p.status == "draft"), None)
        changes = []
        if active:
            old = active.snapshot.baseline.monthly_available
            if abs(baseline.monthly_available-old) > max(50, old*0.15):
                changes.append("The current ordinary-spend allowance has changed materially. Review a replacement plan.")
            if settings != active.snapshot.settings:
                changes.append("Spending preferences changed after approval. The approved snapshot is unchanged.")
            # Tracking can reduce an unsafe allowance, but never increase the
            # approved commitment silently when historical spending grows.
            tracking_baseline = baseline.model_copy(update={"monthly_available": min(old, baseline.monthly_available)})
            progress = track_bonuses(cards, rows, tracking_baseline, today)
            candidate = active.snapshot.candidate
            if candidate and not active.actual_card_id:
                current = next((c for c in candidates if c.key == candidate.key), None)
                if current is None or current.terms_fingerprint != candidate.terms_fingerprint or not current.terms_current:
                    changes.append("Recheck the approved card's offer or feasibility before applying.")
                elif current.key != (candidates[0].key if candidates else None):
                    changes.append("Another card or applicant now ranks higher. Compare before changing the approved plan.")
                if today > date.fromisoformat(candidate.application_by):
                    changes.append("The proposed application window passed. Refresh the recommendation before applying.")
            bills = self._bill_status(active, bills, rows, cards)
        self.bill_preferences.apply(bills)
        recommendation = ("Review the leading card and applicant; verify the listed checks before approval."
                          if candidates else "Wait on a new application. Resolve cash-flow, spending or existing-bonus gaps first.")
        events = []
        if active and active.snapshot.candidate is None and active.approved_at:
            review_on = date.fromisoformat(active.approved_at[:10]) + timedelta(days=30)
            events.append({"id": "wait-review", "title": "Review the decision to wait", "date": review_on.isoformat(),
                           "detail": "Compare current spending and opportunities before approving the next revision."})
        for card in cards:
            due = parse_day(card.annual_fee_due_date)
            if card.status not in {"candidate", "closed"} and due and due <= today+timedelta(days=45):
                events.append({"id": "fee-"+card.id, "title": "Review keeping or downgrading " + (card.account_label or card.product.product_name),
                               "date": due.isoformat(), "detail": "Review the annual fee and benefits; no closure is assumed."})
        return StrategyView(as_of=today.isoformat(), settings=settings, baseline=baseline, candidates=candidates,
            recommendation=recommendation, active=active, draft=draft, history=plans, progress=progress,
            bills=bills, changes=changes, review_events=events)

    def propose(self, request: ProposeStrategy) -> SavedStrategy:
        view = self.view()
        candidate = None
        if not request.wait:
            candidate = next((c for c in view.candidates if c.key == request.candidate_key), None) if request.candidate_key else next(iter(view.candidates), None)
            if candidate is None:
                raise ValueError("This candidate is no longer available. Refresh the recommendation or choose to wait.")
        snapshot = StrategySnapshot(baseline=view.baseline, candidate=candidate, bills=view.bills,
            settings=view.settings, recommendation=view.recommendation if candidate else "Keep the current cards and review when circumstances change.")
        digest = fingerprint(snapshot.model_dump(mode="json"))
        with self.storage.connection() as conn:
            conn.execute("SELECT pg_advisory_xact_lock(%s)", [_LOCK])
            existing = conn.execute("SELECT id::text FROM card_strategy_plans WHERE status='draft' AND fingerprint=%s", [digest]).fetchone()
            if existing:
                plan_id = str(existing[0])
            else:
                plan_id = str(uuid.uuid4())
                conn.execute("UPDATE card_strategy_plans SET status='superseded',updated_at=now() WHERE status='draft'")
                conn.execute("""INSERT INTO card_strategy_plans (id,fingerprint,snapshot,previous_plan_id)
                    VALUES (%s,%s,%s::jsonb,%s)""", [plan_id,digest,snapshot.model_dump_json(),view.active.id if view.active else None])
            conn.commit()
        return next(p for p in self._plans() if p.id == plan_id)

    def decide(self, plan_id: str, request: StrategyDecision) -> SavedStrategy:
        # Read fresh evidence before entering the short state-transition transaction.
        view = self.view()
        plan = next((p for p in view.history if p.id == plan_id), None)
        if plan is None:
            raise ValueError("Plan not found.")
        if request.fingerprint != plan.fingerprint:
            raise ValueError("This plan changed. Reload before continuing.")
        candidate = plan.snapshot.candidate
        if request.action == "approve":
            if plan.status != "draft":
                raise ValueError("Only the current draft can be approved.")
            if not request.cash_flow_confirmed:
                raise ValueError("Review and confirm the cash-flow assumptions.")
            if candidate:
                current = next((c for c in view.candidates if c.key == candidate.key), None)
                if (current is None or current.terms_fingerprint != candidate.terms_fingerprint
                        or current.application_on > candidate.application_by
                        or view.settings != plan.snapshot.settings
                        or view.baseline.monthly_available < plan.snapshot.baseline.monthly_available * 0.95):
                    raise ValueError("Offer, timing or spending assumptions changed. Create a fresh draft.")
                if not current.terms_current:
                    raise ValueError("Current issuer evidence is required. Review the offer terms, then create a fresh draft.")
                if not request.eligibility_confirmed:
                    raise ValueError("Confirm the named applicant's card history and offer eligibility.")
        card = None
        if request.action == "link_card":
            if plan.actual_card_id and plan.actual_card_id != request.card_id:
                raise ValueError("This plan already tracks an opened card. Its billing history must stay linked to that card.")
            card = next((c for c in self.cards.list_owned_cards() if c.id == request.card_id), None)
            if (not candidate or not card or card.product_id != candidate.product_id or card.player != candidate.player
                    or card.status in {"candidate", "closed"} or not card.opened_date):
                raise ValueError("Choose the matching opened card for the approved applicant. Record its opening date first.")
        with self.storage.connection() as conn:
            conn.execute("SELECT pg_advisory_xact_lock(%s)", [_LOCK])
            row = conn.execute("SELECT status,fingerprint FROM card_strategy_plans WHERE id=%s FOR UPDATE", [plan_id]).fetchone()
            if row is None or row[0] != plan.status or row[1] != request.fingerprint:
                raise ValueError("The plan was changed in another window. Reload it.")
            if request.action == "approve":
                conn.execute("UPDATE card_strategy_plans SET status='superseded',updated_at=now() WHERE status IN ('approved','paused')")
                conn.execute("UPDATE card_strategy_plans SET status='approved',approved_at=now(),updated_at=now(),eligibility_confirmed=%s WHERE id=%s",
                             [request.eligibility_confirmed,plan_id])
            elif request.action in {"pause", "resume"}:
                expected = "approved" if request.action == "pause" else "paused"
                if plan.status != expected:
                    raise ValueError("This plan cannot make that transition.")
                conn.execute("UPDATE card_strategy_plans SET status=%s,updated_at=now() WHERE id=%s",
                             ["paused" if request.action == "pause" else "approved",plan_id])
            else:
                if plan.status != "approved" or card is None:
                    raise ValueError("Resume the approved plan before linking its card.")
                conn.execute("UPDATE card_strategy_plans SET actual_card_id=%s,updated_at=now() WHERE id=%s", [card.id,plan_id])
            conn.commit()
        return next(p for p in self._plans() if p.id == plan_id)

    def _bill_status(self, plan, bills, rows, cards):
        with self.storage.connection() as conn:
            saved = {r[0]: r for r in conn.execute("""SELECT merchant_key,status,fee_per_charge,lost_discount,
                confirmed_at::date,first_charge_due_on FROM card_strategy_bill_moves WHERE plan_id=%s""", [plan.id]).fetchall()}
        current_keys = {b.key for b in bills}
        bills.extend(b.model_copy(deep=True) for b in plan.snapshot.bills if b.key in saved and b.key not in current_keys)
        card = next((c for c in cards if c.id == plan.actual_card_id), None)
        for bill in bills:
            record = saved.get(bill.key)
            if record:
                bill.status, bill.fee_per_charge, bill.lost_discount = record[1], float(record[2]), float(record[3])
                bill.first_charge_due_on = record[5].isoformat() if record[5] else None
            if not card or not card.household_account_id:
                continue
            matches = [r for r in rows if merchant_key(str(r["merchant"])) == bill.key and not r.get("pending")
                       and r.get("household_account_id") == card.household_account_id
                       and float(r.get("signed_amount", r["amount"])) > 0
                       and abs(float(r["amount"])-bill.amount) <= bill.amount*0.35
                       and (not record or r["date"] > record[4])]
            if matches and (not record or record[1] == "confirmed"):
                latest = max(matches, key=lambda r: r["date"])
                bill.status = "observed" if record else "already_on_card"
                bill.observed_on, bill.observation_id = latest["date"].isoformat(), latest["id"]
        return bills

    def save_bill_preference(self, key: str, preference: BillPaymentPreference) -> None:
        if key not in {bill.key for bill in self.view().bills}:
            raise ValueError("This recurring bill is no longer current.")
        with self.storage.connection() as conn:
            conn.execute("SELECT pg_advisory_xact_lock(%s)", [_LOCK])
            self.bill_preferences.save(key, preference, conn)
            conn.commit()

    def bill_decision(self, plan_id: str, key: str, request: BillDecision) -> None:
        view = self.view()
        if not view.active or view.active.id != plan_id or view.active.status != "approved":
            raise ValueError("Use the current approved plan.")
        if key not in {b.key for b in view.bills}:
            raise ValueError("This recurring bill is no longer current.")
        if request.confirmed_on and request.confirmed_on > date.today():
            raise ValueError("A payment change cannot be confirmed in the future.")
        if request.status == "confirmed":
            if not view.active.actual_card_id:
                raise ValueError("Link the actually opened card before recording a billing change.")
            if (not request.card_accepted or not request.benefits_checked
                    or request.fee_per_charge is None or request.lost_discount is None):
                raise ValueError("Check card acceptance, fees, lost discounts and existing benefits first.")
            if request.fee_per_charge + request.lost_discount > 0:
                raise ValueError("This move adds costs. Keep this bill in place and use the ordinary spending already in the plan.")
        bill = next(b for b in view.bills if b.key == key)
        confirmed = request.confirmed_on or date.today()
        due = parse_day(bill.next_expected)
        if due is None or due <= confirmed:
            months = {"monthly": 1, "bimonthly": 2, "quarterly": 3, "annual": 12, "yearly": 12}.get(bill.cadence)
            due = add_months(confirmed, months) if months else confirmed + timedelta(days=35)
        with self.storage.connection() as conn:
            conn.execute("SELECT pg_advisory_xact_lock(%s)", [_LOCK])
            current = conn.execute("SELECT status FROM card_strategy_plans WHERE id=%s FOR UPDATE", [plan_id]).fetchone()
            if current is None or current[0] != "approved":
                raise ValueError("The plan changed. Reload the checklist.")
            if request.status == "confirmed":
                self.bill_preferences.apply([bill], conn)
                if bill.keep_current_payment:
                    raise ValueError("This bill is set to keep its current payment method. Choose Consider a credit card first.")
            if request.status == "reset":
                conn.execute("DELETE FROM card_strategy_bill_moves WHERE plan_id=%s AND merchant_key=%s", [plan_id,key])
            else:
                conn.execute("""INSERT INTO card_strategy_bill_moves
                    (plan_id,merchant_key,status,fee_per_charge,lost_discount,benefits_checked,confirmed_at,first_charge_due_on)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (plan_id,merchant_key) DO UPDATE SET
                    status=excluded.status,fee_per_charge=excluded.fee_per_charge,lost_discount=excluded.lost_discount,
                    benefits_checked=excluded.benefits_checked,confirmed_at=excluded.confirmed_at,first_charge_due_on=excluded.first_charge_due_on""",
                    [plan_id,key,request.status,request.fee_per_charge or 0,request.lost_discount or 0,
                     request.benefits_checked,confirmed,due])
            conn.commit()

    def actions(self) -> list[dict[str, object]]:
        view = self.view()
        if not view.settings.reminders_enabled or (view.active and view.active.status == "paused"):
            return []
        notices: list[tuple[str,str,str,str]] = []
        if view.draft:
            notices.append(("draft","Review your card strategy","A saved proposal is ready for your approval.","medium"))
        if view.active:
            candidate = view.active.snapshot.candidate
            if view.changes:
                notices.append(("changed","Review changes to your card plan",view.changes[0],"medium"))
            elif candidate and not view.active.actual_card_id and candidate.application_on <= view.as_of:
                notices.append(("apply","Card application window: "+candidate.applicant,
                                candidate.product_name+". Check the issuer offer, then record the result in Cards.","medium"))
            for bill in view.bills:
                if bill.status == "confirmed" and bill.first_charge_due_on and bill.first_charge_due_on < view.as_of:
                    notices.append(("bill-"+bill.key,"Check "+bill.merchant+" billing",
                                    "The payment change is confirmed, but its first matching card charge is not yet observed.","medium"))
        for p in view.progress:
            if p.status in {"at_risk","needs_data","expired","awaiting_bonus"}:
                notices.append(("bonus-"+p.card_id,p.label+": "+p.status.replace("_"," "),p.explanation,
                                "high" if p.status in {"at_risk","expired"} else "medium"))
        notices.extend((e["id"],e["title"],e["date"]+". "+e["detail"],"medium") for e in view.review_events if e["id"] != "wait-review" or e["date"] <= view.as_of)
        return [{"id":"card-strategy-"+key,"source":"household","category":"household","priority":priority,
                 "title":title,"detail":detail,"action_label":"Review card plan","href":"/money?tab=cards#card-strategy",
                 "badge":"Cards"} for key,title,detail,priority in notices]
