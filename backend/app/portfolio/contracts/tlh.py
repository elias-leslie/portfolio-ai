"""Pydantic contracts for TLH (tax-loss-harvesting) analytics.

The canonical TLH analyzer in ``app/portfolio/tlh.py`` returns these
shapes; routers serialize them; ``st portfolio tlh ...`` consumes them
unchanged. Field names stay technical here — the human-friendly
translations from the plan's "UX & Language Discipline" table happen at
the render boundary, never in the contract.

``schema_version`` is bumped only on an actual breaking change. Adding
optional fields is non-breaking.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ReplacementConfidence = Literal["exact", "close", "approximate"]


class ReplacementSecurity(BaseModel):
    """Suggested replacement ticker for a TLH sale.

    'exact' is reserved for sales of the same fund family with no
    overlap (rare). 'close' is the substantially-identical risk zone
    (e.g. VTI <-> ITOT) — flagged but not auto-blocked; user judgement
    required. 'approximate' is safer (different index, similar
    exposure).
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = 1
    from_symbol: str
    to_symbol: str
    asset_class: str
    name: str
    rationale: str | None = None
    confidence: ReplacementConfidence


class ConflictingBuy(BaseModel):
    """A purchase row inside the wash-sale window that blocks a sale."""

    model_config = ConfigDict(frozen=True)

    txn_id: str
    account_id: str
    account_type: str
    trade_date: date
    shares: float
    days_offset: int
    """Calendar days from the proposed sell_date. Negative = before sell."""


class WashSaleVerdict(BaseModel):
    """Outcome of scanning the household's 61-day window for substantially-identical buys.

    Per IRS Pub 550 and Rev. Rul. 2008-5, the window is
    ``[sell_date - 30, sell_date + 30]`` inclusive and includes spouse
    accounts and tax-advantaged accounts (IRA / Roth / 401k / HSA). A
    'close' ETF equivalent is flagged with ``substantially_identical=
    True`` and ``blocked=True`` because the IRS has not published a
    bright-line list — caller must override deliberately.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = 1
    symbol: str
    sell_date: date
    household_id: str | None = None
    blocked: bool
    reason: str | None = None
    conflicting_buys: list[ConflictingBuy] = Field(default_factory=list)
    substantially_identical: bool = False


class TLHCandidate(BaseModel):
    """A single TLH opportunity surfaced by the analysis engine.

    Default-projection fields (returned when ``detail=False``) are
    ``symbol``, ``account_id``, ``unrealized_loss``, ``unrealized_loss_pct``.
    Detail fields (``replacement``, ``holding_period_days``,
    ``realized_loss_long_term``, ``realized_loss_short_term``,
    ``wash_sale_blocked``, ``wash_sale_reason``) are excluded from the
    minimal payload by the router serializer.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = 1
    symbol: str
    account_id: str
    account_type: str
    shares: float
    cost_basis: float
    """Per-share cost basis — same units as ``portfolio_positions.cost_basis``."""
    current_price: float
    current_value: float
    unrealized_loss: float
    """Negative number (loss). Zero/positive positions are filtered out."""
    unrealized_loss_pct: float
    """Loss as a fraction of cost basis: -0.12 means down 12%."""
    holding_period_days: int | None = None
    realized_loss_long_term: float = 0.0
    realized_loss_short_term: float = 0.0
    replacement: ReplacementSecurity | None = None
    wash_sale_blocked: bool = False
    wash_sale_reason: str | None = None
