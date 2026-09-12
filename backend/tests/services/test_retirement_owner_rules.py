"""Owner and cohort boundaries must agree in every retirement projection."""

from datetime import date

import pytest

from app.portfolio.contracts.retirement import RetirementAccountBucket, RetirementInputs
from app.services.retirement_plan_simulation import _apply_tax_aware_withdrawals
from app.services.retirement_planning_assumptions import (
    _bucket_balances,
    _rmd_amount,
    _tax_context_from_profile,
)


def inputs(**values):
    return RetirementInputs(
        household_id="test",
        primary_age=60,
        spouse_age=55,
        retirement_age=60,
        annual_expenses=10000,
        portfolio_value=100000,
        as_of_date=date(2026, 9, 11),
        **values,
    )


def withdraw(balances, **kwargs):
    return _apply_tax_aware_withdrawals(
        balances,
        spending=kwargs.pop("spending", 10000),
        income_components={"ordinary": 0, "social_security": 0, "total": 0},
        primary_age=kwargs.pop("primary_age", 60),
        spouse_age=kwargs.pop("spouse_age", 55),
        inflation_factor=1,
        tax_context=_tax_context_from_profile(None, inputs()),
        **kwargs,
    )


def test_people_born_after_1959_do_not_have_rmds_at_73_or_74():
    assert _rmd_amount(100000, 73, birth_year=1977) == 0
    assert _rmd_amount(100000, 74, birth_year=1982) == 0
    assert _rmd_amount(100000, 75, birth_year=1977) == pytest.approx(100000 / 24.6)


def test_account_ownership_survives_bucket_aggregation():
    buckets = tuple(
        RetirementAccountBucket(
            bucket_type="pre_tax",
            label=owner,
            account_type="ira",
            tax_treatment="ordinary_income",
            current_value=amount,
            withdrawal_priority=4,
            owner=owner,
        )
        for owner, amount in [("primary", 5000), ("spouse", 95000)]
    )
    balances = _bucket_balances(inputs(), buckets)
    assert balances["pre_tax"] == 5000
    assert balances["spouse__pre_tax"] == 95000


def test_spouses_early_distribution_does_not_use_primarys_older_age():
    result = withdraw({"pre_tax": 0, "spouse__pre_tax": 100000})
    assert result.withdrawals["spouse__pre_tax"] > 10000
    assert result.penalty_estimate == pytest.approx(result.withdrawals["spouse__pre_tax"] * 0.1)


def test_eligible_owner_draws_before_younger_owner_within_same_tax_bucket():
    result = withdraw({"pre_tax": 5000, "spouse__pre_tax": 100000})
    assert result.withdrawals["pre_tax"] == 5000
    assert result.penalty_estimate == pytest.approx(result.withdrawals["spouse__pre_tax"] * 0.1)


def test_rmd_is_separate_by_owner_and_uses_prior_year_balance():
    result = withdraw(
        {"pre_tax": 120000, "spouse__pre_tax": 120000},
        primary_age=75,
        spouse_age=70,
        spending=0,
        primary_birth_year=1951,
        spouse_birth_year=1956,
        rmd_balances={"pre_tax": 100000, "spouse__pre_tax": 100000},
    )
    assert result.rmd_amount == pytest.approx(100000 / 24.6)
    assert result.withdrawals["spouse__pre_tax"] == 0


def test_spouses_457_is_not_available_before_their_separation():
    result = withdraw(
        {"spouse__governmental_457b": 100000}, owner_retirement_ages={"primary": 60, "spouse": 60}
    )
    assert result.withdrawals["spouse__governmental_457b"] == 0
    assert result.shortfall == 10000


def test_rmd_uses_age_attained_during_calendar_year():
    from app.services._retirement_ownership import before_rmd_age

    case = inputs().model_copy(
        update={"primary_age": 74, "primary_birth_year": 1951, "spouse_birth_year": 1971}
    )
    assert not before_rmd_age(case, 0)
    result = withdraw(
        {"pre_tax": 100000},
        primary_age=74,
        spouse_age=55,
        spending=0,
        primary_birth_year=1951,
        spouse_birth_year=1971,
        calendar_year=2026,
    )
    assert result.rmd_amount == pytest.approx(100000 / 24.6)


