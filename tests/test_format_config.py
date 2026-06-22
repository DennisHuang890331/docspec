"""format-config「格式旋鈕」子系統：驗證（防幻覺閘門）、確定性編譯、export 注入。

核心承諾：agent 只填驗證過的值；壞值/幻覺**在編成 LaTeX 之前**就被拒、export 非零、
不產 PDF。本檔不需 xelatex/pandoc（驗 validate/compile 純函式 + export run() 的拒絕路徑）。
"""

from __future__ import annotations

import pytest

from dspx import paths
from dspx.commands import export as export_cmd
from dspx.format_config import (
    DEFAULT_FORMAT,
    FormatConfigError,
    compile_format_config,
    pandoc_highlight_style,
    validate_format_config,
)
from dspx.layout import Layout


# ── validate：補預設、未知鍵 warn 忽略 ──────────────────────────────

def test_validate_empty_gives_defaults():
    k = validate_format_config({})
    assert k["font"]["cjk_body"] == "TW-Sung"       # C5 定版：內文宋體
    assert k["font"]["cjk_heading"] == "TW-Kai"     # C5 定版：標題標楷
    assert k["font"]["base_size"] == 14.5          # 定版內文字級（C4）
    assert k["table"]["style"] == "github" and k["table"]["zebra"] is True
    assert k["code"]["highlight"] == "tango"
    assert k["page"] == {"preset": "a4-wide"}
    # C3 新旋鈕預設（＝現狀）
    assert k["font"]["heading_scale"] == 1.0
    assert k["table"]["size"] == 12.0 and k["table"]["column_rules"] is True


def test_validate_partial_merges_with_defaults():
    k = validate_format_config({"font": {"base_size": 11}})
    assert k["font"]["base_size"] == 11.0          # 覆寫的
    assert k["font"]["cjk_body"] == "TW-Sung"      # 其餘仍預設（C5 定版宋體）


def test_validate_unknown_section_and_key_warn_ignored():
    warned = []
    k = validate_format_config(
        {"bogus": {"x": 1}, "font": {"nope": 9, "base_size": 13}},
        warn=warned.append)
    assert any("bogus" in w for w in warned)
    assert any("nope" in w for w in warned)
    assert k["font"]["base_size"] == 13.0          # 已知鍵仍生效


# ── validate：防幻覺閘門（不合法值一律拋，永不進 compile）─────────────

@pytest.mark.parametrize("bad", [
    {"font": {"base_size": 99}},        # 超範圍 pt
    {"font": {"base_size": 9}},         # 低於下限
    {"font": {"leading": 2.0}},         # 超範圍
    {"font": {"cjk_body": "MicrosoftJhengHei"}},   # 幻覺/專有字型不在 enum
    {"font": {"cjk_heading": "Comic Sans"}},
    {"table": {"style": "fancy"}},      # 非 enum
    {"table": {"zebra": "yes"}},        # 型別錯（須 bool）
    {"code": {"highlight": "rainbow"}}, # pandoc 不支援
    {"page": {"margin": 5}},            # 超範圍 mm
    {"page": {"margin": 100}},
    {"page": {"preset": "letter"}},     # 非具名 preset
    {"font": {"heading_scale": 2.0}},   # C3 超範圍（0.8–1.6）
    {"font": {"heading_scale": 0.5}},
    {"table": {"size": 20}},            # C3 表格字級超範圍（8–14）
    {"table": {"column_rules": "yes"}}, # C3 型別錯（須 bool）
])
def test_validate_rejects_bad_values(bad):
    with pytest.raises(FormatConfigError):
        validate_format_config(bad)


def test_validate_error_names_the_knob_and_options():
    with pytest.raises(FormatConfigError) as ei:
        validate_format_config({"table": {"style": "fancy"}})
    msg = str(ei.value)
    assert "table.style" in msg and "github" in msg and "booktabs" in msg


def test_validate_margin_clears_preset():
    k = validate_format_config({"page": {"margin": 25}})
    assert k["page"] == {"margin": 25.0}   # margin 給了就以 margin 為準、無 preset


