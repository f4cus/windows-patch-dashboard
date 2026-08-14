# Architecture Decision Record — V1

## Product
Working name: `windows-patch-dashboard`.

Purpose: transform public Microsoft Windows security-update information into a compact, traceable, readable monthly report suitable for interactive browsing and PNG export.

## V1 architecture
- Frontend: React + Vite + TypeScript.
- Styling: CSS/Tailwind may be used; keep the rendering deterministic.
- Design quality: Hallmark is the preferred project-scoped design skill.
- Decorative effects: Canvas UI may be used selectively, maximum one or two non-essential effects.
- Collector: Python 3.
- HTTP: httpx.
- Parsing: BeautifulSoup and/or lxml.
- Security data: MSRC CVRF is the V1 monthly discovery source. MSRC CSAF remains a tested, complementary structured-source boundary.
- KB article data: official Microsoft Support articles remain authoritative for KB highlights, fixes, and known issues.
- Persistence: versioned JSON committed to Git.
- Tests: pytest for collector/data; frontend test tooling may be added when justified.
- CI/CD and scheduler: GitHub Actions.
- Hosting: GitHub Pages.
- Database: none in V1.
- Persistent backend/API: none in V1.
- Azure dependency: none.
- Runtime LLM dependency: none.
- TanStack Charts: not in V1.
- Thinking Orbs: not in V1.
- Gooey: optional only for small micro-interactions.
- Export: PNG is primary; CSV is secondary.
- Automation: GitHub Actions performs daily/manual collection and semantic report comparison.
- Deployment: GitHub Pages receives only the Vite production artifact through official Pages actions.

## Core principles
1. Microsoft is the source of truth.
2. Never infer or fabricate KB numbers, release dates, fixes, known issues, or supersedence.
3. Missing official data must be represented explicitly as unavailable / not published.
4. Every production record must preserve provenance.
5. Data collection/normalization must be independent from presentation.
6. The frontend must not scrape Microsoft directly.
7. Git history is the first audit trail.
8. The application must work without an AI service at runtime.
9. Report Mode must remain visually stable and easy to capture/export.
10. Prefer simple, maintainable components over unnecessary infrastructure.

## Data trust hierarchy
1. Official Microsoft Support KB article.
2. MSRC CSAF, MSRC CVRF, and other official Microsoft security data.
3. Microsoft Release Health / official Microsoft documentation when used.
4. No third-party source may silently override Microsoft data.

## V1 user experience
Two modes:
- Interactive Mode: filters, month selection, status badges, source links, details.
- Report Mode: clean fixed report surface designed for PNG export; no navigation, decorative effects, or irrelevant controls.

## Status vocabulary
- `none`: Microsoft reports no known issues.
- `open`: at least one known issue remains open.
- `resolved`: a previously known issue is resolved by a later update.
- `not-published`: expected monthly update was not published / not available.
- `unknown`: collector cannot verify the state; must not be converted into `none`.

OOB is an update type, not a known-issue status. `supersededBy` records supersedence independently from known-issue state.

## Phase 1 data-contract refinements
- The pre-production `1.0.0` schema requires normalized `os.version`, `os.channel`, and
  `supersededBy` fields. Supported Windows Server identities are exact tuples; Windows 11
  versions use ordered `<year>H<half>` labels and may combine branches with `/`. Phase 1.1 keeps
  the August fixture prose unchanged while normalizing its two ESU records to
  `updateType: security`.
- `NO PUBLICADO` is valid only with a null release date, null supersedence, and
  `knownIssuesStatus: not-published`. Conversely, a published KB cannot use `not-published`.
  This prevents missing data from being presented as `none`.
- Every update in `generated`, `partial`, or `verified` reports requires at least one source.
  `manual-golden-fixture` records may omit `sources` or keep an empty array because the fixture is
  test input rather than collector output. Source types are coupled to their official Microsoft
  domains so a third-party URL cannot be mislabeled as authoritative provenance.
- OOB history is additive: the monthly record points to a same-report OOB record through
  `supersededBy`; the target must have `updateType: oob`. `knownIssuesStatus` records only
  known-issue state and is independent from supersedence, so a superseded update may still be
  `open`, `resolved`, `none`, or `unknown`. Standalone or dangling OOB links fail semantic
  validation.
- Persisted updates must use canonical server-first order. Windows 11 records follow from the
  oldest branch represented in their version label to the newest, with deterministic tie-breakers.
