# PRD — Equities Fear & Greed Index (stocks‑centric, cross‑asset aware)

> Portfolio AI addition: durable, transparent, stock‑first Fear & Greed (F&G) index with cross‑asset overlays. No scraping. Vendor‑agnostic. Integrates with existing FastAPI, Celery/Redis, PostgreSQL 16, and the Next.js dashboard.

---

## 1) Objective & Non‑Goals

**Objective**
Deliver a production‑grade F&G index for **equities** that:
- Mirrors the spirit of CNN’s 7‑signal index without relying on scraped data.
- Is auditable (percentiles, raw values, windows documented) and extendable (extra signals, sector/ticker variants).
- Surfaces a **composite 0–100 score**, regime label, and component breakdown, with history for backtests and alerts.

**Non‑Goals**
- Scraping third‑party sites for the composite.
- Crypto‑only index; crypto may appear *only* as an optional overlay if later shown to add explanatory power.

---

## 2) Scope

**In‑scope (v1)**
- **Core equities block (7 signals, 70% weight)**
  1. Momentum — SPX vs 125‑DMA (higher = greed)
  2. Breadth — % of S&P 500 constituents above 50‑DMA (higher = greed)
  3. Strength — NYSE 52‑wk highs − lows (higher = greed)
  4. Options positioning — Cboe **equity** put/call ratio (lower = greed)
  5. Volatility — VIX vs 50‑DMA (lower = greed)
  6. Credit stress — High‑Yield OAS (lower = greed)
  7. Safe‑haven demand — 1‑mo TR spread: SPX − IEF (higher = greed)

- **Cross‑asset overlay (3 signals, 30% weight)**
  8. MOVE (Treasury vol) — higher = fear
  9. USD broad index (DTWEXBGS) — extreme strength = fear
  10. WTI crude (level & recent spike) — extreme/rising = fear for equities ex‑Energy

- Composite score, regime label, and full component percentiles with history.
- Backfill to 10 years where data allows.

**Out‑of‑scope (v1)**
- Sector/ticker‑level F&G (paved for v2).
- Survey inputs (AAII) and funding stress (TED) — candidates for v1.1/v2.

---

## 3) Definitions & Method

**Percentile Engine**
- Window: default **10 years** rolling (fallback to min 5y if data sparse).
- For each signal *S*, compute daily raw value → transform to **empirical percentile** in [0, 100].
- **Sign convention**: invert where higher = fear (VIX, HY OAS, MOVE, PCR, USD, WTI‑spike).
- **Core score** = mean of 7 equities percentiles.
- **Overlay score** = mean of 3 cross‑asset percentiles.
- **Composite**: `FNG = 0.70*Core + 0.30*Overlay`.

**Regime Bands**
- 0–25: Extreme Fear
- 25–45: Fear
- 45–55: Neutral
- 55–75: Greed
- 75–100: Extreme Greed

**Data cadence**
- **Nightly post‑close** compute (primary).
- **Intraday nowcast** (optional flag): recompute fast‑moving subset (SPX, VIX, PCR) and mark as `provisional=true`.

---

## 4) Architecture Fit

**Existing alignment**
- Uses FRED API (already listed), Cboe stats, and price vendors via the **Price Fetcher** failover stack (yfinance → Polygon → TwelveData → FMP → Finnhub → AlphaVantage).
- Fits with **Celery** (scheduled tasks), **Redis** (status/locks), **PostgreSQL 16** (history, components, inputs), **FastAPI** (new Market routes), and **Next.js** (dashboard tile + drawer).

**New modules**
- `app/market/fng/engine.py` — percentile transforms, composition, labeling.
- `app/market/fng/sources.py` — small fetchers: HY OAS (FRED), MOVE (vendor/FRED proxy), USD (FRED), WTI (FRED), put/call + VIX (Cboe/vendor), SPX vs IEF TR calc.
- `app/market/fng/service.py` — orchestration (load inputs → compute → persist) with idempotent writes.

---

## 5) API Design (FastAPI)

