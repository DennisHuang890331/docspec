"""跨文件共享概念：realizes 撈真相、deps→stale-upstream、反向索引視圖。"""

from __future__ import annotations

import yaml

from dspx.engine.aperture import project
from dspx.commands.deliverable import render as render_cmd
from dspx.commands.query.status import _docs_hashes, _leaf_row
from dspx.engine.crossref import build_reverse_indices
from dspx.engine.layout import Layout
from dspx.engine.model import decision_index, load_project
from dspx.engine.schema import load_schema


def _shared_project(make_project, write_leaf):
    """SC 持有狀態機真相；OCC 鏡像節 realizes 它（跨文件）。"""
    home = make_project()
    write_leaf(home, "sc/state-machine",
               concept={"id": "p-sc", "title": "狀態機", "order": 1},
               decisions=[{"id": "d-sm-states", "kind": "normative", "status": "accepted",
                           "statement": "頂層狀態為 OFFLINE/IDLE/EXECUTING/FAULT 四態。"}])
    write_leaf(home, "occ/mirror",
               concept={"id": "occ-mirror", "title": "鏡像", "order": 1,
                        "concept": "OCC 被動鏡像", "brief": {"受眾": "後端"},
                        "realizes": ["d-sm-states"]})
    return home


def test_aperture_follows_realizes(make_project, write_leaf):
    """② draft 渲染 occ/mirror 時，看得到 d-sm-states 的真相。"""
    home = _shared_project(make_project, write_leaf)
    layout = Layout(home)
    leaves = load_project(layout)
    proj = project(layout, load_schema(), "apply", "occ/mirror", leaves)
    assert len(proj.realized) == 1
    r = proj.realized[0]
    assert r["id"] == "d-sm-states"
    assert "四態" in r["statement"]
    assert r["from_section"] == "sc/state-machine"


def test_change_shared_truth_makes_consumer_stale_upstream(make_project, write_leaf, monkeypatch):
    """③ 改 SC 真相 → OCC 鏡像 stale-upstream（不是 stale-own）。"""
    home = _shared_project(make_project, write_leaf)
    monkeypatch.chdir(home.parent)
    render_cmd.run(["occ"])
    latest = home.parent / "docs" / "occ" / "_latest.md"
    latest.write_text(
        latest.read_text(encoding="utf-8").replace("## 1. 鏡像\n", "## 1. 鏡像\n\nOCC 鏡像四態。\n"),
        encoding="utf-8")
    render_cmd.run(["occ"])   # 定基準（含 deps 指紋）

    def sync_of(section):
        layout = Layout(home)
        leaves = load_project(layout)
        by = {lf.section: lf for lf in leaves}
        from dspx.engine.schema import load_schema
        return _leaf_row(layout, by[section], load_schema(), True, _docs_hashes(layout, "occ"),
                         by, decision_index(leaves))["sync"]

    assert sync_of("occ/mirror") == "synced"
    # 改 SC 的共享真相（OCC 自己的檔沒動）★store-only：改 store 記錄的 decisions
    write_leaf.edit_replace(home, "sc/state-machine", "四態。", "五態（加 SUSPENDED）。",
                            category="decisions")
    assert sync_of("occ/mirror") == "stale-upstream"   # ★跨文件依賴觸發


def test_deps_only_tracks_statement_not_rationale(make_project, write_leaf, monkeypatch):
    """改被 realizes 決策的 rationale（statement 不變）→ 不該 stale。"""
    home = _shared_project(make_project, write_leaf)
    # 給共享決策補個 rationale ★store-only：改 store 記錄的 decisions 欄位
    write_leaf.edit_decision(home, "sc/state-machine", 0, rationale="舊理由")
    monkeypatch.chdir(home.parent)
    render_cmd.run(["occ"])
    latest = home.parent / "docs" / "occ" / "_latest.md"
    latest.write_text(latest.read_text(encoding="utf-8").replace("## 1. 鏡像\n", "## 1. 鏡像\n\n內文。\n"),
                      encoding="utf-8")
    render_cmd.run(["occ"])

    write_leaf.edit_decision(home, "sc/state-machine", 0,
                             rationale="新理由（statement 沒動）")

    layout = Layout(home)
    leaves = load_project(layout)
    by = {lf.section: lf for lf in leaves}
    from dspx.engine.schema import load_schema
    sync = _leaf_row(layout, by["occ/mirror"], load_schema(), True, _docs_hashes(layout, "occ"),
                     by, decision_index(leaves))["sync"]
    assert sync == "synced"   # rationale 變、statement 沒變 → 不觸發


def test_reverse_realizes_view(make_project, write_leaf):
    """反向索引：d-sm-states 被 occ/mirror realize（跨文件）；反向 ≡ 正向反轉（同源）。"""
    home = _shared_project(make_project, write_leaf)
    leaves = load_project(Layout(home))
    ri = build_reverse_indices(leaves)
    assert [lf.section for lf in ri.reverse_realizes["d-sm-states"]] == ["occ/mirror"]
    # 同源斷言：leaf∈reverse_realizes[d] ⟺ d∈leaf.realizes（全掃）
    for d, lfs in ri.reverse_realizes.items():
        for lf in lfs:
            assert d in [str(x) for x in (lf.concept.get("realizes") or [])]
