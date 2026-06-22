"""roadmap artifact（Seam 1）：資料模型 ＋ check 整合（depends-on/target/from-audit）。"""

from __future__ import annotations

from pathlib import Path

import yaml

from dspx.check import run_check
from dspx.layout import Layout
from dspx.model import load_project
from dspx.roadmap import (
    KINDS,
    STATUSES,
    all_entries,
    load_doc_roadmap,
    load_forest_roadmap,
    validate_roadmap,
)
from dspx.schema import load_schema


def _check(home):
    """roadmap 驗證只在 layout 非 None 時跑（比照 glossary/audit）。"""
    layout = Layout(home)
    leaves = load_project(layout)
    return run_check(leaves, load_schema(), layout=layout)


def _write_roadmap(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"entries": entries}, allow_unicode=True,
                                   sort_keys=False), encoding="utf-8")


def _doc_root(home: Path, article: str) -> Path:
    """per-doc roadmap 路徑＝corpus/<article>/roadmap.yaml。"""
    return home / "corpus" / article / "roadmap.yaml"


def _forest(home: Path) -> Path:
    return home / "roadmap.yaml"


def _root_concept(cid: str, title: str, order: int = 1) -> dict:
    return {"id": cid, "title": title, "order": order, "concept": "x",
            "brief": {"audience": "a", "depth": "d", "breadth": "b"}}


# ── 載入層（無 check 脈絡）─────────────────────────────────────────

def test_load_absent_returns_empty(make_project):
    home = make_project()
    layout = Layout(home)
    assert load_forest_roadmap(layout) == []
    assert load_doc_roadmap(home / "corpus" / "a", "a") == []


def test_validate_bad_enum():
    errs = validate_roadmap([
        {"id": "r1", "kind": "bogus", "status": "open", "target": "forest"},
        {"id": "r2", "kind": "task", "status": "nope", "target": "forest"},
    ])
    assert any("kind" in e for e in errs)
    assert any("status" in e for e in errs)


def test_validate_duplicate_id():
    errs = validate_roadmap([
        {"id": "r1", "kind": "task", "status": "open", "target": "forest"},
        {"id": "r1", "kind": "task", "status": "open", "target": "forest"},
    ])
    assert any("duplicate" in e for e in errs)


# ── check 整合 ────────────────────────────────────────────────────

def test_valid_roadmap_passes(make_project, write_leaf):
    # forest entry + 一份 doc roadmap（含一條 depends-on）→ 綠
    home = make_project()
    write_leaf(home, "art", concept=_root_concept("c-art", "Art"),
               decisions=[{"id": "d1", "kind": "normative", "status": "accepted",
                           "statement": "s"}])
    _write_roadmap(_forest(home), [
        {"id": "f1", "kind": "task", "status": "open", "title": "森林工作",
         "what": "建森林地圖", "target": "forest"},
    ])
    _write_roadmap(_doc_root(home, "art"), [
        {"id": "r1", "kind": "gap", "status": "open", "title": "缺章",
         "what": "補一節", "target": "art", "depends-on": ["f1"]},
        {"id": "r2", "kind": "task", "status": "doing", "title": "做章",
         "what": "寫", "target": "c-art", "depends-on": ["r1"]},
    ])
    res = _check(home)
    assert res.ok, res.errors


def test_depends_on_dead_ref_fails(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "art", concept=_root_concept("c-art", "Art"))
    _write_roadmap(_doc_root(home, "art"), [
        {"id": "r1", "kind": "task", "status": "open", "title": "t", "what": "w",
         "target": "art", "depends-on": ["ghost"]},
    ])
    res = _check(home)
    assert not res.ok
    assert any("depends-on" in e and "ghost" in e for e in res.errors)


def test_depends_on_cycle_fails(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "art", concept=_root_concept("c-art", "Art"))
    _write_roadmap(_doc_root(home, "art"), [
        {"id": "a", "kind": "task", "status": "open", "title": "t", "what": "w",
         "target": "art", "depends-on": ["b"]},
        {"id": "b", "kind": "task", "status": "open", "title": "t", "what": "w",
         "target": "art", "depends-on": ["a"]},
    ])
    res = _check(home)
    assert not res.ok
    assert any("roadmap depends-on cycle" in e for e in res.errors)


