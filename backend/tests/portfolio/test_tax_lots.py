"""FIFO consumption math + holding-period bucketing for the lot ledger."""

from __future__ import annotations

from copy import deepcopy
from datetime import date

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
