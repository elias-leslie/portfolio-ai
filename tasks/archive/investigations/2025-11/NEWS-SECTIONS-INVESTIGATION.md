# News Sections Investigation - Facts Only

**Date**: 2025-11-08
**Investigated By**: Local Agent
**Method**: Code analysis + API data inspection + Database queries

---

## Question: Why are there TWO news sections?

### Section 1: "News Intelligence" (NEW - Added by cloud agent)
- **Component**: `NewsIntelligenceCard.tsx`
- **Data Source**: `item.news_intelligence` (from API)
- **Location**: Line 940 in `ExpandedRow.tsx`

**What it shows**:
- AI-generated summary headline (e.g., "Mixed news (20 articles in 24h)")
- Overall sentiment score + label
- Article count in 24h
- Key events list (with icons)
- Recent articles (top 5)

**What it's SUPPOSED to do**:
- Display `plain_language_headline` (simplified, jargon-free headlines)
- Display `impact_summary` ("Very positive news - may create short-term momentum")
- Display `actionable_insight` ("Positive sentiment - worth investigating")

### Section 2: "News & Sentiment" (ORIGINAL - User likes this)
- **Location**: Line 968 in `ExpandedRow.tsx`
- **Data Source**: `item.recent_news` (from API)

**What it shows**:
- Sentiment score with change indicator (e.g., "+0.18" with ↑ arrow)
- Model coverage stats ("FinBERT: 85%, Fallback: 15%")
- Sentiment confidence percentage
- Headline mix breakdown
- Detailed article list (up to 5 articles)
- Article metadata: publisher, source, timestamp, sentiment badge

---

## Finding #1: Both Sections Show THE SAME Articles

**Fact**: Both `news_intelligence.recent_articles[]` and `recent_news.articles[]` contain identical source data.

**Evidence** (from API response for NVDA):
```json
news_intelligence.recent_articles[0] = {
  "headline": "Amazon and OpenAI agree $38bn partnership to boost AI development",
  "source": "Retail Insight Network",
  "sentiment_score": 0.8845,
  "plain_language_headline": "News reported - check details"  ← PLACEHOLDER
}

recent_news.articles[0] = {
  "headline": "Amazon and OpenAI agree $38bn partnership to boost AI development",
  "source": "Retail Insight Network",
  "sentiment": {"score": 0.8845, "label": "positive"}
}
```

**Conclusion**: Same articles, different presentation. The "News Intelligence" section was meant to show AI-simplified headlines, but that feature is broken.

---

## Finding #2: "News reported - check details" Is a PLACEHOLDER

**Root Cause**: `plain_language_headline` generation is failing for 57% of articles.

**Database Stats** (4,752 total news articles):
- **667 (14%)** - Have real plain_language_headline (working)
- **2,727 (57%)** - Have placeholder "News reported - check details" (BROKEN)
- **1,358 (29%)** - Have NULL (not processed yet)

**Why It's Failing**:
- `plain_language_news.py` uses keyword-based pattern matching
- Only matches specific patterns like:
  - "earnings beat", "analyst upgrade", "merger announced"
  - "insider buy", "CEO change", "product launch"
- Most news doesn't match these patterns → falls to `EventCategory.UNKNOWN`
- EventCategory.UNKNOWN → returns "News reported - check details" (line 102)

**Example Article That Fails**:
- Headline: "Amazon and OpenAI agree $38bn partnership to boost AI development"
- Pattern matching: Checks for "merger", "acquisition", "partner" keywords
- Result: Matches "partner" but not full pattern → EventCategory.UNKNOWN
- Output: "News reported - check details" ❌

---

## Finding #3: The "News Intelligence" Section Is INCOMPLETE

**What Cloud Agent Tried to Build**:
- Plain language translation (jargon-free headlines)
- Impact summaries for traders
- Actionable insights

**What Actually Works**:
- ✅ AI-generated summary headline ("Mixed news (20 articles in 24h)")
- ✅ Sentiment aggregation
- ✅ Key events extraction
- ❌ Plain language headlines (57% placeholders)
- ✅ Impact summaries (generated, but generic)
- ✅ Actionable insights (generated, but generic)

**Code Evidence** (`NewsIntelligenceCard.tsx` line 136-138):
```typescript
const displayHeadline =
    article.plain_language_headline ||
    article.headline;  // Falls back to raw headline
```

