---
name: dspx-edit
description: Use after draft and before publish, when a drafted document needs the single
  copy-preparation pass to reach publish-ready. Runs the editorial desk in publishing-house
  order (line edit → copy edit → proofread), routing each check to the engine when deterministic
  and to a clean-context subagent only when it needs judgment. Unlike draft it polishes existing
  prose rather than generating it, and unlike factcheck it changes how text reads, never what it claims.
---
## STEP 0 — do this FIRST, every time
> **If `docspec` is not found** — it IS installed (via `uv tool`); your shell's PATH just predates the install (a freshly-launched or sandboxed agent shell). Don't conclude it's missing: run the binary directly from the uv tools bin dir (normally `~/.local/bin/docspec`, Windows `%USERPROFILE%\.local\bin\docspec.exe`; `uv tool dir --bin` prints it), or restart your terminal so the install's PATH update takes effect.

Run `docspec guide` and `docspec instructions edit <section>` before acting. The mechanics —
the file model, field names, formats, read/write aperture, filing rules, the graduation/retire
transactions — live there, projected live from the schema; assume they may have changed since this
file was written. **This skill gives you only STANCE** (judgment and attitude — what to do, what
never to do). Don't restate mechanics or guess field names from memory. The engine gates
(`docspec check` / `ready` / `publish`) are your backstop: file something wrong and they refuse and
tell you exactly what's missing.

---

Enter edit mode. You run the editorial desk on a drafted document, in order — line
edit, then copy edit, then proofread. Your core skill is **routing, not eyeballing**:
for every check, ask "can `docspec lint` / `docspec check` give a single right answer?" If
yes, run the engine and act on its findings. If it needs taste, context, or a whole-
document read, dispatch a clean-context subagent. You **write** ONLY the deliverable
working copy — you may READ a section's `concept`/`brief` (and parent chain) to align
tone, but you never change the outline, decisions, or develop.md. **Never touch any
`archive/` folder** — published snapshots are immutable history (see `docspec guide`).

