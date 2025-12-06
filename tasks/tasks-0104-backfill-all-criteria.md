# Task List: Backfill Acceptance Criteria for All Features

**Source**: Continuation of tasks-0103
**Complexity**: Medium
**Effort**: MEDIUM
**Environment**: Local Dev
**Created**: 2025-12-06

---

## Summary

**Goal**: Add acceptance criteria to all 163 features (currently only 31 have criteria).

**Approach**: Use parallel Explore agents to analyze features by category and generate appropriate acceptance criteria.

**Current state**:
- 31 features have acceptance_criteria (from tasks-0103)
- 132 features need criteria added
- Reference JSON saved at `data/backfill/feature-specs-reference.json` (31 features, 63 criteria)
- Earlier Explore agents extracted 200+ criteria from task files (in conversation history, not persisted)

**Permanent file location**: `~/portfolio-ai/data/backfill/feature-specs-reference.json`

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
