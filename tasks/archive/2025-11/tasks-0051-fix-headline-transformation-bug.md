# Task 0 (URGENT): Fix Plain Language Headline Transformation Bug

**Priority**: CRITICAL - Blocks Phase 2 (feedback loop training on wrong data)
**Complexity**: LOW (disable broken feature + add sentiment override)
**Effort**: 1 hour
**Environment**: Local Dev
**Created**: 2025-11-11

---

## Problem Statement

**CRITICAL BUG**: Plain language headline transformation is completely broken:

1. **Wrong transformations**: "Tesla Stock Is Slipping" → "Company made more money than expected"
2. **Sentiment mismatch**: Sentiment scored on original (-0.96 negative), but user sees transformed headline (looks positive)
3. **User confusion**: Can't understand why positive-sounding headline has negative sentiment
4. **Training data corruption**: User feedback trains on wrong articles (feedback meant for one article applied to another)

**Example from production**:
```
Original: "Tesla Stock Is Slipping Today"
Transformed: "TSLA: Company made more money than expected"
Sentiment: -0.96 NEGATIVE (scored on original)
User sees: Positive words + negative sentiment = ???
```

---

## Root Cause

**File**: `backend/app/services/plain_language_news.py`
**Issue**: Naive keyword matching in `classify_event_category()` (lines 146-150)
- Generic patterns: "revenue" + "strong" → EARNINGS_BEAT
- Misclassifies headlines or defaults to wrong category
- Replaces real headlines with templates like "Company made more money than expected"
- Sentiment is scored on ORIGINAL headline, not transformation
- Creates mismatch between displayed text and sentiment score

---

## Solution

### Phase 1: Disable Broken Feature (30 min)

**Immediate fix**: Stop using `plain_language_headline` until proper LLM available

- [ ] 1.1 Update frontend to display ORIGINAL headline only
  - [ ] File: `frontend/components/watchlist/UnifiedNewsIntelligenceCard.tsx`
  - [ ] Change: `article.plain_language_headline || article.headline` → `article.headline`
  - [ ] Remove plain_language_headline display entirely

- [ ] 1.2 Disable backend generation (don't populate field)
  - [ ] File: `backend/app/services/news_ai_features.py` line 127-135
  - [ ] Comment out or add flag: `ENABLE_PLAIN_LANGUAGE = False`
  - [ ] Skip `translate_to_plain_language()` call when disabled

- [ ] 1.3 Keep existing data (don't delete column)
  - [ ] Database column remains (for future proper LLM integration)
  - [ ] Just stop populating new articles

### Phase 2: Add Sentiment Override Buttons (30 min)

**User control**: Let users correct bad sentiment scoring

- [ ] 2.1 Add sentiment override to article feedback
  - [ ] Extend `user_article_feedback` table with `sentiment_override` column:
    ```sql
    ALTER TABLE user_article_feedback
    ADD COLUMN sentiment_override FLOAT CHECK (sentiment_override >= -1.0 AND sentiment_override <= 1.0);
    ```
  - [ ] Store user's corrected sentiment when they thumbs up/down

- [ ] 2.2 Update feedback API to accept sentiment override
  - [ ] Modify POST `/api/news/article-feedback` to accept optional `sentiment_override`
  - [ ] When user clicks thumbs up on negative article: `{is_useful: true, sentiment_override: 0.9}`
  - [ ] When user clicks thumbs down on positive article: `{is_useful: false, sentiment_override: -0.9}`

- [ ] 2.3 Add "Correct Sentiment" option to UI
  - [ ] Two-step process:
    1. Thumbs up/down saves usefulness
    2. If sentiment seems wrong, show "Correct Sentiment?" dialog
    3. User picks: Positive/Neutral/Negative
    4. Saves sentiment_override to database

- [ ] 2.4 Use overrides in future processing
  - [ ] When calculating quality metrics, prefer `sentiment_override` over `sentiment_score`
  - [ ] Helps FinBERT improve over time (corrected training data)

---

## Verification

**After Phase 1 (disable):**
```bash
# Check frontend shows real headlines
# Navigate to http://192.168.8.233:3000/watchlist
# Verify: Real headlines shown ("Tesla Stock Is Slipping Today")
# Verify: Sentiment matches headline (-0.96 for slipping = correct)
```

**After Phase 2 (sentiment override):**
```bash
# Find article with wrong sentiment
# Click thumbs up/down
# Click "Correct Sentiment"
# Select correct sentiment
# Check database:
psql -U portfolio_ai_user -d portfolio_ai -c "SELECT vendor, is_useful, sentiment_override FROM user_article_feedback WHERE sentiment_override IS NOT NULL LIMIT 5;"
```

---

## Success Criteria

✅ **Phase 1 Complete**:
- Frontend shows real headlines only (no transformations)
- Sentiment matches what user sees
- No more confusion about positive words + negative sentiment

✅ **Phase 2 Complete**:
- Users can correct bad sentiment via UI
- Overrides saved to database
- Future quality metrics use corrected sentiment

---

## Future Proper Implementation

**When ready** (Phase 3+):
- Integrate OpenAI/Anthropic for REAL plain language transformation
- Use LLM to genuinely simplify jargon ("EPS beat" → "made more money")
- Generate transformations that are CORRECT
- Re-enable `plain_language_headline` with confidence checks

**Don't do now**:
- Naive keyword matching is worse than useless
- Generic templates destroy information
- Wait for proper LLM before enabling

---

**Estimated Effort**: 1 hour
**Blocks**: Phase 2 feedback loop (training on wrong data)
**Risk Level**: LOW (disabling broken feature is safe)
