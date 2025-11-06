# Task List: News Phase 2 - Plain Language UI & News Intelligence

**Status**: Paused (20% complete, 2/10 tasks done)
**Created**: 2025-11-06
**Priority**: HIGH
**Estimated Effort**: 10-14 hours (2-3 days)
**Dependencies**: Phase 1 (SEC EDGAR Integration) complete
**Last Updated**: 2025-11-06 18:20
**Paused**: 2025-11-06 18:20 (Context limit - 86% used)

**✅ COMPLETE**: Task 1 (Story Clustering), Task 2 (Plain Language Translator)
**⏹️ NEXT**: Task 3 - Create News Intelligence component for watchlist API

<!-- PAUSED: 2025-11-06 18:20 - Resume with Task 3 -->

---

## Summary

Transform news from raw headlines into actionable intelligence with plain-language narratives, story clustering, and watchlist integration. Follow the PRD #0022 pattern: show "News Intelligence" card in watchlist expanded rows with plain-language summaries that everyday people can understand in 5 seconds.

**Goal**: Add "News Intelligence" section to watchlist with plain-language event summaries, sentiment analysis, and actionable insights (no financial jargon).

---

## Tasks

- [ ] 1. Implement semantic story clustering (deduplicate by story, not headline)
  - [ ] 1.1 Add sentence-transformers to requirements
        ```bash
        # Add to backend/requirements.txt
        sentence-transformers>=2.2.0
        ```
  - [ ] 1.2 Create `backend/app/services/story_clusterer.py`
        ```python
        class StoryClusterer:
            def __init__(self, model_name="all-MiniLM-L6-v2"):
                # Lightweight model, fast, good for sentence similarity
                self.model = SentenceTransformer(model_name)

            def cluster_articles(self, articles: list[NewsArticle]) -> list[Story]:
                # Generate embeddings for headlines + summaries
                # Cluster by cosine similarity (threshold 0.85)
                # Keep earliest article from highest-priority source
                # Track coverage_count (how many outlets covered)
        ```
  - [ ] 1.3 Add database fields for story clustering
        ```sql
        ALTER TABLE news_cache ADD COLUMN IF NOT EXISTS story_id TEXT; -- UUID for cluster
        ALTER TABLE news_cache ADD COLUMN IF NOT EXISTS is_primary_article BOOLEAN DEFAULT FALSE;
        ALTER TABLE news_cache ADD COLUMN IF NOT EXISTS coverage_count INT DEFAULT 1;

        CREATE INDEX IF NOT EXISTS idx_news_story_id ON news_cache(story_id) WHERE story_id IS NOT NULL;
        ```
  - [ ] 1.4 Integrate story clustering into NewsService
        - Run clustering after article ingestion
        - Store story_id, is_primary_article, coverage_count
        - Update deduplication logic to use story_id
  - [ ] 1.5 Test story clustering with real data
        - Find earnings story covered by 10+ outlets
        - Verify clustering groups all variants together
        - Check that primary article is from highest-priority source (SEC > FT > Google)

- [ ] 2. Enhance plain language translator with actionable insights
  - [ ] 2.1 Expand `plain_language_translator.py` with event templates
        ```python
        EVENT_TEMPLATES = {
            "earnings_beat": "Quarterly earnings beat expectations",
            "earnings_miss": "Quarterly earnings missed expectations",
            "insider_buy_large": "Insider buying: {person} bought ${amount} - bullish signal",
            "insider_sell_large": "Insider selling: {person} sold ${amount}",
            "analyst_upgrade": "Wall Street analyst raised price target",
            "analyst_downgrade": "Wall Street analyst lowered price target",
            "m_and_a": "Major business deal announced - {details}",
            "exec_change": "Executive leadership change: {details}",
        }
        ```
  - [ ] 2.2 Add actionable insight generator
        ```python
        def generate_actionable_insight(article: NewsArticle, watchlist: list[str]) -> str:
            """Generate 'what should I do?' recommendation."""
            if article.event_category == "earnings" and article.sentiment > 0.3:
                if article.ticker in watchlist:
                    return "Good news - consider adding to position if you own it"
                else:
                    return "Strong earnings - worth researching for potential entry"
            elif article.event_category == "insider_buying" and article.transaction_value > 1_000_000:
                return "Insiders are buying - bullish signal for long-term holders"
            # ... etc
        ```
  - [ ] 2.3 Add impact summary generator
        ```python
        def generate_impact_summary(article: NewsArticle) -> str:
            """Explain 'what this means' for traders."""
            if article.event_category == "earnings_beat":
                return "Strong results may drive stock higher short-term"
            elif article.event_category == "fed_rate_decision":
                return "May cause volatility across growth stocks tomorrow"
            # ... etc
        ```
  - [ ] 2.4 Add database fields for insights
        ```sql
        ALTER TABLE news_cache ADD COLUMN IF NOT EXISTS impact_summary TEXT;
        ALTER TABLE news_cache ADD COLUMN IF NOT EXISTS actionable_insight TEXT;
        ```

