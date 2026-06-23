# NOTICE — third-party components

docspec itself is licensed under **PolyForm Noncommercial 1.0.0** (see [`LICENSE`](LICENSE)).
It bundles or downloads a few third-party components that keep their own licenses:

## PDF templates

The **default PDF track** uses docspec's own **Typst** house-style template
(`src/dspx/assets/templates/docspec-typst/`), authored by docspec and covered by docspec's
own PolyForm Noncommercial license.

The **journal track** ships per-journal LaTeX **adapter templates**
(`src/dspx/assets/templates/journals/`) derived from each journal's officially published
author template; each keeps its upstream license. docspec only *emits* `.tex` through these —
the user compiles it in the journal's own toolchain.

> Earlier releases bundled a modified, renamed derivative of Elsevier's CAS LaTeX class
> (`docspec-cas`, under LPPL 1.3c). That class and its track were **removed**; docspec no
> longer distributes Elsevier-derived class files.

## Fonts

The fonts are **not shipped in this repository**. They are downloaded at `docspec setup`
from their upstream sources, and are all **SIL OFL 1.1** or **government open-data**.

Full detail: [`src/dspx/assets/fonts/FONT-LICENSES.md`](src/dspx/assets/fonts/FONT-LICENSES.md).

## TeX engine and tooling

`docspec setup` also downloads a pinned **TinyTeX** distribution and a pinned **pandoc**
binary into your user data dir; each keeps its own upstream license.
