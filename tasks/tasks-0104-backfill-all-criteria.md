# Task List: Backfill Acceptance Criteria for ALL 163 Features

**Source**: Continuation of tasks-0103
**Complexity**: Medium
**Effort**: MEDIUM
**Environment**: Local Dev
**Created**: 2025-12-06

---

## CRITICAL INSTRUCTIONS FOR NEXT SESSION

**YOU MUST**:
1. Launch MULTIPLE Explore agents in "very thorough" mode
2. EXHAUSTIVELY gather acceptance criteria for ALL 163 features
3. UPDATE `tasks/backfill/feature-specs-reference.json` with ALL features
4. Use CORRECT schema: `criterion`, `verification`, `type`, `passed` (NOT description/verification_cmd)
5. Run `/audit_it --backfill tasks/backfill/feature-specs-reference.json`
6. VERIFY all 163 features have criteria via API

**NO ASSUMPTIONS** - Only use FACTS from:
- Existing feature names/descriptions in database
- Task files in `tasks/archive/`
- Actual API endpoints and UI components
- Test files that verify functionality

---

## Summary

**Goal**: Add acceptance criteria to ALL 163 features (not just 31).

**Approach**:
1. Launch 6+ parallel Explore agents (very thorough mode)
2. Each agent covers different feature categories
3. Agents analyze: feature name, description, related code, existing tests
4. Generate 2+ testable criteria per feature with correct schema
5. Merge all outputs into reference JSON
6. Run backfill

**Current state**:
- 31 features have acceptance_criteria (from tasks-0103)
- **132 features NEED criteria added**
- Reference JSON at `tasks/backfill/feature-specs-reference.json` (incomplete - only 31 features)

**Target state**:
- ALL 163 features have 2+ acceptance criteria
- ALL criteria have correct schema
- `/audit_it --backfill` runs successfully

---

## Tasks

### 0.0 Verify Starting State

- [ ] 0.1 Count features missing criteria
  ```bash
  curl -s 'http://localhost:8000/api/capabilities/features/?limit=200' | jq '[.features[] | select((.acceptance_criteria | length) == 0)] | length'
  ```
- [ ] 0.2 Get list of feature categories
  ```bash
  curl -s 'http://localhost:8000/api/capabilities/features/?limit=200' | jq '[.features[].category] | unique'
  ```

### 1.0 Generate Criteria by Category (Parallel Agents)

Launch 6 parallel Explore agents, one per major category:

- [ ] 1.1 **Dashboard features** - Agent 1
  - Query: Features where category="Dashboard" and no criteria
  - Generate 2+ criteria per feature based on name/description
  - Output: JSON with correct schema (criterion, verification, type)

- [ ] 1.2 **Watchlist features** - Agent 2
  - Same approach for category="Watchlist"

- [ ] 1.3 **Portfolio features** - Agent 3
  - Same approach for category="Portfolio"

- [ ] 1.4 **Trading/Backtest/Strategies features** - Agent 4
  - Categories: Trading, Backtest, Strategies

- [ ] 1.5 **Agents/Status/Capabilities features** - Agent 5
  - Categories: Agents, Status, Capabilities

- [ ] 1.6 **Infrastructure/Settings/Recs features** - Agent 6
  - Categories: Infrastructure, Settings, Recs, other

### 2.0 Merge and Apply

- [ ] 2.1 Merge all agent outputs into single JSON
- [ ] 2.2 Validate schema (all have criterion, verification, type, passed)
- [ ] 2.3 Run backfill Python script
- [ ] 2.4 Verify all 163 features have criteria

### 3.0 Verification

- [ ] 3.1 API check: all features have acceptance_criteria
  ```bash
  curl -s 'http://localhost:8000/api/capabilities/features/?limit=200' | jq '{
    total: .total,
    with_criteria: [.features[] | select((.acceptance_criteria | length) > 0)] | length,
    without_criteria: [.features[] | select((.acceptance_criteria | length) == 0)] | length
  }'
  ```
- [ ] 3.2 Screenshot: Features tab shows criteria counts for all features
- [ ] 3.3 Delete reference JSON after successful backfill

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
