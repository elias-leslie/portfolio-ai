# Task List: Watchlist + Market News Surface

**PRD**: (Conversation summary – formal PRD pending)
**Status**: In Progress
**Completion**: 80%
**Effort**: Medium
**Updated**: 2025-11-04

---

## Summary

**✅ COMPLETE:** Tasks 1.0–1.8, 2.1–2.6, 3.1–3.7, 4.1–4.3, 5.4–5.5
**🔄 IN PROGRESS:** Task 5.1 (news pytest fixed; broader suite pending DB cleanup), 5.2–5.3
**⚠️ NEXT:** Ensure automated/QA verification once test DB is reachable

---

## Relevant Files

### Create (4 files)
- `backend/app/services/news_service.py` (~180 lines) – shared news cache + sentiment accessors
- `backend/app/api/news.py` (~200 lines) – REST routes for market + watchlist news feeds
- `frontend/app/news/page.tsx` (~220 lines) – News hub with toggle and expandable rows
- `frontend/lib/api/news.ts` (~140 lines) – REST client + hooks for market/watchlist news

### Update (15 files)
- `backend/app/watchlist/watchlist_service.py`
- `backend/app/watchlist/response_builders.py`
- `backend/app/api/watchlist.py`
- `backend/app/celery_app.py`
- `backend/app/tasks/watchlist_tasks.py`
- `backend/app/tasks/news_tasks.py`
- `backend/app/agents/tools.py`
- `backend/app/storage/queries.py`
- `frontend/components/Navigation.tsx`
- `frontend/components/watchlist/ExpandedRow.tsx`
- `frontend/components/watchlist/WatchlistTable.tsx`
- `frontend/components/settings/WatchlistPreferences.tsx`
- `frontend/lib/api/watchlist.ts`
- `frontend/lib/hooks/useNews.ts`
- `docs/core/REFRESH_ARCHITECTURE.md`
- `docs/core/ROADMAP.md`

### Notes
- Tests: `pytest backend/tests/` *(requires Postgres test DB online)* | `npm test --frontend` | `mypy backend/app --strict`
- Scripts: `bash ~/.claude/skills/code-quality/scripts/quality-report.sh backend/app`

---

## Tasks

- [x] 1.0 Backend news service & API exposure
  - [x] 1.1 Run pre-implementation check (see ~/.claude/subagents/pre-check.md)
        - Verify existing news caching + sentiment patterns
        - Confirm API payload gaps (`news_sentiment_score`, `recent_news_headlines`)
  - [x] 1.2 Implement shared `NewsService` wrapping `fetch_news_headlines_cached`, exposing market + ticker batch helpers
  - [x] 1.3 Refactor `AgentTools.execute_get_news` (and any other direct Google News usage) to delegate to `NewsService`
  - [x] 1.4 Update watchlist query + response builders + serializers so API returns `news_sentiment_score` and `recent_news_headlines`
  - [x] 1.5 Add `/api/news/market` and `/api/news/watchlist` endpoints returning structured headlines with sentiment + metadata
  - [x] 1.6 Add API contract tests (or snapshot assertions) ensuring watchlist list/detail responses include populated news fields once service is wired
  - [x] 1.7 Integrate FinBERT headline scoring (fall back to VADER on failures), centralize inference in `NewsService`
  - [x] 1.8 Add aggregated sentiment helpers (recency-weighted composite, positive/neutral/negative counts, top headline excerpts) using FinBERT outputs

- [x] 2.0 Storage alignment & refresh scheduling
  - [x] 2.1 Discover scope using Explore subagent
        - Pattern: `reference_cache` vs `news_cache` usage for news payloads
        - Expected: catalogue all write/read sites before migration
  - [x] 2.2 Decide storage target (document choice) and adjust loaders accordingly
  - [x] 2.3 Re-enable Celery `refresh-news-sentiment` beat task (or equivalent) honoring preference hierarchy, recording last refresh
  - [x] 2.4 Ensure worker + service logic respects `news_refresh_override`, cache TTL guardrails, and logs skips/failures consistently
  - [x] 2.5 Update storage/migrations or configuration docs if schema target changes
  - [x] 2.6 Define FinBERT deployment (local model vs API), package weights/config, and update dependency management

- [x] 3.0 Frontend news experience
  - [x] 3.1 Scaffold `/news` route with layout + toggle (market vs watchlist), server data fetching, loading states
  - [x] 3.2 Implement `frontend/lib/api/news.ts` hooks for new endpoints (market + watchlist) using our existing React Query utilities
  - [x] 3.3 Build expandable headline list components showing sentiment badges, source, timestamp, description
  - [x] 3.4 Surface per-ticker headlines within watchlist `ExpandedRow`, wiring to new response fields and asserting UI renders sentiment + links
  - [x] 3.5 Update navigation and any quick links to include the News page
  - [x] 3.6 Display aggregated sentiment summary (score + badges + change vs previous refresh) for market and watchlist views to support rapid trade decisions
  - [x] 3.7 Surface FinBERT vs fallback indicator in UI (tooltip/badge) to flag confidence level

- [x] 4.0 Preferences & feature controls
  - [x] 4.1 Surface `watchlist_show_news` toggle and both configured vs effective news refresh cadence in settings UI (with validation)
  - [x] 4.2 Persist preference updates through API (validate backend fields, seed defaults if missing)
  - [x] 4.3 Update docs (`docs/core/REFRESH_ARCHITECTURE.md`) describing news refresh flow

- [ ] 5.0 Validation & documentation
  - [ ] 5.1 Generate comprehensive tests (auto-dispatched by TestGen)
        - Cover news service caching, FinBERT scoring (with fixtures), API responses, frontend hooks
        - 2025-11-04: news fixtures updated to use recent publish timestamps + unique headlines; `pytest tests/watchlist/test_news.py -vv -s` ✅ (requires db migrations up to 010)
        - Remaining blockers: test schema cleanup (`news_summary_log`) still missing in local DB; full suite awaits migration + QA env
  - [ ] 5.2 Quality check before commit (0-context)
        - Run: `bash ~/.claude/skills/code-quality/scripts/quality-report.sh backend/app`
  - [ ] 5.3 Manual QA checklist (API smoke, UI toggle, preference persistence)
  - [x] 5.4 Establish baseline evaluation: log aggregated sentiment metrics alongside subsequent price moves to seed future backtests
  - [x] 5.5 Document forward roadmap (news + fundamentals + technicals + strategy engine) and LLM reviewer role in `docs/core/ROADMAP.md`

---

## Follow-up Actions
- [ ] Apply migration `010_news_cache_rebuild.sql` in all environments (includes `news_summary_log`)
- [ ] Install new dependencies (`transformers`, `torch`, `huggingface-hub`, `tokenizers`) in production docker/venv images
- [ ] Seed FinBERT model weights on deployment target (document location & cache strategy)
- [ ] Once Postgres test DB accessible, rerun `pytest tests/watchlist/test_news.py tests/test_api_preferences.py`
- [ ] Execute manual QA checklist (market/watchlist news pages, preferences toggle, agent news tool) and capture screenshots
- [ ] Run code-quality script prior to final commit
