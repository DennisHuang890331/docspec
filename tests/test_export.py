"""docspec export：byte-lock（內容只動呈現）、soft-dep 降級、輸出路徑、凍結快照輸入。

Phase C 定版＝docspec-cas 單欄 class（改自 Elsevier cas-sc）+ 受控 TinyTeX(xelatex)（typst/docx 路已退場）。
軟相依：pandoc（系統或 pypandoc_binary）＋ xelatex（受控 TinyTeX；DOCSPEC_TINYTEX/dev /tmp/ttx）。
缺工具的轉檔斷言 skip。byte-lock 證明＝抽回 PDF 文字後與源快照做 **content-token 多重集** 比對
（NFC＋只留拉丁詞/個別 CJK 字/數字），對表格重排穩健、又能抓出任何內容增刪。
"""

from __future__ import annotations

import pytest

from dspx import paths
from dspx.commands import export as export_cmd
from dspx.layout import Layout

_HAVE_PANDOC = export_cmd._pandoc_path() is not None
# 受控 TinyTeX(xelatex) ＋ 受控字型（data_dir/fonts 或 dev 後備）皆備才跑 PDF build。
# 字型已移出 wheel：fresh 環境未跑 `docspec setup` 時 skip（非 fail）。
_HAVE_XELATEX = export_cmd._xelatex_path() is not None and paths.resolve_fonts_dir() is not None
pytestmark = pytest.mark.skipif(not _HAVE_PANDOC, reason="export 需要 pandoc")

# 中文＋英文＋數字＋表格的定稿快照（含 byte-lock 驗收關鍵 token；首行 H1＝文件標題）
_SNAP = """# 概覽文件

這是限流保護後端的中文段落，閾值是每秒 100 Hz，比率 3.84，關鍵詞 MUST NOT 必須保留。
Mixed English sentence also survives the round trip.

## 細節

| 項目 | 值 |
|---|---|
| 頻率 | 100 Hz |
| 比率 | 3.84 |
"""


# byte-lock 比對邏輯已抽成共用函式（dspx.paths.content_token_multiset），
# export 指令的 runtime 驗證與本測試共用同一套。此 alias 維持既有測試呼叫點。
_content_chars = paths.content_token_multiset


def _setup(make_project, body: str = _SNAP, *, version: str = "1.0.0", article: str = "g"):
    home = make_project()  # docs_layout: per-article
    layout = Layout(home, "per-article")
    snap = layout.docs_snapshot(article, version)
    snap.parent.mkdir(parents=True, exist_ok=True)
    snap.write_text(body, encoding="utf-8")
    return home, layout


# ── 標題抽取（H1 → \title，移出正文）──────────────────────────────

def test_split_title_body_extracts_h1():
    title, body = export_cmd._split_title_body(_SNAP, fallback_title="g")
    assert title == "概覽文件"
    # H1 行不再出現在正文（避免與 before.tex \title 重複）
    assert "# 概覽文件" not in body
    # 其餘內容保留
    assert "限流保護後端" in body and "## 細節" in body


def test_split_title_body_strips_frontmatter_and_falls_back():
    text = "---\narticle: g\nversion: 1\n---\n\n沒有標題的正文，直接是內容。\n"
    title, body = export_cmd._split_title_body(text, fallback_title="g")
    assert title == "g"  # 無 H1 → fallback 文章名
    assert "article: g" not in body and "沒有標題的正文" in body


# ── byte-lock（PDF）───────────────────────────────────────────────

def test_export_pdf_byte_lock_cjk(make_project, monkeypatch):
    if not _HAVE_XELATEX:
        pytest.skip("PDF 需要受控 TinyTeX(xelatex)")
    pdfplumber = pytest.importorskip("pdfplumber")
    home, layout = _setup(make_project)
    monkeypatch.chdir(home.parent)
    assert export_cmd.run(["g", "--format", "pdf"]) == 0
    out = layout.docs_export("g", "1.0.0", "pdf")
    assert out.is_file()
    with pdfplumber.open(str(out)) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    got = _content_chars(text)
    src = _content_chars(layout.docs_snapshot("g", "1.0.0").read_text(encoding="utf-8"))
    # 中文沒豆腐＝CJK 字在；數字/英文字母都在（逐字元）
    for needle in ["概", "覽", "限", "流", "閾", "1", "0", "H", "z", "M", "U", "S", "T", "N", "O"]:
        assert got.get(needle, 0) >= 1, f"PDF 抽回缺字元 {needle!r}（中文豆腐或內容掉）"
    # 源快照所有內容字元都出現在 PDF（無內容遺失；PDF 抽取可能多換行字元故不強求反向）
    missing = src - got
    assert not missing, f"PDF 遺失內容字元：{missing}"


