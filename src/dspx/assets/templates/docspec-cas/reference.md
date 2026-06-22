# docspec-cas template pack — craft reference

Static craft for editing this pack and translating diagrams. Surfaced by
`docspec reference <topic>`. This is **per-pack craft** (how-to for *this* visual
format), not engine rules — those live in `docspec guide`.

<!-- topic: latex-traps -->
## Known LaTeX traps

### Trap 1 — upstream cas-sc NFSS reset (the #1 font-size debugging dead-end)

**Symptom**: you enlarge `\renewcommand\normalsize{...}` in `preamble.tex`, but
the body text in the rendered PDF stays at ≈12 pt. Tables or headings change, body
doesn't.

**Root cause**: the upstream `cas-sc` class (which `docspec-cas` derives from) calls `\maketitle` during the document build. Inside that
call the class resets all NFSS size macros (`\normalsize`, `\small`, … ) back to the
class defaults (≈12 pt). Body text flows immediately after `\maketitle` without an
explicit `\normalsize`, so it picks up the class defaults — not your preamble.

**Correct fix** (already applied in `before.tex`): redefine the NFSS size macros
*after* `\maketitle`, not before, then apply `\normalsize` so the body picks it up.

```latex
% in before.tex, AFTER \maketitle
\makeatletter
\renewcommand\normalsize{\@setfontsize\normalsize{14.5}{18.3}}
\renewcommand\small{\@setfontsize\small{13}{16}}
\renewcommand\footnotesize{\@setfontsize\footnotesize{12}{14.5}}
\makeatother
\normalsize
```

**Verify** with `docspec measure-fonts <pdf>` — body should read ≈14.5 pt. If it
reads ≈12 pt the post-`\maketitle` fix is not in the build.

**Why tables change but body doesn't**: `docspec-tables.lua` emits an explicit
`\fontsize{...}\selectfont` (not `\normalsize`), so tables call the NFSS machinery
directly and pick up the current definition — body never calls `\normalsize`.

### Trap 2 — colortbl vertical-rule bleed

**Symptom**: table vertical rules are invisible — they disappear behind the zebra
`\rowcolor` background.

**Root cause**: `colortbl` draws `\rowcolor` as a full-cell background that covers
bare `|` column separators.

**Fix**: replace `|` with `!{\color{docspecRule}\vrule width \arrayrulewidth}`. The
`!{}` column spec draws *on top of* the background, so the rule stays visible.
Already applied in `docspec-tables.lua` as the `VRULE` constant.

<!-- topic: tikz -->
## Mermaid → TikZ idiom library

Pandoc cannot draw mermaid; the template renders each ` ```mermaid ` block as a
visible placeholder box. Translate the diagram once into native TikZ as a raw-LaTeX
block (a notation translation, presentation layer — never a content change).

### Pre-loaded styles

Use these directly — no `\tikzset` needed:

| Style | Shape | Use for |
|-------|-------|---------|
| `dspxflow` | Rounded rectangle | Flowchart step / process box |
| `dspxstate` | Ellipse | State-machine state |
| `dspxedge` | Arrow (Stealth tip) | Transition / dependency edge |
| `dspxgroup` | Rectangle frame (fit) | Cluster / swimlane boundary |

Pre-loaded libraries: `positioning`, `arrows.meta`, `fit`, `backgrounds`, `calc`,
`shapes.geometric`.

### Pattern: flowchart

```latex
\begin{center}
\begin{tikzpicture}[node distance=14mm and 20mm]
  \node[dspxflow] (a) {Step A};
  \node[dspxflow, right=of a] (b) {Step B};
  \node[dspxflow, right=of b] (c) {Step C};
  \draw[dspxedge] (a) -- node[above,font=\scriptsize]{cond} (b);
  \draw[dspxedge] (b) -- (c);
\end{tikzpicture}
\end{center}
```

### Pattern: state machine

```latex
\begin{center}
\begin{tikzpicture}[node distance=20mm]
  \node[dspxstate] (idle) {Idle};
  \node[dspxstate, right=of idle] (run) {Running};
  \node[dspxstate, right=of run] (done) {Done};
  \draw[dspxedge] (idle) -- node[above,font=\scriptsize]{start} (run);
  \draw[dspxedge] (run) -- node[above,font=\scriptsize]{finish} (done);
  \draw[dspxedge] (done) to[bend right=40] node[below,font=\scriptsize]{reset} (idle);
\end{tikzpicture}
\end{center}
```

### Pattern: cluster / swimlane

```latex
\begin{center}
\begin{tikzpicture}[node distance=12mm and 16mm]
  \node[dspxflow] (a) {Task A};
  \node[dspxflow, right=of a] (b) {Task B};
  \begin{scope}[on background layer]
    \node[dspxgroup, fit=(a)(b), label=above:{\scriptsize Lane 1}] {};
  \end{scope}
\end{tikzpicture}
\end{center}
```

### Gotchas

- **Backslash line-break in raw-LaTeX blocks**: writing `{閒置\\IDLE}` inside a
  ` ```{=latex} ` block — the markdown parser eats the `\\` before LaTeX sees it,
  leaving `\IDLE` (undefined). Use `align=center` + `text width=` to wrap long
  labels, or keep labels single-line.
- **Out-of-scope TikZ libraries**: the controlled TinyTeX does not ship `pdfcol`,
  `tikzfill.image`, `tcolorbox/skins`, etc. Stay within the listed libraries. If a
  diagram truly needs another package → template-pack change (`preamble.tex` AND
  `setup.py` `_TEX_PACKAGES`), not a per-document `\usepackage`.
- **CJK in node labels**: just type the characters. Nodes inherit the document CJK
  font (`xeCJK` is active); no per-node font setup needed.
