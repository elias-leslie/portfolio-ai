#!/bin/bash
# Bead Quality Validation Script
# Pre-push hook blocks if any open bead lacks required labels
# Required: complexity:* AND domains:* labels on all open beads

set -e

ERRORS=0

echo "Validating bead quality..."

# Check for beads without ANY labels
NO_LABELS=$(bd list --status open --json 2>/dev/null | jq '[.[] | select(.labels == null or .labels == [])] | length')
if [ "$NO_LABELS" -gt 0 ]; then
    echo ""
    echo "ERROR: $NO_LABELS bead(s) missing labels (complexity + domains required)"
    echo "---"
    bd list --status open --json 2>/dev/null | jq -r '.[] | select(.labels == null or .labels == []) | "  \(.id): \(.title)"'
    echo ""
    ERRORS=1
fi

# Check for beads missing complexity label
MISSING_COMPLEXITY=$(bd list --status open --json 2>/dev/null | jq '[.[] | select(.labels != null and (.labels | map(select(startswith("complexity:"))) | length == 0))] | length')
if [ "$MISSING_COMPLEXITY" -gt 0 ]; then
    echo ""
    echo "ERROR: $MISSING_COMPLEXITY bead(s) missing complexity label"
    echo "---"
    bd list --status open --json 2>/dev/null | jq -r '.[] | select(.labels != null and (.labels | map(select(startswith("complexity:"))) | length == 0)) | "  \(.id): \(.title)"'
    echo ""
    ERRORS=1
fi

# Check for beads missing domains label
MISSING_DOMAINS=$(bd list --status open --json 2>/dev/null | jq '[.[] | select(.labels != null and (.labels | map(select(startswith("domains:"))) | length == 0))] | length')
if [ "$MISSING_DOMAINS" -gt 0 ]; then
    echo ""
    echo "ERROR: $MISSING_DOMAINS bead(s) missing domains label"
    echo "---"
    bd list --status open --json 2>/dev/null | jq -r '.[] | select(.labels != null and (.labels | map(select(startswith("domains:"))) | length == 0)) | "  \(.id): \(.title)"'
    echo ""
    ERRORS=1
fi

# Warning: beads with minimal descriptions
SMALL_DESC=$(bd list --status open --json 2>/dev/null | jq '[.[] | select((.description // "") | length < 100)] | length')
if [ "$SMALL_DESC" -gt 0 ]; then
    echo ""
    echo "WARNING: $SMALL_DESC bead(s) have descriptions <100 chars (consider adding detail)"
    bd list --status open --json 2>/dev/null | jq -r '.[] | select((.description // "") | length < 100) | "  \(.id): \(.title) (\(.description // "" | length) chars)"'
    echo ""
fi

if [ "$ERRORS" -eq 0 ]; then
    TOTAL=$(bd list --status open --json 2>/dev/null | jq 'length')
    echo "All $TOTAL open beads have required labels (complexity + domains)"
    exit 0
else
    echo ""
    echo "BLOCKED: Fix label issues before pushing."
    echo ""
    echo "Fix command:"
    echo "  bd update <id> --set-labels 'complexity:small|medium|large' --set-labels 'domains:backend|frontend|database'"
    echo ""
    echo "Label reference:"
    echo "  complexity:small  - <3 files, <50 lines"
    echo "  complexity:medium - 3-10 files, <200 lines"
    echo "  complexity:large  - >10 files OR multi-domain"
    echo ""
    echo "  domains:backend   - Python/FastAPI/Celery"
    echo "  domains:frontend  - React/Next.js/TypeScript"
    echo "  domains:database  - Schema/migrations/SQL"
    exit 1
fi
