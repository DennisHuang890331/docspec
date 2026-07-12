"""format-config「格式旋鈕」子系統：驗證（防幻覺閘門）、Typst 變數映射、export 注入。

核心承諾：agent 只填驗證過的值；壞值/幻覺**在編成輸出之前**就被拒、export 非零、
不產 PDF。本檔不需 typst/pandoc（驗 validate/Typst 純函式 + export run() 的拒絕路徑）。

★Typst 為現行預設 PDF 軌：標題字級由 template.typ 以 em-相對設定（隨內文縮放、層級恆正確），
font 旋鈕只剩 base_size/leading；cas-sc 時代的字型 enum/heading_scale/字級階梯已隨 LaTeX 軌退場。
"""

from __future__ import annotations

import pytest

from dspx.commands import export as export_cmd
from dspx.typeset.format_config import (
    FormatConfigError,
    pandoc_highlight_style,
    validate_format_config,
)
from dspx.engine.layout import Layout


# ── validate：補預設、未知鍵 warn 忽略 ──────────────────────────────

def test_validate_empty_gives_defaults():
    k = validate_format_config({})
    assert k["font"]["base_size"] == 14.5          # 內文字級錨點
    assert k["font"]["leading"] == 1.45
    assert set(k["font"]) == {"base_size", "leading"}   # font 只剩這兩顆旋鈕
    assert k["table"]["style"] == "github" and k["table"]["zebra"] is True
    assert k["code"]["highlight"] == "tango"
    assert k["page"] == {"preset": "a4-wide"}
    assert k["table"]["size"] == 12.0 and k["table"]["column_rules"] is True


def test_validate_partial_merges_with_defaults():
    k = validate_format_config({"font": {"base_size": 11}})
    assert k["font"]["base_size"] == 11.0          # 覆寫的
    assert k["font"]["leading"] == 1.45            # 其餘仍預設


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
    {"table": {"style": "fancy"}},      # 非 enum
    {"table": {"zebra": "yes"}},        # 型別錯（須 bool）
    {"code": {"highlight": "rainbow"}}, # pandoc 不支援
    {"page": {"margin": 5}},            # 超範圍 mm
    {"page": {"margin": 100}},
    {"page": {"preset": "letter"}},     # 非具名 preset
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


# ── 旋鈕回傳：highlight / 表格 metavars ──────────────────────────────

def test_pandoc_highlight_style_passthrough():
    assert pandoc_highlight_style(validate_format_config({"code": {"highlight": "kate"}})) == "kate"
    assert pandoc_highlight_style(validate_format_config({})) == "tango"


def test_pandoc_table_metavars_default_is_status_quo():
    from dspx.typeset.format_config import pandoc_table_metavars
    mv = pandoc_table_metavars(validate_format_config({}))
    assert mv == ["-M", "docspec-table-size=12", "-M", "docspec-table-colrules=on"]


def test_pandoc_table_metavars_reflects_knobs():
    from dspx.typeset.format_config import pandoc_table_metavars
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
    """--format-config 含壞值 → export 非零、印清楚錯誤、不產 PDF（驗證在編譯前發生，
    與引擎無關）。"""
    home, layout = _setup(make_project)
    monkeypatch.chdir(home.parent)
    fc = tmp_path / "bad.yaml"
    fc.write_text("font:\n  base_size: 99\n", encoding="utf-8")
    rc = export_cmd.run(["g", "--format", "pdf", "--format-config", str(fc)])
    assert rc == 1
    assert not layout.docs_export("g", "1.0.0", "pdf").is_file()   # 壞值 → 沒產 PDF
    err = capsys.readouterr().err
    assert "base_size" in err and "no PDF produced" in err


def test_export_rejects_missing_format_config_file(make_project, monkeypatch, capsys):
    home, layout = _setup(make_project)
    monkeypatch.chdir(home.parent)
    rc = export_cmd.run(["g", "--format", "pdf", "--format-config", str(home / "nope.yaml")])
    assert rc == 1
    assert "does not exist" in capsys.readouterr().err


# ── Typst 軌旋鈕映射（Stage B 2.4）────────────────────────────────

