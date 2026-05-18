"""L2 + L3 blender — merge deterministic scanner rank with committee verdict.

Spec from the Phase 3 plan::

    blended = W_scanner * scanner_composite + W_committee * committee_pm_score * 10

Where ``scanner_composite`` is 0-100 (universe-relative percentile) and
``committee_pm_score`` is a 0-10 conviction-direction score derived from
the committee's ``PmDecision`` (action + confidence). Multiplying by 10
puts it back on the same 0-100 axis as the scanner so the weighted sum
is meaningful.

Defaults from the spec are 0.6 / 0.4 (scanner-heavy). Both weights are
configurable via env (``SCANNER_BLEND_W_SCANNER`` /
``SCANNER_BLEND_W_COMMITTEE``); a per-user override is a Phase 4 UI
concern — the override is passed in as ``weights`` here.

Δrank flagging: after re-ranking by ``blended`` we compare each
symbol's new rank against its scanner-only rank. ``|Δrank| >= 3`` is
flagged (positive ``Δrank`` = upgrade by the committee, negative =
downgrade).

The blender is pure — it takes scanner rows + a lookup of committee
PmDecisions and returns blended rows. Persistence is the caller's
job. This keeps it cheap to unit-test and easy to back-test against
historical scanner runs once a committee snapshot exists.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_W_SCANNER = 0.6
DEFAULT_W_COMMITTEE = 0.4
DELTA_RANK_FLAG_THRESHOLD = 3


@dataclass(frozen=True, slots=True)
class BlendWeights:
    scanner: float = DEFAULT_W_SCANNER
    committee: float = DEFAULT_W_COMMITTEE

    def normalised(self) -> BlendWeights:
        """Renormalise to sum to 1 so callers can pass raw slider values."""
        total = self.scanner + self.committee
        if total <= 0:
            return BlendWeights(DEFAULT_W_SCANNER, DEFAULT_W_COMMITTEE)
        return BlendWeights(self.scanner / total, self.committee / total)


@dataclass(frozen=True, slots=True)
class CommitteeSignal:
    """Per-symbol summary of the committee's verdict.

    Built from the latest ``committee_runs`` row for the symbol with
    status in ``{'complete', 'approved'}``.
    """

    run_id: str
    action: str
    confidence: float
    pm_score: float  # 0-10, see ``pm_score_from_decision``


@dataclass(frozen=True, slots=True)
class BlendedRow:
    symbol: str
    scanner_rank: int
    scanner_composite_pct: float
    committee: CommitteeSignal | None
    blended_score: float
    blended_rank: int
    delta_rank: int  # scanner_rank - blended_rank; positive = committee upgraded
    flagged: bool   # |delta_rank| >= DELTA_RANK_FLAG_THRESHOLD


def env_weights() -> BlendWeights:
    """Read weights from env with the documented defaults."""
    return BlendWeights(
        scanner=_float_env("SCANNER_BLEND_W_SCANNER", DEFAULT_W_SCANNER),
        committee=_float_env("SCANNER_BLEND_W_COMMITTEE", DEFAULT_W_COMMITTEE),
    ).normalised()


def pm_score_from_decision(action: str | None, confidence: float | None) -> float:
    """Map a ``PmDecision`` into a 0-10 conviction-direction score.

    Bull actions get the full conviction weight; ``hold`` gets half
    (the committee thinks it's worth watching but not adding); bear
    actions zero out the committee contribution so a confident sell
    doesn't pull a symbol *up* the blended ranking. This keeps
    ``blended_score`` strictly in ``[0, 100]`` for the documented
    weights.
    """
    if confidence is None:
        return 0.0
    c = max(0.0, min(1.0, float(confidence)))
    act = (action or "").lower()
    if act in {"buy", "add"}:
        return 10.0 * c
    if act == "hold":
        return 5.0 * c
    # sell, trim, unknown -> no positive contribution
    return 0.0


def blend(
    scanner_rows: list[dict],
    committee_by_symbol: dict[str, CommitteeSignal],
    *,
    weights: BlendWeights | None = None,
    flag_threshold: int = DELTA_RANK_FLAG_THRESHOLD,
) -> list[BlendedRow]:
    """Return blended rows sorted by ``blended_score`` desc.

    ``scanner_rows`` is the canonical scanner output shape returned by
    ``app.scanner.repository.get_scores_for_run`` — each row carries
    ``symbol``, ``rank`` (scanner rank), and ``composite_pct``.
    Symbols without a committee entry fall back to ``pm_score = 0`` so
    they're blended as scanner-only.
    """
    w = (weights or env_weights()).normalised()

    enriched: list[tuple[str, int, float, CommitteeSignal | None, float]] = []
    for row in scanner_rows:
        symbol = str(row["symbol"]).upper()
        scanner_rank = int(row["rank"])
        composite = float(row.get("composite_pct") or 0.0)
        signal = committee_by_symbol.get(symbol)
        pm_score = signal.pm_score if signal else 0.0
        blended = w.scanner * composite + w.committee * pm_score * 10.0
        enriched.append((symbol, scanner_rank, composite, signal, blended))

    enriched.sort(key=lambda t: t[4], reverse=True)

    out: list[BlendedRow] = []
    for blended_idx, (symbol, scanner_rank, composite, signal, blended) in enumerate(
        enriched, start=1
    ):
        delta = scanner_rank - blended_idx  # positive = moved up
        out.append(
            BlendedRow(
                symbol=symbol,
                scanner_rank=scanner_rank,
                scanner_composite_pct=composite,
                committee=signal,
                blended_score=blended,
                blended_rank=blended_idx,
                delta_rank=delta,
                flagged=abs(delta) >= flag_threshold,
            )
        )
    return out


def _float_env(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default
