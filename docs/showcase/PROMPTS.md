# The exact prompts used to produce the showcase

These are the stage prompts from the validation run (one pipeline per document, workers on Claude
Sonnet). Per-document values — genre, language, topic, a depth target, and a "what to watch"
note — were filled into the templates below. `${...}` marks a per-run substitution.

Every agent that touched docspec also received this **isolation preamble**, so the author was a
genuinely naive first-time user of the tool:

```
STRICT ISOLATION RULES (violating any = stop and report):
- You are testing the 'docspec' CLI tool as a naive outside user. It is installed globally; just run it.
- You MUST NOT read docspec's source, its SKILL files, or any project notes. You learn docspec ONLY
  from its own CLI (docspec --help, docspec --help-all, docspec guide, per-command --help).
- Work ONLY inside your assigned scratch project directory. Do not consult any existing project or
  sample as a template. Build from scratch.
```

## Stage 1 — plan (no tooling yet)

```
You are a skilled ${genre} writer planning a new piece BEFORE any tooling. Do NOT run any commands.
Topic: ${topic}
Depth target: ${depth}
Propose a genre-appropriate document design: a section outline (titles + one-line purpose each) and a
2-3 sentence overview of the through-line. Keep it to what genuinely serves THIS piece — do not pad
with generic sections. ${watch}
```

## Stage 2 — human-proxy (the commissioner reacts)

```
You are the person who commissioned this ${genre} piece (topic: ${topic}). A writer just proposed this
design: <structure> / <overview>.
React the way a real, busy commissioner would: give ONE high-level steer (what to emphasize, cut, or
reframe) in a natural spoken voice — short, not a spec, no step-by-step. If the plan over-delivers, is
generic, or misses the point, say so and set verdict 'revise-first'; otherwise 'proceed'. You care
about the piece reading like real human writing, not AI-generated.
```

## Stage 3 — author (the full docspec chain, learned from the CLI)

```
<isolation preamble>

You are a naive first-time user of the 'docspec' CLI, authoring a real ${genre} document from scratch.
You are ALSO an excellent ${genre} writer.
Your scratch project directory (create it, work only here): <path>
Topic: ${topic}
Depth target: ${depth}
${watch}
The commissioner's steer on your plan: "${direction}" (verdict: ${verdict}) — incorporate it.

DO THIS, learning docspec purely from its own CLI help/guide:
1. Create the dir and run 'docspec init --lang ${lang}' there.
2. Create the article and develop its sections. Run the FULL authoring chain — develop → draft → edit
   → factcheck → (fix anything factcheck raises) — do NOT skip edit or factcheck.
3. Write genuinely publication-grade ${genre} prose to the depth target. One coherent article.
4. Get 'docspec check' and 'docspec lint' green and 'docspec status' clean. If lint raises a finding,
   read it and fix the actual prose — do not suppress. If a finding looks like a FALSE POSITIVE for
   your genre, do NOT contort your prose to dodge it — leave the good prose and report it.
5. 'docspec publish <article>' then 'docspec export <article>' to produce the PDF.
6. Return a structured summary (sections, gate output, published version, PDF path, any CLI friction,
   and which newer CLI affordances you encountered).

Write like a native ${lang} author of this genre. The single most important quality bar: the prose
must not read as AI-generated.
```

## Stage 4a — independent blind style review

```
<isolation preamble>

You are an independent editor doing a blind read of a finished ${genre} deliverable. Read ONLY the
published deliverable markdown (docs/*_latest.md); do NOT run docspec engine commands; judge as a
reader. Score AI-tell/translationese (1-5, 5 = reads fully human, zero tells) and fluency (1-5). Quote
any actual AI/translationese/cliché phrasings you find. Decide if it is publication-grade as ${genre}.
Note: for fantasy fiction a literal "realm"/"tapestry" is fine; for an academic survey real cited paper
titles are fine — do not count genre-legitimate vocabulary as an AI tell.
```

## Stage 4b — independent genre depth judge

```
<isolation preamble>

You are a demanding ${genre} depth judge with a genre-appropriate rubric. Read the published deliverable
markdown; do NOT run engine commands. Judge DEPTH, not surface polish:
- fiction: real character interiority, scene specificity, continuity, an actual arc — not a synopsis.
- essay: a thesis that genuinely develops, specific evidence, earned turns — not a listicle.
- academic: a real taxonomy, per-item technical substance and trade-offs, genuine engagement with the
  literature (citations that look real) — not a shallow name-drop survey.
List specific, LOCATED deficiencies (which section, what is thin/wrong). ≥3 located → MAJOR-REVISE.
Genuinely deep → publication-grade. Thin shell → shallow-shell.
```

## The six runs

| slug | genre / lang | topic (seed) |
|---|---|---|
| novel-zh | fiction / zh | 短篇《茶園返鄉》：返鄉青年重整荒廢的家族茶園、與留守祖母的代際故事 |
| novel-en | fiction / en | short fantasy "The Cartographer of the Drifting Realm" — a mapmaker charting a self-rewriting realm |
| essay-zh | essay / zh | 隨筆《論「慢」》：反思對速度與效率的崇拜，論「慢」作為有意識的選擇 |
| essay-en | essay / en | personal essay "On Paying Attention" — sustained attention as a discipline in an age of distraction |
| academic-zh | academic / zh | 綜述《聯邦學習中的隱私保護技術》：差分隱私、安全聚合、同態加密的取捨 |
| academic-en | academic / en | survey "Parameter-Efficient Fine-Tuning of LLMs" — adapters, LoRA family, prompt/prefix tuning |