- These refinements retain schema version `1.0.0` because the original file was an unimplemented
  bootstrap draft rather than a published contract. Future breaking changes must increment it.
- The `manual-golden-fixture` status is reserved for `data/fixtures/2026-08.json`; its month,
  Patch Tuesday date, and null generation timestamp are fixed by the schema. Files at any other
  fixture or report path must use a production status and preserve official provenance.
- Windows 11 display names are derived from their normalized version, combined branches must be
  unique and ordered oldest-to-newest, and the V1 channel is null. ESU is an OS-channel property,
  not an update type; ESU monthly updates use `updateType: security` and `os.channel: ESU`.
- The schema can represent the historical normalized identity `Windows Server, version 23H2`.
  Canonical server order places it after Windows Server 2022 and before Windows Server 2025; the
  August 2026 golden fixture does not need a record for it.
- Supersedence resolves to one later OOB record with the same normalized OS identity. Cross-OS,
  ambiguous, cyclic, and backward-dated links are invalid, as are duplicate OS-and-KB records.
- Report completeness remains future collector policy. Phase 1 deliberately does not impose an
  `updates` minimum or infer that a structurally valid report covers every supported branch.
- Every report carries `generatedAt`: it is exactly null only for the manual August golden fixture
  and a non-null ISO date-time for generated, partial, and verified reports. Every production
  source record likewise carries a non-null ISO `retrievedAt`, while official-domain validation
  continues to bind source type to the corresponding Microsoft host.

## Phase 3 source evaluation boundary
- Phase 3 evaluated the live August 2026 MSRC CSAF and CVRF publications. CVRF is the V1 primary
  discovery source: its single monthly document provided the release metadata and repeated, exact
  KB-to-product remediation relationships needed by this report. Product and remediation parsing
  remains isolated in `sources/msrc_cvrf.py`.
- CSAF supplied detailed product trees and vendor-fix remediation links in individual CVE advisory
  documents. Its public advisory index did not provide a month-level KB/product manifest, so using
  it for complete monthly discovery would require retrieving and reconciling a large set of
  per-CVE documents. The tested `sources/msrc_csaf.py` adapter is retained as a complementary
  boundary, not silently used as report provenance.
- Microsoft Support remains authoritative for KB article changes, fixes, and known issues. Only a
  successfully parsed article is recorded as Support provenance. Missing or changed known-issue
  markup maps to `unknown`, and an official date conflict stops collection.
- Support collection requests official `es-ES` content first and falls back per KB to `en-US` when
  Spanish content is unavailable or cannot be parsed reliably; provenance records only the
  canonical locale URL whose content was actually used.
- CVRF may expose normal LCUs and hotpatch-only packages with the same generic `Security Update`
  subtype. The V1 collector verifies each CVRF KB through Microsoft Support and excludes a package
  only when the canonical official article resolves under Microsoft's `/hotpatch/` publication
  path. It does not choose between competing KB numbers by sequence or proximity.
- CVRF is required for V1 collection; the collector does not fall back to a bulk CSAF crawl. A
  CVRF failure is fatal. Individual Support failures remain explicit and yield a schema-valid
  partial report when possible.
- OOB records and links are supported when an official structured remediation explicitly labels
  the update out-of-band and provides its date and superseded KB. V1 does not infer OOB status from
  a later date and does not attempt brittle generalized OOB discovery.

## Phase 4 automation and deployment boundary

- Normal pushes to `main` validate repository data, build Vite, and deploy without performing live
  Microsoft collection. Daily and manual refreshes collect on the default branch, validate first,
  and deploy the exact resulting commit in the same workflow run.
- An omitted manual month resolves to the latest month whose deterministic Patch Tuesday has
  occurred. An explicit month must use strict `YYYY-MM` form.
- Automated change detection ignores only report `generatedAt` and source `retrievedAt`. When all
  other contract data is equal, the committed report is restored and no commit is created.
  Meaningful changes stage only `data/reports/YYYY-MM.json` and use the built-in `GITHUB_TOKEN`.
- GitHub Pages is published with the official configure, artifact-upload, and deploy actions. Vite
  receives the Pages base path during CI; local development retains `/`. The artifact is limited to
  `frontend/dist`, and no `gh-pages` branch or external deployment secret is used.
- Refresh and deployment use separate non-cancelling concurrency groups. A collection, schema, or
  build failure prevents deployment; successful data commits are not rolled back if Pages itself
  later fails.
