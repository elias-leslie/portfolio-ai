# Task List: Backfill Acceptance Criteria for ALL 163 Features

**Source**: Continuation of tasks-0103
**Complexity**: Medium
**Effort**: MEDIUM
**Environment**: Local Dev
**Created**: 2025-12-06

---

## ~~CRITICAL INSTRUCTIONS FOR NEXT SESSION~~ **COMPLETED 2025-12-06**

All 164 features now have acceptance criteria. Task completed successfully.

---

## Summary

**Goal**: Add acceptance criteria to ALL 164 features (not just 31). **COMPLETED**

**Approach**:
1. Launched 8 parallel Explore agents covering all 26 categories
2. Each agent analyzed feature names/descriptions
3. Generated 2+ testable criteria per feature with correct schema
4. Merged all outputs into `tasks/backfill/generated-criteria.json`
5. Applied via `tasks/backfill/apply_criteria.py`

**Final state** (2025-12-06):
- ALL 164 features have acceptance_criteria
- 163 features have 2 criteria, 1 has 3 criteria
- ALL criteria have correct schema (criterion, verification, type, passed)

**Files created**:
- `tasks/backfill/generated-criteria.json` - 135 criteria definitions
- `tasks/backfill/apply_criteria.py` - Backfill script using API

---

## Tasks

### 0.0 Verify Starting State

- [x] 0.1 Count features missing criteria
  ```bash
  curl -s 'http://localhost:8000/api/capabilities/features/?limit=200' | jq '[.features[] | select((.acceptance_criteria | length) == 0)] | length'
  ```
  **Result**: 133 features missing criteria (31 had existing)
- [x] 0.2 Get list of feature categories
  ```bash
  curl -s 'http://localhost:8000/api/capabilities/features/?limit=200' | jq '[.features[].category] | unique'
  ```
  **Result**: 26 categories identified

### 1.0 Generate Criteria by Category (Parallel Agents)

Launched 8 parallel Explore agents covering all categories:

- [x] 1.1 **Dashboard + Analytics** - Agent 1 (15 features)
- [x] 1.2 **Watchlist + Portfolio** - Agent 2 (25 features)
- [x] 1.3 **Paper Trading + Backtest** - Agent 3 (15 features)
- [x] 1.4 **Strategies + Recommendations + Trading** - Agent 4 (13 features)
- [x] 1.5 **Agents + Status** - Agent 5 (20 features)
- [x] 1.6 **Capabilities + Settings + Shared UI** - Agent 6 (19 features)
- [x] 1.7 **Architecture + Infrastructure + Foundations + Prompts** - Agent 7 (11 features)
- [x] 1.8 **News + Intelligence + Market Data + Fundamentals + Ideas + Validation + Test** - Agent 8 (17 features)

### 2.0 Merge and Apply

- [x] 2.1 Merge all agent outputs into single JSON
  **Result**: Created `tasks/backfill/generated-criteria.json` with 135 criteria definitions
- [x] 2.2 Validate schema (all have criterion, verification, type, passed)
  **Result**: All criteria use correct schema
- [x] 2.3 Run backfill Python script
  **Result**: `tasks/backfill/apply_criteria.py` applied criteria via PATCH /api/capabilities/features/{feature_id}/acceptance-criteria
- [x] 2.4 Verify all 164 features have criteria
  **Result**: 133 updated, 31 already had criteria (2 skipped as duplicates)

### 3.0 Verification

- [x] 3.1 API check: all features have acceptance_criteria
  ```bash
  curl -s 'http://localhost:8000/api/capabilities/features/?limit=200' | jq '{
    total: .total,
    with_criteria: [.features[] | select((.acceptance_criteria | length) > 0)] | length,
    without_criteria: [.features[] | select((.acceptance_criteria | length) == 0)] | length
  }'
  ```
  **Result**: `{"total": 164, "with_criteria": 164, "without_criteria": 0}`
- [x] 3.2 Criteria distribution: 163 features with 2 criteria, 1 feature with 3 criteria
- [ ] 3.3 Keep reference JSON for future reference (not deleted)

---

## Schema Reference

**CORRECT schema** (from backend AcceptanceCriterion model):
```json
{
  "id": "ac-001",
  "criterion": "What needs to be true",
  "verification": "How to verify (curl, screenshot, pytest)",
  "type": "api|ui|test|db|backend|quality",
  "passed": null
}
```

**Vision goals**: VG-INTEL, VG-AUTO, VG-PORT, VG-VALID, VG-RELY, VG-UX, VG-QUAL

---

## Agent Prompt Template

```
Analyze features in category "{CATEGORY}" that have no acceptance criteria.

For each feature, generate 2-3 testable acceptance criteria based on the feature name and description.

Return JSON in this EXACT format:
{
  "FEAT-XXX": {
    "acceptance_criteria": [
      {"id": "ac-001", "criterion": "...", "verification": "...", "type": "api|ui|test|db|backend", "passed": null}
    ],
    "vision_goals": ["VG-XXX"]
  }
}

Map to vision goals:
- Dashboard/display features → VG-UX or VG-INTEL
- API/data features → VG-RELY or VG-INTEL
- Agent features → VG-AUTO
- Backtest/strategy features → VG-VALID
- Portfolio/watchlist features → VG-PORT
- Quality/testing features → VG-QUAL
```

---

## Execution Notes

- Start fresh session (this task uses many agents)
- Each agent handles ~20-30 features
- Merge outputs carefully (validate JSON)
- Run backfill script from backend directory with venv activated

---

**Version**: 1.0.0 | **Created**: 2025-12-06
