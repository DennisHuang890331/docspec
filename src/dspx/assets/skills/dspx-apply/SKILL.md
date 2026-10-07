---
name: dspx-apply
description: >-
  Bring a section's prose into line with its source — the single skill for all prose-to-source
  alignment (the former draft + edit). Two engine-routed modes: rewrite blind-renders a section from
  its aperture (create/revise/redraft targets, or stale-own/upstream/unwritten sections); align
  narrative-aligns existing prose on docs/_latest or acknowledges it with a verdict verb (align/review
  targets, or stale-inherited/style/norm/drifted). You pick the mode from the engine's routing, never
  from an operator-read table. Use whenever an ArtiSpec section's prose needs writing, rewriting, or
  aligning — any stale-*/unwritten state in artispec status, or any revise/align change target.
license: PolyForm-Noncommercial-1.0.0
compatibility: Requires the ArtiSpec CLI (`artispec`) from the `docspec` distribution. For uv tool installs with missing PATH, use the directory printed by `uv tool dir --bin`; for a virtual environment, use its Scripts/bin directory; never reinstall merely to repair PATH (an explicitly requested upgrade is separate).
metadata:
  author: docspec
  version: "2.6"
---

Align a section's prose with its committed source. You are a constrained renderer and copy-desk, not an author — the outline already decided WHAT each section says.

**Input**: an article or section (inside a change, the change id). If vague, run `artispec status <article>` or discover changes with `artispec change` and inspect `artispec change show <id>`; take the document sections with work, and ask the human only when the target itself is ambiguous. `artispec guide` carries the file model, aperture, and filing rules — projected live, assume they moved since this file was written; don't restate mechanics or guess field names.

**Steps**

`get`, `instructions`, `find`, `check` and `diff` default to official content. Inside a document change, use the same explicit `--change <id>` for these queries and for `put` / `render`. Read the reported context and sources before editing. Draft prose that is missing or stale is a diagnostic, not a clean review of official prose; follow the indicated apply/render step. Queries never generate previews or write ledgers.

Before writing, read `artispec handover` and `artispec roadmap`. Reuse the work item for this scope; only if absent, run `artispec roadmap add --title "…" --ref change:<id>` (inside a change) or `--ref doc:<article-or-section>` (otherwise), and keep the returned id. Register only existing targets; link after creation when necessary. Never duplicate work on resumption. Before handing over, update its links and rewrite the entire handover note with `artispec handover write`.

After finding the work, read `artispec roadmap show <work-id>` (or `--json`), then open its referenced original records only for details needed to write. Missing information does not mean no constraints; a superseded reference does not authorize silently adopting its replacement. The summary is read-only and does not refresh records or rewrite handover. An unfrozen document is not a request to freeze it: only the owner's explicit request authorizes freezing. Software differences remain visible without blocking document delivery.

`artispec change --all` includes change history; shared `change` and `change show` queries do not refresh tasks, run tests, write handover or move records. New changes share `docspec/changes/`, but document targets/staging, creation timing and completion rules stay unchanged. A software change in the same root is handled by its software role, not by converting its tasks into document targets or adding software forms to document work.

1. **Route the mode** — anchor `artispec status <article>` / `artispec change status <id>`. Inside a change the target `action` picks the mode (create / revise / redraft → **rewrite**; align / review → **align**; move / retire are structural transactions, never apply). Outside one the staleness type picks it (stale-own / stale-upstream / unwritten / redraft → **rewrite**; stale-inherited / stale-style / stale-norm / drifted → **align**). The engine routes — never read a who-picks-it-up table.

2. **Pull the projection** — `artispec instructions apply <section>`. The schema projects the current mode, clear-with verb, writing principles, verdict-verb whitelist and dispatch exclusions. Follow the existing writing-guide, audience and kind: task steps and lookup differ from explanations. Retain preconditions, expected results, failure handling and necessary limits from sources; keep governance provenance and test diaries in records, without hiding support or unverified limits. Never re-derive rules from memory or invent content to fill a form.

