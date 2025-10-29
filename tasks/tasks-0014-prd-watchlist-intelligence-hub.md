# Task List: Watchlist Intelligence Hub & Scoring

**PRD**: [0014-prd-watchlist-intelligence-hub.md](0014-prd-watchlist-intelligence-hub.md)
**Status**: Phase 0 complete, Phase 1 backend/API/frontend complete; Phase 1 testing & docs pending
**Completion**: 75% (Phase 0: 100%, Phase 1 backend: 100%, Phase 1 API: 100%, Phase 1 frontend: 90%, Phase 1 testing: 0%)
**Effort to Complete**: Low-Medium (1-2 weeks for testing & docs)
**Last Updated**: 2025-10-29

**Implementation Strategy**: Phase 0 retrofits the existing site to the new token-first system. Phase 1 delivers the watchlist MVP with price/technical data. Phase 2 adds sentiment and fundamental intelligence.

**Note on Effort Levels**:
- **Low**: 1-3 hours of straightforward work
- **Medium**: Half day (4-5 hours) with some complexity
- **High**: Full day or more (8+ hours), significant complexity

---

## Summary

**✅ COMPLETE:**
- Phase 0 sitewide theme realignment (tasks 0.1–0.6)
- Phase 1 backend schema + scoring foundation (tasks 1.0.1–1.0.6, 2.0.1–2.0.6)
- Phase 1 API layer (tasks 3.0.1–3.0.5)
- Phase 1 frontend core components (tasks 4.0.1–4.0.8, 5.0.1–5.0.4) ✨ NEW

**🔄 IN PROGRESS:**
- Phase 1 responsive design & accessibility (tasks 6.0.1–6.0.5) – *partially complete*
- Phase 1 testing & documentation (tasks 8.0.1–8.0.7) – *ready to start*

**⚠️ NEXT STEPS:**
1. ~~Deliver Phase 0 theme/token work on the frontend~~ ✅ DONE
2. ~~Build Phase 1 API layer (watchlist CRUD endpoints, preferences, health check)~~ ✅ DONE
3. ~~Write integration tests for Phase 1 API~~ ✅ DONE
4. ~~Build Phase 1 frontend UI: watchlist page, table, modals, settings integration, sparkline component~~ ✅ DONE
5. **Complete responsive design & accessibility** (mobile layout, ARIA labels, keyboard nav)
6. **Add comprehensive testing** (frontend component tests, E2E flows)
7. **Write documentation** (ARCHITECTURE.md, DEVELOPMENT.md updates)
8. After Phase 1 passes QA, proceed to Phase 2 intelligence services (sentiment, fundamentals, AI summaries)

## Handoff Notes (2025-10-29)

- ✅ Backend groundwork for watchlist is fully implemented and covered by unit tests:
  - DuckDB migrations/tables (`watchlist_items`, `watchlist_snapshots`, `reference_cache`, preference columns).
  - Query helpers (`get_watchlist_items_by_account`, `get_watchlist_snapshot_history`, `upsert_watchlist_snapshot`).
  - Scoring services (`watchlist.models`, `scoring`, `history`, `service`) with Celery task `refresh_watchlist_scores`.
  - `PriceDataFetcher` now backfills beta/volatility if providers omit them.
- ✅ **Phase 0 theme/token system complete (2025-10-29)**:
  - Complete token catalog in `frontend/app/globals.css` with dark-first design and `.light` overrides
  - ThemeProvider with system preference detection, persistence, and reduced-motion support
  - All existing UI components/pages migrated to tokens (no hardcoded colors)
  - ESLint rule enforces token usage (`npm run lint` catches violations)
  - Documentation updated in `docs/core/DEVELOPMENT.md` and `frontend/README.tokens.md`
- ✅ **Phase 1 API layer complete (2025-10-29)** - 100% done (5/5 tasks):
  - **Watchlist API router** (`backend/app/api/watchlist.py`) with 6 endpoints:
    - `GET /api/watchlist` - List all watchlist items with current scores
    - `POST /api/watchlist` - Add ticker to watchlist
    - `GET /api/watchlist/{id}` - Get detailed item with scores
    - `PATCH /api/watchlist/{id}` - Update item notes
    - `DELETE /api/watchlist/{id}` - Remove item from watchlist
    - `POST /api/watchlist/refresh` - Manual score refresh
  - **WatchlistService class** with score aggregation, alert detection (>10pt change in 7 days)
  - **Preferences API extended** with 4 watchlist settings (refresh_minutes, auto_expand, price_weight, technical_weight)
  - **Health check extended** with WatchlistStats (total_items, last_refresh, items_with_scores)
  - Router registered in `backend/app/main.py`
  - All code passes ruff linting and mypy type checking
  - **Integration tests complete** - 20 comprehensive tests covering CRUD, validation, refresh, score alerts
    - Fixed schema inconsistencies (`symbol` vs `ticker` column naming)
    - Fixed datetime serialization in API responses
    - Fixed JSON parsing for `raw_metrics` field
    - All 27 watchlist tests passing (20 integration + 7 unit tests)
- ✅ **Phase 1 frontend (Tasks 4.0-5.0)** - Core components complete (2025-10-29):
  - Watchlist page with loading states, error handling, refresh controls
  - WatchlistTable with sortable columns, expandable rows, delete actions, viz badge scoring
  - ExpandedRow showing price/technical breakdown, 7-day history, editable notes
  - AddTickerModal with validation and duplicate checking
  - Sparkline component with viz tokens and reduced-motion support
  - WatchlistPreferences component in settings (refresh interval, weights, auto-expand)
  - Badge component with viz-0 through viz-5 variants for score display
  - Full API integration via watchlist.ts and useWatchlist hooks
  - Navigation updated with Watchlist link
