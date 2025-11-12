# Process Improvement #3: Smart Type-Aware Code Quality Detection

**Date**: 2025-11-09
**Issue**: Detection has SOME type awareness but missing critical categories
**Impact**: One-size-fits-all limits for diverse file types

---

## 📊 Current State

### What We Have ✅
```bash
TEST files:      800 lines  (lenient - test suites)
CONFIG files:    1000 lines (most lenient - schemas)
TYPES/MODELS:    600 lines  (data models)
COMPONENTS:      300 lines  (UI - strictest)
DEFAULT:         500 lines  (everything else)
```

### What We're Missing ❌

**Backend Categories Not Covered**:
- API endpoints (`api/*.py`) - Often have many routes, could be 600-800 lines
- Service files (`services/*.py`) - Orchestration logic, should be 400-600 lines
- Task files (`tasks/*.py`) - Celery tasks, complex workflows, 500-700 lines
- Data processing (`ingestion.py`, ETL) - Transformations, could be 600 lines
- Source connectors (`sources/*.py`) - API clients, 400-500 lines
- Query builders (`queries.py`, `storage/*.py`) - SQL logic, 500-600 lines

**Frontend Categories Not Covered**:
- Pages vs Components (pages can be longer)
- Layout files (structural, can be larger)
- Hook files (should be small, <100 lines)
- Context providers (state management, 200-400 lines)

**Cross-Cutting**:
- Documentation (*.md) - Not checked at all
- Scripts (automation, deployment) - Should be modular
- Database migrations - Currently excluded entirely

---

## 🎯 Recommended Comprehensive Type Catalog

### Backend Python Files

| File Type | Pattern | Threshold | Reason |
|-----------|---------|-----------|--------|
| **API Endpoints** | `api/*.py` | 600 lines | Multiple routes per file (REST convention) |
| **Services** | `services/*.py`, `*_service.py` | 500 lines | Orchestration, should delegate to helpers |
| **Celery Tasks** | `tasks/*.py`, `*_tasks.py` | 600 lines | Complex workflows, external calls |
| **Data Processing** | `ingestion.py`, `processor.py`, `*_etl.py` | 600 lines | Transformations, batching logic |
| **Source Connectors** | `sources/*.py` | 450 lines | API clients, should be focused |
| **Storage/Query** | `storage/*.py`, `queries.py` | 550 lines | SQL builders, connection management |
| **Models/Types** | `models.py`, `types/*.py` | 600 lines | Data definitions (many classes OK) |
| **Config/Schema** | `config.py`, `schema.py`, `settings.py` | 1000 lines | Declarative, low complexity |
| **Utils/Helpers** | `utils/*.py`, `helpers/*.py` | 300 lines | Should be small, focused |
| **Test Files** | `test_*.py`, `*_test.py`, `tests/*` | 800 lines | Test suites, setup/teardown |
| **Fixtures** | `conftest.py`, `fixtures/*.py` | 500 lines | Shared test utilities |
| **Default** | Everything else | 500 lines | General code |

### Frontend TypeScript/JavaScript Files

| File Type | Pattern | Threshold | Reason |
|-----------|---------|-----------|--------|
| **Pages** | `pages/*.tsx`, `app/*/page.tsx` | 400 lines | Complete page logic |
| **Layouts** | `layouts/*.tsx`, `*Layout.tsx` | 300 lines | Structural components |
| **Components** | `components/*.tsx` | 250 lines | Focused UI components |
| **Hooks** | `hooks/*.ts`, `use*.ts` | 100 lines | Reusable logic, must be small |
| **Context** | `contexts/*.tsx`, `*Context.tsx` | 350 lines | State management |
| **API Clients** | `api/*.ts`, `*Client.ts` | 400 lines | Backend communication |
| **Utils** | `utils/*.ts`, `lib/*.ts` | 200 lines | Helper functions |
| **Types** | `types/*.ts`, `*.d.ts` | 500 lines | Type definitions |
| **Config** | `*.config.ts`, `*.config.js` | 300 lines | Configuration |
| **Test** | `*.test.tsx`, `*.spec.ts` | 600 lines | Component tests |

### Documentation & Scripts

| File Type | Pattern | Threshold | Action |
|-----------|---------|-----------|--------|
| **Markdown** | `*.md` | INFO only | Warn if >2000 lines, suggest splitting |
| **Shell Scripts** | `*.sh` | 300 lines | Should be modular |
| **Python Scripts** | `scripts/*.py` | 400 lines | Automation, one-off tasks |

---

## 🔧 Implementation: Enhanced check-file-sizes.sh

