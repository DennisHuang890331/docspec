---
name: dspx-apply
description: Use to bring a section's prose into line with its source — the single skill for all prose-to-source alignment (the former draft + edit). Two engine-routed modes. rewrite mode blind-renders a section from its aperture (for unwritten / stale-own / stale-upstream / redraft-flagged sections, i.e. a change target whose action is create/revise/redraft). align mode narrative-aligns existing prose on docs/_latest, or acknowledges it with the verdict verbs (for stale-inherited / stale-style / stale-norm / drifted sections, i.e. action align). You pick the mode from the change-target action, or from the staleness type outside a change — never an operator-read routing table.
---

## STEP 0 — do this FIRST, every time
> **If `docspec` is not found** — it IS installed (via `uv tool`); your shell's PATH just predates the install (a freshly-launched or sandboxed agent shell). Don't conclude it's missing: run the binary directly from the uv tools bin dir (normally `~/.local/bin/docspec`, Windows `%USERPROFILE%\.local\bin\docspec.exe`; `uv tool dir --bin` prints it), or restart your terminal so the install's PATH update takes effect.

Run `docspec guide` and `docspec instructions apply <section>` before acting. The mechanics —
the file model, field names, formats, read/write aperture, filing rules, the graduation/retire
transactions — live there, projected live from the schema; assume they may have changed since this
file was written. **This skill gives you only STANCE** (judgment and attitude — what to do, what
never to do). Don't restate mechanics or guess field names from memory. The engine gates
(`docspec check` / `ready` / `publish`) are your backstop: file something wrong and they refuse and
tell you exactly what's missing.

---

## Choosing the mode — the engine routes, you don't read a table
`apply` is one skill with two modes. You do NOT consult a "which staleness → which skill" table (there is none any more — that complexity used to leak out of `docspec status`; it now lives here). Open with `docspec status <article>` (or, inside a change, `docspec change status <id>`) to see each section's state, then pick your own mode:

- **Inside a change** — the target's `action` selects the mode: `create` / `revise` / `redraft` → **rewrite**; `align` / `review` → **align**. (`move` / `retire` are structural transactions, not a prose pass — they never route through apply.)
- **Outside a change** (a single-section edit, allowed without a change) — the section's **staleness type** selects the mode: `unwritten` / `stale-own` / `stale-upstream` / redraft-flagged → **rewrite**; `stale-inherited` / `stale-style` / `stale-norm` / `drifted` → **align**.

Same routing either way — it is internal to this skill. `docspec instructions apply <section>` projects the mode this section is currently in plus the render/ack verb that clears it.

---

# Rewrite mode (blind render — the former draft)

Fill the outline's writable leaf sections with prose — nothing more. You are a constrained generator, not an author. The concept/decision outline already decided WHAT each section says; your job is to render it under that section's `brief`, then hand each result to the human.

**IMPORTANT:** You write writable leaf sections only — a section whose `concept.yaml` + `decisions.yaml` are present and that passes `docspec check`. If a section isn't writable, skip it: its structure or decisions are still moving, and drafting it wastes work and invites drift.

## Loop

