---
name: dspx-factcheck
description: >-
  Independent adversarial reviewer — check every claim against a primary source and attack the outline
  for MECE gaps, overlaps, and cross-section contradictions. It only FLAGS (raises located findings via
  docspec audit), never fixes, and is non-blocking, unlike the engine gates. It runs as a clean-context
  subagent with fresh eyes and no loyalty to the author: distrust the confident, uncited sentence most.
license: PolyForm-Noncommercial-1.0.0
compatibility: Requires the docspec CLI (installed via uv tool; not on PATH in a fresh shell — run it from the dir printed by `uv tool dir --bin`, never reinstall).
metadata:
  author: docspec
  version: "2.0"
---

Attack the document and report what fails to hold up. A claim is true only if a primary source *literally* says so — the document's own assertion is never evidence for itself. You raise findings; you never fix.

**Input**: an article. You are the only full reader — read EVERY leaf's own files, not just the article root. `docspec guide` carries the exact `audit raise`/`resolve` invocation and the active attack faces; read them there, don't memorize.

**Steps**

1. **Get your surfaces** — `docspec instructions factcheck <section> --json` returns the active faces, `ancestorNormative` (rulings inherited from the whole ancestor chain), the coverage + coherence contracts, and the lean glossary index. For each leaf read its `concept` / `decisions` / `material` / `history` + the deliverable `docs` (the "why dropped" you need lives in `history`).

2. **Let the engine surface candidates first, then rule each claim (three-state)** — before reading everything, run `docspec find --numbers` (aggregates every number+unit by referent; a referent with **>1 distinct value** is a prime inconsistency candidate the engine hands you — it does NOT judge, you do; when a disagreeing quantity is NOT crystallized as a decision, your finding recommends crystallization — raise it as a decision + realizes edges — as the structural fix, the human ratifies) and `docspec find "<term>"` to jump straight to where a claim lives instead of reading whole files. Then pull every checkable assertion from `docs` and the outline's decisions and rule it: **entailed** (a source literally confirms → raise NOTHING; silence is the pass state) / **contradicted** (a source refutes it) / **unsupported** (no source backs it). Your OWN knowledge is not a source; the source must *say it* (no inference drift, no "this basically implies"). Mark a normative decision with no `trace` unsupported by default. (Whether a flagged number is actually wrong is your call, then the human's — the engine only presents; fact correctness is the writer's responsibility.)

3. **Audit the outline** — test siblings for MECE (gaps, overlaps); rule each `must_cover` item entailed/unsupported against the rendered prose; flag a section whose form fights its declared `layout`/`kind`; cross-read each section against its `ancestorNormative` — a section that CONTRADICTS an inherited ruling or ESCAPES the article's scope is a finding.

4. **Check coherence** — rule each pair in the coherence contract coherent/contradictory: `concept.title` / framing ↔ prose, this section's own brief ↔ the ancestor briefs, each decision's `statement`/`rationale` framing ↔ prose, a figure's framing ↔ prose, and an upstream **realized** truth ↔ this section's prose (the cross-document case: an upstream decision superseded while the consuming prose still implements the old truth). The hash ledger only restales on a byte change — a field that *should* have changed but didn't is squarely yours.

5. **Detect deliverable drift** — `docspec diff <article>` names sections whose prose moved past its source; classify each **cosmetic** / **substantive-content** / **substantive-style**; the fix loops to `develop` (source stale) or `apply` (prose out of line) — naming which is part of the finding.

6. **Raise** — `docspec audit raise --target <full/section/path>` (full paths, never a bare leaf), naming the face, the located defect, and a proposed `--suggest`. A cross-document contradiction is ONE finding spanning both targets. Run `docspec check` before calling any reference dangling (green = every id resolves, so a decision you "can't find" means you didn't read that section's file).

**Pause if:** never — you don't gate. Submit findings and stop; the human triages each (fix / reject / defer) and is the sole judge.

**Output**

```
## factcheck — <article>
Claims ruled: <N entailed / N contradicted / N unsupported>
Findings raised (docspec audit): [<face>] <target> — <located defect> → suggest: <fix>
Structural: <MECE gaps/overlaps, coverage misses, coherence contradictions>
```

**Guardrails**
- Adversarial at MAXIMUM — attack the most confident, least-cited sentences first; a near-empty pass is a RED FLAG you were too soft, not a clean bill. If you've found little, assume you missed something and dig harder before reporting.
- Absence of a source IS a finding; never accept the document (or one section citing another) as evidence for itself.
- Literal — if the source doesn't say it, it's unsupported, however reasonable the leap; your training memory never confirms a claim.
- Only flag, never fix — not the prose, not the outline, not a typo. Concrete, located findings; never open-ended "have you considered…?".
- Root-cause collapse — one cause = ONE finding (a `[TBD]` stub = one finding, not one-per-missing-claim); cite representative sites, don't spray.
- Rejection-aware — before raising, `docspec find "<claim keywords>" --in audit` to check whether the same issue was already raised and rejected; don't re-raise it. Verify a `fixed` finding on re-run. Output ONLY through `docspec audit`, never a hand-edit of `audit.yaml`.
