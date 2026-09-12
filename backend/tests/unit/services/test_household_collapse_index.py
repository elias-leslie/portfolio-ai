"""The amount index must preserve the prior ordered reconciliation semantics."""

import random
from datetime import date, timedelta

from app.services import _household_report_builder as reports


def reference_collapse(rows):
    kept, excluded, absorbed = [], {}, set()
    for row in sorted(rows, key=reports.report_row_priority):
        plain = reports._is_plain_charge_row(row)
        for previous in kept:
            if plain and id(previous) in absorbed:
                continue
            reason = reports.report_row_exclusion_reason(previous, row)
            if reason:
                key = str(row.get("row_hash") or row.get("id") or "")
                if key:
                    excluded[key] = reason
                if plain:
                    absorbed.add(id(previous))
                break
        else:
            kept.append(row)
    return kept, excluded


def test_amount_index_preserves_boundary_refund_account_and_absorption_results():
    rng = random.Random(17)
    rows = [
        {
            "id": str(index),
            "row_hash": f"hash-{index}",
            "date": date(2026, 8, 1) + timedelta(days=rng.randrange(7)),
            "amount": rng.choice([10, 10.005, 9.995, 9.999, 10.001, -10, -9.999, 20]),
            "source_kind": rng.choice(["import", "transaction"]),
            "document_type": rng.choice(["receipt", "bank_statement"]),
            "document_id": str(index),
            "source_type": rng.choice(["receipt", "bank"]),
            "merchant": rng.choice(["Walmart", "Publix"]),
            "household_account_id": rng.choice(["one", "two", None]),
        }
        for index in range(250)
    ]
    assert reports.collapse_report_rows_with_exclusions(rows) == reference_collapse(rows)


def test_unrelated_amounts_are_not_pairwise_compared(monkeypatch):
    calls = 0
    original = reports.report_row_exclusion_reason

    def counted(first, second):
        nonlocal calls
        calls += 1
        return original(first, second)

    monkeypatch.setattr(reports, "report_row_exclusion_reason", counted)
    rows = [
        {"id": str(i), "amount": i * 10, "source_kind": "transaction", "date": date(2026, 8, 1)}
        for i in range(2000)
    ]
    assert reports.collapse_report_rows(rows) == rows
    assert calls == 0
