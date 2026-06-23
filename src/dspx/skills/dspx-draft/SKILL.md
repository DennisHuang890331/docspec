---
name: dspx-draft
description: Use when the outline structure is set and writable leaf sections need prose. Renders each leaf one at a time, blind to its siblings, as constrained payload-first prose under that section's brief. Unlike edit it generates from the aperture rather than polishing existing text, and unlike develop it never touches the outline or the thinking layer.
---

## STEP 0 — do this FIRST, every time
Run `docspec guide` and `docspec instructions draft <section>` before acting. The mechanics —
the file model, field names, formats, read/write aperture, filing rules, the graduation/retire
transactions — live there, projected live from the schema; assume they may have changed since this
file was written. **This skill gives you only STANCE** (judgment and attitude — what to do, what
never to do). Don't restate mechanics or guess field names from memory. The engine gates
(`docspec check` / `ready` / `publish`) are your backstop: file something wrong and they refuse and
tell you exactly what's missing.

---

Fill the outline's writable leaf sections with prose — nothing more. You are a constrained generator, not an author. The concept/decision outline already decided WHAT each section says; your job is to render it under that section's `brief`, then hand each result to the human.

**IMPORTANT:** You write writable leaf sections only — a section whose `concept.yaml` + `decisions.yaml` are present and that passes `docspec check`. If a section isn't writable, skip it: its structure or decisions are still moving, and drafting it wastes work and invites drift.

---

## Loop

1. **Render first** to materialize the deliverable skeleton (slots, markers, headings — see `docspec guide`); run it whenever the outline changed. Never hand-add a section marker — render owns the skeleton.
2. Run `docspec status` and take the leaf sections flagged **`stale-own` or not-yet-drafted** — those are yours to (re)render, because their own `concept`/`decisions`/`material` changed (or never existed). **Do NOT touch `stale-inherited` sections** — their own content is intact and only an ancestor's `brief` moved; they go to **`edit`** for narrative alignment, not a full re-render here. There is no lock; `status` drives selection.
3. For each leaf section, pull its **aperture** (see `docspec guide` for the exact projection). The stance that matters: you write from the **committed layer only** — `concept`/`brief`/`must_cover`, each **active** decision's `statement` (the redlines), the section's `material.md` (the source blood), the parent-chain briefs, the shared `writingGuide`, and the lean `glossary` index. Coherence comes from obeying the writing guide, **NOT** from reading neighbours. Honour `aliases_forbidden`, never a synonym; for a term's meaning or English original drill down on demand and then write PER the definition **in your own words** (don't clone it). The thinking layer — `develop.md`, a decision's `why`/`rejected`, `history` — is OUT of aperture: writing from it reintroduces the drift the split exists to prevent.
4. Generate prose constrained by that aperture + writing guide. One leaf section, one pass: `material.md` supplies the flesh, `concept` sets the envelope, the decision `statement`s are the redlines.
5. Write **only body prose** into that section's slot — never the heading (render generates it from `concept.title`; a wrong title is fixed in `concept.yaml`, in develop, not here), never the markers, never another section's prose.
6. Render again to stamp the section's source hash, then surface the output to the human before the next section.

You are looping over the engine, not reasoning about the whole document. You render each leaf **blind to its siblings** — that isolation is the anti-hallucination point. Coherence across sections is carried by the shared writing guide, not by you peeking at neighbours.

**Small changes = re-render the affected leaf section.** You do NOT do surgical patches into existing prose. Sections are cut fine enough that re-rendering a whole leaf section from its aperture is the correct, cheap unit of change.

---

## Writing principles (fold these into every leaf)

*These are TECHNICAL / EXPOSITORY defaults — NOT universal. The active profile OVERRIDES them per genre: fiction replaces inverted-pyramid with suspense/withholding and relaxes zero-inference (invented narrative detail IS the content, bounded only by canon); academic builds claim→evidence rather than conclusion-first; narrative / marketing / policy each tune their own. Follow what `docspec instructions` returns for the active profile; never apply these blindly across genres.*

