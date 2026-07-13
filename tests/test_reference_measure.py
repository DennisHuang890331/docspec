"""docspec reference + docspec measure-fonts (Part B new commands).

Both are bootstrap-free (no project required) — mirror `version`. reference reads
the active template pack's craft reference (the bundled Typst pack, or a --template
pack); measure-fonts reports rendered PDF font sizes (soft-dep on pdfplumber).
"""

from __future__ import annotations

import pytest

from dspx.commands.export import _measure_fonts as mf_cmd
from dspx.commands.projection import reference as ref_cmd


# ── docspec reference ─────────────────────────────────────────────

def test_reference_registered():
    from dspx.commands import REGISTRY
    assert REGISTRY.get("reference") is ref_cmd
    # measure-fonts folded into `proof` (font diagnostics); no longer a top-level command
    assert "measure-fonts" not in REGISTRY


def test_reference_bundled_pack_is_advisory_or_lists(capsys):
    """Bundled Typst pack → exit 0 (it ships no craft reference today → advisory;
    if one is added later, an index is still a clean exit 0)."""
    assert ref_cmd.run([]) == 0


def _pack_with_reference(tmp_path, body):
    pack = tmp_path / "pack"
    pack.mkdir()
    (pack / "reference.md").write_text(body, encoding="utf-8")
    return pack


def test_reference_template_pack_lists_and_prints_topics(tmp_path, capsys):
    """A --template pack with a reference.md → index lists its topics; a topic prints."""
    pack = _pack_with_reference(
        tmp_path,
        "preamble ignored\n<!-- topic: tables -->\n# Tables\nuse a grid.\n"
        "<!-- topic: figures -->\n# Figures\nplace assets.\n")
    assert ref_cmd.run(["--template", str(pack)]) == 0
    out = capsys.readouterr().out
    assert "tables" in out and "figures" in out

    assert ref_cmd.run(["tables", "--template", str(pack)]) == 0
    assert "use a grid." in capsys.readouterr().out


def test_reference_unknown_topic_lists_available_nonzero(tmp_path, capsys):
    pack = _pack_with_reference(
        tmp_path, "<!-- topic: tables -->\n# Tables\nuse a grid.\n")
    assert ref_cmd.run(["nope", "--template", str(pack)]) == 2
    err = capsys.readouterr().err
    assert "tables" in err              # lists what's available


def test_reference_template_missing_dir_errors(tmp_path, capsys):
    assert ref_cmd.run(["--template", str(tmp_path / "nope")]) == 1
    assert "does not exist" in capsys.readouterr().err


def test_reference_pack_without_reference_is_advisory(tmp_path, capsys, monkeypatch):
    """A --template pack that ships no reference.md, and no bundled writing reference either →
    advisory message, exit 0."""
    monkeypatch.setattr(ref_cmd.paths, "bundled_reference_dir", lambda: None)
    pack = tmp_path / "minimal-pack"
    pack.mkdir()
    assert ref_cmd.run(["--template", str(pack)]) == 0
    out = capsys.readouterr().out
    assert "craft" in out or "reference" in out.lower()


# ── docspec reference: docspec-bundled writing topics (independent of template pack) ──

def _writing_dir(tmp_path, body):
    d = tmp_path / "writing-ref"
    d.mkdir()
    (d / "writing.md").write_text(body, encoding="utf-8")
    return d


def test_reference_writing_topics_available_regardless_of_pack(tmp_path, monkeypatch, capsys):
    """docspec-bundled writing-zh/writing-en topics show up in the index and print, even when
    the active template pack ships no craft reference at all."""
    wdir = _writing_dir(
        tmp_path,
        "<!-- topic: writing-zh -->\n# 中文\n動詞當家。\n"
        "<!-- topic: writing-en -->\n# English\nActive voice.\n")
    monkeypatch.setattr(ref_cmd.paths, "bundled_reference_dir", lambda: wdir)
    pack = tmp_path / "minimal-pack"
    pack.mkdir()

    assert ref_cmd.run(["--template", str(pack)]) == 0
    out = capsys.readouterr().out
    assert "writing-zh" in out and "writing-en" in out

    assert ref_cmd.run(["writing-zh", "--template", str(pack)]) == 0
    assert "動詞當家" in capsys.readouterr().out


def test_reference_writing_and_pack_topics_merge(tmp_path, monkeypatch, capsys):
    """Bundled writing topics and a template pack's own craft topics coexist in one index."""
    wdir = _writing_dir(tmp_path, "<!-- topic: writing-en -->\n# English\nActive voice.\n")
    monkeypatch.setattr(ref_cmd.paths, "bundled_reference_dir", lambda: wdir)
    pack = _pack_with_reference(tmp_path, "<!-- topic: tables -->\n# Tables\nuse a grid.\n")

    assert ref_cmd.run(["--template", str(pack)]) == 0
    out = capsys.readouterr().out
    assert "writing-en" in out and "tables" in out

    assert ref_cmd.run(["tables", "--template", str(pack)]) == 0
    assert "use a grid." in capsys.readouterr().out


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
