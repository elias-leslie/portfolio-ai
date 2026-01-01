# Multi-Agent Cross-Validation

**Implements**: FEAT-219
**Status**: planned
**Effort**: HIGH
**Priority**: P3

## Context
Implement automated quality control where Gemini generates insights and Claude validates them. Starts with human review queue for oversight, graduates to full auto mode when trusted. This aligns with the Agent Hub vision for cross-validation of AI outputs.

## 0.0 Scope Discovery (MANDATORY)
- [ ] Run 2-3 "very thorough" Explore agents on:
  - Existing GeminiCLIClient (`backend/app/agents/clients/gemini_client.py`)
  - Claude Agent SDK usage in Dev Companion (`services/dev-companion/`)
  - Agent runs and tool calls tables
- [ ] Document all files to modify with line ranges
- [ ] Identify similar patterns in codebase
- [ ] Note edge cases and dependencies

## Files to Modify
[Populated after scope discovery]
- backend/app/services/cross_validation.py (NEW) - CrossValidationService
- backend/app/api/routes/cross_validation.py (NEW) - API endpoints
- frontend/components/agents/ReviewQueue.tsx (NEW) - Human review queue
- frontend/components/agents/DisagreementPanel.tsx (NEW) - Show disagreements

## Cross-Validation Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      AUTOMATED CROSS-VALIDATION                             │
├─────────────────────────────────────────────────────────────────────────────┤
│ STEP 1: Gemini generates insight                                           │
│         "NVDA: BUY signal, momentum play, confidence 8/10"                 │
│                                                                            │
│ STEP 2: Claude reviews Gemini's work                                       │
│         "✓ Factual: Earnings beat confirmed                               │
│          ✓ Logic: Momentum thesis consistent with RSI/MACD                │
│          ⚠ Risk: RSI at 72 (overbought) - suggest waiting for pullback"   │
│                                                                            │
│ STEP 3 (Initial): User reviews suggested changes                           │
│         [Accept] [Modify] [Reject]                                        │
│                                                                            │
│ STEP 3 (Full Auto): Changes applied automatically                         │
│         (Only when "Full Auto" enabled in settings)                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Steps

### xval-001-infrastructure: Create CrossValidationService (HIGH)
**What**: Backend service that orchestrates Gemini->Claude review flow
**Why**: Automated quality control - catch errors before they reach users
**How**:
- Create `CrossValidationService` class
- Input: Gemini output (insight, confidence, reasoning)
- Process: Send to Claude for validation with structured prompt
- Output: ValidationResult (approved, modified, flagged_for_review)
- Store validation history for audit
**Files**:
- `backend/app/services/cross_validation.py` (NEW)
- `backend/app/api/routes/cross_validation.py` (NEW)
- `backend/app/models/cross_validation.py` (NEW) - ValidationResult, ValidationHistory
**Verification**: `pytest tests/test_cross_validation.py` passes

### xval-002-human-review: Build Human Review Queue (MEDIUM)
**What**: UI showing pending validations with Accept/Modify/Reject buttons
**Why**: Human oversight required initially before enabling full auto
**How**:
- Create `ReviewQueue.tsx` component
- Show Gemini output, Claude's review comments, disagreement indicators
- Actions: Accept (apply as-is), Modify (edit before apply), Reject (discard)
- Track approval rate for building confidence in full auto
**Files**:
- `frontend/components/agents/ReviewQueue.tsx` (NEW)
- `backend/app/api/routes/cross_validation.py` - endpoints for queue management
**Verification**: Screenshot shows review queue with pending items and action buttons

### xval-003-full-auto: Configurable Full Auto Mode (LOW)
**What**: When enabled, auto-apply validated changes without human review
**Why**: Graduate from manual oversight to autonomous operation
**How**:
- Add settings: full_auto_mode (boolean), auto_apply_threshold (0.0-1.0)
- When both agents agree AND confidence >= threshold, auto-apply
- When agents disagree, always queue for human review
- Log all auto-applied changes for audit
**Files**:
- `backend/app/services/cross_validation.py`
- `frontend/components/agents/SettingsModal.tsx` - full auto toggle
**Verification**: `curl -s http://localhost:8000/api/settings/cross-validation | jq .full_auto_mode` returns boolean

Cross-Validation Settings:
| Setting | Default | Description |
|---------|---------|-------------|
| `cross_validation_enabled` | true | Run validation on automated outputs |
| `require_human_review` | true | Queue changes for user approval |
| `full_auto_mode` | false | Auto-apply validated changes |
| `notify_on_disagreement` | true | Alert when agents disagree |
| `auto_apply_threshold` | 0.9 | Confidence for auto-apply (when full auto) |

### xval-004-disagreement-ui: Disagreement Tracking and Resolution (MEDIUM)
**What**: Show when Gemini and Claude outputs differ, with resolution options
**Why**: Learn from disagreements, improve prompts, build trust
**How**:
- Create `DisagreementPanel.tsx` showing side-by-side comparison
- Track disagreement reasons (factual, logical, risk assessment, other)
- Resolution options: Use Gemini, Use Claude, Hybrid, Escalate
- Store resolutions to improve future validation prompts
**Files**:
- `frontend/components/agents/DisagreementPanel.tsx` (NEW)
- `backend/app/models/cross_validation.py` - DisagreementRecord
**Verification**: UI shows disagreement indicators and resolution options

## Verification
- [ ] ac-001: `pytest tests/test_cross_validation.py` passes
- [ ] ac-002: Screenshot shows review queue UI with pending validations
- [ ] ac-003: `curl -s http://localhost:8000/api/settings/cross-validation | jq .full_auto_mode` returns boolean
- [ ] ac-004: UI shows disagreement indicators and resolution options

## Rollback
If issues occur: `git reset --hard HEAD~1`

## Dependencies
- FEAT-217 (Agent Hub) - Cross-validation is part of Agent Hub settings
- GeminiCLIClient (existing)
- Claude Agent SDK (existing in Dev Companion)
