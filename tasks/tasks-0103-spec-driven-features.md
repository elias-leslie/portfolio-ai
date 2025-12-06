# Task List: Spec-Driven Feature System + Modernize Commands

**Source**: User request + plan from dynamic-wandering-pretzel.md
**Complexity**: Complex
**Effort**: HIGH
**Environment**: Local Dev
**Created**: 2025-12-06

---

## Summary

**Goal**: Implement spec-driven development by adding acceptance criteria to features, modernizing commands to require/verify specs, and removing legacy task file support.

**Approach**:
1. Add schema columns for acceptance_criteria, vision_goals, priority
2. Update API with new endpoints and priority calculation
3. Rewrite all 4 commands (task_it, verify_it, audit_it, do_it)
4. Extract specs from task files 0096-0102 for initial backfill
5. Update UI to show priority and criteria

**Why**: Current `/verify_it` checks "does it run" not "does it meet requirements." Features need explicit, testable acceptance criteria for factual verification.

---

## Tasks

### 0.0 Scope Discovery (MANDATORY) - COMPLETE

- [x] 0.1 Verify current feature_capabilities schema
  - ✅ Existing columns confirmed, no conflicts
- [x] 0.2 Count existing features that need backfill
  - ✅ 163 features total
- [x] 0.3 Confirm task files 0096-0102 are accessible
  - ✅ 11 task files available in archive
- [x] 0.4 Checkpoint: Confirm scope before proceeding
  - Existing features: 163
  - Task files available: 11

**SCOPE CONFIRMED**

---

### 1.0 Database Schema Changes - COMPLETE

- [x] 1.1 Create migration file
  - ✅ Created: `backend/migrations/082_feature_acceptance_criteria.sql`
  - Added: priority INTEGER DEFAULT NULL
  - Added: acceptance_criteria JSONB DEFAULT '[]'
  - Added: vision_goals TEXT[] DEFAULT '{}'
  - Added comments explaining each column
- [x] 1.2 Apply migration
  - ✅ Migration applied via Python script
- [x] 1.3 Verify columns exist
  - ✅ Columns confirmed: priority (integer), acceptance_criteria (jsonb), vision_goals (ARRAY)
- [x] 1.4 Test: Services restart successfully
  - ✅ Services restarted

---

### 2.0 API Updates - COMPLETE

- [x] 2.1 Update response models
  - ✅ File: `backend/app/api/capabilities/features_router.py`
  - ✅ Added AcceptanceCriterion model
  - ✅ Added priority, acceptance_criteria, vision_goals, effective_priority to FeatureResponse
- [x] 2.2 Add priority calculation function
  - ✅ File: `backend/app/services/capability_feature_scanner.py`
  - ✅ Function: _calculate_effective_priority()
  - ✅ Logic: broken=P1, 80%+ verified=P2, 50%+=P3, started=P4, not started=P5
- [x] 2.3 Add PATCH /features/{id}/priority endpoint
  - ✅ Working, tested with FEAT-110
- [x] 2.4 Add PATCH /features/{id}/acceptance-criteria endpoint
  - ✅ Working, tested with FEAT-110
- [x] 2.5 Add PATCH /features/{id}/acceptance-criteria/{ac_id} endpoint
  - ✅ Working
- [x] 2.6 Add PATCH /features/{id}/vision-goals endpoint
  - ✅ Working
- [ ] 2.7 Add sort_by parameter to GET /features/
  - ⏳ Deferred to later (not blocking)
- [x] 2.8 Test: All endpoints work
  - ✅ All tested via curl

---

### 3.0 Command Updates

#### 3.1 Update /task_it

- [ ] 3.1.1 Read current task_it.md
- [ ] 3.1.2 Rewrite to require acceptance criteria
  - MUST include at least 2 criteria
  - MUST include at least 1 vision goal
  - Ask for clarification if ambiguous
- [ ] 3.1.3 Remove any legacy task file references
- [ ] 3.1.4 Add example of criteria definition flow

#### 3.2 Update /verify_it

- [ ] 3.2.1 Read current verify_it.md
- [ ] 3.2.2 Add acceptance criteria verification step
  - For each criterion, run verification command
  - Mark passed/failed with evidence
  - Feature only passes if ALL criteria pass
- [ ] 3.2.3 Update pre-flight check to include criteria

#### 3.3 Update /audit_it

- [ ] 3.3.1 Read current audit_it.md
- [ ] 3.3.2 Add gap detection for missing criteria
  - Flag features with empty acceptance_criteria
  - Flag features without vision_goals
- [ ] 3.3.3 Add --backfill mode
  - Load reference JSON
  - Apply criteria to matching features
  - Report results

#### 3.4 Update /do_it