def test_compile_typst_vars_maps_base_size_and_leading():
    from dspx.typeset.format_config import compile_typst_vars, validate_format_config
    v = compile_typst_vars(validate_format_config({"font": {"base_size": 12.0, "leading": 1.3}}))
    assert "-V" in v and "fontsize=12pt" in v
    assert any(x == "leading=0.8em" for x in v)   # 1.3 - 0.5 = 0.8


def test_compile_typst_vars_default_uses_typst_house_body():
    """預設 base_size＝LaTeX cas-sc 錨點(14.5pt，雙欄期刊用、Typst 單欄 A4 過大)→ 不發 fontsize，
    交給 docspec-typst 模板自己的 house 預設（單欄適中字級）。使用者調 base_size 才覆寫。"""
    from dspx.typeset.format_config import compile_typst_vars, validate_format_config
    v = compile_typst_vars(validate_format_config({}))
    assert not any(x.startswith("fontsize=") for x in v)   # 預設不發 → Typst house 預設生效
    # 明確調過 base_size 才發（且非錨點值）
    v2 = compile_typst_vars(validate_format_config({"font": {"base_size": 11.0}}))
    assert "fontsize=11pt" in v2


# ── D4：page.margin / preset / par.first_line_indent 接線 ─────────────

def test_compile_typst_vars_maps_page_margin():
    from dspx.typeset.format_config import compile_typst_vars, validate_format_config
    v = compile_typst_vars(validate_format_config({"page": {"margin": 25}}))
    assert "margin=25mm" in v


def test_compile_typst_vars_preset_a4_normal_emits_equivalent_margin():
    from dspx.typeset.format_config import compile_typst_vars, validate_format_config
    v = compile_typst_vars(validate_format_config({"page": {"preset": "a4-normal"}}))
    assert "margin=25mm" in v


def test_compile_typst_vars_preset_a4_wide_emits_no_margin():
    """a4-wide（預設）＝house 版心、不發 margin（行為不變）。"""
    from dspx.typeset.format_config import compile_typst_vars, validate_format_config
    v = compile_typst_vars(validate_format_config({}))                       # 預設 a4-wide
    assert not any(x.startswith("margin=") for x in v)


def test_compile_typst_vars_preset_cas_native_warns_no_margin(capsys):
    from dspx.typeset.format_config import compile_typst_vars, validate_format_config
    v = compile_typst_vars(validate_format_config({"page": {"preset": "cas-native"}}))
    assert not any(x.startswith("margin=") for x in v)                       # 不映射
    assert "cas-native" in capsys.readouterr().err                          # 一行警告


def test_compile_typst_vars_first_line_indent_set():
    from dspx.typeset.format_config import compile_typst_vars, validate_format_config
    v = compile_typst_vars(validate_format_config({"par": {"first_line_indent": 2}}))
    assert "first-line-indent=2em" in v


def test_compile_typst_vars_first_line_indent_zero():
    from dspx.typeset.format_config import compile_typst_vars, validate_format_config
    v = compile_typst_vars(validate_format_config({"par": {"first_line_indent": 0}}))
    assert "first-line-indent=0em" in v                                     # 0＝明確關縮排（仍發）


def test_compile_typst_vars_first_line_indent_unset():
    from dspx.typeset.format_config import compile_typst_vars, validate_format_config
    v = compile_typst_vars(validate_format_config({}))
    assert not any(x.startswith("first-line-indent=") for x in v)           # 未設＝交 profile、不發


@pytest.mark.parametrize("bad", [
    {"par": {"first_line_indent": 9}},        # 超範圍（>4）
    {"par": {"first_line_indent": -1}},       # 低於 0
    {"par": {"first_line_indent": "2em"}},    # 型別錯（非數值）
])
def test_validate_rejects_bad_first_line_indent(bad):
    with pytest.raises(FormatConfigError):
        validate_format_config(bad)


def test_typst_knob_followups_no_longer_names_page():
    """未映射 follow-up 只剩 table.*（page margin/preset 已接線、脫離清單）。"""
    from dspx.typeset.format_config import _TYPST_KNOB_FOLLOWUPS
    joined = " ".join(_TYPST_KNOB_FOLLOWUPS)
    assert "page" not in joined and "margin" not in joined
    assert "table" in joined
