# Technical Decisions

This file records the small set of **active** decisions that would be risky to lose. `docs/decisions.md` retains longer Phase history; consult it only when historical detail is needed.

## D001 - Official Microsoft sources only

### Decision
Production report data is populated only from official Microsoft sources. MSRC CVRF is the V1 monthly discovery source. Official Microsoft Support KB articles provide article-specific changes, fixes, and known issues. The CSAF adapter remains tested and complementary, not the primary monthly discovery path.

### Context
The product needs one reliable monthly KB/product view plus article-level operational content.

### Rationale
The repository's live source evaluation found that CVRF exposes one monthly document with the KB/product remediation relationships needed by the supported scope. CSAF is distributed per CVE and has no month-level KB/product manifest in the implemented path. Microsoft Support supplies the KB article content that CVRF does not.

### Alternatives
A bulk monthly CSAF crawl was evaluated for V1 and not selected because it would require downloading and reconciling many per-CVE advisories.

### Consequences
- A CVRF collection failure is fatal for that run.
- Individual Support failures may produce an honest `partial` report.
- Third-party sources must not populate production report facts.

### Status
Active.

## D002 - Static frontend with versioned JSON boundary

### Decision
Keep collection/normalization in Python and presentation in a static React/Vite frontend. The contract between them is versioned JSON under `data/`. Do not add a database, persistent backend/API, Azure dependency, or runtime AI service for the current product scope.

### Context
The product is a public monthly reporting utility, not an account-based or transactional application.

### Rationale
Current product behavior can be served entirely from validated monthly JSON. Git provides report history/auditability, while a static frontend keeps runtime complexity low and prevents the browser from scraping Microsoft.

### Consequences
- New or changed report data appears after a build/deploy, not through browser-side live fetches.
- The frontend must never call Microsoft directly.
- Collection logic stays independent from rendering.

### Status
Active.

## D003 - Contract-first, fail-safe data integrity

### Decision
`data/schema/monthly-report.schema.json` is the report contract, supplemented by cross-record validation in Python. Generated reports require provenance and timestamps. Missing/ambiguous evidence stays explicit (`unknown`, `not-published`, or collection failure); it is never silently converted to clean data. Reports are validated before atomic replacement.

### Context
A patch dashboard is harmful if it presents guessed KBs, dates, known-issue states, or supersedence as facts.

### Rationale
The existing collector and validation layer consistently prefer an incomplete or failed run over fabricated certainty.

### Consequences
- `NO PUBLICADO` has strict semantics for expected Windows Server 2012/2012 R2 ESU monthly data.
- Invalid schema/semantics prevent the new production JSON from replacing the previous valid file.
- Source/provenance fields are part of the production contract.

### Status
Active.

## D004 - Explicit product normalization and conservative candidate resolution

### Decision
Map only supported Microsoft product aliases to normalized Windows Server/Windows 11 identities. Combine Windows 11 branches only when they share the same verified KB. If CVRF returns multiple normal monthly KB candidates for the same normalized OS, select one only when **exactly one** candidate has a successfully verified Microsoft Support article; otherwise fail with a conflict.

### Context
Microsoft structured data can contain multiple package/remediation candidates that cannot safely be distinguished by KB number alone.

### Rationale
Historical rationale for every product-mapping rule is not fully documented; the current implementation shows a deliberate policy of using a second official source as the tie-breaker rather than KB ordering or hardcoded exclusions.

### Consequences
- No "highest KB wins" or similar heuristic is allowed.
- A single unverified candidate can still produce the existing partial behavior; the tie-breaker applies only to duplicate monthly candidates.
- Windows Server, version 23H2 remains representable historically but is not in the current expected monthly server set.

### Status
Active.

## D005 - OOB history is additive and conservative

### Decision
Represent a verified out-of-band update as its own record with `updateType: oob`. The original monthly record may point to it through `supersededBy`. OOB status is independent from `knownIssuesStatus`.

### Context
An OOB release should not erase the monthly update or its known-issue history.

### Rationale
The data contract and validators explicitly preserve both records and require same-OS, later-date, non-cyclic supersedence.

### Consequences
- OOB discovery requires explicit structured evidence for the OOB label, date, and superseded KB.
- Later dates alone do not imply OOB.
- Generalized/brittle OOB inference is outside the current implementation.

### Status
Active.

## D006 - Deterministic Microsoft Support extraction with locale fallback

### Decision
Request official `es-ES` Microsoft Support content first. Fall back per KB to `en-US` only when Spanish content cannot be retrieved and parsed reliably. Do not translate with AI or an external translation service.

### Context
The UI is Spanish-first, while Microsoft article localization availability varies by KB.

### Rationale
The current parser supports both Spanish and English headings/date patterns and records the canonical Support URL actually used.

### Consequences
- Report prose may contain a mix of Spanish and English across months/KBs.
- Markup that cannot be interpreted reliably maps to unavailable/`unknown` semantics rather than invented content.

### Status
Active.

## D007 - Semantic daily refresh, not timestamp churn

### Decision
GitHub Actions performs scheduled/manual collection and compares reports while ignoring only `generatedAt` and source `retrievedAt`. It commits only substantive report changes and stages only the expected `data/reports/YYYY-MM.json` path.

### Context
Live collection naturally changes retrieval timestamps even when Microsoft facts have not changed.

### Rationale
Keeping timestamp-only commits would create noise in Git history without changing the dashboard's meaning.

### Consequences
- Scheduled refreshes can run daily without committing daily.
- Meaningful changes use `github-actions[bot]` and the built-in `GITHUB_TOKEN`.
- A refresh failure prevents that run from deploying newly collected data.

### Status
Active.

## D008 - GitHub Pages is the V1 hosting target

### Decision
Build the React/Vite application in GitHub Actions and deploy only `frontend/dist` through the official GitHub Pages actions. Do not use a `gh-pages` branch. Vite receives the Pages base path through `PAGES_BASE_PATH`; local development uses `/`.

### Context
The runtime application is static and the repository already owns collection/build automation.

### Rationale
Current architecture does not require server-side compute at request time. GitHub Pages matches the static artifact and keeps deployment in the same repository/workflow boundary.

### Consequences
- Normal pushes to `main` validate/build/deploy without live Microsoft collection.
- Scheduled/manual refresh runs collect first, then build/deploy the exact resulting state.
- Repository-side Pages/Actions permissions remain external GitHub settings.

### Status
Active.

## D009 - Validate the report on both sides of the JSON boundary

### Decision
Keep Python schema/semantic validation before data is persisted and keep TypeScript report validation/loading before data reaches the UI.

### Context
The repository currently implements both `collector/.../validation.py` and `frontend/src/data/loadMonthlyReport.ts`.

### Rationale
Historical rationale is not explicitly documented; current implementation suggests defense in depth around a static JSON boundary.

### Consequences
- Contract changes require coordinated updates to the JSON Schema, Python semantic rules where relevant, TypeScript model/loader, and tests.
- This duplication is a maintenance cost and a known drift risk; do not remove one side casually.

### Status
Active.

## D010 - Production reports override same-month fixtures

### Decision
The frontend catalog loads both `data/fixtures/*.json` and `data/reports/*.json`, but a production report has higher priority for the same `reportMonth`.

### Context
The August 2026 manual fixture is retained as test/golden input while a generated August production report also exists.

### Rationale
The fixture should remain available for tests without replacing fresher production data in the application.

### Consequences
- Duplicate files at the same priority for one month are rejected.
- Adding a new production month automatically makes it available to the build-time month catalog after the next build/deploy.

### Status
Active.
