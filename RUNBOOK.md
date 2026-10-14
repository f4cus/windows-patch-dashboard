# Windows Patch Dashboard Runbook

This runbook contains the verified setup, validation, operation, deployment, and troubleshooting paths for the current repository. Commands assume Windows PowerShell unless noted.

## Prerequisites

Verified repository requirements:

- Git.
- Python `>=3.11`; repository CI and README use Python 3.12.
- Node.js 22 with npm for the frontend/CI path.

No database, Azure account, application secret, PAT, or runtime AI service is required for local application/collector operation.

## Local Setup

From the repository root.

### Collector / Python

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e "collector[dev]"
```

macOS/Linux equivalent for the interpreter path: `.venv/bin/python`.

### Frontend

```powershell
cd frontend
npm ci
cd ..
```

## Running Locally

### Collector

Collect one explicit report month:

```powershell
.venv\Scripts\python -m windows_patch_collector collect --month 2026-08
```

The month must be strict `YYYY-MM`.

Resolve the automatic target month (current month opens at D 14:15 ART; otherwise the previous month):

```powershell
.venv\Scripts\python -m windows_patch_collector target-month
```

Validate an explicit month without collecting it:

```powershell
.venv\Scripts\python -m windows_patch_collector target-month --month 2026-08
```

### Frontend

```powershell
cd frontend
npm run dev
```

Vite prints the local URL. Local base path is `/`.

### Create a client PDF

1. In Interactive Mode, select the report month and operating systems. Use all systems for a complete monthly document.
2. Open **Client Report** and review its OS and KB sections. Monthly security and OOB KBs remain separate.
3. Choose **Imprimir / Guardar PDF**, then select the browser's PDF destination with A4 portrait paper. Disable browser headers and footers if the PDF must contain only report content.

The browser produces the PDF from HTML, preserving selectable text and usually preserving official source links. Client Report excludes dashboard navigation and personal attribution. The page title is `Microsoft Patch Tuesday - YYYY-MM` while this mode is open; browser-specific author metadata cannot be controlled by the application.

## Testing

### Python tests

```powershell
.venv\Scripts\python -m pytest collector/tests
.venv\Scripts\python -m ruff check collector
.venv\Scripts\python -m ruff format --check collector
.venv\Scripts\python -m mypy collector/src
```

### Frontend tests

```powershell
cd frontend
npm run format:check
npm run lint
npm run typecheck
npm test
npm run build
```

### Data validation

From the repository root:

```powershell
.venv\Scripts\python -m windows_patch_collector validate
```

Equivalent compatibility entry point:

```powershell
.venv\Scripts\python -m windows_patch_collector.validation
```

### Full validation

No single repository command currently wraps the complete Python + frontend validation set. Run the Python/data commands above, then the frontend commands. Finally:

```powershell
git diff --check
```

## Build

Normal local production build:

```powershell
cd frontend
npm ci
npm run build
```

Output: `frontend/dist/`.

GitHub Pages builds set `PAGES_BASE_PATH`; `frontend/vite.config.js` normalizes it to a trailing-slash Vite `base`. Local builds default to `/`.

## Data Refresh / Collector

### Sources consumed

Production collection currently uses:

- monthly MSRC CVRF: `https://api.msrc.microsoft.com/cvrf/v3.0/cvrf/<YYYY-Mon>`;
- Windows message center: `https://learn.microsoft.com/en-us/windows/release-health/windows-message-center` for dated OOB announcements;
- Microsoft Support KB articles, preferring `es-ES` and falling back to `en-US`;
- official Windows Server/Windows 11 release-information indexes on Microsoft Learn,
  used only to locate linked Support articles when the locale-specific `/help/` routes fail.
  Linked articles still require HTTPS on `support.microsoft.com`, matching KB metadata,
  and the existing locale/hotpatch checks; canonical paths are never constructed from guesses;
- the CSAF parser exists and is tested, but the production monthly collector does not use a bulk CSAF collection path.

### Output

A successful collection writes:

```text
data/reports/YYYY-MM.json
```

The file is validated before an atomic replace. Collection/validation failure must leave an existing valid report intact.

### Manual refresh procedure

```powershell
.venv\Scripts\python -m windows_patch_collector collect --month 2026-08
.venv\Scripts\python -m windows_patch_collector validate
```

Review the collector output for warnings. A schema-valid report can have status `partial` when official evidence is incomplete or ambiguous.

### Semantic reconciliation

GitHub Actions preserves the pre-collection report and calls:

```powershell
.venv\Scripts\python -m windows_patch_collector reconcile-report --month 2026-08 --baseline <baseline-path>
```

It prints `true` for a substantive change and `false` when only volatile timestamps changed. This command is mainly an automation helper; normal manual collection does not need it.

## Deployment

Deployment is defined in `.github/workflows/pages.yml`.

### Triggers

