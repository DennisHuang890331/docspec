---
name: dspx-diagram
description: Author a diagram as a draw.io (.drawio) file and render it to a high-resolution
  raster PNG for embedding in a docspec deliverable. A SUPPORT skill, loaded by a
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
> **If `docspec` is not found** — it IS installed (via `uv tool`); your shell's PATH just predates the install (a freshly-launched or sandboxed agent shell). Don't conclude it's missing: run the binary directly from the uv tools bin dir (normally `~/.local/bin/docspec`, Windows `%USERPROFILE%\.local\bin\docspec.exe`; `uv tool dir --bin` prints it), or restart your terminal so the install's PATH update takes effect. **For the draw.io CLI:** prefer the docspec-managed binary (`docspec setup --with-drawio`) or point `DOCSPEC_DRAWIO` at it.

You are a **delegated subagent**. The main agent gave you the diagram's *intent* (what it must
show) and the deliverable asset dir (`docs/assets/`, where the diagram is delivered). Your job: produce one `.drawio`
source plus a rendered **PNG** image there, then hand the image path back. You do NOT edit the
deliverable prose, place the figure in the document, or assign a figure number — the renderer
numbers figures at export, and `apply` writes the `![caption](assets/<file>)` reference. You make
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
- **One picture, rendered to a high-resolution PNG.** The output is a `.drawio` source + a
  rendered **PNG** (high-DPI raster). Store BOTH in the deliverable-side `docs/assets/` dir — the PNG is what
  the deliverable embeds, the `.drawio` is the editable source that makes the image regenerable.
  **Why PNG, not SVG:** draw.io's SVG export wraps labels in `foreignObject` (HTML) or packs the
  whole canvas as one base64 `<image>` PNG; the default Typst track's renderer (resvg) does NOT
  composite embedded PNGs or support `foreignObject`, so a drawio "SVG" collapses to a **solid
  black box** with the labels gone. A high-DPI PNG embeds reliably on the default Typst track (and
  on the LaTeX track). Render at `--width 2400`+ so the raster stays crisp. Never embed raw TikZ,
  raw `{=latex}`, or mermaid in the deliverable; the diagram travels as an image.
- **Legible at column width — labels must survive the squeeze.** The PNG is scaled to fit the
  document's text column (~160mm on A4), and a raster's text can't be re-enlarged afterwards. So
  the labels' on-page size is set entirely by **label-height ÷ canvas-width**. Keep that ratio
  **≥ 1.5%** (→ ≥7–8pt on the page; **5pt is the absolute floor**, target 10pt at ~2.2%). Concretely:
  on a ~1000–1200px-wide canvas use **14–16px label text**, never the 12px default on a wide canvas.
  **Keep diagrams compact — ≤ 7–10 nodes;** if it needs more, **split it into 2–3 figures** (A/B/C)
  rather than one dense mega-diagram whose labels vanish when scaled. A genuinely wide diagram
  (much wider than tall) should be **split or handed back flagged "needs landscape/full-page"** —
  don't let it be squeezed into the column. Sans labels, weight ≥ 400, contrast ≥ 4.5:1.
- **Connectors must stay legible — jumps at crossings, no occlusion.** Two connectors that cross MUST
  use a line **jump** (`jumpStyle=arc` with a `jumpSize`, in the edge `style`) so one visibly hops over
  the other instead of merging into an ambiguous intersection. Route edges so they do NOT pass over
  (occlude) an unrelated node or its label: use `edgeStyle=orthogonalEdgeStyle`, spread connection points
  with `exitX/exitY`/`entryX/entryY` when a node has 2+ connectors, and add `<Array as="points">`
  waypoints to steer an edge around a shape. A diagram whose lines cross without jumps or run through
  boxes reads as a tangle — fix it before the final render (the vision self-check looks for exactly this).
- **You author the picture, not the document.** No figure numbers, no cross-section references,
  no captions baked into prose. Hand back the image path and a one-line description of what it
  shows; the main agent places it.
