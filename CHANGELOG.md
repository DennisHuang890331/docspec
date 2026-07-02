# Changelog

All notable changes to docspec are recorded here. The project follows
[Semantic Versioning](https://semver.org/). In addition to the package version
(`pyproject.toml`), the **export-format / slot-contract surface** is versioned
independently (`dspx.slots.CONTRACT_VERSION`) so that changes to the journal slot
contract — which affect BYO journal templates downstream — are tracked with their
own semver: a breaking slot rename/removal is a major bump, an added optional slot
a minor bump.

## [Unreleased]

### Added — bundled writing-style reference + language-seeded writing guide

- **`docspec reference writing-zh` / `writing-en`**: docspec now ships a writing-style reference
  (naturalness / anti-translationese for Chinese, anti-AI-tell for English), each claim traceable to
  a cited source, merged with the template-pack craft reference under `docspec reference`. Consulted
  by `develop` when drafting a project's writing-guide "Project conventions" section.
- **`docspec init --lang zh-TW/en` seeds naturalness rules** directly into the new project's
  `writing-guide.md` (via `build_writing_guide(lang)`), instead of leaving language-universal rules
  for `develop` to fill in later. Genre-specific bullets stay fill-in placeholders.

### Added — deliverable-cleanliness lint rules V16 / V17 (both WARN)

- **V16 (zh)**: flags a normative escape-hatch hedge word (`最好`/`儘量`/`酌情`/`如有可能`/`視情況`/
  `最大限度`) in the same sentence as a normative keyword (`應`/`不得`) — an unconditional requirement
  softened into an unverifiable one. `必要時` is deliberately excluded (a legitimate EARS-style
  conditional trigger, confirmed by ground-truthing against real corpora). WARN, never blocks.
- **V17 (en)**: a closed, ground-truthed English "AI-ism" trigger set (delve, tapestry, boasts,
  showcases, seamless, `utilize`-verb-forms, testament to, a myriad of, plethora, `in the realm of`,
  `navigate the complexities of`, `underscores the/that/…`, `leverage`-verb-forms, and the
  sentence-initial "In today's …" opener). `robust` and bare `leverage`/`realm`/`navigate`/
  `underscores`/`utilization` are excluded — refuted or narrowed by real accepted corpora.
- **Lint findings now carry a section locator**: V1–V4/V12/V13/V15/V16/V17 report
  `docs/<article>/_latest.md § <section-path>` instead of file-level only, so an editor can jump
  straight to the section; dedup unit becomes per-section.

### Added — CLI discoverability & authoring seams

- `docspec ready <article>` (batch graduation, per-section independent transactions); `ready`'s
  missing-`decisions.yaml` error now hints that an empty `entries: []` is legal.
- `docspec show <section-path>` (look up a section's ids by path, not just by id); `show` now prints
  `governed-by`.
- `docspec new` seeds the generated id / title / order into the scaffolded `develop.md` header.
- Optional `<article>` positional scope on `check` / `lint` / `list` / `status` (`check` never
  filters its errors/exit code — scope applies only to the green-path id index, no false-green).
- `docspec list` shows group nodes with their localized titles and a `kind` field on every JSON row.
- `docspec publish <article> --dry-run` (consolidated go/no-go pre-publish report, no freeze).
- `docspec audit summary [<article>]` (mechanical convergence signal: open/closed finding counts,
  including forest findings that touch the article).
- Develop's forest map now projects candidate anchor concepts (id + title) for wiring `governed-by`.
- `render` warns on a romanized-slug cover title for a CJK article (fix: add a root `group.yaml`
  title) and strips hand-added closing-form `<!-- /dspx… -->` markers from frozen snapshots.
- The `realizes` field's schema now documents the sibling-dependency filing rule (projected into
  `docspec guide`). `impact`'s zero-blast message no longer reads as "orphan/unused".

### Changed — diagram-intent gate exempts unwritten sections

- The `brief.layout: diagram` gate no longer fires on an empty/whitespace-only section body, so
  batch drafting stays green until prose exists without an embedded figure; the gate's error message
  now routes authors to the drawio→PNG track (dspx-diagram skill / `setup --with-drawio` /
  `docs/assets/`) instead of leaving them to invent mermaid.

### Changed — internal module reorganization (no behavior change)

- `check.py`, `commands/setup.py`, and `commands/export.py` were each split into a subpackage of
  smaller single-concern modules, re-exporting their full public surface so every caller and test is
  unchanged. New capability spec `module-reexport-stability` records the re-export contract.

### Changed — repo hygiene

- `src/dspx/skills/` renamed to `src/dspx/assets/skills/` (alongside `assets/templates|fonts|
  reference/`, no longer colliding in name with the `skills.py` module that reads it).
- `docspec setup` prints an honest stderr notice on macOS that the platform is not yet verified on
  real hardware (only Windows and Linux are tested); it proceeds regardless. CI test matrix widened
  to Python 3.11 / 3.12 / 3.13.

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
- **Image embedding** (Stage A; superseded by Model A below — kept for history) — sections
  originally embedded images from `corpus/<section>/assets/`; a pre-render integrity check failed
  loud on a missing image reference; image hashes folded into the section's staleness fingerprint.

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

### Added — delivery quality, multi-document governance, and skill truthfulness

- **Content-based language detection** (`config.detect_language`) drives changelog i18n and
  export lang/region instead of a static project setting; changelog level labels (major/minor/
  patch) are localized to match.
- **`group.yaml` gets an optional `order`** — render honors it for grouping-node sort instead of
  always alphabetical.
- Journal `.tex` emits to `docs/exports/journals/<id>/` (no collision with the Typst-track output).
- `export` keeps only the latest PDF by default (`--keep` to retain older ones).
- **Multi-document staleness closes real gaps**: `deps_fingerprint` now folds a realized
  decision's `status`, so superseding it correctly restales every consumer across documents;
  `ancestor_brief_fingerprint` spans the full `governed-by` closure (not just the same-tree path),
  so a governance parent's brief change restales its cross-tree children too; `check` rejects a
  `governed-by` edge into a `deprecated` concept.
- `draft` receives ancestor normative rulings and the project purpose in its aperture; `factcheck`'s
  projection foregrounds the coverage contract (`must_cover` + layout/kind).
- Article-root cover title now reads from `corpus/<article>/group.yaml` (fixes a CJK document
  cover showing a romanized slug instead of its real title).
- Skills no longer claim engine enforcement that doesn't exist, or hardcode specific lint rule
  codes in prose (codes drift; skills now describe the behavior). The STEP-0 recovery paragraph is
  byte-identical across all skills (test-guarded, so it can't drift skill-to-skill).
- Typst document-type profiles (paper/manual/essay/novel/academic/default) plus accumulated
  typography fixes: two-column paper layout, table column-width balancing, heading-level tuning.

### Fixed — revision integrity (staleness false-greens + semantic coherence)

- `concept.sources` is now external-provenance-only: `check` ERRORs if it holds an internal
  decision id (that belongs in `realizes`/`governed-by`, which staleness actually tracks) and WARNs
  on a prose-only cross-section reference with no structural edge.
- **The single biggest staleness false-green**: `render` used to re-stamp a section's fingerprint
  on every render even when its prose hadn't actually been rewritten, silently clearing a real
  `stale-own`/`stale-upstream` signal. It now reuses the prior fingerprint when the prose is
  unchanged, so the signal survives until someone actually rewrites the section.
- The corpus YAML loader fails loud on a duplicate mapping key (previously PyYAML silently kept the
  last one, corrupting a decision record without any warning).
- `render --ack <section>` clears `stale-inherited` when the prose genuinely needs no change
  (refused if the section is actually `stale-own`/`stale-upstream` — rewrite it instead).
- `edit`/`factcheck` re-examine the document's title/framing on a deep revision, not just the
  touched section.
- **Non-blocking semantic coherence** (no new engine gate): `factcheck`'s aperture projects a
  coherence contract — title/framing/own-brief/decision/figure checked against the current prose
  and the ancestor brief — and raises non-blocking audit findings on a contradiction; `develop`
  sweeps the metadata/asset layers (not just prose) on a brief pivot or decision supersede;
  `render --ack` prints a non-blocking reminder to re-check coherence.

### Added — `dspx-diagram` hardening + managed drawio install policy

- `validate.py` (vendored, MIT, modified) now flags a floating edge endpoint, treats a vertex that
  geometrically encloses other leaves as a visual container (cut 30 false-positive warnings to 3 on
  a real architecture diagram), and makes the edge-crossing warning jumpStyle-aware.
- `dspx-diagram/SKILL.md` gains a Layout & routing section (layer by flow, re-routing on a frozen
  layout, label positioning) and corrects a misattributed v24 guardrail — the real blocker for
  draw.io CLI exports was the `ELECTRON_RUN_AS_NODE` environment variable, not the drawio version.
- `setup`'s managed drawio install now treats its pinned version as a **minimum floor, not an exact
  pin**: it keeps any installed binary at or above the verified-working floor and only re-downloads
  the pinned, sha256-verified release when a probed version is below that floor (an unprobeable
  version — e.g. headless/timeout — is left alone rather than treated as bad).
- `.gitattributes` pins LF line endings repo-wide, stopping Windows-checkout CRLF churn.

### Added — authoring-guidance completeness (byline, placeholder hygiene, publish checklist)

- **Byline is a `develop`-level decision**: when the real author identity is unknown, fill an
  obvious RFC 2606 reserved placeholder (`author@example.com`) — never a plausible-looking
  fabricated name. Lint **V13** (WARN) backstops this mechanically: it flags reserved
  example/placeholder tokens (`example.*` domains, lorem ipsum, `555-01xx` numbers) shipped in the
  deliverable.
- Lint **V14** (WARN): an image asset that exists in the assets folder but is never embedded by the
  deliverable (orphan asset).
- The coherence contract gains a cross-document pair: `factcheck` now also checks a `realized`
  decision's statement against the consuming section's prose, catching prose that still implements
  a since-superseded upstream truth.
- `publish` runs a whole-document convergence checklist before the trigger, so an agent can't
  declare victory right after `draft` and skip `edit`/`factcheck`.
- `docspec status` projects the sync-state → skill-routing legend (which skill picks up which
  staleness flag).

### Fixed — forest governance, staleness axes, and deliverable-cleanliness (backstage-leak family)

- **`realizes` liveness**: `check` now rejects a `realizes` edge into a retired or misrouted
  (concept-kind) target instead of silently accepting it; a superseded-but-present target is still
  allowed through as a legal transition window. `aperture` surfaces the live/superseded status of a
  realized decision and walks the supersede chain to its terminal live successor, instead of
  silently anchoring `draft`'s output on dead truth.
- **Transitive blast radius**: `docspec impact <concept>` now reports the *transitive*
  `governed-by` blast radius (every downstream document, not just direct children) — this matches
  what `status` actually re-stales, so `impact` no longer under-reports the effect of a change.
  Cycle-path reporting trims the DFS lead-in so only the real cycle prints, not an unrelated
  upstream path fragment.
- **New `stale-style` ledger axis**: a `style_fingerprint` (hash of `writing-guide.md` +
  `glossary.yaml`) means restyling the shared writing guide is no longer invisible to staleness —
  every section written against the old style is flagged `stale-style` (lowest-priority axis: own >
  upstream > inherited > style) and routes through `edit`, clearable via `render --ack`.
- **Diagram assets move to the delivery side (Model A)**: `.drawio` sources and their rendered PNGs
  now live under `docs/assets/` (or `docs/<article>/assets/` in a per-article layout), not
  `corpus/<section>/assets/` — diagrams are a deliverable, not backstage authoring source. This
  supersedes the Stage-A image-embedding note above. The per-section asset-basename-collision guard
  in `check` is dropped (moot once every article's assets live in one place); `export`/`check` read
  from `docs/assets/`.
- **Ledger moves out of `docs/`**: the section-fingerprint ledger (staleness bookkeeping) moves from
  a `docs/` sidecar file into `docspec/.ledger/<article>.sections.yaml` — `docs/` now holds only
  deliverables, no machine bookkeeping. `docspec skills install` defaults to `--tool claude` only
  (was: all three agent integrations) — pass `--tool all` to install every integration.
- **Lint V15** (ERROR, closed blocklist): authoring-tool/governance vocabulary (`forest`,
  `governed-by`, `Tier-N`, `factcheck`, `raise a finding`, …) leaking into deliverable prose.
  Writing-guide backbone rule 8 names the ban and requires a domain-language replacement.
- **Backstage brief/coverage projections carry a non-narration guard**: `instructions` marks the
  backstage brief/coverage/coherence/ancestor-normative blocks it projects to `draft`/`develop` as
  "obey, never narrate" — `draft`/`develop` no longer open a section with a
  "this section establishes…" role-framing announcement. Extended to the whole-document overview
  level: the root/overview section may not narrate the document's own chapter structure or refer to
  the document as a self-made artifact ("this spec splits the work into…").