- Push to `main`: validate repository data, build frontend, deploy Pages. **No live Microsoft collection** on this path.
- `workflow_dispatch`: refresh + deploy; optional strict `YYYY-MM` input.
- Schedule: adaptive around D, the dynamically calculated second Tuesday, using ART (fixed UTC-3).

| Window | ART slots | UTC slots |
| --- | --- | --- |
| D | 14:15–22:15 hourly | 17:15–23:15 on D, then 00:15 and 01:15 on D+1 |
| D+1 | 09:00–21:00 every two hours | 12:00–22:00 every two hours, then 00:00 on D+2 |
| D+2 | 09:00–21:00 every four hours | 12:00, 16:00, 20:00, then 00:00 on D+3 |
| D+3 | 09:00 and 15:00 | 12:00 and 18:00 |
| Otherwise | 15:00 daily | 18:00 daily |

The daily slot continues refreshing the previous month before the next D. UTC crons produce candidates on the relevant weekdays; `Check refresh window` filters their dates dynamically. The 18:00 UTC daily cron supplies D+1 15:00 and D+3 15:00, avoiding duplicate triggers. It is disabled on D and D+2.

The gate reads the workflow's original `created_at` through the GitHub API with `actions: read`, associates it with the latest occurrence of the triggering cron, and accepts delays up to six hours from that slot to the gate. It skips older jobs, rejects unknown crons and fails safely if the API cannot be read. There is no current-minute equality check and no replay of missed slots; GitHub can delay or drop scheduled runs ([GitHub schedule documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)). Manual dispatch bypasses the schedule gate and keeps its optional month override. Push still builds/deploys without collection.

