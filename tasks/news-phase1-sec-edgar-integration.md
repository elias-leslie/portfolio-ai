# Task List: News Phase 1 - SEC EDGAR Integration

**Status**: Not Started
**Created**: 2025-11-06
**Priority**: CRITICAL
**Estimated Effort**: 12-16 hours (2-3 days)
**Dependencies**: None (free tier, no API keys needed)

---

## Summary

Integrate SEC EDGAR filings as the PRIMARY news source - the highest-quality, completely free, institutional-grade data that provides real trading edge. SEC filings are legally binding, zero manipulation, and contain material events (earnings, insider trades, M&A, executive changes) that move markets.

**Goal**: Add SEC EDGAR RSS feeds for 8-K, 10-Q, 10-K, Form 4, and 13F filings as the top-priority news source with plain-language translation for everyday users.

---

## Tasks

- [ ] 1. Research SEC EDGAR API and RSS capabilities
  - [ ] 1.1 Test SEC EDGAR RSS feeds for individual tickers
        - URL format: `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={ticker}&type=&dateb=&owner=exclude&count=100&output=atom`
        - Test with NVDA, AAPL, GOOGL, SPY to verify feed format
        - Document response structure (title, link, published, summary, filing type)
  - [ ] 1.2 Identify filing types and their significance
        - **8-K**: Material events (Item 2.02 = earnings, 1.01 = M&A, 5.02 = exec changes)
        - **10-Q**: Quarterly reports (Risk Factors, MD&A, financial tables)
        - **10-K**: Annual reports (comprehensive financials)
        - **Form 4**: Insider trades (purchases/sales by directors/officers)
        - **13F**: Institutional holdings (quarterly, hedge fund positions)
        - **S-1/S-3**: New offerings (IPO, secondary offerings)
        - **DEF 14A**: Proxy statements (exec comp, board votes)
  - [ ] 1.3 Research rate limits and compliance
        - SEC guidelines: https://www.sec.gov/os/webmaster-faq#developers
        - Rate limit: 10 requests/second per IP (very generous)
        - User-Agent requirement: Must identify application
        - Document compliance requirements for attribution
  - [ ] 1.4 Evaluate bulk download vs RSS feeds vs API
        - RSS: Best for real-time ticker monitoring (recommended for Phase 1)
        - Bulk: EDGAR full index downloads (deferred to Phase 2)
        - API: JSON endpoints if available (evaluate feasibility)

- [ ] 2. Create SECEdgarSource adapter
  - [ ] 2.1 Create `backend/app/sources/sec_edgar_source.py` with base structure
        ```python
        class SECEdgarSource(BaseSource):
            name = "sec_edgar"
            priority = 5  # Highest priority (above YFinance=1)
            supports_news = True

            FILING_TYPES = ["8-K", "10-Q", "10-K", "4", "13F"]
            RSS_URL_TEMPLATE = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={ticker}&type=&dateb=&owner=exclude&count=100&output=atom"
        ```
  - [ ] 2.2 Implement `fetch_news_payload(tickers, start, end)` method
        - Parse RSS feed using feedparser library
        - Extract: title, link, published date, summary, filing type
        - Filter by date range (start/end)
        - Return normalized DataFrame with columns: ticker, headline, url, published_at, source, summary, filing_type
  - [ ] 2.3 Add filing type extraction from RSS entry titles
        - Regex pattern: `r'(\d{1,2}-[KQ]|Form [0-9]+|DEF 14A)'`
        - Extract Item numbers for 8-K: `r'Item (\d+\.\d+)'`
        - Store in `filing_type` field
  - [ ] 2.4 Implement rate limiting (10 req/sec max, use conservative 2 req/sec)
        - Add delay between ticker requests: `time.sleep(0.5)`
        - Track request timestamps to avoid bursts
  - [ ] 2.5 Add User-Agent header for SEC compliance
        - Format: `"PortfolioAI/1.0 (https://github.com/kasadis/portfolio-ai; contact@example.com)"`
        - Document in source code and README

