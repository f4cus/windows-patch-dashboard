# Windows Patch Dashboard

Windows Patch Dashboard turns public Microsoft Patch Tuesday information into a concise, traceable monthly report for Windows Server 2012 ESU and newer, plus supported Windows 11 branches. The repository is intentionally static: a Python collector will produce versioned JSON, while a React application reads that data without a database, persistent API, Azure service, or runtime AI dependency.

Phase 0 and Phase 1 provide the project foundation, validate the monthly-report contract, and render the manually reviewed August 2026 golden fixture. They do not collect data from Microsoft or implement the final dashboard design.

## Prerequisites

- Python 3.12
- Node.js 22 with npm

Run commands from the repository root. On Windows PowerShell, create the environment and install the collector's development dependencies with:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e "collector[dev]"
```

Run the Python tests, lint, type checks, and JSON/schema validation with:

```powershell
.venv\Scripts\python -m pytest collector/tests
.venv\Scripts\python -m ruff check collector
.venv\Scripts\python -m ruff format --check collector
.venv\Scripts\python -m mypy collector/src
.venv\Scripts\python -m windows_patch_collector.validation
```

Install and verify the frontend with:

```powershell
cd frontend
npm ci
npm run lint
npm run format:check
npm run typecheck
npm run build
```

For local development, after installing dependencies:

```powershell
cd frontend
npm run dev
```

Vite prints the local URL. The development page reads `data/fixtures/2026-08.json` at build time; it makes no browser request to Microsoft.

On macOS or Linux, replace `.venv\Scripts\python` with `.venv/bin/python`. The npm commands are unchanged.

## Repository layout

```text
.
|-- frontend/              React, Vite, and TypeScript application
|-- collector/             Python package and tests
|   |-- src/
|   `-- tests/
|-- data/
|   |-- fixtures/          Manually reviewed development inputs
|   |-- reports/           Future generated monthly reports
|   `-- schema/            JSON Schema contract
|-- design/                Visual direction and references
|-- docs/                  Product and architecture decisions
`-- .github/workflows/     Continuous integration
```

## Data contract

`data/schema/monthly-report.schema.json` is the report contract. The validator checks every JSON document under `data/fixtures/` and `data/reports/`. The August 2026 file is a manual golden fixture used for development and tests; it is not evidence that a future collector is correct.

Production reports must retain official Microsoft provenance. Missing or unverifiable data remains explicit and must never be rewritten as "no known issues" or supplied with an inferred KB number. See `AGENTS.md` and `docs/decisions.md` before changing data behavior.

## License

This project is available under the MIT License. See `LICENSE`.
