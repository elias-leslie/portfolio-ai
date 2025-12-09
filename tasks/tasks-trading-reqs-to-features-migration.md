# Trading Requirements → Features Migration

**Created**: 2025-12-08
**Status**: Planning
**Effort**: HIGH
**Vision Goals**: VG-INTEL, VG-RELY, VG-QUAL

---

## Overview

Consolidate the separate "Trading Requirements/Gaps" system into the existing Features system. This eliminates redundancy and creates a single source of truth for all work tracking.

### Why

- **Redundant systems**: Trading Reqs and Features both track "things to build"
- **Two places to look**: Confusing for users and agents
- **Extra maintenance**: Two APIs, two UIs, two tracking mechanisms
- **Against DRY**: Trading Reqs are just Features with different metadata

### Outcome

- Single Features system tracks everything
- Gap detection queries Features instead of separate table
- Trading Reqs tab becomes a filtered Features view
- Agents use one workflow for all work

---

## Phase 1: Schema & Data Migration

### 1.1 Create migration script

Map Trading Req fields to Feature fields:

| Trading Req Field | Feature Field |
|-------------------|---------------|
| `gap_id` | `feature_id` (e.g., GAP-003 → FEAT-GAP-003) |
| `capability` | `name` |
| `desired_state` | `description` |
| `current_state` | Convert to acceptance criteria |
| `criticality` (P0-P3) | `priority` (P1-P5) |
| `effort` | `effort` |
| `analysis_type` | `category` (e.g., "Data - Technical") |
| `data_sources` | `implementation_notes.data_sources` |
| `freshness_requirement` | acceptance criterion |
| `coverage_requirement` | acceptance criterion |
| `why` | `implementation_notes.context` |

### 1.2 Convert current_state + desired_state to acceptance criteria

Example for GAP-003 (Earnings Surprises):

**Before (Trading Req):**
```yaml
current_state: "Only next earnings date, no actual vs consensus"
desired_state: "Actual EPS, Consensus EPS, Surprise %, last 8 quarters"
```

**After (Feature acceptance_criteria):**
```json
[
  {"id": "ac-001", "criterion": "earnings_surprises table exists", "type": "db", "passed": null},
  {"id": "ac-002", "criterion": "actual_eps populated for 80%+ of watchlist", "type": "db", "passed": null},
  {"id": "ac-003", "criterion": "consensus_eps populated", "type": "db", "passed": null},
  {"id": "ac-004", "criterion": "surprise_pct calculated correctly", "type": "backend", "passed": null},
  {"id": "ac-005", "criterion": "data freshness < 1 day after earnings", "type": "backend", "passed": null},
  {"id": "ac-006", "criterion": "last 8 quarters history available", "type": "db", "passed": null}
]
```

### 1.3 Map analysis_type to vision_goals

| Analysis Type | Vision Goal | Category |
|---------------|-------------|----------|
| technical_analysis | VG-INTEL | Data - Technical |
| fundamental_analysis | VG-INTEL | Data - Fundamental |
| sentiment_analysis | VG-INTEL | Data - Sentiment |
| risk_analysis | VG-VALID, VG-RELY | Data - Risk |
| execution_quality | VG-RELY | Data - Execution |
| macro_analysis | VG-INTEL | Data - Macro |
| ml_infrastructure | VG-AUTO, VG-RELY | Data - ML |
| compliance | VG-RELY | Data - Compliance |

### 1.4 Run migration

```bash
# Migration script location
backend/migrations/XXX_migrate_trading_reqs_to_features.sql

# Steps:
# 1. Read trading_requirements.yaml (47 gaps)
# 2. For each gap, create feature via POST /api/capabilities/features/
# 3. Set source = 'trading_requirement'
# 4. Generate acceptance criteria from current/desired state
# 5. Link to appropriate vision goals
```

### 1.5 Verify migration

- [ ] All 47 gaps converted to features
- [ ] Each feature has ≥2 acceptance criteria
- [ ] Each feature linked to vision goal
- [ ] Features visible in /capabilities → Features tab
- [ ] Filter by category "Data - *" shows all migrated features

---

## Phase 2: Update Gap Detection Service

### 2.1 Modify GapDetector to query Features

**Current**: Queries `trading_gaps` table and `trading_requirements.yaml`
**New**: Queries `feature_capabilities` where `source = 'trading_requirement'`

