# PRD #0019: Watchlist Intelligence Layer - Complete Phase 2 with Actual Data

**Status**: Ready for Implementation (Blocked by PRD #0018)
**Owner**: Portfolio AI Platform
**Created**: 2025-10-30
**Audience**: Junior developers
**Priority**: HIGH
**Complexity**: MEDIUM-HIGH
**Dependencies**: PRD #0018 (refresh infrastructure fixes - REQUIRED), PRD #0014 Phase 1 (complete), PRD #0011 (85% complete)

---

## 1. Introduction / Overview

The Watchlist Intelligence Hub currently displays real-time price data and technical indicators, but lacks the intelligence layer that makes scores meaningful. This PRD completes Phase 2 by adding:

- **Historical data backfill** (60 days OHLCV) to enable technical indicator calculations
- **News sentiment scoring** using locally-hosted FinBERT model for ticker-specific sentiment
- **Fundamental metrics** (simplified P/E, EV/EBITDA, FCF yield) from existing multi-source APIs
- **Complete scoring system** that combines price, technical, fundamental, and sentiment into actionable overall scores

This builds on the existing Phase 1 foundation (database schema, API endpoints, frontend UI) and PRD #0011's multi-source infrastructure to deliver a fully functional watchlist with real, non-zero scores.

**Current State**:
- ✅ Watchlist CRUD operational with real price data ($269.70 for AAPL, beta 1.094, volatility 0.377)
- ✅ Database schema complete (watchlist_items, watchlist_snapshots, reference_cache)
- ✅ Frontend UI complete with sparklines, expanded rows, auto-refresh
- ❌ **All scores show 0.0** because historical data and sentiment pipeline are missing

**Target State**:
- Users see non-zero scores (technical 65-85, fundamental 55-75, sentiment -20 to +30, overall 60-80)
- Scores update automatically every 15 minutes with fresh data
- Historical sparklines show 30-day price/RSI trends
- News sentiment reflects last 10 articles with weighted averages

---

## 2. Goals

1. **Enable technical scoring** by backfilling 60 days of historical OHLCV data and calculating indicators (RSI, MACD, SMA, EMA)
2. **Implement sentiment scoring** using FinBERT on latest news articles from free sources (Google News RSS, existing API integrations)
3. **Add fundamental metrics** using existing FMP/Polygon/Finnhub APIs (P/E, EV/EBITDA, FCF yield)
4. **Deliver non-zero scores** that combine all components into meaningful overall scores visible in UI
5. **Maintain 80%+ test coverage** with comprehensive unit and integration tests
6. **Document data flow** in ARCHITECTURE.md showing how multi-source data feeds scoring pipeline

---

## 3. User Stories

- **As a user**, I want to see technical scores (65-85) based on RSI/MACD indicators so I can identify overbought/oversold conditions
- **As a user**, I want to see sentiment scores reflecting recent news so I can gauge market perception before the market moves
- **As a user**, I want to see fundamental scores comparing valuation metrics so I can identify value opportunities
- **As a user**, I want an overall score that combines all factors so I can quickly prioritize which tickers deserve attention
- **As a developer**, I want comprehensive tests covering the scoring pipeline so regressions are caught immediately

---

## 4. Functional Requirements

### 4.1 Historical Data Backfill & Technical Indicators

**4.1.1** Create `backfill_historical_data.py` script that:
- Accepts ticker symbols from watchlist_items table
- Fetches 60 days of OHLCV data using existing MultiSourceFetcher (priority: YFinance → TwelveData → FMP → Polygon)
- Stores results in day_bars table with proper PostgreSQL types (TIMESTAMPTZ, DOUBLE PRECISION)
- Handles rate limiting (batch_size=20, delay=2s between batches)
- Logs progress and errors using existing structlog infrastructure

**4.1.2** Extend `calculate_indicators()` function to:
- Accept ticker symbol and date range parameters
- Calculate RSI (14-period), MACD (12/26/9), SMA-50, SMA-200, EMA-20
- Return indicator values with metadata (calculation_date, source_data_count)
- Cache results in technical_indicators table with 24-hour TTL

**4.1.3** Update `WatchlistService.calculate_scores()` to:
- Compute technical_score from indicators:
  - RSI: 30-40 = +20 pts, 40-60 = +10 pts, 60-70 = +20 pts (scale 0-100)
  - MACD cross: bullish +15 pts, bearish -15 pts
  - Price vs SMA-200: above +10 pts, below -10 pts
  - Normalize to 0-100 scale, default 50 if insufficient data

**4.1.4** Schedule Celery task `refresh_indicators_task`:
- Runs daily at 6 PM ET (after market close)
- Updates indicators for all watchlist tickers
- Respects API quotas (max 50 tickers/day, log warning if exceeded)

### 4.2 News Sentiment Scoring Pipeline

**4.2.1** Create `sentiment_analyzer.py` module with:
- `setup_finbert()` function: downloads FinBERT model (ProsusAI/finbert) to `~/.cache/huggingface/`
- `score_headline(text: str) → float` function: returns -1.0 to 1.0 sentiment score
- Batch processing support (process 10 headlines at once for efficiency)
- Fallback to VADER sentiment if FinBERT fails or unavailable

**4.2.2** Create `news_ingestion.py` service that:
- Fetches latest news from Google News RSS (free, no API key)
  - URL: `https://news.google.com/rss/search?q={ticker}+stock&hl=en-US&gl=US&ceid=US:en`
- Deduplicates using SHA256(title + source)
- Scores each article with FinBERT
- Stores in news_cache table (ticker, published_at, headline, url, sentiment_score, source)
- Maintains rolling 30-day window (deletes older entries)

**4.2.3** Create `sentiment_aggregator.py` that:
- Computes weighted average sentiment for last 10 articles per ticker
- Applies recency weights: newest = 1.0, decay factor 0.9 per day
- Returns sentiment_score (-30 to +30 scale for UI consistency)
- Caches result in watchlist_snapshots with 30-minute TTL

**4.2.4** Update `WatchlistService.calculate_scores()` to:
- Fetch sentiment score from aggregator
- Add sentiment component to overall score calculation
- Store sentiment_score in watchlist_snapshots.news_score column

**4.2.5** Schedule Celery task `refresh_sentiment_task`:
- Runs every 2 hours during market hours (9:30 AM - 4 PM ET)
- Fetches news for all watchlist tickers
- Respects rate limits (delay 1s between tickers)
- Logs article count and average sentiment per ticker

### 4.3 Fundamental Metrics Integration

**4.3.1** Create `fundamentals_fetcher.py` module that:
- Fetches key metrics from existing FMP API integration:
  - Forward P/E ratio (`/api/v3/ratios-ttm/{ticker}`)
  - EV/EBITDA (`/api/v3/enterprise-values/{ticker}`)
  - FCF yield (calculate from `/api/v3/cash-flow-statement/{ticker}`)
- Falls back to Polygon/Finnhub if FMP data unavailable
- Stores raw values in fundamentals_snapshot table
- Normalizes metrics to 0-100 scale using sector medians

**4.3.2** Create `fundamentals_scorer.py` that:
- Computes fundamental_score from metrics:
  - Forward P/E: compare to sector median, below median = +30 pts
  - EV/EBITDA: compare to sector median, below median = +30 pts
  - FCF yield: positive yield = +20 pts, > 5% = +40 pts
- Averages component scores, scales to 0-100
- Returns fundamental_score with metadata (calculation_date, metrics_used)

**4.3.3** Update `WatchlistService.calculate_scores()` to:
- Fetch fundamental metrics using fundamentals_fetcher
- Calculate fundamental_score using fundamentals_scorer
- Store in watchlist_snapshots.fundamental_score column
- Handle missing data gracefully (default score 50, log warning)

**4.3.4** Schedule Celery task `refresh_fundamentals_task`:
- Runs daily at 7 PM ET (after market close + earnings releases)
- Updates fundamentals for all watchlist tickers
- Respects API quotas (FMP free tier: 250 calls/day)
- Logs metrics retrieved and any API errors

### 4.4 Overall Score Calculation

**4.4.1** Update `WatchlistService.calculate_scores()` final aggregation:
- Compute overall_score as weighted average:
  - Price component: 20% (based on day change %, volatility)
  - Technical score: 30% (RSI, MACD, SMA analysis)
  - Fundamental score: 25% (P/E, EV/EBITDA, FCF yield)
  - Sentiment score: 25% (news sentiment weighted average)
- Scale to 0-100, round to 1 decimal place
- Store in watchlist_snapshots.overall_score column

**4.4.2** Add score validation:
- Ensure all component scores are in valid range (0-100 or -30 to +30 for sentiment)
- Log warning if any component is null/missing, use default values
- Track score calculation metadata (which sources contributed, data staleness)

### 4.5 Testing & Quality

**4.5.1** Create unit tests in `tests/test_sentiment_analyzer.py`:
- Test FinBERT scoring with sample headlines (positive, negative, neutral)
- Test VADER fallback when FinBERT unavailable
- Test batch processing (10 headlines)
- Mock model loading to speed up test suite

**4.5.2** Create unit tests in `tests/test_fundamentals_fetcher.py`:
- Test metric extraction from FMP API responses
- Test multi-source fallback (FMP → Polygon → Finnhub)
- Test sector median normalization
- Mock API responses to avoid real API calls

**4.5.3** Create integration test in `tests/test_watchlist_scoring_integration.py`:
- End-to-end test: backfill data → calculate indicators → score → store snapshot
- Verify non-zero scores appear in database
- Test refresh workflow with real tickers (use test database)
- Verify score history tracking (7-day snapshots)

**4.5.4** Achieve 80%+ test coverage:
- Run `pytest --cov=app --cov-report=term-missing`
- Identify uncovered lines, add tests
- Update known-issues.md with any pre-existing gaps

### 4.6 Documentation & Architecture

**4.6.1** Update `docs/core/ARCHITECTURE.md`:
- Add "Watchlist Scoring Pipeline" section with ASCII diagram
- Document data flow: multi-source APIs → storage → scoring → snapshots → UI
- List all Celery tasks and schedules
- Document scoring formula and weights

**4.6.2** Update `docs/core/OPERATIONS.md`:
- Add "Watchlist Maintenance" section with operational procedures
- Document backfill script usage and troubleshooting
- Add quota monitoring procedures
- Include example Celery task logs

**4.6.3** Create `docs/watchlist-scoring-guide.md`:
- Explain how each score component works
- Provide interpretation guidelines (score 70+ = strong, 30-50 = neutral, <30 = weak)
- Document data sources and refresh frequencies
- Include troubleshooting FAQ

---

## 5. Non-Goals (Out of Scope)

- **AI-generated summaries** - Defer to separate PRD for local LLM integration
- **Sector-specific fundamental metrics** - Use simplified metrics first, expand later
- **Competitor/peer comparison** - Phase 3 feature
- **Real-time (<1 min) streaming** - Keep 15-minute polling model
- **Historical data beyond 60 days** - Sufficient for indicators, expand if needed
- **Alert notifications** - Phase 3 feature

---

## 6. Design Considerations

**6.1 No UI Changes Required**
- Existing frontend already displays all score columns
- Sparklines already implemented, will populate automatically
- Score badges already styled, will show colors when scores non-zero

**6.2 Database Schema Extensions**
- Add columns to watchlist_snapshots if needed for detailed metadata
- Ensure PostgreSQL types match (DOUBLE PRECISION for scores, TIMESTAMPTZ for dates)
- Add indices on (ticker, fetched_at) for query performance

**6.3 Performance Targets**
- Backfill 50 tickers in <5 minutes (with rate limiting)
- Sentiment scoring: 10 articles in <10 seconds (FinBERT batch mode)
- Score calculation: <200ms per ticker
- Watchlist refresh API: <2 seconds for 50 tickers

---

## 7. Technical Considerations

**7.1 FinBERT Model Setup**
- Model size: ~450MB (ProsusAI/finbert)
- Download location: `~/.cache/huggingface/transformers/`
- Dependencies: `transformers>=4.30.0, torch>=2.0.0` (already in requirements.txt)
- First-time setup: `python -c "from transformers import AutoModel; AutoModel.from_pretrained('ProsusAI/finbert')"`

**7.2 API Quota Management**
- **Google News RSS**: No API key, rate limit ~100 req/hour (2s delay between calls)
- **FMP Free Tier**: 250 calls/day (sufficient for 50 tickers daily fundamentals)
- **YFinance**: Unlimited (no official API, web scraping)
- Monitor quotas in health endpoint, log warnings when approaching limits

**7.3 Data Storage**
- Historical data: ~60 days × 50 tickers × 5 fields = 15,000 rows in day_bars
- News cache: ~10 articles × 50 tickers = 500 rows (rolling 30-day window)
- Fundamentals: ~3 metrics × 50 tickers = 150 rows (daily refresh)
- Snapshots: 7 days × 50 tickers = 350 rows (pruned automatically)
- Total storage estimate: <5MB for watchlist data

**7.4 Error Handling**
- API failures: fallback to cached data, log error, continue processing remaining tickers
- Missing historical data: return score 50 (neutral), log warning
- FinBERT unavailable: fallback to VADER, log warning
- Rate limit exceeded: queue for next refresh cycle, notify user via health endpoint

**7.5 Backwards Compatibility**
- Existing watchlist items continue to work (will show 0.0 scores until backfilled)
- API responses remain unchanged (just populate previously-empty score fields)
- No frontend changes required

---

## 8. Success Metrics

**8.1 Functional Completeness**
- All watchlist tickers show non-zero overall scores (60-80 range typical)
- Technical scores reflect indicator calculations (verified by comparing to trading platforms)
- Sentiment scores correlate with news tone (manual spot-check of 10 tickers)
- Fundamental scores match data sources (verify FMP/Polygon data accuracy)

**8.2 Performance**
- Backfill completes in <5 minutes for 50 tickers
- Score refresh completes in <10 seconds for 50 tickers
- Watchlist page loads in <2 seconds with fresh scores
- No API quota errors in logs (respects rate limits)

**8.3 Quality**
- Test coverage ≥80% (pytest --cov)
- All pre-commit hooks pass (ruff, mypy, tests)
- Zero console errors in frontend
- Documentation complete (ARCHITECTURE.md, OPERATIONS.md, scoring guide)

**8.4 User Value**
- Users can identify high-scoring tickers at a glance (overall score 70+)
- Sparklines show meaningful trends (price and RSI charts populated)
- Sentiment badges reflect current news (spot-check against Google News)
- Scores update automatically per refresh interval (verify timestamps)

---

## 9. Implementation Plan (Iterative Approach)

**Phase 2.1: Historical Data & Technical Indicators** (Day 1-2)
- Task 1: Create backfill script, test with 3 tickers
- Task 2: Extend indicator calculations, verify against known values
- Task 3: Update scoring service, test end-to-end
- Task 4: Schedule Celery task, verify daily refresh
- Deliverable: Non-zero technical scores in UI

**Phase 2.2: News Sentiment Scoring** (Day 3-4)
- Task 1: Setup FinBERT model, test with sample headlines
- Task 2: Create news ingestion service, test with Google News RSS
- Task 3: Build sentiment aggregator, verify weighted averages
- Task 4: Integrate into scoring service, test end-to-end
- Task 5: Schedule Celery task, verify 2-hour refresh
- Deliverable: Non-zero sentiment scores in UI

**Phase 2.3: Fundamental Metrics** (Day 5-6)
- Task 1: Create fundamentals fetcher, test with FMP API
- Task 2: Build fundamentals scorer, verify calculations
- Task 3: Integrate into scoring service, test multi-source fallback
- Task 4: Schedule Celery task, verify daily refresh
- Deliverable: Non-zero fundamental scores in UI

**Phase 2.4: Testing & Documentation** (Day 7)
- Task 1: Write unit tests (sentiment, fundamentals, integration)
- Task 2: Achieve 80%+ coverage, fix any gaps
- Task 3: Update ARCHITECTURE.md and OPERATIONS.md
- Task 4: Create watchlist-scoring-guide.md
- Task 5: Manual E2E validation (10-ticker smoke test)
- Deliverable: Production-ready watchlist with complete scoring

---

## 10. Open Questions

1. **FinBERT alternatives**: Should we support HuggingFace Inference API as backup? (Decided: local-first, VADER fallback)
2. **Fundamental metrics expansion**: When should we add sector-specific metrics? (Decided: Phase 3, after core scoring stable)
3. **Historical data retention**: Should we keep more than 60 days? (Decided: monitor storage, expand if users request)
4. **Alert thresholds**: What score change triggers alerts? (Decided: >10 point change, Phase 3 feature)
5. **API quota monitoring**: Should we add email alerts for quota warnings? (Decided: log warnings, review in health endpoint)

---

## 11. Dependencies

**Required PRDs**:
- ⚠️ **PRD #0018 (CRITICAL BLOCKER)** - Refresh infrastructure fixes (manual refresh, auto-refresh, market hours handling, staleness logic)
- ✅ PRD #0014 Phase 1 (complete) - Database schema, API endpoints, frontend UI
- ✅ PRD #0011 (85% complete) - Multi-source infrastructure, technical indicators
- ✅ PRD #0016 (complete) - Multi-source price fetcher with all 6 sources

**API Keys Required**:
- ✅ FMP API key (already configured)
- ✅ Polygon API key (already configured)
- ✅ Finnhub API key (already configured)
- ✅ No key needed for Google News RSS (free)
- ✅ No key needed for YFinance (free)

**Python Packages** (verify in requirements.txt):
- `transformers>=4.30.0` (for FinBERT)
- `torch>=2.0.0` (for FinBERT)
- `vaderSentiment>=3.3.2` (fallback sentiment)
- `feedparser>=6.0.0` (for Google News RSS parsing)

---

**Next Steps**:
1. **FIRST**: Complete PRD #0018 (refresh infrastructure fixes) - CRITICAL BLOCKER
2. **THEN**: Use `/task_it tasks/0019-prd-watchlist-intelligence-layer-phase2.md` to generate detailed task breakdown
3. Finally: `/do_it` to implement scoring features
