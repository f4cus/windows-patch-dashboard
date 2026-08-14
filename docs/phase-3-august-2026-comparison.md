# August 2026 generated report comparison

Compared on 2026-08-13:

- Generated report: `data/reports/2026-08.json`
- Manual evidence fixture: `data/fixtures/2026-08.json`

## Structural and factual comparison

| Check | Result |
| --- | --- |
| KB set | 9/9 match; no generated mismatch and no fixture-only KB |
| OS identities | 9/9 exact normalized identity matches |
| Release dates | 9/9 match (`2026-08-11`) |
| Known Issue statuses | 9/9 match: seven `none`, two `open` |
| Provenance | Every generated row has the CVRF URL and its successfully parsed canonical Support URL, each with a UTC retrieval timestamp |

The generated and fixture changes summaries are semantically aligned around the documented Secure Boot targeting and product-specific improvements. They are not textually equal: the generated report preserves deterministic official Support prose, while the manual fixture contains concise Spanish editorial summaries.

Collection requested official `es-ES` Support content first for every verified KB. On 2026-08-13, Microsoft returned English article content or otherwise no reliably parseable Spanish article content for all nine August KBs, so each record fell back independently to its official `en-US` article. The generated provenance therefore contains nine canonical `en-US` Support URLs and no `es-ES` URL. No content was translated locally.

Explicitly documented fixes were reproduced for Server 2016/2019, Server 2025, Windows 11 23H2, and Windows 11 26H1. The generated report intentionally uses an unavailable message where the current article does not expose a compatible explicit fix item, notably the two ESU rollups, Server 2022, and Windows 11 24H2/25H2. It does not infer “no additional fixes” or reconstruct detailed fixes from a previous preview article.

Known Issue semantics match the fixture. Microsoft Support explicitly reports no known issues for the two ESU rows, Server 2016/2019, and all three Windows 11 rows. The current Server 2022 and Server 2025 articles explicitly describe the open WSUS synchronization-error-detail issue. Article-level status is aggregated per parsed issue: any open item wins over resolved or no-issue text; `resolved` requires one or more verified items with no open or ambiguous item.

## Additional live findings

CVRF returned two hotpatch-only packages alongside normal monthly candidates. Their exact Support redirects identified official hotpatch publication paths, so they were excluded without KB inference. No verified August OOB remediation with the explicit relationship required by the contract was added.

Automation could not and did not reproduce the fixture's editorial translation, its manually condensed prose, or statements that require interpreting absence as “no additional bug.” These are presentation differences, not KB, identity, date, or Known Issue conflicts.