**Routes** (Market Router)
- `GET /api/market/fng`
  **Query**: `date?`, `include_components?=false`, `provisional_ok?=true`
  **Resp**: `{ date, score, label, core, overlay, provisional }` (+ components if requested).

- `GET /api/market/fng/history`
  **Query**: `start`, `end`, `granularity=daily`
  **Resp**: `[{ date, score, label, core, overlay }]`.

- `GET /api/market/fng/components`
  **Query**: `date?`
  **Resp**: `{ date, components: [{key, raw, pct, window_days}] }`.

**Pydantic models**
- `FNGReading`, `FNGComponent`, `FNGHistoryItem`, `FNGResponse`.

**Error codes**
- `424 FAILED_DEPENDENCY` when upstreams all fail; return last good with `stale=true`.

---

## 6) Data Model (PostgreSQL 16)

**New tables**
```sql
CREATE TABLE fng_inputs_daily (
  as_of_date date PRIMARY KEY,
  spx_close double precision NOT NULL,
  spx_ma125 double precision,
  pct_above_50dma double precision,
  nyse_52w_highs integer,
  nyse_52w_lows integer,
  equity_put_call double precision,
  vix_close double precision,
  hy_oas double precision,
  spy_tr_1m double precision,
  ief_tr_1m double precision,
  move_index double precision,
  usd_broad double precision,
  wti_spot double precision,
  wti_20d_chg double precision,
  source_map jsonb DEFAULT '{}'::jsonb,  -- provider per field
  created_at timestamptz DEFAULT now()
);

CREATE TABLE fng_components_daily (
  as_of_date date PRIMARY KEY,
  momentum_pct smallint,
  breadth_pct smallint,
  strength_pct smallint,
  pcr_pct smallint,
  vix_pct smallint,
  hy_pct smallint,
  haven_pct smallint,
  move_pct smallint,
  usd_pct smallint,
  wti_pct smallint,
  window_days int,
  provisional boolean DEFAULT false,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE fng_equities_daily (
  as_of_date date PRIMARY KEY,
  core double precision NOT NULL,
  overlay double precision NOT NULL,
  score double precision NOT NULL,
  label text CHECK (label IN ('Extreme Fear','Fear','Neutral','Greed','Extreme Greed')),
  provisional boolean DEFAULT false,
  stale boolean DEFAULT false,
  created_at timestamptz DEFAULT now()
);

CREATE INDEX idx_fng_equities_daily_date ON fng_equities_daily(as_of_date DESC);
```

**Rationale**
- `inputs` preserves auditable raw series per day.
- `components` stores percentiles (window captured).
- `equities_daily` is the published composite.

**Migrations**
- Single migration file adding the three tables + index.
- Add grants for `portfolio_ai_user`.

---

## 7) ETL & Scheduling (Celery/Redis)

**Celery Beat entries**
- `compute_fng_daily` — run at 22:30 ET (post close + buffers).
- `compute_fng_nowcast` (optional) — run hourly 10:00–16:00 ET with `provisional=true`.

**Task flow**
1. Acquire Redis lock `lock:fng:YYYY‑MM‑DD`.
2. Fetch inputs with resilience: price fetcher stack for SPX/IEF/constituents; FRED for HY OAS, USD, WTI; Cboe/vendor for VIX & equity PCR; vendor for MOVE (or proxy via available source).
3. Compute derived fields: MA125, %above50, 1‑mo TRs, WTI 20‑day change.
4. Persist to `fng_inputs_daily`.
5. Run percentile engine (10y window): write `fng_components_daily`.
6. Compose core/overlay/composite + labels → upsert `fng_equities_daily`.
7. Emit telemetry.

**Retries & fallbacks**
- If one upstream fails, compute from others; if all fail, carry‑forward last values and set `stale=true`.

---

## 8) Frontend (Next.js 14 + shadcn/ui)

**Dashboard tile (L)**
- Circular gauge 0–100 with color bands; regime chip.
- 90‑day sparkline (score).
- Tooltip with last 5 regime crossings.

**Detail drawer**
- 10 mini‑cards (7 core + 3 overlay) with: raw value, percentile, 1‑yr sparkline, source icon.
- Toggle to show `provisional` badge during market hours.