3. **rewrite** — render each writable leaf with its required sources ready and document `errors` empty, blind to sibling prose. `software_errors` are reported separately and do not block document work; an aggregate check exit code may still be nonzero for software. `artispec render <article>` first materializes the skeleton (slots, markers, headings) — never hand-add a marker, render owns it. Write from the committed layer only (`concept` / `brief` / `must_cover`, each active decision's `statement`, the section's `material.md`, the parent-chain briefs, the inherited normative rulings you must OBEY, the shared writing guide, the lean glossary index); coherence comes from the guide, NOT from reading neighbours. Write **only body prose** into the section's slot — never the heading, the markers, or another section's prose.

   > **IMPORTANT — zero-inference:** a fact OR rationale absent from material / outline / decisions is written `[TBD]` and you move on; fabricating a number, name, or causal claim is the one unforgivable failure (`lint` blocks a leftover `[TBD]`; nothing catches a plausible fabrication). Faithfully expanding shorthand — a cumulative `+`, ranges, inheritance in `material.md` into explicit per-row values — is rendering, not fabrication. If a draft would contradict a decision, emit a `[!WARNING]` naming it and stop on that section. When a sentence restates a project decision, the owner's information or a software requirement that the section's concept does not `realizes`, report it to the main agent so the link is added (you do not edit concepts).

   Re-render the affected leaf for any change (sections are cut fine enough that this is the cheap, correct unit — no surgical patches). `artispec render` again to stamp the source hash, then surface the output to the human before the next section.

4. **align** — run the editorial desk on docs/_latest in order: line edit → copy edit → proofread (once you reach proofread you STOP rewriting; it only catches, real fixes loop back). Route each check by the projected exclusion list: deterministic → the engine (`artispec lint` / `artispec check`); judgment → a clean-context subagent. **Every subagent brief opens with "You do SEMANTIC work only" and copies the projected exclusion list verbatim** — that is how the punctuation-width sweep never slips into a semantic brief again. Touch ONLY the deliverable working copy; read a section's `brief` / parent chain to align tone, but never change the outline or decisions.

5. **Clear the verdict with the matching verb — after the human rules** — a verdict is the HUMAN's semantic decision, not yours (three-role doctrine): before ANY `--ack`/`--ack-own`, present the section, its staleness state, and your proposed justification to the human and get explicit consent; the `--reason` carries the human's ruling (gist or verbatim). The projected Verdict-verb block is authoritative. In short: prose changed → plain `artispec render`; human-confirmed legitimately-unchanged (stale-inherited / style / norm) → `artispec render <article> --ack <section>`; a structural / metadata-only source change (stale-own / upstream) → `artispec render <article> --ack-own <section> --reason <text>`; a content-bearing change → escalate to rewrite via `artispec stale <section>` (or `artispec stale <article>` for a whole re-projection).

6. **Gate loop** — `artispec check` (references + structure) and `artispec lint` (cleanliness: no leaked machinery, no `[TBD]`/placeholder, no leftover `[!WARNING]`) until zero ERROR. Read check coverage: scans do not establish prose meaning or delivery completion; stale previews can still be scanned. Loop rewrites back to line/copy; the engine gates are your backstop.

**Pause if:**
- The target is ambiguous → ask which section; don't guess.
- A draft would contradict a decision → emit `[!WARNING]`, stop that section (don't write around it).
- A fix would change meaning (a content gap, a cross-section contradiction) → raise a non-blocking `artispec audit` finding or flag it for `develop`; never invent, never leave a `[TBD]`/`[!WARNING]` in `_latest.md`.
- The human interrupts.

Optional: before an align edit, `artispec show <section> --impact` previews which other documents the change ripples to.

**Output**

```
## apply (<rewrite|align>) — <article>/<section>
rewrite: rendered N leaf(s); [TBD] left: <sites or none>; check/lint: 0 ERROR
align:   line/copy/proof findings acted on; residue: <subagent or none>; check/lint: 0 ERROR
Verdict: <artispec render | render --ack <sec> | render --ack-own <sec> --reason "…">
Surfaced to the human: <diff / output path>
```

**Guardrails**
- rewrite: write from the committed layer only, blind to siblings; honor the `brief` as a hard contract; `[TBD]` and keep going; never read a decision's `why`/`rejected` or `history` — the thinking layer is out of aperture.
- align: engine-first inside each stage; keep proofread catch-only and loop rewrites back; change meaning never — numbers, terms, normative claims stay byte-for-byte; touch the selected deliverable only, never frozen `docspec/changes/_versions/.../snapshot/` or legacy published snapshots. `docs/` contains the latest projection; do not restore historical outputs there.
- A verdict (`--ack`/`--ack-own`) is the human's ruling — never run one without the human's explicit consent, and never fabricate an edit or run a perturb-render-revert dance to force a re-stamp (byte-identical end state, zero trace, launders the verdict).
- Copy the dispatch-exclusion list verbatim into every semantic subagent brief; punctuation width → `artispec edit --punct` (engine-deterministic, code/URLs byte-exact), never a hand-rolled full-text width sweep or a blind regex. `edit` writes the official deliverable, so it refuses while a section is in an active change (the official face is frozen — edit after archiving, or through the change workflow).
- Don't leak corpus-only content into `_latest.md` (a `rejected` option, a retired decision's rationale, `history.*` prose).