So when `plain_language_headline` is "News reported - check details", that's what displays!

---

## Finding #4: Both Have Value, But Different Purposes

**News Intelligence Section**:
- **Goal**: Simplified, actionable summaries
- **Audience**: Everyday traders (zero jargon)
- **Format**: Compact, scannable, AI-enhanced
- **Status**: Broken (placeholder headlines)

**News & Sentiment Section**:
- **Goal**: Detailed sentiment analysis with metrics
- **Audience**: Data-driven traders
- **Format**: Comprehensive stats (model coverage, confidence, mix)
- **Status**: Working perfectly

---

## User Requirements (From Discussion)

1. **Keep "News & Sentiment" section** - User likes the detailed stats
2. **Default to collapsed view** - Show top positive + top negative only
3. **Expandable** - Click to see all articles
4. **Keep detail metrics**: confidence, model coverage, headline mix
5. **Fix the placeholder issue** - Show actual article titles, not "News reported"

---

## Recommendations

### Option 1: Remove "News Intelligence" Section (RECOMMENDED)
**Rationale**:
- The feature is broken (57% placeholders)
- Both sections show same articles
- "News & Sentiment" has more useful data (coverage stats, confidence)
- Plain language translation only works for 14% of articles
- Fixing the classification would require LLM calls (expensive, slow)

**Action**:
- Delete `NewsIntelligenceCard` component
- Keep only "News & Sentiment" section
- Add collapsed/expanded view to "News & Sentiment"
- Show top positive + top negative by default
- Remove placeholder headlines entirely

### Option 2: Fix "News Intelligence" Section (NOT RECOMMENDED)
**Rationale**:
- Would require adding LLM calls to generate real plain language headlines
- Expensive (4,752 articles × $0.0001/call = $0.48/day minimum)
- Slow (adds 2-3s latency per article)
- Still duplicates "News & Sentiment" functionality
- Only 14% success rate with current keyword approach

**Action**:
- Integrate OpenAI/Anthropic API for headline translation
- Add caching layer
- Add error handling for failed translations
- Still need collapsed/expanded view

### Option 3: Hybrid Approach (COMPROMISE)
**Rationale**:
- Keep both sections but consolidate
- Use "News & Sentiment" as primary
- Add plain language headlines ONLY for the 14% that work
- Show fallback to original headline for the rest

**Action**:
- Update "News & Sentiment" to show `plain_language_headline` when available
- Fall back to `headline` when placeholder detected
- Remove duplicate "News Intelligence" section
- Add collapsed/expanded view

---

## My Honest Recommendation

**Remove "News Intelligence" section entirely. Here's why:**

1. **Data Duplication**: Both sections show the exact same articles
2. **Broken Feature**: 57% placeholders make it look unfinished
3. **Better Alternative Exists**: "News & Sentiment" has more useful stats
4. **Expensive to Fix**: Would require LLM API calls per article
5. **User Already Likes the Original**: They said "News & Sentiment" looks better

**What to Build Instead**:

**Enhanced "News & Sentiment" Section**:
```
📊 News & Sentiment
Mixed sentiment (+0.18) • 20 articles in 24h
85% FinBERT • 15% Fallback • 92% Confidence

[Collapsed View - DEFAULT]
📈 Top Positive: "Amazon partners with OpenAI..." (+0.88)
📉 Top Negative: "SEC investigation..." (-0.65)
[Expand to see all 18 articles]

[Expanded View - ON CLICK]
[All 20 articles with full details]

Stats: Model Coverage, Confidence, Headline Mix
```

This gives users:
- ✅ Quick scan (top pos/neg)
- ✅ Full details when needed (expand)
- ✅ Real article titles (no placeholders)
- ✅ Same detailed stats they like
- ✅ No broken features
- ✅ No duplicate sections

---

## Files Involved

**Frontend**:
- `frontend/components/watchlist/ExpandedRow.tsx` (line 940 + 968)
- `frontend/components/watchlist/NewsIntelligenceCard.tsx` (entire file - candidate for deletion)

**Backend**:
- `backend/app/services/plain_language_news.py` (classification logic)
- `backend/app/watchlist/watchlist_service.py` (assembles news_intelligence data)

**Database**:
- `news_cache.plain_language_headline` column (57% placeholders)

---

**Investigation Complete**. Ready to discuss with user and update CRITICAL-ISSUES-FOUND.md based on decision.
