"""FastMCP server definition and tool wrappers.

Tools are thin adapters over existing repositories:

* L1 (macro gate)   — :mod:`app.macro_gate.repository`
* Committee         — :mod:`app.agents.committee.store`

Each tool documents its tier and whether the underlying values are
deterministic (back-testable) or non-deterministic (LLM-judgment, paid).
Returns are plain JSON-serializable dicts; the existing repositories
already coerce DB rows into ISO-string + float primitives.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from mcp.server.fastmcp import FastMCP

from ..agents.committee import store as committee_store
from ..macro_gate import repository as macro_repo

INSTRUCTIONS = (
    "Read-only access to portfolio-ai's macro and committee context:\n"
    "  L1 (DETERMINISTIC)     daily macro deployment gate "
    "(FULL_DEPLOY / REDUCED / DEFENSIVE)\n"
    "  Committee (NON-DETERMINISTIC) investment committee verdicts (AI, paid per run)\n\n"
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
def get_committee_runs_today() -> dict[str, Any]:
    """L3 committee runs completed in the last 24 hours, newest first.

    NON-DETERMINISTIC tier — each row is an LLM-pipeline verdict (typically
    ~$0.20-$2.00 per run via agent-hub). Filtered to
    ``status in ('complete', 'approved')`` with a ``completed_at`` inside
    the 24-hour window.
    """
    runs = committee_store.list_recent_runs(None, limit=100)
    cutoff = datetime.now(UTC) - timedelta(hours=24)
    rows: list[dict[str, Any]] = []
    for row in runs:
        if row.get("status") not in {"complete", "approved"}:
            continue
        completed = row.get("completed_at")
        if not completed:
            continue
        try:
            ts = datetime.fromisoformat(completed)
        except ValueError:
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        if ts < cutoff:
            continue
        rows.append(row)
    return {
        "tier": "L3",
        "kind": "non-deterministic",
        "window_hours": 24,
        "count": len(rows),
        "rows": rows,
    }


@mcp.tool()
def get_symbol_full_picture(ticker: str, days: int = 30) -> dict[str, Any]:
    """Unified macro + latest committee view for one symbol.

    Combines the current macro deployment zone with the freshest completed
    committee verdict. ``days`` is accepted for backward compatibility and
    clamped, but no additional historical series is returned.
    """
    sym = ticker.upper().strip()
    if not sym:
        return {
            "error": "empty_ticker",
            "symbol": "",
            "macro": None,
            "committee": None,
        }
    days = max(1, min(int(days), 365))
    macro = macro_repo.get_latest()
    committee = committee_store.get_latest_completed_by_symbol([sym]).get(sym)
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
        "committee": {
            "tier": "committee",
            "kind": "non-deterministic",
            "latest": committee,
        },
    }
