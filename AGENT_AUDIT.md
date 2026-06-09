# AGENT_AUDIT - portfolio-ai
_Sessions: 1 | Last run: 2026-06-08 | State: ISSUES_

## Architecture
- Stack: Python backend (FastAPI, :8000, uv-managed venv) + Next.js frontend (:3000) + Hatchet worker (`portfolio-hatchet-worker.service`) + Postgres + Redis. Managed via `st` (SummitFlow) tooling; services: portfolio-backend / portfolio-frontend / portfolio-hatchet-worker.
- Backend `backend/app/`: api, services, sources, tasks, workflows, ml, analytics, watchlist, storage. Market data via `sources/multi_source_fetcher` over cboe, yfinance, twelvedata, fmp, polygon, finnhub, alphavantage. ML via sklearn (`ml/article_quality_classifier` RandomForest, `services/story_clusterer` TfidfVectorizer).
- Worker entry `backend/app/worker.py`: registers ~50 Hatchet workflows; `worker.handle_kill = False`; ends in `os._exit(0)`.
- Frontend `frontend/`: `app/` Next routes incl. catch-all proxy routes `app/api/[...path]` + `app/health/[...path]` → backend (via `lib/upstream-proxy.proxyRequest` / `ProxyRouteContext`). `components/` (money, committee, home, market, watchlist, shared). Shared utils in `lib/formatters.ts`, `lib/utils.ts`.

## Project Tooling Notes
- Quality gate: `st check --quick --changed-only` (ruff+types+pytest+biome+tsc). Targeted tests: `st check pytest -- <paths>`. Never raw pytest/biome/tsc.
- After code change to a managed service: `st service rebuild portfolio-ai` then verify live (curl/`st browser check`).
- Tasks: `st ready`/`st task list`, `st context <id>`, `st claim`, `st done`, `st cancel -r`, `st log <id> "msg"`.
- `st done` prints a cosmetic `ERROR 404` before `PASS` (known — feedback f4e4446b).
- Biome enforces import ordering (organizeImports): aliased `@/...` sorted alphabetically, relative `./...` grouped after.

## Active Work Context
- Reviewed: task-bf3c32e0 (P1 bug, closed), 14 [TRIAGE] consolidate-duplicate tasks (triaged via 2 Explore sidecars), task-746a8e88 (P2 loky bug, investigated+deferred), code-health sidecar (clean). Feedback queue (1341 open) is ~all sf.*/ah.*/xc.* infra (out of scope for portfolio-ai); only 774dfb6f is portfolio-ai-relevant.
- Parallelism: 3 Explore sidecars used (duplicate triage x2, code-health scan).
- Triage rule learned: many auto-generated [TRIAGE] "Consolidate duplicate" tasks are FALSE POSITIVES (cross-language type pairs, diverged semantics, already-shared-via-helper, shared param names). Verify each at file:line before acting.

## Open Items
- [task-746a8e88] MEDIUM DEFERRED Investigate loky resource_tracker semaphore warning on worker restart - VERIFIED STILL LIVE (journalctl portfolio-hatchet-worker, restart 23:40:50: "6 leaked semaphore objects {/loky-*}"). Root mechanism: KillMode=control-group SIGKILLs whole cgroup (worker+loky pool+tracker) so loky POSIX sems never unlink; worker.py:176 os._exit(0) also skips finalizers. Warning is from CPython multiprocessing.resource_tracker (not loky's own self-cleaning tracker). Could NOT reproduce in isolation (plain joblib.Parallel uses loky's tracker → no warning). Benign (tracker cleans them). Blocker: needs faithful repro of the CPython-tracker path + SIGTERM-drain of loky pool before exit; not shipping a guessed worker.py change (Applied [M:c918f298],[M:1fab9af9]). Full findings in `st log task-746a8e88`.
- [household-refactors] LOW DEFERRED P2 [TRIAGE] "Refactor: ... (High line count)" tasks (task-49f71605, 6258a5a9, 7a32ad25, 6e565709, 86bded9e, 83e5b041, 08bba508, 850a9bda) - auto-generated "reduce size/nesting" refactors of large household files. Most sibling tasks already cancelled by prior sessions. Pure size-reduction with "preserve all behavior" = speculative churn (Coding Golden Rule / [M:7f639611]); high risk, low confirmed benefit. Needs human/architecture judgment on which files are genuinely unwieldy before touching.
- [task-410a5480] MEDIUM OPEN P2 feature "[TRIAGE] Jenny financial lanes integration" - feature scope, needs product judgment; not pure hygiene.
- [failed-P1s] OPEN Large P1 feature/task items in `failed` state (task-60774303, d25816b6, 1c098821, a42b5e7c, f5d4b40f) + paused task-b9a45c5e (net-worth cockpit). Large features, not session-hygiene scope; need owner/product triage.
- [774dfb6f] LOW OPEN Feedback: "Portfolio-AI fundamentals payload missing literature-standard ratios" - 1 vote; candidate enhancement to `sources/yfinance_parsers.parse_quarterly_fundamentals` / fundamentals payload.

## Completed
- [task-bf3c32e0] 2026-06-08 - P1 bug stale VIX/macro-gate: verified fix already in place+deployed (yfinance previousClose no longer masquerades as live quote; vendor quote_time threaded; macro-gate degradation + Live freshness badge). 51 tests green. Closed.
- [consolidations] 2026-06-08 - 8 real DRY consolidations done+verified (ruff/types/biome/tsc green, rebuilt, /money + / render clean console): backend calculate_sma+calculate_rsi (script imports canonical app fns); frontend formatElapsed→lib/formatters; MoneyAccountsFocus+MoneyAccountsIntent→money/types.ts; RouteContext→export ProxyRouteContext; quickActionLabel+quickActionTitle→home/quickActionHelpers.
- [false-positive-triage] 2026-06-08 - Cancelled 14 [TRIAGE] consolidate-duplicate tasks with evidence (fetch_spy_data, emit_event, AccountAccordionItem, PILLAR_WEIGHTS, PROJECT_ROOT, syncFromLocation, STATUS_DOWN, KeyEvent, NewsSentimentDetail, RecentNewsPayload, load_latest_technical, formatXAxis, YFINANCE_AVAILABLE, iso).

## Decisions
- Auto-generated [TRIAGE] consolidate-duplicate tasks: triage each at file:line; cancel false positives with evidence rather than leave noise (matches prior-session precedent of cancelling siblings).
- loky semaphore warning: benign cosmetic restart noise; do not ship an unverified worker.py shutdown change.

## Human Follow-up
- Source credentials: FMP/TwelveData/AlphaVantage entries in source_credentials are broken `{{ENCRYPTED}}` placeholders (enabled-but-failing) per task-bf3c32e0 description — supply real keys or disable those sources. (Credentials authority required.)
- Failed/paused P1 feature tasks + Jenny financial lanes feature need product/owner triage (out of hygiene scope).