# ── soft-dep 降級 ─────────────────────────────────────────────────

def test_export_degrades_when_xelatex_missing(make_project, monkeypatch, capsys):
    home, layout = _setup(make_project)
    monkeypatch.chdir(home.parent)
    monkeypatch.setattr(export_cmd, "_xelatex_path", lambda: None)
    # 缺 xelatex → 不 crash、回 1、印安裝指引、不留半成品 PDF
    assert export_cmd.run(["g", "--format", "pdf"]) == 1
    assert not layout.docs_export("g", "1.0.0", "pdf").is_file()
    err = capsys.readouterr().err
    # 模型 A：缺排版引擎 → 明確叫跑 `docspec setup`（一次性下載受控引擎＋字型）
    assert "TinyTeX" in err and "docspec setup" in err


def test_export_degrades_when_fonts_missing(make_project, monkeypatch, capsys):
    home, layout = _setup(make_project)
    monkeypatch.chdir(home.parent)
    # 引擎在、但受控字型缺 → 模型 A 明確叫跑 `docspec setup`、回 1、不留半成品
    monkeypatch.setattr(export_cmd, "_xelatex_path", lambda: paths.Path("xelatex"))
    monkeypatch.setattr(export_cmd, "_pandoc_path", lambda: "pandoc")
    monkeypatch.setattr(paths, "resolve_fonts_dir", lambda *a, **k: None)
    assert export_cmd.run(["g", "--format", "pdf"]) == 1
    assert not layout.docs_export("g", "1.0.0", "pdf").is_file()
    err = capsys.readouterr().err
    assert "fonts" in err and "docspec setup" in err


def test_export_degrades_when_pandoc_missing(make_project, monkeypatch, capsys):
    home, layout = _setup(make_project)
    monkeypatch.chdir(home.parent)
    monkeypatch.setattr(export_cmd, "_pandoc_path", lambda: None)
    assert export_cmd.run(["g", "--format", "pdf"]) == 1
    err = capsys.readouterr().err
    assert "pandoc" in err


# ── pandoc 格式設定 ────────────────────────────────────────────────

def test_pandoc_from_disables_yaml_metadata_block():
    # 台中港風格文件用 --- 當 section divider；yaml_metadata_block 必須關掉
    # 否則 pandoc 把 --- ... --- 之間的散文當 YAML 解析→失敗。
    assert "-yaml_metadata_block" in export_cmd._PANDOC_FROM


def test_pandoc_from_disables_citations():
    # @token（MPE @import / @提及）不被當成引用文獻
    assert "-citations" in export_cmd._PANDOC_FROM


# ── 輸出路徑：絕不在 archive 下 ───────────────────────────────────

def test_export_output_never_in_archive(make_project, monkeypatch):
    if not _HAVE_XELATEX:
        pytest.skip("PDF 需要受控 TinyTeX(xelatex)")
    home, layout = _setup(make_project)
    monkeypatch.chdir(home.parent)
    export_cmd.run(["g", "--format", "pdf"])
    out = layout.docs_export("g", "1.0.0", "pdf")
    assert "exports" in out.parts
    assert "archive" not in out.parts
    # docs/ 下唯一 archive 內容＝我們放的源快照，無 export 產物滲入
    for p in (layout.docs_dir).rglob("*"):
        if p.is_file() and "archive" in p.parts:
            assert p.suffix == ".md", f"archive 下出現非 md：{p}"


# ── 凍結快照輸入解析 ──────────────────────────────────────────────

def test_export_no_snapshot_errors(make_project, monkeypatch):
    home = make_project()
    monkeypatch.chdir(home.parent)
    # 沒任何發行快照 → 明確錯誤（不靜默退 latest）
    assert export_cmd.run(["g", "--format", "pdf"]) == 1


def test_export_bad_version_errors(make_project, monkeypatch):
    home, _ = _setup(make_project)
    monkeypatch.chdir(home.parent)
    assert export_cmd.run(["g", "--format", "pdf", "--version", "9.9.9"]) == 1
    assert export_cmd.run(["g", "--format", "pdf", "--version", "not-semver"]) == 1