- [ ] 3. Create News Intelligence component for watchlist expanded row
  - [ ] 3.1 Update watchlist API response model
        ```python
        class NewsIntelligence(BaseModel):
            headline: str  # "Insider confidence + positive earnings surprise"
            sentiment_score: float  # +0.45
            sentiment_label: str  # "Positive"
            article_count_24h: int  # 12
            key_events: list[KeyEvent]  # Top 3 events
            recent_articles: list[NewsArticle]  # Top 5 articles

        class KeyEvent(BaseModel):
            icon: str  # "📋", "📈", "📰"
            text: str  # "Quarterly earnings beat expectations"
            time_ago: str  # "8 hours ago"
            is_material: bool
        ```
  - [ ] 3.2 Implement `build_news_intelligence()` in watchlist service
        - Query news_cache for ticker articles in last 24h
        - Filter to PRIMARY and SECONDARY content_type only
        - Calculate average sentiment
        - Extract top 3 material events (is_material_event=true)
        - Format key events with icons and plain language
        - Return NewsIntelligence object
  - [ ] 3.3 Add to watchlist snapshot response
        - Include `news_intelligence` field in WatchlistItemResponse
        - Populate during watchlist refresh
        - Cache for 6 hours (same as news TTL)

- [ ] 4. Build frontend News Intelligence card
  - [ ] 4.1 Create `frontend/components/watchlist/NewsIntelligenceCard.tsx`
        ```tsx
        export function NewsIntelligenceCard({ newsIntelligence, newsHidden }) {
          if (newsHidden) return null;
          if (!newsIntelligence) return null;

          return (
            <Card>
              <CardHeader>
                <CardTitle>📰 News Intelligence</CardTitle>
              </CardHeader>
              <CardContent>
                <h4>{newsIntelligence.headline}</h4>
                <div>Sentiment: {newsIntelligence.sentiment_label} ({newsIntelligence.sentiment_score})</div>
                <div>{newsIntelligence.article_count_24h} articles in 24h</div>

                <h5>Key Events:</h5>
                {newsIntelligence.key_events.map(event => (
                  <div key={event.text}>
                    {event.icon} {event.text} ({event.time_ago})
                  </div>
                ))}

                <h5>Recent Articles (showing {newsIntelligence.recent_articles.length}):</h5>
                {newsIntelligence.recent_articles.map(article => (
                  <div key={article.id}>
                    • {article.plain_language_headline || article.headline}
                    <br/>
                    {article.news_source_name} · {formatTimeAgo(article.published_at)} · [Read more →]
                  </div>
                ))}
              </CardContent>
            </Card>
          );
        }
        ```
  - [ ] 4.2 Add NewsIntelligenceCard to ExpandedRow component
        - Place between "Trading Intelligence" and "Trade Levels"
        - Respect user preference `watchlist_show_news`
        - Show/hide toggle in settings
  - [ ] 4.3 Style with shadcn/ui components
        - Match existing card styling
        - Use Badge components for sentiment
        - Add icons for event types (📋📈📰📉⚠️)
        - Format timestamps with "X hours ago" helper

