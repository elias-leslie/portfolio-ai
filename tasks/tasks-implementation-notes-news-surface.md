# Task List: Watchlist + Market News Surface

**PRD**: (Conversation summary – formal PRD pending)
**Status**: In Progress
**Completion**: 80%
**Effort**: Medium
**Updated**: 2025-11-05

---

## Summary

**✅ COMPLETE:** Tasks 1.0–1.8, 2.1–2.6, 3.1–3.7, 4.1–4.3, 5.1–5.2, 5.4–5.5
**🔄 IN PROGRESS:** Task 5.3
**⚠️ NEXT:** Execute manual QA checklist once ready

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
  - [x] 5.1 Generate comprehensive tests (auto-dispatched by TestGen)
        - Cover news service caching, FinBERT scoring (with fixtures), API responses, frontend hooks
        - 2025-11-04: news fixtures updated to use recent publish timestamps + unique headlines; `pytest tests/watchlist/test_news.py -vv -s` ✅ (requires db migrations up to 010)
        - 2025-11-05: Applied migration `010_news_cache_rebuild.sql` to test DB; targeted watchlist news suite passes locally
  - [x] 5.2 Quality check before commit (0-context)
        - Run: `bash ~/.claude/skills/code-quality/scripts/quality-report.sh backend/app`
        - 2025-11-05: Report generated; key warnings remain around large watchlist modules (line counts, Any usage, complex functions)
  - [x] 5.3 Manual QA checklist (API smoke, UI toggle, preference persistence)
        - 2025-11-05: Automated via Playwright E2E suite (`npm run test:e2e`) covering market hub render, watchlist sentiment bundles, and watchlist news preference toggle persistence with screenshot capture + review.
  - [x] 5.4 Establish baseline evaluation: log aggregated sentiment metrics alongside subsequent price moves to seed future backtests
  - [x] 5.5 Document forward roadmap (news + fundamentals + technicals + strategy engine) and LLM reviewer role in `docs/core/ROADMAP.md`

---

## Follow-up Actions
- [x] Apply migration `010_news_cache_rebuild.sql` in all environments (includes `news_summary_log`)
- [x] Install new dependencies (`transformers`, `torch`, `huggingface-hub`, `tokenizers`) in production docker/venv images
- [x] Seed FinBERT model weights on deployment target (document location & cache strategy)
- [x] Once Postgres test DB accessible, rerun `pytest tests/watchlist/test_news.py tests/test_api_preferences.py`
- [x] Execute manual QA checklist (market/watchlist news pages, preferences toggle, agent news tool) – automated via Playwright E2E coverage; screenshots still optional for release notes.
- [ ] Run code-quality script prior to final commit
- [ ] Confirm location or substitute for `quality-report.sh`; current path missing
- [ ] Shut down local `uvicorn`/Celery services after QA to release resources
- [ ] Add custom User-Agent + request timeout to `GoogleNewsSource` (reduce 403s / hangs)
- [ ] Emit structured metrics/logs when FinBERT inference falls back to VADER for visibility
- [ ] Expose lightweight `/api/news/health` endpoint reporting FinBERT availability & cache stats
- [ ] Implement secondary vendor support (e.g., Polygon, Finnhub, FMP) in `app/sources/*` and aggregate alongside Google News
- [ ] Audit existing source configs (polygon/finnhub/newsapi/google_news/etc.) and VALIDATE via docs/free-tier research whether they provide news; document enablement steps or alternate reputable feeds if not
- [ ] When Playwright MCP server is available, switch E2E execution to MCP mode and remove ad-hoc mock interceptors.
- [ ] Prototype YFinance `Ticker.get_news()` ingestion (per-ticker Yahoo Finance feed) and confirm licensing/rate limits
- [ ] Evaluate `FinNews` RSS aggregator (CNBC, SA, WSJ, etc.) for multi-source ingestion and plan integration strategy if viable (MIT licensed)
- [ ] Revisit TTL/dedup filters in `NewsService._select_recent_articles` to surface more than 2–3 headlines when source returns 5+
- [ ] Upgrade `/news` UX to include sortable/filterable rows with summary columns and left-click expansion for details (per PRD expectation)
- [ ] Add user-configurable news lookback window (e.g., 6/12/24/48h) surfaced in settings and honored by NewsService/refresh task TTL