- [ ] 3. Add database schema for SEC filing metadata
  - [ ] 3.1 Create migration `013_sec_edgar_metadata.sql`
        ```sql
        ALTER TABLE news_cache ADD COLUMN IF NOT EXISTS filing_type TEXT;
        ALTER TABLE news_cache ADD COLUMN IF NOT EXISTS filing_items TEXT[]; -- 8-K item numbers
        ALTER TABLE news_cache ADD COLUMN IF NOT EXISTS is_material_event BOOLEAN DEFAULT FALSE;
        ALTER TABLE news_cache ADD COLUMN IF NOT EXISTS content_type TEXT; -- PRIMARY, SECONDARY, TERTIARY, NOISE
        ALTER TABLE news_cache ADD COLUMN IF NOT EXISTS event_category TEXT; -- earnings, insider_trade, upgrade, etc.

        CREATE INDEX IF NOT EXISTS idx_news_filing_type ON news_cache(filing_type) WHERE filing_type IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_news_material_events ON news_cache(is_material_event) WHERE is_material_event = TRUE;
        ```
  - [ ] 3.2 Update `backend/migrations/__init__.py` to include new migration
  - [ ] 3.3 Run migration on development database
        ```bash
        cd /home/kasadis/portfolio-ai/backend
        .venv/bin/python -m app.storage
        ```
  - [ ] 3.4 Verify schema changes with psql
        ```bash
        psql -U portfolio_ai_user -d portfolio_ai -c "\d news_cache"
        ```

- [ ] 4. Implement content classification system
  - [ ] 4.1 Create `backend/app/services/content_classifier.py`
        - Define `ContentType` enum: PRIMARY, SECONDARY, TERTIARY, NOISE
        - Define `EventCategory` enum: earnings, insider_trade, m_and_a, exec_change, offering, proxy, analyst_rating, general_news
  - [ ] 4.2 Implement `classify_content(article)` function
        - SEC filings (8-K, 10-Q, Form 4) → PRIMARY
        - FT, Reuters, WSJ, Nasdaq → SECONDARY
        - CNBC, MarketWatch → TERTIARY
        - Press releases, PR Newswire → NOISE (filter out)
  - [ ] 4.3 Implement `classify_event_category(article)` function
        - 8-K Item 2.02 → earnings
        - Form 4 → insider_trade
        - 8-K Item 1.01 → m_and_a
        - 8-K Item 5.02 → exec_change
        - S-1/S-3 → offering
        - Keywords: "upgrade", "downgrade" → analyst_rating
  - [ ] 4.4 Implement `is_material_event(article)` function
        - 8-K items: 1.01, 1.02, 2.02, 4.02, 5.02 → TRUE
        - Form 4 with transaction_value >$1M → TRUE
        - 13F changes >10% → TRUE
        - All others → FALSE
  - [ ] 4.5 Integrate into NewsService article ingestion
        - Call classifier after fetching articles
        - Store classification results in news_cache

- [ ] 5. Register SEC EDGAR source in NewsService
  - [ ] 5.1 Update `NewsService._prepare_vendor_sources()` to include SEC EDGAR
        ```python
        # SEC EDGAR (free, highest priority)
        sec_flag = self._env_flag("SEC_EDGAR_ENABLED", default=True)
        if sec_flag:
            try:
                sources.append(SECEdgarSource())
            except Exception as exc:
                logger.warning("sec_edgar_source_init_failed", error=str(exc))
        self._register_vendor(
            "sec_edgar",
            configured=True,
            enabled=sec_flag,
            notes="SEC EDGAR filings (8-K, 10-Q, Form 4, etc.) - highest quality free source",
            reason=None if sec_flag else "disabled_by_flag",
        )
        ```
  - [ ] 5.2 Add `SEC_EDGAR_ENABLED` env toggle to `.env` (default ON)
  - [ ] 5.3 Update vendor health tracking to include SEC EDGAR metrics
  - [ ] 5.4 Verify SEC EDGAR appears in `/api/news/health` response

- [ ] 6. Test SEC EDGAR integration
  - [ ] 6.1 Create unit test `test_sec_edgar_source.py`
        - Test RSS feed parsing with mock responses
        - Test filing type extraction (8-K, 10-Q, Form 4)
        - Test date filtering (start/end window)
        - Test rate limiting (verify delays between requests)
  - [ ] 6.2 Create integration test in `test_news.py`
        - Test real SEC RSS feed fetch (use 1 ticker, limited results)
        - Verify normalized DataFrame structure
        - Test content classification (8-K → PRIMARY, etc.)
        - Test material event detection
  - [ ] 6.3 Manual testing with real tickers
        - Add NVDA to watchlist
        - Force news refresh
        - Verify SEC filings appear in `/api/news/symbol/NVDA`
        - Check `/api/news/health` shows sec_edgar active
  - [ ] 6.4 Verify article deduplication works across SEC + other sources
        - Check that same earnings story from SEC 8-K + Google News dedupes correctly
        - Verify SEC filing is kept as primary source (higher priority)

