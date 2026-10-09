"""FIFO consumption math + holding-period bucketing for the lot ledger."""

from __future__ import annotations

from copy import deepcopy
from datetime import date

import pytest

from app.portfolio.transactions import is_long_term_holding, one_year_anniversary
from tests.portfolio.test_transactions import _make_ledger


def test_consume_lots_fifo_breaks_long_and_short_term() -> None:
    ledger, _ = _make_ledger()

    ledger.record_transaction(
        account_id="acct-1",
        symbol="AAPL",
        transaction_type="buy",
        trade_date=date(2024, 1, 1),
        shares=5.0,
        price=100.0,
    )
    ledger.record_transaction(
        account_id="acct-1",
        symbol="AAPL",
        transaction_type="buy",
        trade_date=date(2026, 3, 1),
        shares=5.0,
        price=200.0,
    )

    result = ledger.consume_lots_fifo(
        account_id="acct-1",
        symbol="AAPL",
        shares=8.0,
        sell_date=date(2026, 4, 1),
        sell_price=300.0,
    )

    # FIFO: 5 from the long-held lot, 3 from the short-held lot.
    assert result.realized_gain_long_term == 1000.0  # (300-100)*5
    assert result.realized_gain_short_term == 300.0  # (300-200)*3
    assert result.used_position_aggregate_fallback is False
    assert sum(c.shares for c in result.consumed) == 8.0
    # First consumption row is the older lot.
    assert result.consumed[0].is_long_term is True
    assert result.consumed[1].is_long_term is False


def test_preview_lots_fifo_is_repeatable_and_does_not_mutate_lots() -> None:
    ledger, store = _make_ledger()

    ledger.record_transaction(
        account_id="acct-1",
        symbol="AAPL",
        transaction_type="buy",
        trade_date=date(2024, 1, 1),
        shares=5.0,
        price=100.0,
    )
    ledger.record_transaction(
        account_id="acct-1",
        symbol="AAPL",
        transaction_type="buy",
        trade_date=date(2026, 3, 1),
        shares=5.0,
        price=200.0,
    )
    lots_before = deepcopy(store.tax_lots)
    store.queries.clear()

    first = ledger.preview_lots_fifo(
        account_id="acct-1",
        symbol="AAPL",
        shares=8.0,
        sell_date=date(2026, 4, 1),
        sell_price=300.0,
    )
    second = ledger.preview_lots_fifo(
        account_id="acct-1",
        symbol="AAPL",
        shares=8.0,
        sell_date=date(2026, 4, 1),
        sell_price=300.0,
    )

    assert first == second
    assert first.realized_gain_long_term == 1000.0
    assert first.realized_gain_short_term == 300.0
    assert store.tax_lots == lots_before
    assert not any("FOR UPDATE" in query.upper() for query in store.queries)
    assert [lot.remaining_shares for lot in ledger.open_lots("acct-1", "AAPL")] == [
        5.0,
        5.0,
    ]


def test_consume_lots_fifo_falls_back_to_position_aggregate_when_no_lots() -> None:
    ledger, store = _make_ledger()
    store.seed_position("acct-1", "AAPL", cost_basis=120.0)

    result = ledger.consume_lots_fifo(
        account_id="acct-1",
        symbol="AAPL",
        shares=10.0,
        sell_date=date(2026, 5, 1),
        sell_price=150.0,
    )

    assert result.used_position_aggregate_fallback is True
    # Conservative: aggregate gains land in the short-term bucket.
    assert result.realized_gain_long_term == 0.0
    assert result.realized_gain_short_term == 300.0
    assert len(result.consumed) == 1
    assert result.consumed[0].lot_id is None


def test_consume_lots_partial_then_aggregate_tail() -> None:
    ledger, store = _make_ledger()
    store.seed_position("acct-1", "AAPL", cost_basis=80.0)
    ledger.record_transaction(
        account_id="acct-1",
        symbol="AAPL",
        transaction_type="buy",
        trade_date=date(2024, 1, 1),
        shares=2.0,
        price=100.0,
    )

    result = ledger.consume_lots_fifo(
        account_id="acct-1",
        symbol="AAPL",
        shares=5.0,
        sell_date=date(2026, 6, 1),
        sell_price=200.0,
    )

    assert result.used_position_aggregate_fallback is True
    # Lot consumption: 2 shares LT @ 100 cost → +200 LT
    # Aggregate tail: 3 shares @ 80 cost → +360 short-term
    assert result.realized_gain_long_term == 200.0
    assert result.realized_gain_short_term == 360.0