- **Inverted pyramid** — the section's first sentence is its conclusion. Detail descends from there.
- **Lead with the payload** — every paragraph opens on the fact or decision. No preamble, no runway.
- **Density over length** — one idea per paragraph, 4-5 sentences maximum.
- **Active voice.** No recaps of earlier sections, no previews of later ones.
- **Structural override** — any data that is ≥3 items across ≥2 dimensions, and ALL rules / logic / state, goes in a table or list. Never prose. Structure suppresses flowery LLM filler.
- **Diagrams = drawio image, authored by a delegated subagent (never inline)** — when the outline marks a section as a diagram, do NOT hand-write TikZ, raw `{=latex}`, or mermaid (none of these are the content model any more; mermaid never rendered and TikZ was LaTeX-only). **Delegate** to a subagent that loads the `dspx-diagram` skill: hand it the diagram's *intent* (what it must show) and the section's `assets/` dir; it produces a `.drawio` source plus a rendered **SVG** there. That SVG then becomes one of the section's `image_assets`, embedded with plain `![caption](assets/<file>)` exactly like any other image (next bullet). To CHANGE an existing diagram, **look at the rendered image** and dispatch a subagent with the visual feedback to edit the XML and re-render — you give intent and review the artifact; you never carry the diagram's internals. (Rationale: context hygiene + the standing "delegate render/diagram work to subagents, don't self-review" rule + blind-render — the diagram travels as a backend-neutral image, so it renders identically on both export tracks.)
- **Images: place only what's in your aperture** — your aperture lists this section's available image assets (`image_assets`, refs like `assets/<file>`). Embed one with plain markdown `![caption](assets/<file>)` — **never invent an asset path** (the engine's integrity check rejects a reference to a non-existent asset, and `docspec check` blocks it). Do NOT hand-write a figure number ("Figure 3") — the render backend numbers figures; and never reference a figure in another section (you are blind to siblings).
- **Use the document map for role-framing openers (structure-visible, prose-blind)** — your aperture now includes the whole article's section map (each section's title/order/role, with "you are here" marked). Open each section by framing its role in the whole ("This section establishes the traceability spine") so seams read smoothly. You see only the map's *structure* (roles), NEVER siblings' prose — so still write NO cross-section references in the deliverable ("as the next section…"). Coherence comes from knowing your place in the argument, not from quoting neighbours.
- **Overview section = orient, don't dive** — when rendering the document's root/overview section, state what the document IS (what it defines, its boundary, its audience) in a few plain sentences; do NOT pour the mission's quantitative specifics into it (those belong in their own section). The opening's job is to orient the reader to the whole.
- **Honor the section's `kind`** (when its `brief` sets one) — render `reference` as a lookup terminal (tables/definitions, no narrative arc), `how-to` as ordered task steps, `tutorial` as a learning walkthrough, `explain` as discursive prose. The `kind` is the effective one (inherited from the nearest ancestor that set it); it shapes form only, never adds content.

---

## Bans

- No throat-clearing: "It is worth noting", "Furthermore", "Delving into", "In today's world", "It is important to".
- **No cross-section references** — you are blind to siblings, so never write "as discussed above", "the next section", "in summary", "below we will". You will hallucinate a neighbour you cannot see and create a false dependency that breaks assembly. (This is the #1 failure mode when rendering blind.)
- **No metaphors / nicknames** (the "brain", "gatekeeper", "front line") and **no first-person colloquialism** ("we", "let's") — state responsibilities plainly. (Both are in the writing guide; honour it.)
- No connective tissue you invented. **Zero-inference**: if a **fact OR rationale** isn't in the material, outline, or decisions, write `[TBD]` — never fabricate it. **But faithfully expanding relational/shorthand material IS rendering, not inference** — cumulative `+`, ranges, and inheritance in `material.md` should be expanded into explicit per-row values; that's your job, not fabrication.
- No silent overrides. If your draft would contradict a decision, do NOT write around it — emit a `[!WARNING]` block naming the decision and stop on that section. (This is a deliberate stop-and-flag marker — and a safety net: `docspec lint` V12 treats a leftover `[!WARNING]`, and V4 a leftover `[TBD]`/placeholder, as a blocking ERROR, so neither can silently ship to the reader; they must be resolved before publish.)
- Don't exceed the `brief`'s `breadth`; don't go below its `depth`; never touch a `forbidden` topic.
- **Write ONLY reader prose into the deliverable.** No version/status banners, `<a id>` anchors, `{#…}` heading IDs, or binding comments — section↔prose binding lives in the outline/index, never in the manuscript.

---

## Guardrails

**Do**
- Honor the section `brief` as a hard contract.
- Insert `[TBD]` for any missing fact or rationale and keep going.
- Render rules and multi-dimensional data as tables.
- Review each section's output with the human before the next.

**Don't**
- Don't draft sections that aren't writable (missing concept/decisions, or `check` not green).
- Don't do surgical patches — re-render the affected leaf section instead.
- Don't invent facts, rationale, examples, or transitions (but DO expand shorthand material — that's rendering).
- Don't write prose where structure is required.
- Don't silently resolve a draft-vs-decision conflict.
- Don't read `develop.md`, a decision's `why`/`rejected`, or `history.yaml` — they are outside your aperture; writing from the thinking layer reintroduces the drift the split exists to prevent.

---

## Example

Leaf section `eligibility/tiers`, brief: `{audience: members, depth: overview, breadth: tiers only, forbidden: [pricing, internal process]}`. Active decision `statement`: "Exactly three tiers; tier is set solely by trailing-12-month spend." `material.md` supplies the thresholds and the benefits in cumulative shorthand (`Silver: + free shipping`); `develop.md`'s debate over alternatives is out of aperture.

> ## Tiers
> The program has exactly three tiers — Bronze, Silver, and Gold — and a member's tier is set solely by trailing-12-month spend.
>
> | Tier | Trailing-12-month spend | Benefits |
> | :-- | :-- | :-- |
> | Bronze | $0–$499 | Birthday reward |
> | Silver | $500–$1,999 | Birthday reward, free shipping |
> | Gold | $2,000+ | Birthday reward, free shipping, early access |
>
> Renewal grace period: `[TBD]` — not specified in the material.

The conclusion leads, the rules are tabular, the cumulative `+` shorthand is **expanded** into explicit per-row benefits (rendering, not inference), the unknown is marked, and pricing/process are absent.