def test_validate_non_dict_raises():
    with pytest.raises(FormatConfigError):
        validate_format_config(["not", "a", "dict"])


# ── compile：確定性 LaTeX 覆寫片段 ─────────────────────────────────

def test_compile_default_is_status_quo_geometry_and_font():
    tex = compile_format_config(validate_format_config({}))
    # 預設＝bundled preamble 現行版心（a4-wide）、內文 TW-Sung 宋、標題 TW-Kai 楷、leading 1.45
    assert "hmargin=12mm" in tex
    assert "\\setCJKmainfont{TW-Sung-98_1}" in tex                     # C5：內文宋體
    assert "\\setCJKsansfont{TW-Kai-98_1}" in tex                      # C5：標題標楷
    assert "BoldFont=SourceHanSerifTC-SemiBold.otf" in tex            # emphasis＝宋粗 SemiBold
    assert "AutoFakeBold" in tex                                       # 標題合成粗體（不換黑體）
    assert "\\linespread{1.45}" in tex
    # ★C4：字級階梯不再發在 preamble compile（搬到 post-\maketitle）。
    assert "\\@setfontsize\\normalsize" not in tex


def test_compile_font_knobs_emit_overrides():
    tex = compile_format_config(validate_format_config(
        {"font": {"cjk_body": "SourceHanSerifTC", "leading": 1.3}}))
    assert "\\setCJKmainfont{SourceHanSerifTC-Regular}" in tex
    assert "\\linespread{1.3}" in tex


# ── C4：post-\maketitle 字級階梯（base_size 真的控制內文）──────────────────

def test_postmaketitle_default_is_byte_identical_to_legacy_block():
    from dspx.format_config import compile_postmaketitle_fonts
    pmt = compile_postmaketitle_fonts(validate_format_config({}))   # base_size 14.5
    assert pmt == (
        "\\makeatletter\n"
        "\\renewcommand\\normalsize{\\@setfontsize\\normalsize{14.5}{18.3}}\n"
        "\\renewcommand\\small{\\@setfontsize\\small{13}{16}}\n"
        "\\renewcommand\\footnotesize{\\@setfontsize\\footnotesize{12}{14.5}}\n"
        "\\makeatother\n"
        "\\normalsize"
    )


def test_postmaketitle_scales_with_base_size():
    from dspx.format_config import compile_postmaketitle_fonts
    pmt = compile_postmaketitle_fonts(validate_format_config({"font": {"base_size": 12}}))
    # 12/14.5 等比例：normalsize 主字級＝12
    assert "\\@setfontsize\\normalsize{12}" in pmt
    # 階梯整條縮（small/footnotesize 也跟著 < 內文）
    assert "\\@setfontsize\\small{" in pmt and "\\@setfontsize\\footnotesize{" in pmt


def test_compile_margin_emits_symmetric_geometry():
    tex = compile_format_config(validate_format_config({"page": {"margin": 25}}))
    assert "hmargin=25mm" in tex and "vmargin=25mm" in tex


def test_compile_table_style_and_zebra():
    gh = compile_format_config(validate_format_config({"table": {"style": "github", "zebra": True}}))
    assert "{D0D7DE}" in gh and "{F6F8FA}" in gh          # 淺灰格線 + 斑馬淡底
    bt = compile_format_config(validate_format_config(
        {"table": {"style": "booktabs", "zebra": False}}))
    assert "{222222}" in bt                                # 近黑粗格線
    assert "docspecZebra}{HTML}{FFFFFF}" in bt             # zebra off → 白（無斑馬）


def test_compile_emitted_fonts_are_all_bundled():
    """compile 出的所有 \\setCJK*font 字型檔，必在 bundled REQUIRED_FONT_FILES 內
    （驗 enum→bundled 字型的對應沒漏；agent 選不到不存在的字型）。"""
    import re
    from dspx.format_config import _CJK_FONTS
    bundled_stems = {f.rsplit(".", 1)[0] for f in paths.REQUIRED_FONT_FILES}
    for enum_name in _CJK_FONTS:
        tex = compile_format_config(validate_format_config({"font": {"cjk_body": enum_name}}))
        for stem in re.findall(r"\\setCJKmainfont\{([^}]+)\}", tex):
            assert stem in bundled_stems, f"{enum_name} → {stem} 不在 bundled 字型"


