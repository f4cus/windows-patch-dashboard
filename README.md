# Windows Patch Dashboard

Windows Patch Dashboard turns public Microsoft Patch Tuesday information into a concise, traceable monthly report for Windows Server 2012 ESU and newer, plus supported Windows 11 branches. The repository is intentionally static: a Python collector produces versioned JSON, while a React application reads that data without a database, persistent API, Azure service, or runtime AI dependency.

Phase 3 adds the local Microsoft collector. It uses official public sources over regular HTTP and writes validated reports directly into the static data catalog; no secret, account, browser automation, backend, database, cloud service, or runtime AI dependency is involved.

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

## Collect a monthly report

From the repository root, with the collector installed in `.venv`, run:

```powershell
.venv\Scripts\python -m windows_patch_collector collect --month 2026-08
```

The month is strict `YYYY-MM`. The collector calculates that month's second Tuesday, discovers supported normal security updates in the official monthly MSRC CVRF document, and then reads each verified KB's Microsoft Support article. It validates and atomically writes `data/reports/YYYY-MM.json`; an existing report remains intact if collection or validation fails. Generated reports take precedence over fixtures in the frontend catalog.

CVRF is the V1 monthly discovery source because it provides one official monthly document with the required KB-to-product relationships. Microsoft Support is authoritative for article changes, documented fixes, and known issues. The public MSRC CSAF distribution was evaluated and has a tested parser boundary, but its per-CVE advisory layout is complementary rather than the V1 monthly discovery path. See `docs/phase-3-source-evaluation.md` for evidence and limitations.

Normal unit tests are offline and use minimal captured-shape responses or HTTP mocks. A live collection can fail because Microsoft is unavailable, a public response is transiently throttled, official sources conflict, or source markup changes. HTTP requests use bounded retries for transient failures. A per-article Support failure produces an explicit `unknown`/unavailable partial report when the contract permits; a structured-source failure, official date conflict, ambiguous monthly KB, or validation failure stops the run without replacing the output file.

Install and verify the frontend with:

```powershell
cd frontend
npm ci
npm run lint
npm run format:check
npm run typecheck
npm test
npm run build
```

For local development, after installing dependencies:

```powershell
cd frontend
npm run dev
```

Vite prints the local URL. The application discovers monthly JSON files under `data/fixtures/` and `data/reports/` at build time. A generated report for a month takes precedence over a fixture for the same month. The browser makes no request to Microsoft.

## V1 report experience

Interactive Mode provides a locally derived month selector, an operating-system checklist based on the current report, a light/dark theme toggle, a known-issue status legend, per-update official source links when present, Report Mode, and client-side PNG export. All operating systems are selected initially; individual selection, select-all, and clear actions filter the interactive table, Report Mode, and export consistently.

Report Mode is the primary artifact. It hides application controls and provenance disclosures while preserving the active theme, the four public metadata fields (Patch Tuesday, Generado, Alcance, and Registros), and exactly five canonical columns: KB, OS, Vulnerabilidades / Cambios Clave, Issues Resueltos, and Problemas Conocidos. `Generado` is the date on which the application rendered the visual report. Press `Escape` to return to Interactive Mode.

`Exportar PNG` captures the filtered report surface in the active theme at 2× pixel density. The export is generated locally in the browser with bundled fonts and no external rendering service. Export is disabled when no operating system is selected. `NO PUBLICADO`, known-issue status, and independent OOB supersedence indicators remain visible in the exported artifact.

On macOS or Linux, replace `.venv\Scripts\python` with `.venv/bin/python`. The npm commands are unchanged.

## Repository layout

```text
.
|-- frontend/              React, Vite, and TypeScript application
|-- collector/             Microsoft collector, normalization, validation, and tests
|   |-- src/
|   `-- tests/
|-- data/
|   |-- fixtures/          Manually reviewed development inputs
|   |-- reports/           Generated monthly reports
|   `-- schema/            JSON Schema contract
|-- design/                Visual direction and references
|-- docs/                  Product and architecture decisions
`-- .github/workflows/     Continuous integration
```

## Data contract

`data/schema/monthly-report.schema.json` is the report contract. The validator checks every JSON document under `data/fixtures/` and `data/reports/`. The August 2026 file is a manual golden fixture used for development and tests; it is not evidence that a future collector is correct.

Production reports must retain official Microsoft provenance, including non-null ISO date-times in report-level `generatedAt` and every source-level `retrievedAt`. The manual golden fixture alone uses `generatedAt: null`. Known-issue state is independent from OOB supersedence, and ESU is represented by `os.channel: "ESU"`, not an update type. Missing or unverifiable data remains explicit and must never be rewritten as "no known issues" or supplied with an inferred KB number. See `AGENTS.md` and `docs/decisions.md` before changing data behavior.

## License

This project is available under the MIT License. See `LICENSE`. Notices for vendored third-party material are listed in `THIRD_PARTY_NOTICES.md`.
