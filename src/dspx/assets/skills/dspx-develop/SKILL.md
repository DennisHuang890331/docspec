---
name: dspx-develop
description: >-
  Developmental editor — shape what a document IS and how it is organized (audience, scope, depth,
  structure) BEFORE any prose. Use when starting a new document or restructuring an existing one.
  Unlike apply it never writes prose: it builds the skeleton, sets each section's brief, and controls
  whether ideas diverge or converge. It is interactive — it asks the framing questions and waits.
license: PolyForm-Noncommercial-1.0.0
compatibility: Requires the docspec CLI (installed via uv tool; not on PATH in a fresh shell — run it from the dir printed by `uv tool dir --bin`, never reinstall).
metadata:
  author: docspec
  version: "2.0"
---

Build and refine the outline — structure and briefs only; the words come later in `apply`. Early you open the space up (surface options, name tensions); then you close it down (settle the axis, prune to MECE, commit the skeleton). Knowing which way to push at each moment is the whole job.

**Input**: an article/section to start or restructure. New = drill into an empty tree; revise = re-drill the affected subtree. `docspec guide` carries the file model, crystallization, ready/retire, and filing rules — projected live; don't restate them from memory.

**Steps**

1. **Orient** — `docspec instructions develop <section>` (the forest map, the roadmap backlog to check before starting, the project purpose) and `docspec guide`. Engine commands (`new` / `render` / `ready` / `check` / `status` / `stale` / `redraft` / `mv` / `put` / `change …`) are your internal machinery — run them autonomously, never ask "should I run docspec X?" and never narrate invocations; the human's interface is intent-in / deliverable-out.

2. **Interrogate → WAIT** — ask who reads this and when, how deep (gate or teach), the one takeaway, and what is explicitly OUT of scope. Get answers before descending; never assume audience or scope — the cheapest fixes now, the most expensive after prose exists. (Running end-to-end without pausing is a TEST-ONLY mode.)

3. **Name the axis, grow a MECE skeleton** — say the ORGANIZING AXIS out loud and let the human correct it (often NOT topic: contradiction-tracking, a timeline, claim→evidence, a mandated clause order). Frame the whole with an orienting OVERVIEW (root or leading scope section) that states what the document defines, its boundary, and its audience, anchored on the subject's core framing idea — NOT a prose table of contents. Walk the tree once per reader perspective (operator / auditor / newcomer / integrator) for coverage; a real gap you can't fill now becomes a roadmap `gap` entry via `docspec roadmap add --kind gap --title "…" --target <section>`.

4. **Name section folders in the deliverable language** — `docspec new <article>/<chapter name>` (a Chinese document gets `適用範圍/`, not an English slug). NEVER prefix a chapter number — ordering's single source is the `order` field and render derives the outline number (`concept.title` carries the bare name). To INSERT between `order: 2` and `3`, give `order: 2.5` (order is a number) — no sibling is renumbered. Renames/moves go through `docspec mv` (atomic); migrate a slug tree with `docspec store tidy`.

5. **Descend, crystallizing section-by-section** — set each section's `brief` (audience / depth / breadth / forbidden), writing ONLY the field that differs from the ancestor chain; always fill `forbidden`. Write each section's one-line `concept` as its ROLE in the argument (each conclusion the next section's premise), then split MECE or call it a leaf. Note when content should be a table, list, or **diagram** (a drawio image authored by a delegated `dspx-diagram` subagent — never TikZ/mermaid). Crystallize each part with `docspec put <section> concept|decisions|material` on the human's nod (the review checkpoint — present children as a batch), then graduate with `docspec ready <section>`.

6. **Open a change when the work touches a normative ruling or spans sections** — `docspec change new <id> --seed <dec-id> --publish advisory|release-bound`, AT THAT MOMENT (mid-develop, not an upfront ceremony); the enlistment line is "touches a ruling?", not section count. Edits then land in `changes/<id>/staging/`; `docspec change status <id>` DERIVES per-target acceptance (never hand-check a task); the human's one gate is `docspec change archive <id>`. Cross-section reasoning lives in the change's `notes.md`, never in the blind-render aperture.

**Reversal is normal** — re-open a settled section with `docspec new <section> --reopen` (rebuilds `develop.md` from its `concept.yaml`; reason lands in `develop.md` as you think, not after). A cross-section restructure reopens the ROOT's `develop.md` as the single central workbench; register it via `docspec roadmap add --kind task --title "…" --target <root-section>` (roadmap is engine-written now; never hand-edit the roadmap store).

**Pause if:**
- Audience or scope is unstated → ask and wait; don't assume.
- Inherited requirements contradict on one field (a tree-parent brief vs a cross-tree governor) → surface both sources verbatim and let the human adjudicate; never pick a winner (no precedence order is defined — it is a semantic call).
- A section's controlling idea can't be stated in one sentence → it isn't ready; keep shaping, don't over-decompose.

**Output**

```
## develop — <article>
Axis: <the organizing axis>
Skeleton (MECE; overlap/gap test): <tree + result>
Crystallized this session: <sections> → docspec ready
Backlog touched: <roadmap gap/task entries (via docspec roadmap add)>
Open questions for you: <the framing calls still owed>
```

**Guardrails**
- Don't write body prose — structure and briefs only; the words are `apply`'s job.
- Don't assume audience or scope; ask and wait.
- Don't auto-crystallize — graduating a section is the human's checkpoint.
- Always fill `forbidden`; establish the byline once (a real value or an obvious RFC 2606 reserved placeholder, NEVER a plausible fabricated name).
- A cross-section dependency is a structural edge (`realizes` / `governed-by`), never a prose mention and never parked in `sources:` (external provenance only) — only structured edges enter the staleness fingerprints.
- After a pivot / supersede, sweep the metadata/asset layers the content-hash ledger can't see (descendant briefs, framing text, `concept.title`, figures, roadmap); mark prose dirty with `docspec stale <section>` (or `docspec stale <article>` for a whole re-projection), never a fake edit to `concept.yaml`.
- Don't self-evaluate or victory-lap — present the state and hand back; the human (or a blind judge) assesses.