Microsoft normally publishes monthly security updates at [10:00 Pacific on D](https://learn.microsoft.com/en-us/windows/deployment/update/release-cycle). In November 2026 that is 15:00 ART: the 14:15 attempt may precede publication. `reconcile-report --require-release` prevents automated publication before that PST/PDT boundary or without any Support-verified monthly security row. Such a run fails before commit/build/deploy and leaves the last deployed report in place; the next slot retries through the normal collector. This guard also applies to manual refresh publication and does not claim that all articles are complete at the nominal release time.

The production CLI's canonical Support URL fallback can remain insufficient when `/help/` returns 403, while a manual call supplied with prior canonical URLs can succeed. This independent resilience debt remains pending; WPD-INC-003 does not change source discovery or parsers. Required classification/verification failures still fail safely.

### Scheduled/manual refresh flow

1. Run the lightweight schedule/manual planner and resolve the requested/latest enabled month without Microsoft access or installing collector dependencies.
2. If enabled, checkout the default branch and install the collector. Disabled candidates skip refresh, build and deploy.
3. Use the planner's target month, anchored to the scheduled slot even if the runner starts later.
4. Preserve the committed report if it exists.
5. Collect official Microsoft data.
6. Validate all repository data.
7. Check the publication boundary and verified monthly evidence; then ignore only `generatedAt` / `retrievedAt` when deciding whether data changed meaningfully.
8. If substantive, stage only the expected monthly report, commit as `github-actions[bot]`, and push to the default branch with `GITHUB_TOKEN`.
9. Record the exact resulting commit SHA.
10. Validate/build the frontend from that exact state.
11. Upload only `frontend/dist` as the Pages artifact.
12. Deploy with the official Pages deployment action.

### Required GitHub repository settings

Verified from README/workflow behavior:

- Pages publishing source: GitHub Actions.
- Actions workflow permission must allow the refresh job's `GITHUB_TOKEN` to write repository contents.
- If `main` is protected, the rule must permit the automated report commit or refresh will fail.

Current branch inspection shows `main` is not protected. Future rule changes must be validated against the refresh workflow.

## Post-deployment Validation

Use this short checklist:

- `Refresh reports and deploy Pages` or the push-triggered Pages run completed successfully.
- `Validate and build Pages artifact` completed successfully.
- `Deploy GitHub Pages` completed successfully.
- Public dashboard opens at `https://f4cus.github.io/windows-patch-dashboard/`.
- Expected report month is visible.
- Expected KB/OS rows load without the `No hay informes disponibles` error.
- Interactive source links, OS filter, Report Mode, and PNG export still work when those areas were affected.
- If a refresh produced a data commit, inspect `data/reports/YYYY-MM.json` and confirm only expected report data changed.

## Troubleshooting

### Symptom: `No module named windows_patch_collector`

**Checks**

```powershell
Get-Location
.venv\Scripts\python -m pip show windows-patch-collector
```

**Likely Cause**

The package uses a `src/` layout and has not been installed into the Python interpreter being used.

**Resolution**

From repository root:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e "collector[dev]"
.venv\Scripts\python -m windows_patch_collector --help
```

Use `.venv\Scripts\python` for collector commands.

### Symptom: Collection fails with multiple normal monthly KB candidates for one OS

**Checks**

- Read the exact conflict from collector/workflow logs.
- Check whether each candidate has a successfully parsed official Microsoft Support article.
- Check its Support release date and explicit **Applies To** product list. A CVRF date
  inherited from the monthly document is not an explicit KB release date.
- Check the Support article title's package type. CVRF `Security Update` can describe
  an SSU or an ESU Monthly Rollup; a parseable article alone is not evidence of an LCU.
  Generic ESU candidates require a Support-confirmed Monthly Rollup and matching product.
  Missing classification fails collection instead of claiming `NO PUBLICADO`.
- Check whether Support explicitly labels a candidate Out-of-band in its article title.
- If an expected OOB is missing from CVRF, check the dated Windows message center announcement and its official KB link.
- Do not choose by KB number/date proximity.

**Likely Cause**

CVRF can expose more than one candidate for a normalized OS. A generic `Security Update` subtype may include an OOB; normalization uses an explicit Support article title to classify it before resolving monthly candidates. Other OOB KBs may be absent from CVRF and are discovered from dated, OS-labelled message center announcements. Multiple actual monthly candidates still require the existing tie-breaker.

CVRF can also retain KBs from earlier months without per-remediation dates. The collector
discards such a candidate only when Support verifies both its earlier release month and
the matching product. Contradictions with explicit CVRF dates or explicit Support products
remain fatal. Multiple remaining monthly candidates require exactly one Support-verified
Patch Tuesday date and product; missing applicability cannot break a tie.

**Resolution**

For a confirmed monthly plus OOB pair, retain both records and their own release dates. A supersedence link requires independent official evidence. Exclude packages explicitly identified by Support as SSU, security-only, or auxiliary. If multiple actual monthly candidates remain, exactly one Support-verified principal package with the matching Patch Tuesday date and product is selected and unverified candidates are warned about; zero or multiple verified candidates cause a deliberate conflict. Investigate official Microsoft evidence before changing classification rules.

### Symptom: Generated report status is `partial`

**Checks**

- Read collector warnings.
- Inspect records with `knownIssuesStatus: unknown` or unavailable Support content.
- Inspect failed/unverified Microsoft Support lookups.

**Likely Cause**

Collection succeeded but official evidence was incomplete, ambiguous, or not parseable under current deterministic rules.

**Resolution**

Treat `partial` as a valid fail-safe output. Fix the source parser/rule only when official evidence supports a deterministic improvement; do not relabel missing evidence as clean.

### Symptom: Scheduled/manual refresh fails before build/deploy

**Checks**

In GitHub Actions inspect `Refresh Microsoft report`, especially:

- `Check refresh window` / `Determine enabled refresh and target month`;
- `Collect official Microsoft data`;
- `Validate generated repository data`;
- `Commit substantive report update`.

A skipped refresh on a candidate outside an enabled slot is expected. A failed `Detect meaningful report changes` can indicate a pre-release attempt or missing monthly publication evidence; inspect its exact error and wait for the next slot rather than bypassing the guard.

**Likely Cause**

Collector/source conflict, validation failure, or repository write permission/protection failure.

**Resolution**

Fix the first failed step. Do not bypass collection/schema failures to force deployment. For commit failures, validate Actions read/write permissions and branch rules.

### Symptom: Push to `main` is rejected with `fetch first`

**Checks**

```powershell
git status
git fetch origin
git log --oneline --graph --decorate -8
```

**Likely Cause**

The remote `main` advanced, commonly because the scheduled workflow committed a refreshed report while local work was in progress.

**Resolution**

With a clean working tree, integrate the remote branch normally and then push:

```powershell
git fetch origin
git merge origin/main
git push origin main
```

Do not force-push merely to bypass the automated report commit.

### Symptom: Month selector has only one month

**Checks**

Inspect:

```text
data/reports/*.json
data/fixtures/*.json
```

**Likely Cause**

Only one unique `reportMonth` is bundled. A production report overrides a same-month fixture, so the August fixture + August report still produce one selectable month.

**Resolution**

Generate/commit another valid monthly report and rebuild/deploy. Do not add a free-form month to the UI without report data.

### Symptom: GitHub Pages assets fail under the project subpath

**Checks**

- Confirm the build ran through `.github/workflows/pages.yml`.
- Confirm `Configure GitHub Pages` produced `base_path` and the build received `PAGES_BASE_PATH`.
- Inspect `frontend/vite.config.js`.

**Likely Cause**

A build was produced with the wrong Vite base path or outside the Pages workflow.

**Resolution**

Use the existing Pages workflow/base-path configuration. Local `/` behavior is intentionally different from the project-site deployment base.

## Recovery / Rollback

The repository stores production report data and deployment state in Git, so a previous commit can be redeployed by reverting the offending change on `main` and pushing the revert; the push-triggered Pages workflow will validate/build/deploy that state.

For a bad automated data refresh, prefer a normal Git revert of the report commit rather than editing Git history. After reverting, note that the next scheduled refresh may reintroduce the same upstream data if the collector still considers it substantive.

A separately documented one-click Pages rollback procedure was not found.

**Current dedicated Pages rollback procedure: Unknown / Pending validation.**
