---
name: dspx-diagram
description: Author a diagram as a draw.io (.drawio) file and render it to a backend-neutral
  image (SVG primary) for embedding in a docspec deliverable. A SUPPORT skill, loaded by a
  delegated subagent — the main authoring agent (draft/develop) never loads it; it hands over
  intent and reviews the rendered image. Use for architecture / flow / sequence / state /
  network diagrams that a docspec section needs as an embedded figure.
kind: support
license: PolyForm-Noncommercial-1.0.0
compatibility: Rendering needs the draw.io desktop CLI (`docspec setup --with-drawio`, or a
  system install). Without it the skill degrades to a browser-fallback URL or XML-only. The
  vision self-check needs a vision-capable model; it is skipped gracefully if absent. The
  vendored scripts are stdlib-only Python 3.
metadata:
  author: docspec
  version: "1.0"
---
## STEP 0 — orient before acting
You are a **delegated subagent**. The main agent gave you the diagram's *intent* (what it must
show) and the *target section* (`corpus/<section>/assets/`). Your job: produce one `.drawio`
source plus a rendered **SVG** image there, then hand the image path back. You do NOT edit the
deliverable prose, place the figure in the document, or assign a figure number — the renderer
numbers figures at export, and `draft` writes the `![caption](assets/<file>)` reference. You make
the picture; the engine and the main agent do the rest.

The two vendored helpers live next to this file:
- `scripts/validate.py <file.drawio>` — fast, deterministic structural lint (dangling edges,
  duplicate/reserved ids, broken parents, overlaps, edge-through-vertex). Run it on every
  generated `.drawio` before you render.
- `scripts/encode_drawio_url.py [--edit] <file.drawio>` — browser fallback: prints a
  diagrams.net URL carrying the XML in the fragment (nothing is uploaded). Use when the CLI
  is unavailable.

(Both are vendored from the MIT-licensed Agents365 draw.io skill — see `scripts/NOTICE.md`.)

---
## The Stance — the iron laws
- **One picture, backend-neutral.** The output is a `.drawio` source + a rendered **SVG** (crisp
  in both Typst `image()` and LaTeX `\includegraphics`). Store BOTH in the section's
  `assets/` dir — the SVG is what the deliverable embeds, the `.drawio` is the editable source
  that makes the image regenerable. Never embed raw TikZ, raw `{=latex}`, or mermaid in the
  deliverable; the diagram travels as an image.
- **You author the picture, not the document.** No figure numbers, no cross-section references,
  no captions baked into prose. Hand back the image path and a one-line description of what it
  shows; the main agent places it.
- **Validate before you render.** A wrong `source`/`target` id or a dangling edge renders as a
  silently broken picture. Run `scripts/validate.py` first; fix every error before exporting.
- **Render small, review, converge.** Export a preview, LOOK at it (vision), fix the obvious
  defects, then export the final SVG. Diagram quality is something you SEE — do not declare a
  diagram done from the XML alone.
- **Degrade honestly.** If the draw.io CLI is missing or crashes, do NOT fake an image. Emit the
  browser-fallback URL (or the `.drawio` XML alone) and say so, so the main agent can decide.

---
## The Rhythm — author → validate → render → self-check → converge
1. **Plan.** Identify the shapes, the relationships, the layout direction (LR or TB), and the
   groups (tiers/layers). Keep it to what the intent needs — docspec diagrams are architecture /
   flow / sequence / state figures, not decorative art.
2. **Generate** the `.drawio` XML to `corpus/<section>/assets/<name>.drawio`. Hand-place
   coordinates (snap to multiples of 10; scale spacing with node count). Use the draw.io XML
   skeleton below.
3. **Validate** — `python3 scripts/validate.py corpus/<section>/assets/<name>.drawio`. Fix every
   error (warnings are advisory). Re-run until clean.
4. **Render a preview** — `drawio -x -f png --width 2000 -o /tmp/<name>.png <name>.drawio`
   (NO `-e`; cap width so vision can read it).
5. **Self-check (vision).** Read the preview PNG. Catch overlaps, clipped labels, missing
   connections, off-canvas shapes, edges crossing unrelated shapes. Apply targeted XML fixes and
   re-render. Max 2 rounds, then proceed. (No vision model → skip this step.)
6. **Final render → SVG** — `drawio -x -f svg -e -o corpus/<section>/assets/<name>.svg
   <name>.drawio`. SVG is text, so `-e` (embed editable XML) is safe. The deliverable embeds the
   SVG; the `.drawio` stays as the source of truth.
7. **Hand back** the SVG path + a one-line description of what the diagram shows. Done.

**If the draw.io CLI is unavailable** (not installed, or crashes / empty output in a sandbox):
do not retry in a loop. Run `python3 scripts/encode_drawio_url.py <name>.drawio` for a browser
URL the user can open to view/export, or hand back the `.drawio` XML alone, and tell the main
agent rendering needs `docspec setup --with-drawio` (or a system draw.io install).

