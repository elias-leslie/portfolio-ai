---
description: Update core documentation to reflect recent changes and maintain single source of truth
---

# Rule: Automated Documentation Update

## Goal

To guide an AI assistant in reviewing recent changes and updating core documentation to reflect current reality, maintaining a single source of truth.

## When to Use

Invoke this workflow by using `/doc_it` in these scenarios:

1. **After completing a feature/phase** - Update docs to reflect new capabilities
2. **After major architectural changes** - Sync architecture docs with code reality
3. **On-demand when documentation feels stale** - User explicitly requests refresh
4. **Before major milestones** - Ensure docs are current before releases/presentations

## Core Documentation Structure

The project maintains **core documentation files** (typically in `docs/core/` or similar):
- System architecture and design decisions
- Setup and installation guides
- Development workflows and standards
- Operations and deployment procedures
- API and command references
- Active work and technical debt tracking

**Note**: The specific file names and structure are project-specific. Review the project's documentation organization first.

## Process

1. **Identify Documentation Timestamp**: Find the last documentation update marker (e.g., `.last_update` file or git commit)
2. **Analyze Changes Since Last Update**:
   - Review git commits since timestamp
   - Review conversation history for features implemented
   - Scan for new/modified files
   - Check for new documentation files outside core structure
3. **Identify Documentation Gaps**:
   - New features not documented
   - Architectural changes not reflected
   - Resolved issues still marked as open
   - Outdated commands or workflows
4. **Update Core Documentation**:
   - Read each core document
   - Update sections based on identified gaps
   - Ensure consistency across documents (no contradictions)
   - Preserve document structure and style
5. **Validate Commands**:
   - Run command validation script: `scripts/validate-commands.sh`
   - Review validation report (passed/failed/new/removed commands)
   - Fix any broken commands in documentation
   - Verify new commands work correctly
   - Update "Last Validated" timestamp in CLAUDE.md and DEVELOPMENT.md with current date
   - **If validation fails**: Update docs BEFORE committing (do not proceed with broken commands)
6. **Consolidate Stray Documentation**:
   - Find documentation files outside core structure
   - Merge content into appropriate core documents
   - Archive or deprecate stray files
7. **Update Index File**: Refresh main documentation map (e.g., README.md, CLAUDE.md)
8. **Finalize**:
   - Update documentation timestamp
   - Create git commit with clear summary
   - Display summary to user

## Quality Standards

### Documentation Should Be:
- **Current**: Reflects actual implementation, not aspirational features
- **Clear**: Written for both AI agents and human developers
- **Consistent**: No contradictions between documents
- **Scannable**: Headers and structure enable quick navigation
- **Cross-referenced**: Links between related sections instead of duplication

### Bloat Review (Critical)
Before finalizing, review each document for bloat:

**Signs of bloat**:
- Duplication of content across multiple documents
- Excessive detail that belongs in code/specs (not docs)
- Long procedural sections that could be summarized
- Project-specific details in generic workflow files
- Historical context that belongs in archives

**Action**: If any document exceeds reasonable size for its purpose:
1. **Archive the old bloated version**: Move to `docs/archive/legacy-YYYYMMDD-vN/<name>_detailed.md`
2. **Create lean core doc**: Rewrite core doc with essential information only (quick reference)
3. **Extract detailed sections to reference files**: Create actual reference docs in `docs/reference/` with extracted detailed content
4. **Update core doc links**: Ensure core doc links to reference files for detailed information
5. **Verify all links work**: Test that all cross-references are valid

**Example extraction** (API_REFERENCE.md bloat review):
- **Old**: `docs/core/API_REFERENCE.md` (1,173 lines with detailed examples)
- **New**: `docs/core/API_REFERENCE.md` (238 lines, quick reference only)
- **Archive**: `docs/archive/legacy-20251025-v2/api_reference_detailed.md` (historical backup)
- **Extracted to** `docs/reference/`:
  - `cli-commands.md` (252 lines) - Detailed CLI examples with output samples
  - `query-examples.md` (276 lines) - SQL query examples, presets, export formats
  - `config-schemas.md` (351 lines) - Complete YAML/JSON schema examples