- [ ] 7. Add plain language translation templates for SEC filings
  - [ ] 7.1 Create `backend/app/services/plain_language_translator.py`
        ```python
        FILING_TRANSLATIONS = {
            "8-K Item 2.02": "Company just reported quarterly earnings",
            "8-K Item 1.01": "Major business deal announced",
            "8-K Item 5.02": "Executive leadership change",
            "Form 4 - Purchase": "Insider buying: {person} bought ${amount}",
            "Form 4 - Sale": "Insider selling: {person} sold ${amount}",
            "10-Q": "Quarterly financial report filed",
            "10-K": "Annual financial report filed",
            "13F": "Institutional investors updated holdings",
        }
        ```
  - [ ] 7.2 Implement `translate_to_plain_language(article)` function
        - Map filing type + items to plain language
        - Extract key details (person, amount, direction) from Form 4
        - Use templates with variable substitution
        - Fallback to simplified headline if no template match
  - [ ] 7.3 Add `plain_language_headline` field to database schema
        ```sql
        ALTER TABLE news_cache ADD COLUMN IF NOT EXISTS plain_language_headline TEXT;
        ```
  - [ ] 7.4 Store plain language translation during article ingestion
        - Generate translation after content classification
        - Store in `plain_language_headline` field
        - Use in API responses (fallback to original headline if null)

- [ ] 8. Update API responses to include SEC filing metadata
  - [ ] 8.1 Update `NewsArticle` model in `backend/app/api/news.py`
        ```python
        class NewsArticle(BaseModel):
            # Existing fields...
            filing_type: str | None = None
            filing_items: list[str] | None = None
            is_material_event: bool = False
            content_type: str | None = None  # PRIMARY, SECONDARY, etc.
            event_category: str | None = None  # earnings, insider_trade, etc.
            plain_language_headline: str | None = None
        ```
  - [ ] 8.2 Update SQL queries in `NewsService` to select new fields
  - [ ] 8.3 Update `build_news_payload()` to include new fields in response
  - [ ] 8.4 Verify `/api/news/market` and `/api/news/symbol/{symbol}` return new fields

- [ ] 9. Document SEC EDGAR integration
  - [ ] 9.1 Update `docs/core/NEWS_FEEDS.md` with SEC EDGAR section
        - Document filing types and their significance
        - Explain rate limits and compliance requirements
        - Provide examples of plain language translations
        - Document env toggles (SEC_EDGAR_ENABLED)
  - [ ] 9.2 Add SEC EDGAR to ARCHITECTURE.md data sources section
  - [ ] 9.3 Create `docs/reference/sec-edgar-filing-types.md` reference guide
        - Comprehensive list of filing types
        - 8-K item numbers and meanings
        - Form 4 transaction codes (P=purchase, S=sale, etc.)
        - Examples of material events

- [ ] 10. Performance optimization
  - [ ] 10.1 Implement caching for SEC RSS feeds (24-hour TTL)
        - SEC filings don't change once published
        - Cache RSS feed responses in memory or Redis
        - Reduce API calls to SEC servers
  - [ ] 10.2 Batch ticker requests efficiently
        - Group tickers to minimize RSS fetches
        - Fetch market-level news separately from ticker-specific
  - [ ] 10.3 Monitor SEC EDGAR source performance
        - Track fetch latency (target <2s per ticker)
        - Monitor rate limit compliance (stay under 2 req/sec)
        - Log errors and retry failed fetches

---

## Success Criteria

- ✅ SEC EDGAR source registered and active in NewsService
- ✅ 8-K, 10-Q, 10-K, Form 4 filings appear in news feed within 24h of filing
- ✅ Content classification correctly identifies SEC filings as PRIMARY
- ✅ Material events (8-K Item 2.02, large Form 4 trades) flagged correctly
- ✅ Plain language translations make filings accessible to everyday users
- ✅ `/api/news/health` shows sec_edgar as active with article counts
- ✅ Rate limiting complies with SEC guidelines (≤10 req/sec)
- ✅ All tests pass (unit + integration)
- ✅ Documentation complete and accurate

---

## Dependencies

**External**:
- SEC EDGAR RSS feeds (free, no API key)
- feedparser library (already in requirements.txt)

**Internal**:
- NewsService infrastructure (complete)
- MultiSourceFetcher (complete)
- Database migrations system (complete)

---

## Notes

- SEC EDGAR is **the** unfair advantage - institutional-grade data for $0
- Filings are legally binding, zero manipulation, highest signal-to-noise ratio
- Plain language translation is CRITICAL for everyday users (no jargon)
- This is Phase 1 foundation - Phase 2 will add impact summaries and actionable insights