**History view**
- Chart score vs SPX; regime heatmap; distribution of forward returns by regime (1/3/6/12m).
- Export CSV.

**Alerts**
- User toggles: Cross ≤25, ≥75 with hysteresis (2 consecutive closes).
- Delivery: toast in‑app now; webhooks/Email/SMS later.

---

## 9) Integration Points

- **Market Router**: new endpoints as above.
- **Watchlist Intelligence Hub**: show current F&G chips beside symbols; use regime in narrative templates (e.g., risk budget tighter in fear regimes).
- **Agents**: feed `FNG label` to Discovery/Portfolio Analyzer prompts as `market_regime` for context/guardrails.
- **Idea outcomes/backtests**: slice performance by regime.

---

## 10) Telemetry & Observability

- `metrics:fng:compute_seconds`, `metrics:fng:inputs_missing_count`, `metrics:fng:upstream_failures{source=}`, `metrics:fng:stale_flag`.
- Structured logs include component raw values, percentiles, and window length.
- Health Dashboard: add F&G card (last compute time, status, provisional/stale flags).

---

## 11) Testing Strategy

- **Unit**: percentile math, label boundaries, sign inversions.
- **Integration**: ETL pipeline with mocked providers + carry‑forward logic.
- **Contract**: API schemas & error cases.
- **Determinism**: golden files for sample windows.

---

## 12) Security & Cost

- All upstream calls via existing credential stores; no secrets in code.
- Respect provider TOS; no scraping.
- FRED heavy lifting is free; vendor calls cached via existing price cache.

---

## 13) Rollout Plan

- **D0**: Schema migration, ETL, API read‑only, tile (behind `feature_fng=true`).
- **D+7**: Enable alerts; add regime chips to Watchlist.
- **D+30**: Forward‑return distributions by regime; add AAII/TED (if desired).

---

## 14) Appendix

**Component keys**
- `momentum`, `breadth`, `strength`, `pcr`, `vix`, `hy`, `haven`, `move`, `usd`, `wti`.

**Label mapping**
```json
[
  {"min":0,  "max":25,  "label":"Extreme Fear"},
  {"min":25, "max":45,  "label":"Fear"},
  {"min":45, "max":55,  "label":"Neutral"},
  {"min":55, "max":75,  "label":"Greed"},
  {"min":75, "max":100, "label":"Extreme Greed"}
]
```

**Pseudocode (engine)**
```python
p = percentile(value=today, series=last_10y, invert=flag)
core = mean([p.momentum, p.breadth, p.strength, p.pcr, p.vix, p.hy, p.haven])
overlay = mean([p.move, p.usd, p.wti])
score = 0.7*core + 0.3*overlay
label = bucket(score)
```

**Future (v2)**
- Sector and theme F&G (AI basket, small caps).
- Options skew (25Δ) as 8th core dial.
- Funding stress (TED), curve shape (2s10s z‑score).
- Ticker‑level F&G for portfolio names.

---

## 15) Deliverables (Engineering Handoff)

1. **DB Migration**: SQL file creating `fng_inputs_daily`, `fng_components_daily`, `fng_equities_daily` (with indexes, comments, grants).
2. **ETL Package**: `app/market/fng/{sources.py, engine.py, service.py, tasks.py}` with unit tests and mocks.
3. **API Layer**: `app/api/market_fng.py` (routers) + `app/models/fng.py` (Pydantic).
4. **Frontend**: `apps/web/components/fng/{FngGauge.tsx, FngMiniCard.tsx, FngHistory.tsx}` + page integration and TanStack Query hooks.
5. **Ops**: Celery Beat schedule entry, Redis lock key policy, health‑dashboard widget, docs page.

---

## 16) Acceptance Criteria

**Compute**
- AC‑C1: Daily job computes **all 10 components** using defined formulas and stores raw + percentiles for the same `as_of_date`.
- AC‑C2: Percentiles use a **rolling 10‑year window** (≥ 2520 trading days when available; ≥ 1260 if history shorter).
- AC‑C3: Composite score = `0.70*core + 0.30*overlay` with rounding to **one decimal**; regime label applied per bands.
- AC‑C4: If ≥1 upstream missing, compute with remaining data; if **all** upstreams for any required component fail → carry‑forward last value, set `stale=true`, return **HTTP 424** for `GET /api/market/fng` unless `provisional_ok=true`.
- AC‑C5: Intraday nowcast (if enabled) sets `provisional=true` and **never overwrites** nightly values.