- **Validate before you render.** A wrong `source`/`target` id or a dangling edge renders as a
  silently broken picture. Run `scripts/validate.py` first; fix every error before exporting.
- **Render small, review, converge.** Export a preview, LOOK at it (vision), fix the obvious
  defects, then export the final PNG. Diagram quality is something you SEE — do not declare a
  diagram done from the XML alone.
- **Degrade honestly.** If the draw.io CLI is missing or crashes, do NOT fake an image. Emit the
  browser-fallback URL (or the `.drawio` XML alone) and say so, so the main agent can decide.

---
## The Rhythm — author → validate → render → self-check → converge
1. **Plan.** Identify the shapes, the relationships, the layout direction (LR or TB), and the
   groups (tiers/layers). Keep it to what the intent needs — docspec diagrams are architecture /
   flow / sequence / state figures, not decorative art.
2. **Generate** the `.drawio` XML to `docs/assets/<name>.drawio`. Hand-place
   coordinates (snap to multiples of 10; scale spacing with node count). Use the draw.io XML
   skeleton below.
3. **Validate** — `python3 scripts/validate.py docs/assets/<name>.drawio`. Fix every
   error (warnings are advisory). Re-run until clean. Known noise: on sequence diagrams the
   pinned vertical lifelines always trip the "floating endpoint" warning — that's expected
   on lifelines, not a defect to fix.
4. **Render a preview** — `drawio -x -f png --width 2000 -o docs/assets/<name>.png <name>.drawio`
   (NO `-e`; cap width so vision can read it). Render the preview straight to the final
   destination — the final high-DPI render (step 6) overwrites it, so no intermediate file is
   left anywhere; never write render output to the system temp dir.
5. **Self-check (vision).** Read the preview PNG. Catch overlaps, clipped labels, missing
   connections, off-canvas shapes, **edges that occlude an unrelated node/label, and crossings rendered
   without a jump** (ambiguous intersections). Apply targeted XML fixes (waypoints, spread exit/entry,
   add `jumpStyle`) and re-render. Max 2 rounds, then proceed. (No vision model → skip this step.)
