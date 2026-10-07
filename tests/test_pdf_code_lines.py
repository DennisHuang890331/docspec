"""Behavioral code-layout regressions through real Pandoc/Typst PDF export."""

from __future__ import annotations

import subprocess
from statistics import median

import pytest

from dspx.commands import export as export_cmd
from dspx.engine import paths
from dspx.engine.layout import Layout
from dspx.reports import freeze


CODE = (
    "# next_step\n"
    "value = 7\n"
    "\n"
    "if value:\n"
    "    print(value)\n"
    "done = value\n"
)


@pytest.fixture
def managed_pdf_tools(monkeypatch):
    """Use managed pinned binaries and controlled fonts, never PATH substitutes."""
    pandoc = paths.pandoc_dir() / paths.pandoc_exe_name()
    typst = paths.typst_dir() / paths.typst_exe_name()
    fonts = paths.fonts_dir()
    missing = [str(p) for p in (pandoc, typst) if not p.is_file()]
    missing += [str(fonts / name) for name in paths.REQUIRED_FONT_FILES
                if not (fonts / name).is_file()]
    if missing:
        pytest.skip("Managed PDF platform unavailable: " + ", ".join(missing))
    for binary, expected in ((pandoc, "pandoc 3.10"), (typst, "typst 0.15.0")):
        version = subprocess.check_output(
            [str(binary), "--version"], text=True, encoding="utf-8"
        ).splitlines()[0]
        assert version.split()[:2] == expected.split(), version
    monkeypatch.setenv("DOCSPEC_PANDOC", str(pandoc))
    monkeypatch.setenv("DOCSPEC_TYPST", str(typst))
    monkeypatch.setenv("DOCSPEC_FONTS_SRC", str(fonts))
    return pytest.importorskip("pdfplumber", reason="PDF coordinate inspection needs pdfplumber")


def _code_positions(pdf, lines):
    """Locate complete non-space line content in actual PDF character streams."""
    positions = []
    for line in lines:
        needle = "".join(line.split())
        matches = []
        for page_number, page in enumerate(pdf.pages):
            chars = [c for c in page.chars if not c["text"].isspace()]
            stream = "".join(c["text"] for c in chars)
            # Synthetic ASCII code has one character per PDF char record.
            assert all(len(c["text"]) == 1 for c in chars)
            start = stream.find(needle)
            if start >= 0:
                assert stream.find(needle, start + 1) == -1, f"Duplicated code: {line!r}"
                matched = chars[start:start + len(needle)]
                tops = [c["top"] for c in matched]
                assert max(tops) - min(tops) < 1, f"Code line wrapped: {line!r}, y={tops}"
                matches.append((page_number, matched[0]["x0"], median(tops),
                                median(c["x1"] - c["x0"] for c in matched)))
        assert len(matches) == 1, f"Code content missing or duplicated: {line!r}"
        positions.append(matches[0])
    return positions


@pytest.mark.parametrize(
    "language,profile,style",
    [("python", "default", "tango"),
     ("python", "manual", "pygments"),
     ("", "default", "tango")],
    ids=["highlighted-default-tango", "highlighted-manual-pygments", "plain-fence-control"],
)
def test_pdf_fenced_code_preserves_lines_blank_line_and_indent(
    make_project, monkeypatch, managed_pdf_tools, language, profile, style
):
    home = make_project(
        "language: en\ndocs_layout: per-article\n"
        f"export:\n  format:\n    code:\n      highlight: {style}\n"
    )
    layout = Layout(home, "per-article")
    snapshot = layout.docs_snapshot("code-layout", "1.0.0")
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    source = f"# Synthetic code layout\n\n```{language}\n{CODE}```\n".encode("utf-8")
    snapshot.write_bytes(source)
    freeze.record(layout.planning_home, layout.project_root, snapshot)
    monkeypatch.chdir(home.parent)
    try:
        # Keep normal export fidelity verification enabled.
        rc = export_cmd.run(["code-layout", "--version", "1.0.0", "--profile", profile])
    finally:
        assert snapshot.read_bytes() == source, "Export changed frozen source bytes"
    assert rc == 0, "Actual PDF export/fidelity verification failed"
    with managed_pdf_tools.open(layout.docs_export("code-layout", "1.0.0", "pdf")) as pdf:
        positions = _code_positions(pdf, [line for line in CODE.splitlines() if line])
    assert len({p[0] for p in positions}) == 1, "Short code block split across pages"
    ys = [p[2] for p in positions]
    gaps = [b - a for a, b in zip(ys, ys[1:])]
    xs = [p[1] for p in positions]
    errors = []
    if not all(gap > 1 for gap in gaps):
        errors.append(f"Separate source lines must have distinct increasing y coordinates: y={ys}, gaps={gaps}")
    normal_step = median([gaps[0], gaps[2], gaps[3]])
    if normal_step <= 1 or not 1.7 * normal_step <= gaps[1] <= 2.3 * normal_step:
        errors.append(f"One deliberate blank line must double the normal baseline gap: gaps={gaps}")
    advance = median(p[3] for p in positions)
    if max(xs[i] for i in (0, 1, 2, 4)) - min(xs[i] for i in (0, 1, 2, 4)) > 1:
        errors.append(f"Unindented lines must share their left edge: x={xs}")
    if abs((xs[3] - xs[2]) - 4 * advance) > advance * 0.6:
        errors.append(f"Four-space indentation must remain measurable: x={xs}, glyph advance={advance}")
    assert not errors, "\n".join(errors)
