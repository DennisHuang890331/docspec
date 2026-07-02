<div align="center">

# docspec

**Write long technical documents with an AI agent that stay internally consistent — clean Markdown and a typeset PDF.**

![Python](https://img.shields.io/badge/python-%E2%89%A53.11-blue)
![License](https://img.shields.io/badge/license-PolyForm%20NC%201.0.0-orange)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux-lightgrey)
<!-- TODO: add CI badge once the repo is public: https://github.com/<owner>/docspec/actions -->

[English](README.en.md) · [中文](README.md)

</div>

> [!WARNING]
> **Non-commercial license.** docspec is licensed under PolyForm Noncommercial 1.0.0. Free for
> personal writing, research, coursework, open-source documentation, and non-paid sharing.
> Commercial use — selling what you write, running it as a company knowledge base, or authoring specs
> for a commercial product — requires a separate license. This is source-available, not OSI-approved
> open source.

docspec is a spec-driven authoring tool for long documents. You and an AI agent settle each section's
concepts and decisions in a structured backstage; the engine renders them to prose and keeps the
whole document consistent as it grows. You read only the rendered deliverable.

## Features

- **Consistent as it grows** — sections have stable ids and share one writing guide, so editing one
  section doesn't silently break another; cross-document edges keep multi-document sets in sync.
- **Structure before prose** — you review concepts and decisions, not a wall of polished text; the
  engine turns them into prose.
- **Clean Markdown and typeset PDF** — every document renders to Markdown and exports to a
  Typst-typeset PDF; a journal LaTeX track can emit `.tex` for submission.
- **Natural prose** — a writing guide and cleanliness lint suppress AI-register tells in English and
  translationese in Chinese ([see real output](docs/showcase/)).
- **Runs in your agent** — Claude Code, Antigravity, or Codex, from one skill set.

## Quick start

Requires `uv` and Python ≥ 3.11 (tested on Windows and Linux; macOS is not yet verified).

```bash
git clone <repo-url> && cd docspec
uv tool install --from . docspec
uv tool update-shell          # add uv's tool bin to PATH (once), then open a new terminal
docspec init --tool claude    # scaffold a project and install the skills into your agent
```

Authoring happens inside your agent's chat through the built-in skills, not by typing docspec commands
yourself. The commands you run by hand are just setup and maintenance:

| Command | Purpose |
|---|---|
| `docspec init` | create a project and install the skills into your agent |
| `docspec setup` | download PDF typesetting assets (only when you export a PDF) |
| `docspec doctor` / `upgrade` / `version` | diagnose / update / show version |

`docspec --help` lists these human-facing commands; the full agent-facing set is under
`docspec --help-all`.

## How it works

A docspec project has two layers. The **backstage** (`corpus/`) holds a few structured YAML files per
section — a one-line concept, a brief (audience, scope, depth), and the decisions the section
realizes. This is where logic and completeness live, and it is for the agent and engine. The **front**
(`docs/`) is the rendered prose deliverable — each section rendered in isolation, then assembled
deterministically. **People read only the front.** Section ids are stable, so moving or renaming a
section never breaks a reference; coherence across sections comes from a shared writing guide, not
from agents reading each other.

You drive all of this from your agent's chat through six skills; the engine gatekeeps behind them.

### Your first document

After `docspec init`, open your agent in the project and describe what you want to write:

1. **"Start a doc on X — use develop."** The agent builds the section skeleton and asks you about
   audience, scope, and depth. You review the outline — concepts and decisions — not prose.
2. **"Draft this section."** The agent renders that section to prose in `docs/`; you read it there.
3. **"Edit"** then **"factcheck"** — a polishing pass, then each claim is checked against a source.
4. **"Publish"** when a version is done: the engine runs its gates, freezes a read-only versioned
   snapshot, and writes a changelog entry. **"Make a PDF"** exports a typeset PDF.

You never edit the backstage or run engine commands by hand — you talk to the agent and read the
rendered `docs/` file at each step. In chat it looks like this:

```text
You: draft a doc on zenoh as a control plane — start with develop
AI:  [develop] created corpus/zenoh/intro/ — recorded the skeleton (no prose yet)
        ├─ concept:  why zenoh for the control plane
        └─ decision: control plane = zenoh, not MQTT
You: outline looks good, draft this section
AI:  [draft] blind-rendered to prose → docs/zenoh/_latest.md
You: publish
AI:  [publish] gates green → froze a read-only v1 snapshot, bumped version, wrote changelog
```

The six skills:

| Skill | What it does |
|---|---|
| **develop** | grow or restructure a section's concepts and decisions (audience, scope, depth); skeleton first, no prose |
| **draft** | render one section to prose, seeing only that section |
| **edit** | an editing pass: line → sentence → proofread |
| **factcheck** | adversarial check of each claim against a source; flags only, never blocks a release |
| **publish** | irreversible release: gates green → freeze a read-only snapshot → bump version → changelog |
| **release** | interactive PDF layout: export → review page images → tune knobs → re-export |

It is a loop, not a pipeline: when factcheck finds a problem, work goes back to develop or draft.
Change an upstream section later and the engine marks every downstream section that needs re-syncing,
so nothing drifts out of consistency unnoticed.

## Design

The decisions docspec is built on:

- **Semantics separated from the engine** — the engine is a thin, deterministic gatekeeper: id
  uniqueness, dead references, cycles, completeness, staleness by content hash, publish freeze. It
  makes no semantic judgment; content correctness is handled by a non-blocking factcheck/audit that
  flags but never blocks a release.
- **Token-efficient authoring** — a document is a projection of a structure layer. Each section is
  rendered blind — seeing only itself plus an engine-projected aperture of the relevant upstream
  truths, never the whole growing document. Only sections whose content hash changed re-render, so
  per-action token cost does not grow with document length.
- **A writing-quality system** — writing-guide backbone rules, language-seeded naturalness
  conventions written at `docspec init --lang` time, glossary consistency, cleanliness lint
  (V1–V17, including rules for Chinese meta-narration and English AI-register clichés), and a citable
  writing reference (`docspec reference writing-zh/en`).
- **Deliverable / backstage separation** — humans read only `docs/`; `corpus/` is for the agent and
  engine, and cleanliness gates keep backstage vocabulary out of the deliverable.
- **Multi-document forest governance** — `governed-by` / `realizes` edges propagate staleness across
  documents, so a set of specs cannot silently contradict itself.

## PDF output

Install the export extra and run setup once; it downloads managed typesetting assets into your user
data directory without touching your system:

```bash
uv tool install --from ".[export]" docspec
docspec setup
```

docspec renders with **Typst** by default (a ~22 MB binary with native CJK and a bundled house-style
template). Content is backend-neutral (Markdown + images), so one source drives two tracks: the
default Typst track (compiled, fidelity-checked) and a bring-your-own journal LaTeX track that emits a
`.tex` through a slot contract for you to compile (IEEE and Elsevier adapters included). Diagrams are
drawn by a delegated subagent as drawio and embedded as high-resolution PNG; `docspec setup
--with-drawio` installs the managed drawio.

## Showcase

Six documents written from scratch by an agent driving docspec — three genres × two languages — each
one passing the structural, cleanliness, and render-fidelity gates and exported to a typeset PDF.
Click through to read the rendered output or open the PDF:

| Genre | Language | Read | PDF |
|---|---|---|---|
| Fiction — short story | Traditional Chinese | [read](docs/showcase/deliverables/novel-zh.md) | [PDF](docs/showcase/pdfs/novel-zh.pdf) |
| Fiction — short fantasy | English | [read](docs/showcase/deliverables/novel-en.md) | [PDF](docs/showcase/pdfs/novel-en.pdf) |
| Essay | Traditional Chinese | [read](docs/showcase/deliverables/essay-zh.md) | [PDF](docs/showcase/pdfs/essay-zh.pdf) |
| Essay | English | [read](docs/showcase/deliverables/essay-en.md) | [PDF](docs/showcase/pdfs/essay-en.pdf) |
| Academic survey | Traditional Chinese | [read](docs/showcase/deliverables/academic-zh.md) | [PDF](docs/showcase/pdfs/academic-zh.pdf) |
| Academic survey | English | [read](docs/showcase/deliverables/academic-en.md) | [PDF](docs/showcase/pdfs/academic-en.pdf) |

How they were made — the models, the method, and the exact prompts — is written up in
**[docs/showcase/](docs/showcase/)**, including an honest account of where the results fell short.

## Contributing

Issues and PRs welcome. Dev setup, running the tests, and why non-ASCII paths on Windows need
`uv run --no-editable` are in [CONTRIBUTING.md](CONTRIBUTING.md).

## License

**PolyForm Noncommercial 1.0.0** — free for any non-commercial use; commercial use requires a
separate license from the author. Source-available, not OSI open source. See the usage boundary at
the top of this file, [`LICENSE`](LICENSE), and [`NOTICE.md`](NOTICE.md) for bundled third-party
components.

## Acknowledgements

docspec is a prose-first derivative of [OpenSpec](https://github.com/Fission-AI/OpenSpec); it runs
standalone and does not depend on it. Thanks to the OpenSpec team for the spec-driven agent workflow
it grew from.
