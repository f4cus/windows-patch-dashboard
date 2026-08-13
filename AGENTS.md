# Agent Guide

Read `docs/product-brief.md`, `docs/decisions.md`, `data/schema/monthly-report.schema.json`, and the relevant fixtures before changing code or data.

## Architecture constraints

- Keep the V1 frontend on React, Vite, and TypeScript.
- Keep collection and normalization in the Python 3 package. The frontend only reads normalized, versioned JSON and must never scrape or call Microsoft directly.
- Use `httpx` for future HTTP work and BeautifulSoup and/or lxml for future parsing. Microsoft collection is outside Phase 0/1.
- Persist reports as JSON in Git. Do not add a database, persistent backend/API, Azure dependency, or runtime AI/LLM service.
- Use pytest for collector and data tests, GitHub Actions for CI, and GitHub Pages for eventual hosting.
- Keep normalization independent from rendering. Presentation may summarize layout, but it must never alter source facts.
- Preserve monthly history. Represent out-of-band updates and supersedence explicitly instead of overwriting the original monthly record.
- Keep Report Mode deterministic and suitable for PNG export. CSV is secondary. TanStack Charts and Thinking Orbs are outside V1; Gooey is limited to optional micro-interactions, and Canvas UI is limited to at most two non-essential decorative effects.

## Source of truth and data integrity

Use this trust order:

1. Official Microsoft Support KB articles.
2. MSRC CVRF and official Microsoft security data.
3. Microsoft Release Health or other official Microsoft documentation when appropriate.

Never let a third-party source silently override official Microsoft facts. Every generated or production report record must include official-source provenance. The manual August 2026 golden fixture may omit sources because it is test input, not generated production data.

Never invent or infer a KB number, release date, change, resolved issue, known issue, or supersedence relationship. A KB is either the verified `KB<number>` value or `NO PUBLICADO`. Do not convert missing, unavailable, or unverifiable information into `knownIssuesStatus: "none"`. Expected Windows Server 2012 or 2012 R2 ESU data that is not published must remain representable as `NO PUBLICADO` and `not-published`.

Keep the canonical report order deterministic: Windows Server 2012 (ESU), Windows Server 2012 R2 (ESU), Windows Server 2016, Windows Server 2019, Windows Server 2022, Windows Server 2025, then supported Windows 11 branches from oldest to newest for that report month.

## Scope boundaries

Phase 0/1 establishes tooling, validates the data contract and golden fixture, and renders only a minimal proof page with the five canonical columns. Do not add Microsoft collection or scraping, scheduling, a final dashboard UI, production deployment, accounts, device inventory, compliance features, analytics, or runtime AI as part of this phase. Do not edit fixture prose based on assumptions or fetch Microsoft to "correct" the August fixture.

Document any deliberate architecture deviation in `docs/decisions.md`. If a schema change breaks existing data, update affected fixtures and record the reason in the same change.

## Required checks

Before completing work, run these commands from the repository root on Windows PowerShell:

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
npm run lint
npm run format:check
npm run typecheck
npm run build
```

If a check cannot run, report the exact blocker; do not claim success from inspection alone.