def test_forest_target_in_doc_file_fails(make_project, write_leaf):
    # forest target 放在 per-doc 檔 → 放置錯
    home = make_project()
    write_leaf(home, "art", concept=_root_concept("c-art", "Art"))
    _write_roadmap(_doc_root(home, "art"), [
        {"id": "r1", "kind": "task", "status": "open", "title": "t", "what": "w",
         "target": "forest"},
    ])
    res = _check(home)
    assert not res.ok
    assert any("forest" in e and "r1" in e for e in res.errors)


def test_doc_target_in_forest_file_fails(make_project, write_leaf):
    # section target 放在 forest 檔 → 放置錯
    home = make_project()
    write_leaf(home, "art", concept=_root_concept("c-art", "Art"))
    _write_roadmap(_forest(home), [
        {"id": "f1", "kind": "task", "status": "open", "title": "t", "what": "w",
         "target": "art"},
    ])
    res = _check(home)
    assert not res.ok
    assert any("forest file" in e and "f1" in e for e in res.errors)


def test_target_dead_ref_fails(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "art", concept=_root_concept("c-art", "Art"))
    _write_roadmap(_doc_root(home, "art"), [
        {"id": "r1", "kind": "task", "status": "open", "title": "t", "what": "w",
         "target": "no-such-section"},
    ])
    res = _check(home)
    assert not res.ok
    assert any("target" in e and "no-such-section" in e for e in res.errors)


def test_doc_target_outside_its_tree_fails(make_project, write_leaf):
    # per-doc 檔（art1）放 target 指向另一文件（art2）的 section → 放置錯
    home = make_project()
    write_leaf(home, "art1", concept=_root_concept("c-a1", "A1"))
    write_leaf(home, "art2", concept=_root_concept("c-a2", "A2", order=2))
    _write_roadmap(_doc_root(home, "art1"), [
        {"id": "r1", "kind": "task", "status": "open", "title": "t", "what": "w",
         "target": "art2"},
    ])
    res = _check(home)
    assert not res.ok
    assert any("art1" in e and "tree" in e for e in res.errors)


def test_from_audit_dead_ref_fails(make_project, write_leaf):
    home = make_project()
    leaf_dir = write_leaf(home, "art", concept=_root_concept("c-art", "Art"))
    # 寫一個 audit.yaml 含 finding F1
    (leaf_dir / "audit.yaml").write_text(
        yaml.safe_dump({"findings": [
            {"id": "F1", "face": "logic", "severity": "med", "status": "open",
             "finding": "x", "targets": ["art"]},
        ]}, allow_unicode=True, sort_keys=False), encoding="utf-8")
    _write_roadmap(_doc_root(home, "art"), [
        {"id": "r1", "kind": "task", "status": "open", "title": "t", "what": "w",
         "target": "art", "from-audit": "F99"},
    ])
    res = _check(home)
    assert not res.ok
    assert any("from-audit" in e and "F99" in e for e in res.errors)


def test_from_audit_live_ref_passes(make_project, write_leaf):
    home = make_project()
    leaf_dir = write_leaf(home, "art", concept=_root_concept("c-art", "Art"),
                          decisions=[{"id": "d1", "kind": "normative",
                                      "status": "accepted", "statement": "s"}])
    (leaf_dir / "audit.yaml").write_text(
        yaml.safe_dump({"findings": [
            {"id": "F1", "face": "logic", "severity": "med", "status": "open",
             "finding": "x", "targets": ["art"]},
        ]}, allow_unicode=True, sort_keys=False), encoding="utf-8")
    _write_roadmap(_doc_root(home, "art"), [
        {"id": "r1", "kind": "task", "status": "open", "title": "t", "what": "w",
         "target": "art", "from-audit": "F1"},
    ])
    res = _check(home)
    assert res.ok, res.errors


def test_all_entries_tags_store(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "art", concept=_root_concept("c-art", "Art"))
    _write_roadmap(_forest(home), [
        {"id": "f1", "kind": "task", "status": "open", "title": "t", "what": "w",
         "target": "forest"}])
    _write_roadmap(_doc_root(home, "art"), [
        {"id": "r1", "kind": "task", "status": "open", "title": "t", "what": "w",
         "target": "art"}])
    layout = Layout(home)
    entries = all_entries(layout, load_project(layout))
    by_id = {e["id"]: e["_store"] for e in entries}
    assert by_id["f1"] == "forest"
    assert by_id["r1"] == "doc:art"
