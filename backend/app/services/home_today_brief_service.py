"""Build the Today market brief for the home dashboard."""

from __future__ import annotations

import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from hashlib import sha1
from importlib import import_module
from math import isfinite
from threading import Lock, Thread
from typing import Any

from app.agents.clients.agent_hub_client import AgentHubAPIClient
from app.api.market._core_helpers import build_intelligence_response_data, fetch_core_market_data
from app.api.market._response_builders import (
    build_fear_greed_response,
    build_market_health_response,
    build_sector_rotation_response,
)
from app.api.news_responses import serialize_article
from app.logging_config import get_logger
from app.market.intraday_mood import (
    calculate_intraday_mood_score,
    label_intraday_mood,
    tone_intraday_mood,
)
from app.portfolio.fund_lookthrough import ExposureItem, build_exposure_breakdown
from app.services._jenny_response_cleanup import extract_json_object_text
from app.services.household_finance_service import HouseholdFinanceService
from app.services.market_events_service import get_upcoming_events
from app.services.market_pulse_research_service import MarketPulseResearchService
from app.storage import get_storage
from app.utils.market_hours import NY_TZ, get_market_status

logger = get_logger(__name__)
_NARRATIVE_CACHE_SECONDS = 60 * 60
_RESPONSE_CACHE_SECONDS = 60
_MARKET_PULSE_AGENT_SLUG = "market-pulse-analyst"
_NARRATIVE_REQUEST_KIND = "today_market_pulse_narrative"

_SOURCE_SIGNAL_RANK = {
    "primary": 3,
    "secondary": 2,
    "commentary": 1,
    "unknown": 0,
}
_OFFICIAL_SOURCE_STACK = [
    {
        "id": "official_fed",
        "kind": "macro_data",
        "label": "Federal Reserve",
        "url": "https://www.federalreserve.gov/monetarypolicy.htm",
        "published_at": None,
        "source_signal_tier": "primary",
        "decision_value_score": 1.0,
    },
    {
        "id": "official_bls",
        "kind": "macro_data",
        "label": "BLS CPI and jobs releases",
        "url": "https://www.bls.gov/schedule/news_release/cpi.htm",
        "published_at": None,
        "source_signal_tier": "primary",
        "decision_value_score": 1.0,
    },
    {
        "id": "official_bea",
        "kind": "macro_data",
        "label": "BEA income and spending releases",
        "url": "https://www.bea.gov/news/schedule",
        "published_at": None,
        "source_signal_tier": "primary",
        "decision_value_score": 0.9,
    },
    {
        "id": "official_treasury",
        "kind": "market_data",
        "label": "U.S. Treasury yield curve",
        "url": "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/textview",
        "published_at": None,
        "source_signal_tier": "primary",
        "decision_value_score": 0.9,
    },
    {
        "id": "official_eia",
        "kind": "macro_data",
        "label": "EIA oil and energy data",
        "url": "https://www.eia.gov/petroleum/",
        "published_at": None,
        "source_signal_tier": "primary",
        "decision_value_score": 0.8,
    },
    {
        "id": "market_google_finance",
        "kind": "market_news",
        "label": "Google Finance market trends",
        "url": "https://www.google.com/finance/",
        "published_at": None,
        "source_signal_tier": "secondary",
        "decision_value_score": 0.5,
    },
]
_TODAY_BRIEF_CONTRACT = {
    "brief": {
        "headline": "string",
        "summary": "string",
        "stance": "constructive|neutral|cautious",
        "confidence": "high|medium|low",
        "why_now": "string",
        "bullets": ["string"],
    },
    "catalysts": [
        {
            "id": "string",
            "title": "string",
            "direction": "positive|negative|mixed|watch",
            "market_effect": "string",
            "portfolio_effect": "string",
            "money_effect": "string",
            "source_ids": ["string"],
        }
    ],
    "impacts": [
        {
            "label": "string",
            "direction": "tailwind|headwind|mixed",
            "magnitude": "high|medium|low",
            "rationale": "string",
            "affected_symbols": ["string"],
            "source_ids": ["string"],
        }
    ],
}


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _json_block(payload: Any) -> str:
    return json.dumps(payload, indent=2, default=_json_default)


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _trim_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _optional_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if isfinite(parsed) else None


def _indicator_payload(indicators: dict[str, Any], key: str) -> dict[str, Any]:
    value = indicators.get(key)
    return value if isinstance(value, dict) else {}


def _metric_value(value: Any, *, precision: int, suffix: str = "", grouped: bool = False) -> str:
    number = _optional_float(value)
    if number is None:
        return "Unavailable"
    format_spec = f",.{precision}f" if grouped else f".{precision}f"
    return f"{number:{format_spec}}{suffix}"


def _parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _format_et_timestamp(value: Any) -> str | None:
    parsed = _parse_timestamp(value)
    if parsed is None:
        return None
    local = parsed.astimezone(NY_TZ)
    hour = local.strftime("%I").lstrip("0") or "0"
    return f"As of {local.strftime('%b')} {local.day}, {hour}:{local.strftime('%M')} {local.strftime('%p')} ET"


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _sort_article(article: dict[str, Any]) -> tuple[float, int, str]:
    return (
        _safe_float(article.get("decision_value_score")),
        _SOURCE_SIGNAL_RANK.get(str(article.get("source_signal_tier") or "unknown"), 0),
        str(article.get("published_at") or ""),
    )


def _normalize_direction(value: Any, *, allowed: set[str], fallback: str) -> str:
    candidate = _trim_text(value).lower().replace(" ", "_")
    return candidate if candidate in allowed else fallback


