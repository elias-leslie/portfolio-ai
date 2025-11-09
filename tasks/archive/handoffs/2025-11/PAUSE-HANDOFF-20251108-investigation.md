# Work Session Handoff - Watchlist Investigation & Planning

**Date**: 2025-11-08 23:45 | **Progress**: Investigation Complete
**Branch**: `claude/watchlist-vision-implementation-011CUw9W27dCwbxtwbECZsKT`
**Context Used**: 55% (110K/200K tokens) - User requested pause for fresh /do_it session

---

## Current Status

✅ **Completed This Session:**
- Comprehensive watchlist implementation review (browser automation + code analysis)
- News sections investigation (why two sections exist)
- Plain language news system analysis (pattern matching bugs found)
- Article quality ranking system design
- LLM integration architecture (Claude/Qwen/local models)
- Complete 2-session fix plan documented

❌ **No Code Written This Session** - Pure investigation and planning

⏹️ **Ready for Implementation:**
- Session 1: Bug fixes (3-4 hours)
- Session 2: News intelligence overhaul (5-8 hours)

---

## Key Findings

### 1. Watchlist Implementation Reality Check

**Grade: B-** (was incorrectly assessed as A+ initially)

**What Works:**
- ✅ Backend: Excellent (A+ grade) - 3-pillar scoring, fundamentals integration
- ✅ Main Table: Good (B+ grade) - filters, search, expand/collapse work
- ✅ Settings: Acceptable - centralized `/settings` page is fine

**Critical Bugs Found (5 issues):**
1. ⭐⭐⭐⭐⭐ Price column data not showing
2. ⭐⭐⭐⭐⭐ Score breakdown identical for all stocks (hardcoded?)
3. ⭐⭐⭐⭐ Two news sections instead of one (duplicate data)
4. ⭐⭐⭐⭐ "Legacy Score Weights (Deprecated)" visible in settings
5. ⭐⭐⭐⭐ News page stuck on "Loading..." infinitely

**Assessment Method:**
- Browser automation screenshots
- API data inspection
- Code analysis
- Database queries

### 2. News Sections Mystery Solved

**Problem**: Two separate news sections showing same data
- "News Intelligence" - NEW (cloud agent added)
- "News & Sentiment" - ORIGINAL (user prefers this)

**Root Cause**:
- Both pull from same articles
- "News Intelligence" tries to show plain language headlines
- 57% of articles get placeholder "News reported - check details"
- Pattern matching has 6 missing categories (PARTNERSHIP, PRODUCT_LAUNCH, etc.)

**Solution**:
- Combine into ONE unified section
- Add LLM for headline translation (Claude ~$0.90/month OR local Qwen $0)
- Smart article ranking (sentiment + materiality + source + recency)
- Collapsed by default (top positive + top negative)
- Deduplication by content similarity

### 3. Article Quality Ranking System

**Current**: First N articles by timestamp (naive)

**Designed**: Quality scoring (0-100 points)
- Sentiment strength: 0-25 points (±0.7+ > ±0.2)
- Event materiality: 0-30 points (earnings > opinions)
- Source quality: 0-20 points (Bloomberg > blogs)
- Recency: 0-15 points (decay over time)
- Story coverage: 0-10 points (multiple sources boost)
- LLM processing: 0-5 points bonus

**Impact**: Shows BEST articles, not just newest

### 4. LLM Architecture Designed

**Flexible, pluggable, config-driven:**

```python
# Abstract interface
class LLMTranslator(ABC):
    def translate(headline, summary) -> dict

# Implementations
- NoOpTranslator (disabled)
- ClaudeTranslator (API, ~$0.90/month)
- LocalLLMTranslator (Qwen/Llama, $0 free)

# Config-driven selection
LLM_TRANSLATION_ENABLED=false  # Master switch
LLM_TRANSLATOR_TYPE=none       # none/claude/local
```

**Database tracking**:
- `llm_processed` BOOLEAN
- `llm_processed_at` TIMESTAMP
- `llm_model_name` VARCHAR(50)
- `quality_score` FLOAT

**Graceful degradation**: No LLM = show original headlines

---

## Code State

**Git**: ✅ Clean - Last commit 9f120b2 (planning docs)
**Uncommitted**: None
**Branch**: `claude/watchlist-vision-implementation-011CUw9W27dCwbxtwbECZsKT`
**Tests**: Not run (no code changes)

