import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from tests.integration.services.test_household_transaction_dedup import _insert_account
from tests.services.test_card_strategy_engine import baseline, card

from app.models.card_strategy import (
    BillDecision,
    BillPaymentPreference,
    BillSuggestion,
    CardCandidate,
    ProposeStrategy,
    StrategyDecision,
    StrategySettings,
)
from app.models.credit_cards import CreditCardCreate
from app.services.card_research_service import RESEARCH_ATTEMPT_KEY, CardResearchService
from app.services.card_strategy_service import CardStrategyService
from app.storage import get_storage


@pytest.fixture
def strategy(monkeypatch):
    service = CardStrategyService(get_storage(), household=object())
    product_id = str(uuid.uuid4())
    with service.storage.connection() as conn:
        conn.execute("""INSERT INTO credit_card_products
            (id,slug,issuer,product_name,annual_fee,welcome_min_spend,welcome_bonus_cash,welcome_window_days)
            VALUES (%s,%s,'Chase','Fixture card',95,4000,600,90)""", [product_id,"fixture-"+product_id])
        conn.commit()
    candidate = CardCandidate(key=product_id+":p2", product_id=product_id, product_name="Fixture card",
        player="p2", applicant="Person Two", application_on=date.today().isoformat(),
        application_by=(date.today()+timedelta(days=14)).isoformat(), minimum_spend=4000,
        window_days=90,bonus_value=600,annual_fee=95,incremental_value=465,monthly_required=1353,
        terms_fingerprint="original-terms",terms_current=True,source_urls=["https://chase.com"],
        checks=["Confirm eligibility"],rationale="Fixture")
    bill = BillSuggestion(key="phone",merchant="Phone",amount=100,cadence="monthly",next_expected=date.today().isoformat(),
                         current_account="Old bank",already_card_spend=False,evidence="Three monthly charges")
    state = SimpleNamespace(cards=[], rows=[], baseline=baseline(), candidates=[candidate], bills=[bill])
    monkeypatch.setattr(service, "_context", lambda _today: (state.cards, service.settings(), state.rows, state.baseline, [], state.candidates,
                                                           [b.model_copy(deep=True) for b in state.bills]))
    return service, state


def approve(service, plan):
    return service.decide(plan.id, StrategyDecision(action="approve",fingerprint=plan.fingerprint,
                          eligibility_confirmed=True,cash_flow_confirmed=True))


def test_draft_approval_is_immutable_and_replacement_requires_approval(strategy):
    service, state = strategy
    draft = service.propose(ProposeStrategy())
    assert service.propose(ProposeStrategy()).id == draft.id
    assert service.view().active is None
    active = approve(service,draft)
    assert service.cards.list_owned_cards() == []
    state.candidates[0].annual_fee = 195
    state.candidates[0].terms_fingerprint = "changed-terms"
    assert service.view().active.snapshot.candidate.annual_fee == 95
    replacement = service.propose(ProposeStrategy())
    assert service.view().active.id == active.id
    approve(service,replacement)
    view = service.view()
    assert view.active.id == replacement.id
    assert next(p for p in view.history if p.id == active.id).status == "superseded"


def test_stale_offer_and_incomplete_evidence_cannot_be_approved(strategy):
    service,state = strategy
    draft = service.propose(ProposeStrategy())
    state.candidates[0].terms_fingerprint = "new"
    with pytest.raises(ValueError,match="changed"):
        approve(service,draft)
    draft = service.propose(ProposeStrategy())
    state.candidates[0].terms_current = False
    with pytest.raises(ValueError,match="issuer evidence"):
        approve(service,draft)
    assert service.view().active is None


def test_two_approvals_do_not_create_two_active_strategies(strategy):
    service,_ = strategy
    draft = service.propose(ProposeStrategy())
    def submit():
        try:
            return approve(service,draft).status
        except ValueError:
            return "rejected"
    with ThreadPoolExecutor(max_workers=2) as pool:
        result = list(pool.map(lambda _:submit(),range(2)))
    assert sorted(result) == ["approved","rejected"]
    assert sum(p.status=="approved" for p in service.view().history) == 1


def test_pause_preserves_snapshot_and_suppresses_actions(strategy):
    service,_ = strategy
    plan = approve(service,service.propose(ProposeStrategy()))
    assert service.actions()
    paused = service.decide(plan.id,StrategyDecision(action="pause",fingerprint=plan.fingerprint))
    assert service.actions() == []
    assert paused.snapshot == plan.snapshot
    resumed = service.decide(plan.id,StrategyDecision(action="resume",fingerprint=plan.fingerprint))
    assert resumed.status == "approved"


def test_bill_move_requires_real_card_cost_checks_and_later_posted_evidence(strategy):
    service,state = strategy
    plan = approve(service,service.propose(ProposeStrategy()))
    with pytest.raises(ValueError,match="opened card"):
        service.bill_decision(plan.id,"phone",BillDecision(status="confirmed"))
    account = _insert_account(service.storage)
    card = service.cards.create_owned_card(CreditCardCreate(product_id=state.candidates[0].product_id,
        player="p2",status="active",opened_date=date.today().isoformat(),household_account_id=account))
    state.cards = [card]
    plan = service.decide(plan.id,StrategyDecision(action="link_card",fingerprint=plan.fingerprint,card_id=card.id))
    with pytest.raises(ValueError,match="acceptance"):
        service.bill_decision(plan.id,"phone",BillDecision(status="confirmed"))
    with pytest.raises(ValueError,match="adds costs"):
        service.bill_decision(plan.id,"phone",BillDecision(status="confirmed",card_accepted=True,benefits_checked=True,
            fee_per_charge=3,lost_discount=0))
    yesterday = date.today()-timedelta(days=1)
    service.bill_decision(plan.id,"phone",BillDecision(status="confirmed",card_accepted=True,benefits_checked=True,
        fee_per_charge=0,lost_discount=0,confirmed_on=yesterday))
    state.rows=[{"id":"pending","merchant":"Phone","household_account_id":account,"date":date.today(),"amount":100,"pending":True}]
    assert service.view().bills[0].status == "confirmed"
    state.rows[0]["pending"] = False
    assert service.view().bills[0].status == "observed"
    assert service.view().bills[0].observation_id == "pending"
    service.bill_decision(plan.id,"phone",BillDecision(status="reset"))
    with service.storage.connection() as conn:
        assert conn.execute("SELECT count(*) FROM card_strategy_bill_moves").fetchone()[0] == 0


