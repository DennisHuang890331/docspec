# Changelog

All notable changes to docspec are recorded here. The project follows
[Semantic Versioning](https://semver.org/). In addition to the package version
(`pyproject.toml`), the **export-format / slot-contract surface** is versioned
independently (`dspx.slots.CONTRACT_VERSION`) so that changes to the journal slot
contract — which affect BYO journal templates downstream — are tracked with their
own semver: a breaking slot rename/removal is a major bump, an added optional slot
a minor bump.

## [Unreleased]

### Changed — skill descriptions now state WHEN to use them (host agents decide skill loading from the description alone)

Audited the bundled skills against Anthropic's official skill-creator criteria; the one real gap was trigger information. `dspx-apply` and `dspx-factcheck` gained positive trigger sentences (apply's names the engine states that summon it: stale-*/unwritten/revise-align targets); `dspx-publish` and `dspx-release` gained CONDITIONAL triggers that bind invocation to the human's explicit ask and state never-self-initiated — assertive auto-trigger phrasing is deliberately absent on the human-gate skills. Tests pin all six descriptions.


### Fixed / Changed — the engine keeps its records straight (three-role doctrine: the engine is the filing cabinet — it must never lose, misfile, or mis-report a record)

Stress-test v2 (deep three-document corpus, cross-document ripple scenarios) caught six ways the record layer could betray its keeper. All fixed:

- **Verdicts inside a change now land in the change's preview journal**, not the official `.ledger/*.verdicts.yaml` (which is frozen while a change is active). This also un-wedges `[review]`-action targets: `change status` reads the same preview journal the verdict was written to, so a review target can actually complete (previously it reported "no review verdict recorded" forever, because the write and the read looked at different files).
- **`put concept` never erases engine-stamped identity**: re-putting content that omits `id`/`order` carries the existing values over (omission is not erasure — wiping the id severed every inbound `realizes` edge); content carrying a *different* id is refused (identity changes go through retire + recreate, not put).
- **`put <group-path> group <file>`** gives grouping nodes (localized `title` / `order` / `numbering`) a real API write path in the one-file-per-article store — previously the only way to title or order a group was hand-editing the sealed store file and re-sealing with `fsck --accept`.
- **`show <section> --realized-by` aggregates** the section's concept id *and* every decision it owns (grouped by id) — a deep-coupled section whose decisions have downstream realizers no longer reports "no section realizes it".
- **`roadmap add` never re-issues an archived id**: allocation scans the archive too, and `check` warns when a live entry and an archived one share an id.
- **A stuck `stale-own` now explains itself**: when the source changed but the prose was not rewritten, `status` / `change status` say so and name the two legitimate exits (rewrite + render, or the human-confirmed ack path) — the keep-the-signal design was correct but undiagnosed, and it was driving agents toward perturb-and-revert fabrication.

### Added — human-decision provenance + value crystallization (three-role doctrine: the human is the only source of decisions; the agent records, compares, discusses, renders)

