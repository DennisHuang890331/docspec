"""export-dx-batch export 層：--template 內容物路由、eject、pack 閘訊息、pandoc 清單決策(D7)、
標題去編號後處理(D8)。

pandoc/typst 端到端缺工具則 skip；路由/去編號/閘訊息等純邏輯不需工具。
"""

from __future__ import annotations

import json

import pytest

from dspx.engine import paths
from dspx.commands import export as export_cmd
from dspx.commands.export import template_cmd
from dspx.commands.export._config import _PANDOC_FROM
from dspx.commands.export._pack_gate import _check_pack_integrity
from dspx.commands.export._preprocess import _denumber_manual_headings
from dspx.engine.config import load_config
from dspx.engine.layout import Layout

_HAVE_PANDOC = paths.resolve_pandoc() is not None


def _setup(make_project, body="# 標題\n\n中文內容。\n", *, version="1.0.0", article="g",
           config_text="language: zh-TW\ndocs_layout: per-article\n"):
    home = make_project(config_text)
    layout = Layout(home, "per-article")
    snap = layout.docs_snapshot(article, version)
    snap.parent.mkdir(parents=True, exist_ok=True)
    snap.write_text(body, encoding="utf-8")
    return home, layout


# ── D5：--template 內容物路由 ─────────────────────────────────────

def test_route_by_template_typ(tmp_path):
    d = tmp_path / "pack"; d.mkdir()
    (d / "template.typ").write_text("// typst", encoding="utf-8")
    assert export_cmd._route_by_template(d) == "typst"


def test_route_by_template_tex(tmp_path):
    d = tmp_path / "pack"; d.mkdir()
    (d / "template.tex").write_text("% latex", encoding="utf-8")
    assert export_cmd._route_by_template(d) == "journal"


def test_route_by_template_both_requires_engine(tmp_path, capsys):
    d = tmp_path / "pack"; d.mkdir()
    (d / "template.typ").write_text("x", encoding="utf-8")
    (d / "template.tex").write_text("y", encoding="utf-8")
    assert export_cmd._route_by_template(d) is None
    assert "--engine" in capsys.readouterr().err


def test_route_by_template_neither_rejected(tmp_path, capsys):
    d = tmp_path / "pack"; d.mkdir()
    assert export_cmd._route_by_template(d) is None
    assert "neither" in capsys.readouterr().err


def test_route_by_template_missing_dir(tmp_path, capsys):
    assert export_cmd._route_by_template(tmp_path / "nope") is None
    assert "does not exist" in capsys.readouterr().err


def test_export_template_neither_errors_nonzero(make_project, monkeypatch, tmp_path, capsys):
    """--template 指向缺 template.typ/tex 的夾 → 非零、指名報缺、不 crash。"""
    home, _layout = _setup(make_project)
    monkeypatch.chdir(home.parent)
    empty = tmp_path / "empty"; empty.mkdir()
    assert export_cmd.run(["g", "--template", str(empty)]) == 1
    assert "neither" in capsys.readouterr().err


# ── D5：BYO Typst 包跳 hash 閘 / config export.template / 旗標覆寫 ─────

def _stub_build(monkeypatch):
    """把真 PDF build 換成擷取呼叫參數的替身（不需 pandoc/typst/字型）。"""
    captured = {}

    def _fake(pandoc, typst, typst_template, fonts_src, title, body_md, out, **kw):
        captured["template"] = typst_template
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"%PDF-1.4 fake")
    monkeypatch.setattr(export_cmd, "_build_pdf_typst", _fake)
    monkeypatch.setattr(export_cmd, "_pandoc_path", lambda: "pandoc")
    monkeypatch.setattr(paths, "resolve_typst", lambda: "typst")
    monkeypatch.setattr(paths, "resolve_fonts_dir", lambda *a, **k: fonts_dummy)
    return captured


fonts_dummy = None  # 佔位；於 test 內以 tmp_path 設定


def test_export_byo_typst_pack_skips_gate(make_project, monkeypatch, tmp_path):
    global fonts_dummy
    fonts_dummy = tmp_path / "fonts"; fonts_dummy.mkdir()
    home, _layout = _setup(make_project)
    monkeypatch.chdir(home.parent)
    pack = tmp_path / "mypack"; pack.mkdir()
    # 使用者包無 .pack-hashes.json（is_bundled=False → 跳閘）；隨意改 template.typ 也不被擋。
    (pack / "template.typ").write_text("// hand-edited BYO pack", encoding="utf-8")
    captured = _stub_build(monkeypatch)
    rc = export_cmd.run(["g", "--template", str(pack), "--no-verify"])
    assert rc == 0
    assert captured["template"] == pack / "template.typ"


