# Technical Decisions

This file records the small set of **active** decisions that would be risky to lose. `docs/decisions.md` retains longer Phase history; consult it only when historical detail is needed.

## D001 - Official Microsoft sources only

### Decision
Production report data is populated only from official Microsoft sources. MSRC CVRF is the V1 monthly discovery source. The official Windows message center supplies dated OOB announcements that may be absent from CVRF. Official Microsoft Support KB articles verify each KB's release date, OOB label, changes, fixes, and known issues. Reviewed product-history navigation can also discover explicitly dated post-ESU OOB links; it is not an unbounded article crawl. The CSAF adapter remains tested and complementary, not the primary monthly discovery path.

### Context
The product needs one reliable monthly KB/product view plus article-level operational content.

### Rationale
The repository's live source evaluation found that CVRF exposes one monthly document with the KB/product remediation relationships needed by the supported scope. CVRF omits some officially announced OOB updates, so the message center complements its discovery. CSAF is distributed per CVE and has no month-level KB/product manifest in the implemented path. Microsoft Support supplies the KB article content that CVRF does not.

### Alternatives
A bulk monthly CSAF crawl was evaluated for V1 and not selected because it would require downloading and reconciling many per-CVE advisories.

### Consequences
- A CVRF collection failure is fatal for that run.
- A message center failure is isolated as incomplete OOB discovery: preserve previously confirmed same-month OOB records and publish verified monthly information as `partial` (D012).
- Individual Support failures produce explicit pending/partial evidence without blocking independent KBs (D012). Contradictory verified facts and unsafe global failures still stop collection.
- Third-party sources must not populate production report facts.
- Validated earlier production reports with status `generated` or `verified` (or independently verified rows in 1.1 partial reports) and matching MSRC CVRF + Support provenance can supply known official Support URLs. Their exact KB/OS release date may exclude only an undated historical monthly candidate before fetching Support. If any candidate for that KB is unmatched, live verification remains required and its evidence is not overridden. Earlier-month facts never supply current rows, package classification, OOB or supersedence; warnings retain the report path, SHA-256 and original source URLs/retrieval times. Live failures still contribute to `partial` status.

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
`data/schema/monthly-report.schema.json` is the report contract, supplemented by cross-record validation in Python. Generated reports require provenance and timestamps. Missing/ambiguous evidence stays explicit through publication, verification and lifecycle fields (D012); it is never silently converted to clean data. Reports are validated before atomic replacement.

### Context
A patch dashboard is harmful if it presents guessed KBs, dates, known-issue states, or supersedence as facts.

### Rationale
The existing collector and validation layer consistently prefer an incomplete or failed run over fabricated certainty.

### Consequences
- Historical 1.0 `NO PUBLICADO` semantics remain valid. In 1.1, publication and known-issue status are independent; after October 2026 the ordinary ESU absence carries explicit `lifecycle.status: esu-ended`, with official provenance (D012).
- Invalid schema/semantics prevent the new production JSON from replacing the previous valid file.
- Source/provenance fields are part of the production contract.

### Status
Active.

## D004 - Explicit product normalization and conservative candidate resolution

### Decision
Map only supported Microsoft product aliases to normalized Windows Server/Windows 11 identities. Combine Windows 11 branches only when they share the same verified KB and matching structured metadata. Exclude SSU, security-only, and auxiliary packages only when the verified Support article title identifies that package type. If CVRF returns multiple remaining normal monthly KB candidates for the same normalized OS, select one only when **exactly one** candidate has a Support-verified principal package type (cumulative or Monthly Rollup), Patch Tuesday date, and matching product applicability; two verified principal candidates fail with a conflict, while candidates lacking sufficient evidence remain explicitly pending (D012).

### Context
Microsoft structured data can contain multiple package/remediation candidates that cannot safely be distinguished by KB number alone.

### Rationale
Historical rationale for every product-mapping rule is not fully documented; the current implementation shows a deliberate policy of using a second official source as the tie-breaker rather than KB ordering or hardcoded exclusions.

