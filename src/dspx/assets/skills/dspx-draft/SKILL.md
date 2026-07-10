---
name: dspx-draft
description: Use when the outline structure is set and writable leaf sections need prose. Renders each leaf one at a time, blind to its siblings, as constrained payload-first prose under that section's brief. Unlike edit it generates from the aperture rather than polishing existing text, and unlike develop it never touches the outline or the thinking layer.
---

## STEP 0 — do this FIRST, every time
> **If `docspec` is not found** — it IS installed (via `uv tool`); your shell's PATH just predates the install (a freshly-launched or sandboxed agent shell). Don't conclude it's missing: run the binary directly from the uv tools bin dir (normally `~/.local/bin/docspec`, Windows `%USERPROFILE%\.local\bin\docspec.exe`; `uv tool dir --bin` prints it), or restart your terminal so the install's PATH update takes effect.

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
2. Run `docspec status` and take the leaf sections flagged **`stale-own`, `stale-upstream`, or not-yet-drafted** — those are yours to (re)render. `stale-own` = the section's own `concept`/`decisions`/`material` changed (or never existed); **`stale-upstream` = a shared decision it `realizes` moved (the cross-document truth it depends on changed)** — that is a redline-equivalent re-render, owned by you, not edit. **Do NOT touch `stale-inherited` sections** — their own content is intact and only an ancestor's `brief` moved; they go to **`edit`** for narrative alignment, not a full re-render here. There is no lock; `status` drives selection. (A `redraft`-flagged section — marked via `docspec stale`/`docspec redraft` after a deep restructuring — surfaces as ordinary `stale-own`: your pickup set is unchanged, and your real rewrite clears the flag on render.)
3. For each leaf section, pull its **aperture** (see `docspec guide` for the exact projection). The stance that matters: you write from the **committed layer only** — `concept`/`brief`/`must_cover`, each **active** decision's `statement` (the redlines), the section's `material.md` (the source blood), the parent-chain briefs, **the ancestor-chain normative rulings** (your aperture surfaces them — your prose must OBEY them, never contradict or overstep a ruling you inherit, cross-tree governance included; this is supplied data you follow, the engine does not gate it semantically), the shared `writingGuide`, and the lean `glossary` index. Coherence comes from obeying the writing guide, **NOT** from reading neighbours. Honour `aliases_forbidden`, never a synonym; for a term's meaning or English original drill down on demand and then write PER the definition **in your own words** (don't clone it). The thinking layer — `develop.md`, a decision's `why`/`rejected`, `history` — is OUT of aperture: writing from it reintroduces the drift the split exists to prevent.
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
- **Diagrams = drawio image, authored by a delegated subagent (never inline)** — when the outline marks a section as a diagram, do NOT hand-write TikZ, raw `{=latex}`, or mermaid (none of these are the content model any more; mermaid never rendered and TikZ was LaTeX-only). **Delegate** to a subagent that loads the `dspx-diagram` skill: hand it the diagram's *intent* (what it must show) and the section's `assets/` dir; it produces a `.drawio` source plus a rendered **PNG** there. That PNG then becomes one of the section's `image_assets`, embedded with plain `![caption](assets/<file>)` exactly like any other image (next bullet). To CHANGE an existing diagram, **look at the rendered image** and dispatch a subagent with the visual feedback to edit the XML and re-render — you give intent and review the artifact; you never carry the diagram's internals. (Rationale: context hygiene + the standing "delegate render/diagram work to subagents, don't self-review" rule + blind-render — the diagram travels as a high-DPI raster PNG, which embeds reliably on the default Typst track. Do NOT use drawio's SVG export: the Typst renderer collapses it to a black box.) **If the subagent hands back a figure flagged "needs full-page / landscape"** (it cannot fit a single column), don't let that verdict die at the handoff — raise a non-blocking `docspec audit raise --target <section>` finding recording the layout intent, so `release` can size it later instead of re-diagnosing a squeezed page from scratch.
- **Images: place only what's in your aperture** — your aperture lists this section's available image assets (`image_assets`, refs like `assets/<file>`). Embed one with plain markdown `![caption](assets/<file>)` — **never invent an asset path** (the engine's integrity check rejects a reference to a non-existent asset, and `docspec check` blocks it). Do NOT hand-write a figure number ("Figure 3") — the render backend numbers figures; and never reference a figure in another section (you are blind to siblings).
- **Use the document map to PLACE the section, then open on the payload (structure-visible, prose-blind)** — your aperture includes the whole article's section map (each section's title/order/role, with "you are here" marked). Use it to KNOW where this section sits in the argument, then **open on the section's substantive conclusion so its role is implicit** — do NOT announce the role as metadiscourse ("This section establishes…", 「本節規範…／本節不寫…／可檢核性:…」). A native reader meets the point first; the role shows *through* the content, it is not declared. This is the same instinct as *inverted pyramid* / *lead with the payload* above — they must not fight, and the metadiscourse opener is the one that goes. You see only the map's *structure* (roles), NEVER siblings' prose — so still write NO cross-section references in the deliverable ("as the next section…"). Coherence comes from knowing your place in the argument, not from quoting neighbours. **When a ruling owned elsewhere must be invoked, name the mechanism or responsibility it governs (e.g. "the safety board's veto", "the traceability spine"), NEVER a section number or id** — that is how `develop` asks you to honour a cross-cutting decision without you naming a section; assembly resolves attribution structurally via ids, not your prose.
- **Overview section = orient by SUBSTANCE, never narrate the layout** — when rendering the document's root/overview section, orient the reader by stating the SUBJECT and the core framing idea the whole document turns on — the central tension or principle, given as a substantive claim — plus plainly what the document defines, its boundary, and its audience. Do NOT pour the mission's quantitative specifics into it (those belong in their own section). **And do NOT narrate the document's own structure** — "orient the reader to the whole" means give the topic and the key idea, NOT a prose table of contents and NOT self-reference to the document as an artifact. Banned (these are real defects pulled from output): a chapter walkthrough ("先以…再以…接著…最後…", "首先…其次…最後…"), "各章環環相扣" / "本文分為N部分", and the document narrating what it does to itself ("本規範把這項工作拆成一條主線", "本規範把…整合成一份…工作文件"). The chapter order reveals itself as the reader proceeds; it is never announced. (Same 報幕 / scaffolding ban as the per-section rule below, raised to the document level — the overview is where it leaks most, because "introduce the whole document" tempts a contents-narration.)
- **Honor the section's `kind`** (when its `brief` sets one) — render `reference` as a lookup terminal (tables/definitions, no narrative arc), `how-to` as ordered task steps, `tutorial` as a learning walkthrough, `explain` as discursive prose. The `kind` is the effective one (inherited from the nearest ancestor that set it); it shapes form only, never adds content.

---

## Bans

- No throat-clearing: "It is worth noting", "Furthermore", "Delving into", "In today's world", "It is important to".
- **No section-scaffolding metadiscourse** — never narrate this section's own `brief` into the deliverable: don't announce its scope ("This section specifies…", 「本節規範…」), exclusions ("not covered here", 「本節不寫…／本節不指定…」), verifiability (「可檢核性:…」), downstream / governance constraints (「本節約束下游…」), or a rote per-section standards tag (「設計依據:…」). The brief, coverage contract, and governed-by edges are constraints you OBEY, not content you recite — state the substance directly and cite a standard inline only where it carries the point. (Distinct from throat-clearing above: this is reciting your own backstage scaffolding, the report-style register that reads as machine-translated spec rather than native prose.)
- **No cross-section references** — you are blind to siblings, so never write "as discussed above", "the next section", "in summary", "below we will". You will hallucinate a neighbour you cannot see and create a false dependency that breaks assembly. (This is the #1 failure mode when rendering blind.)
- **No metaphors / nicknames** (the "brain", "gatekeeper", "front line") and **no first-person colloquialism** ("we", "let's") — state responsibilities plainly. (Both are in the writing guide; honour it.)
- No connective tissue you invented. **Zero-inference**: if a **fact OR rationale** isn't in the material, outline, or decisions, write `[TBD]` — never fabricate it. **But faithfully expanding relational/shorthand material IS rendering, not inference** — cumulative `+`, ranges, and inheritance in `material.md` should be expanded into explicit per-row values; that's your job, not fabrication.
- No silent overrides. If your draft would contradict a decision, do NOT write around it — emit a `[!WARNING]` block naming the decision and stop on that section. (This is a deliberate stop-and-flag marker — and a safety net: `docspec lint` treats a leftover `[!WARNING]` or a leftover `[TBD]`/placeholder as a blocking ERROR, so neither can silently ship to the reader; they must be resolved before publish.)
- Don't exceed the `brief`'s `breadth`; don't go below its `depth`; never touch a `forbidden` topic.
- **Write ONLY reader prose into the deliverable.** No version/status banners, `<a id>` anchors, `{#…}` heading IDs, or binding comments — section↔prose binding lives in the outline/index, never in the manuscript.
- **No hand-rolled punctuation-width sweep.** Write punctuation correctly for the deliverable language as you compose (that is never restricted) — but do NOT go back and run a systematic full-text pass (or a blind regex) to normalize full-width / half-width punctuation. A blind sweep is unguarded and corrupts **code spans, identifiers, protocol tokens, and URLs** — byte-exact zones a width pass must never touch. The engine now does this deterministically: run **`docspec normalize <article>`** (it converts half-width→full-width only inside prose that is CJK on both sides; code / identifiers / URLs are byte-exact). Get it right per sentence while writing; leave document-wide width consistency to `docspec normalize`, never a reflexive manual sweep here.

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
