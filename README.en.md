# docspec

中文: [README.md](README.md)

A spec-driven tool for writing **documents** with an AI agent. It brings the engineering
habit of "settle the spec before you implement" to prose: the agent works out the logic
first (what each section says, which decisions it rests on), then renders it into clean
prose for people to read. The engine only does deterministic gatekeeping; whether the
content is *right* is left to a non-blocking review.

Adapted from [OpenSpec](https://github.com/Fission-AI/OpenSpec), tuned for human-AI
co-authoring of technical docs, wikis, and specs. Standalone, with no OpenSpec dependency.

> **Status:** early, single-maintainer, installed from git (no PyPI release). Requires `uv`
> and Python ≥ 3.11. Tested on Windows and Linux; macOS is not yet verified.

## The idea

The usual failure mode when an AI writes docs: it reasons about logic and polishes wording
at the same time, and you get something fluent but hollow and self-contradictory — and when
you just want to check whether the logic holds, you're forced to read a screen of polished
prose first.

docspec splits those two jobs apart:

- **Backstage `corpus/` (for the agent and the engine).** Each section is a few small
  structured files: a one-line concept, a writing envelope, and the decisions it realizes.
  This layer cares only about rigor and factual completeness, not style.
- **Front `docs/` (for people).** The backstage is **blind-rendered** into finished prose.
  **People read only this layer.**

Sections have stable ids, so moving or renaming folders never breaks a reference. Coherence
across sections doesn't come from agents peeking at each other; it comes from one shared
writing guide plus deterministic assembly.

Roughly, it looks like this — you (via the agent) fill the structured backstage files, and
docspec renders the front prose:

```
corpus/zenoh/intro/concept.yaml          docs/zenoh/_latest.md  (rendered, for people)
  concept: why zenoh for the control   ──▶   ## Why zenoh for the control plane
  brief:  {audience: devs, depth: ...}        zenoh replaces polling with pub/sub …
corpus/zenoh/intro/decisions.yaml             (generated from the brief + decisions;
  - statement: control plane = zenoh          it only says what the decisions say)
```

## How you use it: six skills

The real workflow is six built-in **skills** installed into your AI agent (Claude Code /
Antigravity / Codex). You invoke them in chat; the engine gatekeeps behind them. A skill
carries only **judgment and stance** — the mechanical details (fields, formats, steps) are
projected live by `docspec guide`, never hard-copied into prose that drifts.

| skill | what it does | when |
|---|---|---|
| **develop** | Developmental editing. Grow/restructure the concept & decision outline (audience, scope, depth, structure). Skeleton first — no prose here. | starting a doc, or restructuring |
| **draft** | Blind-render prose. One section at a time, seeing only its projected context, not peeking at siblings — so it can't invent a cross-reference to a section it can't see. | structure is set; turn a section into prose |
| **edit** | Publisher-style passes: line → copy → proofread. Deterministic checks go to the engine; judgment goes to a clean subagent. | prose written; polishing |
| **factcheck** | Adversarial review. Every claim against a primary source; attack the outline for gaps and contradictions. **Flags only, never edits**, and never blocks publishing. | any time you want to verify |
| **publish** | Irreversible release (you pull the trigger). All gates green → freeze a read-only snapshot → bump version → write the changelog. | a version is final |
| **release** | Interactive typesetting. Lay a frozen snapshot into a delivered PDF: export → look at the page images → tune format knobs → re-export until it looks right. Presentation only, content never moves. | producing a PDF |

It's a **loop**, not a pipeline: when factcheck finds a problem, it goes back to develop or draft.

## Install

docspec is a standalone CLI (package `dspx`, command `docspec`), installed via git (the
PyPI name is taken).

```bash
git clone <repo-url> && cd docspec
uv tool install --from . docspec
uv tool update-shell      # add uv's tool bin to PATH (once), then open a new shell
docspec --version
```

To pick up source changes, reinstall (don't omit `--no-cache`, or uv serves a cached old wheel):

```bash
uv tool install --from . docspec --reinstall --no-cache
```

For PDF output, add the export dependencies and run `docspec setup` once to download the
controlled typesetting assets (TinyTeX + OFL fonts, into your user data dir; it never
touches your system environment):

```bash
uv tool install --from . docspec --with pdfplumber --with pypdfium2 --with pypandoc_binary
docspec setup
```

## Quickstart

```bash
docspec init --tool claude     # create the workspace and install the skills into your agent
                               # (omit --tool to be prompted)
```

Then you mostly work inside your agent: develop → draft → edit → factcheck → publish (→
release for a PDF).

As a human you really only touch three commands — everything else the agent calls for itself
through the skills:

- `docspec init` — start a project
- `docspec publish <article>` — finalize and release (irreversible; you pull the trigger)
- `docspec export <article>` — produce a PDF

`docspec --help` lists just these human commands; the full set (for agents) is under
`docspec --help-all`.

## Three agents, one skill set

`docspec skills install` (run automatically by `init`) installs the same SKILL.md set into
Claude Code, Antigravity, and Codex, with a consistent skills-directory layout in each — so
the same writing doctrine works in any of them.

## Development / contributing

Issues and PRs welcome. The dev setup, how to run the tests, and why Windows + non-ASCII
paths need `uv run --no-editable` are all in [CONTRIBUTING.md](CONTRIBUTING.md).

## License

**PolyForm Noncommercial 1.0.0** — free for any **noncommercial** purpose (personal,
research, education, nonprofits, government); **commercial use requires a separate license
from the author**. See [`LICENSE`](LICENSE). This is a source-available, noncommercial
license, not an OSI "open source" license.

Bundled third-party components keep their own licenses: the PDF template's document class
(`docspec-cas`) is a **modified** derivative of Elsevier's CAS class, **renamed** as LPPL
1.3c requires (see [`NOTICE.md`](src/dspx/assets/templates/docspec-cas/NOTICE.md)); fonts are
SIL OFL 1.1 or government open-data (downloaded at `docspec setup`; see
[`FONT-LICENSES.md`](src/dspx/assets/templates/docspec-cas/fonts/FONT-LICENSES.md)).

## Acknowledgements

docspec builds on the concepts and principles of
[OpenSpec](https://github.com/Fission-AI/OpenSpec) — thanks to the OpenSpec team for the
original spec-driven AI-agent workflow design that this prose-first derivative grew from.
