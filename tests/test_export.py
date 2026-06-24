"""docspec export：byte-lock（內容只動呈現）、soft-dep 降級、輸出路徑、凍結快照輸入。

預設 render 軌＝Typst（受控 typst binary + docspec-typst 模板；LaTeX/docspec-cas 軌已退場）。
journal 軌＝BYO emit-only（pandoc --template=<journal> → .tex，不編譯）。
軟相依：pandoc（系統或 pypandoc_binary）＋ typst（受控；DOCSPEC_TYPST/系統 PATH）＋受控字型。
缺工具的轉檔斷言 skip。byte-lock 證明＝抽回 PDF 文字後與源快照做 **content-token 多重集** 比對
（NFC＋只留拉丁詞/個別 CJK 字/數字），對表格重排穩健、又能抓出任何內容增刪。
"""

from __future__ import annotations

import pytest

from dspx import paths
from dspx.commands import export as export_cmd
from dspx.layout import Layout

_HAVE_PANDOC = export_cmd._pandoc_path() is not None
# 受控 typst ＋ 受控字型（data_dir/fonts）皆備才跑真 PDF build（預設 Typst 軌）。
# 字型/typst 已移出 wheel：fresh 環境未跑 `docspec setup` 時 skip（非 fail）。
_HAVE_PDF = paths.resolve_typst() is not None and paths.resolve_fonts_dir() is not None
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


# ── 標題抽取（H1 → 標題 slot，移出正文）──────────────────────────────

def test_split_title_body_extracts_h1():
    title, body = export_cmd._split_title_body(_SNAP, fallback_title="g")
    assert title == "概覽文件"
    # H1 行不再出現在正文（避免與模板的標題 slot 重複）
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
    if not _HAVE_PDF:
        pytest.skip("PDF 需要受控 typst＋字型（docspec setup）")
    pdfplumber = pytest.importorskip("pdfplumber")
    home, layout = _setup(make_project)
    monkeypatch.chdir(home.parent)
    assert export_cmd.run(["g", "--format", "pdf"]) == 0   # 預設 Typst 軌
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

def test_export_latex_engine_retired(make_project, monkeypatch, capsys):
    # LaTeX/xelatex 軌（docspec-cas LPPL 包）已退場 → 明確報錯、回 1、導向 typst/journal
    home, layout = _setup(make_project)
    monkeypatch.chdir(home.parent)
    assert export_cmd.run(["g", "--format", "pdf", "--engine", "latex"]) == 1
    assert not layout.docs_export("g", "1.0.0", "pdf").is_file()
    err = capsys.readouterr().err
    assert "retired" in err and "--engine typst" in err


def test_export_degrades_when_fonts_missing(make_project, monkeypatch, capsys):
    home, layout = _setup(make_project)
    monkeypatch.chdir(home.parent)
    # 受控字型缺（Typst 軌）→ 模型 A 明確叫跑 `docspec setup`、回 1、不留半成品
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


# ── 表格欄寬：pandoc 等分百分比 → typst auto（治窄欄硬斷字）─────────────

def test_balance_table_columns_equal_pct_to_auto():
    # pandoc 對沒指定寬的表給等分百分比 → 改 auto（依內容定寬）
    src = "#table(\n  columns: (33.33%, 33.33%, 33.33%),\n  align: (auto,auto,auto,),\n)"
    out = export_cmd._balance_table_columns(src)
    assert "columns: (auto, auto, auto)" in out
    assert "33.33%" not in out


def test_balance_table_columns_respects_unequal_widths():
    # 非等分＝作者用 grid table 指定的相對寬 → 保留不動
    src = "#table(columns: (50%, 25%, 25%),)"
    assert export_cmd._balance_table_columns(src) == src


def test_balance_table_columns_leaves_auto_and_fr_alone():
    # 已是 auto / fr 的欄寬不碰
    src = "#table(columns: (auto, 1fr, auto),)"
    assert export_cmd._balance_table_columns(src) == src


def test_fix_typst_math_sect_to_inter():
    # pandoc 把 ∩ 譯成 typst 不認的 sect → 在數學區段改 inter
    src = r"text $ frac(\|hat(R)_k sect R\|, \|R\|) $ more"
    out = export_cmd._fix_typst_math(src)
    assert "inter" in out and "sect" not in out


