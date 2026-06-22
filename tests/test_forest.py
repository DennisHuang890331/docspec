"""森林地圖架構不變式：單向、derive（無第二份）、平行＝無邊、地圖只投 develop、
約束＝audit-only 非阻塞（無新引擎硬閘）。每條對應一個拍板的設計決策。"""

from __future__ import annotations

import yaml

from dspx.aperture import project
from dspx.check import run_check
from dspx.commands import impact as impact_cmd
from dspx.forest import forest_view
from dspx.layout import Layout
from dspx.model import load_project
from dspx.schema import load_schema


def _leaves(home):
    return load_project(Layout(home))


def _project(home, skill, section):
    layout = Layout(home)
    leaves = load_project(layout)
    return project(layout, load_schema(), skill, section, leaves)


def _two_tree_governed(make_project, write_leaf):
    """t2 governed-by t1（兩棵 root 樹、一條跨樹治理邊）。"""
    home = make_project()
    write_leaf(home, "t1", concept={"id": "c-t1", "title": "T1", "order": 1,
                                    "status": "draft", "concept": "T1 主旨",
                                    "brief": {"範圍": "一"}})
    write_leaf(home, "t2", concept={"id": "c-t2", "title": "T2", "order": 1,
                                    "status": "draft", "concept": "T2 主旨",
                                    "brief": {"範圍": "二"}, "governed-by": ["c-t1"]})
    return home


# ── 單向：父不存子，反向只由 impact 算 ──
def test_single_direction_parent_stores_no_child(make_project, write_leaf, monkeypatch, capsys):
    home = _two_tree_governed(make_project, write_leaf)
    # t1 自己的 concept 沒有任何指向 t2 的欄位（父不存子）
    t1_raw = yaml.safe_load(
        (home / "corpus" / "t1" / "concept.yaml").read_text(encoding="utf-8"))
    assert "governed-by" not in t1_raw
    assert all("c-t2" not in str(v) and "t2" != v for v in t1_raw.values())

    # 反向只由 impact 算出：impact c-t1 列出 governed-by ← t2
    monkeypatch.chdir(home.parent)
    assert impact_cmd.run(["c-t1"]) == 0
    out = capsys.readouterr().out
    assert "governed-by ← t2" in out


def test_impact_governed_by_json(make_project, write_leaf, monkeypatch, capsys):
    home = _two_tree_governed(make_project, write_leaf)
    monkeypatch.chdir(home.parent)
    import json
    assert impact_cmd.run(["c-t1", "--json"]) == 0
    info = json.loads(capsys.readouterr().out)
    assert info["governedBy"] == ["t2"]


# ── derive（無第二份）：刪掉 governed-by → hierarchy 立刻消失 ──
def test_forest_hierarchy_derives_from_governed_by(make_project, write_leaf):
    home = _two_tree_governed(make_project, write_leaf)
    f = forest_view(_leaves(home))
    assert any(h["childDoc"] == "t2" and h["parentDoc"] == "t1" for h in f["hierarchy"])
    assert f["hierarchy"][0]["via"] == [["c-t2", "c-t1"]]

    # 拿掉 t2 的 governed-by → hierarchy 立刻空（證明 derive 自 concept.governed-by，無第二存）
    write_leaf(home, "t2", concept={"id": "c-t2", "title": "T2", "order": 1,
                                    "status": "draft", "concept": "T2 主旨",
                                    "brief": {"範圍": "二"}})
    f2 = forest_view(_leaves(home))
    assert f2["hierarchy"] == []


# ── 平行＝無邊 ──
def test_parallel_is_no_edge(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "t1", concept={"id": "c-t1", "title": "T1", "order": 1,
                                    "status": "draft", "concept": "T1 主旨", "brief": {}})
    write_leaf(home, "t2", concept={"id": "c-t2", "title": "T2", "order": 1,
                                    "status": "draft", "concept": "T2 主旨", "brief": {}})
    f = forest_view(_leaves(home))
    assert f["hierarchy"] == []
    assert ["t1", "t2"] in f["parallel"]


def test_governed_pair_not_parallel(make_project, write_leaf):
    home = _two_tree_governed(make_project, write_leaf)
    f = forest_view(_leaves(home))
    assert ["t1", "t2"] not in f["parallel"]
    assert f["parallel"] == []


# ── 文件清單一句話 derive 自 root.concept ──
def test_documents_one_liner(make_project, write_leaf):
    home = _two_tree_governed(make_project, write_leaf)
    f = forest_view(_leaves(home))
    docs = {d["article"]: d for d in f["documents"]}
    assert docs["t1"]["oneLiner"] == "T1 主旨"
    assert docs["t1"]["conceptId"] == "c-t1"
    assert docs["t2"]["status"] == "draft"


# ── 地圖只投 develop ──
def test_map_only_develop(make_project, write_leaf):
    home = _two_tree_governed(make_project, write_leaf)
    assert isinstance(_project(home, "develop", "t2").forest, dict)
    for other in ("draft", "edit", "factcheck", "publish"):
        assert _project(home, other, "t2").forest is None


def test_develop_prints_forest_map(make_project, write_leaf, monkeypatch, capsys):
    home = _two_tree_governed(make_project, write_leaf)
    monkeypatch.chdir(home.parent)
    from dspx.commands import instructions as instr
    assert instr.run(["develop", "t2"]) == 0
    out = capsys.readouterr().out
    assert "Forest map" in out
    assert "t2 → t1" in out

    # draft 投影沒有森林地圖段
    assert instr.run(["draft", "t2"]) == 0
    assert "森林地圖" not in capsys.readouterr().out


# ── 約束＝audit-only 非阻塞：語義牴觸但結構合法 → check 綠、可 ready ──
def test_governed_by_adds_no_semantic_gate(make_project, write_leaf, monkeypatch):
    """t2 的 concept 語義上「牴觸」其 governed-by 父 t1，但結構（死引用/環）合法
    → run_check 仍綠（引擎只做結構檢查、不判語義、不新增硬閘）。"""
    home = make_project()
    full_brief = {"audience": "人", "depth": "gate", "breadth": "全", "forbidden": "無"}
    write_leaf(home, "t1", concept={"id": "c-t1", "title": "T1", "order": 1,
                                    "status": "draft",
                                    "concept": "一律使用公制單位", "brief": full_brief})
    write_leaf(home, "t2", concept={"id": "c-t2", "title": "T2", "order": 2,
                                    "status": "draft",
                                    "concept": "一律使用英制單位（直接牴觸 c-t1）",
                                    "brief": full_brief, "governed-by": ["c-t1"]})
    res = run_check(_leaves(home), load_schema())
    assert res.ok is True      # 語義牴觸不擋＝引擎不判語義

    # 且能畢業（ready）：給可榨乾的 develop + 完整 yaml
    write_leaf(home, "t2", concept={"id": "c-t2", "title": "T2", "order": 2,
                                    "status": "draft",
                                    "concept": "一律使用英制單位（直接牴觸 c-t1）",
                                    "brief": full_brief, "governed-by": ["c-t1"]},
               decisions=[{"id": "d-t2", "kind": "normative", "status": "accepted",
                           "statement": "用英制"}],
               develop="<!-- drained -->")
    monkeypatch.chdir(home.parent)
    from dspx.commands import ready as ready_cmd
    assert ready_cmd.run(["t2"]) == 0
    assert not (home / "corpus" / "t2" / "develop.md").exists()
