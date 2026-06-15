"""Unit tests for income-stream auto-detection from the Money ledger (item E)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.services.retirement_income_actuals_service import (
    derive_income_actuals,
)
from app.services.retirement_spending_actuals_service import (
    MIN_ROWS_PER_COVERED_MONTH,
)

TODAY = date(2026, 6, 11)


def _row(
    day: date,
    amount: float,
    *,
    merchant: str = "ACME PAYROLL 12345 DOE JANE",
    account: str = "acct-a",
    source: str = "bank_statement",
) -> dict[str, Any]:
    return {
        "date": day,
        "merchant": merchant,
        "description": merchant,
        "amount": amount,
        "account_id": account,
        "source_system": source,
    }


def _coverage(months: list[tuple[int, int]]) -> list[date]:
    dates: list[date] = []
    for year, month in months:
        dates.extend(
            date(year, month, min(d + 1, 28)) for d in range(MIN_ROWS_PER_COVERED_MONTH)
        )
    return dates


FOUR_MONTHS = _coverage([(2026, 2), (2026, 3), (2026, 4), (2026, 5)])


def test_sparse_income_rows_ride_overall_ledger_coverage() -> None:
    # Two income rows/month would never pass the spend row gate on their own;
    # the window comes from overall ledger coverage instead.
    rows = [
        _row(date(2026, m, 5), 2900.0) for m in (2, 3, 4, 5)
    ] + [
        _row(date(2026, m, 19), 2900.0) for m in (2, 3, 4, 5)
    ]
    # Current partial month must not count.
    rows.append(_row(date(2026, 6, 5), 999.0))

    actuals = derive_income_actuals(rows, coverage_dates=FOUR_MONTHS, today=TODAY)

    assert actuals.first_month == "2026-02"
    assert actuals.last_month == "2026-05"
    assert actuals.coverage_months == 4
    assert actuals.total_monthly_income == 5800.0
    assert len(actuals.streams) == 1
    stream = actuals.streams[0]
    assert stream.cadence == "biweekly"
    assert stream.monthly_average == 5800.0
    assert stream.run_rate_monthly == 6283.33
    assert stream.active is True
    assert stream.status == "active"
    assert actuals.active_monthly_income == 6283.33


def test_alias_twins_collapse_but_same_account_pairs_survive() -> None:
    rows = [
        # The same paycheck ingested twice: PDF statement on one account
        # label, CSV export on another. Case differences only.
        _row(
            date(2026, 5, 8),
            1000.0,
            merchant="Pinellas County Payroll 260508 Leslie Mariana",
            account="acct-a",
            source="bank_statement",
        ),
        _row(
            date(2026, 5, 9),
            1000.0,
            merchant="PINELLAS COUNTY  PAYROLL    260508  LESLIE  MARIANA",
            account="acct-b",
            source="statement_csv",
        ),
        # Two REAL same-day same-amount payouts on one account must survive.
        _row(date(2026, 5, 8), 17.27, merchant="Depop", account="acct-c", source="plaid"),
        _row(date(2026, 5, 8), 17.27, merchant="Depop", account="acct-c", source="plaid"),
    ]

    actuals = derive_income_actuals(
        rows, coverage_dates=_coverage([(2026, 5)]), today=TODAY
    )

    assert actuals.alias_rows_collapsed == 1
    by_label = {s.label: s for s in actuals.streams}
    assert by_label["Depop"].transaction_count == 2
    assert by_label["Depop"].total == 34.54
    payroll = next(s for s in actuals.streams if "Pinellas" in s.label)
    assert payroll.transaction_count == 1
    assert payroll.total == 1000.0


def test_alias_collapse_absorbs_one_twin_per_origin() -> None:
    # acct-b has TWO real 500.00 deposits the same day; acct-a's statement
    # only caught one. The alias collapse may absorb one acct-b row into the
    # acct-a row, but the second acct-b row is real multiplicity.
    rows = [
        _row(date(2026, 5, 4), 500.0, merchant="FL DEO UI BENEFIT XXXXX LESLIE", account="acct-a"),
        _row(
            date(2026, 5, 4),
            500.0,
            merchant="FL DEO UI BENEFIT XXXXX LESLIE",
            account="acct-b",
            source="statement_csv",
        ),
        _row(
            date(2026, 5, 4),
            500.0,
            merchant="FL DEO UI BENEFIT XXXXX LESLIE",
            account="acct-b",
            source="statement_csv",
        ),
    ]

    actuals = derive_income_actuals(
        rows, coverage_dates=_coverage([(2026, 5)]), today=TODAY
    )

    assert actuals.alias_rows_collapsed == 1
    assert actuals.streams[0].transaction_count == 2
    assert actuals.streams[0].total == 1000.0


def test_ended_stream_goes_inactive_and_averages_over_its_own_span() -> None:
    # Biweekly paychecks Feb-Mar that then stop; window runs through May.
    rows = []
    day = date(2026, 2, 6)
    while day <= date(2026, 3, 20):
        rows.append(_row(day, 2000.0))
        day += timedelta(days=14)

    actuals = derive_income_actuals(rows, coverage_dates=FOUR_MONTHS, today=TODAY)

    stream = actuals.streams[0]
    assert stream.cadence == "biweekly"
    assert stream.active is False  # last seen Mar 20, window ends May 31
    assert stream.status == "stopped"
    assert stream.months_spanned == 2
    # 4 paychecks (2/6, 2/20, 3/6, 3/20) over its own 2-month span.
    assert stream.monthly_average == 4000.0
    # Inactive streams stay out of the take-home headline.
    assert actuals.active_monthly_income == 0.0
    # But the window-wide average still includes them.
    assert actuals.total_monthly_income == 2000.0


def test_owner_attribution_and_one_off_and_portfolio_yield() -> None:
    rows = [
        _row(
            date(2026, 5, 6),
            2900.0,
            merchant="PINELLAS COUNTY PAYROLL 260506 LESLIE MARIANA",
        ),
        # One-off refund mislabeled as income: single transaction.
        _row(date(2026, 5, 17), 276.99, merchant="PROG SELECT INS PREM ELIAS LESLIE"),
        # Dividend stream: listed, tagged, excluded from take-home.
        _row(date(2026, 5, 29), 56.80, merchant="DIVIDEND RECEIVED FIDELITY MMKT (SPAXX)"),
    ]

    actuals = derive_income_actuals(
        rows,
        coverage_dates=_coverage([(2026, 5)]),
        today=TODAY,
        owner_names=["Mariana", "Elias"],
    )

    by_label = {s.label: s for s in actuals.streams}
    payroll = next(s for s in actuals.streams if "PINELLAS" in s.label)
    assert payroll.owner == "Mariana"
    one_off = next(s for s in actuals.streams if "PROG" in s.label)
    assert one_off.owner == "Elias"
    assert one_off.cadence == "one-off"
    assert one_off.active is False
    assert one_off.status == "one_off"
    dividend = next(s for s in actuals.streams if "DIVIDEND" in s.label)
    assert dividend.portfolio_yield is True
    assert dividend.status == "portfolio_yield"
    assert dividend.owner is None
    # Take-home headline: nothing qualifies (payroll is one-off here too).
    assert actuals.active_monthly_income == 0.0
    assert len(by_label) == 3


def test_monthly_stream_at_window_end_is_active() -> None:
    rows = [
        _row(
            date(2026, m, 28),
            90.0,
            merchant="DIVIDEND RECEIVED FIDELITY MMKT (SPAXX)",
        )
        for m in (2, 3, 4)
    ]
    # Window ends May; dividend last seen Apr 28 — inside 2x ~30-day gap.
    actuals = derive_income_actuals(rows, coverage_dates=FOUR_MONTHS, today=TODAY)

    stream = actuals.streams[0]
    assert stream.cadence == "monthly"
    assert stream.active is True
    assert stream.portfolio_yield is True
    assert stream.status == "portfolio_yield"
    # Portfolio yield never counts toward take-home even when active.
    assert actuals.active_monthly_income == 0.0


def test_manual_overrides_owner_status_and_merge_target() -> None:
    rows = [
        _row(
            date(2026, m, 5),
            2900.0,
            merchant="PINELLAS COUNTY PAYROLL 260506 LESLIE MARIANA",
        )
        for m in (2, 3, 4, 5)
    ]
    auto = derive_income_actuals(
        rows,
        coverage_dates=FOUR_MONTHS,
        today=TODAY,
        owner_names=["Mariana", "Elias"],
    )
    stream_key = auto.streams[0].stream_key

    stopped = derive_income_actuals(
        rows,
        coverage_dates=FOUR_MONTHS,
        today=TODAY,
        owner_names=["Mariana", "Elias"],
        overrides={stream_key: {"owner_name": "Elias", "status": "stopped"}},
    )

    stream = stopped.streams[0]
    assert stream.owner == "Elias"
    assert stream.owner_override is True
    assert stream.status == "stopped"
    assert stream.status_override == "stopped"
    assert stream.active is False
    assert stopped.active_monthly_income == 0.0

    merged = derive_income_actuals(
        rows,
        coverage_dates=FOUR_MONTHS,
        today=TODAY,
        overrides={
            stream_key: {
                "status": "merged",
                "merged_into_stream_key": "replacement-stream",
            }
        },
    )
    assert merged.streams[0].status == "merged"
    assert merged.streams[0].merged_into_stream_key == "replacement-stream"


def test_no_coverage_returns_empty() -> None:
    actuals = derive_income_actuals(
        [_row(date(2026, 5, 5), 100.0)], coverage_dates=[], today=TODAY
    )
    assert actuals.coverage_months == 0
    assert actuals.streams == []
    assert "No complete months" in actuals.source_label
