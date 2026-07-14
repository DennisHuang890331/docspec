"""roadmap artifact（Seam 1）：資料模型 ＋ check 整合（depends-on/target/from-audit/promoted-to）。

statusless model（change-event-layer）：entries 不再有 status/done-to；present = backlog,
fallen out = done. 完成分流：`docspec roadmap done <id> --note` （小工作）或 promoted-to 一個
change（晉升，由 change archive 交易 prune）。
"""

from __future__ import annotations

from pathlib import Path

import yaml

from dspx.check import run_check
from dspx.engine.layout import Layout
from dspx.engine.model import load_project
from dspx.reports.roadmap import (
    KINDS,
    RoadmapError,
    all_entries,
    load_doc_roadmap,
    load_forest_roadmap,
    mark_done,
    validate_roadmap,
)
from dspx.engine.schema import load_schema


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
    """per-doc roadmap 路徑＝corpus/<article>/roadmap.yaml。★store-only：corpus/<article>/ 夾不再由
    write_leaf 順帶建出——先建夾（引擎 save() 亦自建）。"""
    p = home / "corpus" / f"{article}.roadmap.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _doc_archive(home: Path, article: str) -> Path:
    p = home / "corpus" / article / "roadmap-archive.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _forest(home: Path) -> Path:
    return home / "roadmap.yaml"


def _forest_archive(home: Path) -> Path:
    return home / "roadmap-archive.yaml"


def _root_concept(cid: str, title: str, order: int = 1) -> dict:
    return {"id": cid, "title": title, "order": order, "concept": "x",
            "brief": {"audience": "a", "depth": "d", "breadth": "b"}}


def _write_change(home: Path, cid: str, state: str) -> Path:
    """在 project_root（home.parent）下建一個最小 change 容器（active/_archive/_abandoned）。"""
    root = home.parent / "changes"
    sub = {"active": root, "archived": root / "_archive", "abandoned": root / "_abandoned"}[state]
    cdir = sub / cid
    cdir.mkdir(parents=True, exist_ok=True)
    (cdir / "change.yaml").write_text(
        yaml.safe_dump({"id": cid, "title": "t", "why": "w", "created": "2026-01-01",
                        "publish": "advisory", "targets": []},
                       allow_unicode=True, sort_keys=False), encoding="utf-8")
    return cdir


# ── 載入層（無 check 脈絡）─────────────────────────────────────────

def test_load_absent_returns_empty(make_project):
    home = make_project()
    layout = Layout(home)
    assert load_forest_roadmap(layout) == []
    assert load_doc_roadmap(Layout(home), "a") == []


def test_validate_bad_enum():
    errs = validate_roadmap([
        {"id": "r1", "kind": "bogus", "target": "forest"},
    ])
    assert any("kind" in e for e in errs)


def test_validate_duplicate_id():
    errs = validate_roadmap([
        {"id": "r1", "kind": "task", "target": "forest"},
        {"id": "r1", "kind": "task", "target": "forest"},
    ])
    assert any("duplicate" in e for e in errs)


def test_validate_rejects_legacy_status_field():
    """status 欄已刪——出現即報錯、指向分流機制。"""
    errs = validate_roadmap([
        {"id": "r1", "kind": "task", "status": "open", "target": "forest"},
    ])
    assert any("status" in e and "roadmap done" in e for e in errs)


def test_validate_rejects_legacy_done_to_field():
    errs = validate_roadmap([
        {"id": "r1", "kind": "task", "done-to": "d1", "target": "forest"},
    ])
    assert any("done-to" in e for e in errs)


# ── check 整合 ────────────────────────────────────────────────────

def test_valid_roadmap_passes(make_project, write_leaf):
    # forest entry + 一份 doc roadmap（含一條 depends-on）→ 綠
    home = make_project()
    write_leaf(home, "art", concept=_root_concept("c-art", "Art"),
               decisions=[{"id": "d1", "kind": "normative", "status": "accepted",
                           "statement": "s"}])
    _write_roadmap(_forest(home), [
        {"id": "f1", "kind": "task", "title": "森林工作",
         "what": "建森林地圖", "target": "forest"},
    ])
    _write_roadmap(_doc_root(home, "art"), [
        {"id": "r1", "kind": "gap", "title": "缺章",
         "what": "補一節", "target": "art", "depends-on": ["f1"]},
        {"id": "r2", "kind": "task", "title": "做章",
         "what": "寫", "target": "c-art", "depends-on": ["r1"]},
    ])
    res = _check(home)
    assert res.ok, res.errors


