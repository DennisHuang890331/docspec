---
name: dspx-release
description: >-
  Interactive typesetting gate AFTER publish — turn a frozen snapshot into a delivered PDF. Export →
  proof to page images → read them WITH the human → adjust ONLY the format layer (validated knobs first)
  → re-export until it looks right. Unlike the content skills it touches no word of content (the
  template pack only), and it converges over rounds with the human in every round. Use when the
  human asks to typeset/export a published snapshot into a delivered PDF — never before publish,
  never self-initiated.
license: PolyForm-Noncommercial-1.0.0
compatibility: Requires the docspec CLI with the export extra (pandoc + the bundled typst binary for the default track), pdfplumber, and pypdfium2; installed via uv tool — not on PATH in a fresh shell, run it from the dir printed by `uv tool dir --bin`, never reinstall. The journal track is emit-only (it produces a .tex for an external toolchain like Overleaf, docspec does not compile it); local journal compilation is optional and on-demand (`docspec setup --with-latex`).
metadata:
  author: docspec
  version: "3.0"
---

Publish froze the content; release lays it out. You take a published, immutable snapshot and typeset it into a delivered PDF, running a tight loop with the human — the snapshot's bytes never move. `docspec guide` carries the export/proof commands and the validated `--format-config` knob names, enums, and ranges — read them there, don't guess from memory; a bad knob value is refused before any markup is generated.

**Input**: a published article (or `--latest` for a not-yet-published preview) to typeset. Release runs only after a snapshot exists; it never publishes, never edits content. Its output (`docs/exports/…`) is a derived, regenerable artifact — delete it and re-run, nothing is lost.

**Steps** — the loop; the human is in every round:

1. **Export** — `docspec export <article> --version <X.Y.Z>` (or `--latest`) → a PDF, content byte-locked. If a dependency is missing, surface the hint — don't fake a PDF.
2. **Proof** — `docspec proof <article>` renders every page to a PNG and prints the paths (the scratch dir is cleared each run, so what you see is the current PDF).
3. **Look — together** — READ the page images: the engine cannot see a table overprinting, a column collision, or a broken/blank figure. Walk the pages with the human and name concrete defects.
4. **Classify each defect before touching anything** — **format** (size, spacing, margin, rule weight, font) → adjust the format layer, stay in the loop; **content** (only fixable by changing words/structure) → route upstream, do NOT paper over it with format.
5. **Adjust the format layer** — express a format defect as validated `--format-config` knobs FIRST (a hallucinated setting can never reach the renderer — it's refused first). Escape hatch, flagged-risk: hand-edit the smallest existing pack parameter only when no knob covers it; a wholesale look change = swap the pack (`--template <dir>`), authoring the pandoc bridge ONCE from the journal's own sample `.tex` (its metadata macros in the order/nesting the sample shows). Provide author/abstract/keywords via `--slots`, and keep the body starting at the first real section.
6. **Re-export, re-proof, converge** — repeat until the human says the layout is good. Diagnose by MEASURING (font sizes / dominant body size are appended to `docspec proof` output), not by eye.

**Pause / route upstream if:**
- A layout problem is only fixable by changing content (an overlong heading, a matrix too wide for any page at readable size) → raise a `docspec audit` finding; the human takes it back through `apply` → `publish` → `release`. Release reports and waits; it never reaches into content.
- A figure looks wrong in proof (blank box, clipped, stale, wrong content) → that is a content/asset defect: route it upstream (the `dspx-diagram` subagent re-renders the image in `apply`), never redraw at release. Only a correct-but-too-large image is yours, handled with the image-sizing knobs.

**Output**

```
## release — <article> v<X.Y.Z> · Round N
- Export → PDF (content byte-locked ✓). Proof → M page PNGs.
- Look (together): <concrete defects>
- Classify: <format → knob | content → upstream>
- Adjust: <the --format-config change>
Converged / awaiting the human on: <open upstream findings>
```

**Guardrails**
- Format only — never a word or number of content; the frozen snapshot is the one source and is read-only.
- Reach for the validated `--format-config` knobs first; hand-edit an existing pack parameter only as an escape hatch, changing the smallest one; never author a fresh template body, pixel-place, or write a per-document layout script.
- Don't hand-edit the generated render source (`.typ` / `.tex`), patch the PDF, or route around the bundled-pack acknowledgement gate (it is there on purpose).
- Route a broken/blank/wrong diagram upstream — diagrams are images authored by the `dspx-diagram` subagent in `apply`; there is no sanctioned raw-LaTeX diagram authoring at release.
- Don't substitute non-bundled CJK faces — the house style is unified 思源宋體 + Source Serif 4 + Source Code Pro (validated for a clean PDF text layer).
- Don't touch any `archive/` snapshot, and don't treat the derived PDF as if it were frozen. Present the proofed pages and hand back — the human judges layout quality; don't self-evaluate.
