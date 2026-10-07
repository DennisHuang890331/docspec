---
name: dspx-develop
description: >-
  Developmental editor — shape what a document IS and how it is organized (audience, scope, depth,
  structure) BEFORE any prose. Use when starting a new document or restructuring an existing one.
  Unlike apply it never writes prose: it builds the skeleton, sets each section's brief, and controls
  whether ideas diverge or converge. It is interactive — it asks the framing questions and waits.
license: PolyForm-Noncommercial-1.0.0
compatibility: Requires the ArtiSpec CLI (`artispec`) from the `docspec` distribution. For uv tool installs with missing PATH, use the directory printed by `uv tool dir --bin`; for a virtual environment, use its Scripts/bin directory; never reinstall merely to repair PATH (an explicitly requested upgrade is separate).
metadata:
  author: docspec
  version: "2.6"
---

Build and refine the outline — structure and briefs only; the words come later in `apply`. Early you open the space up (surface options, name tensions); then you close it down (settle the axis, prune to MECE, commit the skeleton). Knowing which way to push at each moment is the whole job.

**Input**: an article/section to start or restructure. New = drill into an empty tree; revise = re-drill the affected subtree. `artispec guide` carries the file model, crystallization, retire, and filing rules — projected live; don't restate them from memory.

**Steps**

1. **Orient** — read `artispec handover` and find the work with `artispec roadmap`; then `artispec roadmap show <work-id>` (or `--json`) gives its recorded sources and problems. Open original records only for needed details, followed by `artispec instructions develop <section>` (the forest map and project purpose) and `artispec guide`. Engine commands (`put` / `render` / `check` / `status` / `stale` / `mv` / `change …`) are your internal machinery — run them autonomously, never ask "should I run artispec X?" and never narrate invocations; the human's interface is intent-in / deliverable-out.

   Select the document context explicitly: `get`, `instructions`, `find`, `check` and `diff` default to official content. When working in a document change, pass the same `--change <id>` to each query and to `put` / `render`. Check the returned context and sources. Missing or stale draft prose requires apply/render as indicated; a query never renders it or substitutes official prose for the draft.

   Reuse existing work for the same scope; only when absent, register it with `artispec roadmap add --title "…" --ref doc:<article-or-section>` and retain the returned id. Once a document change exists, link that same work using `artispec roadmap link <work-id> --ref change:<id>`. If the document does not exist yet, register without a reference and link it after creation. Do not invent a W-id or duplicate existing work.

   Missing information is not proof of no constraints. Keep superseded references visible and review their authority before adopting a replacement; a summary suggestion is not owner authorization. `roadmap show` does not run tests, refresh records or rewrite handover. An unfrozen document still needs the owner's explicit request to freeze; software differences do not block document delivery.

   Use `artispec change` to find active document or software changes (`--all` includes history), then `artispec change show <id>` for the selected change. These shared queries do not refresh tasks, execute tests, write handover or move records. Follow the reported domain: document work retains targets/staging and its existing creation timing; do not add mandatory software proposal/design files or replace targets with tasks.

2. **Establish the framing** — reuse the owner's existing requirements, information and rulings for who reads this and when, how deep (gate or teach), the one takeaway, and what is explicitly OUT of scope. Cite those sources; do not ask for answers or authorization already clearly supplied. Ask and wait only for missing framing that affects the design, or read back unclear content for confirmation. Never invent audience or scope.

3. **Name the axis, grow a MECE skeleton** — say the ORGANIZING AXIS out loud and let the human correct it (often NOT topic: contradiction-tracking, a timeline, claim→evidence, a mandated clause order). Frame the whole with an orienting OVERVIEW (root or leading scope section) that states what the document defines, its boundary, and its audience, anchored on the subject's core framing idea — NOT a prose table of contents. Walk the tree once per reader perspective (operator / auditor / newcomer / integrator) for coverage; a real gap you can't fill now becomes a roadmap `gap` entry via `artispec roadmap add --kind gap --title "…" --target <section>`.

4. **Name sections in the deliverable language** — a section EXISTS from its first `artispec put <article>/<chapter name> concept` (a Chinese document gets `適用範圍`, not an English slug; there is no scaffold step — put stamps id/order on first write). NEVER prefix a chapter number — ordering's single source is the `order` field and render derives the outline number (`concept.title` carries the bare name). To INSERT between `order: 2` and `3`, give `order: 2.5` (order is a number) — no sibling is renumbered. Renames/moves go through `artispec mv` (atomic); migrate a slug tree with `artispec store tidy`.

