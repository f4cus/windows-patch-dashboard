# Phase 2 visual and report contract

Windows Patch Dashboard is a technical-editorial workbench for infrastructure,
security, DevOps, systems administration, patch management, and vulnerability
management professionals. Its primary artifact is the monthly Report Mode
surface: a dense, deterministic bulletin that can be read, verified, shared,
and exported as one high-resolution PNG.

The August 2026 spreadsheet reference establishes the useful five-column
hierarchy, compact row rhythm, and single-image density. It is a functional
reference, not a visual template to clone.

## Hallmark system

- Genre: modern-minimal.
- Macrostructure: Workbench. The product artifact itself leads; marketing
  sections, dashboards, and decorative cards do not.
- Theme: Cobalt. Cool engineered paper, graphite ink, ruler-like rules, tight
  radii, and one cobalt interaction accent.
- Navigation: N9 edge-aligned minimal. Wordmark left; the single Report Mode
  action right. Operational controls sit in a separate workbench bar.
- Footer: Ft2 inline rule. One compact provenance and runtime statement.
- Enrichment: none. Typography and report structure carry the experience.
- Type: Space Grotesk Variable for display and Source Sans 3 Variable for body,
  both bundled locally. Cascadia Mono or platform mono is reserved for small
  metadata.
- Motion: button state feedback only. Report content remains composed and
  static; reduced-motion users receive immediate state changes.

The Cobalt marketing patterns for code heroes and command palettes are not part
of this application. They would add unrelated functionality and conflict with
the fixed Phase 2 scope.

## Information architecture

Interactive Mode follows this order:

1. Minimal product header and Report Mode action.
2. Locally derived month selector, optional OS-family filter, and PNG export.
3. Known-issue status legend, with OOB supersedence explained separately.
4. The canonical report surface.
5. Inline provenance/source disclosures per update.
6. Compact static-runtime footer.

Report Mode renders only the canonical report surface. Escape returns to
Interactive Mode. Navigation, selectors, status legend, source disclosures, and
application footer are absent.

## Canonical report surface

The report header always includes the report title, month, Patch Tuesday date,
generated date, report status, selected scope, and record count. The table has
exactly these five columns, in this order:

1. KB
2. OS
3. Vulnerabilidades / Cambios Clave
4. Issues Resueltos
5. Problemas Conocidos

`NO PUBLICADO` remains explicit. Known-issue status is a text-and-symbol label,
never color alone. `supersededBy` is rendered as an independent OOB label so an
update can simultaneously show an open, resolved, none, or unknown known-issue
state. Fixture prose is rendered verbatim.

The table uses a fixed canonical minimum width. Narrow viewports scroll the
report horizontally inside its own region; the surrounding document does not
overflow. This is intentional because collapsing long operational prose into
cards would destroy the report artifact and the five-column contract.

## Export behavior

PNG export runs entirely in the browser against the report element itself. The
export temporarily removes Interactive Mode-only source disclosures, waits for
bundled fonts to settle, and renders the full report at 2× pixel density on a
stable 1600 CSS-pixel surface. It does not call an external service.

## Explicitly avoid

- Generic SaaS dashboard cards, charts, or KPI tiles.
- Gradients, glassmorphism, glow, ambient illustration, or fake application
  chrome.
- AI-agent, chat, or automation metaphors.
- Decorative effects or controls inside Report Mode.
- Rewriting fixture facts or prose for visual convenience.
- Runtime network requests, collection, backend services, databases, or cloud
  dependencies.
