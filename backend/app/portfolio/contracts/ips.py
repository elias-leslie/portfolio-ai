"""Pydantic contracts for IPS targets, allocation drift, and tax-aware rebalance.

The canonical service in ``app/portfolio/ips.py`` returns these shapes;
the FastAPI router serializes them; ``st portfolio drift|rebalance|ips``
consumes them unchanged. Field names stay technical here — the
human-friendly translations from the plan's UX language table happen at
the render boundary, never in the contract.

``schema_version`` is bumped only on a true breaking change; adding
optional fields is non-breaking.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

IPSScope = Literal["household", "account"]
TradeAction = Literal["buy", "sell"]


class IPSTarget(BaseModel):
    """One row of an Investment Policy Statement target.

    Targets are the user's *goal* allocation; ``drift_band_pct`` is the
    +/- corridor around that goal that we tolerate before flagging the
    class as out-of-band. ``scope`` lets the same table store
    household-wide goals and per-account overrides.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = 1
    scope: IPSScope
    scope_id: str
    asset_class: str
    target_pct: float = Field(..., ge=0.0, le=1.0)
    drift_band_pct: float = Field(0.05, ge=0.0, le=1.0)
    notes: str | None = None


class DriftRow(BaseModel):
    """A single asset class's actual vs target.

    ``drift_pct`` is signed: positive = overweight vs target, negative =
    underweight. ``out_of_band`` is True when ``abs(drift_pct) >
    drift_band_pct``.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = 1
    asset_class: str
    target_pct: float
    actual_pct: float
    drift_pct: float
    drift_band_pct: float
    out_of_band: bool
    target_value: float
    actual_value: float
    drift_value: float


class DriftSummary(BaseModel):
    """Compact digest for ``GET /api/portfolio/ips/drift`` (default response)."""

    model_config = ConfigDict(frozen=True)

    schema_version: int = 1
    scope: IPSScope
    scope_id: str
    total_value: float
    max_drift_pct: float
    classes_out_of_band: int
    snapshot_date: date


class DriftReport(BaseModel):
    """Full allocation drift report.

    Emitted only when ``?summary=false`` is passed; the default response
    of the drift endpoint is :class:`DriftSummary`. Keeps token usage
    low for routine agent reads.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = 1
    scope: IPSScope
    scope_id: str
    snapshot_date: date
    total_value: float
    rows: list[DriftRow] = Field(default_factory=list)
    classes_missing_targets: list[str] = Field(default_factory=list)
    """Asset classes present in the portfolio but absent from IPS targets."""


class RebalanceTrade(BaseModel):
    """One proposed buy or sell row from the rebalance planner.

    ``account_id`` and ``account_type`` identify *where* the trade lands
    after the three-pass router (tax-advantaged-buys-first / LT-loss-
    sells-first / wash-sale-aware) selects the best account. ``rationale``
    is a short machine-readable code, not free text — agents key on it.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = 1
    action: TradeAction
    account_id: str
    account_type: str
    symbol: str
    asset_class: str
    shares: float
    estimated_value: float
    rationale: str
    """Short machine code: 'route_to_tax_advantaged', 'lt_loss_first',
    'lt_gain_over_st', 'wash_sale_blocked', 'wash_sale_rerouted', etc.
    The router never invents a code at runtime — see the constants in
    ``ips.py``."""
    wash_sale_conflict: bool = False
    wash_sale_reason: str | None = None
    realized_gain_long_term: float = 0.0
    realized_gain_short_term: float = 0.0


class RebalancePlan(BaseModel):
    """Full output of ``RebalancePlanner.propose_trades``.

    Token-efficient by default: callers get the full trade list, but
    the per-trade payload is already minimal — no rationale free text,
    no per-lot consumption rows. ``meta`` aggregates are precomputed so
    agents do not need to scan the trade list to answer common
    questions.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = 1
    scope: IPSScope
    scope_id: str
    snapshot_date: date
    trades: list[RebalanceTrade] = Field(default_factory=list)
    total_buy_value: float = 0.0
    total_sell_value: float = 0.0
    realized_gain_long_term: float = 0.0
    realized_gain_short_term: float = 0.0
    wash_sale_conflicts: int = 0
    asset_classes_corrected: list[str] = Field(default_factory=list)
