# Slash Commands Analysis & Improvements

**Date:** 2025-10-30
**Purpose:** Apply lessons learned from band-aid analysis to improve slash commands
**Philosophy:** Clear, explicit, no bloat, prevent band-aids

---

## Overall Health Assessment

| Command | Lines | Bloat Risk | Issues Found | Priority |
|---------|-------|------------|--------------|----------|
| `/check_it` | 486 | 🟡 MEDIUM | 3 issues | MEDIUM |
| `/doc_it` | 239 | ✅ GOOD | 0 issues | NONE |
| `/do_it` | 128 | ✅ GOOD | 1 minor issue | LOW |
| `/next_it` | 226 | ✅ GOOD | 1 minor issue | LOW |
| `/plan_it` | 78 | ✅ GOOD | 0 issues | NONE |
| `/task_it` | 175 | ✅ GOOD | 1 moderate issue | MEDIUM |

**Summary:** Generally healthy, `/check_it` needs attention, `/task_it` needs one key addition

---

## Command-by-Command Analysis

### ✅ `/plan_it` - PERFECT (No changes needed)
**Lines:** 78
**Status:** Well-scoped, clear, concise

**Strengths:**
- ✅ Crisp, focused instructions
- ✅ Clear process flow
- ✅ Good interaction model (clarifying questions)
- ✅ No bloat

**Issues:** None

**Recommendation:** **KEEP AS-IS**

---

### ✅ `/doc_it` - EXCELLENT (No changes needed)
**Lines:** 239
**Status:** Comprehensive but not bloated

**Strengths:**
- ✅ Explicitly addresses bloat prevention (lines 70-100)
- ✅ Path standardization rules are clear
- ✅ Consolidation strategy is actionable
- ✅ Success criteria are specific

**Why it's longer:** Justified detail for complex task (documentation maintenance across many files)

**Issues:** None

**Recommendation:** **KEEP AS-IS** - This is a model of how to write a comprehensive command without bloat

---

### ⚠️ `/do_it` - GOOD (1 minor issue)
**Lines:** 128
**Status:** Clear and actionable

**Strengths:**
- ✅ Explicit about autonomous vs. interactive mode
- ✅ Clear test/commit protocol
- ✅ Good error handling guidance

**Issues:**

#### Issue #1: Missing Clean Code Guidance
The command tells you to fix errors but doesn't mention **preventing band-aids**.

**Impact:** LOW - But relates directly to our migration learnings

**Current:** (Line 14-20)
```markdown
- **ALWAYS fix errors immediately:** Do NOT skip, bypass, or ignore errors...
  - **Pre-commit hook failures:** Fix ALL errors reported by linters/type checkers
  - **Test failures:** Fix ALL failing tests
  - **Type errors:** Fix ALL mypy/type errors in code you touch
```

**Add After Line 20:**
```markdown
- **NO BAND-AIDS:** When implementing tasks, avoid workarounds:
  - **Explicit over implicit:** Don't create "magic" behavior that's hard to debug
  - **Proper types:** Never use `Any` as a shortcut (use proper type hints)
  - **Clear intent:** Don't intercept/parse to add hidden features
  - **Single source of truth:** Don't duplicate logic/data across files
  - **Standard patterns:** Use well-known patterns, not custom workarounds
  - **If blocked:** Ask user for guidance rather than implementing a hack
```

**Recommendation:** Add "NO BAND-AIDS" section (15 lines)

---

### ⚠️ `/next_it` - GOOD (1 minor issue)
**Lines:** 226
**Status:** Well-structured, comprehensive

**Strengths:**
- ✅ Clear prioritization framework
- ✅ Good balance of categories (known/quick/strategic)
- ✅ Free/OSS emphasis is correct

**Issues:**

#### Issue #1: Missing "Avoid Band-Aids" in Discovery
When analyzing code quality, it doesn't explicitly call out band-aid patterns.

**Impact:** LOW - But would improve code quality discovery

**Current:** (Lines 20-27)
```markdown
**Code Quality Scan**:
- Files exceeding project line limits, missing test coverage
- DRY violations (similar code patterns across files)
- Inline TODO/FIXME/HACK comments, missing type hints/docs
```

**Update To:**
```markdown
**Code Quality Scan**:
- Files exceeding project line limits, missing test coverage
- DRY violations (similar code patterns across files)
- Inline TODO/FIXME/HACK comments, missing type hints/docs
- **Band-aid patterns:** `Any` type shortcuts, magic string/SQL parsing, scope inspection, implicit behaviors, duplicated sources of truth
```

**Recommendation:** Add band-aid detection to code quality scan (1 line addition)

---

### 🟡 `/check_it` - NEEDS ATTENTION (3 issues)
**Lines:** 486
**Bloat Risk:** MEDIUM
**Status:** Functional but has issues

**Strengths:**
- ✅ Good use of Gemini for large context analysis
- ✅ Clear process phases
- ✅ Comprehensive scoring dimensions

**Issues:**

