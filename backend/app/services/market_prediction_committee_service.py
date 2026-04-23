"""Market prediction committee service for Portfolio AI."""

from __future__ import annotations

import hashlib
import json
import math
import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any, cast

from app.agents.clients.agent_hub_client import AgentHubAPIClient
from app.constants import MARKET_SYMBOL, PREDICTION_TARGET_SYMBOLS
from app.logging_config import get_logger
from app.models.market_prediction import (
    SUPPORTED_ADAPTIVE_CLUSTER_KEYS,
    SUPPORTED_ADAPTIVE_SEAT_KEYS,
    CommitteeSeatVote,
    MarketPredictionCall,
    MarketPredictionClusterReview,
    MarketPredictionCommitteeResponse,
    MarketPredictionResolvedSeatWeight,
    MarketPredictionRun,
    MarketPredictionScorecard,
    MarketPredictionSeatReview,
    PredictionDirection,
    PredictionFreshnessCluster,
    PredictionFreshnessSummary,
    PredictionSourceCluster,
    normalize_market_prediction_cluster_key,
    normalize_market_prediction_seat_key,
)
from app.repositories.market_prediction_repository import MarketPredictionRepository
from app.services.market_events_service import (
    build_default_macro_calendar_cluster,
    get_macro_calendar_cluster,
)
from app.services.options_flow_service import get_latest_options_flow
from app.sources.fred import FREDSource
from app.storage import PortfolioStorage, get_storage
from app.utils.market_hours import (
    NY_TZ,
    get_expected_data_date,
    get_market_status,
    get_next_trading_day,
    is_market_holiday,
    is_trading_day,
)

logger = get_logger(__name__)

