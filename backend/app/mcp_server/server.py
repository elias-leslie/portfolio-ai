"""FastMCP server definition and tool wrappers.

Tools are thin adapters over existing repositories:

* L1 (macro gate)   — :mod:`app.macro_gate.repository`

Every value a tool returns is deterministic and back-testable: the tools read
rows that background workflows already persisted, and never call a model.
Returns are plain JSON-serializable dicts; the existing repositories
already coerce DB rows into ISO-string + float primitives.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from mcp.server.fastmcp import FastMCP

from ..macro_gate import repository as macro_repo

INSTRUCTIONS = (
    "Read-only access to portfolio-ai's macro context:\n"
    "  L1 (DETERMINISTIC)     daily macro deployment gate "
    "(FULL_DEPLOY / REDUCED / DEFENSIVE)\n\n"
    "All numbers are persisted by background workflows; tools never trigger "
    "LLM inference or recompute anything."
)

mcp: FastMCP = FastMCP(name="portfolio-ai", instructions=INSTRUCTIONS)


_COMPONENT_KEYS: tuple[str, ...] = ("vix", "term", "breadth", "credit", "putcall", "crowding")


def _components_from_snapshot(snapshot: dict[str, Any] | None) -> dict[str, float | None]:
    if snapshot is None:
        return dict.fromkeys(_COMPONENT_KEYS)
    return {
        "vix": snapshot.get("vix_score"),
        "term": snapshot.get("term_score"),
        "breadth": snapshot.get("breadth_score"),
        "credit": snapshot.get("credit_score"),
        "putcall": snapshot.get("putcall_score"),
        "crowding": snapshot.get("crowding_score"),
    }


def _trend_7d(history: list[dict[str, Any]], current_score: float | None) -> dict[str, Any]:
    """Latest deployment score minus the most-recent sample at least 7 days back.

    ``history`` is ascending by ``snapshot_date`` (the repository orders it
    that way). Returns ``None`` scalars when there isn't enough history.
    """
    empty = {"delta_7d": None, "prior_score": None, "prior_date": None}
    if current_score is None or len(history) < 2:
        return empty
    today = datetime.fromisoformat(history[-1]["snapshot_date"]).date()
    seven_back = today - timedelta(days=7)
    prior: dict[str, Any] | None = None
    for row in history[:-1]:
        if datetime.fromisoformat(row["snapshot_date"]).date() <= seven_back:
            prior = row
    if prior is None:
        return empty
    prior_score = prior.get("deployment_score")
    if prior_score is None:
        return {"delta_7d": None, "prior_score": None, "prior_date": prior["snapshot_date"]}
    return {
        "delta_7d": float(current_score) - float(prior_score),
        "prior_score": float(prior_score),
        "prior_date": prior["snapshot_date"],
    }


@mcp.tool()
def get_deployment_zone() -> dict[str, Any]:
    """Today's L1 macro gate: zone, 0-100 composite, 6 component scores, 7-day trend.

    DETERMINISTIC tier — values are computed nightly from already-ingested
    data and are fully back-testable. Fields are ``None`` until the
    ``macro_gate`` workflow has produced at least one snapshot.
    """
    snapshot = macro_repo.get_latest()
    history = macro_repo.get_history(days=14)
    current_score = snapshot.get("deployment_score") if snapshot else None
    return {
        "tier": "L1",
        "kind": "deterministic",
        "snapshot_date": snapshot["snapshot_date"] if snapshot else None,
        "zone": snapshot["zone"] if snapshot else None,
        "deployment_score": current_score,
        "components": _components_from_snapshot(snapshot),
        "trend": _trend_7d(history, current_score),
    }


@mcp.tool()
def get_deployment_history(days: int = 90) -> dict[str, Any]:
    """L1 macro gate daily history: composite + zone + components per persisted snapshot.

    ``days`` is clamped to ``[1, 730]``; rows are returned in ascending
    date order. DETERMINISTIC tier.
    """
    days = max(1, min(int(days), 730))
    history = macro_repo.get_history(days=days)
    return {
        "tier": "L1",
        "kind": "deterministic",
        "days": days,
        "count": len(history),
        "rows": [
            {
                "snapshot_date": row["snapshot_date"],
                "deployment_score": row.get("deployment_score"),
                "zone": row["zone"],
                "components": _components_from_snapshot(row),
            }
            for row in history
        ],
    }


@mcp.tool()
def get_symbol_full_picture(ticker: str, days: int = 30) -> dict[str, Any]:
    """Current macro deployment context, scoped to one symbol.

    ``days`` is accepted for backward compatibility and clamped, but no
    additional historical series is returned.
    """
    sym = ticker.upper().strip()
    if not sym:
        return {
            "error": "empty_ticker",
            "symbol": "",
            "macro": None,
        }
    days = max(1, min(int(days), 365))
    macro = macro_repo.get_latest()
    return {
        "symbol": sym,
        "days": days,
        "macro": {
            "tier": "L1",
            "kind": "deterministic",
            "snapshot_date": macro["snapshot_date"] if macro else None,
            "zone": macro["zone"] if macro else None,
            "deployment_score": macro.get("deployment_score") if macro else None,
            "components": _components_from_snapshot(macro),
        },
    }
