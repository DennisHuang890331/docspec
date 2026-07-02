# Showcase — real docspec output, and exactly how it was made

This folder holds six complete documents produced end-to-end with docspec, across three genres
(fiction / essay / academic survey) × two languages (English / Traditional Chinese). Each was written
from scratch by an AI agent driving docspec, passed docspec's structural, cleanliness, and
render-fidelity gates, and was exported to a typeset PDF. These are raw runs, not hand-edited or
cherry-picked.

This document records the method, the models, and the exact prompts, and reports the results in full,
including where they fell short.

## The six documents

| Genre | Lang | Read it | PDF | Sections / words | Engine gates | Blind style review |
|---|---|---|---|---|---|---|
| Fiction (short story) | ZH | [deliverables/novel-zh.md](deliverables/novel-zh.md) | [pdfs/novel-zh.pdf](pdfs/novel-zh.pdf) | 6 / ~3,500 | ✓ check · ✓ lint · ✓ fidelity | AI-tell 5/5, fluency 5/5 |
| Fiction (short fantasy) | EN | [deliverables/novel-en.md](deliverables/novel-en.md) | [pdfs/novel-en.pdf](pdfs/novel-en.pdf) | 5 / ~2,200 | ✓ check · 1 advisory WARN¹ · ✓ fidelity | AI-tell 4/5, fluency 5/5 |
| Essay | ZH | [deliverables/essay-zh.md](deliverables/essay-zh.md) | [pdfs/essay-zh.pdf](pdfs/essay-zh.pdf) | 5 / ~2,600 | ✓ check · ✓ lint · ✓ fidelity | AI-tell high, fluency high |
| Essay | EN | [deliverables/essay-en.md](deliverables/essay-en.md) | [pdfs/essay-en.pdf](pdfs/essay-en.pdf) | 6 / ~2,800 | ✓ check · ✓ lint · ✓ fidelity | AI-tell 4/5, fluency 5/5 |
| Academic survey | ZH | [deliverables/academic-zh.md](deliverables/academic-zh.md) | [pdfs/academic-zh.pdf](pdfs/academic-zh.pdf) | 10 / ~4,000 | ✓ check · ✓ lint · ✓ fidelity | AI-tell 5/5, fluency 5/5 |
| Academic survey | EN | [deliverables/academic-en.md](deliverables/academic-en.md) | [pdfs/academic-en.pdf](pdfs/academic-en.pdf) | 11 / ~4,900 | ✓ check · ✓ lint · ✓ fidelity | AI-tell 4/5, fluency 5/5 |

¹ novel-en drew one non-blocking `V17` WARN on the word *"tapestry"* — used literally, for a woven
wall-hanging in the story. That is the documented, accepted edge case: docspec flags "tapestry" as a
common AI-register tell, but the rule is advisory (never blocks publish) and the message itself says a
genuine literal use may be legitimate. The author correctly kept the good prose. See "What the lint
integration caught" below.

![Real, correctly-cited references generated in the English survey](images/academic-en-references.png)

*Above: the References page of the English PEFT survey — real papers with correct venues and arXiv
IDs (Lester et al. 2021, Prefix-Tuning, DoRA, AdaLoRA, …), not fabricated. Below: a page of the
Chinese short story, rendered in a book profile with first-line indent and serif CJK typesetting.*

![A page of the Chinese short story](images/novel-zh-prose.png)

## How these were made

**Models.** The authoring, review, and judging agents ran on **Claude Sonnet**. A **Claude Opus**
orchestrator drove the run and did the final verification — but the orchestrator never wrote or graded
the documents; it only dispatched agents and independently re-checked their work.

**Method — "naive author, from scratch."** Each document was produced by an agent that was told
*nothing* about docspec's internals: it was forbidden from reading docspec's source, its SKILL files,
or any project notes, and had to learn the whole tool purely from its CLI help (`docspec --help`,
`docspec guide`). It then ran the full authoring loop with nothing skipped:

```
plan  →  human-proxy reacts  →  author (develop → draft → edit → factcheck → fix → publish → export)
      →  independent blind style review  +  independent genre depth judge
```

- **plan**: propose a genre-appropriate outline (no tooling yet).
- **human-proxy**: a separate agent playing the commissioner reacts to the plan in a real, informal
  voice — one high-level steer, and it can send the plan back if it over-delivers or misses the point.
- **author**: one agent runs the entire docspec chain in a fresh scratch project, learning the CLI as
  it goes, and must get `check` + `lint` green and produce a fidelity-verified PDF.
- **blind review** + **depth judge**: two independent fresh-context agents that read only the finished
  deliverable — one scores AI-tell / fluency, the other judges genre depth with a demanding rubric.
- **orchestrator verification**: afterwards the Opus orchestrator personally re-ran `check`/`lint`/
  `status` on every project and `grep`-ed every deliverable for AI-tell signatures — it did **not**
  trust the agents' self-reports.

The exact stage prompts are reproduced in [PROMPTS.md](PROMPTS.md).

## Anti-AI-tell lint on unfamiliar genres

docspec ships closed-vocabulary "AI-tell" lint rules (Chinese meta-narration / hedge words, English
AI-register clichés). This run also tested whether those rules misfire on genres they were not tuned
on:

- **English `realm` — no false fire.** The fantasy story is literally *"The Cartographer of the
  Drifting Realm"* and uses "realm" as a noun throughout. The lint deliberately only flags the phrase
  *"in the realm of"*, so bare "realm" was correctly left alone.
- **English `leverage` — no false fire.** The academic survey uses the noun "leverage" ("not enough
  leverage to steer a frozen model"); the lint only flags the verb forms, so it was correctly left
  alone.
- **English `tapestry` — one accepted WARN.** Fired once on a literal woven tapestry in the fiction —
  advisory, non-blocking, correctly located to the exact section. Working as designed.
- **Chinese meta-narration ("報幕") — zero hits** across all three Chinese documents, confirmed by
  independent grep.

## Where they fell short: depth

Every document passed the **style** bar (fluent, natural, low AI-tell — confirmed independently). The
independent **depth** judges returned *revise* on all six: genuinely crafted, none a shallow shell,
but not yet publication-grade *deep*. This is a limitation of the test harness, not of docspec: the
author ran a single pass with one planning-stage human check and no iterative depth-revision loop,
whereas depth takes several rounds of write → critique → deepen. What these six demonstrate is style,
structure, consistency, and typesetting; depth at that level needs the revision loop a real
author-in-the-loop provides.

## Reproducing

These were built with the docspec CLI exactly as a user would (`docspec init` → author via the agent
skills → `docspec publish` → `docspec export`). The full run is recorded in the project's development
history; the stage prompts are in [PROMPTS.md](PROMPTS.md).
