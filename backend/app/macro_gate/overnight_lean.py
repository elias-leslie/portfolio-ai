"""Overnight Lean — forward, off-hours risk read from globally-traded instruments.

When U.S. cash markets are shut, the cash indices (``^TNX``/``^VIX``/``DX-Y.NYB``)
only carry the last settle, so they read ~0% off-hours. But the FUTURES on the same
risk drivers keep trading — equity-index, crude, gold and the 10Y note futures run
on CME Globex (Sun 18:00 ET -> Fri 17:00 ET, with a daily 17:00-18:00 ET maintenance
halt) — and crypto is 24/7. This module reads those live instruments and synthesises
a plain-English risk-on / risk-off lean for the session ahead.

It is intentionally honest about the dark spots:
- On weekends every futures market is shut, so the lean is Bitcoin-only and says so.
- VIX-futures (``VX=F``) and the dollar-index future (``DX=F``) are not served by any
  configured data source, so the fear gauge and the dollar are represented as
  "updates at the open" — never faked from a stale settle.

The amateur-facing surface is deliberately small: one direction + confidence +
one sentence. The full per-instrument detail lives in the trend panel. Off-hours
the read also contributes a calibrated stress score that the headline caution
number absorbs (max-only, never below the macro/held-tape floor); during regular
trading hours the live cash tape rules and this never touches caution.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time

import structlog

from app.constants import (
    CRYPTO_BTC,
    FUTURES_10Y,
    FUTURES_CRUDE,
    FUTURES_GOLD,
    FUTURES_NASDAQ,
    FUTURES_SP500,
    OVERNIGHT_LEAN_SYMBOLS,
)
from app.macro_gate.conditions import _current_quote_changes, _stress_from_decline
from app.portfolio.price_fetcher import PriceDataFetcher
from app.storage.facade import get_storage
from app.utils._market_calendar import NY_TZ
from app.utils.market_hours import get_market_status

logger = structlog.get_logger(__name__)

# Move-size bands (percent). Below FLAT the move is noise; at/above STRONG it is a
# decisive lean. Tuned for overnight futures, which move in smaller increments than
# a full RTH session.
_FLAT_BAND = 0.2
_STRONG_BAND = 0.7

# A crude move this large (up OR down) is treated as a geopolitical / inflation
# shock worth flagging — the kind of oil spike that moved markets during the Iran
# conflict. Big oil = caution, regardless of the equity lean.
_OIL_WATCH_PCT = 1.5

# Off-hours stress is capped so a thin overnight print can never alone scream
# "defensive"; it can only nudge caution within an honest band.
_STRESS_FLOOR = 15.0
_STRESS_CAP = 85.0
_OIL_STRESS_BUMP = 10.0
_WEEKEND_CRYPTO_STRESS_CAP = 45.0


@dataclass(frozen=True, slots=True)
class _SignalSpec:
    key: str
    label: str
    symbol: str
    # True  -> up means risk-on (equities, crypto)
    # False -> up means risk-off (gold, Treasuries bid = flight to safety)
    # None  -> watch-only, no risk-on/off vote (oil — direction is ambiguous)
    risk_on_when_up: bool | None
    in_vote: bool = True  # NQ rides with ES so equities count once in the tally
    always_live: bool = False  # crypto trades 24/7


# Display order mirrors OVERNIGHT_LEAN_SYMBOLS: equities, oil, gold, rates, crypto.
_SIGNAL_SPECS: tuple[_SignalSpec, ...] = (
    _SignalSpec("stocks_sp", "S&P 500 futures", FUTURES_SP500, True),
    _SignalSpec("stocks_nq", "Nasdaq futures", FUTURES_NASDAQ, True, in_vote=False),
    _SignalSpec("oil", "Oil (WTI)", FUTURES_CRUDE, None),
    _SignalSpec("gold", "Gold", FUTURES_GOLD, False),
    _SignalSpec("rates", "10Y Treasury", FUTURES_10Y, False),
    _SignalSpec("crypto", "Bitcoin", CRYPTO_BTC, True, always_live=True),
)


@dataclass(frozen=True, slots=True)
class LeanSignal:
    key: str
    label: str
    symbol: str
    change_pct: float | None
    direction: str  # "risk_on" | "risk_off" | "neutral" | "closed" | "unavailable"
    magnitude: str  # "flat" | "mild" | "strong" | "unavailable"
    live: bool
    note: str | None = None


@dataclass(frozen=True, slots=True)
class OvernightLean:
    applies: bool  # True off-hours, when the forward read is the relevant signal
    session: str  # "overnight" | "weekend" | "halt" | "rth"
    session_label: str
    direction: str  # "risk_on" | "risk_off" | "neutral" | "unavailable"
    confidence: int  # number of live dimensions agreeing with the direction
    live_count: int  # number of live voting dimensions (the confidence base)
    headline: str
    stress_score: int | None  # off-hours caution contribution (0-100), else None
    signals: list[LeanSignal]
    note: str | None  # honest-gap note (VIX / dollar)
    as_of: str | None


def _magnitude(change_pct: float) -> str:
    size = abs(change_pct)
    if size < _FLAT_BAND:
        return "flat"
    if size < _STRONG_BAND:
        return "mild"
    return "strong"


def _risk_direction(change_pct: float, risk_on_when_up: bool) -> str:
    if abs(change_pct) < _FLAT_BAND:
        return "neutral"
    moved_up = change_pct > 0
    risk_on = moved_up if risk_on_when_up else not moved_up
    return "risk_on" if risk_on else "risk_off"


def _futures_session(now: datetime) -> tuple[bool, str, str]:
    """Return (futures_live, session_key, human_label) for CME Globex.

    Globex runs Sun 18:00 ET -> Fri 17:00 ET with a daily 17:00-18:00 ET
    maintenance halt. Weekends (Fri 17:00 -> Sun 18:00) are the only true void,
    when nothing but crypto trades. Futures holidays are not modelled (v1).
    """
    moment = now.astimezone(NY_TZ)
    weekday = moment.weekday()  # Mon=0 .. Sun=6
    clock = moment.time()
    weekend_label = "Weekend — U.S. futures reopen Sun 6 PM ET"

    if weekday == 5:  # Saturday
        return False, "weekend", weekend_label
    if weekday == 6:  # Sunday
        if clock < time(18, 0):
            return False, "weekend", weekend_label
        return True, "overnight", "Sunday overnight — U.S. futures live (week ahead)"
    if weekday == 4 and clock >= time(17, 0):  # Friday after the close
        return False, "weekend", weekend_label
    if time(17, 0) <= clock < time(18, 0):  # daily maintenance halt
        return False, "halt", "Daily futures halt (5-6 PM ET) — reopens shortly"
    return True, "overnight", "Overnight — U.S. futures live"


def _warm_quotes() -> None:
    """Best-effort refresh of the overnight quote cache (market-aware TTL).

    Reads stay cache-backed; this keeps them warm without blocking on vendor I/O
    in the request path beyond the configured TTL. Failures are non-fatal — the
    read below simply falls back to whatever is already cached.
    """
    try:
        PriceDataFetcher(get_storage()).fetch_price_data(list(OVERNIGHT_LEAN_SYMBOLS))
    except Exception as exc:  # pragma: no cover - defensive, never break the read
        logger.warning("overnight_lean_quote_warm_failed", error=str(exc))


def _build_signals(
    *,
    changes: dict[str, object],
    futures_live: bool,
) -> list[LeanSignal]:
    signals: list[LeanSignal] = []
    for spec in _SIGNAL_SPECS:
        live = spec.always_live or futures_live
        change = changes.get(spec.symbol.upper())
        change_pct = getattr(change, "change_pct", None)

        if change_pct is None:
            signals.append(
                LeanSignal(
                    key=spec.key,
                    label=spec.label,
                    symbol=spec.symbol,
                    change_pct=None,
                    direction="unavailable",
                    magnitude="unavailable",
                    live=False,
                )
            )
            continue

        if not live:
            # Futures are shut (weekend / halt): the cached value is the last
            # settle, so we surface it as closed context, never as a live vote.
            signals.append(
                LeanSignal(
                    key=spec.key,
                    label=spec.label,
                    symbol=spec.symbol,
                    change_pct=change_pct,
                    direction="closed",
                    magnitude="unavailable",
                    live=False,
                    note="Closed · last settle",
                )
            )
            continue

        magnitude = _magnitude(change_pct)
        if spec.risk_on_when_up is None:  # oil — watch only
            note = (
                "Watch — inflation / geopolitical risk"
                if abs(change_pct) >= _OIL_WATCH_PCT
                else None
            )
            signals.append(
                LeanSignal(
                    key=spec.key,
                    label=spec.label,
                    symbol=spec.symbol,
                    change_pct=change_pct,
                    direction="neutral",
                    magnitude=magnitude,
                    live=True,
                    note=note,
                )
            )
            continue

        signals.append(
            LeanSignal(
                key=spec.key,
                label=spec.label,
                symbol=spec.symbol,
                change_pct=change_pct,
                direction=_risk_direction(change_pct, spec.risk_on_when_up),
                magnitude=magnitude,
                live=True,
            )
        )
    return signals


def _stocks_vote(signals_by_key: dict[str, LeanSignal]) -> tuple[str, float | None, bool]:
    """Collapse ES + NQ into a single equities vote (averaged change)."""
    members = [signals_by_key[k] for k in ("stocks_sp", "stocks_nq") if k in signals_by_key]
    live_members = [s for s in members if s.live and s.change_pct is not None]
    if not live_members:
        return "neutral", None, False
    avg = sum(s.change_pct for s in live_members) / len(live_members)  # type: ignore[misc]
    return _risk_direction(avg, True), avg, True


def _vote(signals: list[LeanSignal]) -> tuple[str, int, int, dict[str, str]]:
    """Tally live risk-on/off votes across the four macro dimensions.

    Returns (direction, confidence, live_count, dimension_directions).
    Equities count once (ES+NQ averaged); oil is watch-only and excluded.
    """
    by_key = {s.key: s for s in signals}
    dims: dict[str, str] = {}

    stocks_dir, _stocks_change, stocks_live = _stocks_vote(by_key)
    if stocks_live:
        dims["stocks"] = stocks_dir

    for spec in _SIGNAL_SPECS:
        if not spec.in_vote or spec.risk_on_when_up is None or spec.key.startswith("stocks"):
            continue
        sig = by_key.get(spec.key)
        if sig and sig.live and sig.direction in {"risk_on", "risk_off", "neutral"}:
            dims[spec.key] = sig.direction

    live_count = len(dims)
    on = sum(1 for d in dims.values() if d == "risk_on")
    off = sum(1 for d in dims.values() if d == "risk_off")
    if on == 0 and off == 0:
        return ("neutral" if live_count else "unavailable"), 0, live_count, dims
    if on > off:
        return "risk_on", on, live_count, dims
    if off > on:
        return "risk_off", off, live_count, dims
    return "neutral", max(on, off), live_count, dims


def _overnight_stress(
    *,
    applies: bool,
    direction: str,
    by_key: dict[str, LeanSignal],
) -> int | None:
    """Off-hours caution contribution on the SAME 0-100 scale as the cash tape.

    The honest caution driver overnight is the equity-futures sell-off, mapped
    through the very same calibration the daytime tape uses (so ES -2% overnight
    reads like S&P -2% in-session). A big crude move adds a bounded geopolitical
    bump. On weekends (futures shut) only a sharp Bitcoin drop nudges it, gently.
    Returns ``None`` during RTH — the live cash tape owns caution then.
    """
    if not applies:
        return None

    stocks = [by_key.get("stocks_sp"), by_key.get("stocks_nq")]
    live_stock_changes = [s.change_pct for s in stocks if s and s.live and s.change_pct is not None]

    if live_stock_changes:
        avg = sum(live_stock_changes) / len(live_stock_changes)
        stress = _stress_from_decline(-avg) if avg < 0 else _STRESS_FLOOR
    else:
        # Weekend: futures shut. Only a real crypto risk-off move counts, damped.
        crypto = by_key.get("crypto")
        if crypto and crypto.live and crypto.change_pct is not None and crypto.change_pct < 0:
            stress = min(
                _WEEKEND_CRYPTO_STRESS_CAP, _stress_from_decline(-crypto.change_pct) * 0.5
            )
        else:
            stress = _STRESS_FLOOR

    oil = by_key.get("oil")
    if oil and oil.live and oil.change_pct is not None and abs(oil.change_pct) >= _OIL_WATCH_PCT:
        stress += _OIL_STRESS_BUMP

    # A risk-on / neutral overnight is not a reason for caution to climb.
    if direction != "risk_off":
        stress = min(stress, _STRESS_FLOOR + _OIL_STRESS_BUMP if oil and oil.note else _STRESS_FLOOR)

    return round(max(_STRESS_FLOOR, min(_STRESS_CAP, stress)))


def _format_pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:+.1f}%"


def _headline(
    *,
    direction: str,
    confidence: int,
    live_count: int,
    session: str,
    by_key: dict[str, LeanSignal],
) -> str:
    crypto = by_key.get("crypto")

    if session == "weekend":
        if crypto and crypto.live and crypto.change_pct is not None:
            mood = (
                "soft" if crypto.change_pct <= -_FLAT_BAND
                else "firm" if crypto.change_pct >= _FLAT_BAND
                else "quiet"
            )
            return (
                f"Weekend — only crypto trading; U.S. futures reopen Sun 6 PM ET. "
                f"Bitcoin {_format_pct(crypto.change_pct)} ({mood})."
            )
        return "Weekend — markets shut; U.S. futures reopen Sun 6 PM ET."

    if direction == "unavailable":
        return "Overnight read unavailable — no live futures or crypto quotes."

    drivers: list[str] = []
    stocks = [by_key.get("stocks_sp"), by_key.get("stocks_nq")]
    live_stock = [s.change_pct for s in stocks if s and s.live and s.change_pct is not None]
    if live_stock:
        avg = sum(live_stock) / len(live_stock)
        if abs(avg) >= _FLAT_BAND:
            drivers.append("futures firm" if avg > 0 else "futures soft")
    gold = by_key.get("gold")
    if gold and gold.live and gold.direction == "risk_off":
        drivers.append("gold bid")
    rates = by_key.get("rates")
    if rates and rates.live and rates.direction == "risk_off":
        drivers.append("bonds bid")
    if crypto and crypto.live and crypto.change_pct is not None and abs(crypto.change_pct) >= _STRONG_BAND:
        drivers.append(f"crypto {_format_pct(crypto.change_pct)}")

    lean = {
        "risk_on": "leaning risk-on",
        "risk_off": "leaning risk-off",
        "neutral": "mixed / quiet",
    }.get(direction, "mixed / quiet")

    driver_text = f" — {', '.join(drivers)}" if drivers else ""
    confidence_text = f" ({confidence} of {live_count} agree)" if live_count else ""

    oil = by_key.get("oil")
    oil_text = ""
    if oil and oil.live and oil.note and oil.change_pct is not None:
        oil_text = f" Oil {_format_pct(oil.change_pct)} — watch geopolitical/inflation risk."

    return f"Overnight: {lean}{driver_text}{confidence_text}.{oil_text}".strip()


def _latest_as_of(changes: dict[str, object]) -> str | None:
    stamps = [getattr(c, "as_of", None) for c in changes.values()]
    stamps = [s for s in stamps if s]
    return max(stamps) if stamps else None


def get_overnight_lean(now: datetime | None = None) -> OvernightLean:
    """Compute the current overnight / off-hours forward risk lean.

    Always returns a value (never raises): off-hours it carries the live read and
    a stress contribution; during RTH ``applies`` is False and ``stress_score`` is
    None so callers can ignore it while the cash tape leads.
    """
    moment = (now or datetime.now(NY_TZ)).astimezone(NY_TZ)
    applies = get_market_status(moment) != "open"
    futures_live, session, session_label = _futures_session(moment)

    _warm_quotes()
    changes = _current_quote_changes(list(OVERNIGHT_LEAN_SYMBOLS))

    signals = _build_signals(changes=changes, futures_live=futures_live)
    by_key = {s.key: s for s in signals}
    direction, confidence, live_count, _dims = _vote(signals)
    stress_score = _overnight_stress(applies=applies, direction=direction, by_key=by_key)
    headline = _headline(
        direction=direction,
        confidence=confidence,
        live_count=live_count,
        session=session,
        by_key=by_key,
    )

    return OvernightLean(
        applies=applies,
        session=session,
        session_label=session_label,
        direction=direction,
        confidence=confidence,
        live_count=live_count,
        headline=headline,
        stress_score=stress_score,
        signals=signals,
        note="VIX & the dollar have no overnight quote — they update at the open.",
        as_of=_latest_as_of(changes),
    )
