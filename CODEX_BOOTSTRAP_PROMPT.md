# Codex Bootstrap Prompt — Phase 0 + Phase 1

You are the primary implementation agent for a public portfolio project tentatively named `windows-patch-dashboard`.

Before changing files, read all repository documentation, especially:
- `docs/product-brief.md`
- `docs/decisions.md`
- `data/schema/monthly-report.schema.json`
- `data/fixtures/2026-08.json`

## Objective for this run
Implement only **Phase 0 (foundation)** and **Phase 1 (data contract + golden fixture validation)**.

Do not implement the Microsoft collector yet.
Do not implement the final dashboard UI yet.
Do not add a database, persistent backend, Azure dependency, or runtime AI service.

## Product context
The application organizes public Microsoft Patch Tuesday information for Windows Server 2012 ESU and newer plus Windows 11 into a concise, traceable report.

The canonical report columns are:
1. KB
2. OS
3. Vulnerabilidades / Cambios Clave
4. Issues Resueltos
5. Problemas Conocidos

The final product will have:
- Interactive Mode for browsing/filtering.
- Report Mode optimized for a clean PNG export.

August 2026 is the manual **golden fixture**. Treat it as test input, not as proof that the future collector is correct.

## Fixed V1 architecture
- React + Vite + TypeScript frontend.
- Python 3 collector.
- httpx.
- BeautifulSoup/lxml when parsing is implemented later.
- MSRC CVRF + official Microsoft Support as authoritative public sources.
- JSON persisted/versioned in Git.
- pytest.
- GitHub Actions for CI/scheduling.
- GitHub Pages for hosting.
- No database.
- No persistent backend/API.
- No Azure.
- No runtime LLM dependency.
- Hallmark is the preferred design skill.
- Canvas UI may later be used selectively for at most one or two decorative, non-essential effects.
- TanStack Charts is not part of V1.
- Thinking Orbs is not part of V1.
- Gooey is optional only for micro-interactions.
- PNG is the primary report export; CSV is secondary.

## Non-negotiable data-integrity rules
1. Never invent or infer a KB number.
2. Never convert missing/unknown data into "no known issues".
3. Missing expected WS2012/WS2012R2 ESU data must remain representable as `NO PUBLICADO`.
4. Production records must preserve official-source provenance.
5. Presentation must not alter source facts.
6. The frontend must never scrape Microsoft directly.
7. OOB updates must be representable without overwriting monthly history.
8. Data normalization must be separated from rendering.

## Required repository structure
Create/refine a maintainable structure similar to:

```text
windows-patch-dashboard/
├── frontend/
├── collector/
│   ├── src/
│   └── tests/
├── data/
│   ├── fixtures/
│   ├── schema/
│   └── reports/
├── design/
│   └── references/
├── docs/
├── .github/
│   └── workflows/
├── AGENTS.md
├── README.md
├── LICENSE
└── .gitignore
```

You may make small structural improvements if justified, but do not over-engineer.

## Phase 0 tasks
1. Initialize the frontend with React + Vite + TypeScript.
2. Initialize a Python project for the collector with a simple modern package layout.
3. Add lint/format/type-check commands with minimal dependencies.
4. Add pytest.
5. Add top-level documentation explaining local development.
6. Add `AGENTS.md` with:
   - architecture constraints,
   - source-of-truth rules,
   - no-fabrication rules,
   - scope boundaries,
   - commands agents must run before completing work.
7. Add a permissive open-source license suitable for a public portfolio project (MIT unless the repository already specifies another).
8. Add `.gitignore`.
9. Add a basic GitHub Actions CI workflow that runs:
   - Python tests,
   - Python lint/checks if configured,
   - frontend install,
   - frontend typecheck/lint,
   - frontend build,
   - JSON/schema validation.
10. Do **not** add scheduled Microsoft collection yet.

## Phase 1 tasks
1. Treat `data/schema/monthly-report.schema.json` as the initial contract.
2. Review it critically and improve it only where necessary.
3. If you make a breaking schema change, explain it in `docs/decisions.md` and update the golden fixture.
4. Add automated validation of every JSON file under `data/fixtures/` and later `data/reports/`.
5. Add tests for:
   - valid KB values (`KB<number>` and `NO PUBLICADO`);
   - known issue status semantics;
   - OOB/supersedence representation;
   - required provenance in production/generated reports while allowing the manual golden fixture to omit sources;
   - deterministic OS ordering for report output.
6. Define the canonical OS order:
   - Windows Server 2012 (ESU)
   - Windows Server 2012 R2 (ESU)
   - Windows Server 2016
   - Windows Server 2019
   - Windows Server 2022
   - Windows Server 2025
   - Windows 11 versions ordered from oldest supported branch to newest for that report month.
7. Add a small TypeScript loader/model layer that reads the August fixture and exposes typed data to the frontend.
8. Render only a minimal development page proving the fixture can be loaded:
   - report month;
   - number of updates;
   - simple unstyled/low-style table with the five canonical columns.
   This is not the final UI.
9. No external API calls from the browser.

## Hallmark preparation
If project-scoped Hallmark is already available, use it only to create/update a concise `design/design.md` describing the intended visual direction.

If Hallmark is not installed and the environment permits it, install the project-scoped skill following the upstream project instructions. If installation is unavailable, do not block Phase 0/1; document the pending step.

The visual brief must explicitly avoid:
- generic SaaS dashboard cards everywhere;
- excessive gradients/glassmorphism;
- fake AI-agent aesthetics;
- decorative effects inside Report Mode;
- low-density layouts that make the report harder to capture.

Desired visual character:
- technical/editorial;
- information-dense but readable;
- trustworthy;
- distinctive enough for a portfolio;
- desktop-first report surface with responsive Interactive Mode;
- status color used semantically, not decoratively.

## Golden fixture
`data/fixtures/2026-08.json` comes from the manually reviewed August 2026 report and is the baseline for development.

Do not "correct" its prose based on assumptions.
Do not fetch Microsoft during this phase.
If a fixture/schema mismatch exists, resolve it explicitly and document the reason.

## Acceptance criteria
Before you finish:
- `pytest` passes.
- schema validation passes.
- frontend typecheck/lint passes.
- frontend build passes.
- the minimal page successfully loads the August fixture.
- CI workflow is syntactically valid.
- no Azure service appears in the implementation.
- no database appears in the implementation.
- no runtime AI/LLM call appears in the implementation.
- no Microsoft scraping/API collection is implemented yet.
- README explains exact local commands.
- `docs/decisions.md` reflects any deviations from this brief.

## Delivery
At the end, return:
1. concise summary of what was created;
2. repository tree;
3. commands executed and results;
4. decisions/deviations;
5. risks or blockers;
6. exact recommended next task for Phase 2 (UI/report design).

Do not start Phase 2 automatically.
