from datetime import date

from app.services._household_one_time_purchases import find_one_time_purchases


def _row(row_id, day, merchant, amount, category="Household", month=7):
    return {
        "id": row_id,
        "date": date(2026, month, day),
        "merchant": merchant,
        "category": category,
        "amount": amount,
        "signed_amount": amount,
    }


def test_an_appliance_split_across_two_cards_is_one_time_on_both_legs():
    month_rows = [
        _row("ac-a", 23, "Costco", 5831.50),
        _row("ac-b", 23, "Costco", 5801.50),
        _row("shop", 15, "Costco", 856.99),
    ]
    history = [*month_rows, _row("prior", 4, "Costco", 247.14, month=6)]

    found = find_one_time_purchases(
        month_rows, history_rows=history, month_total=16658.01
    )

    assert [item.transaction_id for item in found] == ["ac-a", "ac-b"]
    assert found[0].amount == 5831.50
    assert "any other month" in found[0].reason
    assert "$247.14" in found[0].reason


def test_the_ordinary_costco_run_in_the_same_month_stays_ordinary():
    month_rows = [_row("ac-a", 23, "Costco", 5831.50), _row("shop", 15, "Costco", 856.99)]

    found = find_one_time_purchases(
        month_rows, history_rows=month_rows, month_total=16658.01
    )

    assert "shop" not in {item.transaction_id for item in found}


def test_a_merchant_that_bills_this_much_every_month_has_precedent():
    month_rows = [_row("rent", 1, "Harbor Hills", 2400.00, category="Home")]
    history = [
        *month_rows,
        _row("rent-jun", 1, "Harbor Hills", 2400.00, category="Home", month=6),
        _row("rent-may", 1, "Harbor Hills", 2400.00, category="Home", month=5),
    ]

    assert find_one_time_purchases(month_rows, history_rows=history, month_total=5000.0) == []


def test_a_small_purchase_never_rewrites_a_month_however_odd_it_looks():
    month_rows = [_row("gift", 3, "Unheard Of Shop", 300.00)]

    found = find_one_time_purchases(
        month_rows, history_rows=month_rows, month_total=800.0
    )

    assert found == []


def test_a_large_purchase_that_is_a_small_slice_of_the_month_is_not_the_month():
    month_rows = [_row("laptop", 3, "Unheard Of Shop", 1200.00)]

    found = find_one_time_purchases(
        month_rows, history_rows=month_rows, month_total=40000.0
    )

    assert found == []


def test_an_empty_month_reports_nothing_rather_than_dividing_by_zero():
    assert find_one_time_purchases([], history_rows=[], month_total=0.0) == []
