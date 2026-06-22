"""docspec proof：PDF → PNG 逐頁渲圖（release 互動排版迴圈的眼睛）。

驗：頁數對、檔案產出、確定性（同 PDF 重渲產同檔）、版本/latest 對齊 export、
找不到 PDF 的明確提示、pypdfium2 缺的 soft-dep 降級。

PDF 來源＝export 的真產物（需 pandoc + 受控 TinyTeX(xelatex)，缺則 skip 重型測試）。
不需要外部相依的測試（解析、降級、缺 PDF）一律可跑。
"""

from __future__ import annotations

import pytest

from dspx import paths
from dspx.commands import export as export_cmd
from dspx.commands import proof as proof_cmd
from dspx.layout import Layout

_HAVE_PANDOC = export_cmd._pandoc_path() is not None
# xelatex ＋ 受控字型皆備才能真 build PDF（字型已移出 wheel；未 setup → skip）。
_HAVE_XELATEX = export_cmd._xelatex_path() is not None and paths.resolve_fonts_dir() is not None
_HAVE_PDFIUM = proof_cmd._have_pypdfium2()

_SNAP = """# 校樣文件

第一頁的中文段落，閾值每秒 100 Hz。
Mixed English sentence survives.

\\newpage

## 第二節

| 項目 | 值 |
|---|---|
| 頻率 | 100 Hz |
"""


def _setup(make_project, *, version: str = "1.0.0", article: str = "g"):
    home = make_project()  # docs_layout: per-article
    layout = Layout(home, "per-article")
    snap = layout.docs_snapshot(article, version)
    snap.parent.mkdir(parents=True, exist_ok=True)
    snap.write_text(_SNAP, encoding="utf-8")
    return home, layout


def _export(layout, monkeypatch, home, *, latest: bool = False, article: str = "g"):
    """跑真 export 產一份 PDF（需 pandoc+xelatex）。回 PDF 路徑。"""
    monkeypatch.chdir(home.parent)
    if latest:
        p = layout.docs_latest(article)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(_SNAP, encoding="utf-8")
        assert export_cmd.run([article, "--format", "pdf", "--latest"]) == 0
        return layout.docs_export(article, "latest", "pdf")
    assert export_cmd.run([article, "--format", "pdf"]) == 0
    return layout.docs_export(article, "1.0.0", "pdf")


# ── 渲圖：頁數對、檔案產出 ────────────────────────────────────────

@pytest.mark.skipif(not (_HAVE_PANDOC and _HAVE_XELATEX), reason="proof 重型測試需要 pandoc+xelatex")
@pytest.mark.skipif(not _HAVE_PDFIUM, reason="proof 需要 pypdfium2")
def test_proof_renders_pages(make_project, monkeypatch, capsys):
    home, layout = _setup(make_project)
    pdf = _export(layout, monkeypatch, home)
    assert pdf.is_file()

    assert proof_cmd.run(["g"]) == 0
    out_dir = proof_cmd._proof_dir(layout, "g")
    pngs = sorted(out_dir.glob("page_*.png"))
    assert pngs, "未產出任何 PNG"
    # 每張都是非空 PNG（PNG magic）
    for p in pngs:
        assert p.stat().st_size > 0
        assert p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    # 路徑清單印出來供 agent 讀
    out = capsys.readouterr().out
    assert "page_01.png" in out

    # 頁數與 PDF 實際頁數一致
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(str(pdf))
    try:
        assert len(pngs) == len(doc)
    finally:
        doc.close()


@pytest.mark.skipif(not (_HAVE_PANDOC and _HAVE_XELATEX), reason="proof 重型測試需要 pandoc+xelatex")
@pytest.mark.skipif(not _HAVE_PDFIUM, reason="proof 需要 pypdfium2")
def test_proof_deterministic(make_project, monkeypatch):
    """同 PDF 重渲 → 同 PNG bytes（確定性）；重渲清空舊頁、不累積。"""
    home, layout = _setup(make_project)
    _export(layout, monkeypatch, home)
    out_dir = proof_cmd._proof_dir(layout, "g")

    assert proof_cmd.run(["g"]) == 0
    first = {p.name: p.read_bytes() for p in sorted(out_dir.glob("page_*.png"))}
    assert proof_cmd.run(["g"]) == 0
    second = {p.name: p.read_bytes() for p in sorted(out_dir.glob("page_*.png"))}
    assert first.keys() == second.keys()
    for name in first:
        assert first[name] == second[name], f"同 PDF 重渲 {name} 不一致"


@pytest.mark.skipif(not (_HAVE_PANDOC and _HAVE_XELATEX), reason="proof 重型測試需要 pandoc+xelatex")
@pytest.mark.skipif(not _HAVE_PDFIUM, reason="proof 需要 pypdfium2")
def test_proof_output_never_in_archive(make_project, monkeypatch):
    home, layout = _setup(make_project)
    _export(layout, monkeypatch, home)
    assert proof_cmd.run(["g"]) == 0
    out_dir = proof_cmd._proof_dir(layout, "g")
    assert "exports" in out_dir.parts
    assert "archive" not in out_dir.parts


@pytest.mark.skipif(not (_HAVE_PANDOC and _HAVE_XELATEX), reason="proof 重型測試需要 pandoc+xelatex")
@pytest.mark.skipif(not _HAVE_PDFIUM, reason="proof 需要 pypdfium2")
def test_proof_latest(make_project, monkeypatch):
    home, layout = _setup(make_project)
    _export(layout, monkeypatch, home, latest=True)
    assert proof_cmd.run(["g", "--latest"]) == 0
    assert sorted(proof_cmd._proof_dir(layout, "g").glob("page_*.png"))


# ── soft-dep 降級（無需外部相依）──────────────────────────────────

def test_proof_degrades_when_pdfium_missing(make_project, monkeypatch, capsys):
    home, layout = _setup(make_project)
    monkeypatch.chdir(home.parent)
    monkeypatch.setattr(proof_cmd, "_have_pypdfium2", lambda: False)
    assert proof_cmd.run(["g"]) == 1
    err = capsys.readouterr().err
    assert "pypdfium2" in err


# ── 找不到 PDF → 提示先 export（無需外部相依）─────────────────────

def test_proof_no_pdf_hints_export(make_project, monkeypatch, capsys):
    home, layout = _setup(make_project)  # 有快照、但沒跑過 export → 無 PDF
    monkeypatch.chdir(home.parent)
    if not _HAVE_PDFIUM:
        # 無 pypdfium2 時這條會先卡在 soft-dep；仍能驗回 1
        assert proof_cmd.run(["g"]) == 1
        return
    assert proof_cmd.run(["g"]) == 1
    err = capsys.readouterr().err
    assert "docspec export" in err


def test_proof_no_snapshot_errors(make_project, monkeypatch):
    home = make_project()
    monkeypatch.chdir(home.parent)
    # 連快照都沒有 → 明確錯誤
    assert proof_cmd.run(["g"]) == 1


def test_proof_bad_version_errors(make_project, monkeypatch):
    home, _ = _setup(make_project)
    monkeypatch.chdir(home.parent)
    if not _HAVE_PDFIUM:
        return
    assert proof_cmd.run(["g", "--version", "not-semver"]) == 1
