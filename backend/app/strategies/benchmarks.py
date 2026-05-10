"""Benchmark catalog for buy-and-hold comparison.

Declarative list of benchmarks the catalog compares each screened strategy
against. Adding a new benchmark = one entry in BENCHMARKS. No schema change.

Three kinds:
- 'ticker'   - single ETF/symbol (e.g. SPY, VTI, AGG). Pulled from day_bars.
- 'basket'   - equal-weight composite of multiple symbols (e.g. MAG7).
- 'weighted' - explicit weight map (e.g. 60/40 = 60%% SPY + 40%% AGG).

Risk tier and plain-language description live alongside the definition so
the API can present amateur-friendly labels without a separate i18n layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

BenchmarkKind = Literal["ticker", "basket", "weighted"]
RiskTier = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class BenchmarkDefinition:
    """One buy-and-hold benchmark."""

    key: str
    label: str  # short display name
    description: str  # plain-English one-liner for the UI
    kind: BenchmarkKind
    risk_tier: RiskTier
    # For 'ticker': {"symbol": "SPY"}
    # For 'basket': {"symbols": ["AAPL", "MSFT", ...]}  (equal-weight)
    # For 'weighted': {"weights": {"SPY": 0.6, "AGG": 0.4}}
    definition: dict[str, object]


BENCHMARKS: list[BenchmarkDefinition] = [
    BenchmarkDefinition(
        key="SPY",
        label="S&P 500",
        description="The 500 largest US public companies. Most common baseline.",
        kind="ticker",
        risk_tier="medium",
        definition={"symbol": "SPY"},
    ),
    BenchmarkDefinition(
        key="VTI",
        label="Total US Market",
        description="Every US public company, large to small.",
        kind="ticker",
        risk_tier="medium",
        definition={"symbol": "VTI"},
    ),
    BenchmarkDefinition(
        key="QQQ",
        label="Nasdaq 100",
        description="The 100 biggest non-financial companies on the Nasdaq. Tech-heavy.",
        kind="ticker",
        risk_tier="high",
        definition={"symbol": "QQQ"},
    ),
    BenchmarkDefinition(
        key="RSP",
        label="Equal-weight S&P 500",
        description="Same 500 companies as the S&P 500, but each weighted equally instead of by size.",
        kind="ticker",
        risk_tier="medium",
        definition={"symbol": "RSP"},
    ),
    BenchmarkDefinition(
        key="AGG",
        label="US Bonds",
        description="Broad US bond market. The safe alternative.",
        kind="ticker",
        risk_tier="low",
        definition={"symbol": "AGG"},
    ),
    BenchmarkDefinition(
        key="MAG7",
        label="Mag 7 Tech",
        description="The 7 biggest tech names (Apple, Microsoft, Google, Amazon, Nvidia, Meta, Tesla), equally weighted.",
        kind="basket",
        risk_tier="high",
        definition={"symbols": ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"]},
    ),
    BenchmarkDefinition(
        key="S60_B40",
        label="Classic 60/40",
        description="60% S&P 500 + 40% US bonds. The textbook balanced portfolio.",
        kind="weighted",
        risk_tier="low",
        definition={"weights": {"SPY": 0.6, "AGG": 0.4}},
    ),
]

BENCHMARKS_BY_KEY: dict[str, BenchmarkDefinition] = {b.key: b for b in BENCHMARKS}


def get_benchmark(key: str) -> BenchmarkDefinition | None:
    """Look up a benchmark by key, or None if not configured."""
    return BENCHMARKS_BY_KEY.get(key)


def required_symbols(definition: BenchmarkDefinition) -> list[str]:
    """Underlying day_bars symbols a benchmark needs to compute its return."""
    if definition.kind == "ticker":
        symbol = definition.definition.get("symbol")
        return [str(symbol)] if symbol else []
    if definition.kind == "basket":
        symbols = definition.definition.get("symbols", [])
        if isinstance(symbols, list):
            return [str(s) for s in symbols]
        return []
    if definition.kind == "weighted":
        weights = definition.definition.get("weights", {})
        if isinstance(weights, dict):
            return [str(k) for k in weights]
        return []
    return []
