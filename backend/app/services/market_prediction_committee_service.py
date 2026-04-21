"""Market prediction committee service for Portfolio AI."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any, Callable

from app.agents.clients.agent_hub_client import AgentHubAPIClient
from app.constants import PREDICTION_TARGET_SYMBOLS
from app.logging_config import get_logger
from app.models.market_prediction import (
    CommitteeSeatVote,
    MarketPredictionCall,
    MarketPredictionCommitteeResponse,
    MarketPredictionRun,
    PredictionDirection,
    PredictionSourceCluster,
)
from app.repositories.market_prediction_repository import MarketPredictionRepository
from app.services.market_events_service import get_upcoming_events
from app.services.options_flow_service import get_latest_options_flow
from app.storage import PortfolioStorage, get_storage
from app.utils.market_hours import NY_TZ, get_expected_data_date, get_next_trading_day

logger = get_logger(__name__)

SUPPORTED_PREDICTION_WINDOWS = (1, 3, 7, 14)


class MarketPredictionCommitteeService:
    """Generate and serve the latest market-prediction committee snapshot."""

    def __init__(
        self,
        *,
        repository: MarketPredictionRepository | None = None,
        storage: PortfolioStorage | None = None,
        roundtable_client_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.storage = storage or get_storage()
        self.repository = repository or MarketPredictionRepository(self.storage)
        self._roundtable_client_factory = roundtable_client_factory or AgentHubAPIClient

    def get_committee_snapshot(
        self,
        window_days: int,
        *,
        generate_if_missing: bool = True,
    ) -> MarketPredictionCommitteeResponse | None:
        self._validate_window_days(window_days)
        cached = self.repository.get_latest_committee_snapshot(window_days)
        if cached is not None or not generate_if_missing:
            return cached
        return self.generate_snapshot(window_days=window_days)

    def get_history(self, symbol: str, window_days: int, limit: int = 30) -> list[MarketPredictionCall]:
        self._validate_window_days(window_days)
        return self.repository.list_history(symbol=symbol, window_days=window_days, limit=limit)

    def generate_snapshot(
        self,
        *,
        window_days: int,
        as_of_ts: datetime | None = None,
    ) -> MarketPredictionCommitteeResponse:
        self._validate_window_days(window_days)
        generated_at = as_of_ts or datetime.now(UTC)
        if generated_at.tzinfo is None:
            generated_at = generated_at.replace(tzinfo=UTC)

        base_date = get_expected_data_date(generated_at.astimezone(NY_TZ))
        target_date = base_date
        for _ in range(window_days):
            target_date = get_next_trading_day(target_date)

        source_snapshot = self._build_source_snapshot(generated_at)
        if not isinstance(source_snapshot, dict):
            source_snapshot = {}
        source_snapshot = {
            "as_of_ts": generated_at.isoformat(),
            "target_universe": PREDICTION_TARGET_SYMBOLS,
            **source_snapshot,
        }
        if "target_universe" not in source_snapshot:
            source_snapshot["target_universe"] = PREDICTION_TARGET_SYMBOLS
        raw_payload = self._run_roundtable(
            window_days=window_days,
            base_date=base_date.isoformat(),
            target_date=target_date.isoformat(),
            source_snapshot=source_snapshot,
        )

        votes = self._normalize_votes(raw_payload.get("votes"), window_days=window_days)
        calls = self._normalize_calls(
            raw_payload.get("calls"),
            votes=votes,
            window_days=window_days,
        )
        lead_call = next((call for call in calls if call.symbol == "SPY"), calls[0])
        committee_summary = raw_payload.get("committee_summary")
        if not isinstance(committee_summary, dict):
            committee_summary = self._default_committee_summary(votes=votes, calls=calls)

        run = MarketPredictionRun(
            id=str(uuid.uuid4()),
            generated_at=generated_at,
            as_of_ts=generated_at,
            window_days=window_days,
            base_date=base_date,
            target_date=target_date,
            target_universe=PREDICTION_TARGET_SYMBOLS,
            lead_symbol=lead_call.symbol,
            lead_direction=lead_call.direction_label,
            lead_prob_up=lead_call.prob_up,
            lead_expected_move_pct=lead_call.expected_move_pct,
            source_snapshot=source_snapshot,
            committee_summary=committee_summary,
        )
        self.repository.create_run(run)
        for call in calls:
            self.repository.upsert_call(run.id, call)
        self.repository.replace_votes_for_run(run.id, votes)

        return MarketPredictionCommitteeResponse(
            as_of_ts=run.as_of_ts,
            generated_at=run.generated_at,
            window_days=window_days,
            base_date=base_date,
            target_date=target_date,
            target_universe=PREDICTION_TARGET_SYMBOLS,
            lead_call=lead_call,
            calls=calls,
            votes=votes,
            scorecard=self.repository.get_scorecard(window_days),
            committee_summary=committee_summary,
            source_snapshot=source_snapshot,
            last_evaluated_at=self.repository.get_last_evaluated_at(window_days),
        )

    def _validate_window_days(self, window_days: int) -> None:
        if window_days not in SUPPORTED_PREDICTION_WINDOWS:
            raise ValueError(
                f"Unsupported window_days={window_days}. Supported values: {', '.join(str(v) for v in SUPPORTED_PREDICTION_WINDOWS)}"
            )

    def _build_source_snapshot(self, as_of_ts: datetime) -> dict[str, Any]:
        fear_greed = self.storage.get_fear_greed_latest()
        options_flow = get_latest_options_flow(self.storage)
        events = get_upcoming_events(days=14)
        price_rows = self.storage.query(
            """
            SELECT DISTINCT ON (symbol) symbol, date, close
            FROM day_bars
            WHERE symbol = ANY(?::text[])
            ORDER BY symbol, date DESC
            """,
            [PREDICTION_TARGET_SYMBOLS],
        )
        latest_closes = {
            str(row["symbol"]): {
                "date": row["date"].isoformat() if row.get("date") else None,
                "close": float(row["close"]) if row.get("close") is not None else None,
            }
            for row in price_rows.iter_rows(named=True)
        }

        options_summary: dict[str, Any] = {
            "freshness": "missing",
            "as_of_date": None,
            "call_pct": None,
            "near_term_pct": None,
            "concentration_pct": None,
            "sector_weights": {},
        }
        if options_flow is not None:
            options_summary = {
                "freshness": "stale" if options_flow.is_stale else "fresh",
                "as_of_date": options_flow.as_of_date.isoformat() if options_flow.as_of_date else None,
                "call_pct": options_flow.call_pct,
                "near_term_pct": options_flow.near_term_pct,
                "concentration_pct": options_flow.concentration_pct,
                "sector_weights": options_flow.sector_weights,
            }

        return {
            "as_of_ts": as_of_ts.isoformat(),
            "target_universe": PREDICTION_TARGET_SYMBOLS,
            "clusters": {
                "market_regime": {
                    "freshness": "fresh" if latest_closes else "missing",
                    "latest_closes": latest_closes,
                },
                "sentiment": {
                    "freshness": "fresh" if fear_greed else "missing",
                    "fear_greed": fear_greed,
                },
                "options_positioning": options_summary,
                "macro_calendar": {
                    "freshness": "fresh" if events else "missing",
                    "upcoming_events": [event.model_dump() for event in events[:8]],
                },
            },
        }

    def _run_roundtable(
        self,
        *,
        window_days: int,
        base_date: str,
        target_date: str,
        source_snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        prompt = (
            "You are the Market Prediction Committee for Portfolio AI. "
            "Return JSON only with keys committee_summary, calls, votes. "
            "Forecast SPY plus the 11 SPDR sector ETFs for the requested trading-day window. "
            "Each call should include symbol, direction_label, prob_up, expected_move_pct, "
            "confidence_band_low_pct, confidence_band_high_pct, confidence_score, rationale_summary, and top_source_clusters. "
            "Each vote should include seat_key, agent_slug, model_id, provider, symbol, direction_label, prob_up, "
            "expected_move_pct, confidence_score, rationale_summary, and source_clusters. "
            f"Base date: {base_date}. Target date: {target_date}."
        )
        snapshot_json = json.dumps(source_snapshot, default=str, sort_keys=True)
        client = self._roundtable_client_factory(agent_slug="investment-committee")
        try:
            payload = client.run_committee_roundtable(
                prompt=prompt,
                window_days=window_days,
                source_snapshot_json=snapshot_json,
            )
        except Exception as exc:
            logger.warning("market_prediction_roundtable_failed", error=str(exc))
            payload = {
                "committee_summary": {
                    "headline": "Committee unavailable; using neutral fallback.",
                    "disagreement_label": "high",
                },
                "calls": [],
                "votes": [],
            }
        finally:
            try:
                client.close()
            except Exception:
                logger.debug("market_prediction_roundtable_close_failed", exc_info=True)

        return payload if isinstance(payload, dict) else {}

    def _normalize_votes(self, raw_votes: Any, *, window_days: int) -> list[CommitteeSeatVote]:
        if not isinstance(raw_votes, list):
            return []
        votes: list[CommitteeSeatVote] = []
        for raw in raw_votes:
            if not isinstance(raw, dict):
                continue
            symbol = str(raw.get("symbol") or "").upper()
            if symbol not in PREDICTION_TARGET_SYMBOLS:
                continue
            try:
                votes.append(
                    CommitteeSeatVote(
                        seat_key=str(raw.get("seat_key") or "committee-seat"),
                        agent_slug=str(raw.get("agent_slug") or "investment-committee"),
                        model_id=self._optional_str(raw.get("model_id")),
                        provider=self._optional_str(raw.get("provider")),
                        symbol=symbol,
                        window_days=int(raw.get("window_days") or window_days),
                        direction_label=self._direction_from_raw(raw),
                        prob_up=self._clamp(raw.get("prob_up"), 0.5),
                        expected_move_pct=self._float(raw.get("expected_move_pct"), 0.0),
                        confidence_score=self._clamp(raw.get("confidence_score"), 50.0, low=0.0, high=100.0),
                        rationale_summary=self._optional_str(raw.get("rationale_summary")),
                        source_clusters=self._normalize_clusters(raw.get("source_clusters")),
                        metadata=raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {},
                    )
                )
            except Exception:
                logger.debug("market_prediction_vote_dropped", raw_vote=raw, exc_info=True)
        return votes

    def _normalize_calls(
        self,
        raw_calls: Any,
        *,
        votes: list[CommitteeSeatVote],
        window_days: int,
    ) -> list[MarketPredictionCall]:
        call_map: dict[str, MarketPredictionCall] = {}
        if isinstance(raw_calls, list):
            for raw in raw_calls:
                if not isinstance(raw, dict):
                    continue
                symbol = str(raw.get("symbol") or "").upper()
                if symbol not in PREDICTION_TARGET_SYMBOLS:
                    continue
                try:
                    call_map[symbol] = MarketPredictionCall(
                        symbol=symbol,
                        window_days=window_days,
                        direction_label=self._direction_from_raw(raw),
                        prob_up=self._clamp(raw.get("prob_up"), 0.5),
                        expected_move_pct=self._float(raw.get("expected_move_pct"), 0.0),
                        confidence_band_low_pct=self._optional_float(raw.get("confidence_band_low_pct")),
                        confidence_band_high_pct=self._optional_float(raw.get("confidence_band_high_pct")),
                        confidence_score=self._clamp(raw.get("confidence_score"), 50.0, low=0.0, high=100.0),
                        committee_disagreement_score=self._clamp(
                            raw.get("committee_disagreement_score"),
                            self._estimate_disagreement(symbol, votes),
                            low=0.0,
                            high=1.0,
                        ),
                        rationale_summary=self._optional_str(raw.get("rationale_summary")),
                        top_source_clusters=self._normalize_clusters(raw.get("top_source_clusters")),
                        metadata=raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {},
                    )
                except Exception:
                    logger.debug("market_prediction_call_dropped", raw_call=raw, exc_info=True)

        if not call_map and votes:
            call_map = self._aggregate_calls_from_votes(votes=votes, window_days=window_days)

        ordered_calls: list[MarketPredictionCall] = []
        for symbol in PREDICTION_TARGET_SYMBOLS:
            if symbol in call_map:
                ordered_calls.append(call_map[symbol])
                continue
            ordered_calls.append(
                MarketPredictionCall(
                    symbol=symbol,
                    window_days=window_days,
                    direction_label="neutral",
                    prob_up=0.5,
                    expected_move_pct=0.0,
                    confidence_score=0.0,
                    committee_disagreement_score=1.0 if votes else 0.0,
                    rationale_summary="Committee call unavailable; neutral fallback applied.",
                    top_source_clusters=[],
                )
            )
        return ordered_calls

    def _aggregate_calls_from_votes(
        self,
        *,
        votes: list[CommitteeSeatVote],
        window_days: int,
    ) -> dict[str, MarketPredictionCall]:
        by_symbol: dict[str, list[CommitteeSeatVote]] = {}
        for vote in votes:
            by_symbol.setdefault(vote.symbol, []).append(vote)

        calls: dict[str, MarketPredictionCall] = {}
        for symbol, symbol_votes in by_symbol.items():
            avg_prob = sum(vote.prob_up for vote in symbol_votes) / len(symbol_votes)
            avg_move = sum(vote.expected_move_pct for vote in symbol_votes) / len(symbol_votes)
            avg_conf = sum(float(vote.confidence_score or 50.0) for vote in symbol_votes) / len(symbol_votes)
            low_band = min(vote.expected_move_pct for vote in symbol_votes)
            high_band = max(vote.expected_move_pct for vote in symbol_votes)
            calls[symbol] = MarketPredictionCall(
                symbol=symbol,
                window_days=window_days,
                direction_label=self._derive_direction(avg_prob, avg_move),
                prob_up=avg_prob,
                expected_move_pct=avg_move,
                confidence_band_low_pct=low_band,
                confidence_band_high_pct=high_band,
                confidence_score=avg_conf,
                committee_disagreement_score=self._estimate_disagreement(symbol, symbol_votes),
                rationale_summary="Consensus synthesized from seat-level committee votes.",
                top_source_clusters=self._top_clusters_from_votes(symbol_votes),
            )
        return calls

    def _default_committee_summary(
        self,
        *,
        votes: list[CommitteeSeatVote],
        calls: list[MarketPredictionCall],
    ) -> dict[str, Any]:
        disagreement = max((call.committee_disagreement_score or 0.0 for call in calls), default=0.0)
        return {
            "headline": "Committee snapshot generated.",
            "seat_count": len({vote.seat_key for vote in votes}),
            "disagreement_label": "high" if disagreement >= 0.67 else "moderate" if disagreement >= 0.34 else "low",
        }

    def _estimate_disagreement(self, symbol: str, votes: list[CommitteeSeatVote]) -> float:
        symbol_votes = [vote for vote in votes if vote.symbol == symbol]
        if len(symbol_votes) < 2:
            return 0.0
        probs = [vote.prob_up for vote in symbol_votes]
        return min(1.0, max(probs) - min(probs))

    def _top_clusters_from_votes(self, votes: list[CommitteeSeatVote]) -> list[PredictionSourceCluster]:
        totals: dict[str, float] = {}
        notes: dict[str, str | None] = {}
        for vote in votes:
            for cluster in vote.source_clusters:
                totals[cluster.cluster] = totals.get(cluster.cluster, 0.0) + float(cluster.weight or 0.0)
                notes.setdefault(cluster.cluster, cluster.note)
        ordered = sorted(totals.items(), key=lambda item: item[1], reverse=True)[:3]
        return [
            PredictionSourceCluster(cluster=cluster, weight=weight, note=notes.get(cluster))
            for cluster, weight in ordered
        ]

    def _normalize_clusters(self, raw_clusters: Any) -> list[PredictionSourceCluster]:
        if not isinstance(raw_clusters, list):
            return []
        clusters: list[PredictionSourceCluster] = []
        for raw in raw_clusters[:5]:
            if not isinstance(raw, dict):
                continue
            cluster = self._optional_str(raw.get("cluster"))
            if not cluster:
                continue
            clusters.append(
                PredictionSourceCluster(
                    cluster=cluster,
                    weight=self._optional_float(raw.get("weight")),
                    freshness=self._optional_str(raw.get("freshness")),
                    note=self._optional_str(raw.get("note")),
                )
            )
        return clusters

    def _direction_from_raw(self, raw: dict[str, Any]) -> PredictionDirection:
        explicit = self._optional_str(raw.get("direction_label"))
        if explicit in {"bullish", "neutral", "bearish"}:
            return explicit
        return self._derive_direction(
            self._clamp(raw.get("prob_up"), 0.5),
            self._float(raw.get("expected_move_pct"), 0.0),
        )

    def _derive_direction(self, prob_up: float, expected_move_pct: float) -> PredictionDirection:
        if prob_up >= 0.55 and expected_move_pct > 0:
            return "bullish"
        if prob_up <= 0.45 and expected_move_pct < 0:
            return "bearish"
        return "neutral"

    @staticmethod
    def _clamp(value: Any, fallback: float, *, low: float = 0.0, high: float = 1.0) -> float:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            numeric = fallback
        return max(low, min(high, numeric))

    @staticmethod
    def _float(value: Any, fallback: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return fallback

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        try:
            return None if value is None else float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _optional_str(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None
