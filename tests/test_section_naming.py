"""corpus-section-naming：marker 空格容忍（round-trip）＋ put 首寫的路徑安全驗證。"""

from __future__ import annotations

import pytest

from dspx.commands.deliverable import render as render_cmd
from dspx.engine.render import (
    GROUP_MARKER_RE,
    MARKER_RE,
    group_marker,
    parse_section_bodies,
    section_marker,
)

# ── Task 0：marker 路徑容忍空白 ──

# 任意合法路徑字元：半形空格、全形空格（U+3000）、CJK、括號
SPACED_PATHS = [
    "spec/附錄 A",
    "spec/附錄　乙",
    "g/scope (draft)/子節",
    "指南/簡介",
]


@pytest.mark.parametrize("path", SPACED_PATHS)
def test_marker_write_parse_symmetry(path):
    """寫入端 section_marker/group_marker → 讀回端 regex，路徑逐字相等（含空白）。"""
    m = MARKER_RE.match(section_marker(path))
    assert m and m.group(1) == path
    g = GROUP_MARKER_RE.match(group_marker(path))
    assert g and g.group(1) == path


def test_parse_section_bodies_roundtrip_with_spaces():
    """render 寫出的 marker 集合 → parse 讀回集合逐一相等（含空格路徑的散文歸對節）。"""
    text = "\n".join([
        "---", "article: g", "---", "",
        section_marker("g/intro"), "## 概覽", "", "前節散文。", "",
        section_marker("g/附錄 A"), "## 附錄 A", "", "附錄散文。", "",
        section_marker("g/附錄　乙"), "## 附錄乙", "", "全形空格節散文。", "",
    ])
    bodies = parse_section_bodies(text)
    assert set(bodies) == {"g/intro", "g/附錄 A", "g/附錄　乙"}
    assert bodies["g/附錄 A"] == "附錄散文。"
    assert bodies["g/附錄　乙"] == "全形空格節散文。"
    assert bodies["g/intro"] == "前節散文。"   # 前節不被吸入後節內容


def test_render_preserves_prose_in_spaced_sections(make_project, write_leaf, monkeypatch):
    """帶空格路徑 end-to-end：render→寫散文→再 render，散文保留、前節 prose 指紋不變。"""
    from dspx.engine.layout import Layout
    from dspx.engine.render import read_ledger
    home = make_project()
    write_leaf(home, "g/intro", concept={"id": "c1", "title": "概覽", "order": 1})
    write_leaf(home, "g/附錄 A", concept={"id": "c2", "title": "附錄 A", "order": 2})
    write_leaf(home, "g/附 錄/子節", concept={"id": "c3", "title": "子節", "order": 3})
    monkeypatch.chdir(home.parent)
    assert render_cmd.run(["g"]) == 0
    latest = home.parent / "docs" / "g" / "_latest.md"
    text = latest.read_text(encoding="utf-8")
    assert section_marker("g/附錄 A") in text
    assert group_marker("g/附 錄") in text          # 帶空格的分組標記也寫得出
    # 模擬 draft：三節都寫散文
    # 章號：無 order 的分組 g/附 錄 以 0.0 排最前＝1.（子節 1.1），概覽=2.、附錄 A=3.
    text = text.replace("## 2. 概覽\n", "## 2. 概覽\n\n前節散文。\n")
    text = text.replace("## 3. 附錄 A\n", "## 3. 附錄 A\n\n附錄散文。\n")
    text = text.replace("### 1.1 子節\n", "### 1.1 子節\n\n子節散文。\n")
    latest.write_text(text, encoding="utf-8")
    assert render_cmd.run(["g"]) == 0
    ledger1 = read_ledger(Layout(home), "g")
    assert set(ledger1) == {"g/intro", "g/附錄 A", "g/附 錄/子節"}
    intro_prose = ledger1["g/intro"]["prose"]
    # 再 render：散文原樣保留、前節 prose 指紋不變（無假 drift、無靜默丟失）
    assert render_cmd.run(["g"]) == 0
    text2 = latest.read_text(encoding="utf-8")
    assert "附錄散文。" in text2 and "子節散文。" in text2 and "前節散文。" in text2
    ledger2 = read_ledger(Layout(home), "g")
    assert ledger2["g/intro"]["prose"] == intro_prose
    assert set(ledger2) == set(ledger1)