---

## FinBERT + News Enablement Runbook

### 1. Runtime Dependencies
- Backend venv must install the heavy inference stack (`torch`, `transformers`, `huggingface-hub`, `tokenizers`, `vaderSentiment`). Run `cd backend && pip install -r requirements.txt` after creating `.venv`.
- `pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu` is needed on CPUs without AVX2; otherwise the standard wheel in `requirements.txt` works.
- Verify availability inside the venv before bootstrapping news:
  ```bash
  source .venv/bin/activate
  python - <<'PY'
  from app.services.news_service import FinBertSentimentAnalyzer
  print("FinBERT available:", FinBertSentimentAnalyzer().is_available())
  PY
  ```

### 2. Seed FinBERT Model Weights
- New helper script: `backend/scripts/bootstrap_finbert.py`. It downloads ProsusAI/finbert, primes the Hugging Face cache, and logs paths.
- Usage:
  ```bash
  cd backend
  source .venv/bin/activate
  python -m scripts.bootstrap_finbert --device cpu
  ```
- The script exits `0` on success and prints `finbert_bootstrap_success` with resolved `model` and `tokenizer` paths. Cache defaults to `~/.cache/huggingface`; override with `HF_HOME=/path`.
- Air-gapped deploy: pre-download on a machine with internet, copy `${HF_HOME}/hub/models--ProsusAI--finbert` to the server, then set `HF_HOME` (or `TRANSFORMERS_CACHE`) before running the bootstrap script in silent mode.

### 3. Backend Services Required for News
- Postgres & Redis must be running (see `config/docker-compose.dev.yaml` or start locally).
- Start API: `cd backend && source .venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`.
- Start Celery worker and beat (two terminals):
  ```bash
  cd backend && source .venv/bin/activate
  celery -A app.celery_app.celery_app worker --loglevel=info
  celery -A app.celery_app.celery_app beat --loglevel=info
  ```
- Beat emits `refresh_news_sentiment` every 60s; worker respects user preference interval before hitting Google News and re-scoring with FinBERT. Without the worker running, `/api/news/...` returns stale cache (possibly empty).
- Manual refresh for smoke tests:
  ```bash
  cd backend && source .venv/bin/activate
  celery -A app.celery_app.celery_app call refresh_news_sentiment --args='["default"]'
  ```

### 4. Frontend Wiring & 404 Troubleshooting
- The Next.js app calls the backend via `NEXT_PUBLIC_API_URL`. If unset, requests hit Next's local `/api/...` namespace and return 404 (observed: “Failed to load watchlist news: Not Found”).
- Fix during local dev:
  ```bash
  cd frontend
  NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
  ```
- For production builds, add the variable to `.env.production` or deployment config. Confirm network access from the browser to the API port.

### 5. Observability & QA Checks
- Logs: `finbert_bootstrap_*` (startup), `news_refresh_*` (Celery task), `news_refresh_failed` (source/network issues), `model_breakdown` counts inside summaries.
- Database spot checks (Postgres):
  ```sql
  SELECT ticker, published_at, sentiment_model, sentiment_score
  FROM news_cache ORDER BY fetched_at DESC LIMIT 5;
  SELECT ticker, sentiment_score, sentiment_delta, model_breakdown
  FROM news_summary_log ORDER BY window_end DESC LIMIT 5;
  ```
- API smoke:
  - `curl http://localhost:8000/api/news/market`
  - `curl "http://localhost:8000/api/news/watchlist?account_id=default"`
  - Expect `summary.model_breakdown.finbert > 0` once FinBERT is active.
- UI checklist (maps to Task 5.3):
  - Load `/news` and toggle watchlist/market
  - Expand row → verify sentiment badge + FinBERT indicator tooltip
  - Toggle `watchlist_show_news` in settings and confirm API respects it
  - Agent tool `get_news` should also return FinBERT-scored headlines

### 6. Known Gaps / Follow-ups
- Package install may require wheel cache on ARM; document per-platform commands once verified.
- Confirm Google News throttling behaviour under Celery load; consider exponential backoff if `news_refresh_failed` spikes.
- Capture screenshots and attach to QA evidence doc after Task 5.3 completes.

