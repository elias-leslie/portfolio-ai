---
description: Generate a detailed task list from a PRD
argument-hint: [PRD filename]
---

# Rule: Generating a Task List from a PRD

## Goal

To guide an AI assistant in creating a detailed, step-by-step task list in Markdown format based on an existing Product Requirements Document (PRD). The task list should guide a developer through implementation.

## Output

- **Format:** Markdown (`.md`)
- **Location:** `/tasks/`
- **Filename:** `tasks-[prd-file-name].md` (e.g., `tasks-0001-prd-user-profile-editing.md`)

## Process

1.  **Receive PRD Reference:** The user points the AI to a specific PRD file
2.  **Analyze PRD:** The AI reads and analyzes the functional requirements, user stories, and other sections of the specified PRD.
3.  **Assess Current State:** Review the existing codebase to understand existing infrastructre, architectural patterns and conventions. Also, identify any existing components or features that already exist and could be relevant to the PRD requirements. Then, identify existing related files, components, and utilities that can be leveraged or need modification.
4.  **Phase 1: Generate Parent Tasks:** Based on the PRD analysis and current state assessment, create the file and generate the main, high-level tasks required to implement the feature. Use your judgement on how many high-level tasks to use. It's likely to be about five tasks. Present these tasks to the user in the specified format (without sub-tasks yet). Inform the user: "I have generated the high-level tasks based on the PRD. Ready to generate the sub-tasks? Respond with 'Go' to proceed."
5.  **Wait for Confirmation:** Pause and wait for the user to respond with "Go".
6.  **Phase 2: Generate Sub-Tasks:** Once the user confirms, break down each parent task into smaller, actionable sub-tasks necessary to complete the parent task. Ensure sub-tasks logically follow from the parent task, cover the implementation details implied by the PRD, and consider existing codebase patterns where relevant without being constrained by them.
7.  **Identify Relevant Files:** Based on the tasks and PRD, identify potential files that will need to be created or modified. List these under the `Relevant Files` section, including corresponding test files if applicable.
8.  **Generate Final Output:** Combine the parent tasks, sub-tasks, relevant files, and notes into the final Markdown structure.
9.  **Save Task List:** Save the generated document in the `/tasks/` directory with the filename `tasks-[prd-file-name].md`, where `[prd-file-name]` matches the base name of the input PRD file (e.g., if the input was `0001-prd-user-profile-editing.md`, the output is `tasks-0001-prd-user-profile-editing.md`).

## Output Format

The generated task list _must_ follow this structure:

