# Portfolio AI - Work Tracker

**Last Updated:** 2025-11-03 16:30

---

## 🔄 Active (Currently Working)
- **[PRD-0025] Code Refactoring Phase 1 - Large File Splitting**
  - **File:** `tasks-0025-prd-code-refactoring-phase1.md`
  - **Status:** 40% complete (watchlist_service.py extracted, scoring service remaining)
  - **Started:** 2025-11-03 14:00
  - **Last Updated:** 2025-11-03 16:30
  - **Next:** Extract refresh_watchlist_scores (~600 lines) to scoring_service.py
  - **Effort:** HIGH (20-28 hours total, ~12-16 hours remaining)
  - **Type:** Full PRD

---

## 📋 Planned (Up Next - Priority Order)

*No tasks currently planned. Use /plan_it or /task_it to add tasks.*

---

## ✅ Recently Completed (Last 5)

- **[PRD-0024] Audit Quick Wins - High Impact, Low Effort Fixes** ✓ 2025-11-03
  - **File:** `tasks-0024-prd-audit-quick-wins.md`
  - **Duration:** ~2.5 hours
  - **Summary:** Added database indexes, updated PostgreSQL docs, clarified service management

---

## 📁 Archive

See `tasks/archive/2025-11.md` for older completed work.

---

## Usage Notes

**Auto-discovery:**
- Run `/do_it` without arguments to automatically continue active work or start next planned task
- Run `/do_it <file>` to override and work on specific task list

**Context Management:**
- Check context: `node ~/portfolio-ai/.claude/skills/context-manager/check.js <current_tokens>`
- Decision helper: `node ~/portfolio-ai/.claude/skills/context-manager/should-continue.js <current_tokens>`
- Target: Use 85-90% of context before pausing

**Adding Tasks:**
- Full PRD: `/plan_it <feature description>` → `/task_it <PRD file>`
- Simple task: `/task_it <simple task description>` (auto-adds to Planned)

**Archiving:**
- Automatic: When "Recently Completed" exceeds 5 items, oldest auto-archives
- Manual: Move entry to `tasks/archive/YYYY-MM.md` and files to `tasks/archive/prds/` or `tasks/archive/task-lists/`
