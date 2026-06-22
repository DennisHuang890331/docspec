"""roadmap derive view ＋ 指令（Seam 2）：backlog 分組、blocked/unblocked、--json。"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from dspx.commands import roadmap as roadmap_cmd
from dspx.commands.roadmap import build_backlog_view
from dspx.layout import Layout
from dspx.model import load_project


def _write_roadmap(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"entries": entries}, allow_unicode=True,
                                   sort_keys=False), encoding="utf-8")


def _doc_root(home: Path, article: str) -> Path:
    return home / "corpus" / article / "roadmap.yaml"


def _forest(home: Path) -> Path:
    return home / "roadmap.yaml"


def _root_concept(cid: str, title: str, order: int = 1) -> dict:
    return {"id": cid, "title": title, "order": order, "concept": "x",
            "brief": {"audience": "a", "depth": "d", "breadth": "b"}}


def _two_doc_forest_fixture(make_project, write_leaf) -> Path:
    """兩文件（art1/art2）各一 doc roadmap ＋ 一份 forest roadmap。

    art1：r1 done（不該出現）、r2 task open depends-on r1（dep 已 done → unblocked）、
          r3 task open depends-on r-open（dep 仍 open → blocked）、r-open task open。
    art2：a1 task doing。
    forest：f1 task open target=forest（unblocked）。
    """
    home = make_project()
    write_leaf(home, "art1", concept=_root_concept("c-a1", "A1"))
    write_leaf(home, "art2", concept=_root_concept("c-a2", "A2", order=2))
    _write_roadmap(_forest(home), [
        {"id": "f1", "kind": "task", "status": "open", "title": "森林工作",
         "what": "w", "target": "forest"},
    ])
    _write_roadmap(_doc_root(home, "art1"), [
        {"id": "r1", "kind": "task", "status": "done", "title": "已完成",
         "what": "w", "target": "art1"},
        {"id": "r2", "kind": "task", "status": "open", "title": "可開工",
         "what": "w", "target": "art1", "depends-on": ["r1"]},
        {"id": "r-open", "kind": "task", "status": "open", "title": "前置",
         "what": "w", "target": "c-a1"},
        {"id": "r3", "kind": "task", "status": "open", "title": "受阻",
         "what": "w", "target": "art1", "depends-on": ["r-open"]},
    ])
    _write_roadmap(_doc_root(home, "art2"), [
        {"id": "a1", "kind": "task", "status": "doing", "title": "進行中",
         "what": "w", "target": "art2"},
    ])
    return home


def _view(home: Path) -> dict:
    layout = Layout(home)
    return build_backlog_view(layout, load_project(layout))


# ── derive view 邏輯 ──────────────────────────────────────────────

def test_done_and_dropped_dropped(make_project, write_leaf):
    home = _two_doc_forest_fixture(make_project, write_leaf)
    ids = {e["id"] for items in _view(home)["groups"].values() for e in items}
    assert "r1" not in ids          # done 掉出
    assert {"f1", "r2", "r3", "r-open", "a1"} <= ids


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
    # r2 depends-on r1(done) → unblocked
    assert by_id["r2"]["unblocked"] is True
    assert by_id["r2"]["blocked"] is False
    # r3 depends-on r-open(open) → blocked, 列出開放 dep
    assert by_id["r3"]["blocked"] is True
    assert by_id["r3"]["unblocked"] is False
    assert by_id["r3"]["blocking-deps"] == ["r-open"]
    # f1 無 dep, task/open → unblocked
    assert by_id["f1"]["unblocked"] is True
    # a1 doing → 非 unblocked（status 非 open）
    assert by_id["a1"]["unblocked"] is False


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
    assert "r1" not in out                       # done 不顯示
    assert "可開工" in out and "受阻" in out and "進行中" in out
    assert "r-open" in out                        # blocked 的開放 dep 列出


def test_command_json_shape(make_project, write_leaf, monkeypatch, capsys):
    home = _two_doc_forest_fixture(make_project, write_leaf)
    monkeypatch.chdir(home.parent)
    assert roadmap_cmd.run(["--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert set(data["groups"]) == {"forest", "art1", "art2"}
    r2 = next(e for e in data["groups"]["art1"] if e["id"] == "r2")
    assert r2["status"] == "open" and r2["kind"] == "task"
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
