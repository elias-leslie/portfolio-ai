"""Exclusions have to be visible, countable and appealable.

`_household_spend_filters.py` dropped any row matching a literal string --
"zelle to", "atm withdrawal", "payroll" -- plus four categories, and said
nothing about it. 138 of 996 ledger rows left every total with no roll-up of
what that cost and no way to disagree. A Zelle payment to a tutor is real
spend; so is an ATM withdrawal that became groceries.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.services._household_spend_exclusion_rollup import fetch_spend_exclusions
from app.services._household_spend_filters import (
    APPEALABLE_RULES,
    classify_cash_movement,
    is_budget_driving_expense,
    matched_cash_movement_rule,
    non_spend_sql_predicate,
    rule_label,
)


class _Rows:
    """The two calls the roll-up makes against storage."""

    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self._rows = rows

    def connection(self) -> _Rows:
        return self

    def __enter__(self) -> _Rows:
        return self

    def __exit__(self, *exc: object) -> bool:
        return False

    def execute(self, _sql: str, _params: list[Any] | None = None) -> _Rows:
        return self

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self._rows


def _row(
    *,
    category: str = "Retail",
    description: str = "Target",
    merchant: str = "Target",
    amount: float = 40.0,
    override: str | None = None,
    flow: str = "expense",
) -> tuple[Any, ...]:
    return (category, description, merchant, amount, override, flow)


def _rollup(rows: list[tuple[Any, ...]]):
    return fetch_spend_exclusions(
        _Rows(rows),
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
    )


def test_a_zelle_payment_the_household_calls_spend_is_counted_as_spend() -> None:
    """The override outranks the rule, which is the whole point of an appeal."""
    kwargs = {
        "category": "Household",
        "description": "ZELLE TO MARIA TUTORING",
        "merchant": "Zelle",
    }
    assert classify_cash_movement(**kwargs) == "description:zelle to"
    assert classify_cash_movement(**kwargs, spend_override="include") is None
    assert is_budget_driving_expense(flow_type="expense", **kwargs) is False
    assert (
        is_budget_driving_expense(flow_type="expense", **kwargs, spend_override="include")
        is True
    )


def test_a_row_the_rules_kept_can_be_removed_by_hand_too() -> None:
    """An appeal that only runs one way is a re-run of the same argument."""
    kwargs = {"category": "Retail", "description": "TARGET", "merchant": "Target"}
    assert classify_cash_movement(**kwargs) is None
    assert classify_cash_movement(**kwargs, spend_override="exclude") == (
        "override:excluded_by_you"
    )
    assert (
        is_budget_driving_expense(flow_type="expense", **kwargs, spend_override="exclude")
        is False
    )


def test_withdrawing_an_appeal_hands_the_row_back_to_the_rules() -> None:
    kwargs = {
        "category": "Household",
        "description": "ATM WITHDRAWAL AUTHORIZED ON",
        "merchant": "ATM",
    }
    assert classify_cash_movement(**kwargs, spend_override=None) == (
        "description:atm withdrawal"
    )
    assert classify_cash_movement(**kwargs, spend_override="") == (
        "description:atm withdrawal"
    )


def test_an_appealed_row_still_reports_the_rule_it_was_appealed_from() -> None:
    """Otherwise "3 of 41 Zelle payments now count" cannot be stated or checked."""
    kwargs = {
        "category": "Household",
        "description": "ZELLE TO MARIA TUTORING",
        "merchant": "Zelle",
    }
    assert matched_cash_movement_rule(**kwargs) == "description:zelle to"
    assert classify_cash_movement(**kwargs, spend_override="include") is None


def test_the_sql_predicate_and_the_python_predicate_agree_about_an_override() -> None:
    """A row that counts on the Ledger and not on the Dashboard is the bug being fixed."""
    predicate = non_spend_sql_predicate(
        text_expressions=["t.description"],
        category_expression="t.category",
        override_expression="t.spend_override",
    )
    assert "t.spend_override = 'include' THEN FALSE" in predicate
    assert "t.spend_override = 'exclude' THEN TRUE" in predicate
    # Without an override column the predicate is unchanged, so callers that do
    # not carry one keep their old behaviour rather than silently including rows.
    plain = non_spend_sql_predicate(
        text_expressions=["t.description"],
        category_expression="t.category",
    )
    assert "spend_override" not in plain


def test_the_rollup_says_what_was_left_out_and_what_it_came_to() -> None:
    rollup = _rollup(
        [
            _row(amount=40.0),
            _row(amount=60.0),
            _row(
                category="Household",
                description="ZELLE TO MARIA TUTORING",
                merchant="Zelle",
                amount=200.0,
            ),
            _row(
                category="Cash",
                description="ATM WITHDRAWAL AUTHORIZED ON",
                merchant="ATM",
                amount=300.0,
            ),
            _row(category="Income", description="PAYROLL", merchant="Employer",
                 amount=4000.0, flow="income"),
        ]
    )

    assert rollup.included_count == 2
    assert rollup.included_amount == 100.0
    assert rollup.excluded_count == 3
    assert rollup.excluded_amount == 4500.0
    assert "3 of 5 rows" in rollup.summary

    by_rule = {rule.rule: rule for rule in rollup.rules}
    assert by_rule["description:zelle to"].total_amount == 200.0
    assert by_rule["description:zelle to"].appealable is True
    assert by_rule["description:zelle to"].sample_merchants == ["Zelle"]
    assert by_rule["flow:income"].total_amount == 4000.0
    assert by_rule["flow:income"].appealable is False


def test_the_rollup_counts_restored_rows_under_the_rule_that_would_have_dropped_them() -> None:
    rollup = _rollup(
        [
            _row(
                category="Household",
                description="ZELLE TO MARIA TUTORING",
                merchant="Zelle",
                amount=200.0,
                override="include",
            ),
            _row(
                category="Household",
                description="ZELLE TO LANDLORD",
                merchant="Zelle",
                amount=1800.0,
            ),
        ]
    )

    assert rollup.included_count == 1
    assert rollup.excluded_count == 1
    assert rollup.overridden_count == 1
    zelle = next(rule for rule in rollup.rules if rule.rule == "description:zelle to")
    assert zelle.transaction_count == 2
    assert zelle.restored_count == 1
    assert zelle.restored_amount == 200.0
    assert "You have decided 1 of these by hand." in rollup.summary


def test_the_rollup_accounts_for_every_reason_a_row_leaves_the_total() -> None:
    """Naming only the string list answers the wrong question.

    A person arrives asking why the spend total is smaller than their
    transactions, and most of that gap is flow type, not the literal patterns.
    """
    rollup = _rollup(
        [
            _row(amount=40.0),
            _row(flow="transfer_out", amount=5000.0),
            _row(flow="income", amount=3000.0),
            _row(amount=0.0),
        ]
    )

    rules = {rule.rule: rule.label for rule in rollup.rules}
    assert rules["flow:transfer_out"] == "Moved between your own accounts"
    assert rules["flow:income"] == "Money coming in"
    assert rules["amount:non_positive"] == "Zero or credit amount"
    assert rollup.excluded_count == 3
    assert rollup.included_count == 1


def test_a_window_with_nothing_excluded_says_so_plainly() -> None:
    rollup = _rollup([_row(amount=40.0), _row(amount=60.0)])
    assert rollup.rules == []
    assert rollup.summary == "Every one of the 2 rows in this window counts as spend."


def test_every_rule_a_row_can_match_has_a_label_a_person_can_read() -> None:
    for rule in APPEALABLE_RULES:
        label = rule_label(rule)
        assert label
        assert ":" not in label
    assert rule_label("description:some new pattern") == "Matched “some new pattern”"
    assert rule_label("category:groceries") == "Category: Groceries"


def test_two_rules_that_mean_the_same_thing_are_one_line_not_two() -> None:
    """"Income" is reachable as a flow type and as a category.

    Listing "Money coming in" twice would reproduce, inside this card, the
    doubled category legend that task 1.6 existed to remove.
    """
    rollup = _rollup(
        [
            _row(category="Income", description="PAYROLL", merchant="Employer",
                 amount=4000.0, flow="income"),
            _row(category="Income", description="Pinellas Cty Sch Payables",
                 merchant="Pinellas", amount=1102.23),
        ]
    )

    labels = [rule.label for rule in rollup.rules]
    assert labels == ["Money coming in"]
    income = rollup.rules[0]
    assert income.transaction_count == 2
    assert income.total_amount == 5102.23
    assert income.sample_merchants == ["Employer", "Pinellas"]