**Two triggers bring you in:**
1. **Copy-prep after draft** — a freshly drafted document needs line→copy→proof. This is the main job below.
2. **Narrative alignment for `stale-inherited` sections** — see the dedicated section. When `docspec status` flags a section `stale-inherited` (its own content is unchanged, but an ancestor's `brief` moved), `draft` does NOT re-render it — **you** re-tune its existing prose to the new parent brief.

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

**This is a procedure, not a stance.** Unlike develop/factcheck, edit has an ordered
sequence — because copy-prep that runs out of order wastes itself (you don't proofread
prose you're about to rewrite).

**Cost tip (cross-skill order, advisory):** on a freshly drafted section, a cheap `factcheck`
claim-pass FIRST routes content defects upstream while the prose is still cheap to re-render
— spending the expensive line/copy polish here only after that avoids re-polishing prose a
later factcheck would invalidate. This is advice, not a gate (the loop is any-order).

---
## Your yardstick: the writing-guide
Read the shared **`writing-guide.md`** before you start — the engine injects it
(`docspec instructions edit <section> --json` exposes it as `writingGuide`). It is the
whole-document **style contract**, and you are the first and only actor who sees the
whole document at once, so verifying every section conforms to it **consistently** is
your job — the blind per-section drafter could not. Route its rules exactly like
everything else (don't treat the guide as a separate kind of work):
- **Mechanical rules** → route by what the engine truly enforces. `docspec lint` catches
  clean output (leaked machinery, placeholders, leftover `[!WARNING]` alerts) as blocking
  ERROR, and flags term-identity / number drift as WARN. It does **NOT** check banned
  openers or "no cross-section references" (`as above` / `如前一節所述`) — the engine does
  not validate writing-guide doctrine, so those are yours: grep and fix them in place.
  Deliverable-language keywords and canonical terms: lint/glossary flag, you normalize.
- **Judgment rules** → fold into your **line-edit subagent's** brief: tone, register,
  density, rhythm. Never mechanize taste; never hand a regex's job to a subagent.

The guide's backbone is canonical English; its **Project conventions** are in the
deliverable language. If a *new* document-wide convention surfaces while you read the
whole thing, **flag it** (a `docspec audit` finding or your diff summary) for `develop`
to lift into the guide — you do **not** write the writing-guide yourself (you write only
the deliverable). Machine-checkable term identity belongs in `glossary.yaml`, not the guide.

---
## Narrative alignment (the `stale-inherited` job)
When `docspec status` reports a section as **`stale-inherited`**, its own `concept`/`decisions`/
`material` are unchanged — only an **ancestor's `brief`** (audience/depth/breadth/forbidden/
tone) shifted. Re-rendering from scratch would throw away good prose and risk re-hallucinating,
so you do a **light alignment pass**, not a rewrite:

1. `docspec instructions edit <section> --json` — gives you the section's existing prose plus the
   updated `concept`/parent-chain `brief` and the shared `writingGuide`.
2. Re-tune ONLY the prose's tone, framing, and emphasis to fit the new parent brief —
   **the content (facts, decisions, numbers, claims) stays byte-for-byte**. If the new brief
   genuinely demands different content, that's a `draft`/`develop` matter — flag it, don't invent.
3. Re-stamp the section so `stale-inherited` clears — by the path that matches what you did:
   - **If your alignment changed the prose** → `docspec render <article>` re-stamps it (the prose hash
     moved, so the engine recomputes the ancestor fingerprint).
   - **If, after reviewing against the moved brief, the prose legitimately needs NO change** (e.g. a
     bibliography / reference list that carries no framework narrative) → do NOT fabricate an edit to
     force a re-stamp. Acknowledge it: `docspec render <article> --ack <section>`. That re-stamps the
     ancestor fingerprint as your explicit "reviewed, aligned, no change needed". (`--ack` is refused
     if the section is actually `stale-own`/`stale-upstream` — that means its own source changed and
     the prose genuinely needs rewriting, which is `draft`'s job, not an acknowledge.)
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
  prose DOES need rewriting: leave the stale signal for `draft` (or mark explicitly with
  `docspec stale <section> --reason <text>` / `docspec redraft <article> --reason <text>`).
  NEVER ack-own a content change.

Every verdict is recorded in the article's append-only verdicts journal — give a **real**
`--reason`, not boilerplate. An ack-own attests the prose still implements **changed** source
material — a stronger claim than `--ack` — so a factcheck follow-up over the acked sections is
expected (non-blocking, never a gate). And NEVER fabricate an edit or run the
perturb-render-revert dance (change a character, render, revert, render): its end state is
byte-identical to an honest `--ack-own`, but it leaves zero trace and launders the verdict.

---
## Ruling re-check (the `stale-norm` job)
When `docspec status` reports a section as **`stale-norm`**, its own `concept`/`decisions`/
`material` are unchanged — an **ancestor's active `normative` ruling** changed (added, rewritten,
or retired from the active set), on the path-parent chain or a cross-tree `governed-by` parent.
The aperture projects those rulings to `draft` as "obey when writing", so the prose on record may
now violate (or still render) a rule that moved. This is more serious than `stale-inherited`
(a rule, not a narrative frame) but still below `stale-own`/`stale-upstream` — the common outcome
is "the prose is still legal, acknowledge it":

1. `docspec instructions edit <section> --json` — existing prose plus the parent chain; read the
   changed ancestor's `decisions.yaml` normative entries.
2. **Re-check the prose sentence by sentence against the new/changed/retired ruling.** Content
   stays byte-for-byte unless a sentence actually violates the ruling; if the fix needs new facts
   or a re-derivation, that's `draft`'s job — escalate with `docspec stale <section> --reason`
   (or `docspec redraft <article> --reason`), don't invent.
3. Re-stamp by the path that matches what you did, exactly as for `stale-inherited`:
   - **prose changed** → `docspec render <article>` re-stamps it.
   - **prose already conforms to the changed ruling** (no change needed) →
     `docspec render <article> --ack <section>` (re-stamps `norm` together with `anc`/`style`;
     refused if the section is actually `stale-own`/`stale-upstream`).

---
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

1. `docspec instructions edit <section> --json` — gives the existing prose plus the updated
   `writingGuide` and glossary index.
2. Re-tune ONLY register/structure/terminology to the new doctrine — **facts, decisions, numbers,
   claims stay byte-for-byte**. (A doctrine change is never a content change; if you find yourself
   wanting to change a claim, that's `draft`/`develop`, flag it.)
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

This is the only time `edit` consults the brief. Everything else below is plain copy-prep.

---
## The Routing Rule (the heart of this skill)
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

**On a structural/deep revision, re-examine the title and root framing.** When a section was
re-pivoted across its outline or its thesis re-framed, `concept.title` (and the document's
root/overview framing) is the surface most often left stale — and the staleness ledger CANNOT catch
it: a title left *byte-unchanged* while the prose was re-pivoted produces no `own`-fingerprint change,
so `status` stays green even as the title contradicts the new argument. This is a semantic check that
is yours, not the engine's. Confirm the title and root framing still match the rewritten prose; if the
title is stale, that is a `develop` fix (`concept.title`) — flag it, don't rewrite the heading in
`_latest.md` (render owns it).

Never let the engine "judge" prose, and never hand a subagent work a regex (or you) already
settles. That mis-routing is the only way this skill fails.

---
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

---
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

---
## docspec Awareness
`docspec status` tells you which leaves are **drafted** (have rendered prose) and which are
**stale**; it does NOT track an edit/factcheck-progress state (there is no "drafted-but-not-edited"
field) — which sections you have already polished is yours to track. `docspec lint`
and `docspec check` are your deterministic checks (exact coverage in `docspec guide`).
Route to them first — that routing is the whole point. You read and write ONLY the
deliverable working copy. The brief, decisions, and develop.md are off-limits — you
change how the deliverable reads, not what the outline decided. A human reviews your
edits; show the diff, don't silently rewrite.

---
## What You Don't Have To Do
Run fixed sub-passes within a stage · touch every sentence · eyeball what `lint` catches
· fix anything during proofread · read the outline, decisions, or develop.md · finish a
whole doc in one sitting.

---
## Guardrails
**Do**
- Run the stages in order; engine-first inside each.
- Act on every `lint`/`check` finding before spending a subagent.
- Keep proofread catch-only; loop rewrites back to line/copy.
- Treat any leaked machinery or leftover `[TBD]` as blocking.

**Don't**
- Don't change meaning — numbers, terms, normative claims stay byte-for-byte.
- Don't eyeball deterministic checks — that's `lint`/`check`.
- Don't touch the outline, decisions, or develop.md — deliverable only.
- Don't rewrite during proofread, or pass to publish with open findings.
- **Don't hand-roll a punctuation-width sweep** (full-width / half-width) — no blind regex over the
  whole document, no per-occurrence hand-fixing. A bulk hand sweep is unguarded and corrupts
  **code spans, identifiers, protocol tokens, and URLs** (byte-exact zones a width pass must never
  touch). Writing punctuation correctly as you compose is fine; for document-wide width consistency
  run the engine's deterministic pass — **`docspec normalize <article>`** (half-width→full-width
  only where prose is CJK on both sides; byte-exact zones untouched). lint **V18** flags any
  residual and points at `docspec normalize`; it is never an audit finding to rule on.
- **Don't leak corpus-only content into the deliverable** — never paste a `rejected` option, a
  retired decision's `rationale`, or `history.*` prose (incl. a factcheck `--suggest` that quotes
  them) verbatim into `_latest.md`. Rejected/why-dropped reasoning is for the corpus, not the reader;
  state only what the active decision `statement` supports.

---
## Example
Human: "edit handbook/_latest.md"

> **edit — handbook/_latest.md**
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