def test_pandoc_highlight_style_passthrough():
    assert pandoc_highlight_style(validate_format_config({"code": {"highlight": "kate"}})) == "kate"
    assert pandoc_highlight_style(validate_format_config({})) == "tango"


# ── C3：標題字級倍率 + 表格 metavars ──────────────────────────────────

def test_compile_heading_scale_default_emits_nothing():
    tex = compile_format_config(validate_format_config({}))
    assert "\\def\\sectionfont" not in tex          # scale 1.0＝不發＝byte-identical


def test_compile_heading_scale_nondefault_redefines_section_fonts():
    tex = compile_format_config(validate_format_config({"font": {"heading_scale": 1.2}}))
    assert "\\def\\sectionfont" in tex
    assert "\\fontsize{20.4pt}" in tex              # 17×1.2＝20.4
    assert "\\def\\ssectionfont" in tex and "\\def\\sssectionfont" in tex


def test_pandoc_table_metavars_default_is_status_quo():
    from dspx.format_config import pandoc_table_metavars
    mv = pandoc_table_metavars(validate_format_config({}))
    assert mv == ["-M", "docspec-table-size=12", "-M", "docspec-table-colrules=on"]


def test_pandoc_table_metavars_reflects_knobs():
    from dspx.format_config import pandoc_table_metavars
    mv = pandoc_table_metavars(validate_format_config(
        {"table": {"size": 10, "column_rules": False}}))
    assert mv == ["-M", "docspec-table-size=10", "-M", "docspec-table-colrules=off"]


# ── export run()：壞值在 export 被擋（非零、不產 PDF、不進 build）────────

def _setup(make_project, version="1.0.0", article="g"):
    home = make_project()
    layout = Layout(home, "per-article")
    snap = layout.docs_snapshot(article, version)
    snap.parent.mkdir(parents=True, exist_ok=True)
    snap.write_text("# 標題\n\n中文內容。\n", encoding="utf-8")
    return home, layout


def test_export_rejects_bad_format_config_file(make_project, monkeypatch, capsys, tmp_path):
    """--format-config 含壞值 → export 非零、印清楚錯誤、不產 PDF、不呼叫 _build_pdf。"""
    home, layout = _setup(make_project)
    monkeypatch.chdir(home.parent)
    monkeypatch.setattr(export_cmd, "_pandoc_path", lambda: "pandoc")
    monkeypatch.setattr(export_cmd, "_xelatex_path", lambda: paths.Path("xelatex"))
    called = {"n": 0}
    monkeypatch.setattr(export_cmd, "_build_pdf",
                        lambda *a, **k: called.__setitem__("n", called["n"] + 1))
    fc = tmp_path / "bad.yaml"
    fc.write_text("font:\n  base_size: 99\n", encoding="utf-8")
    rc = export_cmd.run(["g", "--format", "pdf", "--format-config", str(fc)])
    assert rc == 1
    assert called["n"] == 0                                # 壞值 → 連 build 都沒進
    err = capsys.readouterr().err
    assert "base_size" in err and "no LaTeX/PDF produced" in err


def test_export_rejects_missing_format_config_file(make_project, monkeypatch, capsys):
    home, layout = _setup(make_project)
    monkeypatch.chdir(home.parent)
    monkeypatch.setattr(export_cmd, "_pandoc_path", lambda: "pandoc")
    monkeypatch.setattr(export_cmd, "_xelatex_path", lambda: paths.Path("xelatex"))
    rc = export_cmd.run(["g", "--format", "pdf", "--format-config", str(home / "nope.yaml")])
    assert rc == 1
    assert "does not exist" in capsys.readouterr().err


