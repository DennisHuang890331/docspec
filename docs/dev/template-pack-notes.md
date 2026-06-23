# Template pack — developer notes

Internal notes for **docspec maintainers** working on the template packs and the export
pipeline. The default PDF track uses docspec's own Typst pack
(`assets/templates/docspec-typst/`, a single `template.typ` — all format control is exposed
as validated `--format-config` knobs, so it ships no separate craft reference). The journal
track ships per-journal LaTeX adapter packs (`assets/templates/journals/`); docspec emits
`.tex` through them and the user compiles it.

> The traps below concern the **LaTeX / journal** track only. The bundled Elsevier-derived
> `docspec-cas` LaTeX class and the docspec-owned `--engine latex` compile path it used were
> **removed**; the default render path is Typst.

## Adding a new LaTeX package (journal track — two-step coupling)

To rely on a new LaTeX package when compiling a journal `.tex` with the controlled TinyTeX
you must change **two** places:

1. add `\usepackage{...}` in the relevant journal adapter under `assets/templates/journals/`, AND
2. add the TeX Live package name to `_TEX_PACKAGES` in `commands/setup.py`.

The template alone works only on a machine where the package happens to be installed;
`_TEX_PACKAGES` is what `docspec setup` installs into the controlled TinyTeX on a fresh
machine. Ship one without the other and the build passes for you and fails for everyone
who runs `docspec setup` clean.

## Trap — xelatex log "black box" (journal track)

When xelatex fails compiling a journal `.tex`, the detail is in `doc.log` in the ASCII build
dir. Keep capturing xelatex stdout and surfacing the first `!` error line on failure; if you
need more, read `doc.log` directly.

## Trap — Windows cp950 codec crash (already fixed)

On zh-TW Windows, `subprocess.run(..., text=True)` decodes xelatex output with the system
locale codec (cp950), which chokes on non-cp950 bytes in the log. The fix — already
applied in `export.py` — is explicit `encoding="utf-8", errors="replace"` on every
subprocess that reads tool output. Keep that invariant when adding new subprocess calls.
