# Vision/Capabilities Integration - Follow-up Tasks

**Created**: 2025-12-08
**Status**: Ready for next session

---

## HIGH PRIORITY - Next Session

### 1. Auto Gap-Feature Linking (User Request)

**Context**: User should NOT manually link gaps to features. Commands should do it automatically.

**Implementation**:

#### 1.1 Update /audit_it for Backfill
- Add `--enrich` mode that auto-links existing features to gaps
- Use keyword pattern matching (25+ patterns identified)
- Call `POST /api/capabilities/features/{id}/gaps` automatically
- Set `linked_by: "audit_it"`

**Keyword patterns ready** (from exploration):
```
earnings, EPS → GAP-003
insider, form 4 → GAP-006
institutional, 13F → GAP-007
analyst, recommendation → GAP-005
short interest → GAP-004
options, call, put → GAP-031
sentiment, fear, greed → GAP-010
intraday, minute → GAP-001
covariance, correlation → GAP-020
backtest → GAP-019
```

#### 1.2 Update /task_it for New Features
- Auto-suggest gap links when creating features
- Based on feature name/description keywords
- Link automatically with `linked_by: "task_it"`

**Gap count**: 49 gaps (GAP-001 to GAP-049)
**Feature count**: 165 features (0 currently linked)

---

### 2. Tech Debt UI Simplification (User Request)

**Current issues**:
- Too many buttons: Confirm, In Progress, Dismiss, Add Note, Create Feature
- Confidence score broken (field name mismatch: `ai_confidence` vs `confidence`)

**User wants**:
- Keep: **Dismiss** button with optional notes
- Remove: Confirm, In Progress buttons
- Fix or remove: Confidence score display

**Files to modify**:
- `frontend/components/capabilities/InsightCard.tsx` - Remove buttons
- `backend/app/api/capabilities/database.py` - Fix field name mapping

---

### 3. Tech Debt → /audit_it Integration (User Request)

**User wants /audit_it to**:
- Review tech debt items during audit
- Add newly discovered tech debt
- Ask before removing resolved/obsolete items
- Mark resolved items as "fixed" (not dismissed) with notes

**Current state**: Tech debt completely separate from /audit_it workflow

---

### 4. Tech Debt → Features Conversion

**Need command to**: Convert tech debt items into features/tasks for /do_it

**Suggested approach**:
- `/audit_it --tech-debt` or new `/tech_debt_it` command
- Creates feature from insight with:
  - Name from `finding`
  - Description from `expected_behavior` + `suggested_fix`
  - Category: "Tech Debt"
  - Links to original insight

---

### 5. Terminology: "Features" → "Work Items"

**User agrees** "Features" is too narrow for bug fixes, tech debt, refactors, etc.

**Recommendation**: Rename to **Work Items**

**Scope**:
- Database: Keep `feature_capabilities` (avoid migration complexity)
- API: Keep `/api/capabilities/features` (backwards compat)
- UI: Change "Features" tab label to "Work Items"
- Commands: Update terminology in task_it, do_it, verify_it, audit_it
- CLAUDE.md: Update documentation

---

## MEDIUM PRIORITY

### 6. Slash Command Consistency
- [ ] Standardize "orphaned features" terminology across all commands
- [ ] Add vision goal prioritization algorithm to task_it.md
- [ ] Ensure all commands use same API response field names

### 7. VG-PERF Cleanup
- Auto-created during migration with placeholder text
- Decision needed: Keep as real goal or remove

### 8. Test Coverage
- [ ] Add tests for vision_content_router endpoints
- [ ] Add tests for vision_goals_router /details endpoint
- [ ] Add tests for feature-gap linking endpoints

---

## LOW PRIORITY / DEFERRED

### 9. Vision Goal Progress Updates
- When features verified/completed, progress could auto-refresh
- Current: calculated on-demand (works fine)
- Enhancement: explicit refresh after verification

### 10. Drop Legacy vision_goals Array Column
- feature_capabilities still has vision_goals TEXT[] alongside junction table
- Junction table (feature_vision_goal_mappings) is source of truth
- Future migration 094+ can drop after confirming all API/UI use junction table

---

## Exploration Findings (Reference)

### Gap Database Stats
- 49 total gaps (GAP-001 to GAP-049)
- P0 Critical: 17 | P1 High: 20 | P2 Medium: 7 | P3 Low: 3

### Tech Debt Schema
- Table: `capability_insights`
- Status values: pending, confirmed, dismissed, in_progress, fixed
- Confidence stored as `ai_confidence` (DECIMAL 3,2)
- Frontend expects `confidence` (NAME MISMATCH - broken)

### Feature-Gap Infrastructure (Ready to Use)
- Table: `feature_gap_mappings` with FK constraints
- Views: `feature_gap_summary`, `gap_resolution_summary`
- API: GET/POST/DELETE endpoints all working
- Just needs command integration

---

**Next Session**: Start with items 1-4 (gap linking, tech debt simplification, audit integration, tech debt→features)
