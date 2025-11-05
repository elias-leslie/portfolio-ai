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
  - [ ] 2.1 Implement adapters under `app/sources/...` respecting provider SDKs/REST endpoints for news.
  - [ ] 2.2 Add feature toggles + graceful fallback logic in `NewsService` so Google News remains baseline if vendor unavailable.
  - [ ] 2.3 Extend aggregation pipeline to de-duplicate content across vendors (hash/title dedupe) and tag `sentiment.model` source metadata.
  - Notes: document rate-limit handling and ensure adapters share retry/backoff utilities.

- [ ] 3. Audit existing source configurations + compliance
  - [ ] 3.1 Inventory current config entries (polygon/finnhub/newsapi/google news) and verify credential/env mappings.
  - [ ] 3.2 Research free-tier/legal allowances for distributing news content; capture findings with references.
  - [ ] 3.3 Update docs (e.g., `docs/core/NEWS_FEEDS.md`) with enablement steps, caveats, or alternate feeds where direct news unavailable.
  - Notes: include gap analysis for sources lacking native news and recommend next actions.

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