### Consequences
- No "highest KB wins" or similar heuristic is allowed.
- A single unverified candidate remains pending in a partial report; the tie-breaker applies only to duplicate monthly candidates.
- CVRF can label ESU Monthly Rollups as generic `Security Update`. Retain those candidates for Support verification; a generic ESU candidate requires a Support-confirmed Monthly Rollup and product applicability. Unresolved classification stays pending rather than claiming `NO PUBLICADO` or blocking independent KBs (D012). An explicit CVRF `Monthly Rollup` can retain partial behavior when Support is unavailable.
- Support classification uses the article title, not references to prerequisites in its body. Unknown package types cannot break a monthly tie and remain pending for a single candidate. No KB-specific exclusions are used.
- Undated monthly CVRF metadata variants are retained until Support can verify an earlier release month and matching product, either live or through the narrowly scoped prior production evidence allowed by D001. Official hotpatch exclusions happen first; remaining contradictory records for the same KB/product fail before package classification or monthly tie-breaking, including when Support is unavailable. A Support failure cannot turn an official metadata contradiction into `pending`. Explicit-date and OOB remediation conflicts remain fatal in the parser.
- Windows Server, version 23H2 remains representable historically but is not in the current expected monthly server set.

### Status
Active.

## D005 - OOB history is additive and conservative

### Decision
Represent an officially identified out-of-band update as its own record with `updateType: oob`; never remove the monthly record. The original monthly record may point to it through `supersededBy` only when separate official evidence establishes that relationship. OOB status and supersedence are independent from `knownIssuesStatus` and from each other.

### Context
An OOB release should not erase the monthly update or its known-issue history.

### Rationale
The data contract and validators preserve both records. When a supersedence link exists, validation requires a same-OS, later-date, non-cyclic relationship.

### Consequences
- OOB classification requires an explicit, deterministic Microsoft source label. CVRF may identify an OOB directly; Microsoft Support may identify it in the article title when CVRF uses the generic `Security Update` subtype. The message center can discover additional OOB KBs through dated, OS-labelled official announcement links; Support then verifies each article.
- An OOB may have `supersededBy: null` on the monthly record. Set the link only from an explicit official supersedence relationship.
- Later dates alone imply neither OOB nor supersedence.
- Conflicting official dates still fail collection; unsupported inference remains outside the implementation.

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
- If a locale-specific `/help/` request follows an official redirect and ends in an HTTP error, the adapter can make one direct attempt to that observed Microsoft Support URL before proceeding with locale fallback. It never constructs a canonical path; KB, locale and hotpatch verification still apply. HTTP 403 remains non-transient in the HTTP client's generic retry policy.

### Status
Active.

## D007 - Adaptive semantic refresh, not timestamp churn

### Decision
GitHub Actions performs scheduled/manual collection and compares reports while ignoring only `generatedAt`, source `retrievedAt` and `verification.checkedAt`. It commits only substantive report changes and stages only the expected `data/reports/YYYY-MM.json` path.

### Context
Live collection naturally changes retrieval timestamps even when Microsoft facts have not changed.

### Rationale
Keeping timestamp-only commits would create noise in Git history without changing the dashboard's meaning.

### Consequences
- WPD-INC-003 uses Argentina's fixed UTC-3 offset: D (second Tuesday) hourly at 14:15–22:15; D+1 every two hours at 09:00–21:00; D+2 every four hours at 09:00–21:00; D+3 at 09:00 and 15:00; otherwise daily at 15:00, including the days before the next month's D.
- Non-overlapping UTC cron candidates are filtered by a dependency-free planning job before installing the collector. Automatic month selection opens at D 14:15 ART; a manual month override remains available.
- The planner associates the triggering cron with its latest occurrence at or before the workflow's API `created_at`, then tolerates up to six hours from that slot to the gate. It never requires the runner's current minute to match. Older runs are skipped, and dropped slots are not replayed; the next approved slot tries again. This is bounded best-effort scheduling, not guaranteed delivery or an exactly-once queue.
- Automated publication still waits until D 10:00 America/Los_Angeles (PST/PDT). Contract 1.1 permits official CVRF, release-health or Support-history KB evidence explicitly labelled pending/partial, without requiring a complete Support article; 1.0 retains its existing Support-verified monthly guard. Empty/lifecycle-only attempts do not qualify. Schedules are unchanged (D012).
- Meaningful changes use `github-actions[bot]` and the built-in `GITHUB_TOKEN`.
- A refresh failure prevents that run from deploying newly collected data.
- Canonical URL resolution uses observed redirects, official indexes and validated prior production URLs. Missing article verification can remain pending/partial under D012; conflicting official metadata still fails safely under D001/D003/D004.

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