- [ ] 5. Add priority indicators to main watchlist table
  - [ ] 5.1 Define priority indicators (matching PRD #0022 pattern)
        ```python
        PRIORITY_INDICATORS = {
            "earnings_alert": {
                "icon": "📋",
                "label": "Earnings Alert",
                "tooltip": "Earnings reported today - check results",
                "condition": lambda item: (
                    item.news_intelligence and
                    any(e.event_category == "earnings" for e in item.news_intelligence.key_events) and
                    any(e.hours_ago < 24 for e in item.news_intelligence.key_events)
                ),
                "priority": 1
            },
            "insider_buying": {
                "icon": "📈",
                "label": "Insider Buying",
                "tooltip": "Executives are buying - bullish signal",
                "condition": lambda item: (
                    item.news_intelligence and
                    any(e.event_category == "insider_trade" and e.transaction_value > 1_000_000
                        for e in item.news_intelligence.key_events)
                ),
                "priority": 2
            },
            "news_alert": {
                "icon": "📰",
                "label": "Breaking News",
                "tooltip": "Major news in last 24h - investigate",
                "condition": lambda item: (
                    item.news_intelligence and
                    item.news_intelligence.article_count_24h > 10
                ),
                "priority": 3
            },
            "negative_catalyst": {
                "icon": "📉",
                "label": "Negative News",
                "tooltip": "Bad news flow - wait for clarity",
                "condition": lambda item: (
                    item.news_intelligence and
                    item.news_intelligence.sentiment_score < -0.3
                ),
                "priority": 4
            }
        }
        ```
  - [ ] 5.2 Implement `calculate_priority_indicators()` in watchlist service
        - Evaluate all conditions for each ticker
        - Return top 2 indicators (highest priority wins)
        - Include icon, label, tooltip for frontend
  - [ ] 5.3 Add `priority_indicators` field to API response
  - [ ] 5.4 Update frontend WatchlistTable to show indicators
        - Add "Priority" column (or merge with "Signal" column)
        - Render icons with tooltips on hover
        - Limit to 2 indicators per row

- [ ] 6. Create standalone News page enhancement
  - [ ] 6.1 Add "Today's Big Stories" section to `/news` page
        ```tsx
        export function BigStories({ stories }) {
          return (
            <section>
              <h2>🔥 Today's Big Stories</h2>
              {stories.map(story => (
                <Card key={story.id}>
                  <h3>{story.plain_language_headline}</h3>
                  <p>{story.impact_summary}</p>
                  <div>
                    {story.coverage_count} related articles |
                    Sentiment: {story.sentiment_label} ({story.sentiment_score})
                  </div>
                  <Button onClick={() => expandStory(story.id)}>
                    Expand story →
                  </Button>
                </Card>
              ))}
            </section>
          );
        }
        ```
  - [ ] 6.2 Implement backend endpoint `GET /api/news/top-stories`
        - Cluster all market news from last 24h
        - Rank by: coverage_count * abs(sentiment_score) * material_event_weight
        - Return top 5 stories with metadata
  - [ ] 6.3 Add "Your Watchlist Impact" personalized section
        ```tsx
        export function WatchlistImpact({ watchlist, news }) {
          const impactedTickers = watchlist.filter(ticker =>
            news.hasRecentNews(ticker) || news.hasHighSentiment(ticker)
          );

          return (
            <section>
              <h2>📈 Your Watchlist Impact</h2>
              {impactedTickers.map(ticker => (
                <div key={ticker}>
                  • {ticker}: {news.getImpactSummary(ticker)}
                </div>
              ))}
            </section>
          );
        }
        ```
  - [ ] 6.4 Implement backend endpoint `GET /api/news/watchlist-impact?account_id=X`
        - Get user's watchlist tickers
        - For each ticker, check for news in last 24h
        - Generate impact summary in plain language
        - Return ticker-level insights

- [ ] 7. Add user settings for news preferences
  - [ ] 7.1 Add news preference fields to user_preferences table
        ```sql
        ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS news_content_filters JSONB DEFAULT '{
          "sec_filings": true,
          "earnings": true,
          "insider_trades": true,
          "analyst_ratings": true,
          "market_news": true,
          "opinion_pieces": false,
          "press_releases": false
        }';
        ```
  - [ ] 7.2 Add settings UI in `/settings` page
        ```tsx
        <FormSection title="News Preferences">
          <Switch
            label="Show news in watchlist"
            checked={preferences.watchlist_show_news}
            onChange={...}
          />
          <RadioGroup
            label="News lookback window"
            options={["6h", "12h", "24h", "48h"]}
            value={preferences.news_lookback_hours}
            onChange={...}
          />
          <RadioGroup
            label="Max headlines per ticker"
            options={[5, 10, 15, 20]}
            value={preferences.news_max_articles}
            onChange={...}
          />
          <CheckboxGroup
            label="Content filters"
            options={[
              { label: "SEC filings (8-K, 10-Q, Form 4)", value: "sec_filings" },
              { label: "Earnings announcements", value: "earnings" },
              { label: "Insider trading", value: "insider_trades" },
              { label: "Analyst ratings", value: "analyst_ratings" },
              { label: "Market news (Reuters, FT, WSJ)", value: "market_news" },
              { label: "Opinion pieces", value: "opinion_pieces" },
              { label: "Press releases", value: "press_releases" },
            ]}
            value={preferences.news_content_filters}
            onChange={...}
          />
        </FormSection>
        ```
  - [ ] 7.3 Wire settings to backend API
        - Update `/api/preferences` endpoint to handle news filters
        - Apply filters during news ingestion
        - Filter articles based on content_type and user preferences

- [ ] 8. Testing and validation
  - [ ] 8.1 Unit tests for plain language translator
        - Test SEC filing translations (8-K → "Earnings reported")
        - Test insight generation (earnings beat → "Good news - consider adding")
        - Test impact summaries
  - [ ] 8.2 Unit tests for story clustering
        - Test embedding generation
        - Test similarity clustering (same story, different outlets)
        - Test primary article selection (highest priority source wins)
  - [ ] 8.3 Integration tests for News Intelligence API
        - Test `/api/news/top-stories` returns clustered stories
        - Test `/api/news/watchlist-impact` personalizes to user's tickers
        - Test watchlist endpoint includes news_intelligence field
  - [ ] 8.4 Browser automation screenshots
        - Capture watchlist expanded row with News Intelligence card
        - Capture /news page with "Today's Big Stories"
        - Capture settings page with news preferences
        - Save to `docs/screenshots/news/phase2-*.png`

- [ ] 9. Documentation
  - [ ] 9.1 Update `docs/core/NEWS_FEEDS.md`
        - Document plain language translation system
        - Explain story clustering and deduplication
        - Document actionable insights logic
  - [ ] 9.2 Update `docs/core/API_REFERENCE.md`
        - Document new endpoints: `/api/news/top-stories`, `/api/news/watchlist-impact`
        - Document new fields in watchlist response (news_intelligence, priority_indicators)
  - [ ] 9.3 Create user guide `docs/user-guides/news-intelligence.md`
        - Explain News Intelligence card in plain language
        - Show example priority indicators and what they mean
        - Explain content filters and how to customize

- [ ] 10. Performance optimization
  - [ ] 10.1 Cache story clustering results (6-hour TTL)
        - Clustering is expensive, don't recompute every request
        - Store embeddings in Redis or database
  - [ ] 10.2 Optimize database queries for news intelligence
        - Add indexes for common queries (ticker + published_at + is_material_event)
        - Use efficient JOINs to fetch related articles
  - [ ] 10.3 Monitor plain language translation performance
        - If using LLM (Llama), measure latency (target <500ms)
        - If using templates, should be <10ms
        - Cache translations to avoid recomputation

---

## Success Criteria

- ✅ Watchlist expanded row shows "News Intelligence" card with plain-language summaries
- ✅ Priority indicators (📋📈📰) appear in main table for material events
- ✅ /news page shows "Today's Big Stories" with clustered articles
- ✅ "Your Watchlist Impact" personalizes news to user's holdings
- ✅ Settings page allows filtering news content types
- ✅ Plain language translations make news accessible to everyday people
- ✅ Story clustering reduces duplicate headlines by 60%+
- ✅ All tests pass (unit + integration)
- ✅ Screenshots demonstrate UI working with real data
- ✅ Documentation complete

---

## Dependencies

**Phase 1 Complete**:
- SEC EDGAR source integrated
- Content classification system
- Database schema with filing metadata

**External**:
- sentence-transformers library (for clustering)
- Frontend: shadcn/ui components

---

## Notes

- Follow PRD #0022 pattern: "Trading Intelligence" → "News Intelligence"
- ZERO JARGON rule: "Earnings beat expectations" NOT "EPS $0.75 vs est. $0.68"
- Actionable insights answer "What should I do?"
- Impact summaries answer "What does this mean?"
- 5-second comprehension test: Would a non-trader understand this?
