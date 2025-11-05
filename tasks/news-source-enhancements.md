# Task List: News Source Enhancements

**Status**: Not Started
**Updated**: 2025-11-05

---

## Summary

Scope covers extending the news ingestion pipeline beyond the current Google News + FinBERT setup. Key deliverables: configurable lookback windows, multi-vendor aggregation, documentation/validation of provider capabilities, Yahoo Finance prototype, and FinNews RSS evaluation.

---

## Tasks

- [ ] 1. Add user-configurable news lookback window
  - [x] 1.1 Persist lookback preference (e.g., enum `6h/12h/24h/48h`) in existing preferences storage and expose via `/settings` UX.
  - [x] 1.2 Update `NewsService` TTL/window selection logic plus Celery refresh task to use preference-driven recency cut-off.
  - [x] 1.3 Surface chosen window + effective TTL in News Health card and API responses (`/api/news/health`).
  - Notes: ensure defaults remain backward compatible (current 6h TTL) and migration handles missing prefs. **Completed:** Migration `011_news_lookback_preference.sql` adds `news_lookback_hours` defaulting to 6; settings UI now exposes a radio group (6/12/24/48h) and News Health card reports the active window.

- [ ] 2. Integrate secondary vendors (Polygon, Finnhub, FMP)
  - [ ] 2.1 Define news-capable source classes (`PolygonNewsSource`, `FinnhubNewsSource`, `FMPNewsSource`) that wrap existing REST helpers, emitting a normalized article payload (headline, url, published_at, source, summary).
  - [ ] 2.2 Introduce a `NewsMultiSourceFetcher` utility (leveraging `MultiSourceFetcher`) that loads enabled sources from `config/sources/*.yaml`, enforces rate-limit cooldowns, and records source metrics in `source_performance`.
  - [ ] 2.3 Extend `NewsService` with pluggable vendor aggregation: fetch in priority order, merge articles (content-hash/title dedupe, prefer freshest), annotate `raw["vendor"]`, and fall back to Google News when vendors fail.
  - [ ] 2.4 Surface per-vendor toggles/env checks (e.g., `POLYGON_NEWS_ENABLED`) and expose vendor status in `/api/news/health` for observability.
  - Notes: document rate-limit handling, shared retry/backoff utilities, and ensure adapters share the existing `rest_api_source` auth helpers where possible.

- [ ] 3. Audit existing source configurations + compliance
  - [ ] 3.1 Inventory current config entries (polygon/finnhub/newsapi/google news) and verify credential/env mappings.
  - [ ] 3.2 Research free-tier/legal allowances for distributing news content; capture findings with references.
  - [ ] 3.3 Update docs (e.g., `docs/core/NEWS_FEEDS.md`) with enablement steps, caveats, or alternate feeds where direct news unavailable.
  - Notes: initial review indicates Polygon (`config/sources/polygon.yaml`) exposes `/v2/reference/news` with publisher metadata; Finnhub (`config/sources/finnhub.yaml`) expects `/company-news` payloads; FMP free tier does **not** include news (config marks `news: false`) and likely needs alternate feed or paid plan—document these constraints.

- [ ] 4. Prototype Yahoo Finance ticker feed
  - [ ] 4.1 Spike `yfinance.Ticker.get_news()` ingestion for per-ticker headlines; measure response latency and rate limits.
  - [ ] 4.2 Wrap in adapter with unit/integration tests ensuring sentiment pipeline compatibility.
  - [ ] 4.3 Confirm licensing terms for redistribution; document constraints and config toggle.
  - Notes: evaluate fallback behaviour when API throttles or returns empty payloads.

- [ ] 5. Evaluate FinNews RSS aggregator
  - [ ] 5.1 Review MIT-licensed `philipperemy/fin-news` feeds for coverage (CNBC, Seeking Alpha, WSJ, etc.) and caching requirements.
  - [ ] 5.2 Prototype ingestion & caching strategy (Redis/db) with rate-limit safeguards.
  - [ ] 5.3 Produce integration plan outlining how FinNews complements other vendors (priority, dedupe, attribution).
  - Notes: track RSS latency versus TTL and define monitoring hooks.

---

## Follow-up / Tracking

- Coordinate with settings UX for lookback selector assets.
- Update QA checklist once new vendors integrated (news health verification needs additional scenarios).