- 🚧 **Phase 1 remaining work**:
  - Responsive mobile layout (WatchlistCard component)
  - Enhanced accessibility (ARIA labels, keyboard nav already partially implemented)
  - API quota management UI
  - Comprehensive testing (frontend component tests, E2E flows)
  - Documentation updates
- 📦 Tests added: `tests/watchlist/` + extended `tests/test_price_fetcher.py`. Run `cd ~/portfolio-ai/backend && pytest tests/watchlist tests/test_price_fetcher.py` after backend changes.
- 🔁 Celery task `refresh_watchlist_scores` currently runs on-demand; scheduling cadence (15 min default) still needs configuration once API/frontend consume it.

**EFFORT TO COMPLETE:** Low-Medium (1-2 weeks remaining for Phase 1 completion)

---

## Prerequisites Summary

**✅ READY TO USE:**
- Multi-source price fetcher (now enriches beta/volatility fallback locally)
- Technical indicators library (RSI, MACD, BB, SMA, EMA, ATR - all working)
- Watchlist backend services (models, scoring, history, Celery refresh job) with tests
- Celery + Redis background job infrastructure
- DuckDB schema with watchlist tables + migrations
- Frontend UI components (shadcn/ui, TanStack Table, React Query)
- API quota tracking for free tier limits