1. **Render first** to materialize the deliverable skeleton (slots, markers, headings — see `docspec guide`); run it whenever the outline changed. Never hand-add a section marker — render owns the skeleton.
2. Run `docspec status` and take the leaf sections flagged **`stale-own`, `stale-upstream`, or not-yet-drafted** — those are yours to (re)render. `stale-own` = the section's own `concept`/`decisions`/`material` changed (or never existed); **`stale-upstream` = a shared decision it `realizes` moved (the cross-document truth it depends on changed)** — that is a redline-equivalent re-render, owned by rewrite mode. **Do NOT touch `stale-inherited`/`stale-style`/`stale-norm` sections here** — their own content is intact; they go to **align mode** below for narrative alignment or an acknowledge, not a full re-render. There is no lock; `status` drives selection. (A `redraft`-flagged section — marked via `docspec stale`/`docspec redraft` after a deep restructuring — surfaces as ordinary `stale-own`: your pickup set is unchanged, and your real rewrite clears the flag on render.)
3. For each leaf section, pull its **aperture** (see `docspec guide` for the exact projection). The stance that matters: you write from the **committed layer only** — `concept`/`brief`/`must_cover`, each **active** decision's `statement` (the redlines), the section's `material.md` (the source blood), the parent-chain briefs, **the ancestor-chain normative rulings** (your aperture surfaces them — your prose must OBEY them, never contradict or overstep a ruling you inherit, cross-tree governance included; this is supplied data you follow, the engine does not gate it semantically), the shared `writingGuide`, and the lean `glossary` index. Coherence comes from obeying the writing guide, **NOT** from reading neighbours. Honour `aliases_forbidden`, never a synonym; for a term's meaning or English original drill down on demand and then write PER the definition **in your own words** (don't clone it). The thinking layer — `develop.md`, a decision's `why`/`rejected`, `history` — is OUT of aperture: writing from it reintroduces the drift the split exists to prevent.
4. Generate prose constrained by that aperture + writing guide. One leaf section, one pass: `material.md` supplies the flesh, `concept` sets the envelope, the decision `statement`s are the redlines.
5. Write **only body prose** into that section's slot — never the heading (render generates it from `concept.title`; a wrong title is fixed in `concept.yaml`, in develop, not here), never the markers, never another section's prose.
6. Render again to stamp the section's source hash, then surface the output to the human before the next section.

You are looping over the engine, not reasoning about the whole document. You render each leaf **blind to its siblings** — that isolation is the anti-hallucination point. Coherence across sections is carried by the shared writing guide, not by you peeking at neighbours.

**Small changes = re-render the affected leaf section.** You do NOT do surgical patches into existing prose. Sections are cut fine enough that re-rendering a whole leaf section from its aperture is the correct, cheap unit of change.

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

## Bans