def test_bill_never_observes_a_charge_before_confirmation_or_on_another_account(strategy):
    service,state = strategy
    plan = approve(service,service.propose(ProposeStrategy()))
    account = _insert_account(service.storage)
    card = service.cards.create_owned_card(CreditCardCreate(product_id=state.candidates[0].product_id,player="p2",status="active",
        opened_date=date.today().isoformat(),household_account_id=account))
    state.cards = [card]
    service.decide(plan.id,StrategyDecision(action="link_card",fingerprint=plan.fingerprint,card_id=card.id))
    service.bill_decision(plan.id,"phone",BillDecision(status="confirmed",card_accepted=True,benefits_checked=True,fee_per_charge=0,lost_discount=0))
    state.rows=[{"id":"old","merchant":"Phone","household_account_id":account,"date":date.today(),"amount":100,"pending":False}]
    assert service.view().bills[0].status == "confirmed"


def test_cma_preferences_persist_without_a_plan_and_do_not_invent_fees_or_spending(strategy):
    service, state = strategy
    state.bills[0].paid_from_cma = True
    initial = service.view()
    assert initial.bills[0].status == "kept_in_place"
    assert initial.bills[0].fee_per_charge is None
    assert initial.bills[0].lost_discount is None
    service.save_bill_preference("phone", BillPaymentPreference(preference="consider_card"))
    assert service.view().bills[0].status == "suggested"
    draft = service.propose(ProposeStrategy())
    assert draft.snapshot.bills[0].payment_preference == "consider_card"
    approve(service, draft)
    assert service.view().bills[0].payment_preference == "consider_card"
    assert service.view().baseline == initial.baseline
    service.save_bill_preference("phone", BillPaymentPreference())
    assert service.view().bills[0].status == "kept_in_place"
    assert service.view().active.snapshot.bills[0].payment_preference == "consider_card"
    with pytest.raises(ValueError, match="no longer current"):
        service.save_bill_preference("not-a-bill", BillPaymentPreference(preference="keep_current"))


def test_cma_payment_move_requires_an_exception_as_well_as_cost_checks(strategy):
    service, state = strategy
    state.bills[0].paid_from_cma = True
    plan = approve(service, service.propose(ProposeStrategy()))
    account = _insert_account(service.storage)
    owned = service.cards.create_owned_card(CreditCardCreate(product_id=state.candidates[0].product_id,
        player="p2", status="active", opened_date=date.today().isoformat(), household_account_id=account))
    state.cards = [owned]
    service.decide(plan.id, StrategyDecision(action="link_card", fingerprint=plan.fingerprint, card_id=owned.id))
    decision = BillDecision(status="confirmed", card_accepted=True, benefits_checked=True, fee_per_charge=0, lost_discount=0)
    with pytest.raises(ValueError, match="Consider a credit card"):
        service.bill_decision(plan.id, "phone", decision)
    service.save_bill_preference("phone", BillPaymentPreference(preference="consider_card"))
    with pytest.raises(ValueError, match="adds costs"):
        service.bill_decision(plan.id, "phone", decision.model_copy(update={"fee_per_charge":3}))
    service.bill_decision(plan.id, "phone", decision)
    assert service.view().bills[0].status == "confirmed"
    service.save_bill_preference("phone", BillPaymentPreference())
    assert service.view().bills[0].status == "confirmed"
    service.bill_decision(plan.id, "phone", BillDecision(status="reset"))
    assert service.view().bills[0].status == "kept_in_place"


def test_automatic_research_is_opt_in_and_failed_attempts_consume_the_cooldown(strategy):
    service,_ = strategy
    research = CardResearchService()
    assert not research.research_due()
    approve(service,service.propose(ProposeStrategy()))
    service.save_settings(StrategySettings(automatic_research=True))
    assert research.research_due()
    research._stamp_marker(RESEARCH_ATTEMPT_KEY)
    assert not research.research_due()
    service.save_settings(StrategySettings(automatic_research=False))
    assert not research.research_due()


def test_research_double_click_is_rejected_before_any_model_call(strategy):
    research = CardResearchService()
    research._claim_attempt("on_demand")
    with pytest.raises(ValueError, match="already attempted"):
        research._claim_attempt("on_demand")


def test_wait_plan_has_a_dated_review_without_automatic_model_calls(strategy):
    service, _ = strategy
    approve(service, service.propose(ProposeStrategy(wait=True)))
    event = service.view().review_events[0]
    assert event["date"] == (date.today()+timedelta(days=30)).isoformat()
    assert not service.actions()


def test_approved_forecast_cannot_silently_expand_with_later_spending(strategy):
    service, state = strategy
    approve(service, service.propose(ProposeStrategy()))
    state.cards = [card().model_copy(update={"opened_date": date.today().isoformat(),
        "welcome_deadline": (date.today()+timedelta(days=30)).isoformat()})]
    state.baseline.monthly_available = 5000
    view = service.view()
    assert view.progress[0].forecast < 2000
    assert view.changes
