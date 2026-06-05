"""Unit tests for current-session intraday ingestion helpers."""

from __future__ import annotations

import datetime as dt

import polars as pl

from app.tasks.ingestion.intraday_ingestion import _latest_session_only


def test_latest_session_only_keeps_each_symbols_newest_session() -> None:
    frame = pl.DataFrame(
        {
            "symbol": ["AAPL", "AAPL", "MSFT"],
            "session_date": [dt.date(2026, 6, 4), dt.date(2026, 6, 5), dt.date(2026, 6, 3)],
            "close": [1.0, 2.0, 3.0],
        }
    )

    out = _latest_session_only(frame)
    by_symbol = {row["symbol"]: row for row in out.iter_rows(named=True)}

    assert out.height == 2
    # AAPL's stale 06-04 bar is dropped in favor of its 06-05 session.
    assert by_symbol["AAPL"]["session_date"] == dt.date(2026, 6, 5)
    assert by_symbol["AAPL"]["close"] == 2.0
    # MSFT only has one session, which is kept as-is.
    assert by_symbol["MSFT"]["session_date"] == dt.date(2026, 6, 3)