6. **Final render → PNG** — `drawio -x -f png --width 2400 -o docs/assets/<name>.png
   <name>.drawio` (high-DPI raster; no `-e` — that's SVG/PDF-only). The deliverable embeds the
   PNG; the `.drawio` stays beside it as the regenerable source of truth.
7. **Hand back** the PNG path + a one-line description of what the diagram shows. If the diagram
   genuinely cannot fit a single column (much wider than tall), say so explicitly — "needs
   full-page / landscape" — so the main agent records that layout intent (it raises a `docspec
   audit` finding) instead of letting it vanish at the handoff. Done.

**If the draw.io CLI is unavailable** (not installed, or crashes / empty output in a sandbox):
do not retry in a loop. Run `python3 scripts/encode_drawio_url.py <name>.drawio` for a browser
URL the user can open to view/export, or hand back the `.drawio` XML alone, and tell the main
agent rendering needs `docspec setup --with-drawio` (or a system draw.io install).

---
## Layout & routing — the part that makes or breaks readability
A structurally-correct but tangled diagram is a FAILED diagram. Two distinct jobs:

**Placing nodes (when you control the layout).** Lay the graph out so edges mostly flow one way:
- **Layer by data-flow direction.** Producers on one side, consumers on the other; commands flow one
  way across the page, status/returns the other. The reader should SEE the flow, not hunt it.
- **Align high-coupling pairs.** The two nodes that exchange the most edges go adjacent, on the same
  row/column — their trunk becomes one short straight line, not a diagonal across the canvas.
- **Render a chain as a straight line.** An A→B→C pipeline = one column (TB) or one row (LR); don't zigzag.
- **Give a long return edge its own channel.** A feedback/status edge that travels far runs in a
  dedicated horizontal/vertical lane *below or beside* the boxes — never back through the node cluster.
- Past ~7–10 nodes the layout cannot stay clean (see the stance) — split into A/B/C with a shared seam node.

**Re-routing on a FROZEN layout (the user says "keep my layout, just clean the lines").** You may move
*edges* but NOT *boxes*:
- **Parallel channels:** when several edges share a corridor, give each its own offset lane
  (x = 400 / 460 / 520 …) so they run parallel instead of weaving through one another.
- **Spread a node's connectors** across its perimeter with `exitX/exitY`/`entryX/entryY` — never let 3
  edges enter one point and knot.
- Separate the **eliminable** crossing (re-routable) from the **position-forced** one (the fixed boxes
  make it unavoidable). Re-route the first; **jump** the second (`jumpStyle=arc`) and stop — chasing
  zero crossings on a frozen layout is wasted effort, the boxes would have to move.
- **Judge by the rendered image, NOT `validate.py`'s crossing count.** A frozen-layout re-route can
  leave the count unchanged while turning a knot into clean parallel lanes — that IS the win. Use vision.

**Label placement (raster text can't be nudged after export).** An edge label's position is
`mxGeometry relative="1"` with **`x ∈ [-1, 1]`** = fraction *along* the edge (−1 = source end, 0 =
middle, 1 = target end), plus an `<mxPoint as="offset">` = pixel nudge *perpendicular* to the edge.
These are NOT absolute coordinates — writing a canvas coordinate there throws the label off-screen.
When two edges share a corridor, push their labels apart with the `offset` so they don't stack. Verify
every label in the render.

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
<mxCell id="10" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;jumpStyle=arc;jumpSize=6;html=1;"
        edge="1" parent="1" source="2" target="3">
  <mxGeometry relative="1" as="geometry" />
</mxCell>
```
Keep `jumpStyle=arc;jumpSize=6;` on edges so crossings render as visible hops, not ambiguous merges.
Pin `exitX/exitY/entryX/entryY` when a node has 2+ connections (spread them across the perimeter);
add `<Array as="points">` waypoints when an edge must route around an unrelated shape (avoid occlusion).

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
# Preview PNG (step 4) — width-capped for vision; same destination, the final render overwrites it
drawio -x -f png --width 2000 -o docs/assets/<name>.png docs/assets/<name>.drawio
# Final PNG (step 6) — high-DPI raster; this is the deliverable image
drawio -x -f png --width 2400 -o docs/assets/<name>.png docs/assets/<name>.drawio
# Linux headless: prefix with  xvfb-run -a  ; running as root in CI: append  --no-sandbox  at the very end
```
Key flags: `-x` export · `-f {png,svg,pdf}` format · `--width <px>` raster width (no `-s` with it) ·
`-o` output path · `-b 10` border. The deliverable image is **PNG** (see the stance: drawio SVGs go
black under the Typst track).

**Guardrail — `bad option: -x` / the CLI ignores export flags:** the draw.io binary is being run as
Node, not as the app. Clear the inherited `ELECTRON_RUN_AS_NODE` env var before invoking it
(`env -u ELECTRON_RUN_AS_NODE drawio …` on POSIX; `$env:ELECTRON_RUN_AS_NODE=$null` then call it on
Windows PowerShell) and retry.

**Guardrail — `bad option: -x` even after PATH/binary looks right:** the cause is almost always the
`ELECTRON_RUN_AS_NODE` env var above, NOT the draw.io version — clear it FIRST and retry. The version
is rarely the culprit: a managed draw.io reporting v24.x still accepts `-x -f` fine once the env var is
cleared. Only after clearing `ELECTRON_RUN_AS_NODE` and STILL getting `bad option` should you suspect a
genuinely stale/ancient system install — then prefer the docspec-managed binary from
`docspec setup --with-drawio` (it pins the release) and point `DOCSPEC_DRAWIO` at it.

---
## Guardrails
**Do**
- Take the intent + target section from the main agent; produce ONE `.drawio` + its rendered PNG.
- Run `scripts/validate.py` before rendering; fix every error.
- Render a width-capped preview and self-check it with vision before the final PNG.
- Store BOTH the `.drawio` source and the rendered PNG in `docs/assets/`.
- Hand back the PNG path + a one-line description; let the main agent place the figure.
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
