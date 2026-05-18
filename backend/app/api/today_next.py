"""Aggregated Today Next signal stack API."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app.api.market._core_helpers import (
    build_intelligence_response_data,
    fetch_core_market_data,
)
from app.api.market._response_builders import (
    build_fear_greed_response,
    build_market_health_response,
    build_sector_rotation_response,
)
from app.logging_config import get_logger
from app.storage import get_storage
from app.watchlist.response_builders import build_watchlist_item_responses
from app.watchlist.watchlist_service import WatchlistService

logger = get_logger(__name__)
router = APIRouter(prefix="/api/today-next", tags=["today-next"])


class MacroGate(BaseModel):
    status: str
    score: int
    label: str
    fear_greed_score: int
    fear_greed_label: str
    vix: float | None = None
    as_of: str | None = None
    signals: list[dict[str, Any]] = Field(default_factory=list)


class ScannerCandidate(BaseModel):
    symbol: str
    signal_type: str | None = None
    signal_strength: int | None = None
    score: float | None = None
    headline: str | None = None
    style: str | None = None
    risk_level: str | None = None
    entry_price: float | None = None
    stop_loss: float | None = None
    profit_target: float | None = None


class CommitteeCandidate(BaseModel):
    symbol: str
    thesis_action: str | None = None
    thesis_status: str | None = None
    expected_return_pct: float | None = None
    cross_validation_score: float | None = None
    committee_run_id: str | None = None
    committee_status: str | None = None
    committee_action: str | None = None
    committee_confidence: float | None = None
    updated_at: str | None = None


class TodayNextResponse(BaseModel):
    macro_gate: MacroGate
    scanner: list[ScannerCandidate]
    committee: list[CommitteeCandidate]


@lru_cache(maxsize=1)
def _get_watchlist_service() -> WatchlistService:
    return WatchlistService(get_storage())


def _macro_status(score: int, fear_greed_score: int) -> str:
    if score >= 65 and fear_greed_score >= 35:
        return "risk_on"
    if score <= 35 or fear_greed_score <= 20:
        return "risk_off"
    return "neutral"


def _build_macro_gate() -> MacroGate:
    market_data = fetch_core_market_data()
    data = build_intelligence_response_data(market_data, market_data.current_timestamp)
    market_health = build_market_health_response(data["health_score_data"])
    fear_greed = build_fear_greed_response(data["fg_reading"])
    sector_rotation = build_sector_rotation_response(
        data["leading_sectors"],
        data["neutral_sectors"],
        data["lagging_sectors"],
    )
    vix_indicator = data["enriched_indicators"].get("vix")
    signals = [
        {
            "label": "Market health",
            "value": market_health.overall_label,
            "score": market_health.overall_score,
        },
        {
            "label": "Fear & Greed",
            "value": fear_greed.label,
            "score": fear_greed.score,
        },
        {
            "label": "Sector breadth",
            "value": f"{sector_rotation.leading_count} leading / {sector_rotation.lagging_count} lagging",
            "score": sector_rotation.leading_count - sector_rotation.lagging_count,
        },
    ]
    if vix_indicator is not None:
        signals.append(
            {
                "label": vix_indicator.short_label,
                "value": vix_indicator.signal,
                "score": vix_indicator.value,
            }
        )
    return MacroGate(
        status=_macro_status(market_health.overall_score, fear_greed.score),
        score=market_health.overall_score,
        label=market_health.overall_label,
        fear_greed_score=fear_greed.score,
        fear_greed_label=fear_greed.label,
        vix=vix_indicator.value if vix_indicator else None,
        as_of=market_health.last_updated or market_data.current_timestamp,
        signals=signals,
    )


def _build_scanner() -> list[ScannerCandidate]:
    items = _get_watchlist_service().get_items_with_scores()
    responses = build_watchlist_item_responses(items)
    candidates: list[ScannerCandidate] = []
    for item in responses:
        score = item.current_score.overall if item.current_score else None
        candidates.append(
            ScannerCandidate(
                symbol=item.symbol,
                signal_type=item.signal_type,
                signal_strength=item.signal_strength,
                score=score,
                headline=item.narrative_headline,
                style=item.recommended_style,
                risk_level=item.risk_level,
                entry_price=item.entry_price,
                stop_loss=item.stop_loss,
                profit_target=item.profit_target,
            )
        )
    return sorted(
        candidates,
        key=lambda item: (item.signal_strength or 0, item.score or 0),
        reverse=True,
    )[:12]


def _fetch_committee_rows(symbols: list[str]) -> list[dict[str, Any]]:
    if not symbols:
        return []
    with get_storage().connection() as conn:
        result = conn.execute(
            """
            WITH ranked_runs AS (
                SELECT
                    symbol,
                    id,
                    status,
                    decision_action,
                    confidence,
                    completed_at,
                    started_at,
                    ROW_NUMBER() OVER (
                        PARTITION BY UPPER(symbol)
                        ORDER BY started_at DESC NULLS LAST
                    ) AS rank
                FROM committee_runs
                WHERE symbol IS NOT NULL AND UPPER(symbol) = ANY(%s)
            )
            SELECT
                t.symbol,
                t.action,
                t.status,
                t.expected_return_pct,
                t.cross_validation_score,
                t.updated_at,
                r.id,
                r.status,
                r.decision_action,
                r.confidence
            FROM watchlist_thesis t
            LEFT JOIN ranked_runs r ON UPPER(r.symbol) = UPPER(t.symbol) AND r.rank = 1
            WHERE UPPER(t.symbol) = ANY(%s)
            ORDER BY t.updated_at DESC NULLS LAST
            LIMIT 12
            """,
            (symbols, symbols),
        )
        rows = result.fetchall()
    return [
        {
            "symbol": row[0],
            "thesis_action": row[1],
            "thesis_status": row[2],
            "expected_return_pct": row[3],
            "cross_validation_score": row[4],
            "updated_at": row[5].isoformat() if row[5] else None,
            "committee_run_id": str(row[6]) if row[6] else None,
            "committee_status": row[7],
            "committee_action": row[8],
            "committee_confidence": row[9],
        }
        for row in rows
    ]


def _build_committee(symbols: list[str]) -> list[CommitteeCandidate]:
    rows = _fetch_committee_rows(symbols)
    return [CommitteeCandidate(**row) for row in rows]


@router.get("", response_model=TodayNextResponse)
async def get_today_next(_request: Request) -> TodayNextResponse:
    """Return three-tier Today Next stack from existing market, watchlist, and thesis data."""
    macro_gate = await run_in_threadpool(_build_macro_gate)
    scanner = await run_in_threadpool(_build_scanner)
    committee = await run_in_threadpool(
        _build_committee,
        [candidate.symbol.upper() for candidate in scanner],
    )
    return TodayNextResponse(
        macro_gate=macro_gate,
        scanner=scanner,
        committee=committee,
    )


@router.get("/", response_model=TodayNextResponse)
async def get_today_next_slash(request: Request) -> TodayNextResponse:
    return await get_today_next(request)