**Files Created This Session:**
1. `tasks/CRITICAL-ISSUES-FOUND.md` - Complete fix plan (Session 1 + 2)
2. `tasks/NEWS-SECTIONS-INVESTIGATION.md` - Why two sections + root cause
3. `tasks/PLAIN-LANGUAGE-NEWS-ASSESSMENT.md` - Pattern bugs + LLM analysis
4. `tasks/WATCHLIST-COMPREHENSIVE-REVIEW.md` - Detailed comparison vs design

**Files Modified:**
- None (investigation only)

---

## Environment

**Services**: Backend/Frontend/Celery/Beat all running
**Venv**: `~/portfolio-ai/backend/.venv` (activated)
**Database**: portfolio_ai (PostgreSQL)
**Tests**: 508 backend tests available (not run this session)

---

## Key Decisions

### Architecture

1. **News Sections**: Combine into one unified section
   - Rationale: Duplicate data, same articles, user prefers detailed stats
   - Pattern: Collapsed by default, expandable for details

2. **LLM Integration**: Abstract interface with multiple backends
   - Rationale: Flexible, can use Claude OR local models OR none
   - Pattern: Config-driven selection, graceful degradation

3. **Article Ranking**: Multi-factor quality scoring
   - Rationale: Best articles from larger pool, not just newest
   - Pattern: Weighted scoring, user-tunable weights

4. **Settings Location**: Keep centralized `/settings` page
   - Rationale: User preference, actually better than scattered settings
   - Pattern: Don't add watchlist-specific settings button

### Patterns Established

1. **Investigation before fixing**: Understand root cause first
   - Used browser automation for visual verification
   - Used database queries for actual data analysis
   - Compared against design references (HTML + PNG)

2. **Honest assessment**: Don't sugar-coat issues
   - Initial "APPROVED" changed to "REWORK REQUIRED"
   - User caught 5 critical bugs we missed initially
   - Systematic comparison revealed 45% expanded row mismatch

3. **Facts over assumptions**: Query database, don't guess
   - Verified 57% placeholder rate with actual counts
   - Sampled failed headlines to understand patterns
   - Calculated LLM costs accurately (~$0.90/month, not wild guesses)

### Issues Discovered & Handled

1. **Price column empty**: Need to investigate WatchlistTable.tsx
2. **Score breakdown hardcoded**: Need to use per-stock data
3. **57% placeholder headlines**: Pattern matching has 6 missing categories
4. **Duplicate news sections**: Architectural decision needed
5. **Article selection naive**: Just picks first N by time

### Band-Aids Avoided

1. ❌ Quick fix to patterns without LLM option
   - Why avoided: Would be whack-a-mole maintenance
   - Better approach: LLM with graceful degradation

2. ❌ Keep both news sections with minor tweaks
   - Why avoided: Data duplication, user confusion
   - Better approach: Unified section with best of both

3. ❌ Add settings button to watchlist page
   - Why avoided: User prefers centralized settings
   - Better approach: Keep `/settings` page

---

## To Resume

### Quick Start
```bash
cd ~/portfolio-ai/backend
source .venv/bin/activate
# Read tasks/CRITICAL-ISSUES-FOUND.md
# Then: /do_it (will auto-discover next work)
```

### Session 1: Bug Fixes (3-4 hours)
**File**: `tasks/CRITICAL-ISSUES-FOUND.md` - Session 1 section

**Tasks**:
1. Fix price column rendering (WatchlistTable.tsx)
2. Fix score breakdown per-stock (ExpandedRow.tsx)
3. Remove legacy settings section (WatchlistPreferences.tsx)
4. Fix news page loading (app/news/page.tsx)
5. Test all fixes

**Expected Outcome**: 5 critical bugs fixed, tests passing

### Session 2: News Intelligence (5-8 hours)
**File**: `tasks/CRITICAL-ISSUES-FOUND.md` - Session 2 section

**Tasks**:
1. Database migrations (LLM tracking columns, quality_score, ranking weights)
2. Create LLM translator interface (abstract + 3 implementations)
3. Implement article quality ranking (scoring algorithm + selection)
4. Build unified news section (collapsed/expanded, deduplication)
5. Write tests for new components

**Expected Outcome**: One unified news section, LLM-ready, smart ranking, works without LLM

---

## Next Action

**Immediate**: User will `/clear` then `/do_it` to start Session 1

**First Task**: Fix price column data display in WatchlistTable.tsx
- Investigate why price column not showing data
- Check if column exists but data missing
- Check if rendering logic has bug
- Fix and verify with multiple stocks

