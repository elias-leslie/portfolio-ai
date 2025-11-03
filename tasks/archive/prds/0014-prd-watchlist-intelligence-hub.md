# PRD #0014: Watchlist Intelligence Hub & Scoring

**Status**: Ready for Implementation
**Owner**: Portfolio AI (internal use only)
**Last Updated**: 2025-10-28
**Audience**: Junior devs + design/analytics teammates

---

## 1. Introduction / Overview

We need a dedicated Watchlist Intelligence Hub that complements the existing dashboard and portfolio pages. The new experience will:

- Run fully in dark mode (default) and maintain the clean, responsive UI/UX established across the app.
- Track user-selected tickers with near-real-time price/indicator updates (≤15 min old) and expose actionable scoring at a glance.
- Let users expand any ticker to inspect the inputs behind each composite score (technical, fundamentals, AI, sentiment, sector, competitor) and capture personal notes.
- Provide auto-refresh controls (down to 1 minute) and configurable data settings from the main Settings page.

Phase 1 focuses on core watchlist CRUD, live data, and score presentation. Phase 2 adds deeper ranking intelligence, per-score breakdowns, row expansion details, and AI-driven context. The entire product must keep consistent dark styling (typography, spacing, hover/focus treatments) and respond gracefully on desktop, tablet, and mobile.

---

## 2. Goals

1. Deliver a first-class watchlist page that surfaces high-level scores and live metrics without expanding rows.
2. Provide expandable detail panels revealing how every score is derived, including the metrics and weights used.
3. Allow configurable refresh intervals (1–15 minutes) and persisted watchlist settings via the existing Settings page.
4. Maintain UX consistency: global dark theme, responsive layout, accessible interactions, and shared component styling.
5. Phase 2: introduce ranking logic combining technical, fundamental, AI, sentiment, sector, and competitor data with adjustable weighting.

---

## 3. User Stories

- As a self-directed investor, I can add/remove tickers and instantly see the most important scores so I know what deserves attention.
- As a user, I can sort by any column (e.g., overall score, sentiment, AI confidence) to prioritize my review order.
- As a user, I can expand a ticker to review the actual metrics and calculations behind each score, plus AI commentary and notes, so I trust the outputs.
- As a user, I can adjust watchlist refresh cadence (1–15 minutes) without leaving the page, ensuring data is as fresh as I need.
- As a user, I can configure defaults (article look-back, refresh interval, weighting multipliers) from the global Settings page.

### Dependencies & Preconditions

- Complete the remaining data tasks from **PRD #0011** / **tasks-0011** that feed the watchlist:
  - Implement the news ingestion + sentiment scoring service (FinBERT/QWEN scoring, `news_cache` with `sentiment_score`, `/api/sentiment` endpoints).
  - Finalize ingestion of reference/fundamental data across Polygon, FMP, TwelveData, Finnhub, etc., including schema support for `reference_cache`/`fundamentals_snapshot` tables.
  - Ensure multi-source historical backfill and indicator caches are operational (Phases 1–4 already marked complete).
- Align with **PRD #0013** for headless Claude/Gemini/local model execution so the watchlist AI summary regenerate button can call the headless agent stack without token limits.
- Verify API credentials and daily quotas for Polygon, FMP, Finnhub, TwelveData, NewsAPI, and Google News are configured in the environment/secrets store; the watchlist must never fall back to mock data.

---

## 4. Functional Requirements

### Phase 1 – Watchlist Foundation
1. **Navigation & Page Shell**
   - Add “Watchlist” to the global nav with active-state styling matching dark mode (Navigation.tsx update).
   - Route: `/watchlist` implemented in Next.js App Router.

2. **Watchlist Table (Collapsed State)**
   - Columns (sortable): Symbol, Price, Day Change %, News Sentiment Score (badge), Technical Score, Fundamental Score, AI Score / Confidence, Sector Score, Competitor Score, Overall Score.
   - News sentiment: compute using latest N articles (default 10, de-duplicated, newest weighted heavier) from stored pipeline; badge text should include direction arrow + adjective (Positive/Neutral/Negative) + numeric score.
   - Price data: feed from `PriceDataFetcher` cache; ensure data is ≤15 minutes old. Show stale-state indicator if cache exceeds TTL.
   - Overall score: default weighted average (equal weights initially) of the five component scores. Persist 2 decimal precision.

