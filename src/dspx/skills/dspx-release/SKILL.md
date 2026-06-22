---
name: dspx-release
description: Enter release mode — the interactive typesetting gate AFTER publish that turns
  a frozen snapshot into a delivered PDF. Use when a published document needs to be typeset
  for delivery. Unlike the content skills, it touches ONLY the format layer (the template
  pack), never a word of content, and converges over rounds with the human in every round.
license: PolyForm-Noncommercial-1.0.0
compatibility: Requires the docspec CLI with the export extra (pandoc + controlled TinyTeX/xelatex), pdfplumber, and pypdfium2.
metadata:
  author: docspec
  version: "2.0"
---
## STEP 0 — do this FIRST, every time
Run `docspec guide` and `docspec instructions release <section>` before acting. The mechanics —
the export/proof commands, the validated `--format-config` knobs (their names, enums, ranges),
the byte-lock check, where the deliverable lands — live there, projected live from the schema and
CLI; assume they may have changed since this file was written. For pack-editing craft (TikZ idioms,
LaTeX traps) run `docspec reference`. **This skill gives you only STANCE.** Don't restate knob
names or guess them from memory. The engine is your backstop: a bad knob value is refused before any
LaTeX is generated, and byte-lock refuses a PDF whose content drifted from the snapshot.

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
  generated `doc.tex` is throwaway — never hand-edit it, never patch the PDF, never "just tweak this
  sentence so it fits." If you find yourself wanting to change a word, STOP — that is the next law.
- **A layout problem you can only fix by changing content → route upstream, don't self-fix.** A
  table too wide because the *content* has too many columns; an overlong heading; a claim that must
  be reworded. Raise an audit finding (or hand it to the human); the human takes it back through
  `edit` → `publish` → `release`. Release reports and waits; it never reaches into content.
- **Reach for the validated format knobs FIRST.** Express a layout change as *values* in a
  `--format-config` YAML (page/font/size/leading/table/code/…). docspec validates every value and
  deterministically compiles it into a LaTeX override — a bad value is refused before any LaTeX
  exists, so a hallucinated setting can never reach xelatex. This is the default tool for the loop's
  "adjust format" step. (The exact knob set is in `docspec guide`; don't memorize it here.)
- **Escape hatch, flagged-risk: hand-edit the template pack only when no knob covers it.** You may
  edit the pack's *existing* declarative parameters (`preamble.tex`, `docspec-tables.lua`,
  `before.tex`). This raw LaTeX is **not** validated, so prefer a knob whenever one fits; when you
  must, change the smallest existing parameter — never author a fresh `.tex` body, never pixel-place,
  never write a per-document one-off layout script. **The engine may refuse an export that touches a
  bundled pack without an explicit acknowledgement** — that gate is on purpose; don't route around it.
- **Changing the look wholesale = swap the pack (`--template`), not a pile of overrides.** A
  different visual format is a different *pack*. Read its class/sample once, author a pandoc bridge a
  single time, then every future export through that pack is deterministic. One careful bridge, then
  mechanical reuse.
- **Diagnose by measuring, not by eye.** When a font-size change "didn't take," run
  `docspec measure-fonts <pdf>` and read the dominant size — don't guess from the proof image.

---
## The Rhythm — the loop (the heart of this skill)
You converge over rounds; the human is in every round.
1. **Export** the published snapshot → a PDF (`--version X.Y.Z`, or `--latest` for a not-yet-published
   preview). If a dependency is missing, surface the hint — don't fake a PDF.
2. **Proof** → renders every page to a PNG and prints the paths.
3. **Look — together.** READ the page images (that is the whole point of proof: the engine cannot see
   a table overprinting, a column collision, or a **mermaid placeholder box**). Walk the pages with
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

**Mermaid → TikZ** (a notation translation, once per diagram): pandoc cannot draw mermaid, so the
template renders each ` ```mermaid ` block as a visible placeholder box. When you see one, run
`docspec reference tikz` for the idiom library and pre-loaded styles, then write the *equivalent*
diagram as a native-TikZ raw-LaTeX block in the throwaway working copy. **This is the one raw-LaTeX
you are sanctioned to author** — it is a presentation-layer notation swap, not a content change. If
you change what the diagram *says* (new state, renamed node) → route upstream.

---
## Guardrails
**Do**
- Run the loop in order: export → proof → look (with the human) → classify → adjust format → repeat.
- Read the proof images yourself every round — the defects you fix are the ones you can SEE.
- Reach for the validated `--format-config` knobs first; keep content byte-locked.
- Use the pack hand-edit only as an escape hatch when no knob fits, changing the smallest parameter.
- Translate each mermaid box into an equivalent TikZ figure (`docspec reference tikz`), once per diagram.
- Route any content-only blocker upstream as an audit finding; let the human re-edit → re-publish.
- Measure with `docspec measure-fonts` instead of guessing font sizes by eye.

**Don't**
- Don't change content — not a word, not a number; the snapshot is the one source and is read-only.
- Don't hand-edit the generated `doc.tex`, patch the PDF, or build the document programmatically.
- Don't write raw LaTeX from scratch or pixel-place — prefer the knobs; hand-edit existing pack
  parameters only when no knob fits; swap the whole pack for a different look. (The one sanctioned
  raw-LaTeX you author is the per-diagram mermaid → TikZ translation.)
- Don't hand-write a preamble line for something a knob already covers — that bypasses validation.
- Don't route around the bundled-pack acknowledgement gate; it is there on purpose.
- Don't bundle proprietary fonts; use the bundled redistributable faces (some "kai" faces corrupt
  the PDF text layer).
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
