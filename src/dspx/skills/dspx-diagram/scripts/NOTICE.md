# Vendored scripts — attribution

`validate.py` and `encode_drawio_url.py` are vendored, essentially unmodified
(only an attribution header added), from the **Agents365 draw.io skill**:

- Source: https://github.com/Agents365-ai/drawio-skill
- License: MIT License — Copyright (c) 2026 Agents365-ai

The full MIT license text follows. docspec itself is distributed under
PolyForm Noncommercial 1.0.0; the MIT license of these vendored files is
compatible with that distribution (MIT permits relicensed redistribution as
long as the MIT copyright notice and permission notice are preserved, which
this NOTICE does).

docspec deliberately vendored ONLY the deterministic structural linter
(`validate.py`) and the browser-fallback URL encoder (`encode_drawio_url.py`).
The heavier parts of the upstream skill — the 10k-shape index, AI-brand icon
lookup, code-import-graph visualizers, Graphviz autolayout, and style presets —
were intentionally dropped (see decision D9 in the
`typst-default-dual-track-rendering` change).

---

MIT License

Copyright (c) 2026 Agents365-ai

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