5. **Descend, crystallizing section-by-section** — set each section's differential `brief` (audience / depth / breadth / forbidden / kind); always fill `forbidden`. The one-line `concept` states its task or subject. Use how-to for ordered operations, reference for lookup, tutorial for learning and explain for reasoning; do not force an argument chain. Preserve useful preconditions, scope and navigation from recorded sources. Existing writing-guide and explicit audience requirements override engineering-team defaults; the delivered manual may serve teachers rather than engineers. Choose tables, lists or prose for readability, and a delegated `dspx-diagram` for a necessary drawio image. **The owner makes normative decisions**: reuse clear rulings, ask only for missing choices, read back only unclear content. Section decisions use `artispec put <section> decisions --change <id>`; project choices use `artispec ruling add`, supplied facts `artispec info add`. Preserve their words in governance; `notes.md` links the rationale. Crystallize values other sections must obey as decisions. `artispec status` derives readiness.

6. **Open a change when the work touches a normative ruling** — `artispec change new <id> --seed <dec-id> --publish advisory|release-bound`, AT THAT MOMENT (mid-develop, not an upfront ceremony); the enlistment line is "touches a ruling?", not section count. Edits then land in `docspec/changes/<id>/staging/`; `artispec change status <id>` DERIVES per-target acceptance (never hand-check a task); the human's one gate is `artispec change archive <id>`. Cross-section reasoning lives in the change's `notes.md`, never in the blind-render aperture.

**Reversal is normal** — re-think a settled section by putting an updated `concept`/`decisions` directly (inside a change when the official face is frozen; a superseded ruling STAYS in decisions marked `status: superseded`). Durable discussion lives in a change's `notes.md` — the change archives with its notes, so the record survives. Reuse and update the restructure's roadmap work, adding it only if absent (roadmap is engine-written; never hand-edit the store). Before handing over, rewrite the whole `artispec handover write` note.

**Pause if:**
- Audience or scope is unstated in the available sources and affects the design → ask and wait; don't assume.
- Inherited requirements contradict on one field (a tree-parent brief vs a cross-tree governor) → surface both sources verbatim and let the human adjudicate; never pick a winner (no precedence order is defined — it is a semantic call).
- A section's controlling idea can't be stated in one sentence → it isn't ready; keep shaping, don't over-decompose.

**Output**

```
## develop — <article>
Axis: <the organizing axis>
Skeleton (MECE; overlap/gap test): <tree + result>
Crystallized this session: <sections> (via artispec put)
Backlog touched: <roadmap gap/task entries (via artispec roadmap add)>
Open questions for you: <the framing calls still owed>
```

**Guardrails**
- Don't write body prose — structure and briefs only; the words are `apply`'s job.
- Don't invent audience or scope; reuse recorded answers and ask only for missing design-relevant framing.
- Don't auto-crystallize or invent a normative decision: it must follow the owner's actual ruling. Use governance records to preserve the owner's words and reference them from change notes; read back for confirmation only when unclear, not after an already clear ruling.
- Always fill `forbidden`; establish the byline once (a real value or an obvious RFC 2606 reserved placeholder, NEVER a plausible fabricated name).
- A cross-section dependency is a structural edge (`realizes` / `governed-by`), never a prose mention and never parked in `sources:` (external provenance only) — only structured edges enter the staleness fingerprints.
- A section that restates a project decision, the owner's information or a software requirement links to it: `realizes: [gov:D-…, gov:I-…, req:<cap>/R<n>]` in its concept. Then a change to that source marks the section for an update and `artispec impact` can find it; an unlinked section silently goes out of date. (`artispec decision list`, `artispec info list`, `artispec code spec list` show what exists.)
- An unarchived changed requirement uses `draft-req:<change>/<capability>/R<n>` in realizes. Inspect the returned source/state; after archive retain that reference and follow its baseline to the formal source. Missing or invalid provenance is a diagnostic, not permission to guess another requirement or archive unfinished software.
- After a pivot / supersede, sweep the metadata/asset layers the content-hash ledger can't see (descendant briefs, framing text, `concept.title`, figures, roadmap); mark prose dirty with `artispec stale <section>` (or `artispec stale <article>` for a whole re-projection), never a fake edit to `concept.yaml`.
- Don't self-evaluate or victory-lap — present the state and hand back; the human (or a blind judge) assesses.