def test_fix_typst_math_leaves_prose_word_alone():
    # 散文裡的 "sect"（非數學）不動
    src = "The religious sect met. $a sect b$"
    out = export_cmd._fix_typst_math(src)
    assert "religious sect met" in out      # 散文不碰
    assert "a inter b" in out               # 數學內改


# ── 輸出路徑：絕不在 archive 下 ───────────────────────────────────

def test_export_output_never_in_archive(make_project, monkeypatch):
    if not _HAVE_PDF:
        pytest.skip("PDF 需要受控 typst＋字型（docspec setup）")
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


def test_lint_ve3_mermaid_flagged(make_project):
    from dspx.lint import _lint_export_safety
    home = make_project()
    layout = Layout(home, "per-article")
    _write_latest(layout, "g",
        "# 文件\n\n## 圖\n\n```mermaid\nflowchart TB\n  A --> B\n```\n\n內容。\n")
    findings = _lint_export_safety(layout, ["g"])
    ve3 = [f for f in findings if f.rule == "Ve3"]
    assert len(ve3) == 1 and "embedded image" in ve3[0].detail


def test_lint_ve3_raw_latex_tikz_flagged(make_project):
    from dspx.lint import _lint_export_safety
    home = make_project()
    layout = Layout(home, "per-article")
    # raw `{=latex}` (舊 TikZ 寫法) 現在非 backend-neutral → Ve3 應 flag（預設 Typst 軌會剝掉）
    _write_latest(layout, "g",
        "# 文件\n\n## 圖\n\n```{=latex}\n\\begin{center}\\begin{tikzpicture}\\node{A};\\end{tikzpicture}\\end{center}\n```\n\n內容。\n")
    ve3 = [f for f in _lint_export_safety(layout, ["g"]) if f.rule == "Ve3"]
    assert len(ve3) == 1 and "backend-neutral" in ve3[0].detail


def test_lint_ve_clean_doc_no_findings(make_project):
    from dspx.lint import _lint_export_safety
    home = make_project()
    layout = Layout(home, "per-article")
    _write_latest(layout, "g",
        "# 文件\n\n## 概覽 (Overview)\n\n見 [概覽](#概覽-overview)。\n\n## 細節\n\n內容。\n")
    assert _lint_export_safety(layout, ["g"]) == []


def test_export_latest_preview(make_project, monkeypatch):
    if not _HAVE_PDF:
        pytest.skip("PDF 需要受控 typst＋字型（docspec setup）")
    home, layout = _setup(make_project)
    latest = layout.docs_latest("g")
    latest.parent.mkdir(parents=True, exist_ok=True)
    latest.write_text(_SNAP, encoding="utf-8")
    monkeypatch.chdir(home.parent)
    assert export_cmd.run(["g", "--format", "pdf", "--latest"]) == 0
    assert layout.docs_export("g", "latest", "pdf").is_file()


# ── 圖片資產：export 把被引用的 assets/<file> copy 進 build dir（嵌圖才渲得出）──────