```bash
#!/bin/bash
# Smart type-aware file size detection
# Auto-categorizes files and applies appropriate thresholds

DIR="${1:-.}"
VERBOSE=false

# Comprehensive type catalog
declare -A FILE_TYPES=(
  # Backend
  ["api"]="600:API endpoints"
  ["service"]="500:Services"
  ["task"]="600:Celery tasks"
  ["processing"]="600:Data processing"
  ["source"]="450:API sources"
  ["storage"]="550:Storage/queries"
  ["model"]="600:Models/types"
  ["config"]="1000:Config/schema"
  ["util"]="300:Utils/helpers"
  ["test"]="800:Tests"
  ["fixture"]="500:Test fixtures"

  # Frontend
  ["page"]="400:Pages"
  ["layout"]="300:Layouts"
  ["component"]="250:Components"
  ["hook"]="100:Hooks"
  ["context"]="350:Context providers"
  ["api-client"]="400:API clients"
  ["frontend-util"]="200:Frontend utils"
  ["types"]="500:Type definitions"

  # Scripts/docs
  ["script"]="300:Shell scripts"
  ["py-script"]="400:Python scripts"
  ["markdown"]="2000:Documentation"
)

# Smart categorization function
categorize_file() {
  local file=$1
  local base=$(basename "$file")

  # Backend patterns
  [[ $file == */api/* ]] && echo "api" && return
  [[ $file == *service*.py || $file == */services/* ]] && echo "service" && return
  [[ $file == *task*.py || $file == */tasks/* ]] && echo "task" && return
  [[ $file == *ingestion*.py || $file == *processor*.py || $file == *_etl.py ]] && echo "processing" && return
  [[ $file == */sources/* ]] && echo "source" && return
  [[ $file == */storage/* || $base == "queries.py" ]] && echo "storage" && return
  [[ $base == "models.py" || $file == */models/* || $file == */types/* ]] && echo "model" && return
  [[ $base == "config.py" || $base == "schema.py" || $base == "settings.py" ]] && echo "config" && return
  [[ $file == */utils/* || $file == */helpers/* ]] && echo "util" && return
  [[ $base == test_* || $base == *_test.py || $file == */tests/* ]] && echo "test" && return
  [[ $base == "conftest.py" || $file == */fixtures/* ]] && echo "fixture" && return

  # Frontend patterns
  [[ $file == */pages/* || $base == page.tsx ]] && echo "page" && return
  [[ $file == */layouts/* || $base == *Layout.tsx ]] && echo "layout" && return
  [[ $file == */components/* ]] && echo "component" && return
  [[ $base == use*.ts || $base == use*.tsx || $file == */hooks/* ]] && echo "hook" && return
  [[ $base == *Context.tsx || $file == */contexts/* ]] && echo "context" && return
  [[ $file == */api/*.ts && $file != */pages/api/* ]] && echo "api-client" && return
  [[ $file == */utils/*.ts || $file == */lib/*.ts ]] && echo "frontend-util" && return
  [[ $base == *.d.ts || $file == */types/*.ts ]] && echo "types" && return

  # Scripts/docs
  [[ $base == *.sh ]] && echo "script" && return
  [[ $file == */scripts/*.py ]] && echo "py-script" && return
  [[ $base == *.md ]] && echo "markdown" && return

  echo "default:500:General code"
}

# Process files
find "$DIR" \( -name "*.py" -o -name "*.ts" -o -name "*.tsx" -o -name "*.js" -o -name "*.sh" -o -name "*.md" \) -type f \
  ! -path "*/migrations/*" ! -path "*/node_modules/*" ! -path "*/.venv/*" | while read file; do

  lines=$(wc -l < "$file")
  category=$(categorize_file "$file")

  # Extract threshold and description
  if [[ $category == *:*:* ]]; then
    # Default format: "default:500:description"
    threshold=$(echo "$category" | cut -d: -f2)
    desc=$(echo "$category" | cut -d: -f3)
    type_name=$(echo "$category" | cut -d: -f1)
  else
    # Catalog format: use lookup
    type_info="${FILE_TYPES[$category]}"
    threshold=$(echo "$type_info" | cut -d: -f1)
    desc=$(echo "$type_info" | cut -d: -f2)
    type_name=$category
  fi

  # Determine severity
  if [ $lines -gt $((threshold * 2)) ]; then
    echo "🔴 CRITICAL: $file ($lines lines, type: $desc, threshold: $threshold)"
  elif [ $lines -gt $threshold ]; then
    echo "⚠️  WARNING: $file ($lines lines, type: $desc, threshold: $threshold)"
  elif [ "$VERBOSE" = true ]; then
    echo "✅ OK: $file ($lines lines, type: $desc)"
  fi
done | sort
```

---

## 🧪 Function Complexity - Also Needs Type Awareness

**Current**: All functions judged by same standard (50/75/100 lines)

**Should have**:
- API route handlers: Can be longer (60-80 lines) - orchestration
- Test functions: Can be longer (80-100 lines) - setup/assertions
- Database queries: Should be shorter (40-60 lines) - focused
- Utility functions: Must be short (20-40 lines) - single purpose
- Main/entry points: Can be longer (80-100 lines) - startup logic
- Signal classifiers: Moderate (60-80 lines) - decision trees
- Narrative generators: Can be longer (70-90 lines) - text assembly

---

## 📈 Dynamic Threshold Learning (Future Enhancement)

Instead of hardcoded thresholds, learn from codebase:

```bash
# Analyze actual distribution per file type
# Set thresholds at 75th percentile (most files pass, outliers flagged)
# Update thresholds quarterly based on codebase evolution
```

---

## ✅ Action Items

**Immediate (this session)**:
- [ ] Implement comprehensive file type catalog in check-file-sizes.sh
- [ ] Add function complexity type awareness
- [ ] Test on current codebase
- [ ] Commit improvements

**Short term**:
- [ ] Add documentation file size checks (markdown)
- [ ] Frontend file categorization
- [ ] Script file checks

**Long term**:
- [ ] Dynamic threshold learning from codebase
- [ ] Complexity metrics beyond line count (cyclomatic, cognitive)
- [ ] Historical trend tracking

---

**Status**: Identified gaps, ready to implement
**Priority**: MEDIUM-HIGH (affects quality of detection)
**Effort**: 2-3 hours for comprehensive catalog
