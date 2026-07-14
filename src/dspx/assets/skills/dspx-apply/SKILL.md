---
name: dspx-apply
description: >-
  Bring a section's prose into line with its source — the single skill for all prose-to-source
  alignment (the former draft + edit). Two engine-routed modes: rewrite blind-renders a section from
  its aperture (create/revise/redraft targets, or stale-own/upstream/unwritten sections); align
  narrative-aligns existing prose on docs/_latest or acknowledges it with a verdict verb (align/review
  targets, or stale-inherited/style/norm/drifted). You pick the mode from the engine's routing, never
  from an operator-read table.
license: PolyForm-Noncommercial-1.0.0
compatibility: Requires the docspec CLI (installed via uv tool; not on PATH in a fresh shell — run it from the dir printed by `uv tool dir --bin`, never reinstall).
metadata:
  author: docspec
  version: "2.0"
---

Align a section's prose with its committed source. You are a constrained renderer and copy-desk, not an author — the outline already decided WHAT each section says.

**Input**: an article or section (inside a change, the change id). If vague, run `docspec status <article>` (or `docspec change status <id>`) and take the sections with work; ask the human only when the target itself is ambiguous. `docspec guide` carries the file model, aperture, and filing rules — projected live, assume they moved since this file was written; don't restate mechanics or guess field names.

**Steps**

1. **Route the mode** — anchor `docspec status <article>` / `docspec change status <id>`. Inside a change the target `action` picks the mode (create / revise / redraft → **rewrite**; align / review → **align**; move / retire are structural transactions, never apply). Outside one the staleness type picks it (stale-own / stale-upstream / unwritten / redraft → **rewrite**; stale-inherited / stale-style / stale-norm / drifted → **align**). The engine routes — never read a who-picks-it-up table.

2. **Pull the projection** — `docspec instructions apply <section>`. It projects, from the schema as the single source: the current mode + the clear-with verb, the **writing principles** (payload-first, inverted-pyramid, structure-into-tables, kind, the scaffolding / cross-ref / metaphor bans, zero-inference), the **Verdict-verb whitelist** (plus which brief field decides ack-or-rewrite), and the **Dispatch-exclusion list**. Obey it verbatim; never re-derive these from memory.

3. **rewrite** — render each writable leaf (its `concept` + `decisions` present and `docspec check` green) from its aperture, blind to its siblings. `docspec render <article>` first materializes the skeleton (slots, markers, headings) — never hand-add a marker, render owns it. Write from the committed layer only (`concept` / `brief` / `must_cover`, each active decision's `statement`, the section's `material.md`, the parent-chain briefs, the inherited normative rulings you must OBEY, the shared writing guide, the lean glossary index); coherence comes from the guide, NOT from reading neighbours. Write **only body prose** into the section's slot — never the heading, the markers, or another section's prose.

   > **IMPORTANT — zero-inference:** a fact OR rationale absent from material / outline / decisions is written `[TBD]` and you move on; fabricating a number, name, or causal claim is the one unforgivable failure (`lint` blocks a leftover `[TBD]`; nothing catches a plausible fabrication). Faithfully expanding shorthand — a cumulative `+`, ranges, inheritance in `material.md` into explicit per-row values — is rendering, not fabrication. If a draft would contradict a decision, emit a `[!WARNING]` naming it and stop on that section.

   Re-render the affected leaf for any change (sections are cut fine enough that this is the cheap, correct unit — no surgical patches). `docspec render` again to stamp the source hash, then surface the output to the human before the next section.

4. **align** — run the editorial desk on docs/_latest in order: line edit → copy edit → proofread (once you reach proofread you STOP rewriting; it only catches, real fixes loop back). Route each check by the projected exclusion list: deterministic → the engine (`docspec lint` / `docspec check`); judgment → a clean-context subagent. **Every subagent brief opens with "You do SEMANTIC work only" and copies the projected exclusion list verbatim** — that is how the punctuation-width sweep never slips into a semantic brief again. Touch ONLY the deliverable working copy; read a section's `brief` / parent chain to align tone, but never change the outline, decisions, or develop.md.

5. **Clear the verdict with the matching verb** — the projected Verdict-verb block is authoritative. In short: prose changed → plain `docspec render`; reviewed-and-legitimately-unchanged (stale-inherited / style / norm) → `docspec render <article> --ack <section>`; a structural / metadata-only source change (stale-own / upstream) → `docspec render <article> --ack-own <section> --reason <text>`; a content-bearing change → escalate to rewrite via `docspec stale <section>` (or `docspec stale <article>` for a whole re-projection). Give a REAL `--reason`.

6. **Gate loop** — `docspec check` (references + structure) and `docspec lint` (cleanliness: no leaked machinery, no `[TBD]`/placeholder, no leftover `[!WARNING]`) until zero ERROR. Loop rewrites back to line/copy; the engine gates are your backstop.

**Pause if:**
- The target is ambiguous → ask which section; don't guess.
- A draft would contradict a decision → emit `[!WARNING]`, stop that section (don't write around it).
- A fix would change meaning (a content gap, a cross-section contradiction) → raise a non-blocking `docspec audit` finding or flag it for `develop`; never invent, never leave a `[TBD]`/`[!WARNING]` in `_latest.md`.
- The human interrupts.

Optional: before an align edit, `docspec show <section> --impact` previews which other documents the change ripples to.

**Output**

```
## apply (<rewrite|align>) — <article>/<section>
rewrite: rendered N leaf(s); [TBD] left: <sites or none>; check/lint: 0 ERROR
align:   line/copy/proof findings acted on; residue: <subagent or none>; check/lint: 0 ERROR
Verdict: <docspec render | render --ack <sec> | render --ack-own <sec> --reason "…">
Surfaced to the human: <diff / output path>
```

**Guardrails**
- rewrite: write from the committed layer only, blind to siblings; honor the `brief` as a hard contract; `[TBD]` and keep going; never read `develop.md`, a decision's `why`/`rejected`, or `history` — the thinking layer is out of aperture.
- align: engine-first inside each stage; keep proofread catch-only and loop rewrites back; change meaning never — numbers, terms, normative claims stay byte-for-byte; touch the deliverable only, never any `archive/` snapshot (immutable published history).
- Clear a staleness verdict with the MATCHING verb — never fabricate an edit or run a perturb-render-revert dance to force a re-stamp (byte-identical end state, zero trace, launders the verdict).
- Copy the dispatch-exclusion list verbatim into every semantic subagent brief; punctuation width → `docspec edit --punct` (engine-deterministic, code/URLs byte-exact), never a hand-rolled full-text width sweep or a blind regex. `edit` writes the official deliverable, so it refuses while a section is in an active change (the official face is frozen — edit after archiving, or through the change workflow).
- Don't leak corpus-only content into `_latest.md` (a `rejected` option, a retired decision's rationale, `history.*` prose).
