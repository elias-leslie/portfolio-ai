# Task List: News Phase 3 - Cleanup, RSS Optimization & Polish

**Status**: Not Started
**Created**: 2025-11-06
**Priority**: MEDIUM
**Estimated Effort**: 6-8 hours (1-2 days)
**Dependencies**: Phase 1 and Phase 2 complete

---

## Summary

Clean up existing RSS feeds, remove low-quality sources, fix Finnhub credential loading, and polish the overall news experience. Focus on quality over quantity - keep only free tier sources that provide high signal-to-noise ratio.

**Goal**: Optimize news source mix to achieve <10% noise, 60% deduplication, and comprehensive coverage from 100% free sources.

---

## Tasks

- [ ] 1. Fix Finnhub credential loading (complete Task 11.3 from news-source-enhancements.md)
  - [ ] 1.1 Verify credentials are in database
        ```bash
        psql -U portfolio_ai_user -d portfolio_ai -c "SELECT source_id, field, LEFT(value, 10) || '...' as masked FROM source_credentials WHERE source_id = 'finnhub';"
        ```
  - [ ] 1.2 Test credential loading in isolation
        ```python
        from app.storage.credential_loader import load_credentials_from_database
        import os
        load_credentials_from_database()
        print("FINNHUB_API_KEY:", os.getenv("FINNHUB_API_KEY")[:10] + "..." if os.getenv("FINNHUB_API_KEY") else "NOT LOADED")
        ```
  - [ ] 1.3 Restart services and verify Finnhub shows articles in `/api/news/health`
        ```bash
        bash ~/portfolio-ai/scripts/restart.sh
        # Wait 2 minutes for service startup
        curl -s http://192.168.8.233:8000/api/news/health | python3 -m json.tool | grep -A 10 '"finnhub"'
        ```
  - [ ] 1.4 If still showing 0 articles, add debug logging
        ```python
        # In FinnhubSource.fetch_news_payload()
        logger.info("finnhub_news_fetch_start", ticker=ticker, api_key_present=bool(os.getenv("FINNHUB_API_KEY")))
        ```
  - [ ] 1.5 Monitor for 24 hours to confirm stable article flow (target: 30-50 articles/day)

- [ ] 2. Remove Polygon news source (not available on free tier)
  - [ ] 2.1 Update `NewsService._prepare_vendor_sources()` to skip Polygon news
        ```python
        # Comment out or remove Polygon news registration
        # Keep Polygon for price/reference data, but not news
        # polygon_flag = self._env_flag("POLYGON_NEWS_ENABLED", default=False)  # Changed to False
        ```
  - [ ] 2.2 Update `docs/core/NEWS_FEEDS.md` to mark Polygon as paid-only
        - Note: "Polygon news endpoints require paid tier ($199+/month)"
        - Polygon still used for OHLCV data (free tier supports day bars)
  - [ ] 2.3 Set `POLYGON_NEWS_ENABLED=0` in `.env`
  - [ ] 2.4 Verify Polygon disappears from `/api/news/health` vendors list

- [ ] 3. Clean up RSS feeds (remove low-quality sources)
  - [ ] 3.1 Test each RSS feed URL manually to verify freshness
        ```bash
        # Test CNBC
        curl -s "https://www.cnbc.com/id/100003114/device/rss/rss.html" | head -50

        # Test MarketWatch
        curl -s "https://feeds.marketwatch.com/marketwatch/topstories/" | head -50

        # Test Seeking Alpha
        curl -s "https://seekingalpha.com/feed.xml" | head -50
        ```
  - [ ] 3.2 Evaluate article quality from each source over 24-hour period
        - Check sentiment analysis accuracy (FinBERT scores)
        - Check relevance to trading/investing
        - Check noise level (promotional content, ads, irrelevant topics)
  - [ ] 3.3 Remove low-quality RSS sources
        - **Remove Seeking Alpha**: Retail opinions, not institutional-grade
        - **Remove Fortune**: General business, not trading-focused
        - **Remove Investing.com**: Ad-heavy, questionable quality
        - Keep: FT, Reuters, Nasdaq, MarketWatch (filtered)
  - [ ] 3.4 Update `NewsService._prepare_vendor_sources()` to exclude removed sources
        - Comment out or remove from rss_configs list
        - Update NEWS_FEEDS.md to document removals
  - [ ] 3.5 Add high-quality RSS sources if free feeds exist
        ```python
        # Add Reuters Business (if not already present)
        ("reuters_business", ReutersBusinessRssSource, "Reuters Business News", "REUTERS_RSS_ENABLED"),

        # Add WSJ Markets (if free RSS available)
        ("wsj_markets", WSJMarketsRssSource, "WSJ Markets RSS", "WSJ_RSS_ENABLED"),

        # Add Bloomberg (if free RSS available)
        ("bloomberg_markets", BloombergMarketsRssSource, "Bloomberg Markets", "BLOOMBERG_RSS_ENABLED"),
        ```

