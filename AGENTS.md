# Agent Instructions

Before modifying code or data, read in this order:

1. `PROJECT.md`
2. `DECISIONS.md`
3. `AGENTS.md`
4. the relevant parts of `RUNBOOK.md`

Then inspect only the code, tests, data, and workflow files directly related to the requested change.

## Core Principles

- Prefer small, incremental, verifiable changes.
- Apply the 80/20 principle: solve the concrete requirement before improving adjacent code.
- Keep scope and token usage narrow; inspect only what is needed to make a safe change.
- Do not redesign working components without a concrete requirement.
- Do not solve unrelated technical debt.
- Do not introduce abstractions for hypothetical future requirements.
- Do not add dependencies unless the requested behavior clearly requires them.
- Preserve existing behavior unless the task explicitly requires changing it.
- Do not change an active decision in `DECISIONS.md` silently. Identify the conflict before implementation.
- Never invent Microsoft KBs, dates, fixes, known issues, product mappings, supersedence, source URLs, or provenance.
- Prefer a safe failure/`unknown` state over fabricated certainty.

## Before Making Changes

1. Identify the affected component: collector, data contract, frontend, automation, or deployment.
2. Read the relevant implementation and focused tests.
3. Trace the data flow through the boundary being changed.
4. Check `DECISIONS.md` for constraints that apply.
5. Define the smallest files/tests needed for the change.
6. For state-dependent bugs, inspect the current report/workflow/code state before proposing a fix.

Do not re-review unrelated architecture that is already documented and working.

## Coding Rules

### Python / Collector

- Package code lives under `collector/src/windows_patch_collector/`; tests live under `collector/tests/`.
- Python package support is `>=3.11`; CI currently runs Python 3.12.
- Follow Ruff configuration in `collector/pyproject.toml`: 100-character line length and the configured `E`, `F`, `I`, `UP`, `B`, `SIM` rules.
- mypy is strict for `collector/src`.
- Keep Microsoft HTTP access behind `MicrosoftHttpClient`/source adapters.
- Keep source-specific parsing separate from report normalization.
- Use the existing small typed dataclasses/models at source boundaries rather than passing unstructured source payloads through the collector.
- Preserve bounded HTTP retries/timeouts and explicit errors; do not add infinite retries.
- Validate before writing reports and preserve atomic output behavior.
- Do not hardcode KB-specific exclusions to resolve source ambiguity unless the requirement explicitly provides a durable official rule.

### TypeScript / React

- Frontend code lives under `frontend/src/`.
- TypeScript is strict, no-emit, ES2022, with unused locals/parameters and switch fallthrough checks enabled.
- Use existing React functional components/hooks and local modules; no component framework is currently used.
- Keep the browser static: no Microsoft scraping/API calls from frontend code.
- Monthly JSON is loaded through the existing `model.ts` / `loadMonthlyReport.ts` / `reportCatalog.ts` boundary.
- Keep the five canonical Report Mode columns and deterministic report rendering unless the task explicitly changes the product contract.
- PNG export remains client-side through the existing report element/export helper.

### Data / Contract

- `data/schema/monthly-report.schema.json` is the JSON contract; Python semantic checks add cross-record rules.
- Generated production reports belong in `data/reports/YYYY-MM.json`; fixtures belong in `data/fixtures/`.
- `data/fixtures/2026-08.json` is the single manual golden fixture and is not production provenance.
- Preserve official-source provenance for generated/partial/verified records.
- OOB is an update type, not a known-issue status.
- `NO PUBLICADO` and supersedence semantics must continue to pass schema and cross-record validation.
- Contract changes are high-impact because Python and TypeScript both validate the boundary.

## Testing and Validation

Run focused tests while iterating, then run the relevant validation set once before completion. Do not rerun the entire suite repeatedly without a reason.

### Python / Collector

From the repository root with the development environment installed:

```powershell
.venv\Scripts\python -m pytest collector/tests
.venv\Scripts\python -m ruff check collector
.venv\Scripts\python -m ruff format --check collector
.venv\Scripts\python -m mypy collector/src
.venv\Scripts\python -m windows_patch_collector validate
```

For a narrow collector change, run the relevant pytest file/test first, then the full Python set once.

### Frontend

```powershell
cd frontend
npm ci
npm run format:check
npm run lint
npm run typecheck
npm test
npm run build
```

Keep this local validation sequence aligned with the frontend CI job.

### Data

```powershell
.venv\Scripts\python -m windows_patch_collector validate
```

This validates JSON Schema plus repository semantic rules for all fixture/report JSON files.

### Repository Diff

Before completion, run:

```powershell
git diff --check
```

## Definition of Done

A task is done only when:

- the requested behavior is implemented;
- relevant focused tests pass;
- the appropriate Python/frontend/data validation passes;
- frontend build passes when frontend/data loading is affected;
- no unrelated files or behavior were changed;
- new meaningful behavior has focused test coverage when practical;
- any blocked check is reported explicitly rather than implied successful.

## Failure / Retry Policy

Use a bounded loop:

`IMPLEMENT → TEST → ANALYZE FAILURE → FIX → TEST`

- Start with the failing or focused test, not repeated full-suite runs.
- Do not retry the same failing approach indefinitely.
- After several materially different attempts fail, stop and report the blocker with the exact command/error and what has been ruled out.
- Do not hide upstream Microsoft/source ambiguity by weakening validation.

## Dangerous / High-impact Changes

Call out the impact before changing:

- `data/schema/monthly-report.schema.json` or fields consumed across Python/TypeScript;
- OS identity/product mapping or canonical ordering;
- source selection/trust/fallback rules;
- report generation, atomic writes, semantic reconciliation, or provenance;
- `.github/workflows/*.yml`, workflow permissions, automated commits, scheduling, or deployment;
- `frontend/vite.config.js` / GitHub Pages base-path behavior;
- major dependencies or framework versions;
- broad code deletion or migration.

Do not proceed with a documented architectural conflict as if it were a routine refactor.

## Documentation Rule

Update root harness documents only when the change materially changes:

- architecture or product boundaries (`PROJECT.md`);
- an important technical decision (`DECISIONS.md`);
- agent working/validation rules (`AGENTS.md`);
- setup, operation, deployment, or troubleshooting procedures (`RUNBOOK.md`).

Do not update harness documentation for trivial UI copy, formatting, or isolated implementation details.