# ── export-safety lint（Ve）：匯出問題前移成事前 lint ──────────────

def _write_latest(layout, article: str, body: str):
    p = layout.docs_latest(article)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")


def test_lint_ve1_dead_anchor_link(make_project):
    from dspx.lint import _lint_export_safety
    home = make_project()
    layout = Layout(home, "per-article")
    # 標題「§7.5 主動安全監控」slug=主動安全監控；連結手寫 #section-7-5 對不上→Ve1
    _write_latest(layout, "g",
        "# 文件\n\n## §7.5 主動安全監控\n\n見 [前文](#section-7-5) 與 [概覽](#概覽)。\n\n## 概覽\n\n內容。\n")
    findings = _lint_export_safety(layout, ["g"])
    ve1 = [f for f in findings if f.rule == "Ve1"]
    assert len(ve1) == 1 and "section-7-5" in ve1[0].detail   # 死連結抓到
    assert all("概覽" not in f.detail for f in ve1)            # 命中標題的連結不誤報


def test_lint_ve1_ignores_links_in_code(make_project):
    from dspx.lint import _lint_export_safety
    home = make_project()
    layout = Layout(home, "per-article")
    # code fence 內的 ](#x) 是內容範例，不該誤報
    _write_latest(layout, "g",
        "# 文件\n\n## 真章節\n\n```\n參考 [x](#不存在的錨點)\n```\n\n正文 [本節](#真章節)。\n")
    findings = _lint_export_safety(layout, ["g"])
    assert [f for f in findings if f.rule == "Ve1"] == []


def test_lint_ve2_mpe_import(make_project):
    from dspx.lint import _lint_export_safety
    home = make_project()
    layout = Layout(home, "per-article")
    _write_latest(layout, "g", '# 文件\n\n@import "revision_history/x.md"\n\n## 章\n\n內容。\n')
    findings = _lint_export_safety(layout, ["g"])
    assert [f for f in findings if f.rule == "Ve2"]


def test_lint_ve_clean_doc_no_findings(make_project):
    from dspx.lint import _lint_export_safety
    home = make_project()
    layout = Layout(home, "per-article")
    _write_latest(layout, "g",
        "# 文件\n\n## 概覽 (Overview)\n\n見 [概覽](#概覽-overview)。\n\n## 細節\n\n內容。\n")
    assert _lint_export_safety(layout, ["g"]) == []


def test_export_latest_preview(make_project, monkeypatch):
    if not _HAVE_XELATEX:
        pytest.skip("PDF 需要受控 TinyTeX(xelatex)")
    home, layout = _setup(make_project)
    latest = layout.docs_latest("g")
    latest.parent.mkdir(parents=True, exist_ok=True)
    latest.write_text(_SNAP, encoding="utf-8")
    monkeypatch.chdir(home.parent)
    assert export_cmd.run(["g", "--format", "pdf", "--latest"]) == 0
    assert layout.docs_export("g", "latest", "pdf").is_file()


# ── mermaid 區塊 → 可見佔位框（lua filter；不再 dump 成原始碼）────────────

def _pandoc_to_latex(body_md: str) -> str:
    """跑真 pandoc＋隨包 docspec-tables.lua，回產出的 LaTeX 片段（不需 xelatex）。

    驗 lua filter 的 CodeBlock(mermaid) handler：mermaid → tcolorbox 佔位框、
    一般 code block 不被攔（維持 pandoc Shaded/verbatim 行為）。
    """
    import shutil
    import subprocess
    import tempfile
    from pathlib import Path

    pandoc = export_cmd._pandoc_path()
    tdir = export_cmd._template_dir()
    assert tdir is not None, "找不到隨包 docspec-cas 模板"
    with tempfile.TemporaryDirectory(prefix="dspx_lua_") as td:
        build = Path(td)
        shutil.copy2(tdir / "docspec-tables.lua", build / "docspec-tables.lua")
        (build / "doc.md").write_text(body_md, encoding="utf-8")
        out = subprocess.run(
            [pandoc, "doc.md", "-f", export_cmd._PANDOC_FROM, "-t", "latex",
             "--syntax-highlighting=tango",
             "--lua-filter=docspec-tables.lua", "-o", "doc.tex"],
            cwd=str(build), check=True, capture_output=True, text=True,
        )
        _ = out
        return (build / "doc.tex").read_text(encoding="utf-8")