- [ ] 4. Debug why RSS feeds return 0 articles
  - [ ] 4.1 Add comprehensive debug logging to `RssNewsSource.fetch_news_payload()`
        ```python
        logger.info("rss_fetch_start", source=self.name, feeds=self.feeds, tickers=list(tickers))

        for url in urls:
            logger.info("rss_fetch_url", source=self.name, url=url)
            entries = self._fetch_feed_entries(url)
            logger.info("rss_fetch_result", source=self.name, url=url, entry_count=len(entries))

            for entry in entries:
                record = self._entry_to_record(entry, normalized_ticker)
                if record is None:
                    logger.debug("rss_entry_skipped", source=self.name, reason="failed_to_parse")
                    continue

                published_at = record.get("published_at")
                if published_at and (published_at < start_utc or published_at > end_utc):
                    logger.debug("rss_entry_skipped", source=self.name, reason="outside_date_range",
                                published_at=published_at.isoformat(), window=f"{start_utc} to {end_utc}")
                    continue
        ```
  - [ ] 4.2 Run manual news refresh and check logs
        ```bash
        # Tail logs in real-time
        cd /home/kasadis/portfolio-ai/backend
        .venv/bin/python -c "
        from app.storage import PortfolioStorage
        from app.services.news_service import NewsService
        storage = PortfolioStorage()
        ns = NewsService(storage)
        bundle = ns.get_market_news(force_refresh=True, max_articles=20)
        print(f'Articles: {len(bundle.articles)}')
        for article in bundle.articles[:5]:
            print(f'  - {article.vendor}: {article.headline}')
        "
        ```
  - [ ] 4.3 Hypotheses to test:
        - **Ticker matching**: RSS feeds are market-level, not ticker-specific → may not match `tickers` param
        - **Date filtering too strict**: 48h window might miss older RSS items
        - **Feed parsing errors**: feedparser may fail silently on some RSS formats
        - **User-Agent required**: Some RSS feeds block requests without proper User-Agent
  - [ ] 4.4 Fix identified issues:
        - If ticker matching: Adjust `_urls_for_ticker()` to return market feeds for `__MARKET__`
        - If date filtering: Widen window or remove strict filtering for RSS
        - If parsing errors: Add try/except with logging around feedparser calls
        - If User-Agent: Ensure all RSS requests include User-Agent header

