# Visual Direction

The dashboard should feel like a carefully edited technical bulletin: trustworthy, information-dense, and immediately scannable, with enough visual character to stand apart in a portfolio. The August 2026 spreadsheet reference establishes the useful five-column hierarchy, compact row rhythm, and single-image report density; it is a functional reference, not a visual template to clone.

## Principles

- Use a strong editorial grid, compact typography, restrained rules, and clear alignment to make long operational text readable.
- Make the desktop report surface the primary composition. Interactive Mode may reflow responsively and add filters, month selection, source links, and details without changing facts.
- Preserve the five canonical report columns in Report Mode: KB, OS, Vulnerabilidades / Cambios Clave, Issues Resueltos, and Problemas Conocidos.
- Use status color only to communicate meaning such as open, resolved, unknown, OOB, or not published. Never use it as ambient decoration, and always pair it with text.
- Favor neutral, high-contrast surfaces and one disciplined accent family. Typography, spacing, and hierarchy should provide most of the identity.
- Keep Report Mode stable, dense, and free of navigation or non-essential effects so it exports cleanly to one readable PNG.

## Explicitly avoid

- Generic SaaS dashboards made from repetitive cards.
- Excessive gradients, glassmorphism, glow, or translucent layers.
- Fake AI-agent aesthetics, chat metaphors, or ornamental automation cues.
- Decorative effects inside Report Mode.
- Low-density layouts that increase scrolling or make the full report harder to capture.

Canvas UI, if later justified, is limited to one or two decorative, non-essential effects outside Report Mode. Gooey is optional only for small micro-interactions. Neither may carry information or interfere with deterministic export.

## Hallmark preparation

Hallmark is installed at project scope under `.codex/skills/hallmark`. Because skills installed during a Codex turn become active on the next turn, this Phase 0/1 brief records the supplied visual requirements and reference analysis without starting UI design. Phase 2 should activate Hallmark to refine this document and define the report/interactive-mode system before implementation.
