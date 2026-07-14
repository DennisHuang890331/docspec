"""roadmap derive view ＋ 指令（Seam 2）：backlog 分組、blocked/unblocked、--json。

statusless model：全部 entry 皆待辦（present = backlog）；一個 dep 只要還在目前的 entries
集合裡就仍在擋（blocked）——不在了 = 已經 fallen out = done，不再擋。
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from dspx.commands.governance import roadmap as roadmap_cmd
from dspx.commands.governance.roadmap import build_backlog_view
from dspx.engine.layout import Layout
from dspx.engine.model import load_project


def _write_roadmap(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"entries": entries}, allow_unicode=True,
                                   sort_keys=False), encoding="utf-8")


def _doc_root(home: Path, article: str) -> Path:
    return home / "corpus" / f"{article}.roadmap.yaml"


def _forest(home: Path) -> Path:
    return home / "roadmap.yaml"


def _root_concept(cid: str, title: str, order: int = 1) -> dict:
    return {"id": cid, "title": title, "order": order, "concept": "x",
            "brief": {"audience": "a", "depth": "d", "breadth": "b"}}


def _two_doc_forest_fixture(make_project, write_leaf) -> Path:
    """兩文件（art1/art2）各一 doc roadmap ＋ 一份 forest roadmap。

    art1：r2 task depends-on r1-gone（r1 已經 fallen out——從沒寫進檔＝已完成 → unblocked）、
          r3 task depends-on r-open（r-open 仍在檔內 → blocked）、r-open task open。
    art2：a1 gap（無 dep，kind≠task → 非 unblocked，落 other backlog 桶）。
    forest：f1 task target=forest（unblocked）。
    """
    home = make_project()
    write_leaf(home, "art1", concept=_root_concept("c-a1", "A1"))
    write_leaf(home, "art2", concept=_root_concept("c-a2", "A2", order=2))
    _write_roadmap(_forest(home), [
        {"id": "f1", "kind": "task", "title": "森林工作",
         "what": "w", "target": "forest"},
    ])
    _write_roadmap(_doc_root(home, "art1"), [
        {"id": "r2", "kind": "task", "title": "可開工",
         "what": "w", "target": "art1", "depends-on": ["r1-gone"]},
        {"id": "r-open", "kind": "task", "title": "前置",
         "what": "w", "target": "c-a1"},
        {"id": "r3", "kind": "task", "title": "受阻",
         "what": "w", "target": "art1", "depends-on": ["r-open"]},
    ])
    _write_roadmap(_doc_root(home, "art2"), [
        {"id": "a1", "kind": "gap", "title": "待補缺項",
         "what": "w", "target": "art2"},
    ])
    return home


def _view(home: Path) -> dict:
    layout = Layout(home)
    return build_backlog_view(layout, load_project(layout))


# ── derive view 邏輯 ──────────────────────────────────────────────

def test_all_present_entries_are_backlog(make_project, write_leaf):
    home = _two_doc_forest_fixture(make_project, write_leaf)
    ids = {e["id"] for items in _view(home)["groups"].values() for e in items}
    assert {"f1", "r2", "r3", "r-open", "a1"} == ids   # 在檔＝皆待辦，無 status 過濾


def test_grouping_by_document_and_forest(make_project, write_leaf):
    groups = _view(_two_doc_forest_fixture(make_project, write_leaf))["groups"]
    assert {e["id"] for e in groups["forest"]} == {"f1"}
    assert {e["id"] for e in groups["art1"]} == {"r2", "r3", "r-open"}
    assert {e["id"] for e in groups["art2"]} == {"a1"}


def test_concept_id_target_resolves_to_article(make_project, write_leaf):
    # r-open 的 target 是 concept id「c-a1」→ 應歸到文件 art1（非 forest）。
    groups = _view(_two_doc_forest_fixture(make_project, write_leaf))["groups"]
    assert "r-open" in {e["id"] for e in groups["art1"]}


def test_unblocked_vs_blocked(make_project, write_leaf):
    groups = _view(_two_doc_forest_fixture(make_project, write_leaf))["groups"]
    by_id = {e["id"]: e for items in groups.values() for e in items}
    # r2 depends-on r1-gone（不在目前 entries 裡＝已掉出＝done）→ unblocked
    assert by_id["r2"]["unblocked"] is True
    assert by_id["r2"]["blocked"] is False
    # r3 depends-on r-open（仍在檔內）→ blocked, 列出仍在擋的 dep
    assert by_id["r3"]["blocked"] is True
    assert by_id["r3"]["unblocked"] is False
    assert by_id["r3"]["blocking-deps"] == ["r-open"]
    # f1 無 dep, task → unblocked
    assert by_id["f1"]["unblocked"] is True
    # a1 kind=gap（非 task）→ 非 unblocked，即使無 dep
    assert by_id["a1"]["unblocked"] is False
    assert by_id["a1"]["blocked"] is False


def test_empty_no_roadmap_files(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "art", concept=_root_concept("c-art", "Art"))
    assert _view(home)["groups"] == {}


# ── 指令 end-to-end ───────────────────────────────────────────────

def test_command_text_output(make_project, write_leaf, monkeypatch, capsys):
    home = _two_doc_forest_fixture(make_project, write_leaf)
    monkeypatch.chdir(home.parent)
    assert roadmap_cmd.run([]) == 0
    out = capsys.readouterr().out
    assert "forest/" in out
    assert "art1/" in out and "art2/" in out
    assert "r2" in out and "r3" in out
    assert "可開工" in out and "受阻" in out and "待補缺項" in out
    assert "r-open" in out                        # blocked 的仍在擋 dep 列出


def test_command_json_shape(make_project, write_leaf, monkeypatch, capsys):
    home = _two_doc_forest_fixture(make_project, write_leaf)
    monkeypatch.chdir(home.parent)
    assert roadmap_cmd.run(["--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert set(data["groups"]) == {"forest", "art1", "art2"}
    r2 = next(e for e in data["groups"]["art1"] if e["id"] == "r2")
    assert r2["kind"] == "task"
    assert "status" not in r2                      # 無狀態模型：entry 不再帶 status 欄
    assert r2["unblocked"] is True and r2["blocked"] is False
    r3 = next(e for e in data["groups"]["art1"] if e["id"] == "r3")
    assert r3["blocked"] is True and r3["blocking-deps"] == ["r-open"]


def test_command_empty_friendly(make_project, write_leaf, monkeypatch, capsys):
    home = make_project()
    write_leaf(home, "art", concept=_root_concept("c-art", "Art"))
    monkeypatch.chdir(home.parent)
    assert roadmap_cmd.run([]) == 0
    assert "(nothing to do)" in capsys.readouterr().out

    assert roadmap_cmd.run(["--json"]) == 0
    assert json.loads(capsys.readouterr().out)["groups"] == {}


# ── `roadmap done <id> --note` ───────────────────────────────────

def test_done_subcommand_removes_entry_and_writes_archive(make_project, write_leaf,
                                                          monkeypatch, capsys):
    home = _two_doc_forest_fixture(make_project, write_leaf)
    monkeypatch.chdir(home.parent)
    assert roadmap_cmd.run(["done", "r-open", "--note", "已直接處理完"]) == 0
    out = capsys.readouterr().out
    assert "r-open" in out and "roadmap-archive.yaml" in out

    ids_after = {e["id"] for items in _view(home)["groups"].values() for e in items}
    assert "r-open" not in ids_after

    archive = yaml.safe_load((home / "roadmap-archive.yaml")
                             .read_text(encoding="utf-8"))
    assert archive["entries"][0]["id"] == "r-open"
    assert archive["entries"][0]["note"] == "已直接處理完"


def test_done_subcommand_unknown_id_fails(make_project, write_leaf, monkeypatch):
    home = _two_doc_forest_fixture(make_project, write_leaf)
    monkeypatch.chdir(home.parent)
    assert roadmap_cmd.run(["done", "ghost", "--note", "x"]) == 1
