# Task List: Watchlist Intelligence Layer - Complete Phase 2

**PRD**: `0019-prd-watchlist-intelligence-layer-phase2.md`
**Status**: Blocked (Waiting for PRD #0018)
**Completion**: 0% (Not started)
**Effort to Complete**: HIGH
**Last Updated**: 2025-10-30

**Note on Effort Levels**:
- **Low**: 1-2 hours of straightforward work
- **Medium**: Half day of work with some complexity
- **High**: Full day or more, significant complexity (this PRD: 6-7 days)

---

## Summary

**BLOCKING DEPENDENCY**: This task list is **blocked by PRD #0018** (refresh infrastructure fixes). Complete `/do_it tasks/tasks-0018-prd-watchlist-refresh-infrastructure-fixes.md` FIRST before starting this work.

**✅ COMPLETE:**
- (None yet - waiting for blocker)

**🔄 IN PROGRESS:**
- (Blocked - waiting for PRD #0018)

**⚠️ NEXT STEPS:**
1. **FIRST**: Complete PRD #0018 (refresh infrastructure fixes)
2. **THEN**: Begin with Task 1.0 (Historical Data & Technical Indicators)
3. Follow checklist sequentially through all 4 phases
4. Update this summary as work progresses

**EFFORT TO COMPLETE:** HIGH (~6-7 days total, split into 4 phases)

---

## Relevant Files

### Files to Create (13 new files)

- `backend/scripts/backfill_historical_data.py` (~150 lines) - Historical OHLCV data backfill script
- `backend/app/watchlist/sentiment_analyzer.py` (~200 lines) - FinBERT sentiment scoring module
- `backend/app/watchlist/news_ingestion.py` (~180 lines) - Google News RSS ingestion service
- `backend/app/watchlist/sentiment_aggregator.py` (~120 lines) - Weighted sentiment aggregation
- `backend/app/watchlist/fundamentals_fetcher.py` (~200 lines) - Fundamental metrics from FMP/Polygon/Finnhub
- `backend/app/watchlist/fundamentals_scorer.py` (~150 lines) - Fundamental score calculation
- `backend/tests/unit/test_sentiment_analyzer.py` (~200 lines) - Unit tests for FinBERT sentiment
- `backend/tests/unit/test_news_ingestion.py` (~150 lines) - Unit tests for news fetching
- `backend/tests/unit/test_fundamentals_fetcher.py` (~180 lines) - Unit tests for fundamental metrics
- `backend/tests/unit/test_fundamentals_scorer.py` (~120 lines) - Unit tests for scoring logic
- `backend/tests/integration/test_watchlist_scoring_integration.py` (~250 lines) - End-to-end scoring tests
- `backend/migrations/005_add_news_fundamentals_tables.sql` (~80 lines) - Database schema for news/fundamentals
- `docs/watchlist-scoring-guide.md` (~300 lines) - User guide for watchlist scoring

### Files to Update (8 files)

- `backend/app/watchlist/service.py` - Add complete scoring logic (technical, sentiment, fundamental, overall)
- `backend/app/tasks/agent_tasks.py` - Add 3 new Celery tasks (indicators, sentiment, fundamentals refresh)
- `backend/app/celery_app.py` - Update beat schedule with new periodic tasks
- `backend/app/analytics/indicators.py` - Extend calculate_indicators for watchlist scoring needs
- `backend/requirements.txt` - Add transformers, torch, vaderSentiment packages
- `docs/core/ARCHITECTURE.md` - Add "Watchlist Scoring Pipeline" section with data flow
- `docs/core/OPERATIONS.md` - Add "Watchlist Maintenance" operational procedures
- `docs/core/REFACTOR_STATUS.md` - Mark PRD #0019 Phase 2 complete

### Notes

- **CRITICAL**: PRD #0018 MUST be complete before starting this work (refresh infrastructure is foundation)
- Sentiment analysis requires ~450MB FinBERT model download (first-time setup only)
- Unit tests should mock model loading and API calls to keep test suite fast
- Use `pytest tests/unit/test_sentiment_analyzer.py -v` to run specific tests
- Use `mypy app/watchlist/ --strict` to verify type safety for new modules
- Use `scripts/lint.sh` to run linting and formatting checks
- Database migration requires manual execution after PRD #0018 migration
- Historical backfill will take ~5 minutes for 50 tickers (respects rate limits)
- **UI Testing**: Use `chrome-devtools` MCP for automated end-to-end UI validation (preferred over manual testing)
  - More reliable: Catches score calculation errors, missing data, UI regressions
  - Comprehensive: Tests complete scoring pipeline from UI to database
  - Documented: Captures screenshots, console errors, network requests for debugging
  - Enable MCP: `/mcp` command (already enabled in this session)

---

## Tasks

### 1.0 Historical Data Backfill & Technical Indicators Enhancement

- [ ] 1.1 Create database migration for new columns
  - [ ] 1.1.1 Create `backend/migrations/005_add_news_fundamentals_tables.sql`
  - [ ] 1.1.2 Write CREATE TABLE for news_cache (ticker, published_at, headline, url, sentiment_score, source, content_hash)
  - [ ] 1.1.3 Write CREATE TABLE for fundamentals_snapshot (ticker, pe_ratio, ev_ebitda, fcf_yield, fetched_at)
  - [ ] 1.1.4 Add indices on (ticker, published_at) for news_cache
  - [ ] 1.1.5 Add indices on (ticker, fetched_at) for fundamentals_snapshot
  - [ ] 1.1.6 Apply migration: `psql -d portfolio_ai < migrations/005_add_news_fundamentals_tables.sql`
  - [ ] 1.1.7 Verify tables exist: `psql -d portfolio_ai -c "\dt"`
- [ ] 1.2 Create historical data backfill script
  - [ ] 1.2.1 Create `backend/scripts/backfill_historical_data.py` file
  - [ ] 1.2.2 Add imports (argparse, datetime, MultiSourceFetcher, get_storage)
  - [ ] 1.2.3 Write function signature: `backfill_ticker(ticker: str, days: int) -> dict`
  - [ ] 1.2.4 Implement MultiSourceFetcher.fetch() call with DATASET_DAY request
  - [ ] 1.2.5 Add error handling for failed fetches (log warning, continue)
  - [ ] 1.2.6 Store results in day_bars table using storage.query()
  - [ ] 1.2.7 Return dict with success/failure counts
- [ ] 1.3 Add batch processing to backfill script
  - [ ] 1.3.1 Write `backfill_all_watchlist_tickers()` function
  - [ ] 1.3.2 Query watchlist_items table for all unique symbols
  - [ ] 1.3.3 Group symbols into batches of 20
  - [ ] 1.3.4 Add 2-second delay between batches (rate limit protection)
  - [ ] 1.3.5 Log progress: "Processing batch 1/5 (symbols: AAPL, GOOGL, ...)"
  - [ ] 1.3.6 Collect aggregate statistics (total success/failures)
- [ ] 1.4 Add CLI interface to backfill script
  - [ ] 1.4.1 Add argparse setup with --ticker and --days arguments
  - [ ] 1.4.2 Add --all flag to backfill entire watchlist
  - [ ] 1.4.3 Add if __name__ == "__main__": block
  - [ ] 1.4.4 Test script: `python scripts/backfill_historical_data.py --ticker AAPL --days 60`
  - [ ] 1.4.5 Verify data appears in day_bars table
- [ ] 1.5 Write unit tests for backfill script
  - [ ] 1.5.1 Create `backend/tests/unit/test_backfill_historical.py`
  - [ ] 1.5.2 Write test: backfill_ticker with valid ticker returns success
  - [ ] 1.5.3 Write test: backfill_ticker with invalid ticker handles error gracefully
  - [ ] 1.5.4 Write test: batch processing respects rate limits (mock sleep)
  - [ ] 1.5.5 Mock MultiSourceFetcher to avoid real API calls
  - [ ] 1.5.6 Run tests: `pytest tests/unit/test_backfill_historical.py -v`
- [ ] 1.6 Extend indicators.py for watchlist scoring
  - [ ] 1.6.1 Open `backend/app/analytics/indicators.py`
  - [ ] 1.6.2 Add function: `calculate_technical_score(indicators: dict) -> float`
  - [ ] 1.6.3 Implement RSI scoring logic (30-40 = +20, 40-60 = +10, 60-70 = +20)
  - [ ] 1.6.4 Implement MACD cross detection (histogram sign change)
  - [ ] 1.6.5 Implement SMA-200 position scoring (price > SMA = +10)
  - [ ] 1.6.6 Normalize final score to 0-100 scale
  - [ ] 1.6.7 Return 50.0 if insufficient data (default neutral score)
- [ ] 1.7 Write unit tests for technical scoring
  - [ ] 1.7.1 Open `backend/tests/test_indicators.py`
  - [ ] 1.7.2 Write test: RSI 35 (oversold) returns score >60
  - [ ] 1.7.3 Write test: RSI 65 (overbought) returns score >60
  - [ ] 1.7.4 Write test: RSI 50 (neutral) returns score ~50
  - [ ] 1.7.5 Write test: bullish MACD cross adds points
  - [ ] 1.7.6 Write test: missing indicators returns default 50.0
  - [ ] 1.7.7 Run tests: `pytest tests/test_indicators.py::test_calculate_technical_score -v`
- [ ] 1.8 Create Celery task for indicator refresh
  - [ ] 1.8.1 Open `backend/app/tasks/agent_tasks.py`
  - [ ] 1.8.2 Add function: `@celery_app.task def update_technical_indicators_daily()`
  - [ ] 1.8.3 Query all watchlist tickers
  - [ ] 1.8.4 Loop through tickers, call calculate_indicators for each
  - [ ] 1.8.5 Store results in technical_indicators table
  - [ ] 1.8.6 Add logging: "Updated indicators for 50 tickers in 45s"
  - [ ] 1.8.7 Handle errors: log warning, continue to next ticker
- [ ] 1.9 Schedule indicator refresh task
  - [ ] 1.9.1 Open `backend/app/celery_app.py`
  - [ ] 1.9.2 Add beat_schedule entry: "update-technical-indicators-daily"
  - [ ] 1.9.3 Set schedule: crontab(hour=18, minute=0, day_of_week='1-5') # 6 PM ET weekdays
  - [ ] 1.9.4 Set task expiry: 1 hour
  - [ ] 1.9.5 Test task manually: `celery -A app.celery_app call update_technical_indicators_daily`
  - [ ] 1.9.6 Verify logs show task execution

### 2.0 News Sentiment Scoring Pipeline Implementation

- [ ] 2.1 Add sentiment analysis dependencies
  - [ ] 2.1.1 Open `backend/requirements.txt`
  - [ ] 2.1.2 Add line: `transformers>=4.30.0`
  - [ ] 2.1.3 Add line: `torch>=2.0.0`
  - [ ] 2.1.4 Add line: `vaderSentiment>=3.3.2`
  - [ ] 2.1.5 Verify feedparser already exists (should be at 6.0.12)
  - [ ] 2.1.6 Run: `cd ~/portfolio-ai/backend && pip install -r requirements.txt`
  - [ ] 2.1.7 Verify installation: `python -c "import transformers; import torch; print('OK')"`
- [ ] 2.2 Create sentiment analyzer module structure
  - [ ] 2.2.1 Create `backend/app/watchlist/sentiment_analyzer.py`
  - [ ] 2.2.2 Add module docstring explaining FinBERT sentiment scoring
  - [ ] 2.2.3 Add imports (transformers, torch, vaderSentiment, logging)
  - [ ] 2.2.4 Define MODEL_NAME constant: "ProsusAI/finbert"
  - [ ] 2.2.5 Add type hints for all function signatures
- [ ] 2.3 Implement FinBERT model loading
  - [ ] 2.3.1 Write function: `setup_finbert() -> tuple[AutoModelForSequenceClassification, AutoTokenizer]`
  - [ ] 2.3.2 Add docstring explaining model download (~450MB first time)
  - [ ] 2.3.3 Implement: `tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)`
  - [ ] 2.3.4 Implement: `model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)`
  - [ ] 2.3.5 Add try/except for download failures, log error
  - [ ] 2.3.6 Return (model, tokenizer) tuple
- [ ] 2.4 Implement single headline scoring
  - [ ] 2.4.1 Write function: `score_headline(text: str, model, tokenizer) -> float`
  - [ ] 2.4.2 Add docstring explaining return range (-1.0 to 1.0)
  - [ ] 2.4.3 Tokenize text: `inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)`
  - [ ] 2.4.4 Run inference: `outputs = model(**inputs)`
  - [ ] 2.4.5 Get logits and apply softmax
  - [ ] 2.4.6 Convert to sentiment score: positive prob - negative prob
  - [ ] 2.4.7 Return float in range -1.0 to 1.0
- [ ] 2.5 Implement batch scoring
  - [ ] 2.5.1 Write function: `score_headlines_batch(texts: list[str], model, tokenizer) -> list[float]`
  - [ ] 2.5.2 Add docstring explaining batch efficiency (10x faster than individual)
  - [ ] 2.5.3 Tokenize batch: `inputs = tokenizer(texts, return_tensors="pt", padding=True, truncation=True)`
  - [ ] 2.5.4 Run batch inference
  - [ ] 2.5.5 Extract scores for each headline
  - [ ] 2.5.6 Return list of floats
- [ ] 2.6 Add VADER fallback
  - [ ] 2.6.1 Write function: `score_headline_vader(text: str) -> float`
  - [ ] 2.6.2 Import SentimentIntensityAnalyzer from vaderSentiment
  - [ ] 2.6.3 Initialize analyzer: `sia = SentimentIntensityAnalyzer()`
  - [ ] 2.6.4 Get compound score: `sia.polarity_scores(text)["compound"]`
  - [ ] 2.6.5 Return compound score (already -1.0 to 1.0 range)
  - [ ] 2.6.6 Add fallback logic in score_headline if FinBERT fails
- [ ] 2.7 Write unit tests for sentiment analyzer
  - [ ] 2.7.1 Create `backend/tests/unit/test_sentiment_analyzer.py`
  - [ ] 2.7.2 Write test: positive headline ("Stock soars on earnings beat") returns >0.5
  - [ ] 2.7.3 Write test: negative headline ("Company faces bankruptcy") returns <-0.5
  - [ ] 2.7.4 Write test: neutral headline ("Stock trades at $100") returns -0.2 to 0.2
  - [ ] 2.7.5 Write test: batch scoring processes 10 headlines correctly
  - [ ] 2.7.6 Mock model loading to avoid downloading in tests
  - [ ] 2.7.7 Write test: VADER fallback works when FinBERT unavailable
  - [ ] 2.7.8 Run tests: `pytest tests/unit/test_sentiment_analyzer.py -v`
- [ ] 2.8 Create news ingestion service
  - [ ] 2.8.1 Create `backend/app/watchlist/news_ingestion.py`
  - [ ] 2.8.2 Add imports (feedparser, hashlib, datetime, storage)
  - [ ] 2.8.3 Write function: `fetch_google_news(ticker: str) -> list[dict]`
  - [ ] 2.8.4 Build URL: `f"https://news.google.com/rss/search?q={ticker}+stock&hl=en-US&gl=US&ceid=US:en"`
  - [ ] 2.8.5 Parse RSS feed: `feed = feedparser.parse(url)`
  - [ ] 2.8.6 Extract entries: title, link, published date
  - [ ] 2.8.7 Return list of dicts with news articles
- [ ] 2.9 Add deduplication to news ingestion
  - [ ] 2.9.1 Write function: `compute_content_hash(title: str, source: str) -> str`
  - [ ] 2.9.2 Implement: `hashlib.sha256(f"{title}|{source}".encode()).hexdigest()`
  - [ ] 2.9.3 In fetch_google_news, add content_hash to each article
  - [ ] 2.9.4 Before inserting, check if hash exists in news_cache
  - [ ] 2.9.5 Skip duplicates, log: "Skipped 3 duplicate articles"
- [ ] 2.10 Implement news storage
  - [ ] 2.10.1 Write function: `store_news_articles(ticker: str, articles: list[dict], storage: DuckDBStorage)`
  - [ ] 2.10.2 Loop through articles
  - [ ] 2.10.3 For each article, INSERT INTO news_cache (ticker, headline, url, published_at, content_hash, source)
  - [ ] 2.10.4 Use parameterized query to avoid SQL injection
  - [ ] 2.10.5 Add ON CONFLICT DO NOTHING (deduplication at DB level)
  - [ ] 2.10.6 Delete articles older than 30 days: `DELETE FROM news_cache WHERE published_at < NOW() - INTERVAL '30 days'`
- [ ] 2.11 Write unit tests for news ingestion
  - [ ] 2.11.1 Create `backend/tests/unit/test_news_ingestion.py`
  - [ ] 2.11.2 Write test: fetch_google_news returns list of articles
  - [ ] 2.11.3 Write test: compute_content_hash generates consistent hashes
  - [ ] 2.11.4 Write test: duplicate articles are skipped
  - [ ] 2.11.5 Write test: old articles are deleted (30-day window)
  - [ ] 2.11.6 Mock feedparser.parse to avoid real HTTP requests
  - [ ] 2.11.7 Run tests: `pytest tests/unit/test_news_ingestion.py -v`
- [ ] 2.12 Create sentiment aggregator
  - [ ] 2.12.1 Create `backend/app/watchlist/sentiment_aggregator.py`
  - [ ] 2.12.2 Write function: `aggregate_sentiment(ticker: str, storage: DuckDBStorage) -> float`
  - [ ] 2.12.3 Query latest 10 articles from news_cache for ticker
  - [ ] 2.12.4 Load sentiment_score for each article
  - [ ] 2.12.5 Apply recency weights: newest = 1.0, decay by 0.9 per day
  - [ ] 2.12.6 Compute weighted average
  - [ ] 2.12.7 Scale to -30 to +30 range (multiply by 30)
  - [ ] 2.12.8 Return sentiment score
- [ ] 2.13 Add caching to sentiment aggregator
  - [ ] 2.13.1 Check if cached result exists in watchlist_snapshots (age < 30 min)
  - [ ] 2.13.2 If fresh cache exists, return cached value
  - [ ] 2.13.3 If stale/missing, compute new score
  - [ ] 2.13.4 Store result in watchlist_snapshots.news_score column
  - [ ] 2.13.5 Log cache hit/miss for monitoring
- [ ] 2.14 Write unit tests for sentiment aggregator
  - [ ] 2.14.1 Create test in `backend/tests/unit/test_sentiment_analyzer.py`
  - [ ] 2.14.2 Write test: aggregate_sentiment with 10 positive articles returns >15
  - [ ] 2.14.3 Write test: aggregate_sentiment with 10 negative articles returns <-15
  - [ ] 2.14.4 Write test: recency weighting works (newer articles weighted higher)
  - [ ] 2.14.5 Write test: fewer than 10 articles still works
  - [ ] 2.14.6 Write test: cache returns stale data if < 30 min old
  - [ ] 2.14.7 Run tests: `pytest tests/unit/test_sentiment_analyzer.py -v`
- [ ] 2.15 Create Celery task for sentiment refresh
  - [ ] 2.15.1 Open `backend/app/tasks/agent_tasks.py`
  - [ ] 2.15.2 Add function: `@celery_app.task def refresh_sentiment_scores()`
  - [ ] 2.15.3 Query all watchlist tickers
  - [ ] 2.15.4 For each ticker: fetch_google_news → score with FinBERT → store in news_cache
  - [ ] 2.15.5 Add 1-second delay between tickers (rate limit protection)
  - [ ] 2.15.6 Log: "Fetched 8 news articles for AAPL, avg sentiment: +0.45"
  - [ ] 2.15.7 Handle errors: log warning, continue to next ticker
- [ ] 2.16 Schedule sentiment refresh task
  - [ ] 2.16.1 Open `backend/app/celery_app.py`
  - [ ] 2.16.2 Add beat_schedule entry: "refresh-sentiment-scores"
  - [ ] 2.16.3 Set schedule: crontab(minute=0, hour='9-16/2', day_of_week='1-5') # Every 2 hours during market
  - [ ] 2.16.4 Set task expiry: 1 hour
  - [ ] 2.16.5 Test task manually: `celery -A app.celery_app call refresh_sentiment_scores`

### 3.0 Fundamental Metrics Integration

- [ ] 3.1 Create fundamentals fetcher module
  - [ ] 3.1.1 Create `backend/app/watchlist/fundamentals_fetcher.py`
  - [ ] 3.1.2 Add imports (FMPSource, PolygonSource, FinnhubSource, storage)
  - [ ] 3.1.3 Write function signature: `fetch_fundamentals(ticker: str) -> dict`
  - [ ] 3.1.4 Add docstring explaining metrics: P/E, EV/EBITDA, FCF yield
  - [ ] 3.1.5 Add type hints for return dict structure
- [ ] 3.2 Implement FMP fundamentals fetching
  - [ ] 3.2.1 Write function: `_fetch_from_fmp(ticker: str, fmp_source: FMPSource) -> dict`
  - [ ] 3.2.2 Fetch P/E ratio from `/api/v3/ratios-ttm/{ticker}`
  - [ ] 3.2.3 Fetch EV/EBITDA from `/api/v3/enterprise-values/{ticker}`
  - [ ] 3.2.4 Fetch cash flow statement for FCF calculation
  - [ ] 3.2.5 Extract metrics from JSON responses
  - [ ] 3.2.6 Return dict with pe_ratio, ev_ebitda, fcf_yield
  - [ ] 3.2.7 Handle missing data: return None for unavailable metrics
- [ ] 3.3 Add multi-source fallback for fundamentals
  - [ ] 3.3.1 In fetch_fundamentals, try FMP first
  - [ ] 3.3.2 If FMP fails, try Polygon API
  - [ ] 3.3.3 If Polygon fails, try Finnhub API
  - [ ] 3.3.4 Log which source succeeded: "Fetched AAPL fundamentals from polygon"
  - [ ] 3.3.5 If all fail, log warning and return None for all metrics
- [ ] 3.4 Implement fundamentals storage
  - [ ] 3.4.1 Write function: `store_fundamentals(ticker: str, metrics: dict, storage: DuckDBStorage)`
  - [ ] 3.4.2 INSERT INTO fundamentals_snapshot (ticker, pe_ratio, ev_ebitda, fcf_yield, fetched_at)
  - [ ] 3.4.3 Use parameterized query
  - [ ] 3.4.4 Add ON CONFLICT UPDATE to refresh existing data
  - [ ] 3.4.5 Delete snapshots older than 7 days (fundamentals refresh daily)
- [ ] 3.5 Write unit tests for fundamentals fetcher
  - [ ] 3.5.1 Create `backend/tests/unit/test_fundamentals_fetcher.py`
  - [ ] 3.5.2 Write test: fetch_fundamentals returns valid dict structure
  - [ ] 3.5.3 Write test: FMP source works with valid ticker
  - [ ] 3.5.4 Write test: fallback to Polygon when FMP fails
  - [ ] 3.5.5 Write test: fallback to Finnhub when both fail
  - [ ] 3.5.6 Write test: all sources fail returns None gracefully
  - [ ] 3.5.7 Mock API responses to avoid real HTTP calls
  - [ ] 3.5.8 Run tests: `pytest tests/unit/test_fundamentals_fetcher.py -v`
- [ ] 3.6 Create fundamentals scorer module
  - [ ] 3.6.1 Create `backend/app/watchlist/fundamentals_scorer.py`
  - [ ] 3.6.2 Add imports (typing, statistics for median calculation)
  - [ ] 3.6.3 Write function: `calculate_fundamental_score(metrics: dict, sector_medians: dict) -> float`
  - [ ] 3.6.4 Add docstring explaining scoring algorithm
  - [ ] 3.6.5 Add type hints for parameters
- [ ] 3.7 Implement P/E ratio scoring
  - [ ] 3.7.1 In calculate_fundamental_score, extract pe_ratio from metrics
  - [ ] 3.7.2 Get sector median P/E from sector_medians dict
  - [ ] 3.7.3 If P/E < median: add 30 points (undervalued)
  - [ ] 3.7.4 If P/E > median: add 0 points (overvalued)
  - [ ] 3.7.5 Handle None values: default to 15 points (neutral)
- [ ] 3.8 Implement EV/EBITDA scoring
  - [ ] 3.8.1 Extract ev_ebitda from metrics
  - [ ] 3.8.2 Get sector median EV/EBITDA
  - [ ] 3.8.3 If EV/EBITDA < median: add 30 points
  - [ ] 3.8.4 If EV/EBITDA > median: add 0 points
  - [ ] 3.8.5 Handle None values: default to 15 points
- [ ] 3.9 Implement FCF yield scoring
  - [ ] 3.9.1 Extract fcf_yield from metrics
  - [ ] 3.9.2 If FCF yield > 5%: add 40 points (strong cash generation)
  - [ ] 3.9.3 If FCF yield 0-5%: add 20 points (positive)
  - [ ] 3.9.4 If FCF yield < 0: add 0 points (burning cash)
  - [ ] 3.9.5 Handle None values: default to 10 points
- [ ] 3.10 Normalize fundamental score
  - [ ] 3.10.1 Sum all component scores (P/E, EV/EBITDA, FCF)
  - [ ] 3.10.2 Average the scores
  - [ ] 3.10.3 Scale to 0-100 range
  - [ ] 3.10.4 Round to 1 decimal place
  - [ ] 3.10.5 Return final score
- [ ] 3.11 Add sector median loading
  - [ ] 3.11.1 Write function: `load_sector_medians(storage: DuckDBStorage) -> dict`
  - [ ] 3.11.2 Query historical fundamentals data grouped by sector
  - [ ] 3.11.3 Calculate median P/E, EV/EBITDA for each sector
  - [ ] 3.11.4 Return dict: {"Technology": {"pe": 25.0, "ev_ebitda": 15.0}, ...}
  - [ ] 3.11.5 Use hardcoded defaults if insufficient data
- [ ] 3.12 Write unit tests for fundamentals scorer
  - [ ] 3.12.1 Create `backend/tests/unit/test_fundamentals_scorer.py`
  - [ ] 3.12.2 Write test: low P/E (undervalued) returns high score
  - [ ] 3.12.3 Write test: high P/E (overvalued) returns low score
  - [ ] 3.12.4 Write test: high FCF yield (>5%) returns high score
  - [ ] 3.12.5 Write test: negative FCF yield returns low score
  - [ ] 3.12.6 Write test: missing metrics return default 50.0 score
  - [ ] 3.12.7 Run tests: `pytest tests/unit/test_fundamentals_scorer.py -v`
- [ ] 3.13 Create Celery task for fundamentals refresh
  - [ ] 3.13.1 Open `backend/app/tasks/agent_tasks.py`
  - [ ] 3.13.2 Add function: `@celery_app.task def refresh_fundamentals_daily()`
  - [ ] 3.13.3 Query all watchlist tickers
  - [ ] 3.13.4 For each ticker: fetch_fundamentals → calculate_score → store
  - [ ] 3.13.5 Respect API quotas: max 250 calls/day for FMP
  - [ ] 3.13.6 Log: "Updated fundamentals for 50 tickers, avg score: 62.5"
  - [ ] 3.13.7 Handle errors: log warning with ticker name, continue
- [ ] 3.14 Schedule fundamentals refresh task
  - [ ] 3.14.1 Open `backend/app/celery_app.py`
  - [ ] 3.14.2 Add beat_schedule entry: "refresh-fundamentals-daily"
  - [ ] 3.14.3 Set schedule: crontab(hour=19, minute=0, day_of_week='1-5') # 7 PM ET weekdays
  - [ ] 3.14.4 Set task expiry: 2 hours
  - [ ] 3.14.5 Test task manually

### 4.0 Overall Score Calculation & Testing

- [ ] 4.1 Update watchlist service for complete scoring
  - [ ] 4.1.1 Open `backend/app/watchlist/service.py`
  - [ ] 4.1.2 Import new modules (sentiment_aggregator, fundamentals_scorer, calculate_technical_score)
  - [ ] 4.1.3 Locate `calculate_scores()` method in WatchlistService
  - [ ] 4.1.4 Add call to `calculate_technical_score()` for technical component
  - [ ] 4.1.5 Add call to `aggregate_sentiment()` for sentiment component
  - [ ] 4.1.6 Add call to `calculate_fundamental_score()` for fundamental component
- [ ] 4.2 Implement overall score aggregation
  - [ ] 4.2.1 Define score weights as constants (PRICE=0.2, TECH=0.3, FUND=0.25, SENT=0.25)
  - [ ] 4.2.2 Calculate weighted average: `overall = price*0.2 + tech*0.3 + fund*0.25 + sent*0.25`
  - [ ] 4.2.3 Handle missing components: use 50.0 default if None
  - [ ] 4.2.4 Scale sentiment from -30/+30 to 0-100 range before averaging
  - [ ] 4.2.5 Round overall score to 1 decimal place
  - [ ] 4.2.6 Ensure final score is in 0-100 range
- [ ] 4.3 Add score validation
  - [ ] 4.3.1 Write function: `validate_score_components(price, tech, fund, sent) -> bool`
  - [ ] 4.3.2 Check price score in 0-100 range
  - [ ] 4.3.3 Check technical score in 0-100 range
  - [ ] 4.3.4 Check fundamental score in 0-100 range
  - [ ] 4.3.5 Check sentiment score in -30 to +30 range
  - [ ] 4.3.6 Log warning if any component out of range
  - [ ] 4.3.7 Return True if all valid, False otherwise
- [ ] 4.4 Store complete scores in database
  - [ ] 4.4.1 Update WatchlistSnapshot model to include all score fields
  - [ ] 4.4.2 Store technical_score, fundamental_score, news_score, overall_score
  - [ ] 4.4.3 Store score calculation metadata (sources_used, data_staleness)
  - [ ] 4.4.4 Use upsert to update existing snapshots
  - [ ] 4.4.5 Commit transaction atomically
- [ ] 4.5 Write integration test for complete scoring pipeline
  - [ ] 4.5.1 Create `backend/tests/integration/test_watchlist_scoring_integration.py`
  - [ ] 4.5.2 Write test: backfill AAPL data → calculate indicators → score → verify non-zero
  - [ ] 4.5.3 Write test: full refresh workflow updates all score components
  - [ ] 4.5.4 Write test: score history tracking works (7-day snapshots)
  - [ ] 4.5.5 Write test: missing data components use defaults gracefully
  - [ ] 4.5.6 Use test database to avoid polluting production data
  - [ ] 4.5.7 Run test: `pytest tests/integration/test_watchlist_scoring_integration.py -v`
- [ ] 4.6 Test score calculation with real tickers
  - [ ] 4.6.1 Run backfill script for AAPL, GOOGL, MSFT
  - [ ] 4.6.2 Trigger manual refresh via API
  - [ ] 4.6.3 Query watchlist_snapshots table
  - [ ] 4.6.4 Verify technical_score is non-zero (expected 60-85 range)
  - [ ] 4.6.5 Verify fundamental_score is non-zero (expected 55-75 range)
  - [ ] 4.6.6 Verify news_score is non-zero (expected -20 to +30 range)
  - [ ] 4.6.7 Verify overall_score is meaningful (expected 60-80 range)
- [ ] 4.7 Run full test suite
  - [ ] 4.7.1 Run all unit tests: `pytest tests/unit/ -v`
  - [ ] 4.7.2 Run all integration tests: `pytest tests/integration/ -v`
  - [ ] 4.7.3 Check coverage: `pytest tests/ --cov=app/watchlist --cov-report=term-missing`
  - [ ] 4.7.4 Verify coverage ≥80%
  - [ ] 4.7.5 Fix any failing tests
- [ ] 4.8 Run type checking and linting
  - [ ] 4.8.1 Run `mypy app/watchlist/ --strict`
  - [ ] 4.8.2 Fix any type errors in new modules
  - [ ] 4.8.3 Run `ruff check app/watchlist/`
  - [ ] 4.8.4 Fix any linting errors
  - [ ] 4.8.5 Run `ruff format app/watchlist/`
  - [ ] 4.8.6 Run `scripts/lint.sh` for full project check
- [ ] 4.9 Update ARCHITECTURE.md documentation
  - [ ] 4.9.1 Open `docs/core/ARCHITECTURE.md`
  - [ ] 4.9.2 Add new section: "Watchlist Scoring Pipeline"
  - [ ] 4.9.3 Create ASCII diagram showing data flow (APIs → storage → scoring → snapshots → UI)
  - [ ] 4.9.4 Document all Celery tasks and schedules
  - [ ] 4.9.5 Document scoring formula and component weights
  - [ ] 4.9.6 Add example score calculation walkthrough
- [ ] 4.10 Update OPERATIONS.md documentation
  - [ ] 4.10.1 Open `docs/core/OPERATIONS.md`
  - [ ] 4.10.2 Add "Watchlist Maintenance" section
  - [ ] 4.10.3 Document backfill script usage: `python scripts/backfill_historical_data.py --all`
  - [ ] 4.10.4 Add troubleshooting guide for common issues
  - [ ] 4.10.5 Document quota monitoring procedures
  - [ ] 4.10.6 Include example Celery task logs
- [ ] 4.11 Create user-facing scoring guide
  - [ ] 4.11.1 Create `docs/watchlist-scoring-guide.md`
  - [ ] 4.11.2 Add introduction explaining watchlist intelligence system
  - [ ] 4.11.3 Document each score component (technical, fundamental, sentiment, overall)
  - [ ] 4.11.4 Provide interpretation guidelines (70+ = strong, 30-50 = neutral, <30 = weak)
  - [ ] 4.11.5 List data sources and refresh frequencies
  - [ ] 4.11.6 Add troubleshooting FAQ
  - [ ] 4.11.7 Include example screenshots (optional, can add later)
- [ ] 4.12 End-to-end validation using chrome-devtools MCP
  - [ ] 4.12.1 Start backend: `cd ~/portfolio-ai/backend && uvicorn app.main:app --reload`
  - [ ] 4.12.2 Start frontend: `cd ~/portfolio-ai/frontend && npm run dev`
  - [ ] 4.12.3 **Automated UI testing with chrome-devtools MCP** (preferred)
    - Use `mcp__chrome-devtools__new_page` to open http://localhost:3000
    - Use `mcp__chrome-devtools__take_snapshot` to verify page loads
    - **Test: Add Tickers to Watchlist**
      - Use `mcp__chrome-devtools__click` to open "Add to Watchlist" dialog
      - Use `mcp__chrome-devtools__fill` to enter ticker symbols (AAPL, GOOGL, MSFT, AMZN, NVDA)
      - Use `mcp__chrome-devtools__click` to submit
      - Use `mcp__chrome-devtools__wait_for` to wait for tickers to appear in table
    - Run backfill script: `python scripts/backfill_historical_data.py --ticker AAPL,GOOGL,MSFT,AMZN,NVDA --days 60`
    - **Test: Refresh Button & Score Display**
      - Use `mcp__chrome-devtools__click` on refresh button
      - Use `mcp__chrome-devtools__wait_for` to wait for completion
      - Use `mcp__chrome-devtools__take_snapshot` to verify all tickers show non-zero overall scores
      - Verify overall scores are in reasonable range (60-80 typical) from snapshot
    - **Test: Sparklines Historical Data**
      - Use `mcp__chrome-devtools__take_snapshot` to check sparklines are present
      - Use `mcp__chrome-devtools__evaluate_script` to verify sparkline SVG elements exist
      - Verify sparklines show 7-day trend data
    - **Test: Expand Row for Score Breakdown**
      - Use `mcp__chrome-devtools__click` on first row to expand
      - Use `mcp__chrome-devtools__take_snapshot` to verify expanded content shows:
        - Technical score (60-85 range expected)
        - Fundamental score (55-75 range expected)
        - Sentiment score (-20 to +30 range expected)
        - Overall score calculation
      - Verify scores are reasonable and non-zero in snapshot
    - **Test: Console Errors & Network**
      - Use `mcp__chrome-devtools__list_console_messages` to verify zero errors
      - Use `mcp__chrome-devtools__list_network_requests` to verify API calls successful
      - Use `mcp__chrome-devtools__take_screenshot` to capture final state for documentation
  - [ ] 4.12.4 **Alternative: Manual testing** (if MCP unavailable)
    - Add 5 test tickers to watchlist via UI
    - Run backfill script for those tickers
    - Click "Refresh" button in UI
    - Verify all tickers show non-zero overall scores
    - Verify sparklines populate with historical data
    - Expand row to view score breakdown
    - Verify technical, fundamental, sentiment scores are reasonable
    - Check browser console for errors (should be zero)
- [ ] 4.13 Update REFACTOR_STATUS.md
  - [ ] 4.13.1 Open `docs/core/REFACTOR_STATUS.md`
  - [ ] 4.13.2 Mark PRD #0019 Phase 2 as "COMPLETE ✅"
  - [ ] 4.13.3 Add completion date
  - [ ] 4.13.4 List any known issues or tech debt
  - [ ] 4.13.5 Update "Next Steps" section with Phase 3 ideas

---

## Verification & Production Readiness

**MANDATORY before marking task "COMPLETE ✅":**

- [ ] **Functional Completeness**
  - [ ] All PRD requirements implemented
  - [ ] Historical data backfilled for all watchlist tickers (60 days minimum)
  - [ ] Technical scores calculated from indicators (non-zero, 60-85 range)
  - [ ] Sentiment scores reflect news articles (non-zero, -20 to +30 range)
  - [ ] Fundamental scores computed from metrics (non-zero, 55-75 range)
  - [ ] Overall scores combine all components meaningfully (60-80 typical)
  - [ ] All user stories satisfied
  - [ ] Zero known bugs or regressions

- [ ] **Test Coverage** (target: 80%+)
  - [ ] Unit tests for sentiment_analyzer (FinBERT + VADER fallback)
  - [ ] Unit tests for news_ingestion (RSS parsing, deduplication)
  - [ ] Unit tests for fundamentals_fetcher (multi-source fallback)
  - [ ] Unit tests for fundamentals_scorer (P/E, EV/EBITDA, FCF logic)
  - [ ] Unit tests for technical score calculation
  - [ ] Integration test for complete scoring pipeline
  - [ ] Integration test for score history tracking
  - [ ] All tests passing: `pytest tests/ -v`
  - [ ] Coverage verified: `pytest tests/ --cov=app/watchlist --cov-report=term-missing`

- [ ] **Type Safety & Code Quality**
  - [ ] 100% type hints on all new functions: `mypy app/watchlist/ --strict` passes
  - [ ] Linting passes: `scripts/lint.sh` returns zero errors
  - [ ] Code formatting applied: `ruff format app/watchlist/`
  - [ ] No `Any` types used (proper type hints throughout)
  - [ ] Function complexity limits met (<50 lines per function)

- [ ] **Clean Implementation (No Band-Aids)**
  - [ ] All type hints are proper (no `Any` shortcuts)
  - [ ] Scoring logic is explicit and testable
  - [ ] Single source of truth for score calculations
  - [ ] Standard patterns used (no custom workarounds)
  - [ ] Clear intent throughout (no hidden behaviors)
  - [ ] Proper error messages (no silent failures)

- [ ] **Documentation**
  - [ ] All public functions have comprehensive docstrings
  - [ ] ARCHITECTURE.md updated with scoring pipeline section
  - [ ] OPERATIONS.md updated with maintenance procedures
  - [ ] watchlist-scoring-guide.md created for end users
  - [ ] Scoring formula documented with examples
  - [ ] Data sources and refresh frequencies documented

- [ ] **Security & Performance**
  - [ ] SQL queries use parameterized placeholders (no f-strings with user input)
  - [ ] API keys stored in environment variables only
  - [ ] Input validation on all user inputs
  - [ ] Backfill completes in <5 minutes for 50 tickers
  - [ ] Score refresh completes in <10 seconds for 50 tickers
  - [ ] FinBERT batch processing achieves 10x speedup vs individual
  - [ ] No API quota errors in logs

- [ ] **Operational Readiness**
  - [ ] Appropriate logging at INFO/WARNING/ERROR levels
  - [ ] Clear error messages on failures with ticker symbol context
  - [ ] Celery tasks scheduled correctly (daily indicators, 2-hour sentiment, daily fundamentals)
  - [ ] Manual end-to-end test via UI successful
  - [ ] Sparklines populate with historical data
  - [ ] Score breakdown visible in expanded rows
  - [ ] FinBERT model downloaded and functional (~450MB)
  - [ ] All 3 Celery tasks executing on schedule
  - [ ] REFACTOR_STATUS.md updated (mark feature complete)

**See**: `docs/core/DEVELOPMENT.md` → "Production Readiness Requirements" for complete checklist
