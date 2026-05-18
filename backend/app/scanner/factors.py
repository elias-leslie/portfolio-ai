"""Pure factor functions for the L2 scanner.

Each function takes already-fetched series and returns a single raw float
(or ``None`` if there isn't enough history). No I/O, no globals — keeps
unit tests deterministic and golden-value back-testing trivial.

Factor menu (per Phase 2 spec):

1. ``mom_xover``       - (EMA10 - EMA50) / EMA50, latest bar
2. ``vol_surge``       - mean(volume[-5:]) / mean(volume[-20:])
3. ``rs_vs_spy``       - symbol 20d return - SPY 20d return
4. ``high_52w_proximity`` - last_close / max(close over ~252 bars)
5. ``short_interest_decline`` - (prior - current) / prior, positive = improving
"""

from __future__ import annotations

from collections.abc import Sequence


def _ema(values: Sequence[float], length: int) -> float | None:
    """Exponential moving average, latest value.

    Standard pandas-ta style: seed with the first sample, then apply the
    ``2/(N+1)`` smoothing constant. Returns ``None`` if ``values`` is too
    short.
    """
    if length <= 0 or len(values) < length:
        return None
    alpha = 2.0 / (length + 1)
    ema = float(values[0])
    for v in values[1:]:
        ema = alpha * float(v) + (1.0 - alpha) * ema
    return ema


def mom_xover(closes: Sequence[float]) -> float | None:
    """EMA10/EMA50 distance, expressed as ``(EMA10 - EMA50) / EMA50``.

    Positive = short-term trend above intermediate trend (bullish cross
    regime); the magnitude scales with how stretched the cross is.
    """
    if len(closes) < 50:
        return None
    short = _ema(closes, 10)
    long = _ema(closes, 50)
    if short is None or long is None or long == 0:
        return None
    return (short - long) / long


def vol_surge(volumes: Sequence[float]) -> float | None:
    """5-day mean volume divided by 20-day mean volume.

    1.0 = unchanged; >1.0 = recent surge; <1.0 = drying up. Returns
    ``None`` if either window is empty or the 20d mean is zero.
    """
    if len(volumes) < 20:
        return None
    last_5 = [float(v) for v in volumes[-5:]]
    last_20 = [float(v) for v in volumes[-20:]]
    mean_20 = sum(last_20) / 20.0
    if mean_20 == 0:
        return None
    mean_5 = sum(last_5) / 5.0
    return mean_5 / mean_20


def rs_vs_spy(symbol_closes: Sequence[float], spy_closes: Sequence[float]) -> float | None:
    """Relative strength vs SPY over the last 20 bars.

    Computed as ``symbol_20d_return - spy_20d_return`` (decimal, not
    percentage). Positive = outperforming SPY over the window.
    """
    if len(symbol_closes) < 21 or len(spy_closes) < 21:
        return None
    sym_start = float(symbol_closes[-21])
    spy_start = float(spy_closes[-21])
    if sym_start == 0 or spy_start == 0:
        return None
    sym_ret = float(symbol_closes[-1]) / sym_start - 1.0
    spy_ret = float(spy_closes[-1]) / spy_start - 1.0
    return sym_ret - spy_ret


def high_52w_proximity(closes: Sequence[float]) -> float | None:
    """``last_close / max(close over the last ~252 bars)``.

    1.0 = sitting at the 52-week high; 0.85 = 15% off the high; etc.
    Universe-relative percentile turns this into the scanner score.
    """
    if not closes:
        return None
    window = [float(v) for v in closes[-252:]]
    peak = max(window)
    if peak == 0:
        return None
    return float(closes[-1]) / peak


def short_interest_decline(
    current_short_pct: float | None,
    prior_short_pct: float | None,
) -> float | None:
    """``(prior - current) / prior`` — positive = short interest receding.

    Both inputs are ``short_percent_of_float`` (decimals 0-1). Returns
    ``None`` if either value is missing or the prior is zero.
    """
    if current_short_pct is None or prior_short_pct is None:
        return None
    prior = float(prior_short_pct)
    if prior == 0:
        return None
    return (prior - float(current_short_pct)) / prior


FACTOR_NAMES: tuple[str, ...] = (
    "mom_xover",
    "vol_surge",
    "rs_vs_spy",
    "high_52w_proximity",
    "short_interest_decline",
)
"""Stable ordering used by repository, percentile assignment, and the API."""