def test_mermaid_block_becomes_visible_placeholder():
    """mermaid code block → tcolorbox 佔位框（含標籤＋\\footnotesize 收原始碼），
    不再整塊 dump 成原始碼 verbatim。"""
    md = (
        "## 圖\n\n"
        "```mermaid\n"
        "stateDiagram-v2\n"
        "    [*] --> 離線\n"
        "    離線 --> 上線: 連線成功\n"
        "```\n"
    )
    tex = _pandoc_to_latex(md)
    # 渲成佔位框（tcolorbox）＋醒目標籤，而非 pandoc 預設的 Shaded/Highlighting/verbatim。
    assert "\\begin{tcolorbox}" in tex
    assert "Mermaid 圖" in tex and "release 時由 agent 轉 TikZ" in tex
    # mermaid 原始碼仍可見（收在框內 Verbatim 小字、供 agent 翻譯時讀）
    assert "stateDiagram-v2" in tex
    # 沒有被當成語法高亮 code（pandoc 的 Highlighting/Shaded 環境）
    assert "Highlighting" not in tex


def test_non_mermaid_codeblock_unaffected():
    """一般語言 code block 不被 mermaid handler 攔——維持 pandoc 既有渲染
    （Shaded/Highlighting 語法高亮），絕不變成佔位框。"""
    md = (
        "## 程式\n\n"
        "```python\n"
        "def f(x):\n"
        "    return x + 1\n"
        "```\n"
    )
    tex = _pandoc_to_latex(md)
    # python code 走 pandoc 既有路徑：有語法高亮環境、無 mermaid 佔位框
    assert "tcolorbox" not in tex
    assert "Mermaid 圖" not in tex
    assert ("Highlighting" in tex) or ("Shaded" in tex) or ("verbatim" in tex.lower())


# ── #1 --template / --fonts 旗標：解析、覆寫生效、缺檔報錯 ─────────────

def _copy_bundled_template(dst):
    """把內建 docspec-cas 模板包整夾 copy 到 dst（供 --template 覆寫測試當「使用者模板包」）。"""
    import shutil
    src = paths.bundled_template_dir()
    assert src is not None
    shutil.copytree(str(src), str(dst))
    return dst


def test_resolve_template_override_used_when_given(tmp_path):
    # 給合法的使用者模板包夾（複製內建、結構齊全）→ 解析回該夾、不退回內建
    user_tpl = _copy_bundled_template(tmp_path / "myjournal")
    got = paths.resolve_template_dir(str(user_tpl))
    assert got == user_tpl
    # 不給 → 退回內建
    assert paths.resolve_template_dir(None) == paths.bundled_template_dir()


def test_resolve_template_override_missing_dir_errors(tmp_path):
    with pytest.raises(paths.AssetError) as ei:
        paths.resolve_template_dir(str(tmp_path / "nope"))
    assert "does not exist" in str(ei.value)


def test_resolve_template_override_missing_file_errors(tmp_path):
    # 結構不完整（缺 preamble.tex）→ AssetError 列出缺檔
    user_tpl = _copy_bundled_template(tmp_path / "broken")
    (user_tpl / "preamble.tex").unlink()
    with pytest.raises(paths.AssetError) as ei:
        paths.resolve_template_dir(str(user_tpl))
    assert "preamble.tex" in str(ei.value)


def test_resolve_template_override_missing_pandoc_data_dir_errors(tmp_path):
    import shutil
    user_tpl = _copy_bundled_template(tmp_path / "nodata")
    shutil.rmtree(str(user_tpl / "pandoc-data"))
    with pytest.raises(paths.AssetError) as ei:
        paths.resolve_template_dir(str(user_tpl))
    assert "pandoc-data" in str(ei.value)


def _make_fonts_dir(dst):
    """造一個含全部必要字型檔名的夾（內容為空 stub；只測解析/覆寫，不真渲染）。"""
    dst.mkdir(parents=True, exist_ok=True)
    for f in paths.REQUIRED_FONT_FILES:
        (dst / f).write_bytes(b"\x00")
    return dst


def test_resolve_fonts_override_used_when_given(tmp_path):
    user_fonts = _make_fonts_dir(tmp_path / "myfonts")
    assert paths.resolve_fonts_dir(str(user_fonts)) == user_fonts