```python
# backend/app/services/gap_detection/gap_detector.py

def get_gaps(self) -> list[Gap]:
    # Old: Load from YAML + check against trading_gaps table
    # New: Query features with source='trading_requirement' and passes != true

    features = self.db.query(
        "SELECT * FROM feature_capabilities WHERE source = 'trading_requirement' AND (passes IS NULL OR passes = false)"
    )
    return [self._feature_to_gap(f) for f in features]

def get_coverage_by_analysis_type(self) -> dict[str, float]:
    # Group features by category, calculate passes/total
    pass
```

### 2.2 Update gap summary endpoint

`GET /api/gaps/summary` should:
- Query features instead of trading_gaps
- Calculate coverage from feature passes status
- Group by category for analysis_type breakdown

### 2.3 Deprecate or remove

- [ ] `trading_gaps` table (after migration verified)
- [ ] `feature_gap_mappings` table (gaps ARE features now)
- [ ] `trading_requirements.yaml` (data now in DB)

---

## Phase 3: UI Updates

### 3.1 Update Trading Reqs tab

**Option A**: Remove tab, add "Data Requirements" filter to Features tab
**Option B**: Keep tab as filtered view of Features (category LIKE 'Data - %')

Recommendation: Option B (less disruptive)

### 3.2 Update gap-related UI components

- [ ] GapsOverview.tsx → Query features API with filter
- [ ] Any gap badges/indicators → Use feature passes status
- [ ] Gap coverage charts → Calculate from features

### 3.3 Update Features tab

- [ ] Add "Data - *" categories to filter dropdown
- [ ] Show source badge for trading_requirement features

---

## Phase 4: Command Updates

### 4.1 Update /task_it

- When creating data-related features, use appropriate "Data - X" category
- Auto-link to VG-INTEL/VG-RELY based on category

### 4.2 Update /audit_it

- Remove separate gap analysis phase
- Gap coverage = features with category "Data - *" and passes=true

### 4.3 Update gap keyword matching in commands

Current (task_it.md lines 261-287):
```
| Keywords | Gap ID |
| earnings, eps | GAP-003 |
```

New:
```
| Keywords | Feature Category |
| earnings, eps | Data - Fundamental |
```

---

## Phase 5: Cleanup

### 5.1 Delete orphan VG-PERF

```bash
curl -X DELETE http://localhost:8000/api/vision-goals/VG-PERF
```

Or reassign its 1 feature to appropriate goal first.

### 5.2 Update roadmap status

Current roadmap shows phases 1-3 as "complete" but vision goals show 13-35% pass rates.

Options:
- Update roadmap status to "in_progress" for accuracy
- Or define "complete" as "code exists" vs "verified working"

### 5.3 Remove deprecated code

- [ ] Delete `backend/app/services/gap_detection/` (or refactor to use features)
- [ ] Delete `backend/app/api/gaps.py` (or refactor as feature filter)
- [ ] Delete `trading_requirements.yaml`
- [ ] Drop `trading_gaps` table
- [ ] Drop `feature_gap_mappings` table

---

## Migration Checklist

### Pre-Migration
- [ ] Backup database
- [ ] Document current gap count and coverage stats
- [ ] Create rollback plan

### Migration
- [ ] Create 47 features from trading_requirements.yaml
- [ ] Set appropriate categories, vision_goals, acceptance_criteria
- [ ] Verify all features created correctly
- [ ] Test gap detection with new feature queries

### Post-Migration
- [ ] Update UI components
- [ ] Update slash commands
- [ ] Delete deprecated tables/code
- [ ] Update documentation
- [ ] Delete VG-PERF orphan

---

## Success Criteria

- [ ] Single Features system (no separate gaps)
- [ ] All 47 trading reqs visible as features
- [ ] Gap coverage calculated from feature passes status
- [ ] /audit_it works with unified system
- [ ] Trading Reqs tab shows filtered features
- [ ] No references to trading_gaps table in codebase

---

## Files to Modify

### New Files
- `backend/migrations/XXX_migrate_trading_reqs_to_features.py`

### Modified Files
- `backend/app/services/gap_detection/gap_detector.py`
- `backend/app/api/gaps.py`
- `frontend/components/capabilities/GapsOverview.tsx`
- `.claude/commands/task_it.md`
- `.claude/commands/audit_it.md`

### Deleted Files (after migration)
- `backend/app/config/trading_requirements.yaml`
- `backend/app/services/gap_detection/requirements.py`
- `backend/migrations/XXX_trading_gaps.sql` (keep for history)

---

## Notes

- This is a significant refactor - do in stages
- Keep gap detection service working throughout (query features instead of gaps)
- Consider feature_id format: FEAT-GAP-003 or just absorb into normal FEAT-XXX sequence
- The 47 gaps become 47 features, which is fine - they're legitimate work items