def test_lint_segments_attribute_spaced_sections():
    """lint 歸節與 render 同一 regex：帶空格路徑的段落歸對節（不回退檔案級）。"""
    from dspx.engine.lint import _split_marker_segments
    body = "\n".join([
        section_marker("g/附錄 A"), "## 附錄 A", "", "附錄文字。", "",
        group_marker("g/附 錄"), "### 附 錄", "",
    ])
    sections = [s for s, _ in _split_marker_segments(body)]
    assert "g/附錄 A" in sections
    assert "g/附 錄" in sections


# ── Task 1：new 的路徑安全驗證（拒建矩陣）──

REJECTED_PATHS = [
    "spec/CON",              # Windows 保留裝置名
    "spec/nul/範圍",         # 保留名在巢狀中段、小寫
    "spec/con.md",           # 保留名＋副檔名形式
    "spec/LPT1",
    "spec/範圍:邊界",        # 非法字元 :
    "spec/a<b",              # 非法字元 <
    "spec/a|b?c*",           # 非法字元 | ? *
    "spec/a\\b",             # 反斜線（Windows pathlib 視為分隔符）
    "spec/a\x01b",           # ASCII 控制字元
    "spec/適用範圍 ",        # 結尾空格
    "spec/end.",             # 結尾點
    "spec/ 頭空格",          # 開頭空格（破 marker round-trip）
    "spec/../x",             # ..
    "spec/./x",              # .
    "spec//x",               # 空段
    "_archive/ghost",        # _ 前綴＝引擎隱形區
    "spec/_draft/範圍",      # _ 前綴在中段
]


def _put_concept(home, tmp_path, section, exit_expected=0):
    """經 put 首寫 concept（★retire-develop-workbench：put＝唯一建節入口、路徑驗證隨之搬家）。"""
    from dspx.commands.corpus import put as put_cmd
    cpt = tmp_path / "_c.yaml"
    cpt.write_text("title: 測\nstatus: draft\nconcept: 一句話\n", encoding="utf-8")
    return put_cmd.run([section, "concept", str(cpt)])


@pytest.mark.parametrize("path", REJECTED_PATHS)
def test_put_rejects_dangerous_path(path, make_project, monkeypatch, capsys):
    """命中黑名單 → exit 非零、訊息指明壞段、corpus 無任何檔被建立（驗證在寫入之前）。"""
    from dspx.commands.corpus import put as put_cmd
    home = make_project()
    monkeypatch.chdir(home.parent)
    assert put_cmd.run([path, "concept", "-"]) == 2
    err = capsys.readouterr().err
    assert "refusing to write" in err and "invalid path segment" in err
    assert not (home / "corpus").exists()


def test_put_accepts_legal_chinese_path(make_project, monkeypatch, capsys, tmp_path):
    """合法中文路徑照常首寫：記錄進 store、零散檔、零工作台目錄、無任何警告。"""
    home = make_project()
    monkeypatch.chdir(home.parent)
    assert _put_concept(home, tmp_path, "測試文章/適用範圍") == 0
    assert capsys.readouterr().err == ""
    assert (home / "corpus" / "測試文章" / "article.yaml").is_file()   # dossier-layout 案卷
    assert not list((home / "corpus" / "測試文章").rglob("concept.yaml"))   # 零散檔
    assert not (home / "work").exists()                   # 零工作台目錄


def test_put_accepts_spaced_and_numbered_names(make_project, monkeypatch, tmp_path):
    """段內空格與含數字的章名合法（引擎不做語義判斷）；`第 3 層防護` 這類名不誤殺。"""
    home = make_project()
    monkeypatch.chdir(home.parent)
    assert _put_concept(home, tmp_path, "手冊/第 3 層防護") == 0
    assert _put_concept(home, tmp_path, "手冊/附錄 A") == 0