def test_buy_creates_open_lot_with_fees_amortized_into_basis() -> None:
    ledger, store = _make_ledger()
    ledger.record_transaction(
        account_id="acct-1",
        symbol="AAPL",
        transaction_type="buy",
        trade_date=date(2026, 1, 5),
        shares=10.0,
        price=180.0,
        fees=10.0,
    )

    assert len(store.tax_lots) == 1
    lot = store.tax_lots[0]
    # Fees pro-rated into per-share basis: 180 + (10/10) = 181
    assert lot["cost_per_share"] == 181.0
    assert lot["cost_basis_total"] == 1810.0
    assert lot["remaining_shares"] == 10.0


def test_sell_decrements_lot_and_marks_disposed_when_emptied() -> None:
    ledger, store = _make_ledger()
    ledger.record_transaction(
        account_id="acct-1",
        symbol="AAPL",
        transaction_type="buy",
        trade_date=date(2024, 1, 1),
        shares=5.0,
        price=100.0,
    )
    commits_before = store.commit_count
    connections_before = store.connection_count
    store.queries.clear()
    ledger.record_transaction(
        account_id="acct-1",
        symbol="AAPL",
        transaction_type="sell",
        trade_date=date(2026, 4, 1),
        shares=5.0,
        price=200.0,
    )

    lot = store.tax_lots[0]
    assert float(lot["remaining_shares"]) == 0.0
    assert lot["disposed_at"] is not None
    assert store.commit_count - commits_before == 1
    assert store.connection_count - connections_before == 1
    assert any("FOR UPDATE" in query.upper() for query in store.queries)


def test_open_lots_skips_fully_disposed_lots() -> None:
    ledger, _ = _make_ledger()
    ledger.record_transaction(
        account_id="acct-1",
        symbol="AAPL",
        transaction_type="buy",
        trade_date=date(2024, 1, 1),
        shares=5.0,
        price=100.0,
    )
    ledger.record_transaction(
        account_id="acct-1",
        symbol="AAPL",
        transaction_type="buy",
        trade_date=date(2025, 6, 1),
        shares=5.0,
        price=150.0,
    )
    ledger.consume_lots_fifo(
        account_id="acct-1",
        symbol="AAPL",
        shares=5.0,
        sell_date=date(2026, 4, 1),
        sell_price=180.0,
    )

    open_lots = ledger.open_lots("acct-1", "AAPL")
    assert len(open_lots) == 1
    assert open_lots[0].acquired_date == date(2025, 6, 1)
    assert open_lots[0].remaining_shares == 5.0


def test_sell_fees_reduce_realized_gain() -> None:
    ledger, store = _make_ledger()
    ledger.record_transaction(
        account_id="acct-1",
        symbol="AAPL",
        transaction_type="buy",
        trade_date=date(2024, 1, 1),
        shares=10.0,
        price=100.0,
        fees=10.0,
    )
    sell_id = ledger.record_transaction(
        account_id="acct-1",
        symbol="AAPL",
        transaction_type="sell",
        trade_date=date(2026, 1, 2),
        shares=10.0,
        price=150.0,
        fees=20.0,
    )

    sell = next(row for row in store.transactions if row["id"] == sell_id)
    # proceeds 1500 - sell fee 20 - basis (1000 + buy fee 10) = 470
    assert sell["realized_gain"] == 470.0


