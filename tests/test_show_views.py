"""show 分類視圖：--decisions / --concepts / --material（正向橫看某一分類）。

--decisions --all-status 取代已刪的 retire 報告（死決策就地在 decisions.yaml）。
tree 與 store 兩 backend 都要對（load_model backend-neutral）。
"""

from __future__ import annotations

import json

from dspx.commands.corpus import store as store_cmd
from dspx.commands.query import show as show_cmd


def _corpus(home, write_leaf):
    write_leaf(home, "g", concept={"id": "c-root", "title": "根", "order": 1,
                                   "concept": "整篇", "brief": {"audience": "工程師",
                                   "depth": "深", "breadth": "廣"}})
    write_leaf(home, "g/intro", concept={"id": "c-in", "title": "簡介", "order": 2,
                                         "concept": "新手第一課",
                                         "brief": {"audience": "新手"}},
               decisions=[{"id": "d-live", "kind": "normative", "status": "accepted",
                           "statement": "用官方範例" + "字" * 100},
                          {"id": "d-dead", "kind": "normative", "status": "superseded",
                           "statement": "舊法", "superseded-by": "d-live"}],
               material="## src: 官方文件 {#m-1}\n內容\n\n## fact: 版本號\n0.1\n")
    write_leaf(home, "g/rules", concept={"id": "c-ru", "title": "規則", "order": 3,
                                         "concept": "規範"})


# ── --decisions ─────────────────────────────────────────────────────────

def test_decisions_active_only_by_default(make_project, write_leaf, monkeypatch, capsys):
    home = make_project()
    _corpus(home, write_leaf)
    monkeypatch.chdir(home.parent)
    assert show_cmd.run(["g", "--decisions", "--json"]) == 0
    p = json.loads(capsys.readouterr().out)
    sec = next(s for s in p["sections"] if s["section"] == "g/intro")
    ids = [d["id"] for d in sec["decisions"]]
    assert ids == ["d-live"]                       # 死決策預設不列
    assert p["dead"] == 0
    assert len(sec["decisions"][0]["statement"]) == 80    # statement 截 80


def test_decisions_all_status_shows_dead(make_project, write_leaf, monkeypatch, capsys):
    """--all-status＝取代刪掉的 retire 報告：死決策就地列出、標 DEAD。"""
    home = make_project()
    _corpus(home, write_leaf)
    monkeypatch.chdir(home.parent)
    assert show_cmd.run(["g", "--decisions", "--all-status", "--json"]) == 0
    p = json.loads(capsys.readouterr().out)
    sec = next(s for s in p["sections"] if s["section"] == "g/intro")
    by_id = {d["id"]: d for d in sec["decisions"]}
    assert set(by_id) == {"d-live", "d-dead"}
    assert by_id["d-dead"]["dead"] is True and by_id["d-live"]["dead"] is False
    assert p["dead"] == 1
    # text 面也標 DEAD
    assert show_cmd.run(["g", "--decisions", "--all-status"]) == 0
    out = capsys.readouterr().out
    assert "d-dead" in out and "DEAD" in out


def test_decisions_store_backend(make_project, write_leaf, monkeypatch, capsys):
    home = make_project()
    _corpus(home, write_leaf)
    monkeypatch.chdir(home.parent)
    assert store_cmd.run(["migrate", "g"]) == 0
    capsys.readouterr()
    assert show_cmd.run(["g", "--decisions", "--all-status", "--json"]) == 0
    p = json.loads(capsys.readouterr().out)
    sec = next(s for s in p["sections"] if s["section"] == "g/intro")
    assert {d["id"] for d in sec["decisions"]} == {"d-live", "d-dead"}


# ── --concepts ──────────────────────────────────────────────────────────

def test_concepts_view_differential_brief(make_project, write_leaf, monkeypatch, capsys):
    home = make_project()
    _corpus(home, write_leaf)
    monkeypatch.chdir(home.parent)
    assert show_cmd.run(["g", "--concepts", "--json"]) == 0
    p = json.loads(capsys.readouterr().out)
    intro = next(s for s in p["sections"] if s["section"] == "g/intro")
    assert intro["concept"] == "新手第一課"
    assert intro["briefDifferential"] == {"audience": "新手"}   # 只列本節覆寫的欄
    rules = next(s for s in p["sections"] if s["section"] == "g/rules")
    assert rules["briefDifferential"] == {}                     # 全繼承


def test_concepts_view_store_backend(make_project, write_leaf, monkeypatch, capsys):
    home = make_project()
    _corpus(home, write_leaf)
    monkeypatch.chdir(home.parent)
    assert store_cmd.run(["migrate", "g"]) == 0
    capsys.readouterr()
    assert show_cmd.run(["g", "--concepts", "--json"]) == 0
    p = json.loads(capsys.readouterr().out)
    assert {s["section"] for s in p["sections"]} == {"g", "g/intro", "g/rules"}


# ── --material ──────────────────────────────────────────────────────────

def test_material_view_title_index(make_project, write_leaf, monkeypatch, capsys):
    home = make_project()
    _corpus(home, write_leaf)
    monkeypatch.chdir(home.parent)
    assert show_cmd.run(["g", "--material", "--json"]) == 0
    p = json.loads(capsys.readouterr().out)
    assert [s["section"] for s in p["sections"]] == ["g/intro"]  # 只有 intro 有 material
    heads = p["sections"][0]["headings"]
    assert {h["title"] for h in heads} == {"官方文件", "版本號"}
    assert any(h["anchor"] == "m-1" for h in heads)


def test_material_view_store_backend(make_project, write_leaf, monkeypatch, capsys):
    home = make_project()
    _corpus(home, write_leaf)
    monkeypatch.chdir(home.parent)
    assert store_cmd.run(["migrate", "g"]) == 0
    capsys.readouterr()
    assert show_cmd.run(["g", "--material", "--json"]) == 0
    p = json.loads(capsys.readouterr().out)
    assert [s["section"] for s in p["sections"]] == ["g/intro"]
    assert {h["title"] for h in p["sections"][0]["headings"]} == {"官方文件", "版本號"}


def test_classification_view_unknown_scope_errors(make_project, write_leaf, monkeypatch, capsys):
    home = make_project()
    _corpus(home, write_leaf)
    monkeypatch.chdir(home.parent)
    assert show_cmd.run(["nope", "--decisions"]) == 1
    assert "no sections found" in capsys.readouterr().err
