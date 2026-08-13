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
- Security data: Microsoft MSRC CVRF.
- KB article data: official Microsoft Support articles.
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
2. MSRC CVRF / official Microsoft security data.
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
- `oob`: an out-of-band update exists/replaces or materially updates the normal monthly state.
- `not-published`: expected monthly update was not published / not available.
- `unknown`: collector cannot verify the state; must not be converted into `none`.

## Phase 1 data-contract refinements
- The pre-production `1.0.0` schema now requires normalized `os.version`, `os.channel`, and
  `supersededBy` fields. Supported Windows Server identities are exact tuples; Windows 11
  versions use ordered `<year>H<half>` labels and may combine branches with `/`. The August
  fixture already satisfied these requirements, so its source prose and values were not changed.
- `NO PUBLICADO` is valid only with a null release date, null supersedence, and
  `knownIssuesStatus: not-published`. Conversely, a published KB cannot use `not-published`.
  This prevents missing data from being presented as `none`.
- Every update in `generated`, `partial`, or `verified` reports requires at least one source.
  `manual-golden-fixture` records may omit `sources` or keep an empty array because the fixture is
  test input rather than collector output. Source types are coupled to their official Microsoft
  domains so a third-party URL cannot be mislabeled as authoritative provenance.
- OOB history is additive: the monthly record points to a same-report OOB record through
  `supersededBy`; the target must have `updateType: oob`. Standalone or dangling OOB links fail
  semantic validation.
- Persisted updates must use canonical server-first order. Windows 11 records follow from the
  oldest branch represented in their version label to the newest, with deterministic tie-breakers.
- These refinements retain schema version `1.0.0` because the original file was an unimplemented
  bootstrap draft rather than a published contract. Future breaking changes must increment it.
- The `manual-golden-fixture` status is reserved for `data/fixtures/2026-08.json`; its month,
  Patch Tuesday date, and null generation timestamp are fixed by the schema. Files at any other
  fixture or report path must use a production status and preserve official provenance.
- Windows 11 display names are derived from their normalized version, combined branches must be
  unique and ordered oldest-to-newest, and the V1 channel is null. The `esu` update type is valid
  only for an OS whose normalized channel is `ESU`.
- Supersedence resolves to one later OOB record with the same normalized OS identity. Cross-OS,
  ambiguous, cyclic, and backward-dated links are invalid, as are duplicate OS-and-KB records.
- Report completeness remains future collector policy. Phase 1 deliberately does not impose an
  `updates` minimum or infer that a structurally valid report covers every supported branch.
