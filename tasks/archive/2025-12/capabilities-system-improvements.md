# Capabilities System Improvements

**Created**: 2025-12-08
**Context**: Follow-up from capabilities review session
**Plan File**: `.claude/plans/functional-percolating-lagoon.md`

---

## Background

The capabilities system was reviewed and refined:
- Renamed tabs for clarity (Gaps→Trading Reqs, Sources→Data Sources, etc.)
- Created `/gap_it` command for iterative gap resolution
- Identified that Insights should be repurposed to Tech Debt
- Found command inconsistencies that need fixing

This task file captures remaining work and includes improvements to make Features replace task md files.

---

## Task 1: Enhance Features to Replace Task Files [PRIORITY: HIGH]

### Problem
Features system lacks fields for detailed implementation context:
- No place for step-by-step instructions
- No structured file paths field
- No code examples storage
- No dependencies/blockers tracking

### Solution
Add `implementation_notes` JSONB field to `feature_capabilities` table.

### Implementation Steps

1. **Create migration** `backend/migrations/XXX_feature_implementation_notes.sql`:
```sql
ALTER TABLE feature_capabilities
ADD COLUMN implementation_notes JSONB DEFAULT '{}';

COMMENT ON COLUMN feature_capabilities.implementation_notes IS
'Structured implementation details: steps, files, examples, blockers';
```

2. **Update API** `backend/app/api/capabilities/features_router.py`:
   - Add `implementation_notes` to FeatureCreate/FeatureUpdate models
   - Include in GET/POST/PATCH endpoints

3. **Update Frontend** `frontend/components/capabilities/FeaturesTab.tsx`:
   - Add expandable "Implementation Notes" section in feature detail view
   - Support markdown rendering for notes
   - Add edit capability for notes

4. **Update `/task_it` command** to populate implementation_notes when creating features

### Acceptance Criteria
- [ ] Migration applied, field exists in DB
- [ ] API accepts/returns implementation_notes
- [ ] UI displays implementation notes in feature detail
- [ ] `/task_it` populates notes when creating features

### Files to Modify
- `backend/migrations/XXX_feature_implementation_notes.sql` (new)
- `backend/app/api/capabilities/features_router.py`
- `frontend/components/capabilities/FeaturesTab.tsx`
- `.claude/commands/task_it.md`

---

## Task 2: Repurpose Insights → Tech Debt [PRIORITY: MEDIUM]

### Problem
Insights system is redundant with Features for tracking issues. Should be repurposed for code quality/tech debt tracking.

### Solution
Rename and recategorize to focus on automated code hygiene discovery.

### Implementation Steps

1. **Update insight types** in `capability_insights` table:
   - Add new types: `dead_code`, `orphaned_infra`, `complexity`, `dry_violation`, `performance`, `test_coverage`, `dependency`
   - Keep existing severity levels

2. **Update Dashboard** `frontend/components/capabilities/CapabilitiesDashboard.tsx`:
   - Already renamed to "Critical Tech Debt" ✓
   - Add category breakdown (by type)

3. **Update scanning logic** (if exists) to categorize findings as tech debt types

4. **Add "Create Feature" action** from tech debt items:
   - Button on tech debt item → creates feature with context
   - Links tech debt item to created feature

### Acceptance Criteria
- [ ] Tech debt types available in API
- [ ] Dashboard shows tech debt by category
- [ ] Can create feature from tech debt item
- [ ] Tech debt items link to features when resolved

### Files to Modify
- `backend/app/api/capabilities/insights_router.py`
- `frontend/components/capabilities/CapabilitiesDashboard.tsx`
- `frontend/components/capabilities/InsightCard.tsx` (add Create Feature button)

---

## Task 3: Fix Command Inconsistencies [PRIORITY: MEDIUM]

### Problem
Found during exploration:
1. `/do_it` uses direct screenshot scripts while `/verify_it` forbids this
2. Artifact path structure not standardized
3. Context thresholds inconsistent across commands

### Implementation Steps

1. **Standardize evidence capture** in `/do_it.md`:
   - Change from direct scripts to API endpoint
   - Match `/verify_it` approach:
   ```bash
   # Use API endpoint (registers in DB)
   curl -X POST "http://localhost:8000/api/artifacts/refresh" \
     -H "Content-Type: application/json" \
     -d '{"feature_id": "...", "criterion_id": "...", "url": "..."}'
   ```

2. **Document artifact path structure** in `CLAUDE.md`:
   ```
   data/artifacts/{feature_id}/{criterion_id}/v{n}/
   ├── screenshot.png
   ├── console.json
   ├── network.json
   └── page_state.json
   ```

3. **Standardize context thresholds** across all commands:
   - < 75%: Continue freely
   - 75-85%: Monitor, check after each task
   - ≥ 85%: Notify user, recommend pause
   - > 90%: Critical, run `/pause_it`

### Acceptance Criteria
- [ ] `/do_it` uses API for evidence capture
- [ ] Artifact path structure documented in CLAUDE.md
- [ ] All commands use same context thresholds

### Files to Modify
- `.claude/commands/do_it.md`
- `.claude/commands/verify_it.md` (verify consistency)
- `CLAUDE.md` (add artifact documentation)

---

## Task 4: Simplify Trading Requirements Display [PRIORITY: LOW]

### Problem
The "Find Providers" button approach requires clicking for each gap. Provider coverage should be visible inline.

### Solution
Show provider count inline in gap rows (after `/gap_it` audit completes).

### Implementation Steps

1. **After gap audit** (via `/gap_it`), most gaps will have provider linkage
2. **Update GapsOverview** to show provider count inline:
   - Fetch all gap providers in batch on tab load
   - Display badge: "2 providers" or "⚠️ No coverage"
3. Keep "Find Providers" button as secondary detail view

### Acceptance Criteria
- [ ] Gap rows show provider count inline
- [ ] Uncovered gaps show warning badge
- [ ] No extra API calls per gap (batch fetch)

### Files to Modify
- `frontend/components/capabilities/GapsOverview.tsx`
- `frontend/components/capabilities/GapsList.tsx`

---

## Execution Order

1. **Task 1** (Features enhancement) - Enables better task tracking going forward
2. **Task 3** (Command fixes) - Quick wins, improves reliability
3. **Task 2** (Tech Debt) - Medium effort, improves system organization
4. **Task 4** (Display improvement) - Low priority, do after `/gap_it` audit

---

## Notes

- Task 1 should be done first so subsequent tasks can be tracked in Features
- After Task 1, create features for Tasks 2-4 using `/task_it`
- This task file becomes obsolete once Features has implementation_notes field