def test_partial_retirement_contributions_go_to_working_spouse():
    from app.services._retirement_ownership import contribution_key

    case = inputs(spouse_retirement_age=65)
    assert contribution_key({"pre_tax": 100, "spouse__pre_tax": 200}, case, 1) == "spouse__pre_tax"
    assert contribution_key({"pre_tax": 100}, case, 1) == "taxable"


@pytest.mark.parametrize("ages", [(60, 55), (75, 70)])
def test_deterministic_and_zero_volatility_paths_match_including_rmd_surplus(ages):
    from app.services.retirement_plan_simulation import _run_tax_aware_monte_carlo
    from tests.services.test_retirement_planning_service import _make_service, _StubConn

    case = inputs(horizon_years=5).model_copy(
        update={
            "primary_age": ages[0],
            "spouse_age": ages[1],
            "retirement_age": 80,
            "spouse_retirement_age": 80,
            "annual_expenses": 0,
            "asset_allocation": {"us_equity": 1},
            "inflation_rate": 0,
        }
    )
    buckets = tuple(
        RetirementAccountBucket(
            bucket_type="pre_tax",
            label=owner,
            account_type="ira",
            tax_treatment="ordinary_income",
            current_value=50000,
            withdrawal_priority=4,
            owner=owner,
        )
        for owner in ["primary", "spouse"]
    )
    service = _make_service(_StubConn())
    service._cma = {
        "version": "test",
        "asset_classes": {
            "us_equity": {"expected_return": 0.05, "volatility": 0},
            "cash": {"expected_return": 0.02, "volatility": 0},
        },
        "correlations": {},
    }
    context = _tax_context_from_profile(None, case)
    rows = service._drawdown_schedule(case, buckets=buckets, tax_context=context)
    sim = _run_tax_aware_monte_carlo(
        case, buckets=buckets, tax_context=context, cma=service._cma, trials=2, seed=7
    )
    assert sim.ending_balance_paths["p50"] == pytest.approx(
        [r.ending_balance for r in rows], abs=0.02
    )
    assert rows[0].ending_balance == 100000
    assert rows[0].balances_by_owner["spouse"]["pre_tax"] == 50000
    if ages[0] == 75:
        assert rows[0].rmd_amount > 0
        assert rows[0].balances_by_bucket["taxable"] > 0


def test_saved_inputs_replay_account_ownership_without_live_readers():
    bucket=RetirementAccountBucket(bucket_type='pre_tax',label='Spouse IRA',account_type='ira',
        tax_treatment='ordinary_income',current_value=100000,withdrawal_priority=4,owner='spouse')
    case=inputs().model_copy(update={'account_buckets':(bucket,)})
    restored=RetirementInputs.model_validate_json(case.model_dump_json())
    balances=_bucket_balances(restored,())
    assert balances['spouse__pre_tax']==100000
    assert balances['taxable']==0
    assert withdraw(balances).penalty_estimate>0


def test_unique_registered_first_name_matches_full_owner_name():
    from app.services._retirement_ownership import account_owner
    members=[{'display_name':'Alex','role':'primary'}, {'display_name':'Jordan','role':'spouse'}]
    assert account_owner('Jordan Example',members)=='spouse'
    assert account_owner('Jamie Example',members)=='unknown'
    assert account_owner('Alex',[*members,{'display_name':'Alex Other','role':'spouse'}])=='unknown'


def test_529_label_overrides_generic_taxable_provider_type():
    from types import SimpleNamespace

    from app.services._retirement_ownership import is_education_account
    assert is_education_account(SimpleNamespace(label='Individual - 529',asset_group='taxable'))
    assert not is_education_account(SimpleNamespace(label='Individual - TOD',asset_group='taxable'))
