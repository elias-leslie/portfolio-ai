# 🚀 Cloud Agent - Start Here

**Mission**: Implement Watchlist Intelligence Hub matching design references exactly

**Branch**: Create new branch `cloud/watchlist-vision-implementation`

**Estimated**: ~16 hours across 5 phases

---

## 📚 Step 1: Read These Files (30 min)

**IN THIS ORDER**:

1. **`docs/watchlist_design_guide.md`** - Complete design vision with ASCII mockups
2. **`docs/DESIGN-REFERENCE-SUMMARY.md`** - TEXT description of visual references (READ THIS - you can't view PNGs)
3. **`docs/design_references/watchlist_design_reference/*.html`** - HTML structure examples (optional)
4. **`tasks/WATCHLIST-GAP-ANALYSIS.md`** - What's currently broken
5. **`tasks/TASK-LIST-REVIEW.md`** - 6 critical missing features
6. **`tasks/tasks-watchlist-complete-vision.md`** - Your task list (working document)
7. **`tasks/CLOUD-AGENT-HANDOFF-INSTRUCTIONS.md`** - Detailed implementation guide

**⚠️ IMPORTANT**: You CANNOT view PNG files. Use `docs/DESIGN-REFERENCE-SUMMARY.md` instead - it describes all 4 design reference screenshots in text.

**Don't skip this reading** - prevents wasted work.

---

## 🎯 Your Task List

**File**: `tasks/tasks-watchlist-complete-vision.md`

**Total**: 23 tasks across 5 phases

### Phase 1: Main Table UX (9 tasks, ~6h)
- Hide technical columns (SMA, RSI, MACD, Volume)
- Add Trading Style column ("Swing (3-7d)" format)
- Add Risk Level column (Low/Mid/High with ⚠️ icons)
- Add search bar
- Add priority indicators (🔥📰⚡📋 badges)

### Phase 2: Filters (4 tasks, ~2h)
- Signal filter dropdown (All/BUY/HOLD/AVOID)
- Trading Style filter dropdown
- Risk filter dropdown

### Phase 3: Settings (3 tasks, ~3h)
- Weight sliders for 3 pillars (price/technical/fundamental)
- Sub-weight sliders for technical (RSI/Trend/MACD)
- Sub-weight sliders for fundamental (4 pillars)

### Phase 4: Enhanced Details (5 tasks, ~4h)
- Rich fundamental display (Revenue %, margins, P/E with context)
- News intelligence enhancements (article counts, coverage, events)
- Complete technical indicators (SMA, Bollinger, ATR)
- Watchlist ranking ("Top 3" badge)
- Market cap display

### Phase 5: Documentation (2 tasks, ~1h)
- Screenshot comparison matrix
- Update docs

---

## 🔴 Critical: 6 Missing Features

The original Part 2 task list was **incomplete**. These are **REQUIRED** per design:

1. **Priority Indicators** - 🔥📰⚡📋💎📉📈 badges in Signal column
2. **Rich Fundamental Metrics** - Show "Revenue +24%, EPS +18%" not just scores
3. **News Intelligence** - Article counts, coverage level, key events
4. **Complete Technical Indicators** - SMA(50/200), Bollinger, ATR (not just RSI/MACD)
5. **Market Cap** - Display in Price Data section
6. **Watchlist Ranking** - "Top 3 in watchlist" badge

See `tasks/TASK-LIST-REVIEW.md` for details on each.

---

## ✅ Success Criteria

**Your implementation screenshots MUST match these design references**:

- `docs/design_references/watchlist_design_reference/watchlist_main_table_view/screen.png`
- `docs/design_references/watchlist_design_reference/expanded_row_-_full_intelligence_view/screen.png`
- `docs/design_references/watchlist_design_reference/watchlist_settings_panel/screen.png`
- `docs/design_references/watchlist_design_reference/search_and_filter_bar/screen.png`

**Main Table MUST have**:
- Exactly 9 columns (no more, no less)
- Trading Style column
- Risk Level column
- Priority indicators in Signal column
- Search bar
- Filter dropdowns

**Expanded Row MUST have**:
- Rich fundamental display with context
- Complete technical indicators
- News intelligence with counts
- Watchlist ranking badge

---

## 🛠️ Quick Start Commands

```bash
# Create new branch
git checkout main
git pull
git checkout -b cloud/watchlist-vision-implementation

# Verify branch
git branch

# Start with Phase 1, Task 1.1 (Research)
# Read current table structure
cat frontend/components/watchlist/WatchlistTable.tsx

# Document findings in code comment
# Then proceed to Task 1.2
```

---

## 📝 Your Working Process

### For Each Task:

1. **Read task description** in `tasks/tasks-watchlist-complete-vision.md`
2. **Read relevant files** mentioned in task
3. **Implement changes** following examples in `tasks/CLOUD-AGENT-HANDOFF-INSTRUCTIONS.md`
4. **Static check**:
   ```bash
   cd ~/portfolio-ai/frontend
   npm run build  # Must pass with 0 errors
   ```
5. **Commit** with clear message:
   ```bash
   git add frontend/ backend/
   git commit -m "feat(watchlist): <description>

   <details>

   Implements Phase X, Task Y.Z

   🤖 Generated with Claude Code"
   ```
6. **Update task list** - mark task as complete with `[x]`
7. **Keep going** - work through all implementation phases

### Work Through ALL Implementation Phases (1-4):

**DO NOT STOP** between phases - keep working autonomously through:
- Phase 1: Main Table UX (9 tasks)
- Phase 2: Filters (4 tasks)
- Phase 3: Settings (3 tasks)
- Phase 4: Enhanced Details (5 tasks)

**Only hand off after Phase 4 is complete** - local agent needs to verify everything at once.

### After Phase 4 Complete:

1. **Create ONE comprehensive handoff document**: `tasks/HANDOFF-watchlist-implementation-YYYYMMDD-HHMM.md`
2. **List ALL changes across all 4 phases**
3. **List what local agent needs to verify** (screenshots, tests, database)
4. **Commit handoff doc**
5. **STOP** - wait for local agent verification
6. **Phase 5 (documentation)** - only after local approves implementation

---

## 🚫 What NOT to Do

1. ❌ **Don't skip** reading design references
2. ❌ **Don't assume** current implementation is correct
3. ❌ **Don't add** features not in design
4. ❌ **Don't use** `any` types in TypeScript
5. ❌ **Don't commit** without running `npm run build`
6. ❌ **Don't move** to next phase without creating handoff doc
7. ❌ **Don't try** to run services/tests/database (you can't in sandbox)