#### Issue #1: Overly Prescriptive Prompt Construction (MAJOR)
**Location:** Lines 53-150

**Problem:** The command includes a HUGE example prompt (97 lines!) with:
- Detailed @ syntax examples
- Specific file patterns for multiple languages
- Complete scoring rubric inline

**Why This Is Bloat:**
- The AI can construct this prompt dynamically based on project type
- Hardcoding file patterns makes it less adaptable
- Scoring dimensions should be discovered, not prescribed

**Impact:** MEDIUM - Makes command rigid and hard to maintain

**Solution:** Replace detailed prompt with **principles**:

**Replace Lines 53-150 with:**
```markdown
**Construction of Analysis Prompt** (Gemini-specific):

**Principles:**
1. **Auto-discover structure:** Use Glob to find all code/doc files dynamically
2. **Use broad wildcards:** Load entire directories (`@backend/**/*.py`, `@frontend/**/*.{ts,tsx}`)
3. **Include all artifacts:** Docs, code, config, tests, planning docs
4. **Let Gemini determine dimensions:** Don't prescribe specific categories; let Gemini identify what matters for this project type
5. **Request specificity:** Ask for file:line references, percentages, concrete recommendations

**Prompt Template:**
```
Analyze this codebase for solution alignment.

CONTEXT LOADED:
@**/*.md @docs/**/* (all documentation)
@backend/**/*.py @frontend/**/*.{ts,tsx} (all code - adapt patterns to project)
@**/pyproject.toml @**/package.json @**/.pre-commit-config.yaml (all config)
@tests/**/* (all tests - adapt pattern to project)
@tasks/**/* @.ai_dev_tasks/**/* (planning docs)

ANALYSIS REQUESTED:
1. Determine appropriate alignment dimensions for this project type
2. Score each dimension 0-100% based on documented standards vs. reality
3. Provide specific file:line references for issues
4. Rank issues by priority (critical/high/medium/low)
5. Include actionable recommendations with effort estimates

FORMAT:
- Executive summary with overall score
- Per-dimension breakdown with aligned/misaligned items
- Prioritized action items (top 15)
- Trend analysis if previous report exists
```
**Total:** ~45 lines instead of 97 lines
```

**Estimated Savings:** Remove ~52 lines of prescriptive detail

---

#### Issue #2: Redundant File Discovery Instructions
**Location:** Lines 163-188

**Problem:** Instructions for using Glob tool are repeated in multiple places:
- Lines 163-168: Auto-discovery instructions
- Lines 170-178: Wildcard pattern construction (duplicates lines 53-82)
- Lines 180-188: Context size management

**Impact:** MINOR - Repetition but not harmful

**Solution:** Consolidate to single "Discovery Process" section:

**Replace with:**
```markdown
### Phase 2: Discovery & Analysis

**Auto-Discovery:**
1. Use Glob to identify project structure:
   - Find all code files: `**/*.py`, `**/*.{ts,tsx,js,jsx}`, `**/*.{rs,go,java}`
   - Find all docs: `**/*.md`, `docs/**/*`
   - Find all configs: `**/pyproject.toml`, `**/package.json`, etc.
   - Find all tests: `tests/**/*`, `**/*.test.*`, `**/*.spec.*`

2. Construct comprehensive Gemini prompt:
   - Use `@` syntax with discovered patterns
   - Load entire directories (don't sample)
   - Include all discovered artifacts

3. Execute Gemini analysis with `mcp__gemini-cli__ask-gemini`:
   - Model: gemini-2.5-pro (default)
   - Let Gemini's large context handle full codebase
   - Request structured scoring and specific recommendations
```

**Estimated Savings:** Remove ~20 lines of redundant instructions

---

#### Issue #3: Missing "Detect Band-Aids" Dimension
**Location:** Lines 84-123 (scoring dimensions)

**Problem:** The command doesn't include a dimension for detecting band-aid patterns we learned about.

**Impact:** LOW - But directly relevant to our learnings

**Solution:** Add after line 119 (after "Security Best Practices"):

```markdown
7. CODE QUALITY & PATTERNS (0-100%):
   - Are proper types used (not `Any` shortcuts)?
   - Is behavior explicit (no magic parsing/interception)?
   - Single source of truth (no duplication)?
   - Standard patterns used (not custom workarounds)?
   - Clear intent (no hidden behaviors)?
```

**Estimated Addition:** +6 lines (justified)

---

### **Recommended Changes for `/check_it`:**

1. **Simplify prompt construction** (remove 52 lines)
2. **Consolidate discovery instructions** (remove 20 lines)
3. **Add band-aid detection dimension** (add 6 lines)

**Net Change:** -66 lines (486 → 420 lines), much clearer

---

### ⚠️ `/task_it` - GOOD (1 moderate issue)
**Lines:** 175
**Status:** Functional, one key addition needed

**Strengths:**
- ✅ Good two-phase approach (parent tasks → sub-tasks)
- ✅ Clear interaction model (wait for "Go")
- ✅ Comprehensive verification checklist

