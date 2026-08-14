# Windows Patch Dashboard

## Product

Windows Patch Dashboard turns official Microsoft Patch Tuesday information into a concise, traceable monthly report for Windows Server 2012 ESU and newer, plus supported Windows 11 branches. A deterministic Python collector produces validated, versioned JSON; a static React application presents it without a database, backend API, or runtime AI dependency.

## Screenshot / usage

Interactive Mode provides month selection, individual operating-system selection, official provenance links, light/dark mode, and client-side PNG export. Report Mode is the primary shareable artifact: it removes application controls and presents the filtered report in exactly five canonical columns. The active OS selection and theme carry into Report Mode and the exported PNG; export is disabled for an empty selection.

All fonts and report rendering are local to the browser. No external screenshot or rendering service receives the report.

## Data sources

Production reports use only official Microsoft content:

- Microsoft Security Response Center CVRF for monthly update discovery and KB-to-product relationships;
- MSRC CSAF as a tested, complementary structured-source boundary;
- official Microsoft Support KB articles for highlights, fixes, and known issues.

Microsoft Support `es-ES` content is preferred per KB, with the official `en-US` article used only when Spanish content cannot be retrieved and parsed reliably. No third-party content populates production reports. The source evaluation and August comparison are documented in [docs/phase-3-source-evaluation.md](docs/phase-3-source-evaluation.md) and [docs/phase-3-august-2026-comparison.md](docs/phase-3-august-2026-comparison.md).

## Architecture

```text
MSRC + Microsoft Support
          →
Python collector
          →
validated JSON in Git
          →
React + Vite
          →
GitHub Pages
```

The frontend bundles the validated report catalog at build time and never calls or scrapes Microsoft. Git history is the audit trail for production report changes.

## Local development

Prerequisites are Python 3.12 and Node.js 22 with npm. From the repository root on Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e "collector[dev]"
.venv\Scripts\python -m pytest collector/tests
.venv\Scripts\python -m ruff check collector
.venv\Scripts\python -m ruff format --check collector
.venv\Scripts\python -m mypy collector/src
.venv\Scripts\python -m windows_patch_collector.validation

cd frontend
npm ci
npm run format:check
npm run lint
npm run typecheck
npm test
npm run build
npm run dev
```

Vite prints the local URL and serves from `/`. On macOS or Linux, replace `.venv\Scripts\python` with `.venv/bin/python`; npm commands are unchanged.

## Collector

Run one explicit month from the repository root:

```powershell
.venv\Scripts\python -m windows_patch_collector collect --month 2026-08
```

The month format is strict `YYYY-MM`. The collector validates and atomically writes `data/reports/YYYY-MM.json`; an existing valid report remains intact if collection or validation fails. Generated reports take precedence over same-month fixtures in the frontend catalog.

## Automation

`.github/workflows/pages.yml` deploys a validated frontend artifact on every push to `main` without performing live collection. It also runs daily at 20:17 UTC and supports manual dispatch with an optional `YYYY-MM` input. Scheduled or month-less manual runs select the most recent Patch Tuesday that has already occurred, so dates before the current month's Patch Tuesday continue to refresh the preceding report.

Refresh runs collect and validate first, then compare reports while ignoring only `generatedAt` and source `retrievedAt`. Timestamp-only refreshes restore the committed file and create no commit. Meaningful changes stage only the expected monthly report, commit with `github-actions[bot]` using `GITHUB_TOKEN`, and build/deploy that exact commit in the same workflow run. The Pages artifact contains only `frontend/dist`; no `gh-pages` branch is used.

To enable deployment, set the repository Pages source to **GitHub Actions** and allow workflow **Read and write permissions** for `GITHUB_TOKEN`. If `main` is protected, its rules must also permit the Actions bot's narrowly scoped report commit or the scheduled refresh will fail safely before deployment. GitHub may disable scheduled workflows on inactive public repositories; they can be re-enabled in the Actions tab.

## Trust / limitations

- Official Microsoft sources only; provenance is retained per production record.
- KB numbers, dates, fixes, issues, and supersedence are never inferred.
- Missing or ambiguous evidence remains `unknown` or `not-published`, never silently becomes `none`.
- Extraction and aggregation are deterministic; Spanish Support is preferred with official English fallback.
- Generalized OOB discovery is intentionally conservative and requires explicit official evidence.
- The static V1 provides report reading and export, not device inventory, patch compliance, accounts, analytics, or a vulnerability-management backend.

The contract is [data/schema/monthly-report.schema.json](data/schema/monthly-report.schema.json). The August fixture is a manual test input, not production-source evidence. See [AGENTS.md](AGENTS.md) and [docs/decisions.md](docs/decisions.md) before changing data behavior.

## License

The project is licensed under the [MIT License](LICENSE). Bundled font and vendored-tool notices are preserved separately in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
