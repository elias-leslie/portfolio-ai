# Portfolio AI

Portfolio AI is a self-hosted workspace for households reviewing money, investments, and retirement decisions. It brings financial records, explicit calculations, source evidence, and optional agent explanations into one place.

## What it does

- Tracks accounts, positions, tax lots, transactions, allocation drift, and watchlist signals.
- Reviews monthly household cash flow, categories, planned funding, and agreed changes.
- Models retirement scenarios and household card economics from saved inputs and sourced terms.
- Captures receipts and shelf tags with scoped household access and upload retry.
- Runs scheduled ingestion/research workflows and exposes a read-only signal MCP server.

## Current scope

The app combines household finance and investment research. Calculations and saved assumptions are distinct from agent judgments. Missing quote, flow, basis, or document evidence limits the results. Recording a decision does not place a trade. Analysis software does not establish an investment outcome or replace the user's financial judgment.

## Getting started

For a standalone Docker installation, use Docker Engine with Compose:

```bash
cp .env.example .env
./scripts/generate-hatchet-dev-token.sh .env
docker compose up -d --build
```

Open <http://localhost:3000>; the API is on port 8000. Compose supplies database and Redis service URLs. Native installation requires Python 3.13, Node.js 20–24, uv, the pinned pnpm version, and backing services; follow the [project guide](docs/project-guide.md#native-standalone).

## Runtime, data, and integrations

FastAPI and Next.js use PostgreSQL, Redis, and Hatchet workflows. Market/news sources and optional keyed providers feed research; Agent Hub companion chat/review is optional. Provider-dependent features show unavailable or degraded status when configuration is absent.

Household uploads and PostgreSQL must be backed up together. The complete backup/restore scripts preserve their relationship and exclude the encryption secret, which requires separate escrow. See [backup and restore](docs/project-guide.md#runtime-backup-and-restore) before operating on financial data. Keep credentials, statements, exports, and database dumps out of public demos and source control.

## Development and verification

```bash
./scripts/test-all.sh
```

The public helper and [manual gates](docs/project-guide.md#testing-linting-types-and-build) cover backend tests/lint/types and frontend tests/types/build. Backup changes also require the isolated backup/restore drill. Optional integrations need their own runtime evidence.

## Documentation

- [Project guide](docs/project-guide.md): installation, configuration, backup/restore, APIs, MCP, and tests.
- [Backend package](backend/pyproject.toml) and [frontend guide](frontend/README.md).
- [Security reporting](SECURITY.md), [license](LICENSE), and [notice](NOTICE).