**Size guidelines** (approximate):
- Main index file (README/CLAUDE.md): <200 lines
- Core documentation files: <800 lines each
- Workflow files (.ai_dev_tasks): <100 lines each

## Output

### Required Artifacts:
1. **Updated core documentation files** - Refreshed to reflect current reality
2. **Archived stray files** - Moved to archive directory with timestamps
3. **Updated index** - Main documentation map points to core docs
4. **Timestamp update** - Marker file updated with current ISO timestamp
5. **Git commit** - Conventional commit format summarizing changes

### Commit Format:
```
docs: <brief summary of update>

Updated documentation for:
- <Feature/change 1>
- <Feature/change 2>

Documents updated:
- <Doc name 1>: <what changed>
- <Doc name 2>: <what changed>

Command validation:
- ✓ X commands validated
- ⊕ Y new commands added
- ⊗ Z obsolete commands removed

Last validated: YYYY-MM-DD

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

## Consolidation Strategy

**For stray documentation files** (files outside core structure):
1. Read the stray file
2. Identify which core document(s) it belongs in
3. Extract relevant content and integrate into core doc(s)
4. Move original file to archive directory with timestamp
5. Document consolidation in commit message

**Archive naming**: `docs/archive/legacy-YYYYMMDD-vN/` where N increments for multiple archives on same day

## Anti-Patterns to Avoid

- ❌ Speculation: "This might be..." → Use "This is..." or "Not yet implemented"
- ❌ Outdated info: Always reflect current reality
- ❌ Duplication: Don't repeat content across multiple docs; link instead
- ❌ Jargon without explanation: Define terms on first use
- ❌ Implementation details: Save for code comments, not docs
- ❌ Bloated workflow files: Keep .ai_dev_tasks files focused and generic

## Target Audience

Assume the primary readers are **AI coding assistants** and **human developers** who need to understand the project quickly and accurately.

## Success Criteria

After completion, verify:
- ✅ All core docs exist and are up-to-date
- ✅ All recent features documented (cross-check git log)
- ✅ All resolved issues marked as resolved
- ✅ No stray documentation files (all consolidated or archived)
- ✅ No contradictions between documents
- ✅ **All documented commands validated and working** (no failed validations)
- ✅ **"Last Validated" timestamps updated** in CLAUDE.md and DEVELOPMENT.md
- ✅ Timestamp marker reflects actual update time
- ✅ Git commit created with clear summary (includes validation results)
- ✅ No bloat: All files within reasonable size limits

---

## Usage

Simply invoke the command (no arguments needed):
```
/doc_it
```

The AI will:
1. Analyze git history since last documentation update
2. Identify gaps and outdated information
3. Update all core documentation files
4. **Validate all documented commands** (run scripts/validate-commands.sh)
5. **Fix any broken commands** before proceeding
6. Consolidate stray documentation files
7. Review for bloat and extract if needed
8. Create a commit with documentation changes and validation summary

## Example Output

```
📚 Documentation Update Summary

Changes analyzed: 15 commits since 2025-10-20

Core docs updated:
✓ ARCHITECTURE.md - Added multi-source failover pattern
✓ REFACTOR_STATUS.md - Marked P1.1 as complete
✓ CLAUDE.md - Updated Phase 1 status

Command validation:
✓ 45 commands validated successfully
⊕ 3 new commands added (verified working)
⊗ 1 obsolete command removed from docs
Last validated: 2025-10-27

Stray files consolidated:
→ docs/feature_notes.md archived to docs/archive/legacy-20251025-v3/

Bloat review:
✓ All files within size guidelines

Commit created: docs: update for P1.1 field mapping completion
```