**API**
- AC‑A1: `GET /api/market/fng` returns `{date, score, label, core, overlay, provisional, stale}` within **100 ms** from cache when hot.
- AC‑A2: `GET /api/market/fng/components` returns the 10 components with `{key, raw, pct, window_days, source}`.
- AC‑A3: `GET /api/market/fng/history?start=YYYY‑MM‑DD&end=YYYY‑MM‑DD` returns daily series; supports CSV via `Accept: text/csv`.

**Frontend**
- AC‑F1: Dashboard tile renders gauge (0–100) + 90‑day sparkline; shows **chip** for regime; shows **Provisional** pill when applicable.
- AC‑F2: Drawer renders 10 mini‑cards with **raw value**, **percentile**, **1‑yr sparkline**, and **source icon** (FRED/Cboe/vendor).
- AC‑F3: History view overlays score vs SPX and shows regime heatmap; export CSV works.
- AC‑F4: Alerts: if enabled, user receives an in‑app toast when score crosses ≤25 or ≥75 for **2 consecutive closes** (hysteresis).

**Quality**
- AC‑Q1: 80%+ unit test coverage for fng engine and tasks; golden‑file tests for two known market dates.
- AC‑Q2: Pydantic validation; typed code; ruff/mypy clean.
- AC‑Q3: Structured logs include component raw/pct and window; traces for upstream calls.

---

## 17) Data Sources & Exact Formulas

### 17.1 Inputs & providers
| Key | Description | Source (preferred) | Fallback / Notes |
|---|---|---|---|
| `spx_close` | S&P 500 close | Price Fetcher (yfinance→Polygon→…) | Ticker `^GSPC` or `SPX` vendor symbol |
| `spx_ma125` | 125‑D MA of SPX | Derived | SMA(125) over `spx_close` |
| `pct_above_50dma` | % S&P 500 constituents above 50‑DMA | Internal compute | Use current S&P 500 membership snapshot; for each member: close > SMA(50) → ratio |
| `nyse_52w_highs/lows` | NYSE new 52‑wk highs/lows count | Vendor breadth feed | If unavailable, proxy using major‑cap universe; document provider |
| `equity_put_call` | Cboe **Equity‑only** put/call ratio (daily) | Cboe | Cache in `reference_cache` 24h |
| `vix_close` | Cboe VIX close | Cboe/vendor | |
| `hy_oas` | ICE BofA US High‑Yield OAS (daily) | FRED `BAMLH0A0HYM2` | |
| `spy_tr_1m` | 1‑mo total return of SPY | Derived | Use dividends if available; else price‑only approximation |
| `ief_tr_1m` | 1‑mo total return of IEF | Derived | Include dividends if available |
| `move_index` | Treasury volatility | Vendor (MOVE) **or** proxy | If MOVE unavailable, compute **proxy**: 20‑day realized vol of daily Δ10y yield (`DGS10`) scaled to index‑like levels |
| `usd_broad` | Broad USD index | FRED `DTWEXBGS` | |
| `wti_spot` | WTI crude spot | FRED `DCOILWTICO` | |
| `wti_20d_chg` | 20‑day % change in WTI | Derived | `(WTI_t / WTI_t‑20)‑1` |

> **MOVE proxy (if needed):** `rv10y = stdev(Δ DGS10, 20) * sqrt(252) * 100`; normalize via 10‑year percentile like others.