## D011 - Client PDF comes from printable HTML

### Decision
Render Client Report from the existing filtered monthly report model and use browser print/Save as PDF with A4 print CSS. Keep PNG export and the existing Report Mode separate.

### Context
Months with additive OOB records can make the five-column PNG very tall. A client deliverable needs readable pagination, selectable text, and official hyperlinks without personal project attribution.

### Consequences
- Client Report has neutral content and its own document layout; it does not change JSON loading or collection.
- The browser controls final PDF generation and may add its own metadata, headers, or footers according to print settings.

### Status
Active.

## D012 - Incremental publication with independent evidence and lifecycle states

### Decision
Publish safe official information progressively. Contract 1.1 adds `publicationStatus`
(`verified`, `partial`, `pending`, `not-published`), a dated Support verification result,
optional retained provenance and a separate lifecycle annotation. Continue reading 1.0
without rewriting historical reports. The five report columns remain unchanged.

A failed individual Support request or parser does not establish non-publication. Keep the
confirmed CVRF KB/product relationship pending; omit inferred dates, update types and
supersedence. An explicitly dated principal package in CVRF or verified official product-history navigation can remain published/partial when its target article is inaccessible. Unknown package types remain pending. A confirmed package with missing article fields remains partial with explicit
`No disponible` text. Subsequent runs can fill those fields. Same-month previously verified
fields and OOB history survive temporary failures with their original sources/timestamps.
Past-report evidence never invents current facts. Independent per-article HTTP sessions
avoid sharing article cookies/connections; canonical discovery and all retries stay bounded.

CVRF failure, invalid contracts, contradictory official metadata for the same KB/product,
contradictory verified dates/products and multiple verified principal monthly candidates
still fail globally before atomic replacement. Metadata conflicts can be bypassed only by
verified historical exclusion or official hotpatch exclusion, never by a failed Support request.
Insufficient classification of otherwise consistent candidates stays pending without selecting
by KB number or approximate date.
Message center outages mark discovery incomplete, preserve confirmed OOB history and do
not block independent monthly information. Hotpatch exclusions require official Support
path evidence; known OOB and supersedence retain their existing validation rules.

Both Windows Server 2012 ESU programmes ended on 2026-10-13, as confirmed by Microsoft Learn
and their final ordinary rollup articles. From November, an absent later update is labelled
`SIN ACTUALIZACIÓN — ESU FINALIZADO`, with the migration recommendation and actual source
retrieval times. Lifecycle alone does not make a report partial. Verified exceptional
updates remain eligible and replace the absence placeholder; end of ESU never suppresses
a documented KB. No publication date or KB is fabricated for an absence record. The bounded post-ESU history adapter reads only explicit current-month OOB navigation labels on the reviewed official product pages, checks the page's product applicability, and verifies the target article when available. It never selects links from prerequisites/body references or derives dates from URL directories.

### Reconciliation
- D001: retain official-only provenance; replace fatal individual/article and message center
  failures with safe evidence isolation. Structured monthly discovery remains required.
- D003: retain validation and atomic writes; distinguish publication, unknown known issues
  and lifecycle. Partial fields remain explicit and cannot be labelled verified.
- D004: retain conservative product/package verification and real-conflict failures; change
  insufficient classification from global failure to pending evidence.
- D007: retain all schedule slots and the release-time boundary. Publish substantive partial
  enrichment; ignore only generation, source-retrieval and verification-check timestamps.
  No timestamp-only commits. The workflow continues staging only the target report.

### Status
Active. Covered by Python/TypeScript contract, collector, incremental-refresh and UI tests.

### Verified November exceptions
The official product histories and target articles also document two exceptional OOBs dated
2026-11-06. The November working report therefore retains the seven previously published
monthly KBs and includes those two verified exceptions with `esu-ended` lifecycle metadata,
rather than asserting an absence. October remains the last ordinary ESU Patch Tuesday.
`SIN ACTUALIZACIÓN — ESU FINALIZADO` is exercised for the genuine no-later-update case.