- **Per-decision human confirmation** is now the projected develop contract: the agent drafts, but each normative decision is confirmed by the human individually before `put`, and the human's ruling (gist or verbatim) is recorded into the change's `notes.md` at that moment. Work that authors normative decisions runs inside a change — first authoring included. (Honest boundary, stated in the projection: the engine cannot observe the conversation; enforcement is projection + journal audit + human review.)
- **`decided-in` is stamped mechanically**: `put decisions --change <id>` stamps `decided-in: <change-id>` onto new entries and entries whose statement changed (agent-provided values are respected; unchanged entries keep their existing stamp even when the incoming file omits it). `check` reports an ERROR for a `decided-in` pointing at a change that never existed; absence stays legal.
- **Acknowledge verdicts are the human's ruling**: the projected verdict-verb contract (and the apply skill) now require presenting the section, its staleness state, and the proposed justification to the human before any `--ack`/`--ack-own`; the journaled reason carries the human's ruling.
- **`change archive` warns when `notes.md` is empty** beyond the `--why` seed — the human-decision record should not be blank (non-blocking; archive stays the human's gate).
- **Value-crystallization filing rule** (projected via guide): a normative value — a threshold/cap/cycle/tolerance other sections or documents will obey or restate — must be crystallized as a decision carrying the value, so a `realizes` edge can attach and staleness propagates; prose/material only reference it. The engine gains no new gate (whether a value is normative is a semantic call — agent asks, human ratifies); factcheck findings now recommend crystallization when a disagreeing cross-document quantity has no decision behind it.

### Removed — the develop workbench retires: `docspec new`, `docspec ready`, `develop.md`, and the `work/` directory are gone; `put` is the single way a section comes into being

The develop.md thinking-pad loop (`new` scaffolds `work/<section>/develop.md` → agent thinks in it → `put` crystallizes → `ready` drains + deletes the file) was a scattered-files-era workflow whose gate had no mechanical consumer: nothing downstream ever read the `ready` state (render/publish/put all ignore it), the whole loop could be bypassed by calling `put` directly (which already stamps id/order and validates the path on first write), and the deliverable never reads develop.md. Its one durable role — a meeting-minutes-style thinking record — is already served properly by a change container's `notes.md`, which is archived with the change. What the loop actually left behind in practice was a pile of empty `work/<section>/` shells after every crystallization.

- **`docspec new` removed** (including `--reopen`). A section EXISTS from its first `docspec put <section> concept`; put stamps the id (path fingerprint) and order (sibling count) and validates the path segments (the Windows-reserved-name / illegal-character / `_`-prefix blacklist moved from new into put — same rules, same messages).
- **`docspec ready` removed** (including article-batch mode). `status` still reports `developing` for sections whose required fields are incomplete — computed from field completeness only. Completeness gates stay where they always mechanically were: `check` and `publish`.
- **`develop` artifact removed from the schema** (template + instruction files deleted; every skill aperture cleaned). The develop SKILL remains — it is the authoring judgment loop — but its steps now read: think in your working context, keep durable discussion in a change's `notes.md` (open the change the moment work touches a ruling or spans sections), then crystallize via `put` with the same four-question triage.
- **`store migrate` now refuses** a scattered tree that still contains legacy `develop.md` / `history.md` workfiles instead of relocating them into `work/` (which no longer exists): distill them into the store with `put` or delete them yourself, then re-run — the engine never silently drops or moves them.
- Planned-but-unwritten sections are the roadmap's job (`docspec roadmap add`); status/list no longer surface develop-only stubs.
- Ghost-command cleanup in the same sweep: messages that pointed at `docspec crystallize` (never a real command) now point at `get/put`.

### Changed — the change containers move under `docspec/` (mirroring how OpenSpec keeps everything under `openspec/`)

The modify-event-layer's `changes/` folder now lives at `docspec/changes/` instead of the project root. It is engine-internal management state (staging branches, previews, change metadata) — not something a human reads directly (humans read `docs/`) — so it belongs alongside `corpus/`, the ledger, glossary, and freeze net inside the engine home, exactly as OpenSpec keeps its `changes/` under `openspec/`. Existing projects: move `changes/` into `docspec/`. (Pre-release, so no compatibility shim.)

### Added — `docspec find` (locate without reading everything) + `status --pending-facts` (the fact-input queue)

Agents that factcheck or edit used to read whole files to locate something; these two read-only queries let them jump straight to the relevant lines and save tokens.

- **`docspec find <query>`** searches every face — deliverable prose (code fences / URLs / markers masked, so no false hits), concept, decisions, material, glossary, audit — and returns, per hit, the section + which face matched + a precise location (a prose hit gives the line in `docs/<article>/_latest.md`; a source hit gives `decisions[i].statement` / `material Ln`) + a snippet, plus the id for a follow-up `show`. Deterministic substring / `--regex`; scope to a section/subtree/article; `--json`.
- **`docspec find --numbers`** is a value presenter (the retired lint V10 idea, reborn): it aggregates every number+unit token in the rendered prose grouped by referent (glossary term → section title → section), and lays out the values with their locations. A referent carrying more than one distinct value is surfaced for an agent to judge — it is **present-only** and never prints a verdict like "drift" or "reconcile" (mechanical judgement of number semantics was measured at 100% false-positive on the real corpus; the engine presents, the agent judges, the human decides). This extends the engine's existing "present, don't judge" pattern (`coherence_contract`) from statement text to values.
- **`docspec status --pending-facts`** lists every `[TBD]` / `[待補]` placeholder in the source (material / decisions / concept) as "facts the writer still owes" — the deterministic surface for the ruling that fact correctness is the writer's responsibility (a mechanical number-provenance gate was investigated against the real corpus and rejected as unworkable; the engine surfaces the gaps, it never judges whether a filled-in fact is correct).
- **`factcheck` skill reframed** to lead with `find --numbers` (triage number inconsistencies the engine surfaces) and `find` (jump to a claim) before reading, and to check `find --in audit` for an already-rejected finding before raising. (The separately-planned coherence value-patch is subsumed by `find --numbers`, which already surfaces every prose value by referent, so it was dropped.)

### Changed — audit & roadmap become engine-owned, integrity-sealed sibling stores (governance-store-native)

Audit findings and the roadmap backlog now live under the SAME discipline as the article store — an engine-owned single file per document, protected by an integrity seal, written atomically, guarded against hand-edits — instead of the old scattered `corpus/<article>/audit.yaml` folder that no longer exists in the one-file-store world.

- **Sibling sealed stores**: per-document audit → `corpus/<article>.audit.yaml`, roadmap → `corpus/<article>.roadmap.yaml` (forest-level ones stay at `docspec/audit.yaml` / `docspec/roadmap.yaml`). Each carries a `sha256` integrity seal over its content; a hand-edit makes the next docspec command fail loud and point at `docspec store fsck`. A new shared helper `engine/sealed.py` (canonical serialize + seal + atomic write) backs both. Old un-sealed files still read (so migration/first-save upgrade them cleanly).
- **New `docspec roadmap add`** — the roadmap gained an engine write gate (previously the backlog was hand-edited, which sealing would have blocked). `roadmap add --kind gap|task --title … --target <section|forest>` validates and seals the entry, routing it to the right document's store. `develop` now records backlog work through this command instead of hand-editing. (This makes roadmap fully engine-owned, symmetric with audit — the "everything through the engine" choice; the alternative of leaving roadmap hand-edited like the glossary was considered and rejected for consistency.)
- **Migration unblocked**: `store migrate` now folds a scattered document's `audit.yaml` / `roadmap.yaml` into the sealed siblings instead of refusing (the roadmap/audit files used to make a document un-migratable). Roadmap completion archives consolidate into a single `docspec/roadmap-archive.yaml`.
- **Guards**: article discovery skips the `*.audit.yaml` / `*.roadmap.yaml` siblings (they're not documents); `new` refuses an article name containing `.` (it would collide with the sibling naming); the hand-edit hook guards the siblings (by the `corpus/` shape) and the forest governance files (by name). Every place that rewrites audit/roadmap during a move / promotion / archive now round-trips through the sealed store instead of a raw write.
- Fingerprints do NOT read audit/roadmap, so this needs zero re-baseline.

### Changed — command-surface round 2: renames, regrouping, a new `edit` primitive, setup folded into `init`

- **`self-update` → `update`** (the freed-up name; `upgrade` was already gone). Pure rename.
- **Four standalone commands folded into their conceptual home** (each old module became an underscore-prefixed helper; behavior unchanged, callers/lint messages/schema/skills updated):
  - `retired` → `status --retired` (querying retired sections is a status view).
  - `tidy` → `store tidy` (deterministic corpus cleanup is store maintenance, alongside dump/migrate/fsck).
  - `measure-fonts` → appended to `proof` output (font/layout diagnostics after the PDF renders; no separate command).
  - `freeze register-legacy` → `publish register-legacy` (seeding legacy versions into the frozen area is a publish-time operation; the standalone `freeze` command retires, the freeze *report*/hash-net stays).
- **New `edit` primitive** — one entry point for mechanical prose edits: `edit <article> --punct` (= old `normalize`), `edit <article> --term OLD NEW` (= old `rename-term`), and the new `edit <section> --replace OLD NEW` (literal replace scoped to ONE section). All three touch prose spans only (code/URLs/markers stay byte-exact) and self-maintain the prose fingerprint; `--replace` is section-scoped, refuses on zero matches (exit 1), and has `--dry-run`. `normalize`/`rename-term` retire as top-level commands. (Semantic fidelity is not mechanically enforceable — the primitive guarantees the mechanical boundary only; whether an edit is *correct* is the human's / factcheck's call.)
- **`skills` command folded into `init`** — `init` already installs the skills (with `--tool` selection and idempotent re-install on re-run), so the standalone `skills` command retires; re-run `init` to (re)install.
- **`instructions` and `reference` kept as independent top-level commands** — an earlier plan merged them into `guide`; on inspection both are low-frequency but distinct, discoverable, and referenced from calibrated lint messages / onboarding text (10+ user-facing strings), so merging was high-churn for marginal gain. They stay independent (matching how OpenSpec keeps `instructions` separate).

### Removed — the scattered per-section file layout retires; one-file store is the only corpus format

- The one-file `corpus/<article>.yaml` store is now the ONLY live corpus format. The old scattered
  layout (one folder per section holding `concept.yaml` / `decisions.yaml` / `material.md`) survives
  only as a migration/recovery bridge: `store migrate` reads it once to convert to the store, and
  `store dump` writes it for debugging/recovery. `new` / `get` / `put` / `mv` / `retire` / `tidy` /
  render / status / check all operate on the store — the dual-backend branching in the normal path
  is gone; `change.py`'s file-granular tree staging is gone (only the structured store staging
  remains). `develop.md` stays outside the store in `work/<section>/`.
- Cleanup pass: removed the dead `mv._is_section_folder` (no callers left after the store rewrite),
  and swept the last scattered-world docstrings (`get`/`put`/`new`/`mv`/`retire`/`change` help text that
  still said "reads/writes scattered files" or compared to "the tree version"). The `hook check`
  (`_postcheck`) completeness reminder is deliberately kept — it now serves edits to scattered
  concept/decisions files that only exist via `store dump` / migration source / `_archive` snapshots;
  the live store is guarded against hand-edits and written through `put`, so it never routes here.
- The engine core was regrouped into subpackages by responsibility: `dspx/engine/` (the coupled
  core — model, render, change, store, aperture, crossref, forest, spans, schema, layout, paths,
  lint, config, glossary), `dspx/reports/` (audit, roadmap, freeze), `dspx/typeset/` (slots,
  format_config), `dspx/env/` (skills, welcome, _install_source, frontmatter). Pure moves.

### Changed / Removed — command-surface consolidation (kill redundant commands, finish store lifecycle)

Four commands were folded into the command that already owned their behavior, and the dead
report-only `retire` was removed. Nothing is lost — every capability moved to a named home
(recorded here + preserved in git history), the CLI just stops carrying triplets and empty shells.

- **Removed `retire` (the non-mutating report).** The old `docspec retire <section>` only *reported*
  dead decisions that already sit in place in `decisions.yaml`; it mutated nothing. That report is
  replaced by the new classification view **`docspec show <article> --decisions --all-status`** (see
  Added below), which lists every ruling incl. superseded/deprecated ones marked `⚰ DEAD`. This
  collapsed the confusing triplet (report `retire` / transaction `retire-section` / query `retired`)
  down to a pair (transaction `retire` / query `retired`).
- **Renamed `retire-section` → `retire`.** The whole-section retirement transaction (move the section
  subtree into `corpus/_archive/`, record a `kind: section` history entry, migrate an orphaned
  article's deliverable + ledger) now *is* `docspec retire <section>`. All schema/instructions/skill
  text that said `retire-section` now says `retire`.
- **Merged `upgrade` → `setup`.** `docspec upgrade` only ever aligned the asset layer (fonts / pandoc
  / typst / optional TinyTeX) — a strict subset of idempotent `setup`. `setup` now also **aligns an
  already-installed TinyTeX** (detected via `tlmgr`) without requiring `--with-latex`, and prints the
  two-track update reminder (assets via `setup`, program via `uv tool install … --reinstall`). Run
  `docspec setup` where you used to run `docspec upgrade`. `doctor`'s fix hints now point at `setup`.
- **Merged `list` → `status`.** `list`'s only capability that `status` lacked — **group-node rows**
  (concept-less grouping folders with their localized `group.yaml` title/order) — is now emitted by
  `status` (a `groups` array in `--json`, a "group nodes" block in text). Per-leaf concept one-liners
  that `list --json` used to carry are available via `docspec show <article> --concepts`.
- **Merged `redraft` → `stale`.** `docspec stale` now takes either a **leaf section** (mark one) or an
  **article name** (mark every written section = whole re-projection, backing up `_latest.md` first —
  the old `redraft` behavior). The verdicts-journal verb stays `stale` for a section and `redraft`
  for a whole article, so the audit trail is unchanged.
- **Removed the redundant `templates/concept.yaml` / `decisions.yaml` / `history.yaml`** (template
  slimming). After the store backend landed, `docspec get` already derived its empty yaml scaffold
  from the schema field contract (`yaml_skeleton`), never from these files; only the aperture
  projection still read them, duplicating the schema-derived skeleton it also emits. The **schema is
  now the single source of truth** for these three artifacts' scaffold (kept `generates:` +
  `instruction:`, dropped `template:`). The `{id}/{title}/{order}` auto-fill they carried is already
  provided by `docspec new` seeding `develop.md`. The **md templates (material / develop / history-md)
  are unchanged** — those are genuinely read. Loading the deleted files was verified to have no other
  code dependency before removal.

### Added — store-backed `mv` / `retire`, and `show` classification views

- **`docspec mv` and `docspec retire` now operate on store-backed articles** (previously they failed
  loud with a "does not yet operate on store-backed article" Phase-C placeholder). `mv` rewrites the
  affected records' `path` prefix in place (+ marker/audit/roadmap references), bumps `revision`,
  self-verifies with `check`, and rolls back on failure with zero partial effect. `retire` extracts
  the section subtree's records, dumps them into a recoverable scattered-file archive package under
  `corpus/_archive/` (with the `kind: section` history entry), removes them from the live store, and
  bumps `revision`; a whole-article retirement removes the store file and migrates the deliverable +
  ledger into the archive. Side sections' records survive byte-for-byte.
- **`docspec show <article> --decisions | --concepts | --material`** — forward classification views
  across an article (or a section subtree), complementing the existing reverse views
  (`--impact`/`--realized-by`/`--referenced-by`). `--decisions` lists each section's rulings
  (path/id/kind/status/statement); `--decisions --all-status` also lists dead rulings (⚰ DEAD),
  replacing the removed report `retire`. `--concepts` lists each section's one-line concept + its
  *differential* brief (only the fields it overrides). `--material` lists which sections carry
  material and each material's `## <type>: <title>` heading index. Both backends supported.

### Added — one-file-per-article store backend (article-store-backend, stage 2: A/B/C/D/E)

- An article's corpus truth can now live in a single engine-owned `corpus/<article>.yaml` **store
  file** (a `format`/`article`/`revision`/`integrity` header plus a path-sorted flat `sections`
  list, each carrying `concept`/`decisions`/`history`/`material` blocks and `kind: group` records)
  instead of the scattered one-folder-per-section files. Both layouts coexist and are **auto-detected
  per article**; one article having both a store file and a leaf tree fails loud.
- New `dspx/store.py` access layer: a **canonical serializer** (key order from the schema fieldmap,
  multi-line strings as literal block scalars, `allow_unicode`, atomic tmp+`os.replace`) that is
  **idempotent** (`load→dump→load` fixpoint, `dump(dump(x))==dump(x)`), and an **integrity seal**
  (sha256 over the canonical body) that makes a hand-edit fail loud on the next command, pointing at
  `docspec store fsck`. The hook guard now also blocks writes to `corpus/*.yaml`.
- New `docspec store` command group: `migrate <article>|--all` (tree→store, **parity-gated**: both
  backends load, every leaf deep-equals, and anc/deps/norm fingerprints match per section, else it
  rolls back), `dump` (store→scattered, read-only recovery export), `load` (scattered→store through
  full validation), `fsck [--accept]` (verify/re-seal). Migration is reversible (dump + delete).
- **Fingerprint own-axis v5**: the own-source hash now reads parsed structure (canonical concept
  minus `order` + canonical decisions + material text + fixed category labels) instead of file
  bytes, so it is backend-neutral — the same content hashes identically whether scattered or stored.
  The other five faces (anc/deps/norm/style/prose) are byte-for-byte unchanged. Ledger fingerprint
  version bumps 4→5; `--rebaseline` absorbs the one-time own-axis change.
- `develop.md` moves out of the store to `docspec/work/<section-path>/develop.md` on migration
  (pre-crystallization workbench). Read-end sites (aperture material, lint material, status flags,
  render group titles/order) are now backend-neutral (they read the model, not the filesystem).
- **Phase C — change-layer structured merge for store articles (done).** A store article can now go
  through the full change workflow. A change's staging is a **partial store** `changes/<id>/staging/
  <article>.yaml` holding only the staged section records; `docspec put --change` writes the
  validated edit into it while the official store stays **byte-frozen**. Landing is a structured
  **merge-by-section-id**: read the official store, swap ONLY the target record (whole record in,
  `pending-create` promoted, `tombstone` removed), bump `revision`, canonically dump, atomic write.
  The **P0 guarantee holds in its new form** — a non-target record is the same parsed object from
  read to dump, so (serializer being idempotent and the store always a canonical product) every
  non-target section's serialized block stays byte-for-byte identical across landing (pinned by a
  byte-level regression test plus deep-equality). The fork-drift guard now works at
  per-section-per-category granularity (`<article>#<path>#<category>` canonical-JSON hash). `stage_section`
  / `unstage_section` / `load_union` / `land_corpus_section` / `section_concept_id` / `fork_drift`
  are all backend-routed; `abandon` leaves the official store byte-unchanged with zero residue.
- **Phase E — dual-backend test parametrization (done for the change workflow).** The change-event
  helpers take a `backend` param; the archive-lands workflow runs on both `tree` and `store`, plus
  store-only tests cover the landing P0 bystander-byte guarantee, the full new→put→render→archive
  e2e, put-into-staging routing (official frozen), abandon zero-residue, and fork-drift.
- **Lifecycle commands are backend-neutral for store articles.** `new` scaffolds `develop.md` into
  `docspec/work/<section>/` (not the corpus) and `ready` graduates a store section by draining that
  work-file; `put` (with or without `--change`) writes through the store record. Structured
  record-move / record-retire for store (`mv` / `retire-section`) are an honest Phase-C follow-up:
  they fail loud and point at the `store dump` ↔ `store load` scattered-file escape hatch rather than
  silently no-op or corrupt.

### Fixed — `put` now routes into a change's staging instead of the frozen official corpus

- A stress test surfaced a P0 workflow trap: while a change was active, `docspec put` on a
  target section wrote the edit into the **official** corpus (the change's staging copy stayed
  stale) — the exact opposite of the change container's model ("edits land in staging, official
  stays byte-frozen until archive"), which the develop skill already promised. It also left no
  command able to write a validated source edit into staging, forcing hand-edits of staging files.
- `put` now detects the active change that targets a section and writes the validated content into
  that change's `staging/` (copy-on-write), leaving the official file **byte-frozen**; a section
  targeted by two active changes fails loud and requires `--change <id>`; a non-target section
  writes official as before. `get` reads the staging version of a staged target by default, with
  `--official` for the frozen baseline and `--change` to disambiguate. `abandon` once again leaves
  zero residue on the official side.
- `docspec show <arg>` now accepts a section path OR an id interchangeably across `--impact` /
  `--referenced-by` / `--realized-by` / bare show (an id resolves to its owning section, a path to
  itself); a mis-addressed argument gets a pointing hint instead of a bare "not found".
- `change new --seed` now hints that a generic-reference downstream (prose that cites via an anchor
  rather than restating a value) can be dropped with `remove-target`; archive now names any
  dropped-target section whose ledger recompute flipped it to synced without explicit re-review,
  instead of absorbing it silently.

### Changed — all six agent skills rewritten as engine-anchored drive-through loops

- **Every SKILL.md was scrapped and rewritten** (develop / apply / factcheck / publish / release /
  diagram) in one uniform format: frontmatter (with a `compatibility` field carrying the CLI
  environment note, and a uniform `license` field) → one-line purpose → **Input** → **Steps**
  (numbered, each anchored to a `docspec` command, with explicit pause conditions) → **Output**
  (literal report template) → **Guardrails**. Body size dropped from ~1,230 lines to ~230 across
  the six skills; every retained lesson (blind-write discipline, honest verdict verbs,
  zero-inference, measure-don't-eyeball, PNG-not-SVG …) was carried over into Steps/Guardrails,
  checked item by item.
- **Rules moved out of the skills into the engine projection** (single source, can't drift):
  `docspec instructions apply <section>` now prints the writing principles (payload-first,
  inverted-pyramid, structure-into-tables, the scaffolding/cross-ref/metaphor bans, zero-inference),
  a `── Verdict verbs ──` block (ack/ack-own whitelist plus which brief fields mean ack-or-rewrite
  vs rewrite), and a `── Dispatch exclusions ──` block. The blocks live in the schema (`authoring`)
  and are projected live; skills only anchor to them.
- **Environment troubleshooting is out of the skill bodies** — the "docspec not on PATH in a fresh
  shell" recovery hint lives in one `compatibility` frontmatter line per skill (previously a
  five-line callout duplicated at the top of all six bodies). `skills.py` now preserves frontmatter
  on install so the field actually survives (it was silently stripped before).
- The writing guide's rule 8 no longer contradicts the anchor mechanism: hand-typed chapter numbers
  stay banned (they drift), the render-injected `<!--@id-->§N<!--@-->` anchor is the sanctioned
  cross-reference form, written as `（詳見<anchor>）`.
- `dspx-diagram` keeps its draw.io mechanics (XML skeleton, shape tables, export flags,
  troubleshooting) in a sibling `reference.md`; the SKILL.md itself is the thin loop.

### Added — reverse relation views: `show --impact` / `--realized-by` / `--referenced-by`

- **The engine already resolves the cross-document truth graph FORWARD** (staleness: "why am I
  stale — who changed that I depend on"). `docspec show` now also exposes the REVERSE of those same
  edges (impact: "who do I break if I change this"), computed by `dspx.crossref.build_reverse_indices`
  from the SAME forward-resolution functions (`decision_index`, `ancestor_leaves`, the shared prose-
  anchor scan) so the reverse view cannot drift from the staleness the engine acts on. Pure addition,
  zero storage change, runs on the current scattered files.
  - **`docspec show <section> --impact`** previews, BEFORE you change a section, every section across
    ALL documents a change would make stale, grouped by staleness type: sections realizing its active
    decisions → **stale-upstream**; its descendants (path children ∪ transitive `governed-by`) →
    **stale-inherited** (and **stale-norm** when the section owns active normative rulings); sections
    whose prose anchors point at it → **cross-reference affected**. An empty result reports "no
    cross-section impact" (honest, not an error); the output notes that a global style carrier change
    (writing-guide / glossary / purpose) is not listed per-section. The stale-upstream set is
    guaranteed to agree with what `section_state` would actually mark stale (same-source).
  - **`docspec show <decision-id> --realized-by`** lists every section, across all articles, whose
    `realizes` includes that decision.
  - **`docspec show <section> --referenced-by`** lists every section whose prose cross-reference
    anchor points at this section. Because anchors live in rendered prose, an article whose
    deliverable is not yet rendered is reported explicitly ("not yet rendered") rather than returned
    as an empty set that reads as "no references".

### Removed — standalone `docspec impact` command + `retire --in` no-op flag

- **`docspec impact <id>` is removed** — its reverse-view function is absorbed into the cohesive
  `show` reverse views above. The functionality does not disappear, only its entry point changes:
  "which sections realize this decision" → `docspec show <decision-id> --realized-by`; "what does
  changing this blast" (governed-by / transitive inheritance) → `docspec show <section> --impact`
  (descendants). The dead-decision inspection hint printed by `docspec retire` now points at
  `docspec show <id> --realized-by` instead of `docspec impact <id>`.
- **`docspec retire --in <tag>` is removed** — it had been a documented deprecated no-op since
  contract slimming made `retire` non-mutating (it wrote nothing, so the change/session tag had no
  effect). No replacement is needed; the flag did nothing.

### Added — engine write gate: `docspec get` / `docspec put`

- **`docspec put <section> <concept|decisions|material> <FILE|->` is the single validated write gate
  for corpus truth**, replacing the pattern where an agent hand-writes `concept.yaml` and the engine
  only flags structural mistakes after the fact. `put` parses the submitted content (bad YAML /
  duplicate mapping key → rejected), runs the existing `run_file_check` plus structural validation
  (duplicate id, malformed `entries` shape, bad enum, dangling relation target), and only on success
  writes atomically (temp file + `os.replace`); a validation failure rejects with a message and
  leaves the original file byte-for-byte unchanged (no partial write). On the first write of a
  section's concept (no `concept.yaml` yet) it stamps `id`/`order`. Completeness (a missing required
  field) is deliberately NOT a write-time gate — that gate lives at advancement (`ready`/`publish`),
  so a half-formed section still writes and stays `developing`.
- **`docspec get <section> <concept|decisions|material> [--out FILE]`** emits the current content to
  stdout or a file for the agent to edit; a section with no such file yet returns an empty schema
  skeleton. `get`/`put` are agent-facing (not in the human command surface). Backend still writes the
  current scattered files — this change establishes the write GATE, not a new storage topology.

### Changed — draft and edit merge into a single `apply` skill

- **The draft and edit workflow skills merge into one skill, `apply`**, with two engine-routed
  modes — **rewrite** (blind-render a section's prose from its concept/brief; the former draft
  skill) and **align** (line/sentence/proofread pass over already-rendered prose; the former edit
  skill) — so the agent no longer chooses between two adjacent skills by hand.
- `docspec status`'s sync-state → skill-routing legend, which named draft and edit as separate
  routing targets, is removed; every routing case now points at `apply`.

### Added — prose cross-references become stable anchors with render-injected §numbers

- **A prose cross-reference to another section/decision is now a stable anchor, not a hand-typed
  chapter number.** Write `<!--@<target-concept-id>--><!--@-->` inline where the number should go;
  `render` injects the current `§number` between the two invisible comments from the target's
  outline position and re-derives it on every render, so it never dangles. This closes the last
  half of the SC-renumber breakage (the real corpus lost 94–107 cross-file references across two
  restructures, each caught only by multi-round audit) — heading numbers were already
  render-derived (contract-slimming); in-prose references were not.
- **The injected number is derived-not-stored (fingerprint version 3 → 4).** `prose_hash`
  normalizes the anchor-bound number away before hashing, so refreshing it (e.g. §6.5 → §7.2 after
  a reorder) never marks the referencing section stale/drifted — same order-out-of-hash principle
  as contract-slimming. Existing ledgers migrate once via `docspec render <article> --rebaseline`
  (prose preserved); may share contract-slimming's migration wave.
- **Cross-document prose references are machine-verifiable for the first time.** `docspec check`
  validates every prose anchor's target id in the same dead-reference class as
  `realizes`/`governed-by`: pointing at a non-existent or retired id is an ERROR, naming the prose
  location and the dangling id. Hand-written literal `§9.2` could never be checked.
- **`docspec lint` V21 (WARN)** flags any un-anchored literal chapter reference left in prose
  (`§9.2`, `第 6 章`, `見 §12`) — it drifts on reorder; bind an anchor instead. External-standard
  clause citations (`ISO 13849-1 §4.2`) are exempt (ground-truthed against the real corpus).
- **`publish` freezes the anchor's current number into the immutable snapshot** and strips the
  binding comments (zero mechanical residue). Anchor resolution runs only inside prose spans —
  code fences / inline code / URLs / image paths are byte-exact untouched. Migration of the ~100
  台中港 literal references to anchors is agent-assisted (each old number's target is a semantic
  judgment); lint V21 lists them, the agent binds each anchor once.

### Changed — contract slimming: concept-required, the rest on-demand (**BREAKING**)

- **A missing `decisions.yaml` is now a legal empty state** ("this section owns no normative
  rulings"): `status` no longer reports `waiting(missing:decisions)` and `ready` no longer refuses
  (nor hints at creating an empty `entries: []` container — the empty-shell anti-pattern is
  withdrawn; 70.3% of real-corpus decisions files were one-line shells). A decisions.yaml that
  exists but is structurally broken still fails loud — absence is legal, presence carries
  responsibility.
- **`concept.brief` sub-fields are all schema-optional (differential brief)**: write a field only
  when it differs from what the ancestor chain provides; absent = inherit. The root section still
  must fill audience/depth/breadth (hierarchy check, unchanged).
- **Live-tree `history.yaml` is removed from the leaf contract**: dead decisions stay in their
  owning `decisions.yaml` marked `status: superseded`/`deprecated` (addressable for the supersede
  chain, deps two-hop, and repoint guidance); `history.yaml` exists only inside `corpus/_archive/`
  retirement packages. `docspec retire` is now a non-mutating report; `retire-section` is
  unchanged. Old projects with a live-tree history.yaml still load; `docspec tidy` reports them.
- **Outline numbering is render-derived** (BREAKING for corpora with hand-numbered titles):
  `concept.title`/`group.yaml title` carry the bare name; `render` derives `6` / `6.1` from
  `order` + tree position and injects the prefix into `_latest.md` headings. Renumbering after a
  reorder is a skeleton re-render — prose and fingerprints are reused (F2), no false staleness.
  New optional `numbering: arabic|appendix|none` field (inherits down the tree): appendix gives
  `附錄 A` / `A.1` letter series, none renders unnumbered without consuming a number.

### Added — engine primitives `docspec mv` / `docspec rename-term` / `docspec tidy`

- **`docspec mv <old> <new>`**: atomic rename/move of a leaf/group folder that also rewrites every
  path-keyed reference in the same transaction — `_latest.md` section/group markers (prose is
  never orphaned/discarded), audit/roadmap path targets — then self-runs `check`; any failure
  rolls back with zero partial effect. Asset mode (`docspec mv docs/assets/a.png b.png`) renames
  an image and rewrites its `![](…)` references. v1 scope: same-article leaf/group (article-root
  moves are a later extension).
- **`docspec rename-term <old> <new> [--article] [--dry-run]`**: deterministic project-wide term
  substitution inside prose spans only (code fences, inline code, URLs, image paths, and bare
  identifiers like `OCC_LIMIT_*` stay byte-exact), with a full-hit dry-run preview and in-place
  prose-fingerprint maintenance (no false drift).
- **`docspec tidy [--dry-run]`**: deterministic, idempotent corpus migration — deletes `entries: []`
  shells, strips brief fields byte-identical to the nearest ancestor, strips hand-written arabic
  numbering prefixes from titles, and renames leaf/group folders to delivery-language title slugs
  (each rename via the `mv` primitive; sibling slug collisions refused); reports live-tree
  history.yaml files with migration guidance; closes with the per-article `render --rebaseline`
  reminder.

### Added — lint rules V19 / V20 (both WARN, corpus hygiene)

- **V19**: a `concept.brief` sub-field byte-identical (after strip) to the value supplied by the
  nearest ancestor — copy-paste inflation; delete the field to inherit (batch: `docspec tidy`).
- **V20**: a `concept.yaml`/`group.yaml` title beginning with an outline-numbering prefix
  (`6.`, `６．`, `6、`, `A.`, `附錄 A`) — numbering is render-derived; a hand prefix is a second,
  drifting source. Ground-truthed on the real 台中港 corpus: 239 + 145 hits, zero false positives.

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

- `docspec ready <article>` (batch graduation, per-section independent transactions). (The
  missing-`decisions.yaml` refusal + `entries: []` hint this batch originally added was later
  withdrawn by contract slimming — a missing decisions.yaml is now a legal empty state.)
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
  `apply` / `develop` / `release` stances updated; lint `Ve3` now flags both ```mermaid and raw
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
- `apply` receives ancestor normative rulings and the project purpose in its aperture; `factcheck`'s
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
- `apply`/`factcheck` re-examine the document's title/framing on a deep revision, not just the
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
  declare victory right after `apply` and skip `factcheck`.
- `docspec status` projects the sync-state → skill-routing legend (which skill picks up which
  staleness flag).

### Fixed — forest governance, staleness axes, and deliverable-cleanliness (backstage-leak family)

- **`realizes` liveness**: `check` now rejects a `realizes` edge into a retired or misrouted
  (concept-kind) target instead of silently accepting it; a superseded-but-present target is still
  allowed through as a legal transition window. `aperture` surfaces the live/superseded status of a
  realized decision and walks the supersede chain to its terminal live successor, instead of
  silently anchoring `apply`'s output on dead truth.
- **Transitive blast radius**: `docspec impact <concept>` now reports the *transitive*
  `governed-by` blast radius (every downstream document, not just direct children) — this matches
  what `status` actually re-stales, so `impact` no longer under-reports the effect of a change.
  Cycle-path reporting trims the DFS lead-in so only the real cycle prints, not an unrelated
  upstream path fragment.
- **New `stale-style` ledger axis**: a `style_fingerprint` (hash of `writing-guide.md` +
  `glossary.yaml`) means restyling the shared writing guide is no longer invisible to staleness —
  every section written against the old style is flagged `stale-style` (lowest-priority axis: own >
  upstream > inherited > style) and routes through `apply`, clearable via `render --ack`.
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
  backstage brief/coverage/coherence/ancestor-normative blocks it projects to `apply`/`develop` as
  "obey, never narrate" — `apply`/`develop` no longer open a section with a
  "this section establishes…" role-framing announcement. Extended to the whole-document overview
  level: the root/overview section may not narrate the document's own chapter structure or refer to
  the document as a self-made artifact ("this spec splits the work into…").
