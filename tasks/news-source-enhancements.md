# Task List: News Source Enhancements

**Status**: In Progress
**Updated**: 2025-11-06

---

## Summary

Scope covers extending the news ingestion pipeline beyond the current Google News + FinBERT setup. Key deliverables: configurable lookback windows, multi-vendor aggregation, documentation/validation of provider capabilities, Yahoo Finance prototype, and FinNews RSS evaluation.

---

## Tasks

- [x] 1. Add user-configurable news lookback window
  - [x] 1.1 Persist lookback preference (e.g., enum `6h/12h/24h/48h`) in existing preferences storage and expose via `/settings` UX.
  - [x] 1.2 Update `NewsService` TTL/window selection logic plus Celery refresh task to use preference-driven recency cut-off.
  - [x] 1.3 Surface chosen window + effective TTL in News Health card and API responses (`/api/news/health`).
  - Notes: ensure defaults remain backward compatible (current 6h TTL) and migration handles missing prefs. **Completed:** Migration `011_news_lookback_preference.sql` adds `news_lookback_hours` defaulting to 6; settings UI now exposes a radio group (6/12/24/48h) and News Health card reports the active window.

- [x] 2. Integrate secondary vendors (Polygon, Finnhub, FMP)
  - [x] 2.1 Define news-capable source classes (`PolygonNewsSource`, `FinnhubNewsSource`, `FMPNewsSource`) that wrap existing REST helpers, emitting a normalized article payload (headline, url, published_at, source, summary).
        - ✅ Polygon `fetch_news_payload` implemented in `PolygonSource`; ✅ Finnhub/FMP adapters now emit normalized frames with publisher + ticker metadata.
  - [x] 2.2 Introduce a `NewsMultiSourceFetcher` utility (leveraging `MultiSourceFetcher`) that loads enabled sources from `config/sources/*.yaml`, enforces rate-limit cooldowns, and records source metrics in `source_performance`.
        - ✅ NewsService bootstraps `MultiSourceFetcher` with enabled vendor adapters; runtime stats stored via existing fetcher metrics.
  - [x] 2.3 Extend `NewsService` with pluggable vendor aggregation: fetch in priority order, merge articles (content-hash/title dedupe, prefer freshest), annotate `raw["vendor"]`, and fall back to Google News when vendors fail.
        - ✅ Vendor + Google articles merged with hashing/backfill logic; `raw['vendor']` persisted for downstream heuristics.
  - [x] 2.4 Surface per-vendor toggles/env checks (e.g., `POLYGON_NEWS_ENABLED`) and expose vendor status in `/api/news/health` for observability.
        - ✅ Env toggles: `POLYGON_NEWS_ENABLED`, `FINNHUB_NEWS_ENABLED`, `FMP_NEWS_ENABLED` (FMP default-off pending paid plan); health payload now reports per-vendor status, last success/error, and article counts.
  - Notes: document rate-limit handling, shared retry/backoff utilities, and ensure adapters share the existing `rest_api_source` auth helpers where possible. **Follow-up:** expand docs with enablement steps + compliance guidance (Task 3).

- [x] 3. Audit existing source configurations + compliance
  - [x] 3.1 Inventory current config entries (polygon/finnhub/newsapi/google news) and verify credential/env mappings.
        - ✅ Reviewed `config/sources/*.yaml` (Polygon, Finnhub, FMP, Google News, NewsAPI, YFinance) and documented env keys + rate limits; confirmed `POLYGON_NEWS_ENABLED`, `FINNHUB_NEWS_ENABLED`, `FMP_NEWS_ENABLED`, `YFINANCE_NEWS_ENABLED`, RSS toggles now control runtime registration.
  - [x] 3.2 Research free-tier/legal allowances for distributing news content; capture findings with references.
        - ✅ Captured licensing/rate notes per vendor in `docs/core/NEWS_FEEDS.md` (e.g., FMP lacks free news, Seeking Alpha limited to personal use, Google/Yahoo require attribution).
  - [x] 3.3 Update docs (e.g., `docs/core/NEWS_FEEDS.md`) with enablement steps, caveats, or alternate feeds where direct news unavailable.
        - ✅ Added NEWS_FEEDS doc covering env toggles, compliance, and optional vendors.
  - Notes: initial review indicates Polygon (`config/sources/polygon.yaml`) exposes `/v2/reference/news` with publisher metadata; Finnhub (`config/sources/finnhub.yaml`) expects `/company-news` payloads; FMP free tier does **not** include news (config marks `news: false`) and likely needs alternate feed or paid plan—document these constraints.

- [x] 4. Prototype Yahoo Finance ticker feed
  - [x] 4.1 Spike `yfinance.Ticker.get_news()` ingestion for per-ticker headlines; measure response latency and rate limits.
  - [x] 4.2 Wrap in adapter with unit/integration tests ensuring sentiment pipeline compatibility.
  - [x] 4.3 Confirm licensing terms for redistribution; document constraints and config toggle.
  - Notes: evaluate fallback behaviour when API throttles or returns empty payloads.