**Issues:**

#### Issue #1: Missing "Review for Band-Aids" in Verification
**Location:** Lines 107-150 (Verification checklist)

**Problem:** The production readiness checklist doesn't mention reviewing for band-aid patterns.

**Impact:** MODERATE - Tasks could be completed with band-aids still present

**Solution:** Add new section after "Type Safety & Code Quality" (line 135):

```markdown
- [ ] **Clean Implementation (No Band-Aids)**
  - [ ] All type hints are proper (no `Any` shortcuts)
  - [ ] Behavior is explicit (no magic parsing/interception)
  - [ ] Single source of truth maintained (no duplication)
  - [ ] Standard patterns used (no custom workarounds)
  - [ ] Clear intent throughout (no hidden behaviors)
  - [ ] Proper error messages (no silent failures)
```

**Estimated Addition:** +8 lines (justified - prevents band-aids in future tasks)

**Recommendation:** Add "Clean Implementation" verification section

---

## Issues NOT Found (Good News!)

### ✅ No Conflicts Between Commands
- Each command has a clear, distinct purpose
- Workflow integration is clear (`/next_it` → `/plan_it` → `/task_it` → `/do_it` → `/doc_it`)
- No overlap or contradictions

### ✅ No Vague Instructions
- All commands have specific, actionable guidance
- Success criteria are measurable
- Process flows are clear

### ✅ Appropriate Length
- No command is bloated except `/check_it` (which has fixable issues)
- `/doc_it` is long but justified (comprehensive scope)
- All others are appropriately concise

---

## Lessons Applied from Band-Aid Analysis

### Key Principles to Enforce:

1. **Explicit Over Implicit**
   - Applied in `/do_it`: "NO BAND-AIDS" section
   - Applied in `/check_it`: "Code Quality & Patterns" dimension

2. **Single Source of Truth**
   - Already present in `/doc_it` (consolidation strategy)
   - Added to verification checklists

3. **Proper Type Safety**
   - Added to `/task_it` verification
   - Mentioned in `/do_it` error handling

4. **Standard Patterns**
   - Added to `/do_it` guidance
   - Added to `/check_it` analysis dimensions

5. **No Magic Behavior**
   - Explicitly called out in band-aid prevention sections
   - Added to code quality scans

---

## Summary of Recommended Changes

| Command | Changes | Lines Impact | Priority |
|---------|---------|--------------|----------|
| `/plan_it` | None | 0 | N/A |
| `/doc_it` | None | 0 | N/A |
| `/do_it` | Add "NO BAND-AIDS" section | +15 | MEDIUM |
| `/next_it` | Add band-aid detection to scan | +1 | LOW |
| `/check_it` | Simplify, consolidate, add dimension | -66 (net) | HIGH |
| `/task_it` | Add "Clean Implementation" check | +8 | MEDIUM |

**Total Impact:** -42 lines (1,332 → 1,290 lines)
**Net Result:** Commands are clearer, more maintainable, and explicitly prevent band-aids

---

## Implementation Plan

### Priority 1: `/check_it` Refactor (HIGH)
1. Simplify prompt construction (remove prescriptive details)
2. Consolidate discovery instructions
3. Add code quality/patterns dimension
4. **Estimated Time:** 15 minutes
5. **Benefit:** More adaptable, easier to maintain, prevents rigidity

### Priority 2: `/do_it` Enhancement (MEDIUM)
1. Add "NO BAND-AIDS" section after error handling
2. **Estimated Time:** 5 minutes
3. **Benefit:** Prevents workarounds during implementation

### Priority 3: `/task_it` Enhancement (MEDIUM)
1. Add "Clean Implementation" verification section
2. **Estimated Time:** 3 minutes
3. **Benefit:** Catches band-aids in review before marking complete

### Priority 4: `/next_it` Enhancement (LOW)
1. Add band-aid patterns to code quality scan
2. **Estimated Time:** 1 minute
3. **Benefit:** Identifies band-aids as known issues

---

## Files to Update

1. `.claude/commands/check_it.md` - Refactor (HIGH priority)
2. `.claude/commands/do_it.md` - Add section (MEDIUM priority)
3. `.claude/commands/task_it.md` - Add section (MEDIUM priority)
4. `.claude/commands/next_it.md` - Add line (LOW priority)
5. `.claude/commands/plan_it.md` - No changes (PERFECT)
6. `.claude/commands/doc_it.md` - No changes (EXCELLENT)

---

## Verification Checklist

After making changes:
- [ ] All commands still under 500 lines (except `/check_it` which goes 486→420)
- [ ] No new contradictions introduced
- [ ] Band-aid prevention explicitly addressed in all workflow commands
- [ ] Instructions remain clear and actionable
- [ ] No prescriptive details that reduce adaptability

---

**Prepared By:** Claude Code Analysis
**Status:** Ready for implementation
**Estimated Total Time:** 24 minutes to apply all changes
