"""Pydantic contracts for the forward-catalyst calendar.

The canonical service is ``app/services/catalyst_calendar_service.py``;
it returns these shapes, the FastAPI router serializes them, and
``st portfolio catalysts`` consumes them unchanged. Field names stay
technical (``ex_dividend_date``, ``fomc``); the plain-English
translations from the plan's UX language table happen at render time
in CLI ``--human`` and any future panel, never in the contract.

Token-saving: every catalyst row carries the four minimum fields by
default; ``?detail=true`` widens the response to add ``time_of_day``,
``confirmed``, and ``source``. Numbers stay numeric, dates ISO 8601.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CatalystKind = Literal["earnings", "ex_dividend", "fomc"]


class Catalyst(BaseModel):
    """One upcoming catalyst row.

    ``symbol`` is empty for FOMC events because the macro calendar is
    not symbol-keyed; clients should treat ``kind == "fomc"`` as the
    canonical signal that ``symbol`` is intentionally blank.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = 1
    symbol: str = ""
    kind: CatalystKind
    date: date
    days_until: int = Field(..., ge=0)
    # Detail-only fields. Default to None so default JSON stays compact;
    # the router is responsible for stripping nulls when ``?detail`` is
    # off (see ``CatalystCalendarResponse.to_minimal_payload``).
    time_of_day: str | None = None
    confirmed: bool | None = None
    source: str | None = None


class CatalystCalendarResponse(BaseModel):
    """Envelope for ``GET /api/catalysts/upcoming``.

    Holds the catalyst rows plus the request echo so agents can verify
    the parameters their query was honored with (especially useful when
    the request used defaults).
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = 1
    days: int
    limit: int
    kinds: tuple[CatalystKind, ...]
    include_watchlist: bool
    catalysts: tuple[Catalyst, ...]

    def to_minimal_payload(self) -> dict[str, object]:
        """Compact JSON serialization (drops detail-only fields).

        Used when ``?detail`` is off — keeps default token cost minimal
        for agent calls.
        """
        rows: list[dict[str, object]] = []
        for c in self.catalysts:
            rows.append(
                {
                    "schema_version": c.schema_version,
                    "symbol": c.symbol,
                    "kind": c.kind,
                    "date": c.date.isoformat(),
                    "days_until": c.days_until,
                }
            )
        return {
            "schema_version": self.schema_version,
            "days": self.days,
            "limit": self.limit,
            "kinds": list(self.kinds),
            "include_watchlist": self.include_watchlist,
            "catalysts": rows,
        }
