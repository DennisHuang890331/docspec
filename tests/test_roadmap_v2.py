"""唯一一份專案 roadmap（第一期第 7 步）：推導狀態、豁免、卡住、前一代轉換、change 晉升。"""

from __future__ import annotations

import json

import pytest

from dspx.check import run_check
from dspx.commands.change import change as change_cmd
from dspx.commands.governance import roadmap as roadmap_cmd
from dspx.commands.governance import ruling as ruling_cmd
from dspx.engine import change as chg
from dspx.engine import governance as gv
from dspx.engine import roadmap_v2 as rv
from dspx.engine.layout import Layout
from dspx.engine.model import load_project
from dspx.engine.schema import load_schema


@pytest.fixture
def project(make_project, write_leaf, monkeypatch):
    home = make_project()
    write_leaf(home, "guide", concept={"id": "c-guide", "title": "說明書", "order": 0,
                                       "concept": "說明", "brief": {"audience": "x", "depth": "y",
                                                                   "breadth": "z"}})
    write_leaf(home, "guide/ch3", concept={"id": "c-ch3", "title": "第三章", "order": 1,
                                           "concept": "資料管理"})
    (home / "governance").mkdir()
    monkeypatch.chdir(home.parent)
    monkeypatch.setenv("DOCSPEC_AGENT", "claude")
    return home


def _view(capsys):
    capsys.readouterr()
    assert roadmap_cmd.run(["--json"]) == 0
    return json.loads(capsys.readouterr().out)


def _status(view, wid):
    for group in [m["items"] for m in view["milestones"]] + [view["unassigned"]]:
        for r in group:
            if r["id"] == wid:
                return r["status"]
    for kids in view["children"].values():
        for r in kids:
            if r["id"] == wid:
                return r["status"]
    raise KeyError(wid)


def test_milestone_types_and_progress(project, capsys):
    assert roadmap_cmd.run(["milestone", "--title", "F-2 第三季查核", "--type", "checkpoint",
                            "--due", "2026/09/30"]) == 0
    assert roadmap_cmd.run(["add", "--title", "寫第三章", "--milestone", "M-claude-1",
                            "--target", "guide/ch3"]) == 0
    assert roadmap_cmd.run(["add", "--title", "盤點報告", "--milestone", "M-claude-1"]) == 0
    v = _view(capsys)
    m = v["milestones"][0]
    assert (m["type"], m["done"], m["total"]) == ("checkpoint", 0, 2)
    assert _status(v, "W-claude-1") == "not-started"          # 章節尚未寫
    assert roadmap_cmd.run(["done", "W-claude-2", "--note", "報告已交"]) == 0
    v = _view(capsys)
    assert _status(v, "W-claude-2") == "done"
    assert v["milestones"][0]["done"] == 1


def test_done_items_stay_and_waivers_are_visible(project, capsys, monkeypatch):
    """驗收情境 S5 的 roadmap 半：change 封存但有經裁定豁免的項目 → 完成（含豁免）。"""
    ruling_cmd.run(["add", "--quote", "車輛 bag 還沒有，先不驗", "--read-back", "車輛 bag 相容性先不驗", "--confirmed", "對"])
    roadmap_cmd.run(["add", "--title", "資料庫功能", "--ref", "change:dataset-library"])
    monkeypatch.setattr(chg, "all_change_states", lambda layout: {"dataset-library": "active"})
    assert _status(_view(capsys), "W-claude-1") == "in-progress"
    monkeypatch.setattr(chg, "all_change_states", lambda layout: {"dataset-library": "archived"})
    assert roadmap_cmd.run(["waive", "W-claude-1", "--ruling", "RL-claude-1",
                            "--note", "車輛 bag 相容性未驗證", "--reopen-when", "拿到真車 bag"]) == 0
    v = _view(capsys)
    assert _status(v, "W-claude-1") == "done-waived"
    item = v["unassigned"][0]
    assert rv.status_label(item["status"], item) == "完成（含豁免 1 項）"
    assert (project / "governance" / "roadmap" / "W-claude-1.yaml").is_file()   # 做完仍保留


