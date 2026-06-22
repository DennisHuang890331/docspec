# Contributing to docspec

Thanks for your interest! Bug reports, fixes, and proposals for new "technical-writing
rules for AI agents" are all welcome — open an issue or a PR.

## Dev setup

docspec is a `uv`-managed Python project (CLI `docspec`, package `dspx`, Python ≥ 3.11).

```bash
# run the CLI from source (no global install)
uv run --no-editable docspec --help

# run the test suite
uv run --no-editable pytest -q
```

> **Windows + non-ASCII project paths** (e.g. a Chinese-named Google Drive folder): always
> use `uv run --no-editable`. An *editable* install writes a `.pth` containing the non-ASCII
> path, which Python 3.11's site machinery decodes with the system codec (cp950 on zh-TW
> Windows) and crashes. `uv tool install` / `uvx` are unaffected (they live in an ASCII cache).

To install it as a global command from your checkout:

```bash
uv tool install --from . docspec --reinstall --no-cache
```

`--reinstall --no-cache` is required after code changes — otherwise uv serves a cached wheel
keyed by name+version and your changes won't take effect.

## Tests & CI

- The full suite must stay green: `uv run --no-editable pytest -q`.
- The **PDF-pipeline tests** (`export`/`proof`) need the controlled TinyTeX + OFL fonts
  (`docspec setup`) and a pandoc binary; without them they **skip** (not fail). CI
  (`.github/workflows/test.yml`) runs the suite on Windows + Linux without `setup`, so it
  exercises the deterministic engine. **macOS is currently unverified** — `setup`'s darwin
  branches (font/pandoc/TinyTeX) exist but have not been run on a real Mac; help wanted.

## Design principle for new rules

docspec keeps "intelligence" out of the engine. If you want to add a rule the agent must
follow:

- **Mechanical / deterministic** (id uniqueness, dead references, field completeness) →
  the engine may enforce it (a `check`/`lint` gate).
- **Semantic / judgment** (is this claim true? is this prose good?) → it is a **non-blocking
  audit** signal, never an engine gate (the audit itself can be wrong).
- Rules live in `schema.yaml` and are **projected** by `docspec guide`; skills only reference
  them, they never re-transcribe them (prose copies drift). Don't add an engine gate without
  a demonstrated real failure.

## Distribution

There is no PyPI release (the name is taken) — docspec is installed from git. See the README.

## License

**PolyForm Noncommercial 1.0.0** — free for any noncommercial purpose; commercial use
requires a separate license from the author. See the [`LICENSE`](LICENSE) file. By
contributing, you agree your contributions are licensed under the same terms. (This is a
*source-available, noncommercial* license — not an OSI "open source" license.)

Bundled third-party components keep their own licenses: the PDF template's document class
(`docspec-cas`) is a modified, renamed derivative of Elsevier's CAS class under LPPL 1.3c
(see `src/dspx/assets/templates/docspec-cas/NOTICE.md`); fonts are SIL OFL / government
open-data (downloaded at `docspec setup`; see `fonts/FONT-LICENSES.md`).