**Success Criteria**:
- Price column shows actual prices (e.g., "$172.50")
- Daily change % shows (e.g., "+1.25%")
- Works for all stocks in watchlist
- No console errors

---

## Files Modified

**Created (4 docs)**:
1. `tasks/CRITICAL-ISSUES-FOUND.md` - Complete 2-session plan
2. `tasks/NEWS-SECTIONS-INVESTIGATION.md` - Investigation findings
3. `tasks/PLAIN-LANGUAGE-NEWS-ASSESSMENT.md` - Pattern bugs + LLM options
4. `tasks/WATCHLIST-COMPREHENSIVE-REVIEW.md` - Detailed comparison

**Modified**:
- None (investigation only, no code changes)

**Deleted**:
- None

---

## Investigation Details

### Browser Automation Used

**Screenshots Captured**:
- `/tmp/current-watchlist-main.png` - Main table view
- `/tmp/current-watchlist-expanded.png` - Expanded row (NVDA)
- `/tmp/current-settings-page.png` - Settings page

**Skills Used**:
- `browser-automation` skill (Playwright-based, 0 context cost)
- `screenshot.js` - Full page captures
- `expand-and-screenshot.js` - Interact + capture
- `execute.js` - Extract data via JavaScript

### Database Queries Run

**News Analysis**:
```sql
-- Plain language headline coverage
SELECT
  COUNT(*) FILTER (WHERE plain_language_headline NOT LIKE 'News reported%') as real,
  COUNT(*) FILTER (WHERE plain_language_headline = 'News reported - check details') as placeholder,
  COUNT(*) as total
FROM news_cache;
-- Result: 667 real, 2,727 placeholder, 4,752 total (57% placeholder rate)

-- Partnership pattern matching test
SELECT headline, summary
FROM news_cache
WHERE headline ILIKE '%partnership%' OR summary ILIKE '%partnership%'
LIMIT 5;
-- Found: Many partnership articles getting placeholder
```

### Code Analysis Performed

**Pattern Matching Bug Found**:
- `plain_language_news.py` line 106-221: `classify_event_category()`
- Has 26 event categories defined
- Only 20 have pattern matching code
- Missing: PARTNERSHIP, PRODUCT_LAUNCH, REGULATORY_WIN/LOSS, MARKET_SHARE_GAIN/LOSS
- Result: 6 common event types fall to UNKNOWN → placeholder

**Frontend Component Review**:
- `ExpandedRow.tsx`: Has TWO news sections (line 940 + 968)
- `NewsIntelligenceCard.tsx`: Shows plain_language_headline OR headline fallback
- `WatchlistTable.tsx`: Price column rendering needs investigation

---

## Quick Stats

**Session Duration**: ~3 hours (investigation + planning)
**Tasks Investigated**: 5 critical bugs + news sections + LLM architecture
**Files Read**: 10+ (frontend components, backend services, database schema)
**Database Queries**: 8 analytical queries
**Screenshots**: 3 full-page captures
**Commits**: 1 (documentation only)
**Code Changes**: 0 (investigation session)
**Planning Docs**: 4 comprehensive documents created

---

## User Feedback Incorporated

1. ✅ "Settings on /settings is fine" - Removed settings button requirement
2. ✅ "Show top positive + top negative, collapsed by default" - Designed
3. ✅ "Keep model coverage, confidence, headline mix stats" - Preserved
4. ✅ "Can we make plain language work?" - Investigated, designed hybrid solution
5. ✅ "Don't want whack-a-mole maintenance" - Designed LLM-based solution
6. ✅ "Pick best articles from larger pool" - Designed quality ranking system

---

## Recommendations for Next Session

**Do This**:
1. Fix the 5 critical bugs first (Session 1, 3-4 hours)
2. Test thoroughly after each fix
3. Then start news intelligence overhaul (Session 2, 5-8 hours)
4. Keep LLM disabled initially (enable later when ready)

**Don't Do This**:
1. ❌ Skip bug fixes and go straight to news overhaul
2. ❌ Try to do both sessions in one go (too complex)
3. ❌ Enable LLM without testing disabled mode first
4. ❌ Add new features while bugs exist

**Success Path**:
- Session 1 → verify bugs fixed → user acceptance
- Session 2 → unified news section → verify works without LLM
- Later → enable Claude or Qwen → verify AI enhancements

---

**Resume Command**: `/do_it` (auto-discovers next work)

**Context Available**: 45% remaining (89K/200K tokens)

**Ready to execute!** 🚀
