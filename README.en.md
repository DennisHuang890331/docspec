<div align="center">

<img src="docs/assets/logo.png" alt="docspec logo" width="140">

# docspec

**Write long technical documents with an AI agent that keeps them consistent as they grow, then export clean Markdown or a typeset PDF.**

![CI](https://github.com/DennisHuang890331/docspec/actions/workflows/test.yml/badge.svg) ![Python](https://img.shields.io/badge/python-%E2%89%A53.11-blue) ![License](https://img.shields.io/badge/license-PolyForm%20NC%201.0.0-orange) ![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux-lightgrey)

[English](README.en.md) · [中文](README.md)

</div>

docspec is a spec-driven authoring tool for long technical documents. The problem it fights is drift: as a document grows, an edit in an early section quietly stops matching a later one, and nobody notices until a reader does. In docspec you and an agent settle each section's concepts and decisions in a structured backstage, a thin deterministic engine renders those into prose, and whenever you change something upstream the engine names every section that has fallen out of sync. You review the structure and read only the finished document.

> Source-available under PolyForm Noncommercial 1.0.0: free for non-commercial use; commercial use needs a separate license. See [License](#-license).

## ✨ Highlights

- 🌱 **Stays consistent as it grows.** Change a section, a shared decision, or the house style, and the engine names exactly which sections you stranded and why they no longer fit. It tracks this by hashing the content each section depends on rather than by file timestamps, so the signal stays reliable even inside a Google Drive or OneDrive folder that rewrites modification times on every sync.
- 🧱 **Structure before prose.** Each section is drafted blind: the agent sees only that section's own backstage plus a computed projection of the specific upstream facts it must honor, never the whole growing document. Consistency across sections comes from one shared writing guide instead of constant rereading, which also keeps the cost of authoring or editing a section roughly flat however long the document gets.
- ⚙️ **A deterministic engine, not an LLM judge.** It blocks only on mechanical faults it can settle for certain: dead references, dependency cycles, missing or malformed fields, leaked internal jargon, and `[TBD]` stubs. Anything that turns on the meaning of the text becomes a non-blocking note rather than a gate, which is exactly why the checks that do block are ones you can trust.
- 🧹 **Clean deliverables.** Publish refuses to run if internal ids, scaffolding, placeholders, or leftover authoring vocabulary have leaked into the prose. A separate advisory lint flags common AI-register tells from a fixed word list, but that one only warns: you stay the judge of whether each flag is really a problem.
- 📄 **A provable PDF.** On export the engine re-reads the finished PDF and fails if a single character of the source text went missing, so a rendering glitch that silently dropped CJK text is caught instead of shipped. Typst renders the PDF by default; for journal submission you can emit a `.tex` instead.
- 🔗 **Document families that stay in sync.** Link related documents with `governed-by` and `realizes`, and a change to an upstream document propagates staleness to every downstream section that depends on it, so a set of specs flags what must re-sync instead of drifting apart in silence.

## 📚 Showcase

Six documents across three genres and two languages, each written from scratch by an agent driving docspec and carried all the way through the structural, cleanliness, and render-fidelity gates to a typeset PDF.

| Genre | Language | Read | PDF |
|---|---|---|---|
| Fiction — short story | Traditional Chinese | [read](docs/showcase/deliverables/novel-zh.md) | [PDF](docs/showcase/pdfs/novel-zh.pdf) |
| Fiction — short fantasy | English | [read](docs/showcase/deliverables/novel-en.md) | [PDF](docs/showcase/pdfs/novel-en.pdf) |
| Essay | Traditional Chinese | [read](docs/showcase/deliverables/essay-zh.md) | [PDF](docs/showcase/pdfs/essay-zh.pdf) |
| Essay | English | [read](docs/showcase/deliverables/essay-en.md) | [PDF](docs/showcase/pdfs/essay-en.pdf) |
| Academic survey | Traditional Chinese | [read](docs/showcase/deliverables/academic-zh.md) | [PDF](docs/showcase/pdfs/academic-zh.pdf) |
| Academic survey | English | [read](docs/showcase/deliverables/academic-en.md) | [PDF](docs/showcase/pdfs/academic-en.pdf) |

The method, the models, and the exact prompts are in [docs/showcase/](docs/showcase/), including where the results fell short.

## 🚀 Quick start

Requires `uv` and Python ≥ 3.11 (tested on Windows and Linux; macOS is not yet verified).

```bash
uv tool install git+https://github.com/DennisHuang890331/docspec
uv tool update-shell          # add uv's tool bin to PATH (once), then open a new terminal
docspec init                  # scaffold a project; installs into Claude Code, Codex, or Antigravity (pick one, or --tool all)
```

You author inside your agent's chat through the installed skills, so the docspec commands you type by hand are only the ones for setup and maintenance:

| Command | Purpose |
|---|---|
| `docspec init` | create a project and install the skills into your agent |
| `docspec setup` | download the PDF typesetting toolchain (only when you export a PDF) |
| `docspec doctor` / `upgrade` / `version` | diagnose the environment / align the managed PDF toolchain / show version |

`docspec --help` lists these human-facing commands, and the full agent-facing set is under `docspec --help-all`. Note that `docspec upgrade` aligns the PDF toolchain rather than docspec's own code; to update docspec, re-run the install command above.

## 🧠 How it works

A docspec project has two layers. The **backstage** (`corpus/`) holds a few YAML files per section: a short concept, a brief that fixes the audience, depth, and breadth, and the section's decisions. The **front** (`docs/`) is the rendered prose, one file per document, assembled from the sections. Keeping them apart is the whole point, because you can review the structure and the decisions without wading through polished prose, and the prose is regenerated from the structure rather than hand-maintained beside it. **You read only the front.**

```text
myproject/
├─ docspec/corpus/peft-survey/       # backstage — for the agent + engine
│  └─ lora-family/                    #   one leaf section
│     ├─ concept.yaml                 #     concept + brief
│     └─ decisions.yaml               #     the section's decisions
└─ docs/peft-survey_latest.md         # front — rendered prose (you read only this)
```

The engine renders those YAML files into prose:

```yaml
# corpus/peft-survey/lora-family/concept.yaml
title: "Low-Rank Reparameterization: LoRA and Its Variants"
concept: "LoRA and its descendants as one low-rank update injected into a frozen weight matrix."
brief:
  audience: the survey's technical readership
  depth: mechanism — the decomposition and why mergeability follows
  breadth: "LoRA, QLoRA, AdaLoRA, DoRA, VeRA — not every variant"
# corpus/peft-survey/lora-family/decisions.yaml
entries:
  - id: dec-lora-merge
    statement: "LoRA's update lives in weight space, so it merges into the frozen
      matrix — a merged checkpoint adds zero inference latency."
```
```markdown
# docs/peft-survey_latest.md  (rendered; you read only this)
## Low-Rank Reparameterization: LoRA and Its Variants
… the low-rank update is added directly into the frozen matrix in weight space,
so it can be merged permanently … with no latency cost beyond the base model.
```

The snippet is simplified; a real `concept.yaml` also carries `id`, `order`, and `status`, and each decision a `kind` and `status`. The field set is closed: a key the engine doesn't recognize is a hard `check` error, never silently ignored. Section ids are content-independent and permanent, so moving or renaming a section never breaks a reference to it.

Staleness travels along four axes, and `docspec status` names them per section: the section's own source changed (own), a decision it `realizes` changed (upstream), an ancestor's brief changed (inherited), or the shared writing guide or glossary changed (style). Each axis points at the right repair — rewrite where the content moved, restyle where only the voice did.

## ✍️ Authoring workflow

You describe what you want in your agent's chat, and it invokes six skills while the engine gatekeeps behind them:

| Skill | What it does |
|---|---|
| **develop** | grow or restructure a section's concepts and decisions (audience, depth, breadth); skeleton first, no prose |
| **draft** | render one section to prose, seeing only that section |
| **edit** | an editing pass: line → sentence → proofread |
| **factcheck** | adversarial check of each claim against a source; flags only, never blocks a release |
| **publish** | irreversible release: gates green → freeze a read-only snapshot → bump version → changelog |
| **release** | interactive PDF layout: export → review page images → tune knobs → re-export |

This is a loop, not a pipeline: when factcheck finds a problem, the work returns to develop or draft before it comes back through publish. Graduating a section is also a transaction: the develop-stage scratch file must be squeezed dry and the fields complete before `docspec ready` lets it advance, so the engine's index never holds a section that looks finished but isn't. The full contract the agent follows (fields, workflow, rules) is projected live by `docspec guide`, not kept in documentation that can go stale.

## 📄 PDF output

Install the export extra and run setup once. Setup downloads a managed toolchain into your user data directory without touching your system:

```bash
uv tool install "docspec[export] @ git+https://github.com/DennisHuang890331/docspec"
docspec setup
```

**Typst, by default.** docspec ships a house-style Typst template with native CJK and no LaTeX dependency, along with layout profiles for essays, manuals, novels, and academic papers. `docspec export <article>` builds the PDF and byte-checks it against the source, so a rendering failure that dropped text is caught at export time rather than discovered by a reader.

**Bring your own journal template.** docspec also has an emit-only journal track for submission: it fills a fixed slot contract of title, authors, abstract, keywords, and body, then writes a `.tex` for Overleaf or your own LaTeX toolchain. Adapters for IEEE, Elsevier, and IET ship in the box, so `docspec export <article> --journal ieee` is enough for those. For a journal docspec doesn't bundle, put that journal's LaTeX template in a directory and pass `--template <dir>`; the release skill reads the journal's own sample `.tex` and maps your article's title, authors, abstract, keywords, and body onto that journal's macros so the emitted file compiles the way the journal expects. docspec emits the `.tex` and leaves the compilation to you.

## 📐 Diagrams

Engineering diagrams are part of the document, not something bolted on at export. When a section needs one, `draft` hands off to a support skill, **dspx-diagram**, which authors the figure as a real draw.io file and renders it to a high-resolution PNG embedded in the deliverable. What lands on the page is vector-drawn boxes and edges, not ASCII art and not an unrendered mermaid block. Install the renderer once with `docspec setup --with-drawio`.

## ✂️ What it deliberately leaves out

The engine never judges meaning. There is no semantic "is this correct" gate, no verbatim transclusion, and no genre type-system; each was considered and cut. Even staleness works at the level of content bytes, so if two sections come to contradict each other without either one's source changing, the engine stays quiet, and reconciling that is the job of the non-blocking factcheck rather than a gate. The engine stays a gate you can trust precisely because it only decides what is mechanically decidable, and it leaves every question of meaning to a human and an advisory pass.

## 📜 License

docspec is licensed under **PolyForm Noncommercial 1.0.0**: free for personal writing, research, coursework, open-source documentation, and non-paid sharing. Commercial use (selling what you write, running it as a company knowledge base, or authoring specs for a commercial product) requires a separate license from the author. It is source-available, not OSI-approved open source. See [`LICENSE`](LICENSE) and [`NOTICE.md`](NOTICE.md) for bundled third-party components.

## 🙏 Acknowledgements

docspec is a prose-first derivative of [OpenSpec](https://github.com/Fission-AI/OpenSpec). It runs standalone and does not depend on it (OpenSpec is used only to manage docspec's own development).

docspec was designed by the author; the implementation and tests were written by Anthropic's [Claude](https://claude.com/claude-code) (Claude Code).
