"""docspec reference + docspec measure-fonts (Part B new commands).

Both are bootstrap-free (no project required) — mirror `version`. reference reads
the bundled docspec-cas pack's craft reference; measure-fonts reports rendered PDF font
sizes (soft-dep on pdfplumber).
"""

from __future__ import annotations

import pytest

from dspx.commands import measure_fonts as mf_cmd
from dspx.commands import reference as ref_cmd


# ── docspec reference ─────────────────────────────────────────────

def test_reference_registered():
    from dspx.commands import REGISTRY
    assert REGISTRY.get("reference") is ref_cmd
    assert REGISTRY.get("measure-fonts") is mf_cmd


def test_reference_index_lists_topics(capsys):
    """No topic → index of the bundled pack's craft topics."""
    assert ref_cmd.run([]) == 0
    out = capsys.readouterr().out
    assert "tikz" in out
    assert "latex-traps" in out


def test_reference_tikz_prints_idiom_library(capsys):
    assert ref_cmd.run(["tikz"]) == 0
    out = capsys.readouterr().out
    assert "dspxflow" in out          # the pre-loaded TikZ styles
    assert "tikzpicture" in out


def test_reference_latex_traps_prints_traps(capsys):
    assert ref_cmd.run(["latex-traps"]) == 0
    out = capsys.readouterr().out
    assert "NFSS" in out              # Trap 1
    assert "colortbl" in out          # Trap 2


def test_reference_unknown_topic_lists_available_nonzero(capsys):
    assert ref_cmd.run(["nope"]) == 2
    err = capsys.readouterr().err
    assert "tikz" in err              # lists what's available


def test_reference_pack_without_reference_is_advisory(tmp_path, capsys):
    """A --template pack that ships no reference.md → advisory message, exit 0."""
    pack = tmp_path / "minimal-pack"
    pack.mkdir()
    # resolve_template_dir validates required files; build a stub pack.
    from dspx import paths
    for f in paths.REQUIRED_TEMPLATE_FILES:
        (pack / f).write_text("stub", encoding="utf-8")
    for d in paths.REQUIRED_TEMPLATE_DIRS:
        (pack / d).mkdir(parents=True, exist_ok=True)
    assert ref_cmd.run(["--template", str(pack)]) == 0
    out = capsys.readouterr().out
    assert "craft" in out or "reference" in out.lower()


# ── docspec measure-fonts ─────────────────────────────────────────

def test_measure_fonts_missing_file_nonzero(capsys):
    assert mf_cmd.run(["does-not-exist.pdf"]) == 1
    err = capsys.readouterr().err
    assert "PDF" in err


def test_measure_fonts_soft_dep_missing(tmp_path, monkeypatch, capsys):
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")  # exists; we never parse it (dep missing first)
    monkeypatch.setattr(mf_cmd, "_have_pdfplumber", lambda: False)
    assert mf_cmd.run([str(pdf)]) == 1
    err = capsys.readouterr().err
    assert "pdfplumber" in err


def test_measure_fonts_bad_pages_nonzero(tmp_path, monkeypatch, capsys):
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    monkeypatch.setattr(mf_cmd, "_have_pdfplumber", lambda: True)
    # patch pdfplumber import path is unnecessary — bad --pages is caught before open
    assert mf_cmd.run([str(pdf), "--pages", "abc"]) == 1
    err = capsys.readouterr().err
    assert "page-number" in err