- No throat-clearing: "It is worth noting", "Furthermore", "Delving into", "In today's world", "It is important to".
- **No section-scaffolding metadiscourse** — never narrate this section's own `brief` into the deliverable: don't announce its scope ("This section specifies…", 「本節規範…」), exclusions ("not covered here", 「本節不寫…／本節不指定…」), verifiability (「可檢核性:…」), downstream / governance constraints (「本節約束下游…」), or a rote per-section standards tag (「設計依據:…」). The brief, coverage contract, and governed-by edges are constraints you OBEY, not content you recite — state the substance directly and cite a standard inline only where it carries the point. (Distinct from throat-clearing above: this is reciting your own backstage scaffolding, the report-style register that reads as machine-translated spec rather than native prose.)
- **No cross-section references** — you are blind to siblings, so never write "as discussed above", "the next section", "in summary", "below we will". You will hallucinate a neighbour you cannot see and create a false dependency that breaks assembly. (This is the #1 failure mode when rendering blind.)
- **No metaphors / nicknames** (the "brain", "gatekeeper", "front line") and **no first-person colloquialism** ("we", "let's") — state responsibilities plainly. (Both are in the writing guide; honour it.)
- No connective tissue you invented. **Zero-inference**: if a **fact OR rationale** isn't in the material, outline, or decisions, write `[TBD]` — never fabricate it. **But faithfully expanding relational/shorthand material IS rendering, not inference** — cumulative `+`, ranges, and inheritance in `material.md` should be expanded into explicit per-row values; that's your job, not fabrication.
- No silent overrides. If your draft would contradict a decision, do NOT write around it — emit a `[!WARNING]` block naming the decision and stop on that section. (This is a deliberate stop-and-flag marker — and a safety net: `docspec lint` treats a leftover `[!WARNING]` or a leftover `[TBD]`/placeholder as a blocking ERROR, so neither can silently ship to the reader; they must be resolved before publish.)
- Don't exceed the `brief`'s `breadth`; don't go below its `depth`; never touch a `forbidden` topic.
- **Write ONLY reader prose into the deliverable.** No version/status banners, `<a id>` anchors, `{#…}` heading IDs, or ownership-binding comments — the section↔prose OWNERSHIP binding lives in the outline/index, never in the manuscript. **The ONE sanctioned inline binding is a cross-reference anchor:** to point the reader at another section ("see §6.5", "per §9.2"), never hand-type the chapter number (it drifts on any reorder — the real corpus lost 94–107 cross-refs to exactly this). Instead write `<!--@<target-concept-id>--><!--@-->` inline where the number should go; `render` injects the current `§number` between the two invisible comments from the target's outline position and re-derives it every render, so it never dangles. Bind to the target section's `concept.id` (or a decision id); `docspec check` verifies the target is live. **External-standard clause citations stay literal** (`ISO 13849-1 §4.2`) — the anchor is only for internal references. (See `docspec guide` → filing rule `crossref-by-anchor`.)
- **No hand-rolled punctuation-width sweep.** Write punctuation correctly for the deliverable language as you compose (that is never restricted) — but do NOT go back and run a systematic full-text pass (or a blind regex) to normalize full-width / half-width punctuation. A blind sweep is unguarded and corrupts **code spans, identifiers, protocol tokens, and URLs** — byte-exact zones a width pass must never touch. The engine now does this deterministically: run **`docspec normalize <article>`** (it converts half-width→full-width only inside prose that is CJK on both sides; code / identifiers / URLs are byte-exact). Get it right per sentence while writing; leave document-wide width consistency to `docspec normalize`, never a reflexive manual sweep here.

## Rewrite guardrails

**Do**
- Honor the section `brief` as a hard contract.
- Insert `[TBD]` for any missing fact or rationale and keep going.
- Render rules and multi-dimensional data as tables.
- Review each section's output with the human before the next.

**Don't**
- Don't rewrite sections that aren't writable (missing concept/decisions, or `check` not green).
- Don't do surgical patches — re-render the affected leaf section instead.
- Don't invent facts, rationale, examples, or transitions (but DO expand shorthand material — that's rendering).
- Don't write prose where structure is required.
- Don't silently resolve a draft-vs-decision conflict.
- Don't read `develop.md`, a decision's `why`/`rejected`, or `history.yaml` — they are outside your aperture; writing from the thinking layer reintroduces the drift the split exists to prevent.

## Example (rewrite mode)

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

---

# Align mode (copy-prep + staleness alignment — the former edit)

Enter align mode. You run the editorial desk on an already-rendered document, in order — line
edit, then copy edit, then proofread. Your core skill is **routing, not eyeballing**:
for every check, ask "can `docspec lint` / `docspec check` give a single right answer?" If
yes, run the engine and act on its findings. If it needs taste, context, or a whole-
document read, dispatch a clean-context subagent. You **write** ONLY the deliverable
working copy — you may READ a section's `concept`/`brief` (and parent chain) to align
tone, but you never change the outline, decisions, or develop.md. **Never touch any
`archive/` folder** — published snapshots are immutable history (see `docspec guide`).

