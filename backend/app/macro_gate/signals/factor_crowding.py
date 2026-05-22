"""Factor crowding — 60-day rolling correlation of momentum and value returns.

When momentum and value (typically uncorrelated or mildly anti-correlated)
become highly correlated, the market is being driven by a single underlying
factor — typically liquidity, sentiment, or a macro shock. Sustained high
correlation precedes deleveraging episodes.

This is computationally heavy (universe-wide cross-sectional sort + rolling
correlation), so by design this collector caches its last run and is meant
to be refreshed weekly, not daily. See plan "Risks & Gotchas #3".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from ...logging_config import get_logger
from ...services import research_universe as universe_service
from ...storage.facade import get_storage

logger = get_logger(__name__)

LOOKBACK_DAYS = 320  # ~120 trading-day formation + 60 trading-day correlation window
TOP_BUCKET_SIZE = 50  # cardinality of momentum long leg / short leg


@dataclass(frozen=True, slots=True)
class CrowdingObservation:
    as_of: date
    rolling_window_days: int
    momentum_value_corr: float
    universe_size: int


def _load_panel(symbols: list[str], days: int) -> pd.DataFrame:
    storage = get_storage()
    with storage.connection() as conn:
        rows = conn.execute(
            f"""
            SELECT date, symbol, close
            FROM day_bars
            WHERE symbol = ANY(%s)
              AND date >= (CURRENT_DATE - INTERVAL '{int(days)} days')::date
            """,
            [symbols],
        ).fetchall()
    if not rows:
        return pd.DataFrame()
    pdf = pd.DataFrame(rows, columns=["date", "symbol", "close"])
    pdf["date"] = pd.to_datetime(pdf["date"])
    pdf["close"] = pdf["close"].astype(float)
    return pdf.pivot(index="date", columns="symbol", values="close").sort_index()


def compute_crowding(window_days: int = 60) -> CrowdingObservation | None:
    """Compute the rolling momentum vs value factor return correlation.

    Momentum factor: long-short of top-50 vs bottom-50 by trailing 120d return.
    Value proxy: dividend yield is not in our universe table — instead we
    proxy "value" with reversal (top-50 worst 60d returners minus the
    universe-mean returner) which is what an academic 60d HMW (high-minus-low
    medium-term reversal) factor would capture. Documented proxy; if a real
    book-to-market source is wired later, swap here.
    """
    symbols = universe_service.list_active_symbols()
    if not symbols:
        logger.warning("factor_crowding_no_universe")
        return None

    panel = _load_panel(symbols, LOOKBACK_DAYS)
    if panel.empty or len(panel) < window_days + 5:
        logger.warning("factor_crowding_panel_insufficient", rows=len(panel))
        return None

    # Align sparse symbol panels explicitly; pandas' implicit pct_change fill is deprecated.
    panel = panel.ffill(limit=5)
    daily_returns = panel.pct_change(fill_method=None).dropna(how="all")
    if len(daily_returns) < window_days:
        return None

    formation_returns = panel.pct_change(periods=120, fill_method=None).iloc[-1].dropna()
    if len(formation_returns) < TOP_BUCKET_SIZE * 2:
        return None

    momentum_long = formation_returns.nlargest(TOP_BUCKET_SIZE).index
    momentum_short = formation_returns.nsmallest(TOP_BUCKET_SIZE).index

    # Reversal proxy: 60d losers (long) minus 60d winners (short)
    reversal_returns = panel.pct_change(periods=60, fill_method=None).iloc[-1]
    reversal_long = reversal_returns.nsmallest(TOP_BUCKET_SIZE).index
    reversal_short = reversal_returns.nlargest(TOP_BUCKET_SIZE).index

    mom_series = (
        daily_returns[momentum_long].mean(axis=1)
        - daily_returns[momentum_short].mean(axis=1)
    )
    val_series = (
        daily_returns[reversal_long].mean(axis=1)
        - daily_returns[reversal_short].mean(axis=1)
    )

    window = min(window_days, len(mom_series))
    corr = mom_series.tail(window).corr(val_series.tail(window))
    if pd.isna(corr):
        return None

    return CrowdingObservation(
        as_of=daily_returns.index[-1].date(),
        rolling_window_days=window,
        momentum_value_corr=float(corr),
        universe_size=len(symbols),
    )


def normalize_to_score(momentum_value_corr: float) -> float:
    """Map factor correlation to a 0-100 score where low |corr| = healthy.

    Mapping (symmetric):
        |corr| <= 0.1 -> 100  (factors decoupled, healthy regime)
        |corr| >= 0.7 -> 0    (crowded, fragile regime)
        linear interpolation between.
    """
    magnitude = abs(momentum_value_corr)
    if magnitude <= 0.1:
        return 100.0
    if magnitude >= 0.7:
        return 0.0
    return 100.0 * (1 - (magnitude - 0.1) / 0.6)
