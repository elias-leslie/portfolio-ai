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
  - [x] 2.1 Define news-capable source classes (`PolygonNewsSource`, `FinnhubNewsSource`, `FMPNewsSource`) that wrap existing REST helpers, emitting a normalized article payload (headline, url, published_at, source, summary).
        - ✅ Polygon `fetch_news_payload` implemented in `PolygonSource`; ✅ Finnhub/FMP adapters now emit normalized frames with publisher + ticker metadata.
  - [x] 2.2 Introduce a `NewsMultiSourceFetcher` utility (leveraging `MultiSourceFetcher`) that loads enabled sources from `config/sources/*.yaml`, enforces rate-limit cooldowns, and records source metrics in `source_performance`.
        - ✅ NewsService bootstraps `MultiSourceFetcher` with enabled vendor adapters; runtime stats stored via existing fetcher metrics.
  - [x] 2.3 Extend `NewsService` with pluggable vendor aggregation: fetch in priority order, merge articles (content-hash/title dedupe, prefer freshest), annotate `raw["vendor"]`, and fall back to Google News when vendors fail.
        - ✅ Vendor + Google articles merged with hashing/backfill logic; `raw['vendor']` persisted for downstream heuristics.
  - [x] 2.4 Surface per-vendor toggles/env checks (e.g., `POLYGON_NEWS_ENABLED`) and expose vendor status in `/api/news/health` for observability.
        - ✅ Env toggles: `POLYGON_NEWS_ENABLED`, `FINNHUB_NEWS_ENABLED`, `FMP_NEWS_ENABLED` (FMP default-off pending paid plan); health payload now reports per-vendor status, last success/error, and article counts.
  - Notes: document rate-limit handling, shared retry/backoff utilities, and ensure adapters share the existing `rest_api_source` auth helpers where possible. **Follow-up:** expand docs with enablement steps + compliance guidance (Task 3).

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

- [ ] 6. UI: Surface vendor + publisher context on News surfaces
  - [ ] 6.1 Update `/app/news` article list to render both the upstream vendor (Polygon/Finnhub/FMP/Google) and the publisher attribution, even when both strings differ.
        - Ensure layout works for long publisher names; add regression tests/storybook notes.
  - [ ] 6.2 Mirror the same treatment inside watchlist expanded rows (`News & Sentiment` block) including stacked badges for vendor + publisher.
  - [ ] 6.3 Capture refreshed screenshots (`docs/screenshots/news/…`) demonstrating both market-level and watchlist-level displays after the change.

- [ ] 7. Implement next news data source (Yahoo Finance prototype)
  - [ ] 7.1 Add `YahooNewsSource` adapter leveraging `yfinance.Ticker.get_news()` with rate-limit/backoff helpers.
  - [ ] 7.2 Wire source into `MultiSourceFetcher` + config toggles (`YFINANCE_NEWS_ENABLED`) and document required env setup.
  - [ ] 7.3 Extend sentiment pipeline tests to cover Yahoo payload normalization + dedupe.

- [ ] 8. UI Verification Task (News surfaces)
  - [ ] 8.1 Manual QA checklist: confirm vendor + publisher badges render for Market + Watchlist views, including fallback when vendor === publisher.
  - [ ] 8.2 Snapshot/visual diff: capture updated screenshots and store under `docs/screenshots/news/...`.
  - [ ] 8.3 Final validation step on every news-related change: load `/news` and `/watchlist` before sign-off to ensure real data renders without console errors.

- [ ] 9. Make max headlines per ticker configurable
  - [ ] 9.1 Add a Settings UI control (probably next to news lookback) letting users choose the max number of headlines per ticker/bundle (options 5/10/15/20 or numeric input).
  - [ ] 9.2 Persist preference in `user_preferences` (new column `news_max_articles` with sensible default, migration + API).
  - [ ] 9.3 Update backend (`NewsService`, Celery refresh, agents) to use the stored value when fetching both market and per-symbol news.
  - [ ] 9.4 Extend verification docs and tests to cover the new setting and ensure watchdog tasks respect it.

---

## Follow-up / Tracking

- Coordinate with settings UX for lookback selector assets.
- Update QA checklist once new vendors integrated (news health verification needs additional scenarios).
