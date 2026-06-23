<div align="center">

# docspec

**Write long technical documents with an AI agent — clean Markdown and fully typeset PDFs that stay internally consistent as they grow.**

![Python](https://img.shields.io/badge/python-%E2%89%A53.11-blue)
![License](https://img.shields.io/badge/license-PolyForm%20NC%201.0.0-orange)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux-lightgrey)
<!-- TODO: add CI badge once the repo is public: https://github.com/<owner>/docspec/actions -->

中文: [README.md](README.md)

</div>

You and the agent settle each section's logic and decisions first; docspec renders the prose and keeps the structure intact. As the document grows it stays consistent. You read only the rendered output — the backstage details are the agent's job.

## Who it's for

- You want to co-write a long, growing technical document or handbook with an AI agent, but worry it will drift and contradict itself.
- You maintain a multi-section spec or wiki that has to stay internally consistent — editing one place shouldn't quietly break another.
- You need a deliverable PDF with proper typesetting, not just Markdown.

## See it in action

You mostly invoke the built-in skills in your AI agent (Claude Code / Antigravity / Codex); the engine gatekeeps behind them:

```text
You: I want to write a doc on zenoh as a control plane — start an outline with develop
AI:  [develop] created corpus/zenoh/intro/, recorded the skeleton (no prose yet)
        ├─ concept:  why zenoh for the control plane
        └─ decision: control plane = zenoh, not MQTT

You: outline looks good, draft this section
AI:  [draft] blind-rendered to prose → docs/zenoh/_latest.md

You: publish
AI:  [publish] all gates green → froze a read-only v1 snapshot, bumped version, wrote changelog

You: make a PDF
AI:  [release] export → review page images → tune layout knobs → docs/exports/zenoh.pdf
```

<!-- TODO: add a screenshot of a rendered docs/exports/zenoh.pdf page (zenoh dogfood sample) -->
> 📄 **What the output looks like:** (PDF page screenshot to come)

## Quick start

> **Requires** `uv` and Python ≥ 3.11. Tested on Windows and Linux; macOS is not yet verified.

```bash
git clone <repo-url> && cd docspec
uv tool install --from . docspec
uv tool update-shell          # add uv's tool bin to PATH (once), then open a new shell
docspec init --tool claude    # create the workspace and install the skills into your agent
```

After that, the whole writing workflow runs inside your agent conversation, across six skills: develop → draft → edit → factcheck → publish (→ release for a PDF). You don't type `docspec publish` yourself — you ask the agent in chat and the engine gatekeeps. publish is irreversible, and that trigger stays with you: nothing is frozen until you say so.

The CLI commands you actually run by hand are the install-and-maintenance ones:

| command | what it does |
|---|---|
| `docspec init` | start a project, install the skills into your agent |
| `docspec setup` | download the PDF typesetting assets (only when you want PDFs) |
| `docspec doctor` / `upgrade` / `version` | health check / update / version |

`docspec --help` lists exactly these human commands; the full set the agent drives behind the scenes is under `docspec --help-all`.

## The six skills you use

A skill carries only judgment and stance. The mechanical details — fields, formats, steps — aren't hard-coded into the skill; they're projected live by `docspec guide`.

| skill | what it does | when |
|---|---|---|
| **develop** | Grow and restructure a section's concept & decision outline (audience, scope, depth). Skeleton first — no prose. | starting a doc, or restructuring |
| **draft** | Write one section into prose, seeing only that section's context — so it can't reference a sibling it can't see. | structure is set; turn a section into prose |
| **edit** | Publisher-style passes: line → copy → proofread. | prose written; polishing |
| **factcheck** | Adversarial review, every claim against a primary source. Flags only, never edits, never blocks publishing. | any time you want to verify |
| **publish** | Irreversible release: all gates green → freeze a read-only snapshot → bump version → write the changelog. | a version is final |
| **release** | Interactive typesetting: export → review page images → tune knobs → re-export. Presentation only, content never moves. | producing a PDF |

It's a loop, not a pipeline. When factcheck finds a problem, it goes back to develop or draft.

## PDF output

PDF delivery is one of docspec's main features. Add the export dependencies, then run `docspec setup` once — it downloads the controlled typesetting assets into your user data dir, without touching your system environment:

```bash
uv tool install --from . docspec --with pdfplumber --with pypdfium2 --with pypandoc_binary
docspec setup
```

**Typst is the default** renderer: a lightweight `typst` binary (~22MB, native CJK) plus a docspec-owned `.typ` house-style template; `setup` installs typst + pandoc + fonts. The content model is **backend-neutral** (Markdown + images, no LaTeX-only notation), so one document drives two tracks:

- **Typst track (default)** — docspec-owned template, bundled compile, full fidelity / byte-lock checks.
- **Journal LaTeX track (BYO, emit-only)** — for journal submission, docspec feeds your content through the journal's own pandoc template via a **slot contract** (title / authors / abstract / keywords / …) and emits a `.tex`; you compile it in Overleaf / the journal toolchain. Example IEEE and Elsevier adapters ship in-box: `docspec export <article> --journal {ieee,elsevier}`.

**Diagrams = drawio images**: during `draft`, a delegated subagent (loading the `dspx-diagram` skill) authors a `.drawio` and renders it to SVG, embedded into the deliverable (both tracks consume the same image). draw.io is an optional asset — run `docspec setup --with-drawio` when you want diagram rendering.

Then use the release skill in your agent to typeset interactively: export → review page images → tune layout knobs → re-export until it looks right. (The underlying `docspec export` is an agent command driven by the skill — you don't run it by hand.)

## Three agents, one skill set

`docspec init` installs the same SKILL.md set into Claude Code, Antigravity, and Codex, with a consistent skills-directory layout in each — so the same writing doctrine works in any of them.

<details>
<summary><b>How it works (open if you want the internals)</b></summary>

The usual failure mode when an AI writes docs: it reasons about logic and polishes wording at the same time, and you get something fluent but hollow and self-contradictory — and when you only want to check whether the logic holds, you're forced to read a screen of polished prose first. docspec splits those two jobs apart:

- **Backstage `corpus/` (for the agent and the engine).** Each section is a few small structured files: a one-line concept, a writing envelope (`brief`: who it's for, how deep), and the decisions it realizes. This layer cares only about rigor and factual completeness, not style.
- **Front `docs/` (for people).** The backstage is blind-rendered into finished prose — each section written in isolation, never peeking at siblings. **People read only this layer.**

Sections have stable ids, so moving or renaming folders never breaks a reference. Coherence across sections doesn't come from agents peeking at each other; it comes from one shared writing guide plus deterministic assembly.

```text
corpus/zenoh/intro/concept.yaml          docs/zenoh/_latest.md  (rendered, for people)
  concept: why zenoh for the control   ──▶   ## Why zenoh for the control plane
  brief:  {audience: devs, depth: ...}        zenoh replaces polling with pub/sub …
corpus/zenoh/intro/decisions.yaml             (generated from the brief + decisions;
  - statement: control plane = zenoh          it only says what the decisions say)
```

The engine only does deterministic gatekeeping (structure, completeness); whether the content is semantically right is left to the non-blocking factcheck.
</details>

## Why docspec

- **Review the logic before the prose.** You check the outline and the decisions, not a screen of polished text.
- **People read only the `docs/` output**; the backstage `corpus/` is for the agent and the engine.
- **The engine gates structure, not semantics.** Mechanical drift is caught deterministically; whether facts are right is flagged by a non-blocking review that never blocks your release.

## Development / contributing

Issues and PRs welcome. The dev setup, how to run the tests, and why Windows + non-ASCII paths need `uv run --no-editable` are all in [CONTRIBUTING.md](CONTRIBUTING.md).

## License

**PolyForm Noncommercial 1.0.0** — free for any noncommercial use; commercial use requires a separate license from the author. This is a source-available, noncommercial license, not an OSI "open source" license. Bundled third-party components keep their own licenses — see [`LICENSE`](LICENSE) and the root [`NOTICE.md`](NOTICE.md).

## Acknowledgements

docspec is adapted from [OpenSpec](https://github.com/Fission-AI/OpenSpec); it runs standalone, with no OpenSpec dependency. Thanks to the OpenSpec team for the original spec-driven AI-agent workflow that this prose-first derivative grew from.