3. **CRUD & Autosave**
   - Add Ticker modal: validate symbol exists, prevent duplicates, optional note entry.
   - Remove Ticker: inline action with confirmation dialog.
   - Persist notes per ticker; autosave with toast feedback.

4. **Refresh Controls**
   - Header controls: refresh dropdown (1m, 2m, 5m, 10m, 15m) + manual refresh button + timestamp of last update.
   - Use React Query + background refetch; manual refresh forces network fetch (bypass cache).

5. **Settings Integration**
   - Settings page gains a Watchlist section (under trading preferences) with: default article count slider (5–25), refresh default selector, weighting sliders (Phase 2 ready), toggle for auto-expand on high-priority signals.
   - Settings updates stored in existing user preferences table (extend schema as needed) and reflected immediately in watchlist via context/provider.

6. **Market & Data Pipelines**
   - **Schema support**: add DuckDB tables `reference_cache` (ticker, as_of_date, payload JSON, source), `fundamentals_snapshot` (ticker, as_of_date, metric_name, metric_value, source), and `news_cache` (ticker, published_at, headline, url, sentiment_score, source, payload JSON). Backfill existing configs through `yaml_loader` so entries exist before watchlist queries run.
   - **Price metadata**: extend `PriceDataFetcher` sourcing to include FMP (and Polygon when available) so each payload contains `price`, `beta`, `volatility`, `sector`, and `52weekHigh/Low` fields. If base source omits beta/volatility, compute from cached day_bars (20/60-day stdev) during ingestion.
   - **Fundamental ingestion**: for each ticker, fetch the sector-specific metrics defined in the “Sector Fundamental Metric Map” (see Appendix) using real endpoints (FMP ratios, Polygon reference, Finnhub profile, etc.). Persist normalized values (raw + z-score vs sector median) into `fundamentals_snapshot` with `metric_basis` metadata indicating peer set and look-back period.
   - **Sentiment ingestion**: finish Feature 6 from PRD #0011 – pull latest N articles per ticker from Google News RSS, NewsAPI, Polygon, or Finnhub, deduplicate by `title+source`, score using FinBERT (primary) with optional QWEN check, and store individual scores + recency weights in `news_cache`. Maintain a materialized view for 1-day/5-day/20-day weighted averages and deltas.
   - **Refresh cadence**: schedule Celery jobs to update prices/technicals every 15 minutes (respecting API quotas), fundamentals daily (after market close), sentiment every 30 minutes (trimming to last 7 days of raw articles).

7. **Backend API**
   - Endpoints: `/api/watchlist` (GET/POST/DELETE/PATCH) for items; `/api/watchlist/refresh` to trigger data refresh job; `/api/watchlist/scores` returning latest scores for all items.
   - Cache layer: store latest scores in `watchlist_snapshots` table keyed by item and fetched_at timestamp.
   - Ensure price + indicator fetch merges multi-source data, leveraging `calculate_indicators`, `PriceDataFetcher`, and news sentiment pipeline.