SUPPORTED_PREDICTION_WINDOWS = (1, 3, 7, 14)
ALLOWED_CLUSTER_FRESHNESS = {"fresh", "stale", "missing", "unknown"}
FRESHNESS_RANK = {"fresh": 0, "stale": 1, "missing": 2, "unknown": 3}
PREDICTION_FRESHNESS_RANK = {"fresh": 0, "aging": 1, "stale": 2, "invalid": 3, "degraded": 4}
DEFAULT_FETCH_ERROR_NOTE = "Committee snapshot unavailable; serving degraded fallback."
DEFAULT_PENDING_TARGET_NOTE = "Target date has not been reached yet."
DEFAULT_WAITING_AFTER_CLOSE_NOTE = "Target date passed; awaiting evaluation data."
DEFAULT_SPARSE_HISTORY_NOTE = "Not enough comparable history for a stable trend."
DEFAULT_LEGACY_SPARSE_NOTE = "Legacy sparse data: selected lead attribution unavailable."
DEFAULT_ATTRIBUTION_NOTE = "Derived fallback; tracked not ranked."
DEFAULT_UNATTRIBUTED_NOTE = "Derived fallback; no usable source snapshot."
CRITICAL_FRESHNESS_CLUSTERS = ("market_regime", "options_positioning", "macro_calendar")
SESSION_FRESHNESS_THRESHOLDS_SECONDS = {
    "open": (20 * 60, 60 * 60, 2 * 60 * 60),
    "pre_market": (60 * 60, 3 * 60 * 60, 6 * 60 * 60),
    "after_hours": (60 * 60, 3 * 60 * 60, 8 * 60 * 60),
    "closed": (3 * 60 * 60, 12 * 60 * 60, 24 * 60 * 60),
}
DEFAULT_ROSTER = [
    {"seat_key": "cross_asset", "agent_slug": "equity-analyst", "model_id": "grok-4.20-reasoning"},
    {"seat_key": "macro", "agent_slug": "market-pulse-analyst", "model_id": "gpt-5.4"},
    {"seat_key": "risk", "agent_slug": "risk-manager", "model_id": "claude-opus-4-7"},
]
MAG7_TICKERS = ["AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA"]
MAG7_SECTOR_PROXIES = ["XLK", "XLC", "XLY"]
WTI_SERIES_ID = "DCOILWTICO"
SEAT_CLUSTER_PREFERENCES = {
    "macro": ["macro_calendar", "sentiment", "market_regime"],
    "macro_risk": ["macro_calendar", "options_positioning", "market_regime"],
    "cross_asset": ["market_regime", "sentiment", "macro_calendar"],
    "technical_regime": ["market_regime", "sentiment", "options_positioning"],
    "positioning": ["options_positioning", "market_regime", "macro_calendar"],
    "risk": ["options_positioning", "macro_calendar", "market_regime"],
}


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
        request_now = datetime.now(UTC)
        try:
            cached = self.repository.get_latest_committee_snapshot(window_days)
            if cached is not None:
                return self._normalize_response(cached, market_now=request_now)
            if not generate_if_missing:
                return None
            return self.generate_snapshot(window_days=window_days, as_of_ts=request_now)
        except Exception as exc:
            logger.warning("market_prediction_snapshot_read_failed", error=str(exc), exc_info=True)
            return self._build_degraded_response(window_days=window_days, as_of_ts=request_now)

    def get_history(self, symbol: str, window_days: int, limit: int = 30) -> list[MarketPredictionCall]:
        self._validate_window_days(window_days)
        calls: list[MarketPredictionCall] = []
        for raw_call in self.repository.list_history(symbol=symbol, window_days=window_days, limit=limit):
            normalized = self._normalize_call_model(raw_call)
            if normalized is not None:
                calls.append(normalized)
        return calls

    def generate_snapshot(
        self,
        *,
        window_days: int,
        as_of_ts: datetime | None = None,
        review: MarketPredictionSeatReview | dict[str, Any] | None = None,
        cluster_review: MarketPredictionClusterReview | dict[str, Any] | None = None,
        source_snapshot: dict[str, Any] | None = None,
    ) -> MarketPredictionCommitteeResponse:
        self._validate_window_days(window_days)
        generated_at = self._coerce_datetime(as_of_ts or datetime.now(UTC))
        base_date, target_date = self._compute_dates(window_days=window_days, as_of_ts=generated_at)

        try:
            source_snapshot = source_snapshot or self.build_source_snapshot(generated_at)
            source_snapshot = {
                **(source_snapshot if isinstance(source_snapshot, dict) else {}),
                "as_of_ts": generated_at.isoformat(),
                "target_universe": PREDICTION_TARGET_SYMBOLS,
            }
            raw_payload = self._run_roundtable(
                window_days=window_days,
                base_date=base_date.isoformat(),
                target_date=target_date.isoformat(),
                source_snapshot=source_snapshot,
            )

            raw_votes = raw_payload.get("votes") if isinstance(raw_payload, dict) else None
            votes = self._normalize_votes_for_generation(
                raw_votes,
                window_days=window_days,
                source_snapshot=source_snapshot,
            )
            review_artifact = self._coerce_review(review=review, window_days=window_days, as_of_ts=generated_at)
            cluster_review_artifact = self._coerce_cluster_review(
                review=cluster_review,
                window_days=window_days,
                as_of_ts=generated_at,
                source_snapshot=source_snapshot,
            )

            calls = self._aggregate_calls_from_votes(
                raw_votes=raw_votes,
                votes=votes,
                window_days=window_days,
                review=review_artifact,
                cluster_review=cluster_review_artifact,
                source_snapshot=source_snapshot,
            )
            lead_call = next((call for call in calls if call.symbol == "SPY"), calls[0])

            committee_summary_raw = raw_payload.get("committee_summary") if isinstance(raw_payload, dict) else None
            if not isinstance(committee_summary_raw, dict):
                committee_summary_raw = self._default_committee_summary(votes=votes, calls=calls)

            executed_seats = self._extract_executed_seats(
                raw_votes=raw_votes,
                committee_config=raw_payload.get("committee_config") if isinstance(raw_payload, dict) else None,
            )
            metadata = self._build_run_metadata(
                existing=None,
                executed_seats=executed_seats,
                committee_execution_path=self._normalize_execution_path(
                    raw_payload.get("_portfolio_execution_path") if isinstance(raw_payload, dict) else None
                ),
                review=review_artifact,
                cluster_review=cluster_review_artifact,
            )
            source_snapshot = self._apply_cluster_review_to_source_snapshot(
                source_snapshot=source_snapshot,
                cluster_review=cluster_review_artifact,
            )
            scorecard = self.repository.get_scorecard(window_days)
            last_evaluated_at = self.repository.get_last_evaluated_at(window_days)

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
                committee_summary=committee_summary_raw,
                metadata=metadata,
            )
            if hasattr(self.repository, "persist_snapshot"):
                self.repository.persist_snapshot(run=run, calls=calls, votes=votes)
            else:
                self.repository.create_run(run)
                for call in calls:
                    self.repository.upsert_call(run.id, call)
                self.repository.replace_votes_for_run(run.id, votes)

            response = MarketPredictionCommitteeResponse(
                as_of_ts=run.as_of_ts,
                generated_at=run.generated_at,
                window_days=window_days,
                base_date=base_date,
                target_date=target_date,
                target_universe=PREDICTION_TARGET_SYMBOLS,
                lead_call=lead_call,
                calls=calls,
                votes=votes,
                scorecard=scorecard,
                committee_summary=committee_summary_raw,
                source_snapshot=source_snapshot,
                last_evaluated_at=last_evaluated_at,
            )
            response._storage_metadata = metadata
            return self._normalize_response(response, market_now=generated_at)
        except Exception as exc:
            logger.warning("market_prediction_snapshot_generation_failed", error=str(exc), exc_info=True)
            return self._build_degraded_response(window_days=window_days, as_of_ts=generated_at)

    def _validate_window_days(self, window_days: int) -> None:
        if window_days not in SUPPORTED_PREDICTION_WINDOWS:
            raise ValueError(
                f"Unsupported window_days={window_days}. Supported values: {', '.join(str(v) for v in SUPPORTED_PREDICTION_WINDOWS)}"
            )

    def _compute_dates(self, *, window_days: int, as_of_ts: datetime) -> tuple[date, date]:
        base_date = get_expected_data_date(as_of_ts.astimezone(NY_TZ))
        target_date = base_date
        for _ in range(window_days):
            target_date = get_next_trading_day(target_date)
        return base_date, target_date

    def build_source_snapshot(self, as_of_ts: datetime) -> dict[str, Any]:
        effective_ts = self._coerce_datetime(as_of_ts)
        source_snapshot = self._build_source_snapshot(effective_ts)
        return {
            **(source_snapshot if isinstance(source_snapshot, dict) else {}),
            "as_of_ts": effective_ts.isoformat(),
            "target_universe": PREDICTION_TARGET_SYMBOLS,
        }

    def _build_source_snapshot(self, as_of_ts: datetime) -> dict[str, Any]:
        fear_greed = self.storage.get_fear_greed_latest()
        options_flow = get_latest_options_flow(self.storage)
        market_date = get_expected_data_date(as_of_ts.astimezone(NY_TZ))
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

        try:
            macro_calendar = get_macro_calendar_cluster(
                market_date=market_date,
                existing={"upcoming_events": []},
                storage=self.storage,
            )
        except Exception:
            logger.warning("market_prediction_macro_calendar_helper_failed", exc_info=True)
            macro_calendar = build_default_macro_calendar_cluster({"upcoming_events": []})

        clusters = {
            "market_regime": {
                "freshness": "fresh" if latest_closes else "missing",
                "latest_closes": latest_closes,
            },
            "sentiment": {
                "freshness": "fresh" if fear_greed else "missing",
                "fear_greed": fear_greed,
            },
            "options_positioning": options_summary,
            "macro_calendar": macro_calendar,
            "mag7_sector_leadership": self._build_mag7_sector_leadership_cluster(as_of_ts=as_of_ts),
            "overnight_premarket_afterhours_futures_news": self._build_overnight_premarket_afterhours_futures_news_cluster(as_of_ts=as_of_ts),
            "oil_shock_overlay": self._build_oil_shock_overlay_cluster(as_of_ts=as_of_ts),
            "holiday_turn_of_month": self._build_holiday_turn_of_month_cluster(as_of_ts=as_of_ts),
            "day_of_week": self._build_day_of_week_cluster(as_of_ts=as_of_ts),
            "freight_transport_event": self._build_freight_transport_event_cluster(as_of_ts=as_of_ts),
        }

        return {
            "as_of_ts": as_of_ts.isoformat(),
            "target_universe": PREDICTION_TARGET_SYMBOLS,
            "clusters": clusters,
        }

    def _query_recent_closes(self, symbols: list[str], *, limit_per_symbol: int = 2) -> dict[str, list[tuple[date, float]]]:
        rows = self.storage.query(
            """
            SELECT symbol, date, close
            FROM (
                SELECT symbol, date, close,
                       ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date DESC) AS rn
                FROM day_bars
                WHERE symbol = ANY(?::text[])
            ) ranked
            WHERE rn <= ?
            ORDER BY symbol ASC, date DESC
            """,
            [symbols, limit_per_symbol],
        )
        grouped: dict[str, list[tuple[date, float]]] = {symbol: [] for symbol in symbols}
        for row in rows.iter_rows(named=True):
            symbol = str(row.get("symbol") or "").upper()
            row_date = row.get("date")
            close = row.get("close")
            if symbol not in grouped or not isinstance(row_date, date) or close is None:
                continue
            try:
                close_value = float(close)
            except (TypeError, ValueError):
                continue
            if not math.isfinite(close_value):
                continue
            grouped[symbol].append((row_date, close_value))
        return grouped

    def _build_mag7_sector_leadership_cluster(self, *, as_of_ts: datetime) -> dict[str, Any]:
        effective_market_date = get_expected_data_date(as_of_ts.astimezone(NY_TZ))
        history = self._query_recent_closes(MAG7_TICKERS + MAG7_SECTOR_PROXIES, limit_per_symbol=2)
        available_tickers: list[str] = []
        latest_dates: list[date] = []
        symbol_changes: dict[str, float] = {}
        for symbol in MAG7_TICKERS:
            rows = history.get(symbol, [])
            if len(rows) < 2:
                continue
            latest_date, latest_close = rows[0]
            _, prior_close = rows[1]
            if prior_close == 0:
                continue
            available_tickers.append(symbol)
            latest_dates.append(latest_date)
            symbol_changes[symbol] = ((latest_close / prior_close) - 1.0) * 100.0
        sector_proxy_changes = dict.fromkeys(MAG7_SECTOR_PROXIES)
        proxy_ok = True
        for symbol in MAG7_SECTOR_PROXIES:
            rows = history.get(symbol, [])
            if len(rows) < 2:
                proxy_ok = False
                continue
            latest_date, latest_close = rows[0]
            _, prior_close = rows[1]
            if prior_close == 0:
                proxy_ok = False
                continue
            latest_dates.append(latest_date)
            sector_proxy_changes[symbol] = ((latest_close / prior_close) - 1.0) * 100.0
        latest_common_date = min(latest_dates).isoformat() if latest_dates else None
        missing_tickers = [symbol for symbol in MAG7_TICKERS if symbol not in available_tickers]
        freshness = "missing"
        if len(available_tickers) >= 4 and proxy_ok and latest_common_date is not None:
            freshness = "fresh" if latest_common_date == effective_market_date.isoformat() else "stale"
        leader_symbol = laggard_symbol = None
        leader_change_pct = laggard_change_pct = average_change_pct = None
        if symbol_changes:
            ordered = sorted(symbol_changes.items(), key=lambda item: item[1], reverse=True)
            leader_symbol, leader_change_pct = ordered[0]
            laggard_symbol, laggard_change_pct = ordered[-1]
            average_change_pct = sum(symbol_changes.values()) / len(symbol_changes)
        return {
            "freshness": freshness,
            "mag7_tickers": MAG7_TICKERS,
            "available_tickers": available_tickers,
            "missing_tickers": missing_tickers,
            "latest_common_date": latest_common_date,
            "average_change_pct": average_change_pct,
            "leader_symbol": leader_symbol,
            "leader_change_pct": leader_change_pct,
            "laggard_symbol": laggard_symbol,
            "laggard_change_pct": laggard_change_pct,
            "sector_proxy_changes": sector_proxy_changes,
            "note": None,
        }

    def _load_market_news_stats(self, *, as_of_ts: datetime) -> dict[str, Any]:
        window_start = as_of_ts - timedelta(hours=24)
        rows = self.storage.query(
            """
            SELECT
                MAX(published_at) AS latest_published_at,
                SUM(CASE WHEN published_at >= ? AND published_at <= ? THEN 1 ELSE 0 END) AS recent_count
            FROM news_cache
            WHERE symbol = ?
              AND published_at IS NOT NULL
              AND published_at <= ?
            """,
            [window_start, as_of_ts, MARKET_SYMBOL, as_of_ts],
        )
        row = next(rows.iter_rows(named=True), {})
        latest_published_at = row.get("latest_published_at")
        recent_count = int(row.get("recent_count") or 0)
        return {
            "latest_published_at": latest_published_at.isoformat() if isinstance(latest_published_at, datetime) else None,
            "recent_count": recent_count,
        }

    def _build_overnight_premarket_afterhours_futures_news_cluster(self, *, as_of_ts: datetime) -> dict[str, Any]:
        effective_market_date = get_expected_data_date(as_of_ts.astimezone(NY_TZ))
        news_stats = self._load_market_news_stats(as_of_ts=as_of_ts)
        spy_history = self._query_recent_closes(["SPY"], limit_per_symbol=2).get("SPY", [])
        news_state = "news_missing"
        latest_news_iso = news_stats["latest_published_at"]
        if latest_news_iso is not None:
            latest_news_dt = datetime.fromisoformat(latest_news_iso.replace("Z", "+00:00"))
            news_state = "news_fresh" if latest_news_dt >= as_of_ts - timedelta(hours=24) else "news_stale"
        price_state = "price_missing"
        spy_latest_close_date = None
        spy_gap_proxy_pct = None
        if len(spy_history) >= 2:
            latest_date, latest_close = spy_history[0]
            _, prior_close = spy_history[1]
            spy_latest_close_date = latest_date.isoformat()
            if prior_close != 0:
                spy_gap_proxy_pct = ((latest_close / prior_close) - 1.0) * 100.0
            price_state = "price_fresh" if latest_date == effective_market_date else "price_stale"
        if news_state == "news_fresh" and price_state == "price_fresh":
            freshness = "fresh"
        elif news_state == "news_missing" and price_state == "price_missing":
            freshness = "missing"
        else:
            freshness = "stale"
        return {
            "freshness": freshness,
            "market_status": str(get_market_status(as_of_ts.astimezone(NY_TZ))),
            "latest_market_news_at": latest_news_iso,
            "recent_market_news_count_24h": news_stats["recent_count"],
            "spy_latest_close_date": spy_latest_close_date,
            "spy_gap_proxy_pct": spy_gap_proxy_pct,
            "note": None,
        }

    def _load_oil_observations(self, *, market_date: date) -> list[tuple[date, float]]:
        rows = self.storage.query(
            """
            SELECT observation_date, value
            FROM macro_indicators
            WHERE (indicator_name = ? OR series_id = ?)
              AND observation_date <= ?
            ORDER BY observation_date DESC
            LIMIT 5
            """,
            [WTI_SERIES_ID, WTI_SERIES_ID, market_date],
        )
        observations: list[tuple[date, float]] = []
        for row in rows.iter_rows(named=True):
            observation_date = row.get("observation_date")
            value = row.get("value")
            if not isinstance(observation_date, date) or value is None:
                continue
            try:
                numeric_value = float(value)
            except (TypeError, ValueError):
                continue
            if not math.isfinite(numeric_value):
                continue
            observations.append((observation_date, numeric_value))
        if len(observations) >= 2:
            return observations[:2]
        fred = FREDSource()
        series = fred.fetch_series(WTI_SERIES_ID, start_date=market_date - timedelta(days=10), end_date=market_date)
        cleaned = [(obs_date, obs_value) for obs_date, obs_value in series if obs_date <= market_date and math.isfinite(float(obs_value))]
        cleaned.sort(key=lambda item: item[0], reverse=True)
        return cleaned[:2]

    def _build_oil_shock_overlay_cluster(self, *, as_of_ts: datetime) -> dict[str, Any]:
        market_date = get_expected_data_date(as_of_ts.astimezone(NY_TZ))
        observations = self._load_oil_observations(market_date=market_date)
        if len(observations) < 2:
            return {
                "freshness": "missing",
                "gate_state": "missing",
                "canonical_series": WTI_SERIES_ID,
                "latest_observation_date": None,
                "latest_value": None,
                "prior_value": None,
                "daily_change_pct": None,
                "event_tags": [],
                "note": None,
            }
        (latest_date, latest_value), (_, prior_value) = observations[:2]
        daily_change_pct = None if prior_value == 0 else ((latest_value / prior_value) - 1.0) * 100.0
        freshness = "fresh" if latest_date == market_date else "stale"
        gate_state = "active" if daily_change_pct is not None and abs(daily_change_pct) >= 2.0 else "off"
        return {
            "freshness": freshness,
            "gate_state": gate_state,
            "canonical_series": WTI_SERIES_ID,
            "latest_observation_date": latest_date.isoformat(),
            "latest_value": latest_value,
            "prior_value": prior_value,
            "daily_change_pct": daily_change_pct,
            "event_tags": [],
            "note": None,
        }

    def _build_holiday_turn_of_month_cluster(self, *, as_of_ts: datetime) -> dict[str, Any]:
        market_date = get_expected_data_date(as_of_ts.astimezone(NY_TZ))
        first_three: list[date] = []
        cursor = market_date.replace(day=1)
        while len(first_three) < 3 and cursor.month == market_date.month:
            if is_trading_day(cursor):
                first_three.append(cursor)
            cursor += timedelta(days=1)
        next_trading = get_next_trading_day(market_date)
        after_next = get_next_trading_day(next_trading)
        is_last_two = next_trading.month != market_date.month or after_next.month != market_date.month
        holiday_name = None
        probe = market_date + timedelta(days=1)
        while probe < next_trading:
            is_holiday, maybe_name = is_market_holiday(probe)
            if is_holiday:
                holiday_name = maybe_name
                break
            probe += timedelta(days=1)
        is_pre_holiday = holiday_name is not None
        is_first_three = market_date in first_three
        gate_state = "active" if is_first_three or is_last_two or is_pre_holiday else "off"
        return {
            "freshness": "fresh",
            "gate_state": gate_state,
            "market_date": market_date.isoformat(),
            "is_first_three_trading_days": is_first_three,
            "is_last_two_trading_days": is_last_two,
            "is_pre_holiday_trading_day": is_pre_holiday,
            "next_full_holiday_name": holiday_name,
            "note": None,
        }

    def _build_day_of_week_cluster(self, *, as_of_ts: datetime) -> dict[str, Any]:
        local_dt = as_of_ts.astimezone(NY_TZ)
        weekday = local_dt.strftime("%A").lower()
        trading = is_trading_day(local_dt.date())
        return {
            "freshness": "fresh" if trading else "missing",
            "gate_state": "tracked_only",
            "calendar_weekday": weekday,
            "trading_weekday": weekday if trading else None,
            "is_trading_day": trading,
            "note": None,
        }

    def _build_freight_transport_event_cluster(self, *, as_of_ts: datetime) -> dict[str, Any]:
        del as_of_ts
        return {
            "freshness": "fresh",
            "gate_state": "tracked_only",
            "event_tags": [],
            "note": None,
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
                "_portfolio_execution_path": "fallback_completion",
            }
        finally:
            try:
                client.close()
            except Exception:
                logger.debug("market_prediction_roundtable_close_failed", exc_info=True)

        return payload if isinstance(payload, dict) else {}

    def _normalize_response(
        self,
        response: MarketPredictionCommitteeResponse,
        *,
        market_now: datetime | None = None,
    ) -> MarketPredictionCommitteeResponse:
        effective_now = self._coerce_datetime(market_now or datetime.now(UTC))
        market_date = get_expected_data_date(effective_now.astimezone(NY_TZ))
        calls = [call for raw_call in response.calls if (call := self._normalize_call_model(raw_call)) is not None]
        votes = [vote for raw_vote in response.votes if (vote := self._normalize_vote_model(raw_vote)) is not None]
        lead_call, legacy_sparse = self._select_public_lead_call(
            raw_lead_call=response.lead_call,
            calls=calls,
            window_days=response.window_days,
        )
        normalized_scorecard = self._normalize_scorecard(response.scorecard)
        normalized_source_snapshot = self._normalize_public_snapshot_contract(
            raw_snapshot=response.source_snapshot,
            market_date=market_date,
        )
        metadata = self._normalize_metadata(getattr(response, "_storage_metadata", {}))
        truth_state = self._determine_truth_state(
            lead_call=lead_call,
            window_days=response.window_days,
            target_date=response.target_date,
            market_date=market_date,
            scorecard=normalized_scorecard,
            legacy_sparse=legacy_sparse,
        )
        scorecard_status_note = self._scorecard_status_note(truth_state)
        committee_summary = self._normalize_committee_summary(
            raw_summary=response.committee_summary,
            metadata=metadata,
            truth_state=truth_state,
            scorecard_status_note=scorecard_status_note,
            as_of_ts=response.as_of_ts,
        )
        normalized = response.model_copy(
            update={
                "lead_call": lead_call,
                "calls": calls,
                "votes": votes,
                "scorecard": normalized_scorecard,
                "committee_summary": committee_summary,
                "source_snapshot": normalized_source_snapshot,
                "target_universe": self._normalize_target_universe(response.target_universe),
                "freshness_summary": self._build_freshness_summary(
                    response=response,
                    truth_state=truth_state,
                    source_snapshot=normalized_source_snapshot,
                    market_now=effective_now,
                    market_date=market_date,
                ),
            }
        )
        normalized._storage_metadata = metadata
        return normalized

    def _normalize_public_snapshot_contract(
        self,
        *,
        raw_snapshot: Any,
        market_date: date,
    ) -> dict[str, Any]:
        snapshot = dict(raw_snapshot) if isinstance(raw_snapshot, dict) else {}
        normalized_clusters = self._normalize_source_snapshot_clusters(snapshot.get("clusters"))
        normalized_clusters["market_regime"] = self._normalize_market_regime_cluster(
            normalized_clusters.get("market_regime"),
            market_date=market_date,
        )
        normalized_clusters["options_positioning"] = self._normalize_options_positioning_cluster(
            normalized_clusters.get("options_positioning"),
            market_date=market_date,
        )
        existing_macro = normalized_clusters.get("macro_calendar")
        try:
            macro_calendar = get_macro_calendar_cluster(
                market_date=market_date,
                existing=existing_macro if isinstance(existing_macro, dict) else None,
                storage=self.storage,
            )
        except Exception:
            logger.warning("market_prediction_macro_calendar_normalization_failed", exc_info=True)
            macro_calendar = dict(existing_macro) if isinstance(existing_macro, dict) else {}
            macro_calendar["freshness"] = self._normalize_source_freshness(macro_calendar.get("freshness"))
        if isinstance(existing_macro, dict):
            for key in ("prior_weight", "effective_weight", "sample_size", "skill_score"):
                if key in existing_macro and key not in macro_calendar:
                    macro_calendar[key] = existing_macro[key]
        normalized_clusters["macro_calendar"] = macro_calendar
        snapshot["clusters"] = normalized_clusters
        if "target_universe" not in snapshot or not isinstance(snapshot.get("target_universe"), list):
            snapshot["target_universe"] = PREDICTION_TARGET_SYMBOLS
        return snapshot

    def _normalize_market_regime_cluster(
        self,
        raw_cluster: Any,
        *,
        market_date: date,
    ) -> dict[str, Any]:
        cluster = dict(raw_cluster) if isinstance(raw_cluster, dict) else {}
        latest_closes = cluster.get("latest_closes") if isinstance(cluster.get("latest_closes"), dict) else {}
        latest_dates = [
            normalized_date
            for payload in latest_closes.values()
            if isinstance(payload, dict)
            and (normalized_date := self._normalize_iso_date(payload.get("date"))) is not None
        ]
        if latest_dates:
            latest_common_date = min(latest_dates)
            cluster["latest_common_date"] = latest_common_date
            cluster["freshness"] = "fresh" if latest_common_date == market_date.isoformat() else "stale"
            return cluster
        cluster["freshness"] = "missing"
        cluster["latest_common_date"] = None
        return cluster

    def _normalize_options_positioning_cluster(
        self,
        raw_cluster: Any,
        *,
        market_date: date,
    ) -> dict[str, Any]:
        cluster = dict(raw_cluster) if isinstance(raw_cluster, dict) else {}
        as_of_date = self._normalize_iso_date(cluster.get("as_of_date"))
        if as_of_date is not None:
            cluster["as_of_date"] = as_of_date
            cluster["freshness"] = "fresh" if as_of_date == market_date.isoformat() else "stale"
            return cluster
        if any(cluster.get(key) is not None for key in ("call_pct", "near_term_pct", "concentration_pct")):
            cluster["freshness"] = self._normalize_source_freshness(cluster.get("freshness"))
            return cluster
        cluster["freshness"] = "missing"
        return cluster

    def _normalize_source_snapshot_clusters(self, raw_clusters: Any) -> dict[str, dict[str, Any]]:
        if not isinstance(raw_clusters, dict):
            return {}
        grouped: dict[str, list[tuple[str, dict[str, Any]]]] = {}
        for raw_key, raw_value in raw_clusters.items():
            trimmed_key = str(raw_key).strip()
            if not trimmed_key or not isinstance(raw_value, dict):
                continue
            grouped.setdefault(trimmed_key, []).append((str(raw_key), dict(raw_value)))

        normalized: dict[str, dict[str, Any]] = {}
        for trimmed_key in sorted(grouped, key=lambda value: (value.lower(), value)):
            raw_key, value = min(
                grouped[trimmed_key],
                key=lambda item: (trimmed_key.lower(), trimmed_key, item[0]),
            )
            del raw_key
            if "freshness" in value:
                value["freshness"] = self._normalize_source_freshness(value.get("freshness"))
            normalized[trimmed_key] = value
        return normalized

    def _normalize_committee_summary(
        self,
        *,
        raw_summary: Any,
        metadata: dict[str, Any],
        truth_state: str,
        scorecard_status_note: str | None,
        as_of_ts: datetime,
    ) -> dict[str, Any]:
        summary = dict(raw_summary) if isinstance(raw_summary, dict) else {}
        summary.pop("_portfolio_execution_path", None)
        executed_seats = self._normalize_executed_seats(metadata.get("executed_seats"))
        resolved_seat_weights = self._normalize_resolved_seat_weights(metadata.get("resolved_seat_weights"))
        review_state = self._optional_str(metadata.get("review_state"))
        summary.update(
            {
                "committee_roster_mode": self._normalize_roster_mode(metadata.get("committee_roster_mode")),
                "committee_execution_path": self._normalize_execution_path(metadata.get("committee_execution_path")),
                "executed_seat_keys": [seat["seat_key"] for seat in executed_seats],
                "truth_state": truth_state,
                "scorecard_status_note": scorecard_status_note,
                "resolved_seat_weights": resolved_seat_weights,
                "review_state": review_state,
                "review_as_of_ts": as_of_ts.isoformat() if review_state is not None or resolved_seat_weights else None,
                "review_row_id": self._optional_str(metadata.get("review_row_id")),
            }
        )
        return summary

    def _build_freshness_summary(
        self,
        *,
        response: MarketPredictionCommitteeResponse,
        truth_state: str,
        source_snapshot: dict[str, Any],
        market_now: datetime,
        market_date: date,
    ) -> PredictionFreshnessSummary:
        market_status = str(get_market_status(market_now.astimezone(NY_TZ)))
        generated_at = self._coerce_datetime(response.generated_at)
        generated_age_seconds = max(0, int((market_now - generated_at).total_seconds()))
        evaluated_at = self._coerce_datetime(response.last_evaluated_at) if response.last_evaluated_at else None
        evaluated_age_seconds = (
            max(0, int((market_now - evaluated_at).total_seconds()))
            if evaluated_at is not None
            else None
        )
        current_local_date = market_now.astimezone(NY_TZ).date()
        generated_local_date = generated_at.astimezone(NY_TZ).date()
        generated_market_date = get_expected_data_date(generated_at.astimezone(NY_TZ))
        critical_clusters = self._build_freshness_clusters(source_snapshot)
        reason_codes: list[str] = []

        state = "fresh"
        invalidated = False
        if truth_state == "fetch_error":
            state = "degraded"
            invalidated = True
            reason_codes.append("fetch_error")
        elif truth_state == "waiting_after_close":
            state = "invalid"
            invalidated = True
            reason_codes.append("target_reached_pending_evaluation")
        elif (
            generated_local_date < current_local_date
            and market_status in {"pre_market", "open", "after_hours"}
        ) or generated_market_date < market_date:
            state = "invalid"
            invalidated = True
            reason_codes.append("previous_market_session")
        else:
            aging_after, stale_after, invalid_after = self._freshness_thresholds_for_market_status(market_status)
            if generated_age_seconds >= invalid_after:
                state = "invalid"
                invalidated = True
                reason_codes.append("snapshot_age")
            elif generated_age_seconds >= stale_after:
                state = "stale"
                reason_codes.append("snapshot_age")
            elif generated_age_seconds >= aging_after:
                state = "aging"
                reason_codes.append("snapshot_age")

        cluster_issue_rank = "fresh"
        for cluster in critical_clusters:
            if cluster.freshness == "missing":
                cluster_issue_rank = self._escalate_prediction_freshness(cluster_issue_rank, "stale")
                reason_codes.append(f"{cluster.cluster}_missing")
            elif cluster.freshness == "stale":
                cluster_issue_rank = self._escalate_prediction_freshness(cluster_issue_rank, "aging")
                reason_codes.append(f"{cluster.cluster}_stale")

        if not invalidated:
            state = self._escalate_prediction_freshness(state, cluster_issue_rank)

        if truth_state == "sparse_history":
            reason_codes.append("insufficient_history")
        elif truth_state == "legacy_sparse":
            reason_codes.append("legacy_sparse_attribution")

        return PredictionFreshnessSummary(
            state=state,
            summary=self._freshness_summary_copy(
                state=state,
                truth_state=truth_state,
                market_status=market_status,
                previous_market_session="previous_market_session" in reason_codes,
                generated_market_date=generated_market_date,
                market_date=market_date,
                critical_clusters=critical_clusters,
            ),
            invalidated=invalidated,
            generated_age_seconds=generated_age_seconds,
            evaluated_age_seconds=evaluated_age_seconds,
            market_status=market_status,
            market_date=market_date,
            refresh_after_seconds=self._freshness_refresh_after_seconds(
                state=state,
                invalidated=invalidated,
                market_status=market_status,
                generated_age_seconds=generated_age_seconds,
            ),
            checked_at=market_now,
            reason_codes=list(dict.fromkeys(reason_codes)),
            critical_clusters=critical_clusters,
        )

    def _build_freshness_clusters(
        self,
        source_snapshot: dict[str, Any],
    ) -> list[PredictionFreshnessCluster]:
        clusters = self._normalize_source_snapshot_clusters(
            source_snapshot.get("clusters") if isinstance(source_snapshot, dict) else {}
        )
        rows: list[PredictionFreshnessCluster] = []
        for cluster_name in CRITICAL_FRESHNESS_CLUSTERS:
            payload = clusters.get(cluster_name, {})
            rows.append(
                PredictionFreshnessCluster(
                    cluster=cluster_name,
                    freshness=self._normalize_source_freshness(payload.get("freshness")),
                    as_of_date=self._freshness_cluster_as_of_date(
                        cluster_name=cluster_name,
                        payload=payload,
                    ),
                    detail=self._freshness_cluster_detail(
                        cluster_name=cluster_name,
                        payload=payload,
                    ),
                )
            )
        return rows

    def _freshness_cluster_as_of_date(
        self,
        *,
        cluster_name: str,
        payload: dict[str, Any],
    ) -> str | None:
        if cluster_name == "market_regime":
            return self._normalize_iso_date(payload.get("latest_common_date"))
        if cluster_name == "options_positioning":
            return self._normalize_iso_date(payload.get("as_of_date"))
        return None

    def _freshness_cluster_detail(
        self,
        *,
        cluster_name: str,
        payload: dict[str, Any],
    ) -> str | None:
        if cluster_name == "macro_calendar":
            reason = self._optional_str(payload.get("reason"))
            if reason in {"stale_table", "staleTable"}:
                return "Macro calendar table stale."
            if reason in {"no_future_rows", "noFutureRows"}:
                return "No future macro rows tracked."
            return None
        if cluster_name == "market_regime":
            latest_common_date = self._normalize_iso_date(payload.get("latest_common_date"))
            return f"Latest closes through {latest_common_date}." if latest_common_date else None
        if cluster_name == "options_positioning":
            as_of_date = self._normalize_iso_date(payload.get("as_of_date"))
            return f"Options positioning through {as_of_date}." if as_of_date else None
        return None

    def _freshness_thresholds_for_market_status(self, market_status: str) -> tuple[int, int, int]:
        return SESSION_FRESHNESS_THRESHOLDS_SECONDS.get(
            market_status,
            SESSION_FRESHNESS_THRESHOLDS_SECONDS["closed"],
        )

    def _freshness_summary_copy(
        self,
        *,
        state: str,
        truth_state: str,
        market_status: str,
        previous_market_session: bool,
        generated_market_date: date,
        market_date: date,
        critical_clusters: list[PredictionFreshnessCluster],
    ) -> str:
        summary = "Snapshot aligned with current market session."
        if state == "degraded":
            summary = "Committee snapshot degraded. Auto-refreshing until a healthy run returns."
        elif truth_state == "waiting_after_close":
            summary = "Target date passed. Refresh after evaluation publishes."
        elif previous_market_session or generated_market_date < market_date:
            summary = "Snapshot predates current market session. Refresh required."
        elif any(cluster.freshness == "missing" for cluster in critical_clusters):
            summary = "Snapshot is running with missing evidence coverage."
        elif state == "invalid":
            summary = "Snapshot is outside its valid refresh window."
        elif state == "stale":
            summary = "Snapshot is stale for the current market session."
        elif state == "aging":
            summary = f"Snapshot still usable, but refresh due soon while market is {market_status.replace('_', ' ')}."
        return summary

    def _freshness_refresh_after_seconds(
        self,
        *,
        state: str,
        invalidated: bool,
        market_status: str,
        generated_age_seconds: int,
    ) -> int:
        if invalidated or state == "degraded":
            return 60 if market_status != "closed" else 300
        aging_after, stale_after, _invalid_after = self._freshness_thresholds_for_market_status(market_status)
        if state == "stale":
            return 300 if market_status != "closed" else 900
        if state == "aging":
            remaining = stale_after - generated_age_seconds
            return max(60, min(900, remaining if remaining > 0 else 300))
        remaining = aging_after - generated_age_seconds
        return max(300, min(3600, remaining if remaining > 0 else 900))

    def _escalate_prediction_freshness(self, current: str, incoming: str) -> str:
        return (
            incoming
            if PREDICTION_FRESHNESS_RANK[incoming] > PREDICTION_FRESHNESS_RANK[current]
            else current
        )

    def _normalize_iso_date(self, value: Any) -> str | None:
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, datetime):
            return value.date().isoformat()
        if not isinstance(value, str) or not value.strip():
            return None
        raw = value.strip()
        if len(raw) < 10:
            return None
        try:
            return date.fromisoformat(raw[:10]).isoformat()
        except ValueError:
            return None

    def _normalize_call_model(self, raw_call: Any) -> MarketPredictionCall | None:
        symbol = self._normalize_symbol(self._value(raw_call, "symbol"))
        if symbol not in PREDICTION_TARGET_SYMBOLS:
            return None
        top_source_clusters = self._normalize_clusters(self._value(raw_call, "top_source_clusters"))
        return MarketPredictionCall(
            id=self._optional_str(self._value(raw_call, "id")),
            symbol=symbol,
            window_days=self._int(self._value(raw_call, "window_days"), 1),
            direction_label=self._direction_from_raw(raw_call),
            prob_up=self._clamp(self._value(raw_call, "prob_up"), 0.5),
            expected_move_pct=self._float(self._value(raw_call, "expected_move_pct"), 0.0),
            confidence_band_low_pct=self._optional_float(self._value(raw_call, "confidence_band_low_pct")),
            confidence_band_high_pct=self._optional_float(self._value(raw_call, "confidence_band_high_pct")),
            confidence_score=self._normalize_confidence_score(
                self._value(raw_call, "confidence_score"),
                fallback=None,
            ),
            committee_disagreement_score=self._clamp(
                self._value(raw_call, "committee_disagreement_score"),
                0.0,
                low=0.0,
                high=1.0,
            ),
            rationale_summary=self._optional_str(self._value(raw_call, "rationale_summary")),
            top_source_clusters=top_source_clusters,
            metadata=self._dict_or_empty(self._value(raw_call, "metadata")),
        )

    def _normalize_vote_model(self, raw_vote: Any) -> CommitteeSeatVote | None:
        symbol = self._normalize_symbol(self._value(raw_vote, "symbol"))
        seat_key = self._normalize_seat_key(self._value(raw_vote, "seat_key"))
        if symbol not in PREDICTION_TARGET_SYMBOLS or seat_key is None:
            return None
        return CommitteeSeatVote(
            seat_key=seat_key,
            agent_slug=self._optional_str(self._value(raw_vote, "agent_slug")) or "investment-committee",
            model_id=self._optional_str(self._value(raw_vote, "model_id")),
            provider=self._optional_str(self._value(raw_vote, "provider")),
            symbol=symbol,
            window_days=self._int(self._value(raw_vote, "window_days"), 1),
            direction_label=self._direction_from_raw(raw_vote),
            prob_up=self._clamp(self._value(raw_vote, "prob_up"), 0.5),
            expected_move_pct=self._float(self._value(raw_vote, "expected_move_pct"), 0.0),
            confidence_score=self._normalize_confidence_score(
                self._value(raw_vote, "confidence_score"),
                fallback=None,
            ),
            rationale_summary=self._optional_str(self._value(raw_vote, "rationale_summary")),
            source_clusters=self._normalize_clusters(self._value(raw_vote, "source_clusters")),
            metadata=self._dict_or_empty(self._value(raw_vote, "metadata")),
        )

    def _normalize_votes_for_generation(
        self,
        raw_votes: Any,
        *,
        window_days: int,
        source_snapshot: dict[str, Any],
    ) -> list[CommitteeSeatVote]:
        if not isinstance(raw_votes, list):
            return []
        votes: list[CommitteeSeatVote] = []
        for raw in raw_votes:
            if not isinstance(raw, dict):
                continue
            seat_key = self._normalize_seat_key(raw.get("seat_key"))
            symbol = self._normalize_symbol(raw.get("symbol"))
            if seat_key is None or symbol not in PREDICTION_TARGET_SYMBOLS:
                continue
            clusters = self._normalize_clusters(raw.get("source_clusters"))
            if not clusters:
                clusters = self._fallback_vote_clusters(seat_key=seat_key, source_snapshot=source_snapshot)
            votes.append(
                CommitteeSeatVote(
                    seat_key=seat_key,
                    agent_slug=self._optional_str(raw.get("agent_slug")) or "investment-committee",
                    model_id=self._optional_str(raw.get("model_id")),
                    provider=self._optional_str(raw.get("provider")),
                    symbol=symbol,
                    window_days=self._int(raw.get("window_days"), window_days),
                    direction_label=self._direction_from_raw(raw),
                    prob_up=self._clamp(raw.get("prob_up"), 0.5),
                    expected_move_pct=self._float(raw.get("expected_move_pct"), 0.0),
                    confidence_score=self._normalize_confidence_score(raw.get("confidence_score"), fallback=50.0),
                    rationale_summary=self._optional_str(raw.get("rationale_summary")),
                    source_clusters=clusters,
                    metadata=self._dict_or_empty(raw.get("metadata")),
                )
            )
        return votes

    def _normalize_calls_for_generation(
        self,
        *,
        raw_calls: Any,
        raw_votes: Any,
        votes: list[CommitteeSeatVote],
        source_snapshot: dict[str, Any],
        window_days: int,
    ) -> list[MarketPredictionCall]:
        call_map: dict[str, MarketPredictionCall] = {}
        if isinstance(raw_calls, list):
            for raw in raw_calls:
                if not isinstance(raw, dict):
                    continue
                symbol = self._normalize_symbol(raw.get("symbol"))
                if symbol not in PREDICTION_TARGET_SYMBOLS:
                    continue
                symbol_votes = [vote for vote in votes if vote.symbol == symbol]
                clusters = self._normalize_clusters(raw.get("top_source_clusters"))
                if not clusters:
                    clusters = self._fallback_call_clusters(
                        raw_votes=raw_votes,
                        votes=symbol_votes,
                        source_snapshot=source_snapshot,
                    )
                call_map[symbol] = MarketPredictionCall(
                    symbol=symbol,
                    window_days=window_days,
                    direction_label=self._direction_from_raw(raw),
                    prob_up=self._clamp(raw.get("prob_up"), 0.5),
                    expected_move_pct=self._float(raw.get("expected_move_pct"), 0.0),
                    confidence_band_low_pct=self._optional_float(raw.get("confidence_band_low_pct")),
                    confidence_band_high_pct=self._optional_float(raw.get("confidence_band_high_pct")),
                    confidence_score=self._normalize_confidence_score(raw.get("confidence_score"), fallback=50.0),
                    committee_disagreement_score=self._clamp(
                        raw.get("committee_disagreement_score"),
                        self._estimate_disagreement(symbol, votes),
                        low=0.0,
                        high=1.0,
                    ),
                    rationale_summary=self._optional_str(raw.get("rationale_summary")),
                    top_source_clusters=clusters,
                    metadata=self._dict_or_empty(raw.get("metadata")),
                )

        if not call_map and votes:
            return self._aggregate_calls_from_votes(
                raw_votes=raw_votes,
                votes=votes,
                window_days=window_days,
                review=self._coerce_review(review=None, window_days=window_days, as_of_ts=datetime.now(UTC)),
                cluster_review=self._coerce_cluster_review(
                    review=None,
                    window_days=window_days,
                    as_of_ts=datetime.now(UTC),
                    source_snapshot=source_snapshot,
                ),
                source_snapshot=source_snapshot,
            )

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
                    top_source_clusters=self._fallback_call_clusters(
                        raw_votes=raw_votes,
                        votes=[vote for vote in votes if vote.symbol == symbol],
                        source_snapshot=source_snapshot,
                    ),
                )
            )
        return ordered_calls

    def _aggregate_calls_from_votes(
        self,
        *,
        raw_votes: Any,
        votes: list[CommitteeSeatVote],
        window_days: int,
        review: MarketPredictionSeatReview,
        cluster_review: MarketPredictionClusterReview,
        source_snapshot: dict[str, Any],
    ) -> list[MarketPredictionCall]:
        by_symbol: dict[str, list[CommitteeSeatVote]] = {}
        for vote in votes:
            by_symbol.setdefault(vote.symbol, []).append(vote)

        resolved_weight_map = self._review_weight_map(review)
        cluster_weight_rows = self._resolved_cluster_weight_rows(cluster_review)
        calls: list[MarketPredictionCall] = []
        for symbol in PREDICTION_TARGET_SYMBOLS:
            symbol_votes = by_symbol.get(symbol, [])
            deduped_votes = self._dedupe_supported_votes(symbol_votes)
            active_votes = [
                vote
                for vote in deduped_votes
                if vote.seat_key in resolved_weight_map
                and math.isfinite(float(vote.prob_up))
                and 0.0 <= float(vote.prob_up) <= 1.0
                and math.isfinite(float(vote.expected_move_pct))
            ]
            call_clusters = self._weighted_call_clusters(
                raw_votes=raw_votes,
                votes=active_votes if active_votes else symbol_votes,
                source_snapshot=source_snapshot,
                cluster_weight_rows=cluster_weight_rows,
            )
            active_cluster_keys = [cluster.cluster for cluster in call_clusters if cluster.weight is not None]
            if not active_votes:
                calls.append(
                    MarketPredictionCall(
                        symbol=symbol,
                        window_days=window_days,
                        direction_label="neutral",
                        prob_up=0.5,
                        expected_move_pct=0.0,
                        confidence_band_low_pct=0.0,
                        confidence_band_high_pct=0.0,
                        confidence_score=0.0,
                        committee_disagreement_score=0.0,
                        rationale_summary="Committee call unavailable; neutral fallback applied.",
                        top_source_clusters=call_clusters,
                        metadata={"aggregation_mode": "neutral_fallback", "active_seat_keys": [], "active_cluster_keys": active_cluster_keys},
                    )
                )
                continue
            if len(active_votes) == 1:
                vote = active_votes[0]
                calls.append(
                    MarketPredictionCall(
                        symbol=symbol,
                        window_days=window_days,
                        direction_label=vote.direction_label,
                        prob_up=vote.prob_up,
                        expected_move_pct=vote.expected_move_pct,
                        confidence_band_low_pct=vote.expected_move_pct,
                        confidence_band_high_pct=vote.expected_move_pct,
                        confidence_score=self._normalize_confidence_score(vote.confidence_score, fallback=50.0),
                        committee_disagreement_score=0.0,
                        rationale_summary="Consensus synthesized from a single supported seat vote.",
                        top_source_clusters=call_clusters,
                        metadata={"aggregation_mode": "single_seat", "active_seat_keys": [vote.seat_key], "active_cluster_keys": active_cluster_keys},
                    )
                )
                continue
            active_weight_map = self._normalize_active_weight_map(
                {vote.seat_key: resolved_weight_map[vote.seat_key] for vote in active_votes}
            )
            weighted_prob = self._weighted_logit_probability(active_votes=active_votes, active_weight_map=active_weight_map)
            weighted_move = self._weighted_vote_mean(
                active_votes=active_votes,
                active_weight_map=active_weight_map,
                accessor=lambda vote: vote.expected_move_pct,
            )
            weighted_conf = self._weighted_vote_mean(
                active_votes=active_votes,
                active_weight_map=active_weight_map,
                accessor=lambda vote: self._normalize_confidence_score(vote.confidence_score, fallback=50.0),
            )
            calls.append(
                MarketPredictionCall(
                    symbol=symbol,
                    window_days=window_days,
                    direction_label=self._derive_direction(weighted_prob, weighted_move),
                    prob_up=weighted_prob,
                    expected_move_pct=weighted_move,
                    confidence_band_low_pct=min(vote.expected_move_pct for vote in active_votes),
                    confidence_band_high_pct=max(vote.expected_move_pct for vote in active_votes),
                    confidence_score=weighted_conf,
                    committee_disagreement_score=self._estimate_disagreement(symbol, active_votes),
                    rationale_summary="Consensus synthesized from weighted seat-level committee votes.",
                    top_source_clusters=call_clusters,
                    metadata={
                        "aggregation_mode": "weighted_committee",
                        "active_seat_keys": sorted(active_weight_map),
                        "active_cluster_keys": active_cluster_keys,
                    },
                )
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

    def _extract_executed_seats(self, *, raw_votes: Any, committee_config: Any) -> list[dict[str, Any]]:
        vote_seats = self._extract_executed_seat_rows(raw_votes)
        if vote_seats:
            return vote_seats
        config_seats = committee_config.get("seats") if isinstance(committee_config, dict) else None
        return self._extract_executed_seat_rows(config_seats)

    def _extract_executed_seat_rows(self, raw_rows: Any) -> list[dict[str, Any]]:
        if not isinstance(raw_rows, list):
            return []
        seats: list[dict[str, Any]] = []
        seen: set[str] = set()
        for raw in raw_rows:
            seat = self._normalize_executed_seat_row(raw)
            if seat is None or seat["seat_key"] in seen:
                continue
            seen.add(seat["seat_key"])
            seats.append(seat)
        return sorted(seats, key=lambda seat: seat["seat_key"])

    def _normalize_executed_seat_row(self, raw: Any) -> dict[str, Any] | None:
        if not isinstance(raw, dict):
            return None
        seat_key = self._normalize_seat_key(raw.get("seat_key"))
        if seat_key is None:
            return None
        return {
            "seat_key": seat_key,
            "agent_slug": self._seat_optional_str(raw.get("agent_slug")),
            "model_id": self._seat_optional_str(raw.get("model_id")),
            "provider": self._seat_optional_str(raw.get("provider")),
        }

    def _build_run_metadata(
        self,
        *,
        existing: Any,
        executed_seats: list[dict[str, Any]],
        committee_execution_path: str,
        review: MarketPredictionSeatReview,
        cluster_review: MarketPredictionClusterReview,
    ) -> dict[str, Any]:
        metadata = self._normalize_metadata(existing)
        review_persisted = bool(review.metadata.get("_persisted", True)) if isinstance(review.metadata, dict) else True
        cluster_review_persisted = bool(cluster_review.metadata.get("_persisted", True)) if isinstance(cluster_review.metadata, dict) else True
        metadata.update(
            {
                "committee_roster_mode": self._classify_roster_mode(executed_seats),
                "committee_fingerprint": self._compute_committee_fingerprint(executed_seats),
                "committee_execution_path": committee_execution_path,
                "executed_seats": executed_seats,
                "adaptive_weighting_version": "seat-v1",
                "review_row_id": review.id if review_persisted else None,
                "review_generated_at": review.generated_at.isoformat(),
                "review_state": review.review_state,
                "resolved_seat_weights": [
                    row.model_dump()
                    for row in self._resolved_seat_weight_rows(
                        self._build_degraded_committee_review(review)
                        if not review_persisted and review.review_state == "degraded"
                        else review
                    )
                ],
                "adaptive_cluster_weighting_version": "cluster-v1",
                "cluster_review_row_id": cluster_review.id if cluster_review_persisted else None,
                "cluster_review_generated_at": cluster_review.generated_at.isoformat(),
                "cluster_review_state": cluster_review.review_state,
                "resolved_cluster_weights": self._resolved_cluster_weight_rows(cluster_review),
            }
        )
        return metadata

    def _normalize_metadata(self, raw_metadata: Any) -> dict[str, Any]:
        return dict(raw_metadata) if isinstance(raw_metadata, dict) else {}

    def _coerce_review(
        self,
        *,
        review: MarketPredictionSeatReview | dict[str, Any] | None,
        window_days: int,
        as_of_ts: datetime,
    ) -> MarketPredictionSeatReview:
        if isinstance(review, MarketPredictionSeatReview):
            return review
        if isinstance(review, dict):
            try:
                return MarketPredictionSeatReview(
                    id=str(review.get("id") or f"seat-review:{window_days}:{as_of_ts.isoformat()}"),
                    generated_at=self._coerce_datetime(review.get("generated_at") or as_of_ts),
                    as_of_ts=self._coerce_datetime(review.get("as_of_ts") or as_of_ts),
                    window_days=self._int(review.get("window_days"), window_days),
                    review_state=str(review.get("review_state") or "warmup"),
                    seat_scorecards=review.get("seat_scorecards") or [],
                    review_summary=review.get("review_summary") or {},
                    metadata=review.get("metadata") or {},
                )
            except Exception:
                logger.warning("market_prediction_review_coercion_failed", exc_info=True)
        prior = 1.0 / len(SUPPORTED_ADAPTIVE_SEAT_KEYS)
        return MarketPredictionSeatReview(
            id=f"seat-review:{window_days}:{as_of_ts.isoformat()}",
            generated_at=as_of_ts,
            as_of_ts=as_of_ts,
            window_days=window_days,
            review_state="warmup",
            seat_scorecards=[
                {
                    "seat_key": seat_key,
                    "prior_weight": prior,
                    "effective_weight": prior,
                    "sample_size": 0,
                    "direction_hit_rate": None,
                    "move_mae_pct": None,
                    "brier_score": None,
                    "skill_score": None,
                    "recommended_action": "hold",
                }
                for seat_key in SUPPORTED_ADAPTIVE_SEAT_KEYS
            ],
            review_summary={
                "generated_at": as_of_ts.isoformat(),
                "review_state": "warmup",
                "drift_callouts": [],
                "top_upweighted": [],
                "top_downweighted": [],
            },
            metadata={},
        )

    def _coerce_cluster_review(
        self,
        *,
        review: MarketPredictionClusterReview | dict[str, Any] | None,
        window_days: int,
        as_of_ts: datetime,
    ) -> MarketPredictionClusterReview:
        if isinstance(review, MarketPredictionClusterReview):
            return review
        if isinstance(review, dict):
            try:
                return MarketPredictionClusterReview(
                    id=str(review.get("id") or f"cluster-review:{window_days}:{as_of_ts.isoformat()}"),
                    generated_at=self._coerce_datetime(review.get("generated_at") or as_of_ts),
                    as_of_ts=self._coerce_datetime(review.get("as_of_ts") or as_of_ts),
                    window_days=self._int(review.get("window_days"), window_days),
                    review_state=str(review.get("review_state") or "warmup"),
                    cluster_scorecards=review.get("cluster_scorecards") or [],
                    review_summary=review.get("review_summary") or {},
                    metadata=review.get("metadata") or {},
                )
            except Exception:
                logger.warning("market_prediction_cluster_review_coercion_failed", exc_info=True)
        prior = 1.0 / len(SUPPORTED_ADAPTIVE_CLUSTER_KEYS)
        return MarketPredictionClusterReview(
            id=f"cluster-review:{window_days}:{as_of_ts.isoformat()}",
            generated_at=as_of_ts,
            as_of_ts=as_of_ts,
            window_days=window_days,
            review_state="warmup",
            cluster_scorecards=[
                {
                    "cluster": cluster,
                    "prior_weight": prior,
                    "effective_weight": prior,
                    "sample_size": 0,
                    "direction_hit_rate": None,
                    "move_mae_pct": None,
                    "brier_score": None,
                    "skill_score": None,
                    "freshness": "unknown",
                    "recommended_action": "hold",
                }
                for cluster in SUPPORTED_ADAPTIVE_CLUSTER_KEYS
            ],
            review_summary={
                "generated_at": as_of_ts.isoformat(),
                "review_state": "warmup",
                "drift_callouts": [],
                "top_upweighted": [],
                "top_downweighted": [],
            },
            metadata={
                "weighting_half_life_days": 20,
                "trailing_window_trading_days": 60,
                "freshness_factors": {"fresh": 1.0, "stale": 0.5, "missing": 0.0, "unknown": 0.25},
                "supported_windows": list(SUPPORTED_PREDICTION_WINDOWS),
            },
        )

    def _build_degraded_committee_review(self, review: MarketPredictionSeatReview) -> MarketPredictionSeatReview:
        prior = 1.0 / len(SUPPORTED_ADAPTIVE_SEAT_KEYS)
        return MarketPredictionSeatReview(
            id=review.id,
            generated_at=review.generated_at,
            as_of_ts=review.as_of_ts,
            window_days=review.window_days,
            review_state="degraded",
            seat_scorecards=[
                {
                    "seat_key": seat_key,
                    "prior_weight": prior,
                    "effective_weight": prior,
                    "sample_size": 0,
                    "direction_hit_rate": None,
                    "move_mae_pct": None,
                    "brier_score": None,
                    "skill_score": None,
                    "recommended_action": "hold",
                }
                for seat_key in SUPPORTED_ADAPTIVE_SEAT_KEYS
            ],
            review_summary={
                "generated_at": review.generated_at.isoformat(),
                "review_state": "degraded",
                "drift_callouts": [],
                "top_upweighted": [],
                "top_downweighted": [],
            },
            metadata={
                **(dict(review.metadata) if isinstance(review.metadata, dict) else {}),
                "_persisted": False,
            },
        )

    def _resolved_seat_weight_rows(
        self,
        review: MarketPredictionSeatReview,
    ) -> list[MarketPredictionResolvedSeatWeight]:
        rows: list[MarketPredictionResolvedSeatWeight] = []
        for seat_key in SUPPORTED_ADAPTIVE_SEAT_KEYS:
            raw_row = next(
                (
                    row
                    for row in review.seat_scorecards
                    if self._normalize_seat_key(self._value(row, "seat_key")) == seat_key
                ),
                None,
            )
            prior = self._clamp(self._value(raw_row, "prior_weight"), 1.0 / len(SUPPORTED_ADAPTIVE_SEAT_KEYS), low=0.0, high=1.0)
            effective = self._clamp(self._value(raw_row, "effective_weight"), prior, low=0.0, high=1.0)
            sample_size = self._int(self._value(raw_row, "sample_size"), 0)
            skill_score = self._optional_float(self._value(raw_row, "skill_score"))
            rows.append(
                MarketPredictionResolvedSeatWeight(
                    seat_key=seat_key,
                    prior_weight=prior,
                    effective_weight=effective,
                    sample_size=sample_size,
                    skill_score=skill_score,
                )
            )
        return rows

    def _coerce_cluster_review(
        self,
        *,
        review: MarketPredictionClusterReview | dict[str, Any] | None,
        window_days: int,
        as_of_ts: datetime,
        source_snapshot: dict[str, Any],
    ) -> MarketPredictionClusterReview:
        if isinstance(review, MarketPredictionClusterReview):
            return review
        if isinstance(review, dict):
            try:
                return MarketPredictionClusterReview(
                    id=str(review.get("id") or f"cluster-review:{window_days}:{as_of_ts.isoformat()}"),
                    generated_at=self._coerce_datetime(review.get("generated_at") or as_of_ts),
                    as_of_ts=self._coerce_datetime(review.get("as_of_ts") or as_of_ts),
                    window_days=self._int(review.get("window_days"), window_days),
                    review_state=str(review.get("review_state") or "warmup"),
                    cluster_scorecards=review.get("cluster_scorecards") or [],
                    review_summary=review.get("review_summary") or {},
                    metadata=review.get("metadata") or {},
                )
            except Exception:
                logger.warning("market_prediction_cluster_review_coercion_failed", exc_info=True)
        return self._build_prior_cluster_review(
            window_days=window_days,
            as_of_ts=as_of_ts,
            review_state="warmup",
            source_snapshot=source_snapshot,
        )

    def _build_prior_cluster_review(
        self,
        *,
        window_days: int,
        as_of_ts: datetime,
        review_state: str,
        source_snapshot: dict[str, Any],
    ) -> MarketPredictionClusterReview:
        prior = 1.0 / len(SUPPORTED_ADAPTIVE_CLUSTER_KEYS)
        return MarketPredictionClusterReview(
            id=f"cluster-review:{window_days}:{as_of_ts.isoformat()}",
            generated_at=as_of_ts,
            as_of_ts=as_of_ts,
            window_days=window_days,
            review_state=review_state,
            cluster_scorecards=[
                {
                    "cluster": cluster,
                    "prior_weight": prior,
                    "effective_weight": prior,
                    "sample_size": 0,
                    "direction_hit_rate": None,
                    "move_mae_pct": None,
                    "brier_score": None,
                    "skill_score": None,
                    "freshness": self._source_cluster_freshness(cluster, source_snapshot),
                    "recommended_action": "hold",
                }
                for cluster in SUPPORTED_ADAPTIVE_CLUSTER_KEYS
            ],
            review_summary={
                "generated_at": as_of_ts.isoformat(),
                "review_state": review_state,
                "drift_callouts": [],
                "top_upweighted": [],
                "top_downweighted": [],
            },
            metadata={},
        )

    def _build_degraded_cluster_review(self, review: MarketPredictionClusterReview) -> MarketPredictionClusterReview:
        prior = 1.0 / len(SUPPORTED_ADAPTIVE_CLUSTER_KEYS)
        return MarketPredictionClusterReview(
            id=review.id,
            generated_at=review.generated_at,
            as_of_ts=review.as_of_ts,
            window_days=review.window_days,
            review_state="degraded",
            cluster_scorecards=[
                {
                    "cluster": cluster,
                    "prior_weight": prior,
                    "effective_weight": prior,
                    "sample_size": 0,
                    "direction_hit_rate": None,
                    "move_mae_pct": None,
                    "brier_score": None,
                    "skill_score": None,
                    "freshness": self._cluster_row_freshness(review, cluster),
                    "recommended_action": "hold",
                }
                for cluster in SUPPORTED_ADAPTIVE_CLUSTER_KEYS
            ],
            review_summary={
                "generated_at": review.generated_at.isoformat(),
                "review_state": "degraded",
                "drift_callouts": [],
                "top_upweighted": [],
                "top_downweighted": [],
            },
            metadata={
                **(dict(review.metadata) if isinstance(review.metadata, dict) else {}),
                "_persisted": False,
            },
        )

    def _resolved_cluster_weight_rows(self, review: MarketPredictionClusterReview) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        prior = 1.0 / len(SUPPORTED_ADAPTIVE_CLUSTER_KEYS)
        for cluster in SUPPORTED_ADAPTIVE_CLUSTER_KEYS:
            raw_row = next(
                (
                    row
                    for row in review.cluster_scorecards
                    if normalize_market_prediction_cluster_key(self._value(row, "cluster")) == cluster
                ),
                None,
            )
            rows.append(
                {
                    "cluster": cluster,
                    "prior_weight": self._clamp(self._value(raw_row, "prior_weight"), prior, low=0.0, high=1.0),
                    "effective_weight": self._clamp(self._value(raw_row, "effective_weight"), prior, low=0.0, high=1.0),
                    "sample_size": self._int(self._value(raw_row, "sample_size"), 0),
                    "skill_score": self._optional_float(self._value(raw_row, "skill_score")),
                    "freshness": self._normalize_source_freshness(self._value(raw_row, "freshness")),
                }
            )
        return rows

    def _apply_cluster_review_to_source_snapshot(
        self,
        *,
        source_snapshot: dict[str, Any],
        cluster_review: MarketPredictionClusterReview,
    ) -> dict[str, Any]:
        snapshot = dict(source_snapshot) if isinstance(source_snapshot, dict) else {}
        clusters = self._normalize_source_snapshot_clusters(snapshot.get("clusters"))
        for row in self._resolved_cluster_weight_rows(cluster_review):
            cluster_payload = dict(clusters.get(row["cluster"], {}))
            cluster_payload.update(row)
            clusters[row["cluster"]] = cluster_payload
        snapshot["clusters"] = clusters
        return snapshot

    def _weighted_call_clusters(
        self,
        *,
        raw_votes: Any,
        votes: list[CommitteeSeatVote],
        source_snapshot: dict[str, Any],
        cluster_review: MarketPredictionClusterReview | None,
    ) -> list[PredictionSourceCluster]:
        active_keys = self._active_cluster_keys_for_call(
            raw_votes=raw_votes,
            votes=votes,
            source_snapshot=source_snapshot,
            cluster_review=cluster_review,
        )
        if not active_keys:
            return []
        weight_map = {
            row["cluster"]: row["effective_weight"]
            for row in self._resolved_cluster_weight_rows(cluster_review)
        } if cluster_review is not None else {}
        return [
            PredictionSourceCluster(
                cluster=cluster,
                weight=self._optional_float(weight_map.get(cluster)),
                freshness=self._source_cluster_freshness(cluster, source_snapshot),
                note=DEFAULT_ATTRIBUTION_NOTE,
            )
            for cluster in sorted(active_keys, key=lambda key: (-float(weight_map.get(key) or 0.0), key))
        ]

    def _active_cluster_keys_for_call(
        self,
        *,
        raw_votes: Any,
        votes: list[CommitteeSeatVote],
        source_snapshot: dict[str, Any],
        cluster_review: MarketPredictionClusterReview | None,
    ) -> list[str]:
        candidates: list[str] = []
        seen: set[str] = set()
        for vote in self._votes_in_raw_order(raw_votes=raw_votes, votes=votes):
            for cluster in vote.source_clusters:
                key = normalize_market_prediction_cluster_key(cluster.cluster)
                if key is None or key in seen:
                    continue
                seen.add(key)
                candidates.append(key)
        if not candidates:
            fallback = self._fallback_call_clusters(raw_votes=raw_votes, votes=votes, source_snapshot=source_snapshot)
            for cluster in fallback:
                key = normalize_market_prediction_cluster_key(cluster.cluster)
                if key is None or key in seen:
                    continue
                seen.add(key)
                candidates.append(key)
        if cluster_review is None:
            return sorted(candidates)
        weight_map = {row["cluster"]: row["effective_weight"] for row in self._resolved_cluster_weight_rows(cluster_review)}
        return sorted([key for key in candidates if float(weight_map.get(key) or 0.0) > 1e-9])

    def _cluster_row_freshness(self, review: MarketPredictionClusterReview, cluster: str) -> str:
        raw_row = next(
            (
                row
                for row in review.cluster_scorecards
                if normalize_market_prediction_cluster_key(self._value(row, "cluster")) == cluster
            ),
            None,
        )
        return self._normalize_source_freshness(self._value(raw_row, "freshness"))

    def _source_cluster_freshness(self, cluster: str, source_snapshot: dict[str, Any]) -> str:
        clusters = self._normalize_source_snapshot_clusters(source_snapshot.get("clusters") if isinstance(source_snapshot, dict) else {})
        return self._normalize_source_freshness(clusters.get(cluster, {}).get("freshness"))

    def _normalize_resolved_seat_weights(self, raw_rows: Any) -> list[dict[str, Any]]:
        if not isinstance(raw_rows, list):
            return []
        normalized: list[dict[str, Any]] = []
        for seat_key in SUPPORTED_ADAPTIVE_SEAT_KEYS:
            raw_row = next(
                (
                    row
                    for row in raw_rows
                    if self._normalize_seat_key(self._value(row, "seat_key")) == seat_key
                ),
                None,
            )
            if raw_row is None:
                continue
            normalized.append(
                {
                    "seat_key": seat_key,
                    "prior_weight": self._clamp(self._value(raw_row, "prior_weight"), 1.0 / len(SUPPORTED_ADAPTIVE_SEAT_KEYS), low=0.0, high=1.0),
                    "effective_weight": self._clamp(self._value(raw_row, "effective_weight"), 1.0 / len(SUPPORTED_ADAPTIVE_SEAT_KEYS), low=0.0, high=1.0),
                    "sample_size": self._int(self._value(raw_row, "sample_size"), 0),
                    "skill_score": self._optional_float(self._value(raw_row, "skill_score")),
                }
            )
        return normalized

    def _review_weight_map(self, review: MarketPredictionSeatReview) -> dict[str, float]:
        return {
            row.seat_key: row.effective_weight
            for row in self._resolved_seat_weight_rows(review)
            if row.seat_key in SUPPORTED_ADAPTIVE_SEAT_KEYS
        }

    def _dedupe_supported_votes(self, votes: list[CommitteeSeatVote]) -> list[CommitteeSeatVote]:
        deduped: list[CommitteeSeatVote] = []
        seen: set[str] = set()
        for vote in votes:
            if vote.seat_key in seen or vote.seat_key not in SUPPORTED_ADAPTIVE_SEAT_KEYS:
                continue
            seen.add(vote.seat_key)
            deduped.append(vote)
        return deduped

    def _normalize_active_weight_map(self, weight_map: dict[str, float]) -> dict[str, float]:
        total = sum(weight_map.values())
        if total <= 0:
            equal_weight = 1.0 / len(weight_map)
            return dict.fromkeys(sorted(weight_map), equal_weight)
        return {seat_key: weight_map[seat_key] / total for seat_key in sorted(weight_map)}

    def _weighted_logit_probability(
        self,
        *,
        active_votes: list[CommitteeSeatVote],
        active_weight_map: dict[str, float],
    ) -> float:
        logit_sum = 0.0
        for vote in active_votes:
            weight = active_weight_map[vote.seat_key]
            clamped_prob = self._clamp(vote.prob_up, 0.5, low=0.05, high=0.95)
            logit_sum += weight * math.log(clamped_prob / (1.0 - clamped_prob))
        return 1.0 / (1.0 + math.exp(-logit_sum))

    def _weighted_vote_mean(
        self,
        *,
        active_votes: list[CommitteeSeatVote],
        active_weight_map: dict[str, float],
        accessor: Callable[[CommitteeSeatVote], float],
    ) -> float:
        return sum(active_weight_map[vote.seat_key] * accessor(vote) for vote in active_votes)

    def _resolved_cluster_weight_rows(
        self,
        review: MarketPredictionClusterReview,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for cluster in SUPPORTED_ADAPTIVE_CLUSTER_KEYS:
            raw_row = next(
                (
                    row
                    for row in review.cluster_scorecards
                    if normalize_market_prediction_cluster_key(self._value(row, "cluster")) == cluster
                ),
                None,
            )
            rows.append(
                {
                    "cluster": cluster,
                    "prior_weight": self._clamp(self._value(raw_row, "prior_weight"), 1.0 / len(SUPPORTED_ADAPTIVE_CLUSTER_KEYS), low=0.0, high=1.0),
                    "effective_weight": self._clamp(self._value(raw_row, "effective_weight"), 1.0 / len(SUPPORTED_ADAPTIVE_CLUSTER_KEYS), low=0.0, high=1.0),
                    "sample_size": self._int(self._value(raw_row, "sample_size"), 0),
                    "skill_score": self._optional_float(self._value(raw_row, "skill_score")),
                    "freshness": self._normalize_source_freshness(self._value(raw_row, "freshness")),
                }
            )
        return rows

    def _cluster_weight_map(self, review: MarketPredictionClusterReview) -> dict[str, dict[str, Any]]:
        return {row["cluster"]: row for row in self._resolved_cluster_weight_rows(review)}

    def _weighted_call_clusters(
        self,
        *,
        raw_votes: Any,
        votes: list[CommitteeSeatVote],
        source_snapshot: dict[str, Any],
        cluster_weight_rows: list[dict[str, Any]],
    ) -> list[PredictionSourceCluster]:
        fallback_clusters = self._fallback_call_clusters(
            raw_votes=raw_votes,
            votes=votes,
            source_snapshot=source_snapshot,
        )
        indexed = {row["cluster"]: row for row in cluster_weight_rows}
        weighted: list[PredictionSourceCluster] = []
        seen: set[str] = set()
        for cluster in fallback_clusters:
            normalized = normalize_market_prediction_cluster_key(cluster.cluster)
            if normalized not in indexed or normalized in seen:
                continue
            seen.add(normalized)
            if not self._cluster_is_weightable_for_attribution(cluster):
                continue
            row = indexed[normalized]
            effective = row.get("effective_weight")
            if effective is None or float(effective) <= 1e-9:
                continue
            weighted.append(
                PredictionSourceCluster(
                    cluster=normalized,
                    weight=float(effective),
                    freshness=row.get("freshness"),
                    note=cluster.note,
                )
            )
        if weighted:
            weighted.sort(key=lambda item: (-float(item.weight or 0.0), item.cluster))
            return weighted[:3]
        return fallback_clusters

    def _apply_cluster_review_to_source_snapshot(
        self,
        source_snapshot: dict[str, Any],
        cluster_review: MarketPredictionClusterReview,
    ) -> dict[str, Any]:
        snapshot = dict(source_snapshot) if isinstance(source_snapshot, dict) else {}
        raw_clusters = snapshot.get("clusters") if isinstance(snapshot.get("clusters"), dict) else {}
        normalized_clusters = dict(raw_clusters)
        for row in self._resolved_cluster_weight_rows(cluster_review):
            cluster = row["cluster"]
            payload = normalized_clusters.get(cluster)
            if not isinstance(payload, dict):
                continue
            normalized_clusters[cluster] = {
                **payload,
                "prior_weight": row["prior_weight"],
                "effective_weight": row["effective_weight"] if row["effective_weight"] > 1e-9 else None,
                "sample_size": row["sample_size"] if row["sample_size"] > 0 else None,
                "skill_score": row["skill_score"],
            }
        snapshot["clusters"] = normalized_clusters
        return snapshot

    def _normalize_executed_seats(self, raw_executed_seats: Any) -> list[dict[str, Any]]:
        if not isinstance(raw_executed_seats, list):
            return []
        seats: list[dict[str, Any]] = []
        seen: set[str] = set()
        for raw in raw_executed_seats:
            seat = self._normalize_executed_seat_row(raw)
            if seat is None or seat["seat_key"] in seen:
                continue
            seen.add(seat["seat_key"])
            seats.append(seat)
        return sorted(seats, key=lambda seat: seat["seat_key"])

    def _classify_roster_mode(self, executed_seats: list[dict[str, Any]]) -> str:
        canonical = [
            {
                "seat_key": seat["seat_key"],
                "agent_slug": seat.get("agent_slug"),
                "model_id": seat.get("model_id"),
            }
            for seat in sorted(executed_seats, key=lambda item: item["seat_key"])
        ]
        return "default_roster" if canonical == DEFAULT_ROSTER else "custom_roster"

    def _compute_committee_fingerprint(self, executed_seats: list[dict[str, Any]]) -> str:
        payload = json.dumps(
            sorted(executed_seats, key=lambda seat: seat["seat_key"]),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _normalize_roster_mode(self, value: Any) -> str | None:
        normalized = self._optional_str(value)
        if normalized in {"default_roster", "custom_roster"}:
            return normalized
        return None

    def _normalize_execution_path(self, value: Any) -> str:
        return "committee_endpoint" if value == "committee_endpoint" else "fallback_completion"

    def _normalize_clusters(self, raw_clusters: Any) -> list[PredictionSourceCluster]:
        if not isinstance(raw_clusters, list):
            return []
        clusters: list[PredictionSourceCluster] = []
        for raw in raw_clusters:
            cluster = self._optional_str(self._value(raw, "cluster"))
            if not cluster:
                continue
            clusters.append(
                PredictionSourceCluster(
                    cluster=cluster,
                    weight=self._optional_float(self._value(raw, "weight")),
                    freshness=self._normalize_attribution_freshness(self._value(raw, "freshness")),
                    note=self._optional_str(self._value(raw, "note")),
                )
            )
        return clusters

    def _fallback_vote_clusters(
        self,
        *,
        seat_key: str,
        source_snapshot: dict[str, Any],
    ) -> list[PredictionSourceCluster]:
        snapshot_clusters = self._ordered_snapshot_clusters(source_snapshot)
        for preferred in SEAT_CLUSTER_PREFERENCES.get(seat_key, []):
            match = next((cluster for cluster in snapshot_clusters if cluster["cluster"] == preferred), None)
            if match is not None:
                return [self._build_fallback_cluster(match)]
        if snapshot_clusters:
            return [self._build_fallback_cluster(snapshot_clusters[0])]
        return [
            PredictionSourceCluster(
                cluster="unattributed",
                weight=None,
                freshness="unknown",
                note=DEFAULT_UNATTRIBUTED_NOTE,
            )
        ]

    def _fallback_call_clusters(
        self,
        *,
        raw_votes: Any,
        votes: list[CommitteeSeatVote],
        source_snapshot: dict[str, Any],
    ) -> list[PredictionSourceCluster]:
        vote_clusters: list[PredictionSourceCluster] = []
        seen: set[str] = set()
        for vote in self._votes_in_raw_order(raw_votes=raw_votes, votes=votes):
            for cluster in vote.source_clusters:
                if cluster.cluster in seen:
                    continue
                seen.add(cluster.cluster)
                vote_clusters.append(
                    PredictionSourceCluster(
                        cluster=cluster.cluster,
                        weight=None,
                        freshness=cluster.freshness or "unknown",
                        note=cluster.note,
                    )
                )
                if len(vote_clusters) == 3:
                    return vote_clusters
        if vote_clusters:
            return vote_clusters
        snapshot_clusters = self._ordered_snapshot_clusters(source_snapshot)
        if snapshot_clusters:
            return [self._build_fallback_cluster(cluster) for cluster in snapshot_clusters[:3]]
        return [
            PredictionSourceCluster(
                cluster="unattributed",
                weight=None,
                freshness="unknown",
                note=DEFAULT_UNATTRIBUTED_NOTE,
            )
        ]

    def _ordered_snapshot_clusters(self, source_snapshot: dict[str, Any]) -> list[dict[str, str]]:
        raw_clusters = self._normalize_source_snapshot_clusters(
            source_snapshot.get("clusters") if isinstance(source_snapshot, dict) else {}
        )
        usable = []
        for cluster_name, cluster_payload in raw_clusters.items():
            usable.append(
                {
                    "cluster": cluster_name,
                    "freshness": self._normalize_source_freshness(cluster_payload.get("freshness")),
                }
            )
        usable.sort(
            key=lambda item: (
                FRESHNESS_RANK[item["freshness"]],
                item["cluster"].lower(),
                item["cluster"],
            )
        )
        return usable

    def _build_fallback_cluster(self, cluster: dict[str, str]) -> PredictionSourceCluster:
        return PredictionSourceCluster(
            cluster=cluster["cluster"],
            weight=None,
            freshness=cluster["freshness"],
            note=DEFAULT_ATTRIBUTION_NOTE,
        )

    def _cluster_is_weightable_for_attribution(self, cluster: PredictionSourceCluster) -> bool:
        normalized = normalize_market_prediction_cluster_key(cluster.cluster)
        if normalized is None:
            return False
        if cluster.note in {DEFAULT_ATTRIBUTION_NOTE, DEFAULT_UNATTRIBUTED_NOTE}:
            return False
        freshness = self._normalize_source_freshness(cluster.freshness)
        return not (normalized == "macro_calendar" and freshness in {"stale", "missing"})

    def _votes_in_raw_order(self, *, raw_votes: Any, votes: list[CommitteeSeatVote]) -> list[CommitteeSeatVote]:
        if not isinstance(raw_votes, list):
            return votes
        indexed_votes: dict[tuple[str, str], CommitteeSeatVote] = {
            (vote.seat_key, vote.symbol): vote for vote in votes
        }
        ordered: list[CommitteeSeatVote] = []
        seen: set[tuple[str, str]] = set()
        for raw in raw_votes:
            if not isinstance(raw, dict):
                continue
            key = (
                self._normalize_seat_key(raw.get("seat_key")) or "",
                self._normalize_symbol(raw.get("symbol")),
            )
            if key in seen:
                continue
            vote = indexed_votes.get(key)
            if vote is None:
                continue
            seen.add(key)
            ordered.append(vote)
        for vote in votes:
            key = (vote.seat_key, vote.symbol)
            if key not in seen:
                ordered.append(vote)
        return ordered

    def _select_public_lead_call(
        self,
        *,
        raw_lead_call: Any,
        calls: list[MarketPredictionCall],
        window_days: int,
    ) -> tuple[MarketPredictionCall, bool]:
        normalized_lead = self._normalize_call_model(raw_lead_call)
        spy_call = next(
            (
                call
                for call in calls
                if self._normalize_symbol(call.symbol) == "SPY"
                and call.top_source_clusters
            ),
            None,
        )
        first_with_clusters = next(
            (call for call in calls if call.top_source_clusters),
            None,
        )

        candidate = normalized_lead if normalized_lead and normalized_lead.top_source_clusters else None
        if candidate is None:
            candidate = spy_call or first_with_clusters
        if candidate is not None:
            return candidate, False

        fallback = normalized_lead
        if fallback is None:
            fallback = next(
                (call for call in calls if self._normalize_symbol(call.symbol) == "SPY"),
                None,
            )
        if fallback is None and calls:
            fallback = calls[0]
        if fallback is None:
            fallback = self._neutral_call(window_days=window_days)
        return fallback, True

    def _normalize_scorecard(self, raw_scorecard: Any) -> MarketPredictionScorecard | None:
        payload = raw_scorecard.model_dump() if isinstance(raw_scorecard, MarketPredictionScorecard) else raw_scorecard
        if not isinstance(payload, dict):
            return None
        sample_size = payload.get("sample_size")
        if isinstance(sample_size, bool) or not isinstance(sample_size, int) or sample_size < 0:
            return None
        metrics: dict[str, float | None] = {}
        for key in ("direction_hit_rate", "move_mae_pct", "brier_score"):
            value = payload.get(key)
            if value is None:
                metrics[key] = None
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return None
            numeric = float(value)
            if not math.isfinite(numeric):
                return None
            metrics[key] = numeric
        return MarketPredictionScorecard(sample_size=sample_size, **metrics)

    def _determine_truth_state(
        self,
        *,
        lead_call: MarketPredictionCall,
        window_days: int,
        target_date: date,
        market_date: date,
        scorecard: MarketPredictionScorecard | None,
        legacy_sparse: bool,
    ) -> str:
        if legacy_sparse:
            return "legacy_sparse"
        if scorecard is None or scorecard.sample_size == 0:
            return "waiting_after_close" if target_date <= market_date else "pending_target"
        if self._history_is_sparse(symbol=lead_call.symbol, window_days=window_days):
            return "sparse_history"
        return "live"

    def _history_is_sparse(self, *, symbol: str, window_days: int) -> bool:
        try:
            history = self.repository.list_history(symbol=symbol, window_days=window_days, limit=30)
        except Exception:
            logger.warning("market_prediction_history_lookup_failed", symbol=symbol, window_days=window_days, exc_info=True)
            return False
        usable_points = 0
        for call in history:
            value = self._value(call, "expected_move_pct")
            if isinstance(value, bool):
                continue
            if not isinstance(value, (int, float)):
                continue
            if not math.isfinite(float(value)):
                continue
            usable_points += 1
            if usable_points >= 2:
                return False
        return True

    def _scorecard_status_note(self, truth_state: str) -> str | None:
        if truth_state == "live":
            return None
        if truth_state == "pending_target":
            return DEFAULT_PENDING_TARGET_NOTE
        if truth_state == "waiting_after_close":
            return DEFAULT_WAITING_AFTER_CLOSE_NOTE
        if truth_state == "sparse_history":
            return DEFAULT_SPARSE_HISTORY_NOTE
        if truth_state == "legacy_sparse":
            return DEFAULT_LEGACY_SPARSE_NOTE
        return DEFAULT_FETCH_ERROR_NOTE

    def _build_degraded_response(
        self,
        *,
        window_days: int,
        as_of_ts: datetime,
    ) -> MarketPredictionCommitteeResponse:
        base_date, target_date = self._compute_dates(window_days=window_days, as_of_ts=as_of_ts)
        market_date = get_expected_data_date(as_of_ts.astimezone(NY_TZ))
        try:
            macro_calendar = get_macro_calendar_cluster(market_date=market_date, storage=self.storage)
        except Exception:
            logger.warning("market_prediction_degraded_macro_calendar_failed", exc_info=True)
            macro_calendar = build_default_macro_calendar_cluster()
        lead_call = self._neutral_call(window_days=window_days)
        return MarketPredictionCommitteeResponse(
            as_of_ts=as_of_ts,
            generated_at=as_of_ts,
            window_days=window_days,
            base_date=base_date,
            target_date=target_date,
            target_universe=PREDICTION_TARGET_SYMBOLS,
            lead_call=lead_call,
            calls=[lead_call],
            votes=[],
            scorecard=None,
            committee_summary={
                "committee_roster_mode": None,
                "committee_execution_path": "fallback_completion",
                "executed_seat_keys": [],
                "truth_state": "fetch_error",
                "scorecard_status_note": DEFAULT_FETCH_ERROR_NOTE,
            },
            source_snapshot={
                "as_of_ts": as_of_ts.isoformat(),
                "target_universe": PREDICTION_TARGET_SYMBOLS,
                "clusters": {"macro_calendar": macro_calendar},
            },
            last_evaluated_at=None,
        )

    def _neutral_call(self, *, window_days: int) -> MarketPredictionCall:
        return MarketPredictionCall(
            symbol="SPY",
            window_days=window_days,
            direction_label="neutral",
            prob_up=0.5,
            expected_move_pct=0.0,
            confidence_score=0.0,
            top_source_clusters=[],
        )

    def _estimate_disagreement(self, symbol: str, votes: list[CommitteeSeatVote]) -> float:
        symbol_votes = [vote for vote in votes if vote.symbol == symbol]
        if len(symbol_votes) < 2:
            return 0.0
        probs = [vote.prob_up for vote in symbol_votes]
        return min(1.0, max(probs) - min(probs))

    def _normalize_confidence_score(
        self,
        value: Any,
        *,
        fallback: float | None,
    ) -> float | None:
        if value is None and fallback is None:
            return None
        normalized = self._clamp(
            value,
            0.0 if fallback is None else fallback,
            low=0.0,
            high=100.0,
        )
        if 0.0 < normalized <= 1.0:
            normalized *= 100.0
        return round(normalized, 4)

    def _direction_from_raw(self, raw: Any) -> PredictionDirection:
        explicit = self._optional_str(self._value(raw, "direction_label"))
        if explicit in {"bullish", "neutral", "bearish"}:
            return cast(PredictionDirection, explicit)
        return self._derive_direction(
            self._clamp(self._value(raw, "prob_up"), 0.5),
            self._float(self._value(raw, "expected_move_pct"), 0.0),
        )

    def _derive_direction(self, prob_up: float, expected_move_pct: float) -> PredictionDirection:
        if prob_up >= 0.55 and expected_move_pct > 0:
            return "bullish"
        if prob_up <= 0.45 and expected_move_pct < 0:
            return "bearish"
        return "neutral"

    def _normalize_target_universe(self, raw_universe: Any) -> list[str]:
        if not isinstance(raw_universe, list):
            return PREDICTION_TARGET_SYMBOLS
        normalized = [self._normalize_symbol(item) for item in raw_universe]
        usable = [symbol for symbol in normalized if symbol in PREDICTION_TARGET_SYMBOLS]
        return usable or PREDICTION_TARGET_SYMBOLS

    def _normalize_seat_key(self, value: Any) -> str | None:
        return normalize_market_prediction_seat_key(value)

    def _normalize_symbol(self, value: Any) -> str:
        return str(value or "").strip().upper()

    def _normalize_attribution_freshness(self, value: Any) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip().lower()
        if not normalized:
            return None
        return normalized if normalized in ALLOWED_CLUSTER_FRESHNESS else "unknown"

    def _normalize_source_freshness(self, value: Any) -> str:
        if value is None:
            return "unknown"
        normalized = str(value).strip().lower()
        if not normalized:
            return "unknown"
        return normalized if normalized in ALLOWED_CLUSTER_FRESHNESS else "unknown"

    @staticmethod
    def _value(source: Any, key: str) -> Any:
        if isinstance(source, dict):
            return source.get(key)
        return getattr(source, key, None)

    @staticmethod
    def _dict_or_empty(value: Any) -> dict[str, Any]:
        return dict(value) if isinstance(value, dict) else {}

    @staticmethod
    def _coerce_datetime(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value

    @staticmethod
    def _clamp(value: Any, fallback: float, *, low: float = 0.0, high: float = 1.0) -> float:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            numeric = fallback
        if not math.isfinite(numeric):
            numeric = fallback
        return max(low, min(high, numeric))

    @staticmethod
    def _float(value: Any, fallback: float) -> float:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return fallback
        return numeric if math.isfinite(numeric) else fallback

    @staticmethod
    def _int(value: Any, fallback: int) -> int:
        try:
            numeric = int(value)
        except (TypeError, ValueError):
            return fallback
        return numeric

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        try:
            numeric = None if value is None else float(value)
        except (TypeError, ValueError):
            return None
        if numeric is None or not math.isfinite(numeric):
            return None
        return numeric

    @staticmethod
    def _optional_str(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _seat_optional_str(value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        text = value.strip()
        return text or None