def test_export_config_export_template_default_and_flag_override(make_project, monkeypatch, tmp_path):
    global fonts_dummy
    fonts_dummy = tmp_path / "fonts"; fonts_dummy.mkdir()
    home, _layout = _setup(
        make_project,
        config_text="language: zh-TW\ndocs_layout: per-article\nexport:\n  template: cfgpack\n")
    monkeypatch.chdir(home.parent)
    # config 指的包（相對專案根）
    cfgpack = home.parent / "cfgpack"; cfgpack.mkdir()
    (cfgpack / "template.typ").write_text("// from config", encoding="utf-8")
    captured = _stub_build(monkeypatch)
    assert export_cmd.run(["g", "--no-verify"]) == 0
    assert captured["template"] == cfgpack / "template.typ"          # config 生效
    # --template 旗標覆寫 config
    flagpack = tmp_path / "flagpack"; flagpack.mkdir()
    (flagpack / "template.typ").write_text("// from flag", encoding="utf-8")
    assert export_cmd.run(["g", "--template", str(flagpack), "--no-verify"]) == 0
    assert captured["template"] == flagpack / "template.typ"


# ── D5：ejected 包 provenance 落後提示 ────────────────────────────

def test_eject_provenance_lag_notice(tmp_path):
    pack = tmp_path / "pack"; pack.mkdir()
    (pack / ".ejected-from.json").write_text(json.dumps({"version": "0.0.1-old"}), encoding="utf-8")
    notice = export_cmd._eject_provenance_notice(pack)
    assert notice is not None and "0.0.1-old" in notice and "re-eject" in notice


def test_eject_provenance_same_version_no_notice(tmp_path):
    from dspx import __version__
    pack = tmp_path / "pack"; pack.mkdir()
    (pack / ".ejected-from.json").write_text(json.dumps({"version": __version__}), encoding="utf-8")
    assert export_cmd._eject_provenance_notice(pack) is None


def test_eject_provenance_absent_no_notice(tmp_path):
    pack = tmp_path / "pack"; pack.mkdir()
    assert export_cmd._eject_provenance_notice(pack) is None


# ── D5：docspec template eject 全流程 ─────────────────────────────

def test_template_eject_copies_records_and_excludes_baseline(make_project, monkeypatch):
    home = make_project()
    monkeypatch.chdir(home.parent)
    assert template_cmd.run(["eject"]) == 0
    dest = home / "template-pack"
    assert (dest / "template.typ").is_file()
    assert not (dest / paths.PACK_HASHES_FILE).exists()              # 排除 baseline
    prov = json.loads((dest / ".ejected-from.json").read_text(encoding="utf-8"))
    assert "version" in prov
    cfg = load_config(home)
    assert cfg["export"]["template"] == "docspec/template-pack"      # config 寫回


def test_template_eject_refuses_existing_without_force(make_project, monkeypatch, capsys):
    home = make_project()
    monkeypatch.chdir(home.parent)
    assert template_cmd.run(["eject"]) == 0
    assert template_cmd.run(["eject"]) == 1                          # 已存在→拒
    assert "already exists" in capsys.readouterr().err
    assert template_cmd.run(["eject", "--force"]) == 0               # --force 覆蓋


def test_ejected_pack_used_by_export_skips_gate(make_project, monkeypatch, tmp_path):
    """eject → export 無 --template → 自動用 ejected 包走 Typst 軌、跳閘。"""
    global fonts_dummy
    fonts_dummy = tmp_path / "fonts"; fonts_dummy.mkdir()
    home, _layout = _setup(make_project)
    monkeypatch.chdir(home.parent)
    assert template_cmd.run(["eject"]) == 0
    captured = _stub_build(monkeypatch)
    assert export_cmd.run(["g", "--no-verify"]) == 0
    assert captured["template"] == home / "template-pack" / "template.typ"


# ── D6：pack 閘訊息指向 eject + gen_pack_hashes、不含裸 --template ─────

def _tampered_pack(tmp_path):
    pack = tmp_path / "pack"; pack.mkdir(parents=True)
    (pack / "template.typ").write_text("orig", encoding="utf-8")
    baseline = paths.pack_content_hashes(pack)
    (pack / paths.PACK_HASHES_FILE).write_text(json.dumps(baseline), encoding="utf-8")
    (pack / "template.typ").write_text("HAND EDITED", encoding="utf-8")   # 竄改
    return pack


