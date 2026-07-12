# dspx-diagram reference — the mechanical craft

The `dspx-diagram` SKILL.md holds the driver loop and stance. This file holds the mechanics the
subagent needs while authoring: the XML skeleton, shape/edge/palette tables, layout & routing rules,
label placement, and the export commands + troubleshooting. Read the whole file before authoring.

(The two vendored helpers next to the skill — `scripts/validate.py` and
`scripts/encode_drawio_url.py` — are vendored from the MIT-licensed Agents365 draw.io skill; see
`scripts/NOTICE.md`.)

## Why PNG, not SVG

draw.io's SVG export wraps labels in `foreignObject` (HTML) or packs the whole canvas as one base64
`<image>`; the default Typst track's renderer (resvg) does NOT composite embedded PNGs or support
`foreignObject`, so a drawio "SVG" collapses to a **solid black box** with the labels gone. A high-DPI
PNG embeds reliably on the default Typst track (and on the LaTeX track). Render at `--width 2400`+ so
the raster stays crisp. Never embed raw TikZ, raw `{=latex}`, or mermaid — the diagram travels as an
image.

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
- Past ~7–10 nodes the layout cannot stay clean — split into A/B/C with a shared seam node.

**Re-routing on a FROZEN layout (the user says "keep my layout, just clean the lines").** Move
*edges* but NOT *boxes*:
- **Parallel channels:** when several edges share a corridor, give each its own offset lane
  (x = 400 / 460 / 520 …) so they run parallel instead of weaving through one another.
- **Spread a node's connectors** across its perimeter with `exitX/exitY`/`entryX/entryY` — never let 3
  edges enter one point and knot.
- Separate the **eliminable** crossing (re-routable) from the **position-forced** one (the fixed boxes
  make it unavoidable). Re-route the first; **jump** the second (`jumpStyle=arc`) and stop — chasing
  zero crossings on a frozen layout is wasted effort.
- **Judge by the rendered image, NOT `validate.py`'s crossing count.** A frozen-layout re-route can
  leave the count unchanged while turning a knot into clean parallel lanes — that IS the win. Use vision.

**Label placement (raster text can't be nudged after export).** An edge label's position is
`mxGeometry relative="1"` with **`x ∈ [-1, 1]`** = fraction *along* the edge (−1 = source end, 0 =
middle, 1 = target end), plus an `<mxPoint as="offset">` = pixel nudge *perpendicular* to the edge.
These are NOT absolute coordinates — a canvas coordinate there throws the label off-screen. When two
edges share a corridor, push their labels apart with the `offset`. Verify every label in the render.

## Validation notes

Run `python3 scripts/validate.py docs/assets/<name>.drawio` before every render; fix every error
(warnings are advisory). Known noise: on sequence diagrams the pinned vertical lifelines always trip
the "floating endpoint" warning — that's expected on lifelines, not a defect to fix.

## Export reference (resolve the binary first)

The CLI is named `drawio` (Homebrew cask, Linux packages) or, on older installs, `draw.io`; on macOS
the bundle binary is `/Applications/draw.io.app/Contents/MacOS/draw.io`; on Windows
`"C:\Program Files\draw.io\draw.io.exe"`. Resolve which one prints `--version` and use it verbatim. A
**docspec-managed** draw.io (from `docspec setup --with-drawio`) lives under docspec's `data_dir/drawio/`
(Windows `draw.io.exe`, macOS `draw.io.app/Contents/MacOS/draw.io`, Linux `drawio.AppImage`); if nothing
is on PATH, look there or point `DOCSPEC_DRAWIO` at it. If draw.io is absent entirely, fall back to
`scripts/encode_drawio_url.py` (browser) or hand back the XML.

```bash
# Preview PNG (step 4) — width-capped for vision; same destination, the final render overwrites it
drawio -x -f png --width 2000 -o docs/assets/<name>.png docs/assets/<name>.drawio
# Final PNG (step 6) — high-DPI raster; this is the deliverable image
drawio -x -f png --width 2400 -o docs/assets/<name>.png docs/assets/<name>.drawio
# Linux headless: prefix with  xvfb-run -a  ; running as root in CI: append  --no-sandbox  at the very end
```

Key flags: `-x` export · `-f {png,svg,pdf}` format · `--width <px>` raster width (no `-s` with it) ·
`-o` output path · `-b 10` border. The deliverable image is **PNG** (drawio SVGs go black under the
Typst track).

**Troubleshooting — `bad option: -x` / the CLI ignores export flags:** the draw.io binary is being run
as Node, not as the app. Clear the inherited `ELECTRON_RUN_AS_NODE` env var before invoking it
(`env -u ELECTRON_RUN_AS_NODE drawio …` on POSIX; `$env:ELECTRON_RUN_AS_NODE=$null` then call it on
Windows PowerShell) and retry. This is almost always the cause — NOT the draw.io version: a managed
draw.io reporting v24.x still accepts `-x -f` fine once the env var is cleared. Only after clearing it
and STILL getting `bad option` should you suspect a genuinely stale system install — then prefer the
docspec-managed binary (`docspec setup --with-drawio`, which pins the release) and point
`DOCSPEC_DRAWIO` at it.
