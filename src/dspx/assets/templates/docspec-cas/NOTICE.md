# Third-party notice — docspec-cas template pack

This template pack's document class is a **modified derivative** of Elsevier's **CAS
(Complex Article Service) LaTeX bundle**:

- `docspec-cas.cls` — derived from and modifies the upstream `cas-sc.cls` (CAS Bundle
  v2.3, 2021/05/11): docspec changes the page geometry and NFSS font sizes and trims the
  class for single-document delivery.
- `docspec-cas-common.sty` — derived from the upstream `cas-common.sty`.

These files are **renamed** (`docspec-cas*`, not `cas-sc`/`cas-common`) because the
**LaTeX Project Public License (LPPL) 1.3c requires a modified work to be renamed** so it
cannot be confused with the original. They remain distributed under the LPPL, version
1.3c or later — <https://www.latex-project.org/lppl/lppl-1-3c/>.

- Original CAS Bundle © Elsevier, under LPPL 1.3c. Upstream: <https://ctan.org/pkg/els-cas-templates>.
- Modifications © 2026 Dennis Huang, under LPPL 1.3c.

The other files in this pack — `preamble.tex`, `before.tex`, `docspec-tables.lua` — are
docspec's own work (PolyForm Noncommercial 1.0.0, the project's license). The bundled
fonts are **not** shipped in this repository; they are downloaded at `docspec setup` from
their upstream sources — see `fonts/FONT-LICENSES.md` (all SIL OFL 1.1 or government
open-data).
