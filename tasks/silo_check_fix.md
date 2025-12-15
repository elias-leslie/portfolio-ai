# Implement Architecture Coherence Governance System

## Objective
Create a mandatory architecture coherence enforcement system that prevents AI agents from building code/database silos and enforces DRY principles. The system must include immediate bead creation when violations are detected.

## Context Gathering (Do This First)
Before implementing, gather context by exploring:

Existing rules structure: ls -la .claude/rules/ - understand current rule file patterns
Existing commands structure: ls -la .claude/commands/ - understand current command patterns
CLAUDE.md format: Read /home/user/portfolio-ai/CLAUDE.md to understand update patterns
AGENTS.md: Read /home/user/portfolio-ai/AGENTS.md for workflow context
Beads CLI usage: Run bd --help and review existing bead patterns with bd list --json | head -50
Existing architecture docs: Read /home/user/portfolio-ai/docs/core/ARCHITECTURE.md
Database schema: Explore backend/ for models/schema to understand current DB patterns
Existing similar commands: Read /home/user/portfolio-ai/.claude/commands/data_check.md and /home/user/portfolio-ai/.claude/commands/clean_it.md for command format patterns
Deliverables
1. Create Rule File: .claude/rules/architecture-coherence.md
Purpose: Mandatory always-on enforcement for all AI coding sessions

Must Include:

Clear definition of what constitutes a "silo" (code and database)
Pre-implementation checklist (MUST verify before writing any code):
Search for existing similar implementations
Check established patterns in codebase
Review existing utilities/helpers
Verify naming conventions
For DB changes: review existing schema for related tables/columns
MANDATORY immediate bead creation protocol:
When ANY violation is discovered during work: STOP IMMEDIATELY
Check if bead exists: bd list --status open --json | jq -r '.[] | "\(.id) \(.title)"'
Create bead if not exists: bd create --title "Arch: <description>" --type tech_debt --priority <1-3> --json
Add full context with bd update <id> --description "..."
Priority guidelines: P1=critical/blocking, P2=clear violations affecting multiple areas, P3=minor inconsistencies
Then resume original work
Red flags that require investigation before proceeding
"Consolidation over creation" principle - default to extending existing code/schema
Concrete examples of BAD (silo) vs GOOD (holistic) approaches for both code and DB
Reference to the companion /silo_check command
Style: Match the format and tone of existing rules in .claude/rules/

2. Create Command File: .claude/commands/silo_check.md
Purpose: On-demand comprehensive architecture coherence audit

Must Include:

Arguments section:

--scope <path>: Limit scan to specific directory (default: full codebase)
--fix: Auto-fix simple violations (default: report only)
--db-only: Focus on database schema analysis only
--code-only: Focus on code analysis only
--deep: Extra thorough analysis with more agents
Phase 1 - Parallel Discovery (launch multiple Task/Explore agents simultaneously):

Agent 1: Duplicate code detection (similar functions, copy-paste, utility duplication)
Agent 2: Database schema analysis (overlapping tables/columns, normalization issues, naming inconsistencies, missing relationships)
Agent 3: Service/module boundary analysis (overlapping responsibilities, shared code opportunities, API pattern inconsistencies)
Agent 4: Pattern consistency analysis (error handling, logging, auth patterns, validation approaches)
Agent 5 (if --deep): Naming convention audit across all layers
Phase 2 - Severity Classification:

CRITICAL: Fix immediately (data integrity, security, blocking)
HIGH: Create P1 bead (>3 occurrences, relationship issues, boundary violations)
MEDIUM: Create P2 bead (2-3 occurrences, non-critical pattern deviations)
LOW: Create P3 bead or note (minor, style-only, future opportunities)
Phase 3 - Auto-Fix (if --fix flag):

What CAN be auto-fixed: naming conventions, import consolidation, exact code duplicates, missing type hints
What CANNOT be auto-fixed: schema changes, business logic, API contracts, anything needing migration
Phase 4 - Bead Creation:

For each non-auto-fixed issue, create bead with:
Title: "Arch: <concise description>"
Type: tech_debt
Priority: 1-3 based on severity
Description with: Issue Type, Severity, Locations, Current State, Desired State, Impact, Suggested Approach, Estimated Effort, Dependencies, Discovery timestamp
Phase 5 - Summary Report:

ASCII table showing: findings by severity, findings by category, beads created, next steps
Categories to track: DRY Violations, Data Silos, Pattern Mismatches, Schema Issues, Boundary Violations
Usage Examples: Show common invocation patterns

Style: Match the format of existing commands like /data_check.md and /clean_it.md

3. Update CLAUDE.md
Add to the appropriate tables:

Quick Reference table: | Silo/DRY check | /silo_check (--fix, --deep, --scope) |
Rules table: | architecture-coherence.md | **MANDATORY: Anti-silo, DRY, holistic architecture** |
4. Update AGENTS.md (if appropriate)
If there's a section about code quality or pre-implementation checks, add a reference to the architecture coherence rule.

Implementation Requirements
Consistency: Match existing file formats, markdown styles, and conventions in the repo
Beads Integration: Use the actual bd CLI syntax from this project (verify with bd --help)
Agent Patterns: Use the Task tool with subagent_type=Explore for the parallel discovery agents in the command
Practical Examples: Include examples specific to THIS codebase where possible (Python/FastAPI backend, Next.js frontend, PostgreSQL)
Cross-References: Link between the rule and command appropriately
Validation
After creating the files:

Verify rule file is readable and follows existing rule patterns
Verify command is executable by testing /silo_check invocation
Verify CLAUDE.md renders correctly with new entries
Run bd list to confirm bead CLI is working as expected
Commit
After implementation, commit with message:

feat: Architecture coherence governance system

- Add .claude/rules/architecture-coherence.md (mandatory anti-silo enforcement)
- Add .claude/commands/silo_check.md (comprehensive audit command)
- Update CLAUDE.md with quick references

Enforces DRY principles, prevents code/DB silos, mandates immediate
bead creation when violations discovered during any coding session.