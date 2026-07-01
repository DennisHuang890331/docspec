---
name: dspx-release
description: Enter release mode — the interactive typesetting gate AFTER publish that turns
  a frozen snapshot into a delivered PDF. Use when a published document needs to be typeset
  for delivery. Unlike the content skills, it touches ONLY the format layer (the template
  pack), never a word of content, and converges over rounds with the human in every round.
license: PolyForm-Noncommercial-1.0.0
compatibility: Requires the docspec CLI with the export extra (pandoc + the bundled typst binary for the default track), pdfplumber, and pypdfium2. The journal track is emit-only (it produces a `.tex` for an external toolchain like Overleaf, docspec does not compile it); local journal compilation is optional and on-demand (`docspec setup --with-latex`).
metadata:
  author: docspec
  version: "2.0"
---
## STEP 0 — do this FIRST, every time
> **If `docspec` is not found** — it IS installed (via `uv tool`); your shell's PATH just predates the install (a freshly-launched or sandboxed agent shell). Don't conclude it's missing: run the binary directly from the uv tools bin dir (normally `~/.local/bin/docspec`, Windows `%USERPROFILE%\.local\bin\docspec.exe`; `uv tool dir --bin` prints it), or restart your terminal so the install's PATH update takes effect.

Run `docspec guide` and `docspec instructions release <section>` before acting. The mechanics —
the export/proof commands, the validated `--format-config` knobs (their names, enums, ranges),
the byte-lock check, where the deliverable lands — live there, projected live from the schema and
CLI; assume they may have changed since this file was written. The format knobs and where the
deliverable lands live in `docspec guide`; a custom journal pack supplied via `--template <dir>` may
ship its own craft notes, readable with `docspec reference --template <dir>` (the bundled Typst pack
ships none — all of its format control is exposed as validated knobs). **This skill gives you only
STANCE.** Don't restate knob names or guess them from memory. The engine is your backstop: a bad knob
value is refused before any markup is generated, and byte-lock refuses a PDF whose content drifted
from the snapshot.

---
You run the **interactive typesetting gate**. Publish froze the content; **release lays it out.**
You take a published, immutable snapshot and typeset it into a delivered PDF, running a tight loop
with the human: export produces the PDF, proof renders it to page images, you and the human READ
those images together, agree what to adjust, you change ONLY the **format layer**, then re-export
and re-proof until it looks right. The snapshot's bytes never move.

**This is a procedure with a loop, not a free stance.** Like `edit` and `publish` it has an ordered
mechanism (export → proof → look → adjust → repeat). Unlike them it is *interactive and iterative*:
it converges over rounds, with the human in every round, because typesetting quality is something
humans see and judge, not something the engine gates.

> Where it sits: `… → publish (freeze) → release (typeset)`. Release runs **only after** a snapshot
> exists; it never publishes, never edits content, never re-opens the loop. Its output —
> `docs/exports/…` — is a **derived** artifact: regenerable, deliberately outside `archive/`, never
> frozen, never gating. Delete it and re-run; nothing is lost.

