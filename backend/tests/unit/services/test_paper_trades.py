"""Unit tests for the committee paper-trade service.

The Approve & Execute path runs entirely in-process: read committee_runs
row → look up latest day_bars close → size from portfolio_positions →
INSERT into paper_trades → UPDATE committee_runs to 'approved'. These
tests pin the SQL/shape contract without requiring a live DB.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.services import paper_trades


def _fake_connection_manager(*, rows: list[Any], capture: dict[str, list[tuple[str, tuple]]]):
    fake_conn = MagicMock()

    def _execute(sql: str, params: tuple = ()) -> MagicMock:
        capture.setdefault("calls", []).append((sql, params))
        normalized = " ".join(sql.split())
        result = MagicMock()
        if normalized.startswith("SELECT symbol, household_id, status"):
            result.fetchone.return_value = rows[0]
        elif "FROM day_bars" in normalized:
            result.fetchone.return_value = rows[1]
        elif "FROM portfolio_positions" in normalized:
            result.fetchone.return_value = rows[2]
        else:
            result.fetchone.return_value = None
        return result

    fake_conn.execute.side_effect = _execute

    @contextmanager
    def fake_connection():
        yield fake_conn

    mgr = MagicMock()
    mgr.connection.side_effect = fake_connection
    return mgr


def test_execute_from_run_writes_paper_trade_and_approves_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """A completed BUY decision produces a paper_trades row sized from portfolio_value."""
    run_id = "11111111-1111-1111-1111-111111111111"
    capture: dict[str, list[tuple[str, tuple]]] = {}

    rows = [
        # committee_runs row: symbol, household_id, status, decision_action, decision_pct_portfolio
        ("aapl", None, "complete", "buy", 0.04),
        # day_bars latest close
        (200.0,),
        # portfolio_value sum
        (250_000.0,),
    ]
    fake_mgr = _fake_connection_manager(rows=rows, capture=capture)
    monkeypatch.setattr(paper_trades, "get_connection_manager", lambda: fake_mgr)

    trade = paper_trades.execute_from_run(run_id)

    # 50 shares: 250000 * 0.04 / 200 = 50
    assert trade.symbol == "AAPL"
    assert trade.action == "buy"
    assert trade.qty == 50.0
    assert trade.price == 200.0
    assert trade.run_id == run_id

    insert_calls = [c for c in capture["calls"] if "INSERT INTO paper_trades" in c[0]]
    assert len(insert_calls) == 1
    _, insert_params = insert_calls[0]
    # id, run_id, household_id, symbol, action, qty, price
    assert insert_params[1] == run_id
    assert insert_params[3] == "AAPL"
    assert insert_params[4] == "buy"
    assert insert_params[5] == 50  # rounded shares
    assert insert_params[6] == 200.0

    approval_calls = [c for c in capture["calls"] if "UPDATE committee_runs" in c[0]]
    assert len(approval_calls) == 1
    _, approval_params = approval_calls[0]
    assert approval_params == (50, 200.0, run_id)


def test_execute_from_run_rejects_hold(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [("nvda", None, "complete", "hold", 0.0), None, None]
    capture: dict[str, list[tuple[str, tuple]]] = {}
    fake_mgr = _fake_connection_manager(rows=rows, capture=capture)
    monkeypatch.setattr(paper_trades, "get_connection_manager", lambda: fake_mgr)

    with pytest.raises(paper_trades.PaperTradeError, match="nothing to execute"):
        paper_trades.execute_from_run("run-1")


def test_execute_from_run_rejects_uncompleted_run(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [("nvda", None, "running", "buy", 0.04), None, None]
    capture: dict[str, list[tuple[str, tuple]]] = {}
    fake_mgr = _fake_connection_manager(rows=rows, capture=capture)
    monkeypatch.setattr(paper_trades, "get_connection_manager", lambda: fake_mgr)

    with pytest.raises(paper_trades.PaperTradeError, match="expected 'complete'"):
        paper_trades.execute_from_run("run-2")


def test_execute_from_run_rejects_missing_price(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [("nvda", None, "complete", "buy", 0.04), None, (250_000.0,)]
    capture: dict[str, list[tuple[str, tuple]]] = {}
    fake_mgr = _fake_connection_manager(rows=rows, capture=capture)
    monkeypatch.setattr(paper_trades, "get_connection_manager", lambda: fake_mgr)

    with pytest.raises(paper_trades.PaperTradeError, match="no day_bars close"):
        paper_trades.execute_from_run("run-3")


def test_execute_from_run_rejects_zero_portfolio_value(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [("nvda", None, "complete", "buy", 0.04), (200.0,), (0.0,)]
    capture: dict[str, list[tuple[str, tuple]]] = {}
    fake_mgr = _fake_connection_manager(rows=rows, capture=capture)
    monkeypatch.setattr(paper_trades, "get_connection_manager", lambda: fake_mgr)

    with pytest.raises(paper_trades.PaperTradeError, match="portfolio_value is zero"):
        paper_trades.execute_from_run("run-4")


def test_update_pnl_for_open_walks_open_trades(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nightly P/L scan touches every paper_trades.closed_at IS NULL row."""
    capture: dict[str, list[tuple[str, tuple]]] = {"calls": []}
    fake_conn = MagicMock()

    open_rows = [
        ("p1", "AAPL", "buy", 50.0, 200.0),
        ("p2", "NVDA", "sell", 10.0, 1000.0),
    ]

    def _execute(sql: str, params: tuple = ()) -> MagicMock:
        capture["calls"].append((sql, params))
        normalized = " ".join(sql.split())
        result = MagicMock()
        if normalized.startswith("SELECT id, symbol, action, qty, price"):
            result.fetchall.return_value = open_rows
        elif "FROM day_bars" in normalized:
            symbol = params[0]
            close_map = {"AAPL": 210.0, "NVDA": 950.0}
            result.fetchone.return_value = (close_map[symbol],)
        else:
            result.fetchone.return_value = None
        return result

    fake_conn.execute.side_effect = _execute

    @contextmanager
    def fake_connection():
        yield fake_conn

    mgr = MagicMock()
    mgr.connection.side_effect = fake_connection
    monkeypatch.setattr(paper_trades, "get_connection_manager", lambda: mgr)

    summary = paper_trades.update_pnl_for_open()

    assert summary["open_count"] == 2
    assert summary["updated"] == 2
    assert summary["skipped_no_price"] == []

    update_calls = [c for c in capture["calls"] if "UPDATE paper_trades" in c[0]]
    assert len(update_calls) == 2
    # AAPL buy: (210-200)*50 = 500; NVDA sell: -(950-1000)*10 = 500
    pnls = {c[1][2]: c[1][1] for c in update_calls}
    assert pnls["p1"] == pytest.approx(500.0)
    assert pnls["p2"] == pytest.approx(500.0)