```markdown
# Task List: [Feature Name]

**PRD**: `[prd-filename].md`
**Status**: Ready for Implementation
**Completion**: 0% (Not started)
**Effort to Complete**: [Low | Medium | High]
**Last Updated**: YYYY-MM-DD

**Note on Effort Levels**:
- **Low**: 1-2 hours of straightforward work
- **Medium**: Half day of work with some complexity
- **High**: Full day or more, significant complexity

---

## Summary

**✅ COMPLETE:**
- (None yet)

**🔄 IN PROGRESS:**
- (Not started)

**⚠️ NEXT STEPS:**
1. Begin with Task 1.0
2. Follow checklist sequentially
3. Update this summary as work progresses

**EFFORT TO COMPLETE:** [Low | Medium | High]

---

## Relevant Files

### Files to Create ([N] new files)

- `path/to/file1.py` (~XX lines) - Brief description (e.g., Main implementation module)
- `tests/unit/test_file1.py` (~XX lines) - Unit tests for file1.py
- `path/to/file2.py` (~XX lines) - Brief description
- `tests/unit/test_file2.py` (~XX lines) - Unit tests for file2.py

### Files to Update ([N] files)

- `path/to/existing.py` - What changes needed (e.g., Add new method X, update import Y)
- `path/to/another.py` - What changes needed
- `docs/core/ARCHITECTURE.md` - Document new pattern/component

### Notes

- Unit tests should be placed in `tests/unit/` or `tests/integration/` directories
- Use `pytest tests/` to run all tests
- Use `pytest tests/unit/test_file1.py -v` to run specific test file
- Use `mypy app/ --strict` to verify type safety
- Use `scripts/lint.sh` to run linting and formatting checks

---

## Tasks

- [ ] 1.0 Parent Task Title
  - [ ] 1.1 Sub-task description 1.1
    - [ ] 1.1.1 Detailed action if needed (e.g., Create class X with methods Y and Z)
    - [ ] 1.1.2 Another detailed action (e.g., Add type hints to all function signatures)
  - [ ] 1.2 Sub-task description 1.2
  - [ ] 1.3 Sub-task description 1.3
- [ ] 2.0 Parent Task Title
  - [ ] 2.1 Sub-task description 2.1
  - [ ] 2.2 Sub-task description 2.2
- [ ] 3.0 Parent Task Title
  - [ ] 3.1 Sub-task description 3.1

---

## Verification & Production Readiness

**MANDATORY before marking task "COMPLETE ✅":**

- [ ] **Functional Completeness**
  - [ ] All PRD requirements implemented
  - [ ] All user stories satisfied
  - [ ] Integration points working correctly
  - [ ] Zero known bugs or regressions

- [ ] **Test Coverage** (target: 80%+)
  - [ ] Unit tests written for all new functions/classes
  - [ ] Integration tests for cross-module interactions
  - [ ] End-to-end test of complete workflow
  - [ ] All tests passing: `pytest tests/ -v`
  - [ ] Coverage verified: `pytest tests/ --cov=app --cov-report=term-missing`

- [ ] **Type Safety & Code Quality**
  - [ ] 100% type hints on all functions: `mypy app/ --strict` passes
  - [ ] Linting passes: `scripts/lint.sh` returns zero errors
  - [ ] Code formatting applied: `ruff format app/`
  - [ ] Complexity limits met (functions <50 lines, complexity <10)

- [ ] **Clean Implementation (No Band-Aids)**
  - [ ] All type hints are proper (no `Any` shortcuts like `Iterator[Any]`)
  - [ ] Behavior is explicit (no magic parsing/interception of strings or scope)
  - [ ] Single source of truth maintained (no duplicated logic/schemas)
  - [ ] Standard patterns used (no custom workarounds that "just work")
  - [ ] Clear intent throughout (no hidden behaviors behind wrappers)
  - [ ] Proper error messages (no silent failures or vague errors)

- [ ] **Documentation**
  - [ ] All public functions/classes have docstrings
  - [ ] ARCHITECTURE.md updated if patterns changed
  - [ ] DEVELOPMENT.md updated if workflows changed
  - [ ] Usage examples provided for new features

- [ ] **Security & Performance**
  - [ ] SQL queries use parameterized placeholders (no f-strings with user input)
  - [ ] No secrets in code (API keys in environment/database only)
  - [ ] Input validation on all user inputs
  - [ ] No performance regressions vs baseline

- [ ] **Operational Readiness**
  - [ ] Appropriate logging at INFO/WARNING/ERROR levels
  - [ ] Clear error messages on failures
  - [ ] Manual end-to-end test via UI/API successful
  - [ ] REFACTOR_STATUS.md updated (mark feature complete)

**See**: `docs/core/DEVELOPMENT.md` → "Production Readiness Requirements" for complete checklist
```

## Interaction Model

The process explicitly requires a pause after generating parent tasks to get user confirmation ("Go") before proceeding to generate the detailed sub-tasks. This ensures the high-level plan aligns with user expectations before diving into details.

## Target Audience

Assume the primary reader of the task list is a **junior developer** who will implement the feature with awareness of the existing codebase context.

---

## Usage

**With PRD filename:**
```
/task_it tasks/0004-prd-multi-source-failover-enforcement.md
```

**Interactive (will ask for PRD):**
```
/task_it
```

The AI will analyze the PRD, generate parent tasks, wait for "Go", then generate detailed sub-tasks.