def test_pack_gate_refusal_points_to_eject_and_genhashes(tmp_path, capsys):
    pack = _tampered_pack(tmp_path)
    assert _check_pack_integrity(pack, is_bundled=True, allow=False) == 1
    err = capsys.readouterr().err
    assert "docspec template eject" in err
    assert "gen_pack_hashes.py" in err
    assert "--template <dir>" not in err                            # 誤導出口移除


def test_pack_gate_allow_and_user_pack_skip(tmp_path, capsys):
    pack = _tampered_pack(tmp_path)
    assert _check_pack_integrity(pack, is_bundled=True, allow=True) == 0   # --allow 放行
    pack2 = _tampered_pack(tmp_path / "u")
    assert _check_pack_integrity(pack2, is_bundled=False, allow=False) == 0  # 使用者包跳閘


# ── D7：+lists_without_preceding_blankline 實測否決（不採用）─────────

def test_pandoc_from_does_not_enable_lists_extension():
    """實測：該擴充在受控 pandoc 上使硬換行散文行首 `- ` 反被切成清單（引入 design 想防的
    false-positive），故不採用。此測釘死決策，避免日後誤加。"""
    assert "lists_without_preceding_blankline" not in _PANDOC_FROM


@pytest.mark.skipif(not _HAVE_PANDOC, reason="需要 pandoc")
def test_pandoc_hard_wrapped_dash_stays_prose():
    """現狀 _PANDOC_FROM（不開擴充）＝硬換行散文續行行首 `- ` 正確保留為散文、不成 bullet list。"""
    import subprocess
    pandoc = paths.resolve_pandoc()
    md = "這是一段散文的開頭句子。\n- 這是硬換行後以破折號開頭的續行內容\n更多散文。\n"
    out = subprocess.run([pandoc, "-f", _PANDOC_FROM, "-t", "typst"],
                         input=md, capture_output=True, text=True, encoding="utf-8").stdout
    # typst bullet list item 會有獨立行首 "- "；散文則 `-` 內嵌於段落文字中。
    assert not any(ln.lstrip().startswith("- ") for ln in out.splitlines())


# ── D8：手寫編號標題去除模板自動編號 ─────────────────────────────

@pytest.mark.parametrize("text,expect_rewrite", [
    ("3.2 系統架構", True),          # 十進位層級
    ("3. 系統架構", True),           # 單層＋尾點
    ("§ 3 範圍", True),              # § 編號
    ("Annex A", True),              # Annex
    ("附錄 A", True),               # 附錄（空格）
    ("附錄B", True),                # 附錄（無空格）
    ("A.1 詞彙", True),             # 字母.數字
    ("系統概述", False),            # 無手寫編號
    ("2026 年度計畫", False),       # 數字後無點分隔＝非編號、不誤傷
    ("概述 3 項要點", False),       # 數字非行首
])
def test_denumber_heading_matches(text, expect_rewrite):
    src = f"= {text}\n<label>\n內文。\n"
    out = _denumber_manual_headings(src)
    if expect_rewrite:
        assert out.startswith(f"#heading(level: 1, numbering: none)[{text}]")
    else:
        assert out.startswith(f"= {text}")            # 原樣不動


def test_denumber_respects_heading_level():
    out = _denumber_manual_headings("=== 1.2.3 深層節\n")
    assert out.startswith("#heading(level: 3, numbering: none)[1.2.3 深層節]")


def test_denumber_skips_fenced_code():
    src = "```\n= 1. 這是 code 區\n```\n= 2.1 真標題\n"
    out = _denumber_manual_headings(src)
    assert "= 1. 這是 code 區" in out                 # code 區內不動
    assert "#heading(level: 1, numbering: none)[2.1 真標題]" in out


def test_denumber_leaves_plain_headings_untouched():
    src = "= 系統架構\n= 詳細設計\n"
    assert _denumber_manual_headings(src) == src


@pytest.mark.skipif(not _HAVE_PANDOC, reason="需要 pandoc")
def test_pandoc_single_line_heading_shape_pinned():
    """釘住 pandoc `-t typst` 的單行 heading 形狀假設：`= <text>`（label 在下一行）。
    pandoc 升版若改輸出形狀，此測先炸（而非後處理靜默漏改）。"""
    import subprocess
    pandoc = paths.resolve_pandoc()
    md = "## 3.2 系統架構\n\n內文。\n"
    typ = subprocess.run([pandoc, "-f", _PANDOC_FROM, "-t", "typst", "--shift-heading-level-by=-1"],
                         input=md, capture_output=True, text=True, encoding="utf-8").stdout
    assert "= 3.2 系統架構" in typ                     # 單行 heading 假設成立
    assert "#heading(level: 1, numbering: none)[3.2 系統架構]" in _denumber_manual_headings(typ)