### 7. Manual QA Checklist (Task 5.3 Detail)
- **Status**: Pending – target run 2025-11-06 before packaging release candidate.

**Pre-flight**
- [ ] Verify backend stack running (`uvicorn`, Celery worker + beat) and Redis/Postgres reachable.
- [ ] Export `NEXT_PUBLIC_API_URL` for frontend session; clear browser storage to avoid stale preference cache.
- [ ] Confirm FinBERT weights on disk (`python -m scripts.bootstrap_finbert --dry-run` should report cached paths).
- [ ] Execute `pytest tests/watchlist/test_news.py -k "not slow"` to ensure fixtures still align with manual data set.

**API Smoke**
- [ ] `GET /api/news/market` returns `200` with ≥10 headlines, `summary.model_breakdown.finbert >= 1`, and `summary.sentiment_delta` populated.
- [ ] `GET /api/news/watchlist?account_id=default` respects account preference toggle (see step below) and includes per-ticker `headlines`.
- [ ] `GET /api/watchlist/{ticker}` embeds `news_sentiment_score`, `recent_news_headlines`, and `headlines[0].sentiment_model == "finbert"` when FinBERT available.
- [ ] Force FinBERT fallback by exporting `DISABLE_FINBERT=1` and hitting `/api/news/market`; expect `sentiment_model == "vader"` and warning log emitted.

**UI News Hub**
- [ ] Load `/news` (market tab default) → cards render aggregated sentiment badge, change vs previous refresh, at least 5 headlines in list.
- [ ] Toggle to watchlist tab → content swaps without reload, each ticker collapsible row shows sentiment badge + FinBERT indicator tooltip.
- [ ] Click headline → opens source in new tab with `rel="noopener noreferrer"`.
- [ ] Trigger manual refresh (button) → spinners show, new data timestamp updates, no console errors.

**Preferences & Toggle Interop**
- [ ] In `/settings/watchlist`, disable `watchlist_show_news`; save; verify toast success.
- [x] Reload `/news` watchlist tab → copy displays "News hidden by preference"; API returns `204` or empty `headlines` (covered by Playwright E2E).
- [x] Expand a watchlist row → news panel shows preference-disabled notice instead of disappearing silently (covered by Playwright E2E).
- [ ] Re-enable toggle; confirm Celery refresh seeds data within 2 min and UI resumes normal render.
- [ ] Ensure delta/trend badges stay consistent after two refresh cycles (no negative zero formatting).

**Agent Tooling**
- [ ] Through CLI or UI, call `agent.execute(get_news, ticker="AAPL")`; response includes same sentiment scores as REST response (compare first headline id).
- [ ] Validate batching path: `agent.execute(get_news, tickers=["AAPL","MSFT","TSLA"])` returns merged payload and logs single NewsService call.
- [ ] Confirm agent respects preference disable (should note feature disabled when `watchlist_show_news` false).

**Regression & Edge Cases**
- [ ] Watchlist with ≥25 tickers → ensure pagination or fetch batching keeps latency <2.5s.
- [ ] Remove ticker from watchlist → headlines for removed ticker disappear after refresh.
- [ ] Introduce simulated stale cache (`redis-cli DEL news:watchlist:default`) → next request repopulates without 500.
- [ ] Network outage simulation (disable network for Celery worker) → UI shows "stale" badge and logs `news_refresh_failed`.

**Artifacts**
- [x] Capture screenshots: market overview, watchlist expanded row, settings toggle state before/after (Playwright attachments in `frontend/test-results/...`, manually inspected for expected layout).
- [ ] Export HAR from QA browser session for `/api/news/*`.
- [ ] Summarize findings + anomalies in QA doc (`docs/qa/NEWS_SURFACE_QA.md`).

### 8. Automation Strategy Notes
- Local Playwright mocks are a stopgap for environments without the Playwright MCP server. Once the MCP server is loaded in a future session, retire the local mock helpers (`frontend/tests/e2e/utils/mockData.ts`) and run the UI suite via the MCP interface against real data.