- [ ] 5. Implement content filtering to reduce noise
  - [ ] 5.1 Create keyword-based noise filters
        ```python
        NOISE_KEYWORDS = [
            "sponsored", "advertisement", "paid promotion",
            "buy now", "limited time offer", "act fast",
            "PR Newswire", "Business Wire", "GlobeNewswire",
        ]

        OPINION_KEYWORDS = [
            "opinion", "editorial", "commentary", "analysis",
            "why you should", "top 10", "best stocks",
        ]

        def is_noise(headline: str, summary: str) -> bool:
            text = (headline + " " + summary).lower()
            return any(keyword in text for keyword in NOISE_KEYWORDS)

        def is_opinion(headline: str, summary: str) -> bool:
            text = (headline + " " + summary).lower()
            return any(keyword in text for keyword in OPINION_KEYWORDS)
        ```
  - [ ] 5.2 Apply filters during article ingestion
        - Skip articles marked as NOISE (don't store)
        - Mark articles as TERTIARY if opinion/analysis
        - Only show PRIMARY + SECONDARY in watchlist by default
  - [ ] 5.3 Respect user's content filter preferences
        - Check `news_content_filters` from user_preferences
        - Filter articles based on content_type and event_category
        - Apply filters in API responses, not just ingestion

- [ ] 6. Optimize article mix and deduplication
  - [ ] 6.1 Verify round-robin vendor selection is working
        ```bash
        curl -s http://192.168.8.233:8000/api/news/health | python3 -m json.tool | jq '.article_mix'
        ```
        - Check `per_vendor_post_dedupe` distribution
        - No single vendor should dominate (>70%)
  - [ ] 6.2 Monitor deduplication ratio
        - Target: 60% deduplication (total_pre=500 → total_post=200)
        - Check `article_mix.dedupe_ratio` in health response
  - [ ] 6.3 If deduplication too low (<40%), tighten similarity threshold
        - Adjust content hash in `_merge_entries()` to catch more duplicates
        - Consider title similarity (Levenshtein distance) in addition to exact match
  - [ ] 6.4 If deduplication too high (>80%), loosen threshold
        - May be losing unique stories
        - Review dedupe logic to ensure distinct stories aren't merged

- [ ] 7. Add monitoring and alerting for news health
  - [ ] 7.1 Create health check script `scripts/check-news-health.sh`
        ```bash
        #!/bin/bash
        # Check news system health
        HEALTH=$(curl -s http://192.168.8.233:8000/api/news/health)

        # Check total articles in 24h (target: 200-500)
        TOTAL=$(echo "$HEALTH" | jq '.headlines_24h')
        if [ "$TOTAL" -lt 100 ]; then
          echo "WARNING: Only $TOTAL articles in 24h (target: 200-500)"
        fi

        # Check vendor bias (no single vendor >70%)
        VENDORS=$(echo "$HEALTH" | jq '.article_mix.per_vendor_post_dedupe')
        # ... parse and check percentages

        # Check fallback rate (target: <10%)
        FALLBACK=$(echo "$HEALTH" | jq '.fallback_rate_24h')
        if (( $(echo "$FALLBACK > 0.1" | bc -l) )); then
          echo "WARNING: FinBERT fallback rate $FALLBACK (target: <10%)"
        fi
        ```
  - [ ] 7.2 Add to cron or monitoring system (optional)
        - Run every 6 hours
        - Send alerts if thresholds exceeded
  - [ ] 7.3 Document monitoring thresholds in `docs/core/OPERATIONS.md`

- [ ] 8. Performance benchmarking
  - [ ] 8.1 Benchmark news refresh time for 50 tickers
        ```python
        import time
        start = time.time()
        # Refresh watchlist news
        elapsed = time.time() - start
        print(f"Refresh time: {elapsed:.2f}s for {ticker_count} tickers")
        # Target: <10 seconds for 50 tickers
        ```
  - [ ] 8.2 Benchmark API response time for `/api/news/market`
        ```bash
        time curl -s http://192.168.8.233:8000/api/news/market?max_results=20
        # Target: <500ms with cache hit
        ```
  - [ ] 8.3 If performance issues, optimize:
        - Add database indexes (ticker + published_at)
        - Increase cache TTL for market news (6h → 12h)
        - Batch database queries instead of N+1

- [ ] 9. Final testing and validation
  - [ ] 9.1 End-to-end test: Add new ticker to watchlist
        - Add AAPL to watchlist
        - Wait for scheduled refresh (or force refresh)
        - Verify news appears in expanded row
        - Check priority indicators show for material events
  - [ ] 9.2 Test content filtering
        - Add opinion piece to news_cache with content_type=TERTIARY
        - Verify it's filtered out in watchlist if user preference disabled
        - Verify it appears if user enables opinion pieces in settings
  - [ ] 9.3 Test story clustering
        - Find earnings story covered by 10+ outlets (e.g., NVDA earnings)
        - Verify all variants cluster to same story_id
        - Check coverage_count reflects total outlets
        - Verify primary article is from highest-priority source (SEC > FT > Google)
  - [ ] 9.4 Browser automation: Capture final screenshots
        - `/watchlist` with News Intelligence card populated
        - `/news` with "Today's Big Stories" and "Your Watchlist Impact"
        - `/settings` with news preferences UI
        - Save to `docs/screenshots/news/phase3-final-*.png`

- [ ] 10. Documentation updates
  - [ ] 10.1 Update `docs/core/NEWS_FEEDS.md` with final vendor list
        - Document which sources kept vs removed and why
        - Update rate limits, compliance notes
        - Add troubleshooting section for common issues
  - [ ] 10.2 Update `README.md` with news feature highlights
        - "SEC EDGAR filings integration (institutional-grade, $0 cost)"
        - "Plain language news intelligence - no financial jargon"
        - "Story clustering reduces duplicate headlines by 60%"
  - [ ] 10.3 Create `docs/user-guides/getting-started-with-news.md`
        - Explain what news sources are included
        - Show how to customize news preferences
        - Explain priority indicators and what they mean
        - Screenshots with annotations

---

## Success Criteria

- ✅ Finnhub contributing 30-50 articles/day (credential loading fixed)
- ✅ Polygon news removed/disabled (not free)
- ✅ Low-quality RSS feeds removed (Seeking Alpha, Fortune, Investing.com)
- ✅ Noise filtering reduces junk to <10% of total articles
- ✅ Article mix balanced: No vendor >70%, SEC filings prioritized
- ✅ Deduplication ratio 50-70% (reduces duplicates without losing stories)
- ✅ News refresh time <10s for 50 tickers
- ✅ `/api/news/market` response time <500ms (cached)
- ✅ All tests pass, screenshots captured, documentation complete

---

## Dependencies

**Phase 1 & 2 Complete**:
- SEC EDGAR source
- Plain language translation
- News Intelligence UI

**External**: None (all free tier)

---

## Notes

- Focus on quality over quantity: 200 high-signal articles > 1000 noisy headlines
- Monitor vendor mix daily for first week to ensure stability
- User feedback loop: Track which content filters users enable/disable
- RSS feeds may degrade over time (feeds move, break, get paywalled) - plan for maintenance