def test_resolve_fonts_override_missing_dir_errors(tmp_path):
    with pytest.raises(paths.AssetError) as ei:
        paths.resolve_fonts_dir(str(tmp_path / "nope"))
    assert "does not exist" in str(ei.value)


def test_resolve_fonts_override_missing_font_errors(tmp_path):
    user_fonts = _make_fonts_dir(tmp_path / "partial")
    (user_fonts / paths.REQUIRED_FONT_FILES[0]).unlink()
    with pytest.raises(paths.AssetError) as ei:
        paths.resolve_fonts_dir(str(user_fonts))
    assert paths.REQUIRED_FONT_FILES[0] in str(ei.value)


def test_export_template_flag_missing_dir_errors(make_project, monkeypatch, capsys):
    """export --template 指不存在的夾 → 清楚報錯、非零、不 crash（不需 xelatex/pandoc）。"""
    home, _ = _setup(make_project)
    monkeypatch.chdir(home.parent)
    monkeypatch.setattr(export_cmd, "_pandoc_path", lambda: "pandoc")
    monkeypatch.setattr(export_cmd, "_xelatex_path", lambda: paths.Path("xelatex"))
    rc = export_cmd.run(["g", "--format", "pdf", "--template", str(home / "missing_tpl")])
    assert rc == 1
    assert "does not exist" in capsys.readouterr().err


def test_export_fonts_flag_missing_font_errors(make_project, monkeypatch, capsys, tmp_path):
    """export --fonts 指缺字型的夾 → 清楚報錯、非零、不 crash。"""
    home, _ = _setup(make_project)
    monkeypatch.chdir(home.parent)
    monkeypatch.setattr(export_cmd, "_pandoc_path", lambda: "pandoc")
    monkeypatch.setattr(export_cmd, "_xelatex_path", lambda: paths.Path("xelatex"))
    partial = _make_fonts_dir(tmp_path / "partial")
    (partial / paths.REQUIRED_FONT_FILES[0]).unlink()
    rc = export_cmd.run(["g", "--format", "pdf", "--fonts", str(partial)])
    assert rc == 1
    err = capsys.readouterr().err
    assert "font" in err and paths.REQUIRED_FONT_FILES[0] in err


def test_export_fonts_flag_overrides_build(make_project, monkeypatch):
    """--fonts 真的把使用者字型夾餵進 build：攔 _build_pdf 斷言 fonts_src＝給的夾。"""
    if not _HAVE_XELATEX:
        pytest.skip("PDF 需要受控 TinyTeX(xelatex)")
    home, layout = _setup(make_project)
    monkeypatch.chdir(home.parent)
    # 用真字型夾複製出一份當「使用者字型夾」，確保 build 能成
    real_fonts = paths.resolve_fonts_dir()
    assert real_fonts is not None
    import shutil
    user_fonts = home.parent / "user_fonts"
    shutil.copytree(str(real_fonts), str(user_fonts))

    seen = {}
    orig = export_cmd._build_pdf

    def spy(pandoc, xelatex, template_dir, fonts_src, title, body_md, out, **kw):
        seen["fonts_src"] = fonts_src
        seen["template_dir"] = template_dir
        return orig(pandoc, xelatex, template_dir, fonts_src, title, body_md, out, **kw)

    monkeypatch.setattr(export_cmd, "_build_pdf", spy)
    assert export_cmd.run(["g", "--format", "pdf", "--fonts", str(user_fonts)]) == 0
    assert seen["fonts_src"] == user_fonts
    # 沒給 --template → 仍用內建
    assert seen["template_dir"] == paths.bundled_template_dir()


# ── #3 export runtime byte-lock 驗證 ──────────────────────────────────

def test_verify_byte_lock_passes_on_consistent(monkeypatch):
    """PDF 抽回文字含源全部內容 token → byte-lock 通過（回 0、靜默）。"""
    body = "限流保護後端，閾值每秒 100 Hz，MUST NOT 保留。Mixed English."

    class _FakePage:
        def __init__(self, t): self._t = t
        @property
        def chars(self): return [{"text": c} for c in self._t]

    class _FakePDF:
        def __init__(self, t): self._t = t
        def __enter__(self): return self
        def __exit__(self, *a): return False
        @property
        def pages(self): return [_FakePage(self._t)]

    import types
    fake = types.SimpleNamespace(open=lambda p: _FakePDF(body))
    monkeypatch.setitem(__import__("sys").modules, "pdfplumber", fake)
    assert export_cmd._verify_byte_lock(paths.Path("x.pdf"), body) == 0


