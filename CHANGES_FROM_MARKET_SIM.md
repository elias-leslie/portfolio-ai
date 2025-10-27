# Changes from Market-Sim

This document tracks how Portfolio AI differs from the market-sim project it was bootstrapped from.

**Last Updated**: 2025-10-27

---

## Key Differences

### 1. **Execution Model**
- **Market-Sim**: Docker Compose orchestration
- **Portfolio-AI**: Native execution (Python venv + npm)
- **Why**: Simpler setup, faster development iteration for AI-focused platform

### 2. **File Size Guidelines** ✅ Updated
- **Market-Sim CLAUDE.md**: Still references "300-line file limit" (outdated)
- **Market-Sim DEVELOPMENT.md**: Uses 500/800 guidelines (current)
- **Portfolio-AI**: Updated to 500 soft / 800 hard limits everywhere
- **Rationale**: Real-world testing showed 300 was too restrictive

### 3. **Project Structure**
```
Market-Sim:                    Portfolio-AI:
├── app/                       ├── backend/app/
├── web/                       ├── frontend/
├── web-api/                   └── (no separate API - unified in backend/)
├── data/
└── config/
```

### 4. **Technology Stack**

| Component | Market-Sim | Portfolio-AI |
|-----------|------------|--------------|
| Backend | Python 3.11+ | Python 3.11+ |
| API Framework | FastAPI | FastAPI |
| Storage | DuckDB | DuckDB |
| Frontend | Next.js 14 | Next.js 14 |
| UI Components | shadcn/ui | shadcn/ui |
| Data Sources | Polygon, FRED, News | yfinance, Polygon (backup), FRED, News |
| AI | N/A | Anthropic Claude API |

### 5. **Data Sources**
- **Market-Sim**: Polygon primary, multi-source failover pattern
- **Portfolio-AI**: yfinance primary, Polygon backup (simpler for personal portfolios)
- **Shared**: FRED for economic data, Google News RSS for sentiment

### 6. **AI Integration** (New in Portfolio-AI)
- Discovery Agent: Scans market for general opportunities
- Portfolio Analyzer Agent: Generates personalized ideas
- Cost tracking: $0.50 per-run limit
- Execution tracking: All tool calls logged to DuckDB

### 7. **Database Schema**
- **Market-Sim**: Focus on multi-source market data ingestion
- **Portfolio-AI**: Additional tables for portfolio management, AI agents, and ideas
  - portfolio_accounts
  - portfolio_positions
  - user_preferences
  - agent_runs
  - agent_ideas
  - agent_tool_calls
  - validation_results

### 8. **Development Workflow**
- **Shared**: Same `.claude/commands/` slash commands (/plan_it, /task_it, /do_it, etc.)
- **Shared**: Same AI Dev Tasks workflow
- **Shared**: Same pre-commit checklist (lint, test, type-check)
- **Difference**: Portfolio-AI has simpler setup (no Docker)

### 9. **Documentation Structure** (Identical)
Both use the same 6 core docs:
- ARCHITECTURE.md
- DEVELOPMENT.md
- SETUP.md
- OPERATIONS.md
- API_REFERENCE.md
- REFACTOR_STATUS.md

---

## Inherited Components (Unchanged)

### From Market-Sim Storage Layer
- `app/storage/connection.py` - DuckDB connection manager
- `app/storage/metadata.py` - Metadata tracking
- `app/storage/queries.py` - Query helpers
- `app/storage/ingestion.py` - Data ingestion patterns

### From Market-Sim Data Sources
- `app/sources/fred.py` - FRED API integration
- `app/sources/news.py` - Google News RSS
- `app/sources/multi_source_fetcher.py` - Failover pattern

### From Market-Sim Dev Infrastructure
- `.claude/commands/` - All 5 slash commands
- `scripts/lint.sh` - Code quality checks (adapted for native Python)
- `scripts/validate-commands.sh` - Slash command validation
- `pyproject.toml` - ruff/mypy configuration
- `.gitignore` - Ignore patterns

---

## Configuration Differences

### Python Dependencies
**Added in Portfolio-AI**:
- `anthropic>=0.25.0` - AI agent API
- `yfinance==0.2.66` - Primary price data source
- `feedparser>=6.0.11` - News RSS parsing

**Same as Market-Sim**:
- FastAPI, uvicorn, pydantic
- DuckDB, polars, pandas
- pytest, ruff, mypy

### Frontend Dependencies
**Same core stack**:
- Next.js 14
- TypeScript
- Tailwind CSS
- shadcn/ui

**Added in Portfolio-AI**:
- @tanstack/react-query
- @tanstack/react-table

---

## File Size Guidelines Evolution

### History
1. **Original**: 300-line limit (too restrictive)
2. **Market-Sim Testing**: Discovered 300 lines caused artificial splits
3. **New Guidelines**: 500 soft / 800 hard limits
4. **Market-Sim Status**: DEVELOPMENT.md updated, CLAUDE.md not yet updated
5. **Portfolio-AI Status**: All documents updated to 500/800 ✅

### Exceptions (Both Projects)
- Schema files (*_schema.py, *_ddl.py): No limit
- Generated code: No limit
- Test files: 600-line limit
- CLI command files: 600-line limit

---

## Commands Comparison

### Backend Startup
**Market-Sim**:
```bash
docker compose up --build api
```

**Portfolio-AI**:
```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload
```

### Testing
**Market-Sim**:
```bash
docker compose run --rm ingestor pytest tests/ -v
```

**Portfolio-AI**:
```bash
cd backend
source .venv/bin/activate
pytest tests/ -v
```

### Linting
**Both** (run from repo root):
```bash
./scripts/lint.sh
```

---

## Migration Notes

If moving code from market-sim to portfolio-ai:

1. **Adapt imports**: Change `app/` to `backend/app/` if needed
2. **Remove Docker**: Convert Docker commands to native execution
3. **Update data sources**: Use yfinance primary pattern instead of Polygon
4. **Add AI integration**: Implement agent system if feature needs AI
5. **Update file size references**: Use 500/800 instead of 300
6. **Test thoroughly**: Run full test suite after migration

---

## Future Considerations

### Potential Backports to Market-Sim
- yfinance integration (useful for portfolios)
- 500/800 file size updates to CLAUDE.md
- AI agent patterns (if market analysis benefits from LLMs)

### Portfolio-AI Enhancements
- More sophisticated agent orchestration
- Portfolio optimization algorithms
- Tax-loss harvesting strategies
- Multi-account rebalancing

---

**Status**: Portfolio-AI is a standalone project with different goals but shared infrastructure patterns from market-sim.
