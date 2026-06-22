# Template pack — developer notes

Internal notes for **docspec maintainers** working on the `docspec-cas` template pack and
the export pipeline. These are *not* agent-facing (the agent-facing craft reference
ships with the pack at `assets/templates/docspec-cas/reference.md`, surfaced by
`docspec reference`). They are recorded here so they leave the agent's prose surface
without being lost.

## Adding a new LaTeX package (two-step coupling)

To use a new LaTeX package in the pack you must change **two** places:

1. add `\usepackage{...}` in `assets/templates/docspec-cas/preamble.tex`, AND
2. add the TeX Live package name to `_TEX_PACKAGES` in `commands/setup.py`.

The preamble alone works only on a machine where the package happens to be installed;
`_TEX_PACKAGES` is what `docspec setup` installs into the controlled TinyTeX on a fresh
machine. Ship one without the other and the build passes for you and fails for everyone
who runs `docspec setup` clean.

## Trap — xelatex log "black box"

When xelatex fails, the detail is in `doc.log` in the ASCII build dir (export prints the
path). `export.py` already captures xelatex stdout and surfaces the first `!` error line
on failure; if you need more, read `doc.log` directly.

## Trap — Windows cp950 codec crash (already fixed)

On zh-TW Windows, `subprocess.run(..., text=True)` decodes xelatex output with the system
locale codec (cp950), which chokes on non-cp950 bytes in the log. The fix — already
applied in `export.py` — is explicit `encoding="utf-8", errors="replace"` on every
subprocess that reads tool output. Keep that invariant when adding new subprocess calls.
