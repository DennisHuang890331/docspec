# NOTICE — third-party components

docspec itself is licensed under **PolyForm Noncommercial 1.0.0** (see [`LICENSE`](LICENSE)).
It bundles or downloads a few third-party components that keep their own licenses:

## PDF template document class — `docspec-cas`

The PDF template's document class is a **modified, renamed derivative** of Elsevier's
**CAS (Complex Article Service) LaTeX bundle**. docspec changes the page geometry and NFSS
font sizes and trims the class for single-document delivery. Per **LPPL 1.3c**, a modified
work must be renamed, so the files ship as `docspec-cas*` (not `cas-sc`/`cas-common`).

- Original CAS Bundle © Elsevier, under LPPL 1.3c — <https://ctan.org/pkg/els-cas-templates>
- Modifications © 2026 Dennis Huang, under LPPL 1.3c — <https://www.latex-project.org/lppl/lppl-1-3c/>

Full detail: [`src/dspx/assets/templates/docspec-cas/NOTICE.md`](src/dspx/assets/templates/docspec-cas/NOTICE.md).

## Fonts

The fonts are **not shipped in this repository**. They are downloaded at `docspec setup`
from their upstream sources, and are all **SIL OFL 1.1** or **government open-data**.

Full detail: [`src/dspx/assets/templates/docspec-cas/fonts/FONT-LICENSES.md`](src/dspx/assets/templates/docspec-cas/fonts/FONT-LICENSES.md).

## TeX engine and tooling

`docspec setup` also downloads a pinned **TinyTeX** distribution and a pinned **pandoc**
binary into your user data dir; each keeps its own upstream license.
