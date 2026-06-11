"""Unit tests for the FedWatch-style fed-funds futures odds."""

from __future__ import annotations

from datetime import UTC, date, datetime

from app.macro_gate import fed_odds


def test_zq_symbol_uses_cme_month_codes() -> None:
    assert fed_odds._zq_symbol(2026, 6) == "ZQM26.CBT"
    assert fed_odds._zq_symbol(2026, 12) == "ZQZ26.CBT"
    assert fed_odds._zq_symbol(2027, 1) == "ZQF27.CBT"


def test_solve_post_meeting_rate_blended_month() -> None:
    # June 2026 (30 days), meeting on the 17th: 17 pre days at 3.62, 13 post
    # days at r_post. Contract priced for a clean 25bp cut to 3.37:
    # month avg = (17*3.62 + 13*3.37)/30 -> price = 100 - avg.
    month_avg = (17 * 3.62 + 13 * 3.37) / 30
    rate = fed_odds._solve_post_meeting_rate(
        meeting=date(2026, 6, 17),
        effr=3.62,
        meeting_month_price=100.0 - month_avg,
        next_month_price=None,
    )
    assert rate is not None
    assert abs(rate - 3.37) < 1e-9


def test_solve_post_meeting_rate_late_month_falls_back_to_next_contract() -> None:
    # Oct 28 meeting leaves only 3 post days — meeting-month algebra is too
    # noisy, so the November contract prices the new rate directly.
    rate = fed_odds._solve_post_meeting_rate(
        meeting=date(2026, 10, 28),
        effr=3.62,
        meeting_month_price=96.30,
        next_month_price=96.50,
    )
    assert rate == 3.5


def test_solve_post_meeting_rate_returns_none_without_quotes() -> None:
    assert (
        fed_odds._solve_post_meeting_rate(
            meeting=date(2026, 6, 17),
            effr=3.62,
            meeting_month_price=None,
            next_month_price=None,
        )
        is None
    )


def test_move_odds_buckets() -> None:
    assert fed_odds._move_odds(3.62, 3.62) == (0, 100, 0)
    # half a cut priced
    assert fed_odds._move_odds(3.495, 3.62) == (50, 50, 0)
    # full cut (or more) caps at 100
    assert fed_odds._move_odds(3.30, 3.62) == (100, 0, 0)
    # hikes mirror cuts
    p_cut, p_hold, p_hike = fed_odds._move_odds(3.745, 3.62)
    assert (p_cut, p_hike) == (0, 50)
    assert p_hold == 50


def test_get_fed_odds_assembles_payload(monkeypatch) -> None:
    monkeypatch.setattr(fed_odds, "_latest_effr", lambda: 3.62)
    monkeypatch.setattr(fed_odds, "_next_fomc_date", lambda _today: date(2026, 6, 17))
    month_avg = (17 * 3.62 + 13 * 3.37) / 30
    monkeypatch.setattr(
        fed_odds,
        "_quote_prices",
        lambda _symbols: {
            "ZQM26.CBT": (100.0 - month_avg, "2026-06-11T04:00:00+00:00"),
            "ZQF27.CBT": (96.12, "2026-06-11T04:10:00+00:00"),
        },
    )

    odds = fed_odds.get_fed_odds(datetime(2026, 6, 11, 0, 30, tzinfo=UTC))

    assert odds is not None
    assert odds.meeting_date == "2026-06-17"
    assert odds.implied_post_rate == 3.37
    assert (odds.p_cut, odds.p_hold, odds.p_hike) == (100, 0, 0)
    assert odds.year_end_rate == 3.88
    # negative cuts == hikes priced by December
    assert odds.cuts_priced_by_year_end == -1.0
    assert odds.as_of == "2026-06-11T04:10:00+00:00"


def test_get_fed_odds_returns_none_when_inputs_missing(monkeypatch) -> None:
    monkeypatch.setattr(fed_odds, "_latest_effr", lambda: None)
    monkeypatch.setattr(fed_odds, "_next_fomc_date", lambda _today: date(2026, 6, 17))
    assert fed_odds.get_fed_odds(datetime(2026, 6, 11, tzinfo=UTC)) is None