### 17.2 Component definitions
- **Momentum (greed)**: `pct_momentum = pct_rank( (spx_close / spx_ma125) - 1 )`.
- **Breadth (greed)**: `pct_breadth = pct_rank( pct_above_50dma )`.
- **Strength (greed)**: `pct_strength = pct_rank( nyse_52w_highs - nyse_52w_lows )`.
- **PCR (fear)**: `pct_pcr = 100 - pct_rank( equity_put_call )`.
- **VIX (fear)**: `vix_rel = vix_close / SMA_50(vix_close)` → `pct_vix = 100 - pct_rank(vix_rel)`.
- **HY OAS (fear)**: `pct_hy = 100 - pct_rank( hy_oas )`.
- **Safe‑haven (greed)**: `haven = spy_tr_1m - ief_tr_1m` → `pct_haven = pct_rank(haven)`.
- **MOVE (fear)**: `pct_move = 100 - pct_rank(move_index_or_proxy)`.
- **USD (fear)**: `pct_usd = 100 - pct_rank( zscore_tail(usd_broad) )` with tail emphasis (e.g., winsorize 1% tails), or simply `100 - pct_rank(usd_broad)`.
- **WTI (fear)**: combine **level** and **20d change**: `wti_score = 0.5*pct_rank(wti_spot) + 0.5*pct_rank(wti_20d_chg)` → `pct_wti = 100 - wti_score`.

**Percentile spec**
- `pct_rank(x_t) = 100 * ECDF_{window}(x_t)`; window = last N valid daily values (default 2520).
- Missing data handling: forward‑fill up to 5 trading days; beyond that, mark component as missing for AC‑C4 logic.
- Winsorize each series at 0.5%/99.5% prior to ECDF to reduce tail shock.

---

## 18) API Schemas & Examples

### 18.1 OpenAPI snippets (Pydantic)
```python
class FNGComponent(BaseModel):
    key: Literal['momentum','breadth','strength','pcr','vix','hy','haven','move','usd','wti']
    raw: float | None
    pct: int | None  # 0..100
    window_days: int | None
    source: str | None

class FNGReading(BaseModel):
    date: date
    score: float
    label: Literal['Extreme Fear','Fear','Neutral','Greed','Extreme Greed']
    core: float
    overlay: float
    provisional: bool = False
    stale: bool = False

class FNGResponse(BaseModel):
    reading: FNGReading
    components: list[FNGComponent] | None = None
```

### 18.2 REST
- `GET /api/market/fng?include_components=true`
```json
{
  "reading": {
    "date": "2025-11-05",
    "score": 61.2,
    "label": "Greed",
    "core": 63.5,
    "overlay": 56.0,
    "provisional": false,
    "stale": false
  },
  "components": [
    {"key":"momentum","raw":0.043,"pct":68,"window_days":2520,"source":"yfinance"},
    {"key":"pcr","raw":0.59,"pct":72,"window_days":2520,"source":"cboe"},
    {"key":"move","raw":88.1,"pct":38,"window_days":2520,"source":"proxy:dgs10rv"}
  ]
}
```

- `GET /api/market/fng/history?start=2020-01-01&end=2025-11-06`
```json
[
  {"date":"2025-11-01","score":58.7,"label":"Greed","core":60.1,"overlay":55.3},
  {"date":"2025-11-04","score":60.9,"label":"Greed","core":63.0,"overlay":56.2}
]
```

- CSV variant (header): `date,score,label,core,overlay`.

- Errors: `424 FAILED_DEPENDENCY` with body `{ "error":"upstreams_failed","last_good":"2025-11-04" }`.

---

## 19) Migration Script (ready‑to‑run)