- [ ] 3.4.1 Read current do_it.md
- [ ] 3.4.2 Remove ALL legacy task file references
  - No markdown file reading
  - No WORK_TRACKER references
- [ ] 3.4.3 Add --target FEAT-XXX support
- [ ] 3.4.4 Add work plan display with approval
  - Show features by priority
  - Show criteria pass/fail counts
  - Wait for user approval
- [ ] 3.4.5 Add priority-based ordering

---

### 4.0 Extract Specs from Task Files

- [ ] 4.1 Read and analyze task file 0096
  - Extract verification sections
  - Map to feature categories
- [ ] 4.2 Read and analyze task file 0097
- [ ] 4.3 Read and analyze task file 0098
- [ ] 4.4 Read and analyze task file 0099
- [ ] 4.5 Read and analyze task file 0100
- [ ] 4.6 Read and analyze task file 0101
- [ ] 4.7 Read and analyze task file 0102
- [ ] 4.8 Create reference JSON
  - File: `/tmp/feature-specs-reference.json`
  - Format: feature_id → acceptance_criteria mapping
- [ ] 4.9 Checkpoint: Review extraction before backfill

---

### 5.0 Backfill Existing Features

- [ ] 5.1 Run /audit_it --backfill
  - Load reference JSON
  - Match features to extracted criteria
  - Apply criteria via API
- [ ] 5.2 Report results
  - Features backfilled: X
  - Features needing manual criteria: Y
- [ ] 5.3 Review features without criteria
  - List for manual follow-up
- [ ] 5.4 Discard reference JSON
  - All criteria now in DB

---

### 6.0 UI Updates

- [ ] 6.1 Add Priority column to FeaturesTab
  - File: `frontend/components/capabilities/FeaturesTab.tsx`
  - P1-P5 badges with color coding
  - P1=red, P2=orange, P3=yellow, P4=blue, P5=gray
- [ ] 6.2 Add Criteria column
  - Show X/Y passed format
- [ ] 6.3 Update expanded row
  - Show individual criteria with pass/fail status
  - Show verification command
  - Show evidence if available
- [ ] 6.4 Add priority edit capability
  - Dropdown to set user override
- [ ] 6.5 Test: Screenshot verification

---

### 7.0 Verification & Cleanup

- [ ] 7.1 Run /audit_it to verify all features have criteria
- [ ] 7.2 Run lint checks
  - `~/portfolio-ai/scripts/lint.sh`
- [ ] 7.3 Run backend tests
  - `pytest tests/ -v`
- [ ] 7.4 Restart services
  - `bash ~/portfolio-ai/scripts/restart.sh`
- [ ] 7.5 Manual UI verification
  - Screenshot Features tab
  - Verify priority and criteria display
- [ ] 7.6 Commit changes
  - Descriptive commit message

---

## Verification (FACTS)

- [ ] Schema: `\d feature_capabilities` shows 3 new columns
- [ ] API: All new endpoints return 200
- [ ] Commands: All 4 commands updated and tested
- [ ] Backfill: X features have acceptance_criteria
- [ ] UI: Priority and criteria visible in Features tab
- [ ] Quality: `~/portfolio-ai/scripts/lint.sh` passes
- [ ] Services: Restarted and verified

---

## Files to Modify

**Database:**
- `backend/migrations/085_feature_acceptance_criteria.sql` (NEW)

**Backend API:**
- `backend/app/api/capabilities/features_router.py`
- `backend/app/api/capabilities/schemas.py`
- `backend/app/services/capability_feature_scanner.py`

**Frontend:**
- `frontend/components/capabilities/FeaturesTab.tsx`

**Commands:**
- `.claude/commands/task_it.md`
- `.claude/commands/verify_it.md`
- `.claude/commands/audit_it.md`
- `.claude/commands/do_it.md`

**Temporary:**
- `/tmp/feature-specs-reference.json` (discarded after backfill)

---

## Dependencies

- This task HAS NO BLOCKERS
- This task BLOCKS: All future feature work (will use new spec-driven approach)

---

## Resume Points

Each numbered task section (1.0, 2.0, etc.) is a natural pause point.

**Recommended session splits:**
- Session 1: Tasks 0.0-2.0 (Schema + API)
- Session 2: Task 3.0 (Commands)
- Session 3: Tasks 4.0-5.0 (Extraction + Backfill)
- Session 4: Tasks 6.0-7.0 (UI + Verification)

---

## Notes

- Priority based on layer verification progress, NOT subtask completion
- Acceptance criteria are testable (curl, SQL, screenshot)
- Vision goals link features to VISION.md strategic goals
- JSON extraction is one-time for backfill only
- Future features: Claude writes criteria directly to DB

---

**Version**: 1.0.0 | **Created**: 2025-12-06