def _merge_sources(*source_lists: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_urls: set[str] = set()
    for source_list in source_lists:
        for source in source_list:
            source_id = _trim_text(source.get("id"))
            url = _trim_text(source.get("url"))
            dedupe_key = source_id or url
            if not dedupe_key:
                continue
            if source_id and source_id in seen_ids:
                continue
            if url and url in seen_urls:
                continue
            if source_id:
                seen_ids.add(source_id)
            if url:
                seen_urls.add(url)
            merged.append(source)
    return merged


def _market_event_importance(impact_score: Any) -> str:
    score = abs(_safe_float(impact_score))
    if score >= 4:
        return "high"
    if score >= 2:
        return "medium"
    return "scheduled"


def _upcoming_event_payloads(events: list[Any]) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for event in events[:5]:
        impact_score = getattr(event, "impact_score", None)
        payloads.append(
            {
                "label": _trim_text(getattr(event, "title", "")) or str(getattr(event, "event_type", "")),
                "event_type": str(getattr(event, "event_type", "")),
                "event_date": _iso(getattr(event, "event_date", None)),
                "importance": _market_event_importance(impact_score),
                "impact_score": impact_score,
            }
        )
    return payloads


class HomeTodayBriefService:
    """Build a market- and portfolio-aware brief for the Today page."""

    def __init__(self) -> None:
        self.storage = get_storage()
        self.household_service = HouseholdFinanceService()
        self.research_service = MarketPulseResearchService()
        self._narrative_lock = Lock()
        self._narrative_cache: dict[str, Any] | None = None
        self._narrative_cache_key: str | None = None
        self._narrative_cached_at: datetime | None = None
        self._refresh_in_flight = False
        self._response_cache: dict[str, Any] | None = None
        self._response_cached_at: datetime | None = None

    def _news_service(self) -> Any:
        return import_module("app.api.news").news_service()

    def _portfolio_payload(self) -> Any:
        return import_module("app.api.portfolio")._get_portfolio_payload(False)

    def _market_snapshot(self) -> tuple[dict[str, Any], str, str | None]:
        market_data = fetch_core_market_data()
        current_timestamp = market_data.current_timestamp
        built = build_intelligence_response_data(market_data, current_timestamp)
        now = datetime.now(NY_TZ)
        snapshot = {
            "status": get_market_status(now),
            "market_health": build_market_health_response(
                built["health_score_data"]
            ).model_dump(mode="json"),
            "fear_greed": build_fear_greed_response(built["fg_reading"]).model_dump(
                mode="json"
            ),
            "indicators": {
                key: value.model_dump(mode="json")
                for key, value in built["enriched_indicators"].items()
            },
            "sector_rotation": build_sector_rotation_response(
                built["leading_sectors"],
                built["neutral_sectors"],
                built["lagging_sectors"],
            ).model_dump(mode="json"),
            "last_updated": _iso(current_timestamp),
        }
        return snapshot, snapshot["status"], _iso(current_timestamp)

    def _market_metrics(self, market: dict[str, Any]) -> list[dict[str, Any]]:
        indicators = market.get("indicators", {})
        if not isinstance(indicators, dict):
            indicators = {}
        sp500 = _indicator_payload(indicators, "sp500")
        vix = _indicator_payload(indicators, "vix")
        tnx = _indicator_payload(indicators, "tnx")
        sector_rotation = market.get("sector_rotation", {})
        if not isinstance(sector_rotation, dict):
            sector_rotation = {}
        leading = sector_rotation.get("leading", [])[:3]
        leadership = ", ".join(str(row.get("name") or "") for row in leading if row.get("name"))
        market_as_of = market.get("last_updated")
        sp500_as_of = sp500.get("last_updated") or market_as_of
        vix_as_of = vix.get("last_updated") or market_as_of
        tnx_as_of = tnx.get("last_updated") or market_as_of
        leadership_as_of = leading[0].get("last_updated") if leading else market_as_of
        sp500_change = _optional_float(sp500.get("change_pct"))
        vix_value = _optional_float(vix.get("value"))
        tnx_value = _optional_float(tnx.get("value"))
        mood_score = calculate_intraday_mood_score(
            indicators,
            [
                *(_as_list(sector_rotation.get("leading"))),
                *(_as_list(sector_rotation.get("neutral"))),
                *(_as_list(sector_rotation.get("lagging"))),
            ],
        )
        return [
            {
                "key": "sp500",
                "label": "S&P 500",
                "value": _metric_value(sp500.get("value"), precision=2, grouped=True),
                "change_pct": sp500.get("change_pct"),
                "detail": "Broad market benchmark",
                "horizon": "Current quote · 1D vs prior close",
                "as_of": sp500_as_of,
                "as_of_label": _format_et_timestamp(sp500_as_of),
                "tone": "neutral"
                if sp500_change is None
                else "positive"
                if sp500_change > 0
                else "negative",
            },
            {
                "key": "vix",
                "label": "VIX",
                "value": _metric_value(vix.get("value"), precision=2),
                "change_pct": vix.get("change_pct"),
                "detail": "Risk pricing",
                "horizon": "Current quote · 1D vs prior close",
                "as_of": vix_as_of,
                "as_of_label": _format_et_timestamp(vix_as_of),
                "tone": "neutral"
                if vix_value is None
                else "positive"
                if vix_value < 20
                else "warning",
            },
            {
                "key": "tnx",
                "label": "10Y Yield",
                "value": _metric_value(tnx.get("value"), precision=3, suffix="%"),
                "change_pct": tnx.get("change_pct"),
                "detail": "Rate pressure",
                "horizon": "Current quote · 1D vs prior close",
                "as_of": tnx_as_of,
                "as_of_label": _format_et_timestamp(tnx_as_of),
                "tone": "warning" if tnx_value is not None and tnx_value >= 4.5 else "neutral",
            },
            {
                "key": "intraday_mood",
                "label": "Intraday Mood",
                "value": str(mood_score),
                "change_pct": None,
                "detail": label_intraday_mood(mood_score),
                "horizon": "Live proxy · Quote inputs",
                "as_of": market_as_of,
                "as_of_label": _format_et_timestamp(market_as_of),
                "tone": tone_intraday_mood(mood_score),
            },
            {
                "key": "leadership",
                "label": "Leadership",
                "value": leadership or "Mixed",
                "change_pct": leading[0].get("change_pct") if leading else None,
                "detail": "Sectors leading today",
                "horizon": "Current quotes · 1D sectors",
                "as_of": leadership_as_of,
                "as_of_label": _format_et_timestamp(leadership_as_of),
                "tone": "positive" if leading else "neutral",
            },
        ]

    def _curated_news_articles(self) -> tuple[list[dict[str, Any]], str | None]:
        bundle = self._news_service().get_news_intelligence(None, max_articles=50, force_refresh=False)
        serialized = [
            serialize_article(article).model_dump(mode="json")
            for article in bundle.articles[:50]
        ]
        ranked = sorted(serialized, key=_sort_article, reverse=True)
        curated = [
            article
            for article in ranked
            if article.get("source_signal_tier") != "commentary"
        ][:4]
        if not curated:
            curated = ranked[:4]
        latest_published_at = max(
            (str(article.get("published_at")) for article in curated if article.get("published_at")),
            default=None,
        )
        compact = [
            {
                "headline": _trim_text(article.get("headline")),
                "summary": _trim_text(article.get("summary")),
                "impact_summary": _trim_text(article.get("impact_summary")),
                "actionable_insight": _trim_text(article.get("actionable_insight")),
                "source": _trim_text(article.get("source")),
                "published_at": article.get("published_at"),
                "url": article.get("url"),
                "sentiment": {
                    "label": article.get("sentiment", {}).get("label"),
                    "score": article.get("sentiment", {}).get("score"),
                },
                "event_category": article.get("event_category"),
                "market_context_topic": article.get("market_context_topic"),
                "source_signal_tier": article.get("source_signal_tier"),
                "decision_value_score": _safe_float(article.get("decision_value_score")),
            }
            for article in curated
        ]
        return compact, latest_published_at

    def _news_sources(self, articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
        sources: list[dict[str, Any]] = []
        for index, article in enumerate(articles, start=1):
            source_id = f"news_{index}"
            article["source_id"] = source_id
            sources.append(
                {
                    "id": source_id,
                    "kind": "market_news",
                    "label": _trim_text(article.get("headline"))
                    or _trim_text(article.get("source"))
                    or f"Market article {index}",
                    "published_at": article.get("published_at"),
                    "url": article.get("url"),
                    "source_signal_tier": article.get("source_signal_tier") or "unknown",
                    "decision_value_score": _safe_float(article.get("decision_value_score")),
                }
            )
        return sources

    def _household_snapshot(self, dashboard: Any) -> dict[str, Any]:
        overview = dashboard.overview
        budget = dashboard.budget_snapshot
        return {
            "generated_at": _iso(dashboard.generated_at),
            "net_worth": _safe_float(overview.net_worth),
            "net_worth_status": str(overview.net_worth_status),
            "net_worth_detail": str(overview.net_worth_detail),
            "invested_assets": _safe_float(overview.invested_assets),
            "cash_reserve": _safe_float(overview.cash_reserve),
            "monthly_spend_status": str(overview.monthly_spend_status),
            "monthly_spend_detail": str(overview.monthly_spend_detail),
            "visibility_score": int(overview.visibility_score),
            "needs_refresh_count": int(overview.needs_refresh_count),
            "budget_summary": str(budget.summary),
            "pace_status": str(budget.pace_status),
            "pace_detail": str(budget.pace_detail),
            "month_to_date_spend": _safe_float(budget.month_to_date_spend),
            "month_to_date_plan": _safe_float(budget.month_to_date_plan),
            "future_dated_transactions": len(getattr(dashboard, "transaction_date_issues", []) or []),
            "top_needs": [
                {
                    "title": str(need.title),
                    "detail": str(need.detail),
                    "priority": str(need.priority),
                }
                for need in list(getattr(dashboard, "jenny_needs", []) or [])[:3]
            ],
        }

    def _portfolio_snapshot(self, payload: Any) -> dict[str, Any]:
        positions = sorted(
            [
                {
                    "symbol": str(position.symbol),
                    "current_value": _safe_float(position.current_value),
                    "gain_pct": _safe_float(position.gain_pct),
                }
                for position in list(payload.positions or [])
            ],
            key=lambda row: row["current_value"],
            reverse=True,
        )
        breakdown = build_exposure_breakdown(
            [
                ExposureItem(
                    symbol=row["symbol"],
                    current_value=row["current_value"],
                )
                for row in positions
            ],
            self.storage,
        )
        total_positions_value = breakdown.total_value

        def summarize_bucket_values(
            bucket_values: dict[str, float],
        ) -> tuple[str | None, float, float, float]:
            ranked = sorted(
                bucket_values.items(),
                key=lambda item: item[1],
                reverse=True,
            )
            if not ranked or total_positions_value <= 0:
                return None, 0.0, 0.0, 0.0
            top_name = ranked[0][0]
            top_holding_pct = (ranked[0][1] / total_positions_value) * 100
            top_3_pct = (
                sum(value for _, value in ranked[:3]) / total_positions_value
            ) * 100
            herfindahl_index = sum(
                ((value / total_positions_value) * 100) ** 2 for _, value in ranked
            )
            return top_name, top_holding_pct, top_3_pct, herfindahl_index

        (
            vehicle_top_name,
            vehicle_top_holding_pct,
            vehicle_top_3_pct,
            vehicle_herfindahl_index,
        ) = summarize_bucket_values(breakdown.vehicle_values)
        lookthrough_available = breakdown.lookthrough_covered_value > 0 and bool(
            breakdown.single_name_values
        )
        if lookthrough_available:
            (
                top_holding_name,
                top_holding_pct,
                top_3_pct,
                _,
            ) = summarize_bucket_values(breakdown.single_name_values)
            _, _, _, herfindahl_index = summarize_bucket_values(
                breakdown.risk_bucket_values
            )
        else:
            top_holding_name = vehicle_top_name
            top_holding_pct = vehicle_top_holding_pct
            top_3_pct = vehicle_top_3_pct
            herfindahl_index = vehicle_herfindahl_index
        return {
            "quotes_updated_at": _iso(payload.quotes_updated_at),
            "quote_freshness_status": str(payload.quote_freshness_status or "unknown"),
            "household_invested_total_value": _safe_float(
                payload.household_invested_total_value
            ),
            "effective_total_value": _safe_float(payload.effective_total_value),
            "total_gain": _safe_float(payload.total_gain),
            "positions": positions[:5],
            "num_positions": len(positions),
            "num_symbols": len({row["symbol"] for row in positions}),
            "concentration": {
                "top_holding_pct": top_holding_pct,
                "top_3_pct": top_3_pct,
                "herfindahl_index": herfindahl_index,
                "method": "lookthrough" if lookthrough_available else "line_item",
                "top_holding_name": top_holding_name,
                "vehicle_top_holding_pct": vehicle_top_holding_pct,
                "vehicle_top_3_pct": vehicle_top_3_pct,
                "vehicle_herfindahl_index": vehicle_herfindahl_index,
                "vehicle_top_holding_name": vehicle_top_name,
                "lookthrough_coverage_pct": (
                    (breakdown.lookthrough_covered_value / total_positions_value) * 100
                    if total_positions_value > 0
                    else 0.0
                ),
            },
        }

    def _prompt_context(
        self,
        household: dict[str, Any],
        portfolio: dict[str, Any],
        market: dict[str, Any],
        articles: list[dict[str, Any]],
        source_list: list[dict[str, Any]],
        upcoming_events: list[dict[str, Any]],
        scout_research: dict[str, Any] | None,
    ) -> dict[str, Any]:
        return {
            "run_timestamp": datetime.now(UTC).isoformat(),
            "analysis_constraints": {
                "max_catalysts": 3,
                "max_impacts": 4,
                "focus": "catalysts -> market reaction -> portfolio/money impact",
            },
            "household_snapshot": household,
            "portfolio_snapshot": portfolio,
            "market_snapshot": market,
            "news_evidence": articles,
            "external_research": scout_research,
            "source_list": source_list,
            "upcoming_macro_catalysts": upcoming_events[:5],
            "output_contract": _TODAY_BRIEF_CONTRACT,
        }

    def _fallback_payload(
        self,
        household: dict[str, Any],
        portfolio: dict[str, Any],
        market: dict[str, Any],
        articles: list[dict[str, Any]],
    ) -> dict[str, Any]:
        top_holding_pct = _safe_float(
            portfolio["concentration"].get("top_holding_pct")
        )
        top_holding_name = _trim_text(
            portfolio["concentration"].get("top_holding_name")
        ) or "top single-name exposure"
        concentration_method = str(
            portfolio["concentration"].get("method") or "line_item"
        )
        vehicle_top_holding_pct = _safe_float(
            portfolio["concentration"].get("vehicle_top_holding_pct")
        )
        vehicle_top_name = _trim_text(
            portfolio["concentration"].get("vehicle_top_holding_name")
        ) or "largest vehicle"
        top_positions = portfolio.get("positions", [])[:3]
        top_symbols = [str(row.get("symbol")) for row in top_positions if row.get("symbol")]
        leading = market["sector_rotation"].get("leading", [])[:3]
        leadership = ", ".join(
            str(row.get("name") or "") for row in leading if row.get("name")
        )
        stance = "cautious" if top_holding_pct >= 20 else "constructive"
        if concentration_method == "lookthrough":
            summary = (
                f"Risk appetite is holding up while {leadership or 'leadership is mixed'}, "
                f"and your largest vehicle is {vehicle_top_name} at {vehicle_top_holding_pct:.1f}% "
                f"of positioned assets, but top single-name exposure is only "
                f"{top_holding_name} at {top_holding_pct:.1f}% after ETF look-through."
            )
            headline = (
                "Constructive tape, ETF-heavy but not single-name concentrated"
                if vehicle_top_holding_pct >= 50 and top_holding_pct < 10
                else "Constructive tape, but watch portfolio sensitivity"
            )
        else:
            summary = (
                f"Risk appetite is holding up while {leadership or 'leadership is mixed'}, "
                f"but your positioned portfolio stays unusually concentrated."
            )
            headline = (
                "Risk-on tape, concentration still main risk"
                if top_holding_pct >= 60
                else "Constructive tape, but watch portfolio sensitivity"
            )
        catalysts: list[dict[str, Any]] = []
        for index, article in enumerate(articles[:3], start=1):
            source_id = str(article.get("source_id") or f"news_{index}")
            catalysts.append(
                {
                    "id": f"catalyst_{index}",
                    "title": _trim_text(article.get("headline")) or f"Catalyst {index}",
                    "direction": "positive"
                    if str(article.get("sentiment", {}).get("label")) == "positive"
                    else "negative"
                    if str(article.get("sentiment", {}).get("label")) == "negative"
                    else "mixed",
                    "market_effect": _trim_text(article.get("impact_summary"))
                    or "Market tone moved on fresh headlines.",
                    "portfolio_effect": (
                        f"{', '.join(top_symbols) or 'Your equity exposure'} will likely feel this first."
                    ),
                    "money_effect": (
                        "Keep money decisions tied to cash visibility, because one spending account is stale."
                    ),
                    "source_ids": [source_id],
                }
            )
        if not catalysts:
            catalysts.append(
                {
                    "id": "catalyst_market_tape",
                    "title": "Broad market leadership is still risk-on",
                    "direction": "positive",
                    "market_effect": "S&P 500 is firm and fear/greed remains above neutral.",
                    "portfolio_effect": (
                        "That helps broad ETF-heavy exposure, but wrapper size still drives most of the portfolio move."
                        if concentration_method == "lookthrough"
                        else "That helps VTI-heavy exposure, but also magnifies concentration."
                    ),
                    "money_effect": "Do not let a strong tape hide stale cash-flow inputs.",
                    "source_ids": [],
                }
            )

        primary_impact = (
            {
                "label": "Broad market beta dominates the read",
                "direction": "mixed",
                "magnitude": "medium",
                "rationale": (
                    f"Largest vehicle is {vehicle_top_name} at {vehicle_top_holding_pct:.1f}% "
                    f"of positioned assets, but top single-name exposure is only "
                    f"{top_holding_name} at {top_holding_pct:.1f}% after ETF look-through."
                ),
                "affected_symbols": top_symbols,
                "source_ids": [],
            }
            if concentration_method == "lookthrough"
            else {
                "label": "Portfolio concentration dominates the read",
                "direction": "headwind" if top_holding_pct >= 60 else "mixed",
                "magnitude": "high",
                "rationale": (
                    f"Top holding is {top_holding_pct:.1f}% of the positioned portfolio, "
                    "so broad-market strength helps, but one allocation still drives most of the swing."
                ),
                "affected_symbols": top_symbols,
                "source_ids": [],
            }
        )

        impacts = [
            primary_impact,
            {
                "label": "Tech and growth leadership matter more here",
                "direction": "tailwind",
                "magnitude": "medium",
                "rationale": (
                    f"Leading sectors are {leadership or 'mixed'}, which maps well to VTI, NVDA, AMZN, TSLA, and VUG."
                ),
                "affected_symbols": [
                    symbol
                    for symbol in top_symbols
                    if symbol in {"VTI", "NVDA", "AMZN", "TSLA", "VUG"}
                ],
                "source_ids": [],
            },
            {
                "label": "Cash and spend confidence still need cleanup",
                "direction": "mixed",
                "magnitude": "medium",
                "rationale": (
                    f"Cash reserve is ${household['cash_reserve']:,.0f}, but "
                    f"{household['needs_refresh_count']} account(s) need fresher evidence and "
                    f"{household['future_dated_transactions']} future-dated transactions are outside current spend math."
                ),
                "affected_symbols": [],
                "source_ids": [],
            },
        ]
        return {
            "brief": {
                "headline": headline,
                "summary": summary,
                "stance": stance,
                "confidence": "medium",
                "why_now": (
                    "Macro tone is constructive, but ETF-heavy positioning still means broad-market tape drives portfolio swings."
                    if concentration_method == "lookthrough"
                    else "Macro tone is constructive, but portfolio and cash-flow concentration still matter more than headlines alone."
                ),
                "bullets": [
                    "Watch catalysts that move broad U.S. equity leadership first.",
                    (
                        f"Separate vehicle size from single-name risk: {vehicle_top_name} is {vehicle_top_holding_pct:.1f}% of assets, but top single-name exposure is {top_holding_name} at {top_holding_pct:.1f}%."
                        if concentration_method == "lookthrough"
                        else "Treat strong market action as portfolio-sensitive, not automatically diversified."
                    ),
                    "Keep money decisions anchored to stale-data cleanup until cash-flow trust improves.",
                ],
            },
            "catalysts": catalysts,
            "impacts": impacts[:4],
        }

    def _normalize_payload(
        self,
        payload: dict[str, Any],
        fallback: dict[str, Any],
        source_ids: set[str],
    ) -> dict[str, Any]:
        brief = payload.get("brief") if isinstance(payload.get("brief"), dict) else {}
        fallback_brief = fallback["brief"]
        normalized_brief = {
            "headline": _trim_text(brief.get("headline")) or fallback_brief["headline"],
            "summary": _trim_text(brief.get("summary")) or fallback_brief["summary"],
            "stance": _normalize_direction(
                brief.get("stance"),
                allowed={"constructive", "neutral", "cautious"},
                fallback=fallback_brief["stance"],
            ),
            "confidence": _normalize_direction(
                brief.get("confidence"),
                allowed={"high", "medium", "low"},
                fallback=fallback_brief["confidence"],
            ),
            "why_now": _trim_text(brief.get("why_now")) or fallback_brief["why_now"],
            "bullets": [
                _trim_text(item)
                for item in _as_list(brief.get("bullets"))
                if _trim_text(item)
            ][:4]
            or fallback_brief["bullets"],
        }

        catalysts = []
        raw_catalysts = _as_list(payload.get("catalysts"))
        for index, raw in enumerate(raw_catalysts[:3], start=1):
            if not isinstance(raw, dict):
                continue
            valid_source_ids = [
                source_id
                for source_id in [_trim_text(value) for value in _as_list(raw.get("source_ids"))]
                if source_id in source_ids
            ]
            catalysts.append(
                {
                    "id": _trim_text(raw.get("id")) or f"catalyst_{index}",
                    "title": _trim_text(raw.get("title")) or fallback["catalysts"][0]["title"],
                    "direction": _normalize_direction(
                        raw.get("direction"),
                        allowed={"positive", "negative", "mixed", "watch"},
                        fallback="mixed",
                    ),
                    "market_effect": _trim_text(raw.get("market_effect"))
                    or fallback["catalysts"][0]["market_effect"],
                    "portfolio_effect": _trim_text(raw.get("portfolio_effect"))
                    or fallback["catalysts"][0]["portfolio_effect"],
                    "money_effect": _trim_text(raw.get("money_effect"))
                    or fallback["catalysts"][0]["money_effect"],
                    "source_ids": valid_source_ids,
                }
            )
        if not catalysts:
            catalysts = fallback["catalysts"]

        impacts = []
        raw_impacts = _as_list(payload.get("impacts"))
        for raw in raw_impacts[:4]:
            if not isinstance(raw, dict):
                continue
            valid_source_ids = [
                source_id
                for source_id in [_trim_text(value) for value in _as_list(raw.get("source_ids"))]
                if source_id in source_ids
            ]
            impacts.append(
                {
                    "label": _trim_text(raw.get("label")) or fallback["impacts"][0]["label"],
                    "direction": _normalize_direction(
                        raw.get("direction"),
                        allowed={"tailwind", "headwind", "mixed"},
                        fallback="mixed",
                    ),
                    "magnitude": _normalize_direction(
                        raw.get("magnitude"),
                        allowed={"high", "medium", "low"},
                        fallback="medium",
                    ),
                    "rationale": _trim_text(raw.get("rationale"))
                    or fallback["impacts"][0]["rationale"],
                    "affected_symbols": [
                        _trim_text(symbol).upper()
                        for symbol in _as_list(raw.get("affected_symbols"))
                        if _trim_text(symbol)
                    ][:5],
                    "source_ids": valid_source_ids,
                }
            )
        if not impacts:
            impacts = fallback["impacts"]

        return {
            "brief": normalized_brief,
            "catalysts": catalysts,
            "impacts": impacts,
        }

    def _agent_payload(
        self,
        context: dict[str, Any],
        fallback: dict[str, Any],
        source_ids: set[str],
    ) -> dict[str, Any]:
        prompt = (
            "Use this context to produce the Today Market Pulse brief.\n\n"
            f"{_json_block(context)}"
        )
        client = AgentHubAPIClient(
            agent_slug=_MARKET_PULSE_AGENT_SLUG,
        )
        try:
            response = client.complete_messages(
                messages=[{"role": "user", "content": prompt}],
                purpose="home_today_brief",
                response_format={"type": "json_object"},
                max_turns=3,
                execute_tools=True,
                enable_programmatic_tools=True,
            )
        finally:
            client.close()

        payload_text = extract_json_object_text(str(getattr(response, "content", "") or ""))
        if payload_text is None:
            return fallback
        try:
            parsed = json.loads(payload_text)
        except json.JSONDecodeError:
            logger.warning("home_today_brief_parse_failed", content=payload_text)
            return fallback
        if not isinstance(parsed, dict):
            return fallback
        return self._normalize_payload(parsed, fallback, source_ids)

    def _market_cache_basis(self, market: dict[str, Any]) -> dict[str, Any]:
        indicators = market.get("indicators", {})
        sp500 = _indicator_payload(indicators, "sp500")
        vix = _indicator_payload(indicators, "vix")
        tnx = _indicator_payload(indicators, "tnx")
        leading = [
            row.get("name")
            for row in _as_list(market.get("sector_rotation", {}).get("leading"))[:3]
            if isinstance(row, dict) and row.get("name")
        ]
        fear_greed = market.get("fear_greed", {})
        if not isinstance(fear_greed, dict):
            fear_greed = {}

        def rounded(value: Any, digits: int = 1) -> float | None:
            number = _optional_float(value)
            return round(number, digits) if number is not None else None

        return {
            "status": market.get("status"),
            "sp500_change_pct": rounded(sp500.get("change_pct")),
            "vix_bucket": rounded(vix.get("value"), 0),
            "tnx_bucket": rounded(tnx.get("value")),
            "fear_greed_label": fear_greed.get("label"),
            "fear_greed_score_bucket": rounded(fear_greed.get("score"), 0),
            "leading_sectors": leading,
        }

    def _household_cache_basis(self, household: dict[str, Any]) -> dict[str, Any]:
        return {
            "net_worth_status": household.get("net_worth_status"),
            "monthly_spend_status": household.get("monthly_spend_status"),
            "needs_refresh_count": household.get("needs_refresh_count"),
            "future_dated_transactions": household.get("future_dated_transactions"),
            "pace_status": household.get("pace_status"),
        }

    def _portfolio_cache_basis(self, portfolio: dict[str, Any]) -> dict[str, Any]:
        concentration = portfolio.get("concentration", {})
        if not isinstance(concentration, dict):
            concentration = {}
        return {
            "quote_freshness_status": portfolio.get("quote_freshness_status"),
            "top_symbols": [
                row.get("symbol")
                for row in _as_list(portfolio.get("positions"))[:5]
                if isinstance(row, dict) and row.get("symbol")
            ],
            "concentration_method": concentration.get("method"),
            "top_holding_name": concentration.get("top_holding_name"),
            "top_holding_pct": round(_safe_float(concentration.get("top_holding_pct")), 1),
            "top_3_pct": round(_safe_float(concentration.get("top_3_pct")), 1),
        }

    def _research_cache_key(
        self,
        household: dict[str, Any],
        portfolio: dict[str, Any],
        market: dict[str, Any],
        articles: list[dict[str, Any]],
        upcoming_events: list[dict[str, Any]],
    ) -> str:
        compact = {
            "household": self._household_cache_basis(household),
            "portfolio": self._portfolio_cache_basis(portfolio),
            "market": self._market_cache_basis(market),
            "headlines": [article.get("headline") for article in articles[:4]],
            "events": [event.get("label") for event in upcoming_events[:5]],
        }
        return sha1(_json_block(compact).encode("utf-8")).hexdigest()

    def _narrative_cache_key_for_context(self, context: dict[str, Any]) -> str:
        external_research = context.get("external_research")
        if not isinstance(external_research, dict):
            external_research = {}
        compact = {
            "household": self._household_cache_basis(context["household_snapshot"]),
            "portfolio": self._portfolio_cache_basis(context["portfolio_snapshot"]),
            "market": self._market_cache_basis(context["market_snapshot"]),
            "headlines": [article.get("headline") for article in context.get("news_evidence", [])],
            "external_summary": _trim_text(external_research.get("summary")),
            "external_sources": [
                source.get("url")
                for source in _as_list(external_research.get("sources"))
                if isinstance(source, dict)
            ][:8],
        }
        return sha1(_json_block(compact).encode("utf-8")).hexdigest()

    def _cached_narrative(self) -> tuple[dict[str, Any] | None, bool]:
        with self._narrative_lock:
            if self._narrative_cache is None or self._narrative_cached_at is None:
                return None, False
            age = (datetime.now(UTC) - self._narrative_cached_at).total_seconds()
            return self._narrative_cache, age <= _NARRATIVE_CACHE_SECONDS

    def _load_persisted_narrative(self, cache_key: str) -> dict[str, Any] | None:
        try:
            with self.storage.connection() as conn:
                row = conn.execute(
                    """
                    SELECT metadata
                    FROM market_pulse_research_runs
                    WHERE request_kind = %s
                      AND status = 'success'
                      AND cache_key = %s
                      AND completed_at >= %s
                    ORDER BY completed_at DESC
                    LIMIT 1
                    """,
                    [
                        _NARRATIVE_REQUEST_KIND,
                        cache_key,
                        datetime.now(UTC) - timedelta(seconds=_NARRATIVE_CACHE_SECONDS),
                    ],
                ).fetchone()
        except Exception as exc:
            logger.warning("home_today_brief_narrative_cache_load_failed", error=str(exc))
            return None

        if row is None:
            return None
        metadata = row[0]
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except json.JSONDecodeError:
                return None
        payload = metadata.get("payload") if isinstance(metadata, dict) else None
        if not isinstance(payload, dict) or not isinstance(payload.get("brief"), dict):
            return None
        with self._narrative_lock:
            self._narrative_cache = payload
            self._narrative_cache_key = cache_key
            self._narrative_cached_at = datetime.now(UTC)
        return payload

    def _record_narrative_success(self, *, cache_key: str, payload: dict[str, Any]) -> None:
        metadata = json.dumps({"agent_slug": _MARKET_PULSE_AGENT_SLUG, "payload": payload})
        now = datetime.now(UTC)
        try:
            with self.storage.connection() as conn:
                conn.execute(
                    """
                    INSERT INTO market_pulse_research_runs (
                        id,
                        provider,
                        model,
                        status,
                        request_kind,
                        cache_key,
                        fallback_used,
                        input_tokens,
                        output_tokens,
                        reasoning_tokens,
                        source_count,
                        error_detail,
                        metadata,
                        created_at,
                        completed_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s
                    )
                    """,
                    [
                        str(uuid.uuid4()),
                        "agent_hub",
                        _MARKET_PULSE_AGENT_SLUG,
                        "success",
                        _NARRATIVE_REQUEST_KIND,
                        cache_key,
                        False,
                        0,
                        0,
                        0,
                        len(_as_list(payload.get("catalysts"))),
                        None,
                        metadata,
                        now,
                        now,
                    ],
                )
                conn.commit()
        except Exception as exc:
            logger.warning("home_today_brief_narrative_cache_write_failed", error=str(exc))

    def _cached_response(self) -> dict[str, Any] | None:
        with self._narrative_lock:
            if self._response_cache is None or self._response_cached_at is None:
                return None
            age = (datetime.now(UTC) - self._response_cached_at).total_seconds()
            return self._response_cache if age <= _RESPONSE_CACHE_SECONDS else None

    def _refresh_narrative(
        self,
        *,
        household: dict[str, Any],
        portfolio: dict[str, Any],
        market: dict[str, Any],
        articles: list[dict[str, Any]],
        news_sources: list[dict[str, Any]],
        official_sources: list[dict[str, Any]],
        upcoming_events: list[dict[str, Any]],
        research_cache_key: str,
        fallback: dict[str, Any],
        claimed: bool = False,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        if not claimed:
            with self._narrative_lock:
                if self._refresh_in_flight:
                    cached_narrative = self._narrative_cache or fallback
                    return cached_narrative, _merge_sources(news_sources, official_sources)
                self._refresh_in_flight = True

        try:
            scout_research = self.research_service.build_research(
                cache_key=research_cache_key,
                household=household,
                portfolio=portfolio,
                market=market,
                articles=articles,
                official_sources=official_sources,
                upcoming_events=upcoming_events,
            )
            source_stack = _merge_sources(
                news_sources,
                _as_list(scout_research.get("sources")) if isinstance(scout_research, dict) else [],
                official_sources,
            )
            source_ids = {source["id"] for source in source_stack}
            context = self._prompt_context(
                household,
                portfolio,
                market,
                articles,
                source_stack,
                upcoming_events,
                scout_research,
            )
            cache_key = self._narrative_cache_key_for_context(context)
            generated = self._agent_payload(context, fallback, source_ids)
            with self._narrative_lock:
                self._narrative_cache = generated
                self._narrative_cache_key = cache_key
                self._narrative_cached_at = datetime.now(UTC)
            self._record_narrative_success(cache_key=cache_key, payload=generated)
            return generated, source_stack
        except Exception as exc:
            logger.warning("home_today_brief_agent_failed", error=str(exc))
            cached_narrative, _ = self._cached_narrative()
            return cached_narrative or fallback, _merge_sources(news_sources, official_sources)
        finally:
            with self._narrative_lock:
                self._refresh_in_flight = False

    def _start_background_narrative_refresh(
        self,
        *,
        household: dict[str, Any],
        portfolio: dict[str, Any],
        market: dict[str, Any],
        articles: list[dict[str, Any]],
        news_sources: list[dict[str, Any]],
        official_sources: list[dict[str, Any]],
        upcoming_events: list[dict[str, Any]],
        research_cache_key: str,
        fallback: dict[str, Any],
    ) -> None:
        with self._narrative_lock:
            if self._refresh_in_flight:
                return
            self._refresh_in_flight = True

        thread = Thread(
            target=self._refresh_narrative,
            kwargs={
                "household": household,
                "portfolio": portfolio,
                "market": market,
                "articles": articles,
                "news_sources": news_sources,
                "official_sources": official_sources,
                "upcoming_events": upcoming_events,
                "research_cache_key": research_cache_key,
                "fallback": fallback,
                "claimed": True,
            },
            daemon=True,
            name="home-today-brief-refresh",
        )
        thread.start()

    def get_today_brief(self) -> dict[str, Any]:
        cached_response = self._cached_response()
        if cached_response is not None:
            return cached_response

        with ThreadPoolExecutor(max_workers=4) as executor:
            household_future = executor.submit(self.household_service.get_dashboard)
            portfolio_future = executor.submit(self._portfolio_payload)
            market_future = executor.submit(self._market_snapshot)
            news_future = executor.submit(self._curated_news_articles)
            household_dashboard = household_future.result()
            portfolio_payload = portfolio_future.result()
            market, market_status, market_as_of = market_future.result()
            articles, news_as_of = news_future.result()

        household = self._household_snapshot(household_dashboard)
        portfolio = self._portfolio_snapshot(portfolio_payload)
        news_sources = self._news_sources(articles)
        official_sources = list(_OFFICIAL_SOURCE_STACK)
        upcoming_events = _upcoming_event_payloads(get_upcoming_events(14))

        fallback = self._fallback_payload(household, portfolio, market, articles)
        research_cache_key = self._research_cache_key(
            household,
            portfolio,
            market,
            articles,
            upcoming_events,
        )
        scout_research, scout_is_fresh = self.research_service.get_cached_research(
            research_cache_key
        )
        source_stack = _merge_sources(
            news_sources,
            _as_list(scout_research.get("sources")) if isinstance(scout_research, dict) else [],
            official_sources,
        )
        context = self._prompt_context(
            household,
            portfolio,
            market,
            articles,
            source_stack,
            upcoming_events,
            scout_research,
        )
        cache_key = self._narrative_cache_key_for_context(context)
        cached_narrative, cache_is_fresh = self._cached_narrative()
        cached_key = self._narrative_cache_key
        if (
            cached_narrative is None
            or not cache_is_fresh
            or cached_key != cache_key
        ):
            persisted_narrative = self._load_persisted_narrative(cache_key)
            if persisted_narrative is not None:
                cached_narrative = persisted_narrative
                cache_is_fresh = True
                cached_key = cache_key
        narrative = cached_narrative or fallback
        should_refresh = (
            cached_narrative is not None
            and (
                not cache_is_fresh
                or cached_key != cache_key
                or not scout_is_fresh
            )
        )
        if should_refresh:
            self._start_background_narrative_refresh(
                household=household,
                portfolio=portfolio,
                market=market,
                articles=articles,
                news_sources=news_sources,
                official_sources=official_sources,
                upcoming_events=upcoming_events,
                research_cache_key=research_cache_key,
                fallback=fallback,
            )

        staleness_notes: list[str] = []
        if household["monthly_spend_status"] != "current":
            staleness_notes.append(household["monthly_spend_detail"])
        if household["net_worth_status"] != "current":
            staleness_notes.append(household["net_worth_detail"])
        if portfolio["quote_freshness_status"] not in {"fresh", "current"}:
            staleness_notes.append(
                f"Portfolio quotes are {portfolio['quote_freshness_status']}."
            )

        response = {
            "generated_at": datetime.now(UTC).isoformat(),
            "cache_ttl_seconds": _RESPONSE_CACHE_SECONDS,
            "as_of": {
                "household": household["generated_at"],
                "portfolio": portfolio["quotes_updated_at"],
                "market": market_as_of,
                "news": news_as_of,
            },
            "market_status": market_status,
            "brief": narrative["brief"],
            "catalysts": narrative["catalysts"],
            "impacts": narrative["impacts"],
            "market_metrics": self._market_metrics(market),
            "sources": source_stack,
            "staleness_notes": staleness_notes[:3],
        }
        with self._narrative_lock:
            self._response_cache = response
            self._response_cached_at = datetime.now(UTC)
        return response
