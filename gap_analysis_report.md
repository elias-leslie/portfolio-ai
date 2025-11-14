# Gap Analysis Report

## Methodology

- Reviewed the FastAPI backend, Celery tasks, data-source adapters, and supporting docs in this repository with a focus on `app/sources`, `app/portfolio`, `app/watchlist`, and `app/tasks`.
- Traced how data flows from external feeds into internal tables (`price_cache`, `day_bars`, `technical_indicators`, `fear_greed_inputs`, `options_market_metrics`, etc.) and how analytics consume those tables.
- Compared the implemented calculations with peer‑reviewed research on market microstructure, risk modeling, and signal construction to identify strengths, gaps, and required datasets.

## Findings

### 1. Price & Market Data Foundation

**What’s working**

- The price fetcher wires up six vendors with structured failover, so outages on any one feed do not halt the platform (`backend/app/portfolio/price_fetcher.py:57-107`).  
- Equity and macro tickers are auto-backfilled via Celery (`backend/app/watchlist/refresh_builders.py:127-174`, `backend/app/tasks/market_data_tasks.py:57-214`), which keeps the daily history tables healthy without manual intervention.

**Gaps**

- `PriceDataFetcher` only requests the `reference` dataset and stores a single snapshot per symbol (`backend/app/portfolio/price_fetcher.py:205-241`), while the `PriceData` model has no fields for intraday OHLC, volume, or bid/ask data (`backend/app/portfolio/models.py:37-47`). Although the schema defines a `minute_bars` table (`docs/core/ARCHITECTURE.md:239`), the ingestion task never requests `dataset="minute"` (`backend/app/tasks/data_ingestion_tasks.py:332-350`), leaving short-horizon signals or realized volatility calculations impossible. High-frequency realized volatility materially improves risk forecasts, so relying on end-of-day data forfeits edge [1].
- Vendor-derived betas/volatility are accepted as-is, despite well-known noise in Yahoo! Finance’s `info` payload, and there is no data quality filter before caching (`backend/app/portfolio/price_fetcher.py:205-250`).

**Needed data/calculations**

- Capture full OHLCV history (daily + minute) for every traded symbol and persist realized volatility/volume percentiles so intraday-aware risk models can be built, in line with Andersen et al. (2003) [1].

### 2. Portfolio Risk & Analytics

**What’s working**

- The analytics layer already computes concentration metrics, Sharpe ratio, and a basic risk profile (`backend/app/portfolio/analytics.py:124-170`, `backend/app/portfolio/analytics_risk.py:120-205`), which is a solid baseline for user feedback.

**Gaps**

- Portfolio beta and volatility are computed as simple value-weighted averages of per-security betas/vols (`backend/app/portfolio/analytics_returns.py:67-126`). This implicitly assumes every holding is perfectly correlated with the rest, which contradicts mean-variance portfolio theory [2] and materially overstates diversified risk.
- When vendor betas are missing, the system re-computes them from only ~90 trading days of local data against SPY (`backend/app/portfolio/price_fetcher.py:57-58` and `324-385`). Short windows inflate estimation error, and literature shows beta estimates mean-revert toward one unless you shrink them with longer samples or Bayesian techniques [3].
- No factor exposure, sector tilt, or style decomposition is produced even though widely accepted factors (value, size, momentum, quality) drive returns [8]. `PortfolioAnalytics.calculate_full_analytics` ends after basic beta/volatility/sector stats (`backend/app/portfolio/analytics.py:124-170`).

**Needed data/calculations**

- Persist a covariance matrix (or at least pairwise correlations) from `day_bars` so volatility can be computed with proper cross-terms [2].
- Extend beta estimation to multi-year windows with shrinkage toward cross-sectional means per Blume (1975) [3].
- Join holdings with Fama-French style factors or internal fundamental factors to expose multi-factor risk contributions [8].

### 3. Fundamental & Alternative Data

**What’s working**

- Fundamental fetchers already fail over between Yahoo!, Finnhub, and FMP (`backend/app/watchlist/fundamentals.py:238-261`), and results are cached in `reference_cache`.

**Gaps**

- `FundamentalData` holds only profit margin, revenue growth, debt/equity, and analyst opinion (`backend/app/watchlist/fundamentals.py:37-53`). The valuation score explicitly notes a TODO for P/E, P/B, and PEG integration (`backend/app/watchlist/fundamentals.py:307-331`), and there is no support for accruals, cash conversion, earnings revisions, or share repurchase data even though those signals materially improve stock selection [4].
- Earnings calendar handling grabs only the next date (`backend/app/watchlist/refresh_data_fetchers.py:213-236`) but never stores surprises or revision momentum, leaving the system blind to one of the most persistent equity premia [4].

**Needed data/calculations**

- Expand the fundamental schema to include cash-flow ratios, accrual quality, earnings revisions, and payout metrics, enabling Piotroski-style composite scores [4].
- Tie earnings surprise data into watchlist scoring and agent prompts.

### 4. Signal Engine & Watchlist Scoring

**What’s working**

- The refresh pipeline batches price/news/technical data, queues historical backfills when needed, and logs metadata for every component (`backend/app/watchlist/scoring_service.py:148-248`, `backend/app/watchlist/refresh_builders.py:127-174`).

**Gaps**