def test_depends_on_and_suspects_block(project, capsys):
    roadmap_cmd.run(["add", "--title", "先做 A"])
    roadmap_cmd.run(["add", "--title", "再做 B", "--depends-on", "W-claude-1", "--target", "guide/ch3"])
    assert _status(_view(capsys), "W-claude-2") == "blocked"
    roadmap_cmd.run(["done", "W-claude-1", "--note", "ok"])
    assert _status(_view(capsys), "W-claude-2") == "not-started"
    layout = Layout(project)
    gv.write_record(layout, "suspect", {"id": "S-claude-1", "trigger": "D-claude-1",
                                        "target": "W-claude-2", "status": "open",
                                        "created-at": "2026-09-29"})
    assert _status(_view(capsys), "W-claude-2") == "blocked"


def test_parent_rolls_up_children(project, capsys):
    roadmap_cmd.run(["add", "--title", "標註工具"])
    roadmap_cmd.run(["add", "--title", "首頁", "--parent", "W-claude-1"])
    roadmap_cmd.run(["add", "--title", "匯出", "--parent", "W-claude-1"])
    roadmap_cmd.run(["done", "W-claude-2", "--note", "ok"])
    assert _status(_view(capsys), "W-claude-1") == "in-progress"
    roadmap_cmd.run(["done", "W-claude-3", "--note", "ok"])
    assert _status(_view(capsys), "W-claude-1") == "done"


def test_dead_refs_are_check_errors(project):
    roadmap_cmd.run(["add", "--title", "x", "--ref", "change:nope,doc:guide/nope,bogus:1"])
    layout = Layout(project)
    errs = run_check(load_project(layout), load_schema(), layout).errors
    assert any("\"change:nope\" points to nothing" in e for e in errs)
    assert any("\"doc:guide/nope\" points to nothing" in e for e in errs)
    assert any("must start with change:, doc: or gov:" in e for e in errs)


def test_change_promotion_links_instead_of_collapsing(project, capsys):
    roadmap_cmd.run(["add", "--title", "改寫第三章", "--what", "依新裁定改寫", "--target", "guide/ch3"])
    assert change_cmd.run(["new", "rewrite-ch3", "--publish", "advisory",
                           "--from-roadmap", "W-claude-1"]) == 0
    rec = gv.load_record(gv.record_path(Layout(project), "work", "W-claude-1"), "work")
    assert rec["refs"] == ["doc:guide/ch3", "change:rewrite-ch3"]
    assert rec["title"] == "改寫第三章"                          # 沒有被收攏


def test_migrate_legacy_roadmap(make_project, write_leaf, monkeypatch, capsys):
    home = make_project()
    write_leaf(home, "guide", concept={"id": "c-guide", "title": "說明書", "order": 0,
                                       "concept": "說明", "brief": {"audience": "x", "depth": "y",
                                                                   "breadth": "z"}})
    write_leaf(home, "guide/ch3", concept={"id": "c-ch3", "title": "第三章", "order": 1,
                                           "concept": "資料管理"})
    monkeypatch.chdir(home.parent)
    # 前一代：無治理層，roadmap add 走舊路（R 編號、分文件存）
    assert roadmap_cmd.run(["add", "--kind", "gap", "--title", "缺章", "--target", "c-ch3"]) == 0
    assert roadmap_cmd.run(["add", "--kind", "task", "--title", "跨文件", "--target", "forest",
                            "--depends-on", "R1"]) == 0
    assert roadmap_cmd.run(["add", "--kind", "task", "--title", "小事", "--target", "forest"]) == 0
    assert roadmap_cmd.run(["done", "R3", "--note", "做完了"]) == 0
    monkeypatch.setenv("DOCSPEC_AGENT", "claude")
    capsys.readouterr()
    assert roadmap_cmd.run(["migrate"]) == 0
    out = capsys.readouterr().out
    assert "R1 -> W-claude-1" in out
    layout = Layout(home)
    gov = gv.load_governance(layout)
    by_legacy = {w["legacy-id"]: w for w in gov.work}
    assert by_legacy["R1"]["refs"] == ["doc:guide/ch3"]
    assert by_legacy["R2"]["depends-on"] == [by_legacy["R1"]["id"]]
    assert by_legacy["R3"]["closed"]["note"] == "做完了"
    assert not (home / "roadmap.yaml").exists()
    assert not (home / "roadmap-archive.yaml").exists()
    errs = run_check(load_project(layout), load_schema(), layout).errors
    assert errs == []
    # 轉換後 roadmap 指令改走新模型
    capsys.readouterr()
    assert roadmap_cmd.run(["--json"]) == 0
    assert len(json.loads(capsys.readouterr().out)["unassigned"]) == 3
    assert roadmap_cmd.run(["migrate"]) == 0                    # 冪等
