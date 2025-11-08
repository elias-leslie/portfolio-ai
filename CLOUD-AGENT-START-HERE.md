# 🚀 Cloud Agent - Start Here

**Mission**: Implement Watchlist Intelligence Hub matching design references exactly

**Branch**: Create new branch `cloud/watchlist-vision-implementation`

**Estimated**: ~16 hours across 5 phases

---

## 📚 Step 1: Read These Files (30 min)

**IN THIS ORDER**:

1. **`docs/watchlist_design_guide.md`** - Complete design vision with ASCII mockups
2. **`docs/design_references/watchlist_design_reference/*.png`** - 4 visual reference screenshots
3. **`tasks/WATCHLIST-GAP-ANALYSIS.md`** - What's currently broken
4. **`tasks/TASK-LIST-REVIEW.md`** - 6 critical missing features
5. **`tasks/tasks-watchlist-complete-vision.md`** - Your task list (working document)
6. **`tasks/CLOUD-AGENT-HANDOFF-INSTRUCTIONS.md`** - Detailed implementation guide

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
   git add frontend/
   git commit -m "feat(watchlist): <description>

   <details>

   Implements Phase X, Task Y.Z

   🤖 Generated with Claude Code"
   ```
6. **Update task list** - mark task as complete with `[x]`

### After Each Phase:

1. **Create handoff document**: `tasks/HANDOFF-watchlist-phaseN-YYYYMMDD-HHMM.md`
2. **Use template** from `tasks/CLOUD-AGENT-HANDOFF-INSTRUCTIONS.md`
3. **List what local agent needs to verify** (screenshots, tests, database)
4. **Commit handoff doc**
5. **STOP** - wait for local agent verification

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

## 📞 Handoff to Local Agent

**After Phase 1** (main table UX), create:

`tasks/HANDOFF-watchlist-phase1-YYYYMMDD-HHMM.md`

**Template**:
```markdown
# Watchlist Phase 1 Handoff

**Cloud Agent Completed**:
- ✅ Task 1.1: Research and documentation
- ✅ Task 1.2: Removed technical columns
- ✅ Task 1.3: Added Trading Style column
- ✅ Task 1.4: Added Risk Level column
- ✅ Task 1.5: Added search bar
- ✅ Task 1.6-1.7: Priority indicators (backend + frontend)
- ✅ Task 1.8: Static analysis passed
- ✅ npm run build: PASSED

**Commits**: [list commit hashes]

**Local Agent Tasks**:
1. Pull branch: `git checkout cloud/watchlist-vision-implementation && git pull`
2. Restart services: `bash ~/portfolio-ai/scripts/restart.sh`
3. Take screenshot:
   ```bash
   node ~/portfolio-ai/.claude/skills/browser-automation/scripts/screenshot.js \
     http://192.168.8.233:3000/watchlist \
     /tmp/watchlist-phase1-current.png
   ```
4. Compare with: `docs/design_references/watchlist_design_reference/watchlist_main_table_view/screen.png`
5. Verify: Table has 9 columns, search works, priority indicators show
6. If issues: Document and hand back
7. If good: Approve Phase 1, cloud continues to Phase 2

**Next**: Phase 2 (Filters)
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