- The price pillar scores only the most recent percent change and clamps it between ±20% (`backend/app/watchlist/scoring.py:39-103`), ignoring any multi-week momentum, relative strength vs sector, or volatility-adjusted moves. Academic evidence shows predictive power comes from 3–12 month momentum rather than 1-day noise [5].
- Signal classification is a set of hard thresholds on EMA(20), SMA(5), RSI(14), simple volume ratio, a binary company-health flag, and coarse news sentiment (`backend/app/watchlist/signal_classifier.py:92-207`). There is no aggregation of multiple lookback horizons, breadth indicators, or pair-relative signals, which limits edge.
- News sentiment is fetched, but it never becomes its own score pillar—only a modifier in heuristics—so the system cannot surface pure macro/news-driven trades even though textual tone adds incremental alpha [7].

**Needed data/calculations**

- Persist multi-horizon momentum (e.g., 10/40/120-day), percentile-based volume shocks, and relative performance vs sector ETFs to align with momentum research [5].
- Promote news (and eventually options flow) to first-class scoring pillars so signals can explicitly trade information shocks [7].

### 5. Macro & Sentiment Layers

**What’s working**

- `fetch_options_activity_metrics` scrapes CBOE “Most Active” data and normalizes near-term versus longer-dated flows plus sector concentration (`backend/app/tasks/market_data_tasks.py:305-389`), providing valuable derivative sentiment.

**Gaps**

- Fear & Greed inputs rely on a manual script that “uses reasonable estimates” for VIX and high-yield spread when data is missing (`backend/scripts/update_fear_greed_inputs.py:191-199`). Synthetic fear gauges contradict Whaley’s guidance that the official VIX is the investor fear proxy [7], so any downstream score can be materially off.
- Option-flow metrics are collected but never influence alerts or analytics; the only consumer is the `/api/market/conditions` response builder (`backend/app/api/market.py:388-420`). Pan & Poteshman (2006) show option volume imbalances predict stock returns [6], so leaving these metrics unused in signals forfeits an empirically proven edge.

**Needed data/calculations**

- Automate VIX and credit-spread ingestion directly from exchange or FRED endpoints so Fear & Greed inputs never rely on static defaults [7].
- Feed `options_market_metrics` into watchlist scoring/agents (e.g., as a contrarian filter) per the predictive evidence in option volumes [6].

### 6. Execution & Risk Controls

**What’s working**

- When technical data exists, stop losses are set at entry − 2×ATR using cached indicators (`backend/app/analytics/trade_calculations.py:33-56`), which is a reasonable volatility-aware heuristic.

**Gaps**

- If ATR data is missing, every trade defaults to a flat 5% stop (`backend/app/analytics/trade_calculations.py:58-74`), ignoring each asset’s volatility regime and correlation to the rest of the book; that directly conflicts with basic risk-parity principles [2].
- Position sizing pulls a single `watchlist_risk_budget` value from preferences (default $500) with no linkage to account equity, exposure, or symbol-level liquidity (`backend/app/utils/preferences_loader.py:32-97`). Without tying risk to portfolio value or volatility, bet size drifts away from the intended budget [2][3].

**Needed data/calculations**

- Derive allowable risk per trade from account equity, realized volatility, and correlation (e.g., via conditional VaR) instead of a flat dollar preference.
- Incorporate transaction cost and liquidity data (average dollar volume, spread) before emitting recommended share counts to avoid un-executable orders.

## Recommendations

1. **Broaden the market data lake**  
   - Enable `minute_bars` ingestion, store realized volatility/volume curves, and track data quality per source so short-horizon analytics can run on reliable feeds.

2. **Upgrade portfolio risk math**  
   - Persist covariance matrices, implement longer-horizon/shrunk betas, and expose factor tilts so risk dashboards reflect true diversification benefits.

3. **Expand fundamentals & alternative signals**  
   - Extend `FundamentalData` with cash-flow, accrual, revision, and payout metrics, and calculate composite health/valuation scores instead of single ratios.

4. **Modernize signal scoring**  
   - Replace single-day price scoring with multi-horizon momentum, add sector-relative strength and news/option pillars, and calibrate thresholds with historical percentiles rather than fixed cutoffs.

5. **Harden macro & sentiment inputs**  
   - Automate VIX/credit data ingestion, backfill `fear_greed_inputs` via scheduled Celery tasks, and wire option-flow metrics into watchlist and agent prompts.

6. **Anchor execution risk to the portfolio**  
   - Compute position sizes from user equity, ATR, and covariance, and only fall back to percentage stops when volatility data truly cannot be retrieved.

## References

[1] Andersen, T. G., T. Bollerslev, F. X. Diebold, and P. Labys (2003). “Modeling and Forecasting Realized Volatility.” *Econometrica* 71(2), 579–625.  
[2] Markowitz, H. (1952). “Portfolio Selection.” *Journal of Finance* 7(1), 77–91.  
[3] Blume, M. E. (1975). “Betas and Their Regression Tendencies.” *Journal of Finance* 30(3), 785–795.  
[4] Piotroski, J. D. (2000). “Value Investing: The Use of Historical Financial Statement Information to Separate Winners from Losers.” *Journal of Accounting Research* 38, 1–41.  
[5] Jegadeesh, N., and S. Titman (1993). “Returns to Buying Winners and Selling Losers: Implications for Stock Market Efficiency.” *Journal of Finance* 48(1), 65–91.  
[6] Pan, J., and A. M. Poteshman (2006). “The Information in Option Volume for Future Stock Prices.” *Journal of Finance* 61(3), 871–907.  
[7] Whaley, R. E. (2000). “The Investor Fear Gauge.” *Journal of Portfolio Management* 26(3), 12–17.  
[8] Fama, E. F., and K. R. French (1993). “Common Risk Factors in the Returns on Stocks and Bonds.” *Journal of Financial Economics* 33(1), 3–56.