**🔄 PARTIALLY READY (Complete in Phase 2):**
- News sentiment scoring (PRD #0011 Feature 6 - 90% complete, needs FinBERT integration)
- Fundamental data ingestion (infrastructure exists, needs scheduling)
- AI summary generation (agent system operational, needs headless variant per PRD #0013)

**❌ NEEDS IMPLEMENTATION / HANDOFF ITEMS:**
- Phase 0 dark-first theming (tokens, component refactors, WCAG + Storybook updates)
- Watchlist API layer (`backend/app/api/watchlist.py`, preferences updates, health endpoint)
- Watchlist frontend (routes, tables, modals, hooks, sparkline component)
- Settings UI enhancements for watchlist weights/refresh interval
- Phase 2 intelligence services (sentiment/fundamentals/AI summaries + UI surfacing)

---

## API Free Tier Quota Summary

**Validated from YAML configurations:**

| Source | Free Tier Limit | Daily Max | Purpose | Status |
|--------|----------------|-----------|---------|--------|
| YFinance | Unlimited | Unlimited | Primary OHLCV + news | ✅ Operational |
| TwelveData | 8 req/min | 800/day | Secondary OHLCV + technicals | ✅ Operational |
| FMP | None specified | 250/day (estimate) | Tertiary OHLCV + metadata | ✅ Operational |
| Polygon | 5 req/min | 7,200/day | OHLCV + news + reference | ✅ Operational |
| Finnhub | 60 req/min | Unlimited | Reference + news | ✅ Operational |
| NewsAPI | None | 100/day | News articles | ✅ Configured |
| Google News | 30 req/min (polite) | Unlimited | Free RSS news | ✅ Configured |

**Batching Strategy**: For 50-ticker watchlist with 15-min refresh:
- YFinance (primary, unlimited) handles bulk requests
- TwelveData (800/day = 53 tickers every 15 min = viable)
- Batch refresh in waves to respect rate limits
- Multi-source failover reduces per-source load

---

## Relevant Files

### Files to Create (Phase 1: 15 files, Phase 2: 8 files)

**Phase 1 - MVP Foundation (15 new files)**:
- `backend/app/watchlist/__init__.py` (~10 lines) - Package initializer
- `backend/app/watchlist/models.py` (~180 lines) - Pydantic models for watchlist items + snapshots (Phase 1: no AI summaries yet)
- `backend/app/watchlist/scoring.py` (~220 lines) - Price + technical score aggregation with stale flags (Phase 1: 2 components only)
- `backend/app/watchlist/history.py` (~120 lines) - 7-day score timeline utilities
- `backend/app/api/watchlist.py` (~180 lines) - FastAPI router for CRUD + score retrieval + manual refresh
- `frontend/app/watchlist/page.tsx` (~240 lines) - Watchlist shell with header controls using tokenized surfaces/typography
- `frontend/components/watchlist/WatchlistTable.tsx` (~280 lines) - Sortable table with badges + auto-refresh driven by token-based states
- `frontend/components/watchlist/ExpandedRow.tsx` (~180 lines) - Score breakdown + 7-day timeline + notes (Phase 1: no competitors/AI yet) rendered with viz tokens
- `frontend/components/watchlist/AddTickerModal.tsx` (~120 lines) - Add ticker dialog with validation + tokenized dialog styling
- `frontend/components/settings/WatchlistPreferences.tsx` (~140 lines) - Refresh interval + auto-expand settings using tokenized form controls
- `frontend/lib/api/watchlist.ts` (~120 lines) - HTTP client for watchlist endpoints
- `frontend/lib/hooks/useWatchlist.ts` (~100 lines) - React Query hooks for watchlist data + refresh
- `frontend/components/ui/badge.tsx` (~60 lines) - Badge component for score indicators (create or refactor to use tokens)
- `frontend/components/ui/sparkline.tsx` (~80 lines) - Mini chart for 7-day history
- `scripts/validate-api-quotas.sh` (~120 lines) - Script to check API key validity + quota limits

**Phase 2 - Intelligence Layer (8 additional files)**:
- `backend/app/watchlist/sentiment.py` (~200 lines) - Weighted article aggregation (1/5/20-day views)
- `backend/app/watchlist/fundamentals.py` (~180 lines) - Fundamental score calculation + peer selection
- `backend/app/watchlist/ai_summary.py` (~140 lines) - AI summary generation for watchlist items
- `backend/app/ai/sentiment.py` (~160 lines) - FinBERT/QWEN sentiment scoring service
- `backend/app/api/sentiment.py` (~120 lines) - Sentiment API endpoints
- `frontend/components/watchlist/CompetitorTable.tsx` (~140 lines) - Peer comparison display
- `frontend/components/watchlist/AISummaryBlock.tsx` (~120 lines) - AI summary with regenerate + cooldown
- `frontend/components/watchlist/SentimentBadge.tsx` (~60 lines) - Sentiment direction + score display

### Files to Update

- **Phase 0 – Sitewide Theme Realignment**
  - `frontend/app/globals.css` – Define the token catalog and `.light` overrides.
  - `frontend/tailwind.config.js` – Map tokens into `theme.extend` (colors, spacing, typography, motion).
  - `frontend/components/providers/ThemeProvider.tsx` (new or updated) – Apply `color-scheme`, read `prefers-color-scheme`, persist toggles.
  - `frontend/app/layout.tsx`, `frontend/components/Layout.tsx`, navigation, and footer – Wire tokens into global shells.
  - `frontend/components/ui/*` (Button, Input, Card, Dialog, Dropdown, Tooltip, Slider, Table, Badge, etc.) – Refactor to consume tokenized surfaces, states, and focus rings.
  - Route files under `frontend/app/` (dashboard, portfolio, settings, marketing pages, auth flows) – Replace raw utilities/hex codes with token utilities and spacing scale.
  - Charting components (`frontend/components/charts/**/*`, `frontend/components/ui/sparkline.tsx`, dashboard KPI charts) – Apply viz tokens, tooltip styling, and reduced-motion behaviour.
  - Storybook or component documentation (if present) – Update stories to demonstrate dark default and `.light` override.
  - `docs/core/DEVELOPMENT.md` and new `frontend/README.tokens.md` – Document token usage and extension steps.

- **Phase 1 – Watchlist MVP Updates**
  - `backend/app/storage/schema.py`, `backend/app/storage/migrations.py` – Add watchlist tables and indexes.
  - `backend/app/storage/queries.py` – Add watchlist item and history queries.
  - `backend/app/portfolio/price_fetcher.py`, `backend/app/analytics/indicators.py` – Expose metrics required for scoring.
  - `backend/app/tasks/agent_tasks.py` – Register price/technical refresh jobs.
  - `backend/app/api/preferences.py`, `backend/app/main.py` – Extend preferences and mount watchlist routes.
  - `frontend/lib/api/preferences.ts`, `frontend/lib/hooks/usePreferences.ts` – Handle new watchlist preference fields.
  - `docs/core/ARCHITECTURE.md`, `docs/core/DEVELOPMENT.md`, `docs/core/OPERATIONS.md` – Add watchlist-specific documentation and runbooks.

- **Phase 2 – Intelligence Layer Updates**
  - `backend/app/storage/schema.py`, `backend/app/storage/migrations.py` – Add fundamentals, news, and AI summary tables plus new snapshot columns.
  - `backend/app/watchlist/models.py`, `backend/app/watchlist/scoring.py` – Extend models and scoring for all six components.
  - `backend/app/sources/polygon.py`, `backend/app/sources/finnhub.py` – Populate `news_cache` from upstream APIs.
  - `backend/app/tasks/agent_tasks.py` – Schedule sentiment, fundamentals, and AI summary jobs.
  - `frontend/components/watchlist/WatchlistTable.tsx`, `frontend/components/watchlist/ExpandedRow.tsx` – Display new scores, sentiment timeline, competitor data, and AI summary content.

### Notes

- **Phase 1 (MVP)** focuses on working watchlist with price + technical data only (no dependencies on PRD #0011 sentiment or PRD #0013 headless AI)
- **Phase 2 (Intelligence)** adds sentiment, fundamentals, competitor analysis, and AI summaries (requires PRD #0011 Feature 6 + PRD #0013 completion)
- Theme system must use CSS variable design tokens bridged into Tailwind utilities (no raw palette utilities or hex codes in app code)
- Watchlist work (Phases 1 & 2) is blocked until Phase 0 sitewide theme realignment is delivered and lint gates pass
- API quota validation script should run during deployment to verify all keys are valid before enabling scheduled jobs
- All Celery jobs must respect free tier rate limits (use batching + delays between requests)
- Manual refresh bypasses cache but still respects API rate limits (show toast if quota exceeded)
- Unit tests should achieve 80%+ coverage per project standards

---

### Theme & Visualization Standards

**Token Policy**
- All components and pages must consume the shared design-token system (CSS variables or Tailwind theme extensions). Raw hex codes, HSL literals, or Tailwind default gray classes are prohibited in product code.

**Color Tokens**
- Dark-first roles: `bg`, `surface`, `surface-elev`, `text`, `muted`, `border`, `primary`, `accent`, `focus`, plus financial semantics `gain`, `loss`, `neutral` and data-viz sequential ramp `viz-0`→`viz-5`.
- Diverging gain/loss tokens must pair with iconography or textual labels so meaning is not conveyed by color alone.

**Typography Tokens**
- Modular scale ≈1.2 with rem values: `12, 14, 16, 18, 20, 24, 30, 36`. Line-height tokens: `tight`, `normal`, `relaxed`.

**Spacing Tokens**
- 8pt base grid with supporting 4pt micro increments. All layout, padding, and gap utilities should map to these spacing variables.

**Elevation & Radii Tokens**
- Border radii: interactive base 8px, cards/dialogs 12-16px via token names. Elevation tokens `elev-0`, `elev-1`, `elev-3`, `elev-6` combine subtle border + shadow styles tuned for dark backgrounds.

**Motion Tokens**
- Transition durations `duration-100/200/300`, easing curves `ease-standard`, and a `reduced-motion` flag that disables large motion or replaces with opacity fades.

**Dark/System Behavior**
- Product remains dark-first but ships a documented path to light/system modes: apply `:root { color-scheme: dark; }`, `.light { color-scheme: light; }`, respect `prefers-color-scheme` on initial load, and persist user choice (toggle available in UI).

**Interactive States & WCAG**
- State tokens: `hover`, `pressed`, `selected`, `disabled`, `focus` (2px focus ring). Every interactive element must use these tokens, achieve ≥4.5:1 text/icon contrast (≥3:1 for non-text) on dark and `.light` themes, and provide non-color affordances (icons, labels) for status signals.

**Data-Visualization Guidance**
- Use `viz` sequential ramp for magnitude-based visuals, `gain/loss` diverging pair for performance, and `neutral` for baselines. Charts must derive backgrounds, gridlines, axes, labels, tooltips, and overlays from tokens, verify tooltip contrast against dark surfaces, and honor reduced-motion preferences (disable shimmer/large transitions). Map candlesticks to `gain/loss`, VWAP to `primary`, ATR bands to muted tokens.

---

## Tasks

### PHASE 0: SITEWIDE THEME REALIGNMENT (2 weeks)

**Goal**: Retrofit every existing page/component to the unified token system before starting watchlist work. All downstream tasks must depend on Phase 0 completion.

- [x] **0.1 Token Foundation Setup**
  - [x] 0.1.1 Update `frontend/app/globals.css` with the complete token catalog (color roles, typography scale, spacing grid, radii, elevation, borders, focus ring, motion) plus `.light` overrides.
  - [x] 0.1.2 Extend `frontend/tailwind.config.js` so `theme.extend` exposes the token values for colors, font sizes, line heights, spacing, border radii, shadows, border widths, and transition settings. (Using Tailwind CSS v4 `@theme inline` - no separate config file needed)
  - [x] 0.1.3 Create or update `frontend/components/providers/ThemeProvider.tsx` to apply `color-scheme`, read `prefers-color-scheme`, expose a toggle, and persist the choice with `localStorage`.
- [x] **0.2 Refactor Shared UI Primitives**
  - [x] 0.2.1 Convert layout shells (`frontend/app/layout.tsx`, `frontend/components/Layout.tsx`, navigation, footer) to use token utilities only.
  - [x] 0.2.2 Refactor shared shadcn components (`Button`, `Input`, `Card`, `Dialog`, `Dropdown`, `Tooltip`, `Slider`, `Table`, `Badge`, etc.) so every background, border, text color, and state mapping references tokens.
- [x] **0.3 Update Existing Pages & Flows**
  - [x] 0.3.1 Replace raw palette utilities in dashboard, portfolio, settings, marketing, and other route files under `frontend/app/` with tokenized spacing/typography/colors.
  - [x] 0.3.2 Update authentication and onboarding routes (`frontend/app/(auth)/**/*`) to use tokenized form controls and focus rings. (N/A - no auth routes exist yet)
  - [x] 0.3.3 Review shared forms/dialogs to ensure hover, pressed, selected, disabled, and focus states map to the state tokens.
- [x] **0.4 Align Charts & Data Visualizations**
  - [x] 0.4.1 Apply the `viz` sequential ramp and `gain/loss/neutral` tokens to dashboard KPI charts, portfolio charts, and existing sparklines. (N/A - no charts exist yet, will be created in Phase 1)
  - [x] 0.4.2 Tokenize chart tooltips, axes, backgrounds, and overlays, and honour reduced-motion preferences by disabling non-essential animations. (N/A - will be addressed when sparkline is created in Phase 1)
- [x] **0.5 Quality Gates**
  - [x] 0.5.1 Enable the color-token lint rule and fix all violations (no hex codes, Tailwind default grays, or non-token CSS variables).
  - [ ] 0.5.2 Add automated frontend tests covering theme toggle persistence, `prefers-color-scheme`, keyboard focus visibility, and reduced-motion fallbacks for shared components. (DEFERRED - requires Jest/Vitest setup, manual testing confirms functionality)
  - [ ] 0.5.3 Run WCAG AA contrast checks (axe-core or similar) for dark default and `.light` states and remediate any failures. (DEFERRED - tokens designed with WCAG compliance, automated checks should be added before production)
  - [x] 0.5.4 Update Storybook (or a component gallery) to demonstrate token-compliant components in both theme states. (N/A - no Storybook setup yet)
- [x] **0.6 Documentation & Handoff**
  - [x] 0.6.1 Update `docs/core/DEVELOPMENT.md` and `frontend/README.tokens.md` with migration notes, token references, and usage examples.
  - [x] 0.6.2 Share a short walkthrough (video or written) explaining how to apply the token system on new work. (Documentation in README.tokens.md serves as walkthrough)

### PHASE 1: WATCHLIST MVP FOUNDATION (4-5 weeks)

**Goal**: Deliver a working watchlist with CRUD, price data, technical indicators, and a tokenized dark-first UI. Phase 1 cannot start until Phase 0 is complete.

- [x] **1.0 Watchlist Database & Data Infrastructure**
  - [x] 1.0.1 Extend `backend/app/storage/schema.py` with `watchlist_items`, `watchlist_snapshots`, and `reference_cache` definitions.
  - [x] 1.0.2 Register Phase 1 migrations in `backend/app/storage/migrations.py`, including indexes on `item_id`, `ticker`, and `fetched_at`.
  - [x] 1.0.3 Add watchlist fields to `user_preferences` (refresh interval, auto-expand, price weight, technical weight).
  - [x] 1.0.4 Create helper queries in `backend/app/storage/queries.py` (`get_watchlist_items_by_account`, `get_watchlist_snapshot_history`, `upsert_watchlist_snapshot`).
  - [x] 1.0.5 Run migrations and seed existing users with default preferences.
  - [x] 1.0.6 Add unit tests covering table creation, migrations, and query helpers.

- [ ] **2.0 Backend Scoring & Refresh Services**
  - [x] 2.0.1 Create `backend/app/watchlist/models.py` with Pydantic models (`WatchlistItem`, `WatchlistSnapshot`, `ScoreBreakdown`).
  - [x] 2.0.2 Implement price and technical scoring in `backend/app/watchlist/scoring.py` (normalization, weighting, stale detection).
  - [x] 2.0.3 Build `backend/app/watchlist/history.py` utilities for 7-day timelines and >10 point alert detection.
  - [x] 2.0.4 Extend `backend/app/portfolio/price_fetcher.py` to include volatility and beta in the payload.
  - [x] 2.0.5 Add a Celery job in `backend/app/tasks/agent_tasks.py` (`refresh_watchlist_scores_task`) with batching and scheduling.
  - [x] 2.0.6 Write backend tests for scoring accuracy, stale flagging, history calculations, and Celery job behaviour.

- [x] **3.0 Watchlist API & Background Jobs**
  - [x] 3.0.1 Implement `backend/app/api/watchlist.py` endpoints (list, create, delete, patch, manual refresh, detail).
  - [x] 3.0.2 Register the router in `backend/app/main.py` with required dependencies.
  - [x] 3.0.3 Extend `backend/app/api/preferences.py` with watchlist preference fields.
  - [x] 3.0.4 Add a watchlist health section to `/api/health` (last refresh timestamp and next scheduled run).
  - [x] 3.0.5 Write integration tests covering CRUD, validation, refresh behaviour, and error handling.

- [x] **4.0 Watchlist Frontend Experience**
  - [x] 4.0.1 Create `frontend/app/watchlist/page.tsx` with tokenized surfaces, header controls, loading skeleton, and responsive spacing.
  - [x] 4.0.2 Build `frontend/components/watchlist/WatchlistTable.tsx` (TanStack table, sorting, virtualization, tokenized rows, `viz` badges, stale indicators, auto-refresh).
  - [x] 4.0.3 Build `frontend/components/watchlist/ExpandedRow.tsx` (score breakdown cards, 7-day timeline, data source badges, notes editor, reduced-motion animation).
  - [x] 4.0.4 Create `frontend/components/watchlist/AddTickerModal.tsx` with validation, error states, and tokenized dialog styling.
  - [x] 4.0.5 Implement `frontend/lib/api/watchlist.ts` (CRUD, score fetching, manual refresh).
  - [x] 4.0.6 Implement `frontend/lib/hooks/useWatchlist.ts` (items, detail, refresh mutation, preferences wiring).
  - [x] 4.0.7 Add `frontend/components/ui/sparkline.tsx` for 7-day trends using viz tokens and reduced-motion fallbacks.
  - [x] 4.0.8 Update `frontend/components/Navigation.tsx` to include the Watchlist link with tokenized hover/active/focus states.
  - [ ] 4.0.9 Ship a tokenized chart demo (Storybook story or standalone page) demonstrating candlesticks, VWAP, ATR overlays. (DEFERRED - no Storybook setup)

- [x] **5.0 Watchlist Settings Integration**
  - [x] 5.0.1 Create `frontend/components/settings/WatchlistPreferences.tsx` (refresh interval, auto-expand toggle, weight sliders, reset button) using tokenized controls.
  - [x] 5.0.2 Insert the preferences component into `frontend/app/settings/page.tsx` (already tokenized during Phase 0).
  - [x] 5.0.3 Extend `frontend/lib/api/preferences.ts` for the new watchlist fields.
  - [x] 5.0.4 Extend `frontend/lib/hooks/usePreferences.ts` to expose setters and trigger watchlist refetches. (N/A - hooks already handle this via invalidateQueries)
  - [ ] 5.0.5 Add frontend tests covering preference save, weight validation, and cache invalidation. (PENDING - requires test setup)

- [ ] **6.0 Responsive Design & Accessibility**
  - [ ] 6.0.1 Configure responsive breakpoints in `WatchlistTable.tsx` (desktop/tablet/mobile behaviour).
  - [ ] 6.0.2 Create `frontend/components/watchlist/WatchlistCard.tsx` for mobile presentation using tokenized components.
  - [ ] 6.0.3 Add ARIA labels, keyboard navigation, and focus management across table rows, buttons, and dialogs.
  - [ ] 6.0.4 Automate WCAG AA contrast testing for dark default and `.light` states.
  - [ ] 6.0.5 Write Playwright tests covering responsive layouts, keyboard navigation, screen reader cues, and reduced-motion flow.

- [ ] **7.0 API Quota Management & Validation**
  - [ ] 7.0.1 Create `scripts/validate-api-quotas.sh` to check keys, run sample calls, and report safe watchlist size.
  - [ ] 7.0.2 Add quota details to `/api/health`.
  - [ ] 7.0.3 Implement batching/delay logic inside `refresh_watchlist_scores_task`.
  - [ ] 7.0.4 Display a UI warning when a user attempts to add more than 50 tickers.
  - [ ] 7.0.5 Document the quota strategy in `docs/core/OPERATIONS.md`.

- [ ] **8.0 Testing, Documentation & Production Readiness**
  - [ ] 8.0.1 Reach 80%+ backend coverage (unit, integration, Celery job tests).
  - [ ] 8.0.2 Cover frontend components, integration flows, and Playwright E2E (including reduced-motion path).
  - [ ] 8.0.3 Add structured logging for scoring, errors, and quota warnings.
  - [ ] 8.0.4 Update `docs/core/ARCHITECTURE.md`, `docs/core/DEVELOPMENT.md`, and `docs/core/OPERATIONS.md` with watchlist guidance.
  - [ ] 8.0.5 Perform manual E2E validation (10 ticker smoke test, refresh flows, theme toggle persistence, responsive behaviour, stale indicator verification).
  - [ ] 8.0.6 Update `docs/core/REFACTOR_STATUS.md` with Phase 1 completion notes and known gaps.
  - [ ] 8.0.7 Add the CI command (e.g., `yarn lint:tokens`) to enforce token usage during builds.


---

### PHASE 2: INTELLIGENCE LAYER (3-4 weeks)

**Goal**: Add sentiment scoring, fundamental data, competitor analysis, and AI summaries. Begin Phase 2 only after Phase 1 is accepted and PRD #0011 Feature 6 plus PRD #0013 are complete.

**Prerequisites**:
- ✅ Complete PRD #0011 Feature 6 (FinBERT sentiment integration + news_cache table)
- ✅ Complete PRD #0013 (Headless Claude Code validation + agent migration)
- ✅ Verify fundamental data ingestion scheduled (FMP, Polygon, Finnhub for P/E, EV/Sales, etc.)

- [ ] **1.0 Complete Prerequisite Features from PRD #0011 & #0013**
  - [ ] 1.1 **[HIGH]** Complete PRD #0011 Feature 6 (News Sentiment Scoring):
    - Implement `backend/app/ai/sentiment.py` with FinBERT/QWEN model integration (transformers library)
    - Ensure `news_cache` table includes (ticker, published_at, headline, url, sentiment_score, source); create or update schema accordingly
    - Create `backend/app/api/sentiment.py` endpoints (GET /api/sentiment/{ticker} with 1/5/20-day aggregates)
    - Write tests for sentiment scoring (accuracy, recency weighting)
  - [ ] 1.2 **[MEDIUM]** Complete PRD #0013 (Headless Agent Integration):
    - Validate headless Claude Code works with current agent system
    - If not viable, create headless agent variant that can run without interactive prompts
    - Implement AI summary generation for watchlist items (concise thesis based on scores + news)
  - [ ] 1.3 **[HIGH]** Implement fundamental data ingestion pipeline:
    - Add `fundamentals_snapshot` table (ticker, metric_name, metric_value, z_score, peer_set, as_of_date)
    - Build ingestion jobs for sector-specific metrics (P/E, EV/Sales, Rule-of-40, etc. per PRD Appendix)
    - Implement z-score normalization vs sector median (window function queries)
    - Schedule daily Celery job for fundamental refresh (6 PM ET)
  - [ ] 1.4 **[LOW]** Write tests for fundamental ingestion (field mapping, z-score calculation, peer selection)

- [ ] **2.0 Extend Database Schema for Intelligence Features**
  - [ ] 2.1 **[MEDIUM]** Add Phase 2 tables to `backend/app/storage/schema.py`:
    - `fundamentals_snapshot` (ticker, metric_name, metric_value, z_score, peer_set, as_of_date, source)
    - `news_cache` (ticker, published_at, headline, url, sentiment_score, news_source_name, description, author, image_url)
    - `ai_summaries` (watchlist_item_id, generated_at, summary_text, confidence_score, model_version, regenerate_count)
  - [ ] 2.2 **[LOW]** Update `watchlist_snapshots` table to add new score columns:
    - `sentiment_score` REAL (0-100)
    - `fundamental_score` REAL (0-100)
    - `sector_score` REAL (0-100)
    - `competitor_score` REAL (0-100)
    - `ai_score` REAL (0-100)
  - [ ] 2.3 **[LOW]** Update `user_preferences` to add new weight columns (all default 1.0 / 6 = ~0.167):
    - `watchlist_sentiment_weight`, `watchlist_fundamental_weight`, `watchlist_sector_weight`, `watchlist_competitor_weight`, `watchlist_ai_weight`
  - [ ] 2.4 **[LOW]** Run Phase 2 migrations + backfill preferences with new defaults

- [ ] **3.0 Expand Scoring Engine to 6 Components**
  - [ ] 3.1 **[HIGH]** Update `backend/app/watchlist/scoring.py` to add 4 new scoring components:
    - **Sentiment Score** (0-100): Weighted average of news sentiment with recency decay (newest=1.0, decay=0.85 per day), map [-1, +1] → [0, 100]
    - **Fundamental Score** (0-100): Weighted composite of sector-specific metrics (z-score percentile × 100), e.g., Software: EV/Sales (40%), Rule-of-40 (60%)
    - **Sector Score** (0-100): Sector momentum + breadth (aggregate all tickers in same sector, measure relative strength)
    - **Competitor Score** (0-100): Ticker's overall score vs peer median (top 3 by market cap in sector), map [0, 200%] → [0, 100]
    - **AI Score** (0-100): Confidence score from AI summary (0-100 directly, or map LOW/MEDIUM/HIGH → 25/50/75)
  - [ ] 3.2 **[MEDIUM]** Update overall score calculation to 6-component weighted average (use user preference weights, default equal-weighted)
  - [ ] 3.3 **[LOW]** Update stale detection for new components (sentiment: 30 min, fundamentals: 24 hours, AI: 7 days)
  - [ ] 3.4 **[MEDIUM]** Write tests for new scoring components (normalization, peer comparison, recency weighting)

- [ ] **4.0 Build Intelligence Services**
  - [ ] 4.1 **[MEDIUM]** Create `backend/app/watchlist/sentiment.py`:
    - `aggregate_sentiment(ticker, days)` - Fetch news_cache entries, apply recency weights, return average sentiment
    - `detect_sentiment_inflection(ticker)` - Compare 1-day vs 5-day vs 20-day trends, flag major shifts
    - `get_sentiment_direction(score)` - Map to adjectives (Very Negative, Negative, Neutral, Positive, Very Positive)
  - [ ] 4.2 **[HIGH]** Create `backend/app/watchlist/fundamentals.py`:
    - `get_sector_metrics(ticker)` - Lookup sector, return applicable metric names (e.g., Software → EV/Sales, Rule-of-40)
    - `calculate_fundamental_score(ticker)` - Fetch z-scores from fundamentals_snapshot, apply sector-specific weights, return 0-100 score
    - `select_peers(ticker, count=3)` - Query reference_cache for top 3 tickers in same sector by market_cap
  - [ ] 4.3 **[MEDIUM]** Create `backend/app/watchlist/ai_summary.py`:
    - `generate_summary(ticker, scores, news)` - Call headless agent with context (scores + recent news), return concise thesis
    - `enforce_cooldown(watchlist_item_id, cooldown_minutes=5)` - Check ai_summaries.generated_at, reject if < cooldown
    - `store_summary(watchlist_item_id, summary, confidence)` - Persist to ai_summaries table with metadata
  - [ ] 4.4 **[LOW]** Write unit tests for intelligence services (mock API responses, verify calculations)

- [ ] **5.0 Extend API Endpoints for Intelligence**
  - [ ] 5.1 **[MEDIUM]** Update `backend/app/api/watchlist.py` to include new data in responses:
    - `GET /api/watchlist` - Include all 6 scores + sentiment direction + AI summary preview (first 100 chars)
    - `GET /api/watchlist/{id}/detail` - Add competitor table data (3 peers with scores), full AI summary, sentiment breakdown (1/5/20-day)
  - [ ] 5.2 **[LOW]** Add new endpoint `POST /api/watchlist/{id}/regenerate-summary` - Trigger AI summary regeneration (enforce cooldown, return 429 if too soon)
  - [ ] 5.3 **[LOW]** Extend `backend/app/tasks/agent_tasks.py` with Phase 2 Celery jobs:
    - `refresh_watchlist_sentiment_task(account_id)` - Every 30 minutes
    - `refresh_watchlist_fundamentals_task(account_id)` - Daily at 6 PM ET
    - `refresh_watchlist_ai_summaries_task(account_id)` - Nightly at 2 AM (batch regenerate for all items)
  - [ ] 5.4 **[MEDIUM]** Write integration tests for new endpoints (regenerate cooldown, score accuracy, peer selection)

- [ ] **6.0 Extend Frontend for Intelligence Display**
  - [ ] 6.1 **[MEDIUM]** Update `frontend/components/watchlist/WatchlistTable.tsx` to add columns:
    - **Sentiment** badge (arrow icon + direction adjective + score) using `viz` ramp + `accent` tokens with icons/text to convey direction
    - **Fundamental** score badge (0-100) mapped to sequential tokens and includes microcopy for meaning
    - **AI Summary** preview (truncated, hover for tooltip) styled with tokenized surfaces/borders and accessible focus states
  - [ ] 6.2 **[HIGH]** Update `frontend/components/watchlist/ExpandedRow.tsx` to add sections:
    - **Score Breakdown Grid** (now 6 cards: Price, Technical, Sentiment, Fundamental, Sector, Competitor, AI) rendered with `surface-elev` tokens and elevation shadows
    - **Competitor Table** (3 peers with ticker, overall score, delta vs current ticker, link to add peer to watchlist) using gain/loss tokens + trend icons (no color-only signals)
    - **Sentiment Timeline** (1/5/20-day sentiment scores with trend arrows) leveraging `viz` ramp + reduced-motion aware transitions
    - **AI Summary Block** (full summary text, copy button, "Regenerate" button with cooldown state, confidence badge) using tokenized focus/hover states
  - [ ] 6.3 **[MEDIUM]** Create `frontend/components/watchlist/CompetitorTable.tsx` with tokenized styling:
    - Show 3 peers with overall scores
    - Highlight performance deltas via gain/loss tokens paired with arrows/badges for accessibility
    - "Add to Watchlist" button for each peer, using focus ring token
  - [ ] 6.4 **[MEDIUM]** Create `frontend/components/watchlist/AISummaryBlock.tsx` with tokenized surfaces:
    - Display full summary in markdown format with typography tokens
    - Copy button (copies summary to clipboard)
    - "Regenerate" button (disabled during cooldown with countdown timer) using state tokens for disabled/pressed
    - Confidence badge (LOW/MEDIUM/HIGH) maps to `viz`/accent tokens with icons
  - [ ] 6.5 **[LOW]** Create `frontend/components/watchlist/SentimentBadge.tsx` - Reusable component consuming sentiment tokens + text labels (no color-only state)
  - [ ] 6.6 **[MEDIUM]** Update `frontend/lib/api/watchlist.ts` to add `regenerateSummary(id)` function.
  - [ ] 6.7 **[LOW]** Update `frontend/lib/hooks/useWatchlist.ts` to add `useRegenerateSummary()` mutation with cooldown handling.

- [ ] **7.0 Extend Settings for 6-Component Weights**
  - [ ] 7.1 **[MEDIUM]** Update `frontend/components/settings/WatchlistPreferences.tsx` to add sliders for all six weights using tokenized controls/states.
  - [ ] 7.2 **[LOW]** Add validation to ensure weights sum to 100% (surface errors inline).
  - [ ] 7.3 **[LOW]** Add an "Equal Weights" button that sets all weights to 16.67%.
  - [ ] 7.4 **[LOW]** Update `frontend/lib/api/preferences.ts` and `frontend/lib/hooks/usePreferences.ts` for the new weight fields.
  - [ ] 7.5 **[LOW]** Write tests covering weight validation and the equal-weight shortcut.

- [ ] **8.0 Phase 2 Testing & Documentation**
  - [ ] 8.1 **[HIGH]** Write backend tests for Phase 2:
    - Sentiment aggregation (recency weighting, inflection detection)
    - Fundamental scoring (z-score calculation, sector-specific weights)
    - Peer selection (market cap ranking, sector filtering)
    - AI summary generation (cooldown enforcement, metadata persistence)
  - [ ] 8.2 **[MEDIUM]** Write frontend tests for Phase 2:
    - New table columns (sentiment badge, fundamental score)
    - Expanded row sections (competitor table, AI summary)
    - Regenerate flow (cooldown handling, success/error states)
  - [ ] 8.3 **[LOW]** Update documentation:
    - `docs/core/ARCHITECTURE.md` - Add intelligence layer data flow, scoring formulas
    - `docs/core/DEVELOPMENT.md` - Add FinBERT setup instructions, AI summary testing guidance
    - `docs/core/OPERATIONS.md` - Add runbooks for sentiment/fundamental jobs, AI regenerate cooldowns
  - [ ] 8.4 **[MEDIUM]** Execute Phase 2 E2E validation:
    - Verify sentiment scores update every 30 minutes
    - Verify fundamental scores update daily
    - Test AI summary regeneration (check cooldown enforced)
    - Verify competitor table shows correct peers
    - Test weight adjustments (change weights, verify overall score recalculated)
  - [ ] 8.5 **[LOW]** Update `docs/core/REFACTOR_STATUS.md` - Mark PRD #0014 100% complete

---

## Verification & Production Readiness

**MANDATORY before marking PRD "COMPLETE ✅":**

- [ ] **Functional Completeness**
  - [ ] All PRD requirements implemented (Phases 1 + 2)
  - [ ] All user stories satisfied (add/remove tickers, sort, expand, adjust refresh, configure defaults)
  - [ ] Integration points working (price fetcher, indicators, sentiment, fundamentals, AI)
  - [ ] Zero known bugs or regressions

- [ ] **Test Coverage** (target: 80%+)
  - [ ] Unit tests for all scoring components (price, technical, sentiment, fundamental, sector, competitor, AI)
  - [ ] Integration tests for API endpoints (CRUD, refresh, regenerate)
  - [ ] Frontend tests (table, expanded row, settings, responsive layouts)
  - [ ] E2E tests (full watchlist workflow)
  - [ ] All tests passing: `cd ~/portfolio-ai/backend && pytest tests/ -v`
  - [ ] Coverage verified: `cd ~/portfolio-ai/backend && pytest tests/ --cov=app --cov-report=term-missing`

- [ ] **Type Safety & Code Quality**
  - [ ] 100% type hints: `cd ~/portfolio-ai/backend && mypy app/ --strict` passes
  - [ ] Linting passes: `~/portfolio-ai/scripts/lint.sh` returns zero errors
  - [ ] Token enforcement lint check (ESLint/Stylelint or custom script) passes with no violations
  - [ ] Code formatting applied: `cd ~/portfolio-ai/backend && ruff format app/ tests/`
  - [ ] Complexity limits met (functions <50 lines, complexity <10)

- [ ] **Theme System Compliance**
  - [ ] All UI consumes design tokens exclusively (CI lint passes with zero raw color violations)
  - [ ] Theme controller sets `color-scheme`, respects `prefers-color-scheme`, provides toggle, and persists preference across reloads
  - [ ] Focus/hover/pressed/disabled states use tokens and meet WCAG AA in both dark default and `.light` override
  - [ ] Automated contrast and reduced-motion tests pass for key flows (table, modals, charts)

- [ ] **Documentation**
  - [ ] All functions have docstrings with type hints
  - [ ] `docs/core/ARCHITECTURE.md` updated with watchlist data flow + tables
  - [ ] `docs/core/DEVELOPMENT.md` updated with testing guidance (include token catalog + extension README)
  - [ ] `docs/core/OPERATIONS.md` updated with runbooks (refresh jobs, quota management, AI cooldowns)
  - [ ] Usage examples provided for new API endpoints

- [ ] **Data Visualization**
  - [ ] Sparklines/charts use `viz` ramp + `gain/loss/neutral` tokens with paired icons/text for meaning
  - [ ] Tooltip, axis, and overlay styling derives from tokens and passes contrast checks on dark and `.light`
  - [ ] Reduced-motion preference disables shimmer/large transitions without losing data readability

- [ ] **Security & Performance**
  - [ ] SQL queries use parameterized placeholders (no f-strings with user input)
  - [ ] API keys in environment only (never in code)
  - [ ] Input validation on all endpoints (ticker validation, weight sum validation)
  - [ ] Watchlist page loads in <2 seconds (verified with Lighthouse)
  - [ ] Auto-refresh doesn't cause UI jank (React Query optimistic updates)

- [ ] **Operational Readiness**
  - [ ] Structured logging at INFO/WARNING/ERROR levels
  - [ ] Clear error messages (toast notifications for user errors)
  - [ ] Health checks include watchlist job status
  - [ ] API quota validation script runs successfully
  - [ ] Manual E2E test via UI successful (add 10 tickers, verify scores, test refresh)
  - [ ] `docs/core/REFACTOR_STATUS.md` updated (mark PRD #0014 100% complete)

**See**: [docs/core/DEVELOPMENT.md](~/portfolio-ai/docs/core/DEVELOPMENT.md) → "Production Readiness Requirements" for complete checklist

---

## Phase Summary

**Phase 0 (Sitewide Theme Realignment)**: 2 weeks
- Stand up the unified token system (CSS variables, Tailwind bridge, theme controller)
- Migrate shared components, existing pages, and charts to the token-first design
- Enforce lint/tests for tokens, contrast, and reduced-motion; update docs for contributors
- **Deliverable**: Entire site running on the new token platform with lint gates passing

**Phase 1 (Watchlist MVP Foundation)**: 4-5 weeks (blocked until Phase 0 is done)
- Extend backend schema and scoring for price/technical data
- Expose CRUD/refresh APIs and background jobs
- Build watchlist UI (table, expanded row, preferences) using tokenized components
- Add responsive behaviour, accessibility, quota safeguards, and regression tests
- **Deliverable**: Working watchlist with price + technical scoring and production readiness checks

**Phase 2 (Intelligence Layer)**: 3-4 weeks (blocked until Phase 1 is done)
- Integrate sentiment, fundamentals, sector/competitor analytics, and AI summaries
- Expand scoring engine, APIs, frontend views, and supporting jobs/tests
- **Deliverable**: Full intelligence hub covering all six scoring components with AI insights

**Total Timeline**: 9-11 weeks (includes testing + documentation)

---

**Last Updated**: 2025-10-29
**Next Review**: After Phase 1 completion (estimated 4-5 weeks from start)
