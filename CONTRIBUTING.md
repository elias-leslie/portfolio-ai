# Contributing

Thanks for your interest in improving Portfolio AI.

## Before you start

- Open an issue or start a discussion before larger changes.
- Keep changes focused and avoid mixing unrelated work.
- Expect review to be best-effort rather than immediate.
- No CLA is required at this time.

## Development

- **Actions belongs only in the top bar.** Keep its queue, counts, and quick-answer controls inside the header popover. Do not add action cards, a "Needs attention" section, or a duplicate task list to Today's page content. This is an explicit, repeated user preference. Preserve the CoreRoutes and runtime Actions regression checks when changing Today or navigation.

- Use the documented setup in `README.md`.
- Keep secrets out of the repo. Use local environment files and placeholders only.
- Add or update tests when behavior changes.
- Run the relevant quality checks before opening a PR.
- Grounding checks in `backend/scripts/evaluate_financial_grounding.py` are offline by default. Use `--live` only intentionally; `--only` limits the cases/routes sent. The evaluator batches synthetic facts, disables application retries, fallback, tools and memory, and records the actual serving model and reported tokens. Never substitute real financial records into these fixtures. A pass is regression evidence, not a claim that a model cannot hallucinate.

## Pull requests

- Describe the user-visible impact and any operational risk.
- Note schema, dependency, or environment changes explicitly.
- By submitting a contribution, you agree that it may be distributed under the repository license.