def _setup_with_asset(make_project, write_leaf):
    """建一個帶圖片資產的最小專案：corpus 末節 + assets/diagram.svg + 引用它的快照。"""
    home = make_project()
    write_leaf(home, "art/intro", concept={"concept": "art/intro"})
    leaf = home / "corpus" / "art" / "intro"
    (leaf / "assets").mkdir(exist_ok=True)
    (leaf / "assets" / "diagram.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="80" height="40"></svg>', encoding="utf-8")
    layout = Layout(home, "per-article")
    snap = layout.docs_snapshot("art", "1.0.0")
    snap.parent.mkdir(parents=True, exist_ok=True)
    snap.write_text("# 標題\n\n內文。\n\n![圖](assets/diagram.svg)\n", encoding="utf-8")
    return home, layout


def test_collect_referenced_assets_maps_refs(make_project, write_leaf, monkeypatch):
    home, layout = _setup_with_asset(make_project, write_leaf)
    monkeypatch.chdir(home.parent)
    body = "![圖](assets/diagram.svg)\n\n![缺](assets/missing.svg)\n"
    found = export_cmd._collect_referenced_assets(layout, "art", body)
    assert "assets/diagram.svg" in found and found["assets/diagram.svg"].is_file()
    assert "assets/missing.svg" not in found  # 不存在的不收（check ⑨ 會擋斷引用）


def test_copy_assets_into_build(tmp_path):
    src = tmp_path / "src.svg"
    src.write_text("<svg/>", encoding="utf-8")
    build = tmp_path / "build"
    build.mkdir()
    export_cmd._copy_assets_into(build, {"assets/x.svg": src})
    assert (build / "assets" / "x.svg").is_file()


def test_typst_export_embeds_image(make_project, write_leaf, monkeypatch):
    if paths.resolve_typst() is None:
        pytest.skip("Typst 軌嵌圖端到端需要受控 typst（docspec setup）")
    if paths.resolve_fonts_dir() is None:
        pytest.skip("Typst 軌需要受控字型")
    home, layout = _setup_with_asset(make_project, write_leaf)
    monkeypatch.chdir(home.parent)
    # 若圖沒被 copy 進 build，typst compile 會找不到圖而失敗 → rc!=0
    assert export_cmd.run(["art", "--engine", "typst"]) == 0
    assert layout.docs_export("art", "1.0.0", "pdf").is_file()


# ── journal 軌（BYO LaTeX、emit-only：pandoc --template=<journal> → .tex，不編譯）──────

def test_journal_emit_ieee(make_project, monkeypatch, tmp_path):
    home, layout = _setup(make_project)
    slots = tmp_path / "slots.yaml"
    slots.write_text(
        "authors:\n  - name: Ada\n    affiliation: Lab\nabstract: An abstract.\n"
        "keywords:\n  - alpha\n  - beta\n", encoding="utf-8")
    monkeypatch.chdir(home.parent)
    assert export_cmd.run(["g", "--engine", "journal", "--journal", "ieee",
                           "--slots", str(slots)]) == 0
    out = layout.docs_journal_export("g", "1.0.0", "ieee", "tex")
    assert out.is_file()
    tex = out.read_text(encoding="utf-8")
    assert "\\documentclass[journal]{IEEEtran}" in tex
    assert "概覽文件" in tex                       # title slot (derived from H1)
    assert "An abstract." in tex                     # abstract slot
    assert "alpha, beta" in tex                       # keywords list joined
    assert "Ada" in tex                               # author
    # 不應產出 PDF（emit-only）
    assert not layout.docs_export("g", "1.0.0", "pdf").is_file()


def test_journal_implied_by_journal_flag(make_project, monkeypatch):
    home, layout = _setup(make_project)
    monkeypatch.chdir(home.parent)
    # 給 --journal 但不給 --engine → 隱含 journal 軌
    assert export_cmd.run(["g", "--journal", "elsevier"]) == 0
    tex = layout.docs_journal_export("g", "1.0.0", "elsevier", "tex").read_text(encoding="utf-8")
    assert "{cas-dc}" in tex


def test_journal_iet_adapter(make_project, monkeypatch):
    home, layout = _setup(make_project)
    monkeypatch.chdir(home.parent)
    assert export_cmd.run(["g", "--journal", "iet"]) == 0
    tex = layout.docs_journal_export("g", "1.0.0", "iet", "tex").read_text(encoding="utf-8")
    assert "{cta-author}" in tex


def test_journal_table_filter_avoids_longtable(make_project, monkeypatch):
    """兩欄期刊 class 拒 longtable → journal 軌的 Lua filter 必須把表格改寫成 tabular。"""
    home, layout = _setup(make_project)  # _SNAP 內含一個 markdown 表格
    monkeypatch.chdir(home.parent)
    assert export_cmd.run(["g", "--journal", "ieee"]) == 0
    tex = layout.docs_journal_export("g", "1.0.0", "ieee", "tex").read_text(encoding="utf-8")
    assert "\\begin{longtable}" not in tex   # 環境（非 \usepackage{longtable}）不該出現
    assert "\\begin{tabularx}" in tex        # tabularx X 欄＝寬表自動換行、收進 \textwidth、不溢出版面
    assert "}X" in tex                       # X 欄型（ragged-right）


def test_strip_journal_frontmatter_drops_author_and_abstract():
    # 作者列＋Abstract/Keywords 節進了 slot → 從 body 砍掉、保留至第一個內容標題（Introduction）
    body = (
        "**Dennis Huang**\n\n*Some Affiliation*\n\n"
        "## Abstract\n\nThe abstract text.\n\n"
        "## Keywords\n\nfoo; bar\n\n"
        "## Introduction\n\nReal body starts here.\n"
    )
    out = export_cmd._strip_journal_frontmatter(body)
    assert out.startswith("## Introduction")
    assert "Dennis Huang" not in out
    assert "The abstract text" not in out
    assert "Real body starts here." in out


def test_strip_journal_frontmatter_no_heading_left_untouched():
    # 整份無 heading → 保守不動（不誤砍）
    body = "Just a paragraph with no headings at all.\n"
    assert export_cmd._strip_journal_frontmatter(body) == body


def test_journal_unknown_slot_value_fails(make_project, monkeypatch, tmp_path):
    home, layout = _setup(make_project)
    slots = tmp_path / "slots.yaml"
    slots.write_text("bogus_slot: x\n", encoding="utf-8")
    monkeypatch.chdir(home.parent)
    rc = export_cmd.run(["g", "--engine", "journal", "--journal", "ieee", "--slots", str(slots)])
    assert rc == 1
    assert not layout.docs_journal_export("g", "1.0.0", "ieee", "tex").is_file()


def test_journal_missing_template_errors(make_project, monkeypatch):
    home, _ = _setup(make_project)
    monkeypatch.chdir(home.parent)
    # engine journal 但沒給 --journal/--template → 報錯非零
    assert export_cmd.run(["g", "--engine", "journal"]) == 1


def test_journal_byo_template_dir(make_project, monkeypatch, tmp_path):
    home, layout = _setup(make_project)
    pack = tmp_path / "myjournal"
    pack.mkdir()
    (pack / "template.tex").write_text(
        "\\documentclass{article}\n\\title{$title$}\n\\begin{document}\n"
        "\\maketitle\n$body$\n\\end{document}\n", encoding="utf-8")
    monkeypatch.chdir(home.parent)
    assert export_cmd.run(["g", "--engine", "journal", "--template", str(pack)]) == 0
    tex = layout.docs_journal_export("g", "1.0.0", "myjournal", "tex").read_text(encoding="utf-8")
    assert "\\documentclass{article}" in tex and "概覽文件" in tex


# ── #1 --template / --fonts 旗標：解析、覆寫生效、缺檔報錯 ─────────────

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
    """export --template 指不存在的夾（隱含 journal 軌）→ 清楚報錯、非零、不 crash。"""
    home, _ = _setup(make_project)
    monkeypatch.chdir(home.parent)
    monkeypatch.setattr(export_cmd, "_pandoc_path", lambda: "pandoc")
    rc = export_cmd.run(["g", "--template", str(home / "missing_tpl")])
    assert rc == 1
    assert "journal template not found" in capsys.readouterr().err


def test_prune_old_pdfs_keeps_only_latest_scoped(make_project):
    """D8：清同篇舊版 PDF（含 _vlatest），只留剛產出；他篇/journal 子夾/archive 不碰。"""
    home, layout = _setup(make_project)
    exports = layout.docs_exports_dir
    exports.mkdir(parents=True, exist_ok=True)
    (exports / "g_v1.0.0.pdf").write_text("old", encoding="utf-8")
    (exports / "g_v1.0.1.pdf").write_text("old", encoding="utf-8")
    (exports / "g_vlatest.pdf").write_text("preview", encoding="utf-8")
    (exports / "other_v1.0.0.pdf").write_text("other-article", encoding="utf-8")  # 他篇
    jtex = layout.docs_journal_export("g", "1.0.0", "ieee", "tex")               # journal 子夾
    jtex.parent.mkdir(parents=True, exist_ok=True)
    jtex.write_text("tex", encoding="utf-8")
    keep = exports / "g_v1.0.2.pdf"
    keep.write_text("new", encoding="utf-8")

    pruned = {p.name for p in export_cmd._prune_old_pdfs(layout, "g", keep)}
    assert pruned == {"g_v1.0.0.pdf", "g_v1.0.1.pdf", "g_vlatest.pdf"}
    assert keep.is_file()                                  # 留最新
    assert (exports / "other_v1.0.0.pdf").is_file()        # 他篇不碰（前綴 g_v 不匹配）
    assert jtex.is_file()                                  # journal 子夾不碰（非遞迴）


def test_journal_adapters_no_collision(make_project, monkeypatch):
    """B7：ieee 與 elsevier 落不同子夾、互不覆寫。"""
    home, layout = _setup(make_project)
    monkeypatch.chdir(home.parent)
    assert export_cmd.run(["g", "--journal", "ieee"]) == 0
    assert export_cmd.run(["g", "--journal", "elsevier"]) == 0
    ieee = layout.docs_journal_export("g", "1.0.0", "ieee", "tex")
    elsevier = layout.docs_journal_export("g", "1.0.0", "elsevier", "tex")
    assert ieee.is_file() and elsevier.is_file()
    assert ieee.parent != elsevier.parent
    assert "{IEEEtran}" in ieee.read_text(encoding="utf-8")
    assert "{cas-dc}" in elsevier.read_text(encoding="utf-8")


def test_export_fonts_flag_missing_font_errors(make_project, monkeypatch, capsys, tmp_path):
    """export --fonts 指缺字型的夾（Typst 軌）→ 清楚報錯、非零、不 crash。"""
    home, _ = _setup(make_project)
    monkeypatch.chdir(home.parent)
    monkeypatch.setattr(export_cmd, "_pandoc_path", lambda: "pandoc")
    partial = _make_fonts_dir(tmp_path / "partial")
    (partial / paths.REQUIRED_FONT_FILES[0]).unlink()
    rc = export_cmd.run(["g", "--format", "pdf", "--fonts", str(partial)])
    assert rc == 1
    err = capsys.readouterr().err
    assert "font" in err and paths.REQUIRED_FONT_FILES[0] in err


def test_export_fonts_flag_overrides_build(make_project, monkeypatch):
    """--fonts 真的把使用者字型夾餵進 build（Typst 軌）：攔 _build_pdf_typst 斷言 fonts_src＝給的夾。"""
    if not _HAVE_PDF:
        pytest.skip("PDF 需要受控 typst＋字型（docspec setup）")
    home, layout = _setup(make_project)
    monkeypatch.chdir(home.parent)
    # 用真字型夾複製出一份當「使用者字型夾」，確保 build 能成
    real_fonts = paths.resolve_fonts_dir()
    assert real_fonts is not None
    import shutil
    user_fonts = home.parent / "user_fonts"
    shutil.copytree(str(real_fonts), str(user_fonts))

    seen = {}
    orig = export_cmd._build_pdf_typst

    def spy(pandoc, typst, typst_template, fonts_src, title, body_md, out, **kw):
        seen["fonts_src"] = fonts_src
        return orig(pandoc, typst, typst_template, fonts_src, title, body_md, out, **kw)

    monkeypatch.setattr(export_cmd, "_build_pdf_typst", spy)
    assert export_cmd.run(["g", "--format", "pdf", "--fonts", str(user_fonts)]) == 0
    assert seen["fonts_src"] == user_fonts


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


def test_verify_byte_lock_hard_gate_when_pdfplumber_missing(monkeypatch, capsys):
    """pdfplumber 缺 → 渲染忠實度 hard-gate：印安裝提示、回 1（fail-closed，--no-verify 才跳）。"""
    import builtins
    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name == "pdfplumber":
            raise ImportError("no pdfplumber")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert export_cmd._verify_byte_lock(paths.Path("x.pdf"), "內容") == 1
    err = capsys.readouterr().err
    assert "pdfplumber" in err and "--no-verify" in err


def test_export_no_verify_skips_check(make_project, monkeypatch):
    """--no-verify → 不呼叫 _verify_byte_lock（即使一致也跳過）。"""
    if not _HAVE_PDF:
        pytest.skip("PDF 需要受控 typst＋字型（docspec setup）")
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
    if not _HAVE_PDF:
        pytest.skip("PDF 需要受控 typst＋字型（docspec setup）")
    home, layout = _setup(make_project)
    monkeypatch.chdir(home.parent)
    monkeypatch.setattr(export_cmd, "_verify_byte_lock", lambda *a, **k: 1)
    assert export_cmd.run(["g", "--format", "pdf"]) == 1


# ── C2 逃生口 gate：內建模板包竄改偵測 ────────────────────────────────

def _stub_pack(tmp_path):
    # 模型化現行內建包＝Typst pack（單一 template.typ；docspec-cas 的 preamble/before.tex 已退場）。
    pack = tmp_path / "pack"
    pack.mkdir()
    (pack / "template.typ").write_text("base content", encoding="utf-8")
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
    (pack / "template.typ").write_text("HAND EDITED", encoding="utf-8")
    assert export_cmd._check_pack_integrity(pack, is_bundled=True, allow=False) == 1
    err = capsys.readouterr().err
    assert "template.typ" in err and "hand-edited" in err


def test_pack_integrity_allow_overrides(tmp_path):
    pack = _stub_pack(tmp_path)
    (pack / "template.typ").write_text("HAND EDITED", encoding="utf-8")
    assert export_cmd._check_pack_integrity(pack, is_bundled=True, allow=True) == 0


def test_pack_integrity_user_template_skips_gate(tmp_path):
    pack = _stub_pack(tmp_path)
    (pack / "template.typ").write_text("HAND EDITED", encoding="utf-8")
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


def test_bundled_typst_pack_matches_its_shipped_baseline():
    """★關鍵：Typst 內建包（template.typ）live 內容必須對得上自帶的 .pack-hashes.json。
    改了 template.typ 要重跑 tools/gen_pack_hashes.py。"""
    pack = paths.bundled_typst_template_dir()
    assert pack is not None
    baseline = paths.read_pack_baseline(pack)
    assert baseline is not None, "Typst pack 未帶 .pack-hashes.json（dotfile 被打包工具吃掉？）"
    live = paths.pack_content_hashes(pack)
    assert live == baseline, "Typst 內建包內容與基線不符——改了 template.typ 要重跑 tools/gen_pack_hashes.py"


# ── Typst 軌（Stage B：typst-default-dual-track-rendering）─────────────

_HAVE_TYPST = paths.resolve_typst() is not None


def test_strip_raw_latex_removes_tikz_blocks():
    md = "前文\n\n```{=latex}\n\\begin{tikzpicture}調度層\\end{tikzpicture}\n```\n\n後文"
    out = export_cmd._strip_raw_latex(md)
    assert "tikzpicture" not in out and "調度層" not in out
    assert "前文" in out and "後文" in out


def test_bundled_typst_template_exists():
    d = paths.bundled_typst_template_dir()
    assert d is not None and (d / "template.typ").is_file()


def test_resolve_typst_honors_env(monkeypatch, tmp_path):
    fake = tmp_path / ("typst.exe" if paths.os.name == "nt" else "typst")
    fake.write_text("", encoding="utf-8")
    monkeypatch.setenv("DOCSPEC_TYPST", str(fake))
    assert paths.resolve_typst() == str(fake)


def test_export_typst_degrades_when_typst_missing(make_project, monkeypatch, capsys):
    home, _ = _setup(make_project)
    monkeypatch.chdir(home.parent)
    monkeypatch.setattr(export_cmd._pandoc_path.__module__ + ".paths", paths, raising=False)
    monkeypatch.setattr(paths, "resolve_typst", lambda: None)
    monkeypatch.setattr(paths, "resolve_fonts_dir", lambda *a, **k: paths.Path("fonts"))
    assert export_cmd.run(["g", "--engine", "typst"]) == 1
    assert "typst not found" in capsys.readouterr().err


@pytest.mark.skipif(not _HAVE_TYPST, reason="Typst 軌端到端需要 typst binary（設 DOCSPEC_TYPST）")
def test_export_typst_produces_pdf(make_project, monkeypatch):
    if paths.resolve_fonts_dir() is None:
        pytest.skip("需要受控字型（docspec setup）")
    home, layout = _setup(make_project)
    monkeypatch.chdir(home.parent)
    assert export_cmd.run(["g", "--engine", "typst"]) == 0
    assert layout.docs_export("g", "1.0.0", "pdf").is_file()


# ── C3：圖片健檢（非阻塞）＋表格分頁 ─────────────────────────────

def test_figure_health_warns_unresolved_ref():
    warns = export_cmd._figure_health_warnings("See ![d](assets/missing.png).", {})
    assert any("missing.png" in w and "missing this figure" in w for w in warns)


def test_figure_health_warns_black_png(tmp_path):
    Image = pytest.importorskip("PIL.Image")
    p = tmp_path / "black.png"
    Image.new("RGB", (24, 24), (0, 0, 0)).save(p)
    warns = export_cmd._figure_health_warnings("![d](assets/black.png)", {"assets/black.png": p})
    assert any("black.png" in w and "black" in w for w in warns)


def test_figure_health_clean_png_no_warn(tmp_path):
    Image = pytest.importorskip("PIL.Image")
    p = tmp_path / "ok.png"
    Image.new("RGB", (24, 24), (120, 130, 140)).save(p)
    warns = export_cmd._figure_health_warnings("![d](assets/ok.png)", {"assets/ok.png": p})
    assert warns == []


def test_typst_template_table_breakable():
    pack = paths.bundled_typst_template_dir()
    txt = (pack / "template.typ").read_text(encoding="utf-8")
    assert "figure.where(kind: table): set block(breakable: true)" in txt


# ── C5：文類版面 profile（typesetting-document-profiles）─────────────

def test_export_profiles_enum_and_default():
    from dspx.config import EXPORT_PROFILES, DEFAULTS
    assert set(EXPORT_PROFILES) == {"default", "academic", "paper", "manual", "essay", "novel"}
    assert DEFAULTS["export"]["profile"] == "default"


def test_typst_template_has_profile_branches():
    txt = (paths.bundled_typst_template_dir() / "template.typ").read_text(encoding="utf-8")
    assert 'profile == "novel"' in txt          # 文類條件分支
    assert "first-line-indent" in txt           # 段落模型（縮排 XOR 段距）
    assert "tracking: 0.35em" in txt            # novel 場景分隔花飾 * * *
    assert "1.7em" in txt                        # 標題模數（title 1.7×＝對齊單欄學術慣例，收斂自過大的 2.0）
    assert "Source Sans 3" in txt                # sans 標題/手冊內文（非 CJK 文件）
    assert "_sansok" in txt                      # ★sans 受語言條件：CJK 文件退 serif（typst Source Sans 3 子集 bug 破壞 CJK 抽取）
    assert "cjk-latin-spacing" in txt            # 漢字↔Latin 自動間距
    # 刻意不用 covers（破壞 fidelity 抽取）：字型用簡單 Latin-first fallback；CJK 用 typst 註冊名「思源宋體」
    assert '#let _serif = ("Source Serif 4", "思源宋體")' in txt


def test_typst_template_has_paper_two_column():
    txt = (paths.bundled_typst_template_dir() / "template.typ").read_text(encoding="utf-8")
    assert 'profile == "paper"' in txt            # paper profile 分支
    assert "_twocol" in txt                       # 雙欄旗標
    assert "columns: if _twocol { 2 } else { 1 }" in txt   # 雙欄頁面
    assert 'scope: "parent"' in txt               # 標題/摘要跨欄（IEEE 慣例）


def test_export_rejects_unknown_profile_from_config(make_project, write_leaf, monkeypatch):
    home = make_project("language: zh-TW\ndocs_layout: per-article\nexport:\n  profile: bogus\n")
    write_leaf(home, "g/x", concept={"id": "c1", "title": "X", "order": 1})
    monkeypatch.chdir(home.parent)
    assert export_cmd.run(["g"]) == 1   # 友善報錯（config 壞 profile），非 argparse SystemExit