def test_check_rejects_legacy_status(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "art", concept=_root_concept("c-art", "Art"))
    _write_roadmap(_doc_root(home, "art"), [
        {"id": "r1", "kind": "task", "status": "doing", "title": "t", "what": "w",
         "target": "art"},
    ])
    res = _check(home)
    assert not res.ok
    assert any("status" in e and "r1" in e for e in res.errors)


def test_depends_on_dead_ref_fails(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "art", concept=_root_concept("c-art", "Art"))
    _write_roadmap(_doc_root(home, "art"), [
        {"id": "r1", "kind": "task", "title": "t", "what": "w",
         "target": "art", "depends-on": ["ghost"]},
    ])
    res = _check(home)
    assert not res.ok
    assert any("depends-on" in e and "ghost" in e for e in res.errors)


def test_depends_on_cycle_fails(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "art", concept=_root_concept("c-art", "Art"))
    _write_roadmap(_doc_root(home, "art"), [
        {"id": "a", "kind": "task", "title": "t", "what": "w",
         "target": "art", "depends-on": ["b"]},
        {"id": "b", "kind": "task", "title": "t", "what": "w",
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
        {"id": "r1", "kind": "task", "title": "t", "what": "w",
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
        {"id": "f1", "kind": "task", "title": "t", "what": "w",
         "target": "art"},
    ])
    res = _check(home)
    assert not res.ok
    assert any("forest file" in e and "f1" in e for e in res.errors)


def test_target_dead_ref_fails(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "art", concept=_root_concept("c-art", "Art"))
    _write_roadmap(_doc_root(home, "art"), [
        {"id": "r1", "kind": "task", "title": "t", "what": "w",
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
        {"id": "r1", "kind": "task", "title": "t", "what": "w",
         "target": "art2"},
    ])
    res = _check(home)
    assert not res.ok
    assert any("art1" in e and "tree" in e for e in res.errors)


def test_from_audit_dead_ref_fails(make_project, write_leaf):
    home = make_project()
    leaf_dir = write_leaf(home, "art", concept=_root_concept("c-art", "Art"))
    # 寫一個 audit.yaml 含 finding F1
    leaf_dir.mkdir(parents=True, exist_ok=True)   # ★store-only：corpus/art/ 夾另建放 audit
    (leaf_dir.parent / f"{leaf_dir.name}.audit.yaml").write_text(
        yaml.safe_dump({"findings": [
            {"id": "F1", "face": "logic", "severity": "med", "status": "open",
             "finding": "x", "targets": ["art"]},
        ]}, allow_unicode=True, sort_keys=False), encoding="utf-8")
    _write_roadmap(_doc_root(home, "art"), [
        {"id": "r1", "kind": "task", "title": "t", "what": "w",
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
    leaf_dir.mkdir(parents=True, exist_ok=True)   # ★store-only：corpus/art/ 夾另建放 audit
    (leaf_dir.parent / f"{leaf_dir.name}.audit.yaml").write_text(
        yaml.safe_dump({"findings": [
            {"id": "F1", "face": "logic", "severity": "med", "status": "open",
             "finding": "x", "targets": ["art"]},
        ]}, allow_unicode=True, sort_keys=False), encoding="utf-8")
    _write_roadmap(_doc_root(home, "art"), [
        {"id": "r1", "kind": "task", "title": "t", "what": "w",
         "target": "art", "from-audit": "F1"},
    ])
    res = _check(home)
    assert res.ok, res.errors


def test_all_entries_tags_store(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "art", concept=_root_concept("c-art", "Art"))
    _write_roadmap(_forest(home), [
        {"id": "f1", "kind": "task", "title": "t", "what": "w",
         "target": "forest"}])
    _write_roadmap(_doc_root(home, "art"), [
        {"id": "r1", "kind": "task", "title": "t", "what": "w",
         "target": "art"}])
    layout = Layout(home)
    entries = all_entries(layout, load_project(layout))
    by_id = {e["id"]: e["_store"] for e in entries}
    assert by_id["f1"] == "forest"
    assert by_id["r1"] == "doc:art"


# ── ★G6：promoted-to 反查（active/archived 健康、abandoned 孤兒、死指標）──────

def test_promoted_to_active_change_passes(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "art", concept=_root_concept("c-art", "Art"))
    _write_change(home, "chg-x", "active")
    _write_roadmap(_doc_root(home, "art"), [
        {"id": "r1", "kind": "task", "title": "t", "promoted-to": "chg-x"},
    ])
    res = _check(home)
    assert res.ok, res.errors


def test_promoted_to_archived_change_passes(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "art", concept=_root_concept("c-art", "Art"))
    _write_change(home, "chg-x", "archived")
    _write_roadmap(_doc_root(home, "art"), [
        {"id": "r1", "kind": "task", "title": "t", "promoted-to": "chg-x"},
    ])
    res = _check(home)
    assert res.ok, res.errors


def test_promoted_to_abandoned_change_is_orphan_error(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "art", concept=_root_concept("c-art", "Art"))
    _write_change(home, "chg-x", "abandoned")
    _write_roadmap(_doc_root(home, "art"), [
        {"id": "r1", "kind": "task", "title": "t", "promoted-to": "chg-x"},
    ])
    res = _check(home)
    assert not res.ok
    assert any("abandoned" in e and "chg-x" in e and "r1" in e for e in res.errors)


def test_promoted_to_nonexistent_change_is_dead_pointer(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "art", concept=_root_concept("c-art", "Art"))
    _write_roadmap(_doc_root(home, "art"), [
        {"id": "r1", "kind": "task", "title": "t", "promoted-to": "chg-ghost"},
    ])
    res = _check(home)
    assert not res.ok
    assert any("nonexistent" in e and "chg-ghost" in e for e in res.errors)


# ── 完成分流：`docspec roadmap done <id> --note` ─────────────────────

def test_mark_done_moves_doc_entry_to_archive(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "art", concept=_root_concept("c-art", "Art"))
    _write_roadmap(_doc_root(home, "art"), [
        {"id": "r1", "kind": "task", "title": "潤除殘留", "what": "w", "target": "art"},
        {"id": "r2", "kind": "task", "title": "另一件", "what": "w", "target": "art"},
    ])
    layout = Layout(home)
    leaves = load_project(layout)
    record = mark_done(layout, leaves, "r1", "風格殘留已潤除")
    assert record["id"] == "r1" and record["note"] == "風格殘留已潤除" and record["date"]

    remaining = load_doc_roadmap(Layout(home), "art")
    assert {e["id"] for e in remaining} == {"r2"}          # r1 掉出、r2 還在

    archive = yaml.safe_load(_forest_archive(home).read_text(encoding="utf-8"))
    assert archive["entries"][0]["id"] == "r1"
    assert archive["entries"][0]["title"] == "潤除殘留"


def test_mark_done_deletes_file_when_last_entry_removed(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "art", concept=_root_concept("c-art", "Art"))
    _write_roadmap(_doc_root(home, "art"), [
        {"id": "r1", "kind": "task", "title": "t", "what": "w", "target": "art"},
    ])
    layout = Layout(home)
    leaves = load_project(layout)
    mark_done(layout, leaves, "r1", "done")
    assert not _doc_root(home, "art").is_file()   # 沒待辦了 → 整檔刪除（按需生成慣例）
    assert _forest_archive(home).is_file()


def test_mark_done_finds_forest_entry(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "art", concept=_root_concept("c-art", "Art"))
    _write_roadmap(_forest(home), [
        {"id": "f1", "kind": "task", "title": "森林項", "what": "w", "target": "forest"},
    ])
    layout = Layout(home)
    leaves = load_project(layout)
    mark_done(layout, leaves, "f1", "已處理")
    assert not _forest(home).is_file()
    archive = yaml.safe_load(_forest_archive(home).read_text(encoding="utf-8"))
    assert archive["entries"][0]["id"] == "f1"


def test_mark_done_unknown_id_raises(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "art", concept=_root_concept("c-art", "Art"))
    layout = Layout(home)
    leaves = load_project(layout)
    import pytest
    with pytest.raises(RoadmapError):
        mark_done(layout, leaves, "ghost", "note")


def test_roadmap_done_command_end_to_end(make_project, write_leaf, monkeypatch, capsys):
    from dspx.commands.governance import roadmap as roadmap_cmd

    home = make_project()
    write_leaf(home, "art", concept=_root_concept("c-art", "Art"))
    _write_roadmap(_doc_root(home, "art"), [
        {"id": "r1", "kind": "task", "title": "t", "what": "w", "target": "art"},
    ])
    monkeypatch.chdir(home.parent)
    assert roadmap_cmd.run(["done", "r1", "--note", "小工作已結案"]) == 0
    out = capsys.readouterr().out
    assert "r1" in out and "roadmap-archive.yaml" in out
    assert not _doc_root(home, "art").is_file()