---
## draw.io XML skeleton
```xml
<?xml version="1.0" encoding="UTF-8"?>
<mxfile host="docspec">
  <diagram name="Page-1">
    <mxGraphModel>
      <root>
        <mxCell id="0" />
        <mxCell id="1" parent="0" />
        <!-- user shapes start at id="2" -->
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
```
Rules that keep `validate.py` and the renderer happy:
- `id="0"` and `id="1"` are required root cells — never omit them; user shapes start at `id="2"`.
- Every shape has `parent="1"` (or its container's id) and `html=1` in `style`.
- **Every edge `mxCell` MUST contain a `<mxGeometry relative="1" as="geometry" />` child** —
  self-closing edge cells do not render.
- Multi-line labels use `&#xa;` (not literal `\n`); escape `&amp; &lt; &gt; &quot;` in attributes;
  never put `--` inside an XML comment.
- CJK labels: just type the characters (the docspec fonts cover CJK); for the browser fallback,
  `encode_drawio_url.py` already percent-encodes them.

### Common shapes
| Style keyword | Use for |
|---|---|
| `rounded=1;whiteSpace=wrap;html=1;` | services, modules, process steps |
| `ellipse;whiteSpace=wrap;html=1;` | start/end, states |
| `rhombus;whiteSpace=wrap;html=1;` | decision points |
| `shape=cylinder3;whiteSpace=wrap;html=1;` | databases / stores |
| `swimlane;startSize=30;html=1;` | titled container / tier |

### Edge
```xml
<mxCell id="10" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;"
        edge="1" parent="1" source="2" target="3">
  <mxGeometry relative="1" as="geometry" />
</mxCell>
```
Pin `exitX/exitY/entryX/entryY` when a node has 2+ connections (spread them across the perimeter);
add `<Array as="points">` waypoints when an edge must route around an unrelated shape.

### A restrained default palette (fill / stroke)
blue `#dae8fc`/`#6c8ebf` (services) · green `#d5e8d4`/`#82b366` (stores) ·
yellow `#fff2cc`/`#d6b656` (decisions) · grey `#f5f5f5`/`#666666` (external) ·
purple `#e1d5e7`/`#9673a6` (security). Pick a small set and stay consistent.

---
## Export reference (resolve the binary first)
The CLI is named `drawio` (Homebrew cask, Linux packages) or, on older installs, `draw.io`; on
macOS the bundle binary is `/Applications/draw.io.app/Contents/MacOS/draw.io`; on Windows
`"C:\Program Files\draw.io\draw.io.exe"`. Resolve which one prints `--version` and use it verbatim.
A **docspec-managed** draw.io (from `docspec setup --with-drawio`) lives under docspec's
`data_dir/drawio/` (Windows `draw.io.exe`, macOS `draw.io.app/Contents/MacOS/draw.io`, Linux
`drawio.AppImage`); if nothing is on PATH, look there or point `DOCSPEC_DRAWIO` at it. If draw.io is
absent entirely, fall back to `scripts/encode_drawio_url.py` (browser) or hand back the XML.

```bash
# Preview PNG (step 4) — NO -e, width-capped for vision
drawio -x -f png --width 2000 -o preview.png input.drawio
# Final SVG (step 6) — -e safe for SVG; this is the deliverable image
drawio -x -f svg -e -o output.svg input.drawio
# Linux headless: prefix with  xvfb-run -a  ; running as root in CI: append  --no-sandbox  at the very end
```
Key flags: `-x` export · `-f {svg,png,pdf}` format · `-e` embed editable XML (SVG/PDF only for the
deliverable) · `--width <px>` cap (no `-s` with it) · `-o` output path · `-b 10` border.

---
## Guardrails
**Do**
- Take the intent + target section from the main agent; produce ONE `.drawio` + its rendered SVG.
- Run `scripts/validate.py` before rendering; fix every error.
- Render a width-capped preview and self-check it with vision before the final SVG.
- Store BOTH the `.drawio` source and the SVG in `corpus/<section>/assets/`.
- Hand back the SVG path + a one-line description; let the main agent place the figure.
- Degrade to the browser URL / XML-only and SAY SO when the CLI is unavailable.

**Don't**
- Don't edit the deliverable prose, write a `![](…)` reference, assign a figure number, or add a
  cross-section reference — that is the engine's and the main agent's job.
- Don't embed raw TikZ / `{=latex}` / mermaid in the deliverable — diagrams travel as images.
- Don't declare a diagram done from the XML alone — look at the render.
- Don't fake an image when the CLI is missing — fall back honestly.
- Don't pull in the dropped heavy machinery (10k-shape index, AI-brand icons, code-import
  visualizers, Graphviz autolayout, style presets) — this lean skill hand-places architecture
  diagrams; that scope was intentionally trimmed.
