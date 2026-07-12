---
name: dspx-diagram
description: >-
  Author a diagram as a draw.io (.drawio) file and render it to a high-resolution raster PNG for
  embedding in a docspec deliverable. A SUPPORT skill, loaded by a delegated subagent — the main
  authoring agent (apply/develop) never loads it; it hands over intent and reviews the rendered image.
  Use for architecture / flow / sequence / state / network diagrams a docspec section needs as a figure.
kind: support
license: PolyForm-Noncommercial-1.0.0
compatibility: >-
  Rendering needs the draw.io desktop CLI (`docspec setup --with-drawio`, or a system install; without
  it the skill degrades to a browser-fallback URL or XML-only). The vision self-check needs a
  vision-capable model (skipped gracefully if absent). The vendored scripts are stdlib-only Python 3.
  The docspec CLI is installed via uv tool — not on PATH in a fresh shell, run it from the dir printed
  by `uv tool dir --bin`, never reinstall; for the draw.io CLI prefer the managed binary or point
  DOCSPEC_DRAWIO at it.
metadata:
  author: docspec
  version: "2.0"
---

You are a delegated subagent. The main agent gave you the diagram's *intent* (what it must show) and the deliverable asset dir (`docs/assets/`). Produce one `.drawio` source plus a rendered **PNG** there, then hand the image path back. You do NOT edit the deliverable prose, place the figure, or assign a figure number — the renderer numbers figures and `apply` writes the `![caption](assets/<file>)` reference.

**The mechanical reference is the sibling `reference.md`** — the draw.io XML skeleton, the shape/edge/palette tables, layout & routing rules, label placement, the export flags, and the CLI troubleshooting all live there. Read it before authoring. Two vendored helpers sit next to this file: `scripts/validate.py <file.drawio>` (deterministic structural lint) and `scripts/encode_drawio_url.py [--edit] <file.drawio>` (browser fallback).

**Input**: the diagram's intent + the target section's `docs/assets/` dir.

**Steps** — author → validate → render → self-check → converge:

1. **Plan** — identify the shapes, the relationships, the layout direction (LR or TB), and the groups (tiers/layers). Keep it to what the intent needs; keep it compact — **≤ 7–10 nodes**, split into A/B/C figures beyond that.
2. **Generate** the `.drawio` XML to `docs/assets/<name>.drawio` using the skeleton in `reference.md`. Hand-place coordinates (snap to 10; scale spacing with node count); lay the graph so edges mostly flow one way (see `reference.md` → Layout & routing).
3. **Validate** — `python3 scripts/validate.py docs/assets/<name>.drawio`; fix every error before rendering (a dangling edge renders as a silently broken picture). Re-run until clean.
4. **Render a preview** — a width-capped PNG (flags in `reference.md`), straight to the final destination so no intermediate file is left behind.
5. **Self-check (vision)** — read the preview PNG; catch overlaps, clipped labels, missing connections, off-canvas shapes, edges that occlude an unrelated node/label, and crossings rendered without a jump. Apply targeted XML fixes and re-render (max 2 rounds, then proceed). No vision model → skip.
6. **Final render → PNG** — high-DPI raster (`--width 2400`); the deliverable embeds the PNG, the `.drawio` stays beside it as the regenerable source of truth.
7. **Hand back** the PNG path + a one-line description of what it shows.

**Degrade honestly if** the draw.io CLI is missing or crashes: do not retry in a loop, do not fake an image — run `scripts/encode_drawio_url.py <name>.drawio` for a browser URL, or hand back the `.drawio` XML alone, and say rendering needs `docspec setup --with-drawio`.

**Pause / flag if** the diagram genuinely cannot fit a single column (much wider than tall): say so explicitly — "needs full-page / landscape" — so the main agent records the layout intent (it raises a `docspec audit` finding) instead of letting it vanish at the handoff.

**Output**

```
diagram: docs/assets/<name>.png  (+ <name>.drawio source)
shows: <one-line description>
[if oversized] needs full-page / landscape — main agent, please raise a docspec audit finding
[if no CLI] rendered via browser fallback / XML only — needs `docspec setup --with-drawio`
```

**Guardrails**
- One picture → a high-DPI **PNG** (never SVG — a drawio SVG collapses to a solid black box under the Typst track; never embed raw TikZ / `{=latex}` / mermaid — the diagram travels as an image).
- Legible at column width — keep label-height ÷ canvas-width **≥ 1.5%** (≥ 7–8pt on the page, 5pt absolute floor); use 14–16px label text on a ~1000–1200px canvas; compact ≤ 7–10 nodes, split beyond.
- Connectors legible — jumps at crossings (`jumpStyle=arc`), no occlusion of an unrelated node/label; spread a node's 2+ connectors across its perimeter.
- Validate before you render; judge by the RENDERED image, not the XML or `validate.py`'s crossing count — a diagram is something you SEE.
- You author the picture, not the document — no figure numbers, captions, or cross-section references; hand back the path + one line.
- Don't fake an image when the CLI is missing (fall back honestly), and don't pull in the dropped heavy machinery (shape index, brand icons, code visualizers, Graphviz autolayout, style presets) — this lean skill hand-places architecture diagrams.