```sql
-- 0015_fng.sql
BEGIN;

CREATE TABLE IF NOT EXISTS fng_inputs_daily (
  as_of_date date PRIMARY KEY,
  spx_close double precision NOT NULL,
  spx_ma125 double precision,
  pct_above_50dma double precision,
  nyse_52w_highs integer,
  nyse_52w_lows integer,
  equity_put_call double precision,
  vix_close double precision,
  hy_oas double precision,
  spy_tr_1m double precision,
  ief_tr_1m double precision,
  move_index double precision,
  usd_broad double precision,
  wti_spot double precision,
  wti_20d_chg double precision,
  source_map jsonb DEFAULT '{}'::jsonb,
  created_at timestamptz DEFAULT now()
);

COMMENT ON TABLE fng_inputs_daily IS 'Raw daily inputs for Fear & Greed computation with provider mapping.';

CREATE TABLE IF NOT EXISTS fng_components_daily (
  as_of_date date PRIMARY KEY,
  momentum_pct smallint,
  breadth_pct smallint,
  strength_pct smallint,
  pcr_pct smallint,
  vix_pct smallint,
  hy_pct smallint,
  haven_pct smallint,
  move_pct smallint,
  usd_pct smallint,
  wti_pct smallint,
  window_days int,
  provisional boolean DEFAULT false,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS fng_equities_daily (
  as_of_date date PRIMARY KEY,
  core double precision NOT NULL,
  overlay double precision NOT NULL,
  score double precision NOT NULL,
  label text CHECK (label IN ('Extreme Fear','Fear','Neutral','Greed','Extreme Greed')),
  provisional boolean DEFAULT false,
  stale boolean DEFAULT false,
  created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_fng_equities_daily_date ON fng_equities_daily(as_of_date DESC);

COMMIT;
```

---

## 20) Celery & Services

**Beat config (YAML or Python)**
```python
CELERY_BEAT_SCHEDULE.update({
  'compute_fng_daily': {
    'task': 'app.market.fng.tasks.compute_fng_daily',
    'schedule': crontab(hour=22, minute=30, timezone='America/New_York')
  },
  'compute_fng_nowcast': {
    'task': 'app.market.fng.tasks.compute_fng_nowcast',
    'schedule': crontab(minute='0', hour='10-16', timezone='America/New_York')
  }
})
```

**Task skeleton**
```python
@celery_app.task(bind=True)
def compute_fng_daily(self):
    with redis_lock('fng:'+today()):
        inputs = fetch_inputs(date=today())
        upsert_inputs(inputs)
        comps = compute_components(inputs, window_years=10)
        upsert_components(comps)
        reading = compose_reading(comps)
        publish_reading(reading)
```

---

## 21) Frontend Contracts

**Hooks**
```ts
export function useFng(){ /* GET /api/market/fng */ }
export function useFngHistory(params){ /* GET /api/market/fng/history */ }
```

**Components**
- `FngGauge`: props `{ score:number; label:string; provisional?:boolean }`.
- `FngMiniCard`: props `{ keyId:string; raw:number; pct:number; source:string }`.
- `FngHistory`: props `{ items: {date:string; score:number}[] }`.

**UX details**
- Color bands map to regimes; sparkline uses `score` history; drawer mini‑cards sort by **contribution to score** (descending).

---

## 22) Testing Plan (explicit cases)

**Golden dates** (update with true values once wired):
- 2020‑03‑23 (COVID crash low): Expect `score < 10` and `label = Extreme Fear`; VIX & HY OAS percentiles near 100 (fear‑inverted percentiles → low contributions).
- 2021‑11‑08 (peak bullish): Expect `score > 80`, `label = Extreme Greed`; momentum/breadth/strength high.

**Unit cases**
- Sign inversion correctness (VIX/HY/PCR/MOVE/USD/WTI).
- Edge windows (exactly 5y history).
- Carry‑forward & `stale` flag when all upstreams fail.
- Hysteresis alert logic.

**Integration**
- Mock FRED/Cboe/vendor; assert DB writes; idempotent upserts.

---

## 23) Work Breakdown (tickets)

1. **DB‑015**: Add migration `0015_fng.sql`; apply in all envs.
2. **ETL‑201**: Implement `sources.py` (FRED, Cboe, prices, MOVE proxy).
3. **ETL‑202**: Implement `engine.py` (percentiles, composition, labels).
4. **ETL‑203**: Implement `service.py` (idempotent compute + persistence).
5. **API‑301**: Add routers + models; OpenAPI docs + error handling.
6. **WEB‑401**: Gauge + sparkline tile; drawer + mini‑cards; history view.
7. **OPS‑501**: Celery Beat entries; Redis lock policy; Health card.
8. **QA‑601**: Unit/integration tests; golden dates; load test API; docs update.

**Estimate**: 3–5 dev‑days for v1 across BE/FE if signals are already available from providers; +1‑2 days if MOVE proxy required.