---
## The Stance — the iron laws
- **Format only — never content.** The content's one source is the frozen snapshot md. The
  generated render source (the `.typ`, or the journal track's `.tex`) is throwaway — never hand-edit
  it, never patch the PDF, never "just tweak this
  sentence so it fits." If you find yourself wanting to change a word, STOP — that is the next law.
- **A layout problem you can only fix by changing content → route upstream, don't self-fix.** A
  table too wide because the *content* has too many columns; an overlong heading; a claim that must
  be reworded. Raise an audit finding (or hand it to the human); the human takes it back through
  `edit` → `publish` → `release`. Release reports and waits; it never reaches into content.
- **Reach for the validated format knobs FIRST.** Express a layout change as *values* in a
  `--format-config` YAML (page/font/size/leading/table/code/…). docspec validates every value and
  deterministically compiles it into a renderer override — a bad value is refused before any markup
  exists, so a hallucinated setting can never reach the renderer (typst, or xelatex on the journal
  track). This is the default tool for the loop's "adjust format" step. (The exact knob set is in
  `docspec guide`; don't memorize it here.)
- **Escape hatch, flagged-risk: hand-edit the template pack only when no knob covers it.** You may
  edit the pack's *existing* declarative parameters — for the bundled Typst pack that is its
  `template.typ`; for a BYO journal pack (`--template <dir>`) its own template files. This raw
  template code is **not** validated, so prefer a knob whenever one fits; when you must, change the
  smallest existing parameter — never author a fresh template body, never pixel-place, never write a
  per-document one-off layout script. **The engine may refuse an export that touches a bundled pack
  without an explicit acknowledgement** — that gate is on purpose; don't route around it.
- **Changing the look wholesale = swap the pack (`--template`), not a pile of overrides.** A
  different visual format is a different *pack*. Read its class/sample once, author a pandoc bridge a
  single time, then every future export through that pack is deterministic. One careful bridge, then
  mechanical reuse.
- **BYO journal template (`--engine journal --template <dir>`): the bridge MUST follow the journal's
  own sample `.tex`, not a generic guess.** A journal class exposes *its own* metadata macros — IET
  uses `\author{\au{Name$^1$}…}` + `\address{\add{1}{…}\email{…}}` + `\begin{abstract}` before
  `\maketitle`; Elsevier `cas-dc` uses `\author[1]{Name}` + `\ead{}` + `\affiliation[1]{organization={…}}`
  + `\begin{abstract}`/`\begin{keywords}…\sep…`; IEEEtran uses `\author{\IEEEauthorblockN{…}…}`. Open
  the template's bundled sample/author `.tex` (e.g. `Author_tex.tex`, `cas-dc-sample.tex`) and map the
  slot contract (title / authors.name·affiliation·email / abstract / keywords / body) onto **exactly
  those macros**, in the order and nesting the sample shows. Wrong macros → the class silently drops
  the field or miscompiles. The bundled `ieee`/`elsevier`/`iet` adapters are the worked examples; a new
  journal's bridge is authored the same way — from its sample, once.
- **Journal track emits one `.tex`; front matter lives in the macros, not twice.** The slot contract
  feeds title/authors/abstract/keywords into the class macros; the body must NOT also repeat the author
  block or the Abstract/Keywords sections (a real journal `.tex` never does). docspec strips that
  leading front matter from the body automatically when those slots are supplied — keep the body
  starting at the first real section (Introduction). Provide author/abstract/keywords via `--slots`, not
  buried only in the prose. The emitted `.tex` is compiled by the journal's toolchain (Overleaf), not by
  docspec.
- **Diagnose by measuring, not by eye.** When a font-size change "didn't take," run
  `docspec measure-fonts <pdf>` and read the dominant size — don't guess from the proof image.

---
## The Rhythm — the loop (the heart of this skill)
You converge over rounds; the human is in every round.
1. **Export** the published snapshot → a PDF (`--version X.Y.Z`, or `--latest` for a not-yet-published
   preview). If a dependency is missing, surface the hint — don't fake a PDF.
2. **Proof** → renders every page to a PNG and prints the paths.
3. **Look — together.** READ the page images (that is the whole point of proof: the engine cannot see
   a table overprinting, a column collision, or a **broken / blank figure image**). Walk the pages with
   the human and name concrete defects.
4. **Classify each defect** before touching anything: **format** (size, spacing, margin, rule weight,
   font) → adjust the format layer, stay in the loop; **content** (only fixable by changing
   words/structure) → route upstream, do NOT paper over it with format.
5. **Adjust the format layer** — express format defects as validated `--format-config` knobs first;
   reach for the pack escape hatch only when no knob covers it.
6. **Re-export, re-proof** and repeat. The proof scratch dir is cleared each run, so what you see is
   always the current PDF.
7. **Converge** when the human says the layout is good. The snapshot is unchanged; the deliverable
   PDF is the only new thing.

**Broken diagram → route upstream (diagrams are embedded images, authored upstream).** Diagrams travel
as raster images: a subagent loading the `dspx-diagram` skill authors a `.drawio` + its rendered PNG into
the section's `assets/` upstream in `draft`, and the deliverable embeds the PNG (drawio's SVG export
collapses to a black box under the Typst track, so the embedded image is a PNG). Release does NOT draw,
re-draw, or hand-edit a diagram — there is **no sanctioned raw-LaTeX** here any more (TikZ and the
mermaid→TikZ swap are retired). If a figure looks wrong in proof (blank box, clipped, stale, wrong
content), that is a content/asset defect: **route it upstream** — the human takes it back through
`draft`, where the diagram subagent re-renders the image; then re-publish and re-release. A genuinely
format-level figure issue (the image is correct but too large / poorly placed on the page) is the only
kind you handle here, and you handle it with the validated format knobs (image sizing), never by
editing the picture.

---
## Guardrails
**Do**
- Run the loop in order: export → proof → look (with the human) → classify → adjust format → repeat.
- Read the proof images yourself every round — the defects you fix are the ones you can SEE.
- Reach for the validated `--format-config` knobs first; keep content byte-locked.
- Use the pack hand-edit only as an escape hatch when no knob fits, changing the smallest parameter.
- Route a broken/blank/wrong diagram upstream — diagrams are images authored by the `dspx-diagram` subagent in `draft`; never redraw at release.
- Route any content-only blocker upstream as an audit finding; let the human re-edit → re-publish.
- Measure with `docspec measure-fonts` instead of guessing font sizes by eye.

**Don't**
- Don't change content — not a word, not a number; the snapshot is the one source and is read-only.
- Don't hand-edit the generated render source (`.typ` / `.tex`), patch the PDF, or build the document programmatically.
- Don't write raw template code from scratch or pixel-place — prefer the knobs; hand-edit existing
  pack parameters only when no knob fits; swap the whole pack for a different look. (Diagrams are
  upstream-authored images now — there is no sanctioned raw-LaTeX diagram authoring at release.)
- Don't hand-write a preamble line for something a knob already covers — that bypasses validation.
- Don't route around the bundled-pack acknowledgement gate; it is there on purpose.
- Don't substitute non-bundled CJK faces; use the bundled redistributable faces (the house style
  is unified 思源宋體 + Source Serif 4 + Source Code Pro, validated for a clean PDF text layer).
- Don't touch any `archive/` snapshot, and don't treat the derived PDF as if it were frozen.
- Don't self-evaluate or victory-lap — present the proofed pages and hand back; the human judges.

---
## Example
Human: "v1.2.0 is published — typeset it for delivery."

> **release — handbook v1.2.0 · Round 1**
> - Export v1.2.0 → PDF (content byte-locked ✓). Proof → 9 page PNGs.
> - Look (together): p.3 eligibility table rules are heavy and the body feels dense; p.6 a 7-column
>   matrix overflows the right margin.
> - Classify: table rules + body density = **format** → knobs. The 7-column overflow can't fit any
>   page at readable size = **content** (too many columns) → route upstream.
> - Adjust: a `--format-config` bumping leading and lightening table rules. Leave the matrix alone.
> - Route upstream: raise an audit finding on the matrix — split or transpose in `edit`, then re-publish.
>
> **Round 2** — re-export, re-proof: p.3 and body read cleanly; the matrix is the open finding, the
> human's call. Hand back: layout is clean except the matrix, which is upstream. Awaiting the human.

Export, proof, look, fix only the format, route content upstream, converge — the content never moved
and the PDF looks right.
