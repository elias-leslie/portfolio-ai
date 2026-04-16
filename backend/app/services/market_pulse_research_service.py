"""External market scout support for the Today Market Pulse."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from hashlib import sha1
from threading import Lock
from typing import Any
from urllib.parse import urlparse

from app.agents.clients.agent_hub_client import AgentHubAPIClient
from app.logging_config import get_logger
from app.services._jenny_response_cleanup import extract_json_object_text
from app.storage import get_storage

logger = get_logger(__name__)

_SCOUT_AGENT_SLUG = "market-pulse-scout"
_SCOUT_CACHE_SECONDS = 60 * 20
_SCOUT_COOLDOWN_MINUTES = 60 * 6
_SCOUT_MAX_TURNS = 4

_OFFICIAL_DOMAINS = {
    "bea.gov",
    "bls.gov",
    "eia.gov",
    "federalreserve.gov",
    "home.treasury.gov",
    "sec.gov",
    "treasury.gov",
}
_MAJOR_MARKET_DOMAINS = {
    "bloomberg.com",
    "cnbc.com",
    "finance.yahoo.com",
    "ft.com",
    "google.com",
    "marketwatch.com",
    "nasdaq.com",
    "reuters.com",
    "wsj.com",
}
_SCOUT_OUTPUT_CONTRACT = {
    "summary": "string",
    "catalysts": [
        {
            "title": "string",
            "direction": "positive|negative|mixed|watch",
            "market_effect": "string",
            "why_it_matters": "string",
            "source_ids": ["string"],
        }
    ],
    "watch_items": ["string"],
    "sources": [
        {
            "id": "string",
            "label": "string",
            "url": "string",
            "published_at": "string|null",
            "kind": "official|filing|market_data|market_news|x_post|x_thread|commentary",
        }
    ],
}


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _json_block(payload: Any) -> str:
    return json.dumps(payload, indent=2, default=_json_default)


def _trim_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _source_id(url: str) -> str:
    return f"scout_{sha1(url.encode('utf-8')).hexdigest()[:12]}"


def _normalize_domain(url: str) -> str:
    parsed = urlparse(url)
    return (parsed.netloc or "").lower().removeprefix("www.")


def _score_source(url: str, kind: str | None, label: str | None) -> dict[str, Any]:
    domain = _normalize_domain(url)
    lowered_kind = _trim_text(kind).lower()
    lowered_label = _trim_text(label).lower()

    if domain in _OFFICIAL_DOMAINS or lowered_kind in {"official", "filing"}:
        return {
            "kind": "macro_data" if lowered_kind != "filing" else "filing",
            "source_signal_tier": "primary",
            "decision_value_score": 1.0 if domain in _OFFICIAL_DOMAINS else 0.95,
            "domain": domain,
        }
    if domain in {"x.com", "twitter.com"} or lowered_kind in {"x_post", "x_thread"}:
        is_official_handle = any(
            token in lowered_label
            for token in ("federal reserve", "u.s. treasury", "bls", "bea", "eia", "sec")
        )
        return {
            "kind": "market_news" if is_official_handle else "commentary",
            "source_signal_tier": "secondary" if is_official_handle else "commentary",
            "decision_value_score": 0.65 if is_official_handle else 0.35,
            "domain": domain,
        }
    if domain in _MAJOR_MARKET_DOMAINS:
        return {
            "kind": "market_news" if "news" in lowered_kind or lowered_kind else "market_data",
            "source_signal_tier": "secondary",
            "decision_value_score": 0.75,
            "domain": domain,
        }
    return {
        "kind": "market_news" if lowered_kind else "commentary",
        "source_signal_tier": "unknown",
        "decision_value_score": 0.5,
        "domain": domain,
    }


class MarketPulseResearchService:
    """Run a scout agent that gathers external market evidence."""

    def __init__(self) -> None:
        self.storage = get_storage()
        self._lock = Lock()
        self._cache: dict[str, Any] | None = None
        self._cache_key: str | None = None
        self._cached_at: datetime | None = None
        self._cooldown_until: datetime | None = None

    def get_cached_research(self, cache_key: str) -> tuple[dict[str, Any] | None, bool]:
        with self._lock:
            if self._cache is None or self._cache_key != cache_key or self._cached_at is None:
                return None, False
            age = (datetime.now(UTC) - self._cached_at).total_seconds()
            return self._cache, age <= _SCOUT_CACHE_SECONDS

    def _trusted_source_seed(self, *, limit: int = 6) -> list[dict[str, Any]]:
        try:
            with self.storage.connection() as conn:
                rows = conn.execute(
                    """
                    SELECT
                        url,
                        domain,
                        label,
                        source_kind,
                        source_signal_tier,
                        decision_value_score,
                        validation_status,
                        last_validated_at
                    FROM market_pulse_source_profiles
                    WHERE validation_status IN ('validated', 'watch')
                    ORDER BY decision_value_score DESC, last_validated_at DESC NULLS LAST, updated_at DESC
                    LIMIT %s
                    """,
                    [limit],
                ).fetchall()
        except Exception as exc:
            logger.warning("market_pulse_source_seed_failed", error=str(exc))
            return []

        return [
            {
                "url": str(row[0]),
                "domain": str(row[1]),
                "label": str(row[2]),
                "kind": str(row[3]),
                "source_signal_tier": str(row[4]),
                "decision_value_score": float(row[5] or 0.0),
                "validation_status": str(row[6]),
                "last_validated_at": row[7].isoformat() if row[7] else None,
            }
            for row in rows
        ]

    def build_research(
        self,
        *,
        cache_key: str,
        household: dict[str, Any],
        portfolio: dict[str, Any],
        market: dict[str, Any],
        articles: list[dict[str, Any]],
        official_sources: list[dict[str, Any]],
        upcoming_events: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        cached, fresh = self.get_cached_research(cache_key)
        if fresh:
            return cached

        now = datetime.now(UTC)
        with self._lock:
            if self._cooldown_until is not None and now < self._cooldown_until:
                return cached

        prompt = self._build_prompt(
            household=household,
            portfolio=portfolio,
            market=market,
            articles=articles,
            official_sources=official_sources,
            upcoming_events=upcoming_events,
        )

        client = AgentHubAPIClient(agent_slug=_SCOUT_AGENT_SLUG)
        run_id = str(uuid.uuid4())
        started_at = datetime.now(UTC)
        failure_reason: str | None = None
        normalized: dict[str, Any] | None = None
        try:
            response = client.complete_messages(
                messages=[{"role": "user", "content": prompt}],
                purpose="market_pulse_scout",
                response_format={"type": "json_object"},
                max_turns=_SCOUT_MAX_TURNS,
                execute_tools=True,
                enable_programmatic_tools=True,
            )
        except Exception as exc:
            failure_reason = str(exc)
        finally:
            client.close()

        if failure_reason is None:
            payload_text = extract_json_object_text(str(getattr(response, "content", "") or ""))
            if payload_text is None:
                failure_reason = "scout returned no JSON payload"
            else:
                try:
                    parsed = json.loads(payload_text)
                except json.JSONDecodeError as exc:
                    failure_reason = str(exc)
                else:
                    if not isinstance(parsed, dict):
                        failure_reason = "scout returned non-object payload"
                    else:
                        normalized = self._normalize_payload(parsed)
                        if not normalized["sources"]:
                            failure_reason = "scout returned no usable sources"

        if failure_reason is not None:
            self._record_failure(
                run_id=run_id,
                started_at=started_at,
                error=failure_reason,
            )
            return cached

        assert normalized is not None
        self._upsert_source_profiles(normalized["sources"])
        self._record_success(
            run_id=run_id,
            started_at=started_at,
            response=response,
            source_count=len(normalized["sources"]),
            cache_key=cache_key,
        )
        with self._lock:
            self._cache = normalized
            self._cache_key = cache_key
            self._cached_at = datetime.now(UTC)
            self._cooldown_until = None
        return normalized

    def _build_prompt(
        self,
        *,
        household: dict[str, Any],
        portfolio: dict[str, Any],
        market: dict[str, Any],
        articles: list[dict[str, Any]],
        official_sources: list[dict[str, Any]],
        upcoming_events: list[dict[str, Any]],
    ) -> str:
        context = {
            "run_timestamp": datetime.now(UTC).isoformat(),
            "task": {"output_contract": _SCOUT_OUTPUT_CONTRACT},
            "household_snapshot": household,
            "portfolio_snapshot": {
                "quotes_updated_at": portfolio.get("quotes_updated_at"),
                "positions": portfolio.get("positions", []),
                "concentration": portfolio.get("concentration", {}),
            },
            "market_snapshot": market,
            "news_seed": articles[:4],
            "trusted_source_seed": self._trusted_source_seed(),
            "official_source_seed": official_sources,
            "upcoming_macro_catalysts": upcoming_events[:5],
        }
        return (
            "Today Market Pulse scout input. Return JSON only.\n\n"
            f"{_json_block(context)}"
        )

    def _normalize_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        raw_sources = _as_list(payload.get("sources"))
        source_id_map: dict[str, str] = {}
        sources: list[dict[str, Any]] = []
        seen_urls: set[str] = set()

        for raw in raw_sources[:8]:
            if not isinstance(raw, dict):
                continue
            url = _trim_text(raw.get("url"))
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            raw_id = _trim_text(raw.get("id")) or url
            normalized_id = _source_id(url)
            source_id_map[raw_id] = normalized_id
            scoring = _score_source(url, _trim_text(raw.get("kind")) or None, _trim_text(raw.get("label")) or None)
            sources.append(
                {
                    "id": normalized_id,
                    "kind": scoring["kind"],
                    "label": _trim_text(raw.get("label")) or scoring["domain"] or url,
                    "published_at": _trim_text(raw.get("published_at")) or None,
                    "url": url,
                    "source_signal_tier": scoring["source_signal_tier"],
                    "decision_value_score": scoring["decision_value_score"],
                }
            )

        catalysts: list[dict[str, Any]] = []
        for raw in _as_list(payload.get("catalysts"))[:3]:
            if not isinstance(raw, dict):
                continue
            source_ids = [
                source_id_map[source_id]
                for source_id in [_trim_text(item) for item in _as_list(raw.get("source_ids"))]
                if source_id in source_id_map
            ]
            catalysts.append(
                {
                    "title": _trim_text(raw.get("title")),
                    "direction": _trim_text(raw.get("direction")).lower() or "mixed",
                    "market_effect": _trim_text(raw.get("market_effect")),
                    "why_it_matters": _trim_text(raw.get("why_it_matters")),
                    "source_ids": source_ids,
                }
            )

        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "summary": _trim_text(payload.get("summary")),
            "catalysts": [item for item in catalysts if item["title"]],
            "watch_items": [
                _trim_text(item)
                for item in _as_list(payload.get("watch_items"))
                if _trim_text(item)
            ][:3],
            "sources": sources,
        }

    def _record_success(
        self,
        *,
        run_id: str,
        started_at: datetime,
        response: Any,
        source_count: int,
        cache_key: str,
    ) -> None:
        usage = getattr(response, "usage", None)
        input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
        output_details = getattr(usage, "output_tokens_details", None)
        reasoning_tokens = int(getattr(output_details, "reasoning_tokens", 0) or 0)
        self._insert_run(
            run_id=run_id,
            provider=str(getattr(response, "provider", "agent_hub")),
            model=str(getattr(response, "model", _SCOUT_AGENT_SLUG)),
            status="success",
            cache_key=cache_key,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            reasoning_tokens=reasoning_tokens,
            source_count=source_count,
            error_detail=None,
            started_at=started_at,
            completed_at=datetime.now(UTC),
            fallback_used=False,
        )

    def _record_failure(
        self,
        *,
        run_id: str,
        started_at: datetime,
        error: str,
    ) -> None:
        lowered = error.lower()
        fallback_used = True
        status = "failed"
        if any(token in lowered for token in ("quota", "rate limit", "429", "402", "insufficient credits")):
            status = "quota_exhausted"
            with self._lock:
                self._cooldown_until = datetime.now(UTC) + timedelta(minutes=_SCOUT_COOLDOWN_MINUTES)
        self._insert_run(
            run_id=run_id,
            provider="agent_hub",
            model=_SCOUT_AGENT_SLUG,
            status=status,
            cache_key=None,
            input_tokens=0,
            output_tokens=0,
            reasoning_tokens=0,
            source_count=0,
            error_detail=error[:500],
            started_at=started_at,
            completed_at=datetime.now(UTC),
            fallback_used=fallback_used,
        )

    def _insert_run(
        self,
        *,
        run_id: str,
        provider: str,
        model: str,
        status: str,
        cache_key: str | None,
        input_tokens: int,
        output_tokens: int,
        reasoning_tokens: int,
        source_count: int,
        error_detail: str | None,
        started_at: datetime,
        completed_at: datetime,
        fallback_used: bool,
    ) -> None:
        payload = json.dumps({"agent_slug": _SCOUT_AGENT_SLUG})
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
                        run_id,
                        provider,
                        model,
                        status,
                        "today_market_pulse",
                        cache_key,
                        fallback_used,
                        input_tokens,
                        output_tokens,
                        reasoning_tokens,
                        source_count,
                        error_detail,
                        payload,
                        started_at,
                        completed_at,
                    ],
                )
                conn.commit()
        except Exception as exc:
            logger.warning("market_pulse_research_run_log_failed", error=str(exc))

    def _upsert_source_profiles(self, sources: list[dict[str, Any]]) -> None:
        now = datetime.now(UTC)
        try:
            with self.storage.connection() as conn:
                for source in sources:
                    metadata = json.dumps(
                        {"latest_label": source["label"], "latest_kind": source["kind"]}
                    )
                    conn.execute(
                        """
                        INSERT INTO market_pulse_source_profiles (
                            id,
                            url,
                            domain,
                            label,
                            source_kind,
                            source_signal_tier,
                            decision_value_score,
                            validation_status,
                            last_seen_at,
                            last_validated_at,
                            metadata,
                            created_at,
                            updated_at
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s
                        )
                        ON CONFLICT (url) DO UPDATE SET
                            label = EXCLUDED.label,
                            source_kind = EXCLUDED.source_kind,
                            source_signal_tier = EXCLUDED.source_signal_tier,
                            decision_value_score = EXCLUDED.decision_value_score,
                            validation_status = EXCLUDED.validation_status,
                            last_seen_at = EXCLUDED.last_seen_at,
                            last_validated_at = EXCLUDED.last_validated_at,
                            metadata = market_pulse_source_profiles.metadata || EXCLUDED.metadata,
                            updated_at = EXCLUDED.updated_at
                        """,
                        [
                            str(uuid.uuid4()),
                            source["url"],
                            _normalize_domain(str(source["url"])),
                            source["label"],
                            source["kind"],
                            source["source_signal_tier"],
                            source["decision_value_score"],
                            "validated",
                            now,
                            now,
                            metadata,
                            now,
                            now,
                        ],
                    )
                conn.commit()
        except Exception as exc:
            logger.warning("market_pulse_source_profile_upsert_failed", error=str(exc))