def test_verify_byte_lock_red_on_tampered(monkeypatch, capsys):
    """PDF 抽回文字漏了源的字（人工竄改：拔掉「閾」「Hz」）→ 紅燈、回非零、印缺 token。"""
    body = "限流保護後端，閾值每秒 100 Hz，MUST NOT 保留。"
    # 模擬轉檔動到內容：PDF 文字層缺「閾」「H」「z」
    tampered = "限流保護後端，值每秒 100 ，MUST NOT 保留。"

    class _FakePage:
        def __init__(self, t): self._t = t
        @property
        def chars(self): return [{"text": c} for c in self._t]

    class _FakePDF:
        def __init__(self, t): self._t = t
        def __enter__(self): return self
        def __exit__(self, *a): return False
        @property
        def pages(self): return [_FakePage(self._t)]

    import types
    fake = types.SimpleNamespace(open=lambda p: _FakePDF(tampered))
    monkeypatch.setitem(__import__("sys").modules, "pdfplumber", fake)
    assert export_cmd._verify_byte_lock(paths.Path("x.pdf"), body) == 1
    err = capsys.readouterr().err
    assert "render fidelity" in err
    assert "閾" in err  # 缺的 CJK 樣本有印


def test_verify_byte_lock_ack_passes_despite_cjk_loss(monkeypatch, capsys):
    """--ack：CJK 缺仍印報告（含 page/context）但回 0（已 proof 複判）。"""
    body = "限流保護後端，閾值每秒 100 Hz。"
    tampered = "限流保護後端，值每秒 100 Hz。"   # 拔掉「閾」

    class _FakePage:
        def __init__(self, t): self._t = t
        @property
        def chars(self): return [{"text": c} for c in self._t]

    class _FakePDF:
        def __init__(self, t): self._t = t
        def __enter__(self): return self
        def __exit__(self, *a): return False
        @property
        def pages(self): return [_FakePage(self._t)]

    import types
    monkeypatch.setitem(__import__("sys").modules, "pdfplumber",
                        types.SimpleNamespace(open=lambda p: _FakePDF(tampered)))
    assert export_cmd._verify_byte_lock(paths.Path("x.pdf"), body, "art", ack=True) == 0
    err = capsys.readouterr().err
    assert "閾" in err and "--ack" in err


def test_verify_byte_lock_latin_only_loss_is_informational(monkeypatch, capsys):
    """拉丁/數字差異＝informational：回 0（不再 5% 硬容差 fail）。"""
    body = "中文都在。" + "ABCDEFGHIJ" * 5     # 大量拉丁
    tampered = "中文都在。" + "ABCDEFGHI" * 5  # 每組少一個拉丁字（>10% 缺）

    class _FakePage:
        def __init__(self, t): self._t = t
        @property
        def chars(self): return [{"text": c} for c in self._t]

    class _FakePDF:
        def __init__(self, t): self._t = t
        def __enter__(self): return self
        def __exit__(self, *a): return False
        @property
        def pages(self): return [_FakePage(self._t)]

    import types
    monkeypatch.setitem(__import__("sys").modules, "pdfplumber",
                        types.SimpleNamespace(open=lambda p: _FakePDF(tampered)))
    assert export_cmd._verify_byte_lock(paths.Path("x.pdf"), body) == 0   # 拉丁缺不 fail
    assert "informational" in capsys.readouterr().err


def test_verify_byte_lock_soft_dep_when_pdfplumber_missing(monkeypatch, capsys):
    """pdfplumber 缺 → 印提示、跳過驗證但回 0（PDF 仍出，不 crash）。"""
    import builtins
    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name == "pdfplumber":
            raise ImportError("no pdfplumber")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert export_cmd._verify_byte_lock(paths.Path("x.pdf"), "內容") == 0
    assert "pdfplumber" in capsys.readouterr().err


