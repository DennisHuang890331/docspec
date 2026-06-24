# Changelog

All notable changes to docspec are recorded here. The project follows
[Semantic Versioning](https://semver.org/). In addition to the package version
(`pyproject.toml`), the **export-format / slot-contract surface** is versioned
independently (`dspx.slots.CONTRACT_VERSION`) so that changes to the journal slot
contract — which affect BYO journal templates downstream — are tracked with their
own semver: a breaking slot rename/removal is a major bump, an added optional slot
a minor bump.

## [Unreleased]

### Changed — PDF strategy pivot: Typst-default, dual-track binder

- **Typst is now the default render track.** docspec ships one owned `.typ` house-style
  template and a bundled lightweight `typst` binary (native CJK); `docspec setup` installs
  typst alongside pandoc and fonts. The engine-agnostic fidelity / byte-lock / proof checks
  run against the Typst PDF. Export `--engine {typst,journal}` selects the track
  (default typst); the project `export.engine` config sets a per-project default.
- **Content model is backend-neutral.** Diagrams are embedded images, not LaTeX-only TikZ.
- **Journal LaTeX track (BYO, emit-only).** `docspec export <article> --journal {ieee,elsevier}`
  (or `--engine journal --template <dir>`) feeds the content through a journal's own pandoc
  template via the **slot contract** and emits a `.tex` — docspec does NOT compile it (compile
  in Overleaf / the journal toolchain). New `--slots <file>` supplies authors/abstract/keywords.
  Render-time slot validation reports template-wanted-but-unknown and provided-but-unused slots.
  Bundled adapters: **IEEE** (IEEEtran), **Elsevier** (cas-dc), **IET** (cta-author) — all three
  verified by compiling the emitted `.tex` against the real journal classes. A shared journal-track
  Lua filter (`journal-tables.lua`) rewrites pandoc's `longtable` into a `tabular` `table*` so the
  two-column journal classes accept tables.

### Added

- **`dspx-diagram` support skill** (drawio): a lean, docspec-style stance skill loaded by a
  *delegated subagent* (draft/develop never load it themselves). Vendors the MIT-licensed
  Agents365 `validate.py` (structural lint) + `encode_drawio_url.py` (browser fallback).
  Diagrams are authored as `.drawio` and rendered to SVG, embedded backend-neutrally.
- **`docspec setup --with-drawio`** — optional managed draw.io desktop install (pinned v30.2.4,
  per-platform portable archive + sha256). Core `setup` stays typst + pandoc + fonts only.
  On Linux it detects X/Electron libs + xvfb and prompts to install them (Docker renderer noted
  as an alternative).
- **Slot contract** (`dspx.slots`) — a validated, closed named set (title / subtitle / authors /
  date / version / abstract / keywords / shorttitle / shortauthors / body) both emitters honor.
- **Image embedding** (Stage A) — sections embed images from `corpus/<section>/assets/`; a
  pre-render integrity check fails loud on a missing image reference; image hashes fold into the
  section's staleness fingerprint.

### Fixed — Typst typography

- The Typst template's heading ladder was oversized and the document title (hardcoded 20pt) was
  *smaller* than a level-1 section heading (1.45 × 14.5pt = 21pt) — an inverted hierarchy. Title is
  now the largest element (1.45em, scales with body) and the ladder is gentler (1.30/1.15/1.05em).
- The Typst track now uses its own house body size (sized for single-column A4) instead of inheriting
  the LaTeX cas-sc 14.5pt anchor (tuned for two-column journal LaTeX, oversized in Typst). The
  `font.base_size` knob still overrides it. Verified on real Chinese and English documents
  (思源宋體 CJK, tables, lists, EARS keywords — no tofu, correct hierarchy).

### Changed — diagram doctrine

- The native-TikZ and mermaid→TikZ doctrine is retired in favor of embedded drawio images.
  `draft` / `develop` / `release` stances updated; lint `Ve3` now flags both ```mermaid and raw
  `{=latex}`/`{=tex}` blocks (not backend-neutral; stripped on the Typst track) and points at the
  drawio image workflow.

### Removed — docspec-cas LaTeX class + `latex` render track

- **The bundled `docspec-cas` template pack is removed** (the modified Elsevier cas-sc LPPL class,
  its `preamble.tex` / `before.tex` / `docspec-tables.lua` mermaid filter / craft `reference.md` /
  fonts). The `--engine latex` track that compiled it is **retired**: it now errors with guidance to
  use `--engine typst` (default) or `--engine journal` (journal submission). PDFs are produced by the
  Typst track; LaTeX output is the emit-only journal track (compiled by the user, not docspec).
- **TinyTeX (xelatex) is kept** — it is the general LaTeX engine, a separate concern from the removed
  class; `docspec setup` still installs it for the journal toolchain.
- Removed paths helpers `bundled_template_dir()` / `resolve_template_dir()` / `REQUIRED_TEMPLATE_*`,
  export's LaTeX build path, and the format-config cas-sc LaTeX-emit functions (format_config.py now
  exposes only `validate_format_config` / `compile_typst_vars` / `pandoc_highlight_style` /
  `pandoc_table_metavars` plus helpers).