def test_export_valid_format_config_compiles_and_injects(make_project, monkeypatch, tmp_path):
    """合法旋鈕：export 編出覆寫並餵進 _build_pdf（攔 _build_pdf 斷言 override 含旋鈕、
    highlight 帶對）。不需真 xelatex（攔截 build）。"""
    home, layout = _setup(make_project)
    monkeypatch.chdir(home.parent)
    monkeypatch.setattr(export_cmd, "_pandoc_path", lambda: "pandoc")
    monkeypatch.setattr(export_cmd, "_xelatex_path", lambda: paths.Path("xelatex"))
    # 模板/字型解析放行（不真 build）
    monkeypatch.setattr(paths, "resolve_template_dir", lambda *a, **k: paths.Path("tpl"))
    monkeypatch.setattr(paths, "resolve_fonts_dir", lambda *a, **k: paths.Path("fnt"))
    seen = {}

    def spy(pandoc, xelatex, template_dir, fonts_src, title, body_md, out,
            format_override="", highlight_style="tango", **k):
        seen["override"] = format_override
        seen["highlight"] = highlight_style

    monkeypatch.setattr(export_cmd, "_build_pdf", spy)
    fc = tmp_path / "good.yaml"
    fc.write_text("font:\n  cjk_body: SourceHanSerifTC\ncode:\n  highlight: kate\n",
                  encoding="utf-8")
    rc = export_cmd.run(["g", "--format", "pdf", "--format-config", str(fc), "--no-verify"])
    assert rc == 0
    assert "\\setCJKmainfont{SourceHanSerifTC-Regular}" in seen["override"]
    assert seen["highlight"] == "kate"


def test_export_no_format_config_uses_default_override(make_project, monkeypatch):
    """不給 --format-config、config 無 format → 注入的是預設旋鈕覆寫（＝現狀），highlight=tango。"""
    home, layout = _setup(make_project)
    monkeypatch.chdir(home.parent)
    monkeypatch.setattr(export_cmd, "_pandoc_path", lambda: "pandoc")
    monkeypatch.setattr(export_cmd, "_xelatex_path", lambda: paths.Path("xelatex"))
    monkeypatch.setattr(paths, "resolve_template_dir", lambda *a, **k: paths.Path("tpl"))
    monkeypatch.setattr(paths, "resolve_fonts_dir", lambda *a, **k: paths.Path("fnt"))
    seen = {}

    def spy(*a, format_override="", highlight_style="tango", **k):
        seen["override"] = format_override
        seen["highlight"] = highlight_style

    monkeypatch.setattr(export_cmd, "_build_pdf", spy)
    rc = export_cmd.run(["g", "--format", "pdf", "--no-verify"])
    assert rc == 0
    assert "\\setCJKmainfont{TW-Sung-98_1}" in seen["override"]   # C5 定版預設＝宋體內文
    assert seen["highlight"] == "tango"


def test_export_project_config_format_default(make_project, monkeypatch):
    """config 的 export.format 區塊＝專案級預設旋鈕，無 --format-config 時生效。"""
    home = make_project(
        "language: zh-TW\ndocs_layout: per-article\n"
        "export:\n  format:\n    font:\n      cjk_body: SourceHanSansTC\n")
    layout = Layout(home, "per-article")
    snap = layout.docs_snapshot("g", "1.0.0")
    snap.parent.mkdir(parents=True, exist_ok=True)
    snap.write_text("# 標題\n\n中文。\n", encoding="utf-8")
    monkeypatch.chdir(home.parent)
    monkeypatch.setattr(export_cmd, "_pandoc_path", lambda: "pandoc")
    monkeypatch.setattr(export_cmd, "_xelatex_path", lambda: paths.Path("xelatex"))
    monkeypatch.setattr(paths, "resolve_template_dir", lambda *a, **k: paths.Path("tpl"))
    monkeypatch.setattr(paths, "resolve_fonts_dir", lambda *a, **k: paths.Path("fnt"))
    seen = {}
    monkeypatch.setattr(export_cmd, "_build_pdf",
                        lambda *a, format_override="", **k: seen.__setitem__("o", format_override))
    assert export_cmd.run(["g", "--format", "pdf", "--no-verify"]) == 0
    assert "\\setCJKmainfont{SourceHanSansTC-Regular}" in seen["o"]   # 專案預設生效
