---
name: dspx-release
description: >-
  Fix the layout of an exported PDF — only when the human says something in it looks wrong.
  Producing the PDF is one command (`docspec export <article>`) and needs no skill; this skill is
  the adjustment loop: look at the named pages together, classify each defect as format or content,
  change only the validated format knobs, re-export. Never edits content, never runs unprompted.
license: PolyForm-Noncommercial-1.0.0
compatibility: Requires the docspec CLI with the export extra (pandoc + the bundled typst binary for the default track), pdfplumber, and pypdfium2; installed via uv tool — not on PATH in a fresh shell, run it from the dir printed by `uv tool dir --bin`, never reinstall. The journal track is emit-only (it produces a .tex for an external toolchain like Overleaf, docspec does not compile it); local journal compilation is optional and on-demand (`docspec setup --with-latex`).
metadata:
  author: docspec
  version: "3.0"
---

A PDF is one command: `docspec export <article>` (latest frozen version; `--latest` for the working copy), using the project's `export` settings. Hand the PDF to the human and stop. Only when they say something looks wrong do you run this loop — and only for what they named. `docspec guide` carries the validated `--format-config` knobs, enums and ranges; a bad value is refused before anything renders.

**Input**: the human's complaint about an exported PDF ("the table on page 4 overflows", "headings too big").

**Steps**

1. **See it** — `docspec proof <article>` renders the pages to PNGs; open the pages the human named and confirm the defect. Measure (the proof output lists font sizes) rather than guess.
2. **Classify** — **format** (size, spacing, margins, rules, fonts, image size) → fix here. **Content** (only fixable by changing words or structure: an overlong heading, a table too wide at any readable size, a wrong or blank figure) → raise it with `docspec audit` for `dspx-apply` / `dspx-diagram`, and tell the human; do not paper over it with format.
3. **Adjust the format layer** — validated knobs first: the project's `export.format` in `config.yaml` (lasting) or `--format-config <file>` (this document only). A whole different look = another profile (`--profile`) or template pack (`--template <dir>`). Hand-editing a bundled pack parameter is the last resort, smallest change only.
4. **Re-export and show** — `docspec export <article>` again, `docspec proof`, show the human the same pages. Stop when they are satisfied; do not start further rounds on your own.

**Output**

```
## release — <article> v<X.Y.Z>
Complaint: <what the human named>
Cause: <format → knob changed | content → audit finding raised>
Result: <re-exported PDF path; pages shown>
```

**Guardrails**
- Format only — never change a word or number of content; frozen snapshots are read-only.
- Never start a layout loop the human did not ask for; one export, then wait.
- Knobs before pack edits; never hand-edit generated `.typ`/`.tex`, patch the PDF, or bypass the bundled-pack acknowledgement gate.
- Keep the bundled CJK faces (思源宋體 + Source Serif 4 + Source Code Pro); don't substitute non-bundled fonts.