8. **Dark Mode & Responsiveness**
   - All new components use existing dark theme tokens (bg levels, border, text). Table rows use subtle color steps (#111 → #151) and accessible focus rings.
   - Tablet: columns collapse to Symbol, Price, Δ%, Overall Score, Score Summary popover.
   - Mobile: stacked card layout with badges and chevron for expansion.

### Phase 2 – Scoring Intelligence & Detail
9. **Per-score Calculation Transparency**
   - Expanded row reveals sections for each score with metric tables (value, percentile vs peer, weight).
   - Include historical sparkline for price and key indicator (RSI) using 30-day data.
   - Show sector and top 3 competitor comparison (overall and component scores) with table + quick commentary.

10. **AI Insights**
   - Display AI summary paragraph with timestamp + regenerate button, leveraging existing agent infrastructure (Discovery Agent variant). Regenerate triggers Celery task and updates row on completion; show spinner while pending.
   - AI confidence displayed both in main row (numerical) and detail (explain drivers).

11. **Weight Adjustments & Ranking**
    - Watchlist settings allow user to set weight sliders (0–100%) for each component. Persist per user; default equal weighting.
    - Overall score recomputed on change; row order sorts descending by default.

12. **Competitor & Sector Data**
    - For each ticker, store peer list (top 3 by market cap within sector). Detail view surfaces competitor scores + difference relative to target.
    - Sector score derived from sector-wide metrics (momentum, breadth, sentiment) reused from analytics module.

13. **Historical Context**
    - Provide 7-day log of score changes (small timeline list) to spot trend direction.
    - Provide “alert badge” in collapsed row if any sub-score dropped or increased by >10 points since previous snapshot.

---

## 5. Non-Goals

- Executing trades or syncing with brokerage accounts.
- Portfolio auto-allocation or rebalancing from watchlist signals.
- Building multi-user sharing or exporting watchlists (optional future work).
- Supporting options/crypto fundamentals in Phase 1 (can appear later once data sources validated).
- Real-time (<1 min) streaming quotes (we stick to scheduled refresh with caching).

---

## 6. Design Considerations

All components must respect the dark theme (background #050505 → card #111, text #f3f4f6) and share typography spacing consistent with existing pages. Settings button/section stays visible in nav.

```text
Diagram A – Global Layout & Navigation (Desktop)
┌────────────────────────────────────────────────────────────────────────────┐
│ Top Nav (dark)                                                            │
│ ┌──────┐ ┌──────────┐ ┌─────────┐ ┌────────────┐ ┌──────────────┐        │
│ │Logo  │ │Dashboard │ │Portfolio│ │Watchlist ▼ │ │Settings (⚙) │        │
│ └──────┘ └──────────┘ └─────────┘ └────────────┘ └──────────────┘        │
└────────────────────────────────────────────────────────────────────────────┘
Page container provides 24px gutters (desktop), 16px (tablet), 12px (mobile). All pages—including Settings—inherit dark mode.
```

```text
Diagram B – Watchlist Page (Collapsed Rows)
Header: “Watchlist Overview”   [Add Ticker] [Refresh ↻] [Auto Refresh ▾] [Settings shortcut]
│─ Global Filters: sector chips, alert toggles
└─ Data Table (sortable)
   Symbol │ Price │ Δ% │ News Sentiment ▲ 28 (Positive) │ Technical 72 │ Fundamental 65 │ AI 78 / 0.82 │ Sector 69 │ Competitors 71 │ Overall 74
   Secondary muted line reserved for short notes placeholder (“Add note…”) to maintain row height.
   Tablet: columns collapse to Symbol, Price, Δ%, Overall Score, “Score Summary” popover.
   Mobile: cards per ticker with badges, chevron to expand.
```

```text
Diagram C – Watchlist Expanded Row (Desktop)
Main row (above) stays visible. Expanded panel content (within accordion):
1. Score Breakdown Grid (2 rows × 3 cards) showing metrics, percentiles, weights.
2. Sector & Competitor Drilldown – table of top 3 peers + narrative.
3. AI Summary block with regenerate + copy buttons.
4. Trend Area – price and RSI sparklines, data source badges, timestamp.
5. Notes editor (markdown, autosave).
Alerts appear as small accent pills (e.g., “New AI summary” / “Score -12 past 24h”).
```

```text
Diagram D – Settings Page (Dark Mode)
Settings Header (same structure as existing page, now dark themed):
┌─────────────────────────────────────────────┐
│ Watchlist Preferences                      │
│  • Refresh Interval (dropdown 1–15m)       │
│  • News Articles (slider 5–25, default 10) │
│  • Score Weights (stacked sliders, % total)│
│  • Auto-expand high alerts (toggle)        │
│ Existing sections (Risk Tolerance, Position Size, Trading Prefs) remain below. │
└─────────────────────────────────────────────┘
```

---

## 7. Technical Considerations

- **Backend Data Model**: Extend schema with
  - `watchlist_items` (id, symbol, metadata JSON, note, created_at, updated_at) and `watchlist_snapshots` (item_id FK, fetched_at, price, change_pct, beta, volatility, news_score, technical_score, fundamental_score, ai_score, ai_confidence, sector_score, competitor_score, overall_score, raw_metrics JSON).
  - `reference_cache` (ticker, as_of_date, payload JSON, source, created_at) for raw company profiles.
  - `fundamentals_snapshot` (ticker, as_of_date, metric_name, metric_value, z_score, peer_set, lookback_days, source).
  - `news_cache` (ticker, published_at, headline, url, sentiment_score, recency_weight, source, payload JSON) plus a materialized aggregate view for 1/5/20-day averages.
  - `ai_summaries` (watchlist_item_id, generated_at, summary_text, confidence, generator_id) for regenerate history.
- **Valuation & Fundamental Metrics**: Implement the full “mafia” metric grid. For each sector:
  - Retrieve the primary and secondary ratios from FMP/Polygon/Finnhub (e.g., Software: forward revenue growth, Rule-of-40 = growth + FCF margin; Banks: price/tangible book, ROE – cost_of_equity spread; Energy: EV/EBITDA at strip, proved-reserves NAV/production).
  - Compute support metrics locally when vendor data is absent (e.g., 20/60-day volatility from `day_bars`, dividend yield using trailing dividends, debt/EBITDA from balance sheet + cash flow endpoints).
  - Normalize each metric against the relevant peer universe (sector or subsector) using z-score and percentile; store both raw and normalized values in `fundamentals_snapshot` with metadata describing data source and calculation timestamp.
  - Aggregate the Fundamental Score as a weighted blend (default weights: primary 50%, secondary 30%, support 20%) with per-sector overrides if needed.
- **Sentiment Pipeline**: Use PRD #0011 Feature 6 deliverables. After ingesting articles from Google News RSS, NewsAPI, Polygon, Finnhub:
  - Deduplicate using `sha256(title + source_url)`.
  - Score each headline+summary via FinBERT (primary). If FinBERT confidence <0.55, run secondary check with QWEN sentiment tool. Persist sentiment_score (-1.0 to 1.0) and model metadata.
  - Compute weighted averages (newest article weight = 1.0, decay factor 0.85 per day) and store alongside day-over-day deltas for quick retrieval.
- **AI Integration**: Reuse Celery tasks from PRD #0013 to call headless Claude/Gemini/local model stack. Store regenerated summaries in `ai_summaries` and respect cooldown (default 5 minutes) to control compute costs.
- **Caching & TTL**: Price/indicator TTL 15 minutes with MultiSourceFetcher fallback; sentiment TTL 30 minutes; fundamental snapshot TTL 24 hours; AI summary TTL 12 hours (unless user regenerates).
- **Accessibility**: Maintain 4.5:1 contrast, keyboard focus outlines, aria labels on tables, ensure expand/collapse reachable via keyboard, provide screen-reader friendly column descriptions for score badges.
- **Testing**: Add API unit tests for watchlist endpoints, integration tests for scoring pipeline (including normalization + weighting), regression tests for sentiment aggregator, React RTL tests for table sorting/expansion/refresh controls.
- **Performance**: Favor server-side pagination if list grows >100 tickers; for MVP, load all items with virtualization (TanStack Virtual). Use DuckDB window functions/materialized views for score aggregation to keep requests <200 ms on 100-ticker watchlist.

---

## 8. Success Metrics

- Watchlist page renders within 2 seconds with live data ≤15 minutes old.
- Scores update automatically according to selected refresh interval without console errors.
- Expanded row surfaces full metric breakdown and AI summary for ≥90% of tickers (fallback state displayed otherwise).
- Settings changes (refresh interval, article count, weights) persist and reflect immediately.
- Dark-mode consistency: no light components, accessible contrast confirmed via automated checks (axe + manual spot-check).

---

## 9. Open Questions

1. Should we implement alert notifications (email/push) when overall score crosses a threshold? (Future consideration.)
2. Do we need to support bulk import/export (CSV) for watchlist tickers in Phase 2?
3. For AI regenerate, is there a cooldown per ticker to control API costs?
4. Should competitor lists be auto-derived daily or allow manual overrides?
5. How do we visualize long-term score trends (line chart vs table) beyond 7-day history? Potential Phase 3 feature.

---

**Appendix – Sector Fundamental Metric Map** (reference for devs building scoring pipeline)

| Sector/Sub-sector | Primary Metric (Weight 50%) | Secondary Metric (Weight 30%) | Support Metric (Weight 20%) | Formula / Notes |
| --- | --- | --- | --- | --- |
| Info Tech (Software) | EV/Sales (forward 12M) vs sector median | Rule-of-40 (rev growth % + FCF margin %) | Unlevered FCF margin | Use FMP `enterprise-value` + revenue guidance; compute growth using trailing four quarters; cap Rule-of-40 at 100. |
| Info Tech (Hardware/Semi) | Forward P/E (next FY) | EV/EBITDA (TTM) | FCF yield (FCF / market cap) | Pull earnings estimates from FMP; derive FCF from cash-flow statement; smooth using 3-year avg to reduce cyclicality. |
| Communication Services (Platforms) | EV/EBITDA (forward) | Forward P/E | Subscriber/MAU growth vs revenue growth delta | For streamers/social, use quarterly user metrics; compute delta = revenue growth – user growth to detect monetization. |
| Telecom | EV/EBITDA (TTM) | FCF yield | Debt/EBITDA | Include spectrum-adjusted debt from balance sheet notes; ensure FCF excludes capex deferrals. |
| Consumer Discretionary (Retail/Auto) | Forward P/E | EV/Sales | Same-store sales or unit growth | Normalise comps by region when available; fallback to revenue growth if comps missing. |
| Consumer Staples | Forward P/E | Dividend yield vs 5Y median | Gross margin stability (std dev last 8 qtrs) | Gross margin stability score = 1 / stddev%; clamp max contribution at 10. |
| Health Care (Pharma/Biotech) | EV/EBITDA (forward) + pipeline NPV coverage | Forward P/E | R&D intensity (% revenue) | Pipeline coverage = projected peak sales / current revenue; use FMP/Finnhub pipeline data where available, else default 0. |
| Health Care (Providers) | EV/EBITDA | EV/Revenue | Patient volume mix (inpatient vs outpatient growth) | Volume mix from Finnhub/SEC filings; favour outpatient growth. |
| Financials (Banks) | Price/Tangible Book | Forward P/E (using ROE target) | Net Interest Margin trend + CET1 buffer | CET1 buffer = CET1 – regulatory minimum; apply penalty if buffer <1%. |
| Financials (Insurance) | Price/Tangible Book | Forward P/E | Combined ratio (3-year avg) | Combined ratio <100 gives positive z-score; include catastrophe load adjustments for P&C. |
| Payments/Asset Managers | Forward P/E | EV/EBITDA | AUM/TPV growth (YoY) | Use share of wallet metrics where available; adjust for net inflows/outflows. |
| Energy (E&P/Majors) | EV/EBITDA (at strip) | NAV per share vs price (PV10 reserves) | FCF yield at strip prices | Revalue reserves using latest NYMEX strip; include hedges in NAV. |
| Industrials | EV/EBITDA | Forward P/E | Backlog-to-book ratio & book-to-bill trend | Backlog ratio >1 positive; include government contract adjustments. |
| Materials | EV/EBITDA | EV/EBIT | Commodity spread vs cost (rolling 3M avg) | Spread data from FMP commodity endpoints; penalize negative spreads. |
| Utilities | Dividend yield vs 5Y avg | Forward P/E | Net debt / EBITDA + regulated ROE delta | Regulated ROE delta = allowed ROE – actual ROE; negative delta penalizes score. |
| Real Estate (REITs) | Price/AFFO | NAV premium/discount | Occupancy & lease spread trend | Use sector-specific AFFO adjustments (e.g., data centers vs office) and same-property NOI growth. |
