# Phase 3 Microsoft source evaluation

Evaluation date: 2026-08-13. Target publication: August 2026 Patch Tuesday.

## Result

The V1 collector uses the official monthly MSRC CVRF document for KB/product discovery and official Microsoft Support KB articles for article content. CSAF remains a tested complementary adapter; it is not used as provenance unless a future collection path actually consumes its advisory.

## Evidence

The public [CSAF provider metadata](https://msrc.microsoft.com/csaf/provider-metadata.json) advertises Microsoft's advisory and VEX distributions. The live [advisory index](https://api.msrc.microsoft.com/csaf/advisories/index.txt) contained thousands of individual JSON paths, including many 2026 advisories. A representative August advisory exposed a useful CSAF product tree and `vendor_fix` remediations with release dates, product IDs, and official KB links. The distribution is organized per CVE, however, and did not expose a month-level manifest of all applicable KB/product relationships. Complete monthly discovery would therefore require a broad per-CVE download and reconciliation pass.

The official [August 2026 CVRF document](https://api.msrc.microsoft.com/cvrf/v3.0/cvrf/2026-Aug) was one monthly XML response. At evaluation time it contained 207 product identities and 790 vulnerability entries. Its `Vendor Fix` remediations supplied all nine normal KB/product mappings represented by the project scope, including Monthly Rollup subtype evidence for Windows Server 2012 and 2012 R2 ESU. Repeated relationships across vulnerabilities could be deterministically deduplicated.

CVRF also exposed hotpatch packages with the generic `Security Update` subtype. The collector did not select by KB sequence. Fetching the exact CVRF-provided KB through Microsoft Support resolved those packages to official `/servicing/os/hotpatch/` article paths, which gives a narrow official exclusion signal for the normal monthly report.

For article content, the collector requested only `https://support.microsoft.com/help/<verified-number>` and retained each canonical redirect URL. The August articles supplied Improvements/Summary content and explicit Known Issues states. Microsoft Support remains authoritative for `changesSummary`, `resolvedIssuesSummary`, `knownIssuesSummary`, and `knownIssuesStatus`.

## Limitations

- CVRF is required for V1 monthly discovery; there is no automatic bulk-CSAF fallback.
- The CSAF adapter parses one supplied advisory but does not attempt to download every monthly CVE document.
- Deterministic Support extraction preserves official English prose and does not recreate manually edited Spanish summaries.
- Markup without a recognizable Known Issues section maps to `unknown`; it never maps to `none` by absence.
- OOB output requires explicit structured evidence for the OOB label, release date, and superseded KB. Later dates alone are insufficient.