**Two triggers bring you into align mode:**
1. **Copy-prep after a rewrite** — a freshly rendered document needs line→copy→proof. This is the main procedure below.
2. **Narrative / ruling / style alignment** — when `docspec status` flags a section `stale-inherited`, `stale-norm`, or `stale-style` (its own content is unchanged, but an ancestor's `brief`, an ancestor ruling, or the document-wide writing doctrine moved), rewrite mode does NOT re-render it — **you** re-tune or acknowledge its existing prose. See the dedicated sections below.

**IMPORTANT: improve → mechanize → only catch.** The three stages run in this order
and never backwards. Once you reach proofread you STOP rewriting; proofread only
catches, and real fixes loop back to line/copy.

**IMPORTANT: engine first — but route to what the engine ACTUALLY enforces.**
Leaked codes/anchors/scaffolding, placeholder leftovers (`[TBD]`/`[TBD: …]`/`[TODO]`/
`[待補]`), leftover `> [!WARNING]` alerts, and structural integrity are the engine's job
(`docspec lint`/`check`, blocking ERROR) — do not eyeball them. A dead internal anchor
link is an **export-safety WARN** (it does NOT block publish, but it breaks the PDF at
export time) — so fix it, but know it is a WARN, not a blocking ERROR.
Cross-document **number** consistency and **term** identity are engine **WARN** advisories
(the engine flags, it does not fix — review each and reconcile by hand). Banned openers and
**cross-section references** (`as above` / `如前一節所述`) are writing-guide doctrine the
engine does **NOT** validate — they are your manual proofread duty, not a lint catch.
Readability, register, contextual word-choice, and the final whole-document read are the
only things worth a subagent.

**This is a procedure, not a loose stance.** Unlike rewrite mode, align mode has an ordered
sequence — because copy-prep that runs out of order wastes itself (you don't proofread
prose you're about to rewrite).

**Cost tip (advisory):** on a freshly rewritten section, a cheap `factcheck`
claim-pass FIRST routes content defects upstream while the prose is still cheap to re-render
— spending the expensive line/copy polish here only after that avoids re-polishing prose a
later factcheck would invalidate. This is advice, not a gate (the loop is any-order).

## Your yardstick: the writing-guide
Read the shared **`writing-guide.md`** before you start — the engine injects it
(`docspec instructions apply <section> --json` exposes it as `writingGuide`). It is the
whole-document **style contract**, and you are the first and only actor who sees the
whole document at once, so verifying every section conforms to it **consistently** is
your job — the blind renderer could not. Route its rules exactly like
everything else (don't treat the guide as a separate kind of work):
- **Mechanical rules** → route by what the engine truly enforces. `docspec lint` catches
  clean output (leaked machinery, placeholders, leftover `[!WARNING]` alerts) as blocking
  ERROR, and flags term-identity / number drift as WARN. It does **NOT** check banned
  openers or "no cross-section references" (`as above` / `如前一節所述`) — the engine does
  not validate writing-guide doctrine, so those are yours: grep and fix them in place.
  Deliverable-language keywords and canonical terms: lint/glossary flag, you normalize.
- **Judgment rules** → fold into your **line-edit subagent's** brief: tone, register,
  density, rhythm. Never mechanize taste; never hand a regex's job to a subagent.

If a *new* document-wide convention surfaces while you read the whole thing, **flag it**
(a `docspec audit` finding or your diff summary) for `develop` to lift into the guide — you do
**not** write the writing-guide yourself (you write only the deliverable). Machine-checkable
term identity belongs in `glossary.yaml`, not the guide.

## Narrative alignment (the `stale-inherited` job)
When `docspec status` reports a section as **`stale-inherited`**, its own `concept`/`decisions`/
`material` are unchanged — only an **ancestor's `brief`** (audience/depth/breadth/forbidden/
tone) shifted. Re-rendering from scratch would throw away good prose and risk re-hallucinating,
so you do a **light alignment pass**, not a rewrite:

1. `docspec instructions apply <section> --json` — gives you the section's existing prose plus the
   updated `concept`/parent-chain `brief` and the shared `writingGuide`.
2. Re-tune ONLY the prose's tone, framing, and emphasis to fit the new parent brief —
   **the content (facts, decisions, numbers, claims) stays byte-for-byte**. If the new brief
   genuinely demands different content, that's a rewrite-mode/`develop` matter — flag it, don't invent.
3. Re-stamp the section so `stale-inherited` clears — by the path that matches what you did:
   - **If your alignment changed the prose** → `docspec render <article>` re-stamps it (the prose hash
     moved, so the engine recomputes the ancestor fingerprint).
   - **If, after reviewing against the moved brief, the prose legitimately needs NO change** (e.g. a
     bibliography / reference list that carries no framework narrative) → do NOT fabricate an edit to
     force a re-stamp. Acknowledge it: `docspec render <article> --ack <section>`. That re-stamps the
     ancestor fingerprint as your explicit "reviewed, aligned, no change needed". (`--ack` is refused
     if the section is actually `stale-own`/`stale-upstream` — that means its own source changed and
     the prose genuinely needs rewriting, which is rewrite mode's job, not an acknowledge.)
   Then `docspec lint`/`docspec check` as usual.

### Source-change verdicts (`stale-own`/`stale-upstream` whose prose needs no change)
`--ack` cannot clear the opposite direction. When a section is `stale-own`/`stale-upstream` and your
review concludes the prose **legitimately needs no change**, route by WHAT changed in the source:

- **Structural wiring / metadata only** — a `realizes`/`governed-by` edge re-wired, an `order`
  change, a `sources:` path move, a `decided-in` correction, a title renumbering →
  `docspec render <article> --ack-own <section> --reason <text>`. That re-stamps `own`/`deps` to
  current while `anc`/`style` are kept, so a masked `stale-inherited`/`stale-style` may surface —
  that is the point: clear it on its own merits, don't absorb it. This whitelist is exhaustive:
  if the change isn't on it, it isn't an ack-own case.
- **Content-bearing change** — `must_cover`, `breadth`, or a decision `statement` moved → the
  prose DOES need rewriting: route to **rewrite mode** (mark explicitly with
  `docspec stale <section> --reason <text>` / `docspec redraft <article> --reason <text>`).
  NEVER ack-own a content change.

Every verdict is recorded in the article's append-only verdicts journal — give a **real**
`--reason`, not boilerplate. An ack-own attests the prose still implements **changed** source
material — a stronger claim than `--ack` — so a factcheck follow-up over the acked sections is
expected (non-blocking, never a gate). And NEVER fabricate an edit or run the
perturb-render-revert dance (change a character, render, revert, render): its end state is
byte-identical to an honest `--ack-own`, but it leaves zero trace and launders the verdict.

## Ruling re-check (the `stale-norm` job)
When `docspec status` reports a section as **`stale-norm`**, its own `concept`/`decisions`/
`material` are unchanged — an **ancestor's active `normative` ruling** changed (added, rewritten,
or retired from the active set), on the path-parent chain or a cross-tree `governed-by` parent.
The aperture projects those rulings to rewrite mode as "obey when writing", so the prose on record may
now violate (or still render) a rule that moved. This is more serious than `stale-inherited`
(a rule, not a narrative frame) but still below `stale-own`/`stale-upstream` — the common outcome
is "the prose is still legal, acknowledge it":

1. `docspec instructions apply <section> --json` — existing prose plus the parent chain; read the
   changed ancestor's `decisions.yaml` normative entries.
2. **Re-check the prose sentence by sentence against the new/changed/retired ruling.** Content
   stays byte-for-byte unless a sentence actually violates the ruling; if the fix needs new facts
   or a re-derivation, that's rewrite mode's job — escalate with `docspec stale <section> --reason`
   (or `docspec redraft <article> --reason`), don't invent.
3. Re-stamp by the path that matches what you did, exactly as for `stale-inherited`:
   - **prose changed** → `docspec render <article>` re-stamps it.
   - **prose already conforms to the changed ruling** (no change needed) →
     `docspec render <article> --ack <section>` (re-stamps `norm` together with `anc`/`style`;
     refused if the section is actually `stale-own`/`stale-upstream`).

## Restyle (the `stale-style` job)
When `docspec status` reports a section as **`stale-style`**, nothing in its `concept`/`decisions`/
`material`/ancestors moved — the **writing doctrine itself** did: the shared `writing-guide.md`
(tone/structure/register conventions), `glossary.yaml` (canonical terms — only the projected index
fields: canonical/bucket/code/aliases_forbidden; a definition-only edit never restales), or
`config.purpose` (the project north star) was rewritten since this
section's prose was last rendered — `docspec status` names which carrier moved. Because the doctrine is document-wide, a doctrine change re-stales
**every** written section at once — that list **is** your worklist (the engine cannot supply it any
other way; the doctrine is not in any section's source hash, so this `stale-style` flag is the only
signal you get that the deliverable still carries the old style). Same discipline as `stale-inherited`:
this is a **restyle pass, not a rewrite**.

1. `docspec instructions apply <section> --json` — gives the existing prose plus the updated
   `writingGuide` and glossary index.
2. Re-tune ONLY register/structure/terminology to the new doctrine — **facts, decisions, numbers,
   claims stay byte-for-byte**. (A doctrine change is never a content change; if you find yourself
   wanting to change a claim, that's rewrite mode/`develop`, flag it.)
3. Re-stamp by the path that matches what you did, exactly as for `stale-inherited`:
   - **prose changed** → `docspec render <article>` re-stamps the `style` fingerprint.
   - **prose already conforms to the new doctrine** (no change needed) → `docspec render <article>
     --ack <section>` (refused if the section is actually `stale-own`/`stale-upstream`).

**Batch-clear the doctrine sweep in one command.** A doctrine change re-stales EVERY written
section at once, and after review most legitimately need no change — don't fire one `render --ack`
per section. Pull the worklist deterministically (`docspec status <article> --json`, filter the
`stale-style` sections), review each against the moved doctrine, then clear the ones that need no
change in a SINGLE call: `docspec render <article> --ack <sec-a> --ack <sec-b> …` (each `--ack`
takes one section; stack them). Any section whose prose you actually re-tuned is re-stamped by a
plain `docspec render <article>` instead — so the batch `--ack` carries only the reviewed-no-change
sections. This is the same mechanical-discipline principle as `normalize`/`tidy`: one deterministic
pass, not a hand loop.

These three (`stale-inherited` / `stale-norm` / `stale-style`) are the only times align mode consults
the brief / rulings / doctrine. Everything below is plain copy-prep.

## The Routing Rule (the heart of copy-prep)
For each check you are about to make:
- **Deterministic** (one right answer from files + ids) → **run the engine** (`docspec lint`
  for cleanliness/leaks/format/term drift, `docspec check` for references + structure; exact
  coverage in `docspec guide`). Act on each finding mechanically; don't argue with it.
- **Semantic** (needs taste / context / a holistic read) → **dispatch a clean-context
  subagent** with just the prose and a tight instruction.
- **Deterministic but the engine doesn't cover it** (e.g. `a`/`an`, subject–verb agreement, a
  malformed modal like "must to") → **fix it in place yourself.** One right answer; spawning a
  subagent for a single article is wasted overhead. For short/trivial passages apply the obvious
  fix inline — the clean-context dispatch is for whole-section judgment, not one sentence.

**Where "flag, don't invent" goes:** when a fix would change meaning (a content/decision gap, a
cross-section contradiction), raise a non-blocking `docspec audit` finding OR list it in your diff
summary — **never** leave a `[!WARNING]`/`[TBD]` in `_latest.md`.

Never let the engine "judge" prose, and never hand a subagent work a regex (or you) already
settles. That mis-routing is the only way copy-prep fails.

## Subagent dispatch briefs — the exclusion list (copy it, don't re-derive it)
When you dispatch a clean-context subagent for judgment work (line edit, a whole-document read),
the failure is not the routing principle above — it is that **at brief-writing time you re-derive
which work is mechanical from memory and, in a hurry, let a deterministic sweep slip into a
semantic brief** (the 台中港 case: "normalize all punctuation to full-width" landed in a semantic
subagent's brief). Fix: don't re-derive it. **Every dispatch brief opens with one line — "You do
SEMANTIC work only"** — and then you copy this exclusion list verbatim. Each item names the
mechanical work kept OUT of the brief and exactly where it goes instead:

- **Punctuation width (full-width / half-width)** → **NOT dispatched.** It is deterministic
  engine work, not semantic: run **`docspec normalize <article>`** (converts half-width→full-width
  only where prose is CJK on both sides; code spans / identifiers / protocol tokens / URLs stay
  byte-exact). No subagent, no blind regex, no per-sentence hand-fixing, no audit finding — lint
  **V18** flags any residual and points right back at `docspec normalize`.
- **Leaked scaffolding / placeholder leftovers** (`{#…}` ids, `[TBD]`/`[待補]`, stray `[!WARNING]`)
  → `docspec lint` (blocking ERROR). Act on its findings; don't send a subagent hunting them.
- **Term identity / number drift** → `docspec lint` (advisory WARN). The engine flags, it does not
  fix — **you** reconcile each by hand against the source; not a subagent's call.
- **Anchors / reference structure** → `docspec check`. Deterministic resolution, engine-owned.
- **Banned openers / cross-section references** (`as above`, `如前一節所述`) → the engine does
  **NOT** validate these; **you** grep for them by hand. Still **NOT dispatched** — a one-line grep
  is your own job, and spawning a subagent for it is both waste and a mis-signal that it needs taste.

Keep the list honest about engine reality: only items the engine truly enforces say "→ the engine";
items it does not validate say "→ you, by hand". A brief that hands any of these to a subagent is
mis-routed before it is even read.

## Stage 1 — Line edit (readability) · SEMANTIC → subagent
The engine cannot hear cadence. Dispatch a subagent to make each section READABLE for
its audience — tighten rhythm, cut throat-clearing, surface buried subjects, kill word
salad — **changing how it reads, never what it says**. No number, term, or normative
claim moves; no new claim, example, or caveat is added. If a fix needs new structure,
that is a `develop` finding — flag it and leave it.

## Stage 2 — Copy edit (correctness & consistency) · ENGINE first, agent for the residue
1. Run `docspec lint`. Fix each finding in place:
   - leaked code/anchor/scaffolding → rewrite to display-text + hidden target, or cut
   - dead link / cross-reference → repair or remove
   - glossary exact-match miss / format drift → normalize to the one canonical term/format.
   - **number** drift (an advisory lint WARN): the engine flags a value conflict but you cannot tell
     which is correct — do NOT pick one (numbers stay byte-for-byte). Raise an audit / diff-
     summary finding to reconcile against the source.
     The projected glossary is a **lean index** (`canonical` + `bucket` + `aliases_forbidden`);
     for a term's meaning or English original, `docspec show <term-id>` returns the full record
     (incl `definition`) — prose should be written PER the definition in its own words (not cloned);
     faithfulness is a non-blocking factcheck concern, not an edit rewrite.
2. **Deterministic grammar lint doesn't catch** (articles `a`/`an`, subject–verb agreement,
   malformed modals) → fix in place yourself. THEN dispatch a subagent only for what needs
   judgment: the right term in THIS context, parallelism, register. Mechanical means mechanical —
   if a fix would change meaning, raise an audit finding / note it, don't guess.
This is a living document: overwrite stale state in place, never append a correction note.

## Stage 3 — Proofread (final gate) · ENGINE gate + one catch-only read
1. Re-run the engine as the deterministic final gate:
   - `docspec lint` — deliverable cleanliness ERRORs must be **zero**: no leaked machinery,
     no `[TBD]`/placeholder, no leftover `[!WARNING]`. (Number drift is an advisory WARN — review
     and reconcile it; it does not block, but don't ship an unreviewed value conflict.)
   - `docspec check` — every reference resolves, structure whole.
2. Dispatch a subagent for ONE clean-context, end-to-end read — **catch-only**: flow
   seams, a contradiction across sections, anything confusing on first read. It LISTS
   problems; it does not fix them. Anything needing a rewrite loops back to Stage 1/2.

## On a structural / deep revision, re-check the title and root framing
When a section was re-pivoted across its outline or its thesis re-framed, `concept.title` (and the
document's root/overview framing) is the surface most often left stale — and the staleness ledger
CANNOT catch it: a title left *byte-unchanged* while the prose was re-pivoted produces no
`own`-fingerprint change, so `status` stays green even as the title contradicts the new argument.
This is a semantic check that is yours, not the engine's. Confirm the title and root framing still
match the rewritten prose; if the title is stale, that is a `develop` fix (`concept.title`) — flag
it, don't rewrite the heading in `_latest.md` (render owns it).

## Example (align mode)
Human: "align handbook/_latest.md"

> **apply (align) — handbook/_latest.md**
> **Stage 1 line edit** (subagent): tightened §2–§4, cut 6 throat-clearing openers; no claim moved.
> **Stage 2 copy edit** — engine first:
>   `docspec lint` → 3 findings: leaked `{#eligibility}` id in §2 (→ plain heading); dead "see §6" in §4 (→ §5 Renewal); "sign-up / signup" drift (→ normalized **sign-up**).
>   in place: "a applicant" → "an applicant" (deterministic article; no subagent needed).
>   subagent residue: none.
> **Stage 3 proofread** — engine gate:
>   `docspec lint` → clean (0).  `docspec check` → all refs resolve.
>   subagent read → 1 finding: §3→§4 seam abrupt. **Catch-only — routed back to line edit, not fixed here.**
> Result: clean except the §3→§4 seam; re-run after that one bridge.

Order held, the engine caught every mechanical defect, deterministic grammar was fixed in place, the subagent spent its judgment only on cadence and the final read — and nothing was rewritten at the gate.

---

## docspec awareness (both modes)
`docspec status` tells you which leaves are **rendered** (have prose) and which are **stale**, and
in which way (`stale-own`/`upstream` → rewrite; `stale-inherited`/`style`/`norm`/`drifted` → align);
it does NOT track a polish-progress state (there is no "rendered-but-not-aligned" field) — which
sections you have already polished in align mode is yours to track. `docspec lint` and `docspec
check` are your deterministic checks (exact coverage in `docspec guide`); route to them first — that
routing is the whole point of align mode. In rewrite mode you write from the committed layer, blind
to siblings; in align mode you read and write ONLY the deliverable working copy. A human reviews
your work; show the diff / surface the output, don't silently rewrite.

## Guardrails (both modes)
**Do**
- Pick the mode from the change-target action (inside a change) or the staleness type (outside one); don't ask the operator to route.
- rewrite: honor the `brief` as a hard contract; lead with the payload; insert `[TBD]` and keep going.
- align: run the three stages in order, engine-first inside each; keep proofread catch-only and loop rewrites back to line/copy.
- Clear a staleness verdict with the MATCHING verb (plain `render` when prose changed; `render --ack` / `render --ack-own --reason` when it legitimately did not) — never fabricate an edit or run a perturb-render-revert dance to force a re-stamp.

**Don't**
- Don't invent facts, rationale, examples, or transitions (rewrite); don't change meaning — numbers, terms, normative claims stay byte-for-byte (align).
- Don't eyeball deterministic checks — that's `lint`/`check`.
- Don't do surgical patches in rewrite mode — re-render the affected leaf section instead.
- Don't touch the outline, decisions, or develop.md in align mode — deliverable only; don't rewrite during proofread, or pass to publish with open findings.
- Don't read `develop.md`, a decision's `why`/`rejected`, or `history.yaml` in rewrite mode (the thinking layer is out of aperture); don't leak corpus-only content — never paste a `rejected` option, a retired decision's `rationale`, or `history.*` prose (incl. a factcheck `--suggest` that quotes them) verbatim into `_latest.md`.
- **Don't hand-roll a punctuation-width sweep** (full-width / half-width) — no blind regex over the
  whole document, no per-occurrence hand-fixing. A bulk hand sweep is unguarded and corrupts
  **code spans, identifiers, protocol tokens, and URLs** (byte-exact zones a width pass must never
  touch). Writing punctuation correctly as you compose is fine; for document-wide width consistency
  run the engine's deterministic pass — **`docspec normalize <article>`** (half-width→full-width
  only where prose is CJK on both sides; byte-exact zones untouched). lint **V18** flags any
  residual and points at `docspec normalize`; it is never an audit finding to rule on.