---

## 📊 Phase 1 Quick Reference

**Start Here**: Task 1.1 (Research current table)

**Tasks 1.2-1.5**: Main table cleanup
- Remove: SMA, RSI, MACD, Volume columns
- Add: Trading Style, Risk Level columns
- Add: Search bar

**Tasks 1.6-1.7**: Priority indicators
- Backend: Create `priority_indicators.py` with detection logic
- Frontend: Display 🔥📰⚡ badges in Signal column

**Task 1.8**: Static analysis & commit

**Task 1.9**: Create handoff doc for local agent

**Code examples** for all tasks in `tasks/CLOUD-AGENT-HANDOFF-INSTRUCTIONS.md`

---

## 🎯 Your Starting Point

**Right Now, Do This**:

1. Read `docs/watchlist_design_guide.md` (10 min)
2. View design reference PNGs (5 min)
3. Read `tasks/WATCHLIST-GAP-ANALYSIS.md` (5 min)
4. Read `tasks/TASK-LIST-REVIEW.md` (10 min)
5. Open `tasks/tasks-watchlist-complete-vision.md` (your working file)
6. Begin Phase 1, Task 1.1: Research current table structure

**File to edit**: `frontend/components/watchlist/WatchlistTable.tsx`

**Action**: Add comment documenting current vs design columns

---

## 📞 Handoff to Local Agent (After Phase 4)

**After completing ALL implementation (Phases 1-4)**, create:

`tasks/HANDOFF-watchlist-implementation-YYYYMMDD-HHMM.md`