def test_sell_fees_allocated_pro_rata_across_consumed_lots() -> None:
    ledger, _ = _make_ledger()
    ledger.record_transaction(
        account_id="acct-1",
        symbol="AAPL",
        transaction_type="buy",
        trade_date=date(2024, 1, 1),
        shares=5.0,
        price=100.0,
    )
    ledger.record_transaction(
        account_id="acct-1",
        symbol="AAPL",
        transaction_type="buy",
        trade_date=date(2026, 3, 1),
        shares=5.0,
        price=200.0,
    )

    result = ledger.consume_lots_fifo(
        account_id="acct-1",
        symbol="AAPL",
        shares=8.0,
        sell_date=date(2026, 4, 1),
        sell_price=300.0,
        fees=8.0,
    )

    # Fee split by shares: 5/8 * 8 = 5 to the LT lot, 3 to the ST lot.
    assert result.realized_gain_long_term == 995.0
    assert result.realized_gain_short_term == 297.0
    assert [c.proceeds for c in result.consumed] == [1495.0, 897.0]
    assert result.total_proceeds == 2392.0
    assert result.total_realized_gain == 1292.0


def test_sell_without_any_basis_source_records_unknown_gain() -> None:
    ledger, store = _make_ledger()

    result = ledger.preview_lots_fifo(
        account_id="acct-1",
        symbol="AAPL",
        shares=10.0,
        sell_date=date(2026, 5, 1),
        sell_price=150.0,
    )
    assert result.used_position_aggregate_fallback is True
    assert result.basis_unknown is True
    assert result.unknown_basis_shares == 10.0
    assert result.total_realized_gain is None
    assert result.consumed[0].cost_basis is None
    assert result.consumed[0].realized_gain is None
    # No fabricated full-proceeds gain in the buckets.
    assert result.realized_gain_short_term == 0.0

    sell_id = ledger.record_transaction(
        account_id="acct-1",
        symbol="AAPL",
        transaction_type="sell",
        trade_date=date(2026, 5, 1),
        shares=10.0,
        price=150.0,
    )
    sell = next(row for row in store.transactions if row["id"] == sell_id)
    assert sell["realized_gain"] is None

    ytd = ledger.realized_gains_ytd("acct-1", 2026)
    assert ytd["total"] == 0.0
    assert ytd["unknown_gain_sells"] == 1


def test_partial_lots_without_position_marks_whole_sell_unknown() -> None:
    ledger, store = _make_ledger()
    ledger.record_transaction(
        account_id="acct-1",
        symbol="AAPL",
        transaction_type="buy",
        trade_date=date(2024, 1, 1),
        shares=2.0,
        price=100.0,
    )
    sell_id = ledger.record_transaction(
        account_id="acct-1",
        symbol="AAPL",
        transaction_type="sell",
        trade_date=date(2026, 6, 1),
        shares=5.0,
        price=200.0,
    )
    sell = next(row for row in store.transactions if row["id"] == sell_id)
    assert sell["realized_gain"] is None


def test_backdated_buy_replays_fifo_for_later_sells() -> None:
    ledger, store = _make_ledger()
    ledger.record_transaction(
        account_id="acct-1",
        symbol="AAPL",
        transaction_type="buy",
        trade_date=date(2024, 1, 1),
        shares=10.0,
        price=100.0,
    )
    sell_id = ledger.record_transaction(
        account_id="acct-1",
        symbol="AAPL",
        transaction_type="sell",
        trade_date=date(2026, 1, 2),
        shares=5.0,
        price=200.0,
    )
    sell = next(row for row in store.transactions if row["id"] == sell_id)
    assert sell["realized_gain"] == 500.0

    commits_before = store.commit_count
    ledger.record_transaction(
        account_id="acct-1",
        symbol="AAPL",
        transaction_type="buy",
        trade_date=date(2023, 1, 3),
        shares=5.0,
        price=50.0,
    )

    # FIFO now consumes the older (backdated) lot: (200 - 50) * 5.
    assert sell["realized_gain"] == 750.0
    open_lots = ledger.open_lots("acct-1", "AAPL")
    assert [(lot.acquired_date, lot.remaining_shares) for lot in open_lots] == [
        (date(2024, 1, 1), 10.0)
    ]
    backdated = next(lot for lot in store.tax_lots if lot["acquired_date"] == date(2023, 1, 3))
    assert backdated["disposed_at"] is not None
    reopened = next(lot for lot in store.tax_lots if lot["acquired_date"] == date(2024, 1, 1))
    assert reopened["disposed_at"] is None
    # Insert + replay share one DB transaction.
    assert store.commit_count - commits_before == 1


