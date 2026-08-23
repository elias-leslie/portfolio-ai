from datetime import date

from app.services._household_reversal_pairs import (
    find_reversal_pairs,
    reversal_reasons_by_id,
)


def _row(row_id, day, flow_type, amount, merchant, description=None):
    return {
        "id": row_id,
        "date": date(2026, 7, day),
        "flow_type": flow_type,
        "amount": amount,
        "merchant": merchant,
        "description": description or merchant,
    }


def test_pairs_a_reversed_payroll_deposit_with_its_clawback():
    pairs = find_reversal_pairs(
        [
            _row("in", 9, "income", 1102.23, "DIRECT DEPOSIT PINELLAS COUPAYROLL (Cash)"),
            _row("out", 10, "expense", 1102.23, "DIRECT DEBIT PINELLAS COUNTREVERSAL (Cash)"),
        ]
    )

    assert len(pairs) == 1
    assert pairs[0].inflow_id == "in"
    assert pairs[0].outflow_id == "out"
    assert pairs[0].amount == 1102.23
    assert "PINELLAS".lower().startswith(pairs[0].merchant_token)


def test_leaves_the_untouched_paycheque_of_the_same_day_alone():
    rows = [
        _row("keep", 9, "income", 2450.34, "DIRECT DEPOSIT PINELLAS COUPAYROLL (Cash)"),
        _row("in", 9, "income", 1102.23, "DIRECT DEPOSIT PINELLAS COUPAYROLL (Cash)"),
        _row("out", 10, "expense", 1102.23, "DIRECT DEBIT PINELLAS COUNTREVERSAL (Cash)"),
    ]

    paired = {row_id for pair in find_reversal_pairs(rows) for row_id in (pair.inflow_id, pair.outflow_id)}

    assert paired == {"in", "out"}


def test_two_unrelated_charges_of_the_same_amount_do_not_annihilate():
    pairs = find_reversal_pairs(
        [
            _row("groceries", 4, "expense", 50.00, "Publix"),
            _row("gift", 5, "income", 50.00, "Zelle From Sister"),
        ]
    )

    assert pairs == []


def test_a_credit_cancels_at_most_one_charge():
    pairs = find_reversal_pairs(
        [
            _row("charge-a", 4, "expense", 75.00, "Duke Energy"),
            _row("charge-b", 5, "expense", 75.00, "Duke Energy"),
            _row("credit", 6, "refund", 75.00, "Duke Energy"),
        ]
    )

    assert len(pairs) == 1
    assert pairs[0].outflow_id == "charge-a"


def test_a_reversal_outside_the_window_is_left_as_real_money():
    pairs = find_reversal_pairs(
        [
            _row("charge", 1, "expense", 320.00, "Frontier Communications"),
            _row("credit", 20, "refund", 320.00, "Frontier Communications"),
        ]
    )

    assert pairs == []


def test_both_sides_carry_the_same_stated_reason():
    pairs = find_reversal_pairs(
        [
            _row("in", 9, "income", 1102.23, "DIRECT DEPOSIT PINELLAS COUPAYROLL"),
            _row("out", 10, "expense", 1102.23, "DIRECT DEBIT PINELLAS COUNTREVERSAL"),
        ]
    )
    reasons = reversal_reasons_by_id(pairs)

    assert set(reasons) == {"in", "out"}
    assert reasons["in"] == reasons["out"]
    assert "1,102.23" in reasons["in"]
    assert "2026-07-09" in reasons["in"]
    assert "2026-07-10" in reasons["in"]