**Template**:
```markdown
# Watchlist Complete Implementation Handoff

**Cloud Agent Completed** (Phases 1-4):

### Phase 1: Main Table UX (9 tasks)
- ✅ Task 1.1: Research and documentation
- ✅ Task 1.2: Removed technical columns (SMA, RSI, MACD, Volume)
- ✅ Task 1.3: Added Trading Style column
- ✅ Task 1.4: Added Risk Level column
- ✅ Task 1.5: Added search bar
- ✅ Task 1.6-1.7: Priority indicators (backend + frontend)
- ✅ Task 1.8: Static analysis
- ✅ Task 1.9: Phase 1 complete

### Phase 2: Filters (4 tasks)
- ✅ Task 2.1: Signal filter dropdown
- ✅ Task 2.2: Trading Style filter dropdown
- ✅ Task 2.3: Risk filter dropdown
- ✅ Task 2.4: Filter logic integration

### Phase 3: Settings (3 tasks)
- ✅ Task 3.1: Weight sliders UI (12 sliders total)
- ✅ Task 3.2: Settings API integration
- ✅ Task 3.3: Validation and persistence

### Phase 4: Enhanced Details (5 tasks)
- ✅ Task 4.1: Rich fundamental display
- ✅ Task 4.2: News intelligence enhancements
- ✅ Task 4.3: Complete technical indicators
- ✅ Task 4.4: Watchlist ranking
- ✅ Task 4.5: Market cap display

**Static Analysis**:
- ✅ npm run build: PASSED (0 errors)
- ✅ TypeScript: All types correct
- ✅ No `any` types used

**Files Modified**:
- frontend/components/watchlist/WatchlistTable.tsx (main table)
- frontend/app/watchlist/page.tsx (search, filters)
- frontend/components/settings/WatchlistPreferences.tsx (sliders)
- frontend/components/watchlist/ExpandedRow.tsx (rich details)
- frontend/lib/api/watchlist.ts (types)
- backend/app/watchlist/priority_indicators.py (NEW - if created)
- [list any other backend files]

**Commits**: [list all commit hashes from phases 1-4]

**Local Agent Comprehensive Verification Tasks**:

1. **Pull and setup**:
   ```bash
   git checkout cloud/watchlist-vision-implementation
   git pull
   bash ~/portfolio-ai/scripts/restart.sh
   ```

2. **Main table screenshot**:
   ```bash
   node ~/portfolio-ai/.claude/skills/browser-automation/scripts/screenshot.js \
     http://192.168.8.233:3000/watchlist \
     /tmp/watchlist-main-after-implementation.png
   ```
   Compare with: `docs/design_references/watchlist_design_reference/watchlist_main_table_view/screen.png`

   Verify:
   - [ ] Exactly 9 columns
   - [ ] Trading Style column shows "Swing (3-7d)" format
   - [ ] Risk column shows icons (✓ ⚠️)
   - [ ] Priority indicators show in Signal column (🔥📰⚡)
   - [ ] Search bar filters by symbol/note
   - [ ] Filter dropdowns present

3. **Expanded row screenshots** (take 3 different stocks):
   ```bash
   node ~/portfolio-ai/.claude/skills/browser-automation/scripts/expand-and-screenshot.js \
     http://192.168.8.233:3000/watchlist NVDA /tmp/watchlist-expanded-nvda.png
   ```
   Compare with: `docs/design_references/watchlist_design_reference/expanded_row_-_full_intelligence_view/screen.png`

   Verify:
   - [ ] Score breakdown shows rich context (Revenue %, margins, etc.)
   - [ ] Technical indicators complete (SMA, Bollinger, ATR, RSI, MACD)
   - [ ] News intelligence shows counts and coverage
   - [ ] Watchlist ranking badge ("Top N") displays
   - [ ] Market cap displayed

4. **Settings panel**:
   - Open settings
   - Take screenshot
   - Compare with: `docs/design_references/watchlist_design_reference/watchlist_settings_panel/screen.png`
   - Verify:
     - [ ] 12 weight sliders present
     - [ ] Sliders functional
     - [ ] Save/load works

5. **Functional testing**:
   - [ ] Search: Type symbol, verify filter works
   - [ ] Filters: Test each dropdown, verify combinations work
   - [ ] Settings: Change weights, save, reload page, verify persisted
   - [ ] Expanded row: Expand 3-5 different stocks, verify data displays

6. **Database verification** (if backend changes):
   ```bash
   psql -U portfolio_ai_user -d portfolio_ai -c "SELECT * FROM user_preferences LIMIT 1;"
   ```
   Verify weight columns populated

7. **Tests**:
   ```bash
   cd ~/portfolio-ai/backend
   source .venv/bin/activate
   pytest tests/ -v -k "watchlist"
   ```
   All tests must pass

**If Issues Found**:
- Document specific issues with screenshots
- Hand back to cloud agent with clear fix requirements

**If All Good**:
- Approve implementation
- Cloud agent proceeds to Phase 5 (documentation)

**Next Phase**: Phase 5 (Documentation and final screenshot matrix)
```

---

## 🎯 Summary

**You are**: Cloud agent in sandbox (can write code, can't run services)

**Your mission**: Implement complete watchlist vision per design references

**Your task list**: `tasks/tasks-watchlist-complete-vision.md`

**Your guide**: `tasks/CLOUD-AGENT-HANDOFF-INSTRUCTIONS.md`

**Start with**: Phase 1, Task 1.1 (Research)

**Hand off after**: Each phase completion

**Success**: Screenshots match design references exactly

---

**Good luck! Read the design references thoroughly and ensure every change aligns with the vision.** 🚀

**Last Updated**: 2025-11-08 16:35