def test_backdated_sell_replays_in_trade_date_order() -> None:
    ledger, store = _make_ledger()
    for trade_date, price in ((date(2024, 1, 1), 100.0), (date(2025, 1, 2), 150.0)):
        ledger.record_transaction(
            account_id="acct-1",
            symbol="AAPL",
            transaction_type="buy",
            trade_date=trade_date,
            shares=5.0,
            price=price,
        )
    later_id = ledger.record_transaction(
        account_id="acct-1",
        symbol="AAPL",
        transaction_type="sell",
        trade_date=date(2026, 6, 1),
        shares=5.0,
        price=200.0,
    )
    earlier_id = ledger.record_transaction(
        account_id="acct-1",
        symbol="AAPL",
        transaction_type="sell",
        trade_date=date(2025, 6, 1),
        shares=5.0,
        price=180.0,
    )
    by_id = {row["id"]: row for row in store.transactions}
    # Earlier sell takes the 2024 lot, later sell the 2025 lot.
    assert by_id[earlier_id]["realized_gain"] == 400.0
    assert by_id[later_id]["realized_gain"] == 250.0
    assert ledger.open_lots("acct-1", "AAPL") == []


@pytest.mark.parametrize(
    ("acquired", "sold", "expected"),
    [
        (date(2023, 3, 1), date(2024, 3, 1), False),
        (date(2023, 3, 1), date(2024, 3, 2), True),
        (date(2024, 2, 29), date(2025, 2, 28), False),
        (date(2024, 2, 29), date(2025, 3, 1), True),
    ],
)
def test_long_term_uses_calendar_anniversary(
    acquired: date, sold: date, expected: bool
) -> None:
    assert is_long_term_holding(acquired, sold) is expected


def test_one_year_anniversary_maps_leap_day_to_feb_28() -> None:
    assert one_year_anniversary(date(2024, 2, 29)) == date(2025, 2, 28)
    assert one_year_anniversary(date(2023, 3, 1)) == date(2024, 3, 1)


@pytest.mark.parametrize(
    ("sold", "expect_long_term"),
    [(date(2024, 3, 1), False), (date(2024, 3, 2), True)],
)
def test_fifo_holding_period_across_leap_year(sold: date, expect_long_term: bool) -> None:
    ledger, _ = _make_ledger()
    ledger.record_transaction(
        account_id="acct-1",
        symbol="AAPL",
        transaction_type="buy",
        trade_date=date(2023, 3, 1),
        shares=1.0,
        price=100.0,
    )
    result = ledger.preview_lots_fifo(
        account_id="acct-1",
        symbol="AAPL",
        shares=1.0,
        sell_date=sold,
        sell_price=150.0,
    )
    assert result.consumed[0].is_long_term is expect_long_term
    if expect_long_term:
        assert result.realized_gain_long_term == 50.0
    else:
        assert result.realized_gain_short_term == 50.0


def test_fractional_share_residue_does_not_trigger_aggregate_fallback() -> None:
    ledger, store = _make_ledger()
    # In float math 0.8 - 0.7 = 0.10000000000000009 > 0.1, leaving a ~1e-16
    # remainder that used to force the position-aggregate fallback.
    for trade_date, shares in ((date(2024, 1, 1), 0.7), (date(2024, 2, 1), 0.1)):
        ledger.record_transaction(
            account_id="acct-1",
            symbol="AAPL",
            transaction_type="buy",
            trade_date=trade_date,
            shares=shares,
            price=100.0,
        )

    result = ledger.consume_lots_fifo(
        account_id="acct-1",
        symbol="AAPL",
        shares=0.8,
        sell_date=date(2026, 1, 2),
        sell_price=200.0,
    )

    assert result.used_position_aggregate_fallback is False
    assert result.basis_unknown is False
    assert result.total_shares == 0.8
    assert result.realized_gain_long_term == 80.0
    assert ledger.open_lots("acct-1", "AAPL") == []
    assert all(lot["disposed_at"] is not None for lot in store.tax_lots)
