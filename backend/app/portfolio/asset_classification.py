"""Six-class asset taxonomy and ETF look-through for IPS / drift / rebalance.

Single source of truth for the v1 IPS taxonomy. The six classes match
what amateur investors actually plan around — US stocks, foreign
stocks, bonds, cash, alternatives, real estate. Sector exposure
remains as a *secondary* view through the existing
``calculate_sector_exposure`` path; it is not re-derived here.

Classification logic:

1. If ``fund_lookthrough`` returns asset-class weights for the symbol
   (typical for ETFs/mutual funds), distribute the position's value
   pro-rata across those classes.
2. Otherwise, fall back to the symbol-level mapping in
   ``ASSET_CLASS_BY_SYMBOL`` (a small curated table covering common
   tickers). Symbols not in the table are bucketed into the
   *unclassified* class so the user can see how much of their
   portfolio is unclassified rather than silently mis-allocating it.

Returning a missing-classes list lets the IPS service surface
"you have $X in unclassified holdings" to the user; the contract
already has ``classes_missing_targets`` for the inverse case.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal, cast

from ..storage import PortfolioStorage
from .fund_lookthrough import get_fund_lookthroughs

AssetClass = Literal[
    "us_equity",
    "intl_equity",
    "bonds",
    "cash",
    "alts",
    "real_estate",
    "unclassified",
]

ASSET_CLASSES: tuple[AssetClass, ...] = (
    "us_equity",
    "intl_equity",
    "bonds",
    "cash",
    "alts",
    "real_estate",
    "unclassified",
)

# Curated symbol → asset_class fallback table. Intentionally small;
# fund_lookthrough handles the long tail. Lowercase keys are normalized
# at lookup time.
ASSET_CLASS_BY_SYMBOL: dict[str, AssetClass] = {
    # US equity
    "VTI": "us_equity",
    "ITOT": "us_equity",
    "VOO": "us_equity",
    "SPY": "us_equity",
    "IVV": "us_equity",
    "QQQ": "us_equity",
    "VTV": "us_equity",
    "VUG": "us_equity",
    "VBR": "us_equity",
    "AAPL": "us_equity",
    "GOOG": "us_equity",
    "MSFT": "us_equity",
    "NVDA": "us_equity",
    # Intl equity
    "VXUS": "intl_equity",
    "IXUS": "intl_equity",
    "VEA": "intl_equity",
    "VWO": "intl_equity",
    "EFA": "intl_equity",
    "EEM": "intl_equity",
    # Bonds
    "BND": "bonds",
    "AGG": "bonds",
    "BNDX": "bonds",
    "VGIT": "bonds",
    "VCIT": "bonds",
    "TLT": "bonds",
    "SHY": "bonds",
    # Real estate
    "VNQ": "real_estate",
    "SCHH": "real_estate",
    "IYR": "real_estate",
    # Alts bucket: gold, commodities, hedge-style ETFs
    "GLD": "alts",
    "IAU": "alts",
    "DBC": "alts",
    # Cash-equivalent ETFs
    "BIL": "cash",
    "SHV": "cash",
    "SGOV": "cash",
}

# Mapping from yfinance fund_lookthrough's ``asset_classes`` keys to
# our v1 taxonomy. yfinance uses keys like 'stockPosition',
# 'bondPosition', etc.; many ETF reports do not split US vs intl
# inside ``asset_classes`` — treat the un-split portion as US equity
# (the dominant allocation for a typical US-listed ETF) and let
# fund-level overrides in ASSET_CLASS_BY_SYMBOL refine when needed.
_LOOKTHROUGH_KEY_MAP: dict[str, AssetClass] = {
    "stockPosition": "us_equity",
    "bondPosition": "bonds",
    "cashPosition": "cash",
    "preferredPosition": "alts",
    "convertiblePosition": "alts",
    "otherPosition": "alts",
}


@dataclass(slots=True, frozen=True)
class ValueByClass:
    """Holds dollar value bucketed by asset class for one snapshot."""

    total_value: float
    by_class: dict[str, float]
    unclassified_value: float


@dataclass(slots=True, frozen=True)
class HoldingValue:
    """A single (symbol, value) tuple consumed by :class:`AssetClassifier`."""

    symbol: str
    value: float


class AssetClassifier:
    """Classify holdings into the v1 six-class taxonomy.

    Uses fund look-through (``fund_lookthrough.get_fund_lookthroughs``)
    when the symbol resolves; falls back to the curated table; falls
    back to ``unclassified`` so nothing is silently lost.
    """

    def __init__(self, storage: PortfolioStorage | None) -> None:
        self.storage = storage

    def classify_value(self, holdings: Iterable[HoldingValue]) -> ValueByClass:
        """Bucket a stream of (symbol, value) tuples by asset class.

        Returns a normalized payload with both per-class totals and
        a top-level ``unclassified_value`` for UI surfacing.
        """
        usable = [
            HoldingValue(symbol=str(h.symbol).upper(), value=float(h.value))
            for h in holdings
            if h.value is not None and float(h.value) > 0
        ]
        if not usable:
            return ValueByClass(total_value=0.0, by_class={}, unclassified_value=0.0)

        symbols = sorted({h.symbol for h in usable})
        profiles = get_fund_lookthroughs(symbols, self.storage) if self.storage else {}

        by_class: dict[str, float] = dict.fromkeys(ASSET_CLASSES, 0.0)
        for holding in usable:
            distribution = self._asset_class_weights(holding.symbol, profiles)
            for cls, weight in distribution.items():
                by_class[cls] += holding.value * weight

        total = sum(by_class.values())
        unclassified = by_class.get("unclassified", 0.0)
        # Strip empty buckets to keep payloads compact.
        cleaned = {cls: round(value, 4) for cls, value in by_class.items() if value > 0}
        return ValueByClass(
            total_value=round(total, 4),
            by_class=cleaned,
            unclassified_value=round(unclassified, 4),
        )

    def primary_class(self, symbol: str) -> AssetClass:
        """Return the dominant asset class for a single symbol.

        Used by the rebalance planner when picking which symbol to
        buy/sell in a given asset class. Falls back through:
        explicit table → look-through (largest weight) → unclassified.
        """
        symbol_upper = symbol.upper()
        explicit = ASSET_CLASS_BY_SYMBOL.get(symbol_upper)
        if explicit is not None:
            return explicit
        if not self.storage:
            return "unclassified"
        profile = get_fund_lookthroughs([symbol_upper], self.storage).get(symbol_upper)
        if profile is None:
            return "unclassified"
        weights = _classify_via_lookthrough(profile.asset_classes)
        if not weights:
            return "unclassified"
        # Largest-weight bucket wins. cast() preserves the AssetClass
        # literal; the dict's keys come from the curated _LOOKTHROUGH_KEY_MAP
        # which is itself typed AssetClass, but the comprehension widens
        # the value type to str.
        winning = max(weights.items(), key=lambda kv: kv[1])[0]
        return cast(AssetClass, winning)

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    def _asset_class_weights(
        self,
        symbol: str,
        profiles: dict[str, object],
    ) -> dict[str, float]:
        """Return a weight distribution for one symbol that sums to 1.0."""
        explicit = ASSET_CLASS_BY_SYMBOL.get(symbol)
        if explicit is not None:
            return {explicit: 1.0}

        profile = profiles.get(symbol)
        asset_classes = getattr(profile, "asset_classes", None) if profile else None
        if isinstance(asset_classes, dict) and asset_classes:
            mapped = _classify_via_lookthrough(asset_classes)
            if mapped:
                return mapped

        return {"unclassified": 1.0}


def _classify_via_lookthrough(asset_classes: dict[str, float]) -> dict[str, float]:
    """Convert yfinance ``asset_classes`` weights to the v1 taxonomy.

    Sums weights for keys that map to the same target class (e.g.
    ``preferredPosition`` and ``otherPosition`` both → ``alts``) and
    re-normalizes so the result sums to 1.0. Unmapped keys are dropped.
    """
    bucketed: dict[str, float] = {}
    for source_key, weight in asset_classes.items():
        target = _LOOKTHROUGH_KEY_MAP.get(source_key)
        if target is None:
            continue
        try:
            value = float(weight)
        except (TypeError, ValueError):
            continue
        if value <= 0:
            continue
        bucketed[target] = bucketed.get(target, 0.0) + value
    total = sum(bucketed.values())
    if total <= 0:
        return {}
    return {cls: weight / total for cls, weight in bucketed.items()}