def test_export_no_verify_skips_check(make_project, monkeypatch):
    """--no-verify → 不呼叫 _verify_byte_lock（即使一致也跳過）。"""
    if not _HAVE_XELATEX:
        pytest.skip("PDF 需要受控 TinyTeX(xelatex)")
    home, layout = _setup(make_project)
    monkeypatch.chdir(home.parent)
    called = {"n": 0}
    monkeypatch.setattr(export_cmd, "_verify_byte_lock",
                        lambda *a, **k: called.__setitem__("n", called["n"] + 1) or 0)
    assert export_cmd.run(["g", "--format", "pdf", "--no-verify"]) == 0
    assert called["n"] == 0
    assert layout.docs_export("g", "1.0.0", "pdf").is_file()


def test_export_verify_red_returns_nonzero(make_project, monkeypatch):
    """預設驗：_verify_byte_lock 回非零（內容被動到）→ export 回非零。"""
    if not _HAVE_XELATEX:
        pytest.skip("PDF 需要受控 TinyTeX(xelatex)")
    home, layout = _setup(make_project)
    monkeypatch.chdir(home.parent)
    monkeypatch.setattr(export_cmd, "_verify_byte_lock", lambda *a, **k: 1)
    assert export_cmd.run(["g", "--format", "pdf"]) == 1


# ── C2 逃生口 gate：內建模板包竄改偵測 ────────────────────────────────

def _stub_pack(tmp_path):
    pack = tmp_path / "pack"
    pack.mkdir()
    (pack / "preamble.tex").write_text("base content", encoding="utf-8")
    (pack / "before.tex").write_text("title block", encoding="utf-8")
    (pack / "fonts").mkdir()
    (pack / "fonts" / "x.ttf").write_text("not hashed", encoding="utf-8")
    import json
    baseline = paths.pack_content_hashes(pack)
    (pack / paths.PACK_HASHES_FILE).write_text(json.dumps(baseline), encoding="utf-8")
    return pack


def test_pack_integrity_clean_passes(tmp_path):
    pack = _stub_pack(tmp_path)
    assert export_cmd._check_pack_integrity(pack, is_bundled=True, allow=False) == 0


def test_pack_integrity_tampered_refused(tmp_path, capsys):
    pack = _stub_pack(tmp_path)
    (pack / "preamble.tex").write_text("HAND EDITED", encoding="utf-8")
    assert export_cmd._check_pack_integrity(pack, is_bundled=True, allow=False) == 1
    err = capsys.readouterr().err
    assert "preamble.tex" in err and "hand-edited" in err


def test_pack_integrity_allow_overrides(tmp_path):
    pack = _stub_pack(tmp_path)
    (pack / "preamble.tex").write_text("HAND EDITED", encoding="utf-8")
    assert export_cmd._check_pack_integrity(pack, is_bundled=True, allow=True) == 0


def test_pack_integrity_user_template_skips_gate(tmp_path):
    pack = _stub_pack(tmp_path)
    (pack / "preamble.tex").write_text("HAND EDITED", encoding="utf-8")
    # --template 自有包（is_bundled=False）：合法替換、不設限
    assert export_cmd._check_pack_integrity(pack, is_bundled=False, allow=False) == 0


def test_pack_integrity_fonts_change_ignored(tmp_path):
    """fonts/ 不進基線（各機器自裝、會異）→ 改 fonts/ 不觸發 gate。"""
    pack = _stub_pack(tmp_path)
    (pack / "fonts" / "x.ttf").write_text("different font bytes", encoding="utf-8")
    assert export_cmd._check_pack_integrity(pack, is_bundled=True, allow=False) == 0


def test_pack_integrity_no_baseline_passes(tmp_path, capsys):
    pack = _stub_pack(tmp_path)
    (pack / paths.PACK_HASHES_FILE).unlink()
    assert export_cmd._check_pack_integrity(pack, is_bundled=True, allow=False) == 0
    assert "integrity baseline" in capsys.readouterr().err


def test_bundled_pack_matches_its_shipped_baseline():
    """★關鍵：隨 wheel 出貨的內建包，其 live 內容必須對得上自帶的 .pack-hashes.json
    （否則一安裝就被 gate 擋；也抓 wheel 漏帶 dotfile / 基線過期）。"""
    pack = paths.bundled_template_dir()
    assert pack is not None
    baseline = paths.read_pack_baseline(pack)
    assert baseline is not None, "wheel 未帶 .pack-hashes.json（dotfile 被打包工具吃掉？）"
    live = paths.pack_content_hashes(pack)
    assert live == baseline, "內建包內容與基線不符——改了包要重跑 tools/gen_pack_hashes.py"