- [x] 5. Evaluate FinNews RSS aggregator
  - [x] 5.1 Review MIT-licensed `philipperemy/fin-news` feeds for coverage (CNBC, Seeking Alpha, WSJ, etc.) and caching requirements.
  - [x] 5.2 Prototype ingestion & caching strategy (Redis/db) with rate-limit safeguards.
  - [x] 5.3 Produce integration plan outlining how FinNews complements other vendors (priority, dedupe, attribution).
  - Notes: FinNews repo proved unmaintained (last update 2020) with hardcoded feeds; instead we built first-party RSS adapters (Task 10) covering CNBC, MarketWatch, Nasdaq, Fortune, Investing.com, FT, and Seeking Alpha.

- [x] 6. UI: Surface vendor + publisher context on News surfaces
  - [x] 6.1 Update `/app/news` article list to render both the upstream vendor (Polygon/Finnhub/FMP/Google/Yahoo) and the publisher attribution, even when both strings differ.
        - ✅ Vendor badges now reflect the actual data source (e.g., Google News vs. YFinance) and sit alongside publisher text; copy sanitized to handle long names.
  - [x] 6.2 Mirror the same treatment inside watchlist expanded rows (`News & Sentiment` block) including stacked badges for vendor + publisher.
        - ✅ Watchlist snapshots now store vendor/publisher metadata via `build_recent_news_payload`; expanded rows show badges for every ticker news card.
  - [x] 6.3 Capture refreshed screenshots (`docs/screenshots/news/…`) demonstrating both market-level and watchlist-level displays after the change.
        - ✅ Saved `docs/screenshots/news/news-multi-vendor-ui-20251106.png` and `docs/screenshots/news/watchlist-vendor-badges-20251106.png` after manual verification.

- [ ] 7. Implement next news data source (Yahoo Finance prototype)
  - [x] 7.1 Add `YahooNewsSource` adapter leveraging `yfinance.Ticker.get_news()` with rate-limit/backoff helpers.
  - [x] 7.2 Wire source into `MultiSourceFetcher` + config toggles (`YFINANCE_NEWS_ENABLED`) and document required env setup.
  - [x] 7.3 Extend sentiment pipeline tests to cover Yahoo payload normalization + dedupe.

- [x] 8. UI Verification Task (News surfaces)
  - [x] 8.1 Manual QA checklist: confirmed vendor + publisher badges render for Market + Watchlist views (tested with Google News + YFinance articles after forcing cache refresh).
  - [x] 8.2 Snapshot/visual diff: captured updated screenshots (`docs/screenshots/news/news-multi-vendor-ui-20251106.png`, `docs/screenshots/news/watchlist-vendor-badges-20251106.png`).
  - [x] 8.3 Final validation: manually loaded `/news` and `/watchlist` (post-refresh) to ensure real data renders without console errors and badges match API payloads.

- [x] 9. Make max headlines per ticker configurable
  - [x] 9.1 Add a Settings UI control (probably next to news lookback) letting users choose the max number of headlines per ticker/bundle (options 5/10/15/20 or numeric input).
        - ✅ Watchlist Preferences now exposes a “Max Headlines Per Ticker” radio group (5/10/15/20) wired to the preferences mutation.
  - [x] 9.2 Persist preference in `user_preferences` (new column `news_max_articles` with sensible default, migration + API).
        - ✅ Migration `012_news_max_articles_preference.sql` adds the column (default 10); `/api/preferences` request/response + validators updated.
- [x] 9.3 Update backend (`NewsService`, Celery refresh, agents) to use the stored value when fetching both market and per-symbol news.
        - ✅ `NewsService.refresh_max_articles_from_preferences()` now feeds API routes, Celery tasks, watchlist refresh, and agent tools.
  - [x] 9.4 Extend verification docs and tests to cover the new setting and ensure watchdog tasks respect it.
        - ✅ Added unit test (`test_refresh_max_articles_from_preferences`) and wired logs/health output to reflect the new preference.
- [x] 10. Integrate & monitor supplemental RSS vendors (free tier)
  - [x] 10.1 Add CNBC Finance/Earnings RSS feeds (require custom `User-Agent`) via new RSS adapter, cache results ~30m.
  - [x] 10.2 Add MarketWatch Top Stories + Real-Time feeds; normalize publisher metadata and enforce dedupe with API vendors.
  - [x] 10.3 Add Nasdaq Original + ticker RSS endpoints for U.S. equity coverage; expose toggle in source config.
  - [x] 10.4 Add Fortune business feed and Investing.com Market Overview RSS for macro context; log rate limits.
  - [x] 10.5 Add Financial Times RSS (with attribution text) and evaluate Seeking Alpha RSS legality; only ingest if compliance ok.
  - [x] 10.6 Update source health reporting/tests to tag new RSS vendors and capture fetch latency + last success/error timestamps.
        - ✅ `rss_source.py` introduces dedicated adapters (CNBC, MarketWatch, Nasdaq, Fortune, Investing.com, FT, Seeking Alpha) with env toggles and vendor registration so `/api/news/health` reports them.

---

## Follow-up / Tracking

- Coordinate with settings UX for lookback selector assets.
- Update QA checklist once new vendors integrated (news health verification needs additional scenarios).
