"""contract-slimming：缺 decisions.yaml＝合法空（晉升閘鬆綁）＋死決策留原檔（D2/D3）。

Task 1.3/1.4：缺檔＝空、壞檔 fail-loud、`entries: []` 與缺檔行為等價。
Task 3.2/3.3：舊 live 樹 history.yaml 相容照讀；死決策留 decisions.yaml → supersede 鏈/
deps 二跳/check 一致性三套接線不斷。
"""

from __future__ import annotations

import json

import pytest
import yaml

from dspx.check import run_check
from dspx.commands.query import check as check_cmd
from dspx.commands.corpus import ready as ready_cmd
from dspx.commands.query import show as show_cmd
from dspx.commands.query import status as status_cmd
from dspx.commands.corpus.ready import _graduate
from dspx.commands.query.status import section_state
from dspx.engine.layout import Layout
from dspx.engine.model import (
    ModelError,
    decision_index,
    deps_fingerprint,
    load_project,
    realized_statements,
)
from dspx.engine.schema import load_schema


def _leaf_dir(home, section):
    d = home / "corpus"
    for p in section.split("/"):
        d = d / p
    return d


# ── Task 1.3：壞檔照樣 fail-loud、缺檔＝合法空 ───────────────────────────────────


@pytest.mark.parametrize("broken", [
    "- a\n- b\n",                                    # 頂層是 list
    "foo:\n  - 1\n",                                 # 有內容卻缺 entries: key
    "entries:\n  - id: a\nentries:\n  - id: b\n",    # 重複頂層 key
])
def test_broken_decisions_still_fails_loud(make_project, write_leaf, broken):
    """壞檔（頂層型別錯／誤名 key／重複 key）＝載入即 raise。★store-only：散檔 decisions 的
    載入契約由遷移橋（`store.load_tree_leaves`，migrate 用）保留、走同一 `_entries` 載入器。"""
    from dspx.engine import store as _store
    home = make_project()
    d = _leaf_dir(home, "g/x")
    d.mkdir(parents=True, exist_ok=True)
    (d / "concept.yaml").write_text(
        yaml.safe_dump({"id": "c1", "title": "X", "order": 1, "status": "draft",
                        "concept": "x", "brief": {}}, allow_unicode=True), encoding="utf-8")
    (d / "decisions.yaml").write_text(broken, encoding="utf-8")
    with pytest.raises(ModelError):
        _store.load_tree_leaves(Layout(home))


def test_concept_only_loads_with_empty_decisions(make_project, write_leaf):
    """只有 concept.yaml（無 decisions.yaml）＝合法空、decisions == []、零新例外。"""
    home = make_project()
    write_leaf(home, "g/x", concept={"id": "c1", "title": "X", "order": 1})
    (leaf,) = load_project(Layout(home))
    assert leaf.decisions == []
    assert not (leaf.dir / "decisions.yaml").exists()


def test_status_concept_only_not_waiting_decisions(
        make_project, write_leaf, monkeypatch, capsys):
    """無 decisions.yaml 的節不再被判 waiting(missing:decisions)；d 旗標仍顯示（False）。"""
    home = make_project()
    write_leaf(home, "g/x", concept={"id": "c1", "title": "X", "order": 1})
    monkeypatch.chdir(home.parent)
    assert status_cmd.run(["--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    (row,) = [r for r in data["sections"] if r["section"] == "g/x"]
    assert "missing:decisions" not in row["state"]
    assert row["files"]["decisions"] is False        # d 旗標保留（缺席≠降級）


def test_ready_graduates_without_decisions(make_project, write_leaf, monkeypatch, capsys):
    """concept 完整、develop 榨乾、無 decisions.yaml → 晉升成功、不要求建 entries:[] 容器。"""
    home = make_project()
    write_leaf(home, "g/x",
               concept={"id": "c1", "title": "X", "order": 1, "concept": "real",
                        "brief": {"audience": "a", "depth": "d", "breadth": "b"}},
               develop="<!-- drained -->")
    monkeypatch.chdir(home.parent)
    assert ready_cmd.run(["g/x"]) == 0
    assert not (home / "work" / "g" / "x" / "develop.md").exists()


def test_ready_missing_concept_still_refused(make_project, monkeypatch, capsys):
    """缺 concept.yaml 的拒絕維持原樣（concept 無合法空形狀）。"""
    from dspx.commands.corpus import new as new_cmd
    home = make_project()
    monkeypatch.chdir(home.parent)
    new_cmd.run(["g/a"])                              # 只有 develop.md（work/）
    assert ready_cmd.run(["g/a"]) == 1
    # ★store-only：未結晶＝無 store 記錄／無 concept
    assert "not crystallized" in capsys.readouterr().err


# ── Task 1.4：`entries: []` 空殼 ⟺ 缺檔（行為等價）───────────────────────────────


def test_empty_entries_behaves_like_missing_decisions(make_project, write_leaf, monkeypatch):
    """`entries: []` 空殼節與無 decisions.yaml 節：model.decisions／status state／ready 結果全等。"""
    home = make_project()
    write_leaf(home, "g/a",
               concept={"id": "ca", "title": "A", "order": 1, "concept": "real",
                        "brief": {"audience": "a", "depth": "d", "breadth": "b"}})
    write_leaf(home, "g/b",
               concept={"id": "cb", "title": "B", "order": 2, "concept": "real",
                        "brief": {"audience": "a", "depth": "d", "breadth": "b"}},
               decisions=[])                          # 空殼 entries: []
    monkeypatch.chdir(home.parent)
    layout = Layout(home)
    schema = load_schema()
    leaves = load_project(layout)
    by = {lf.section: lf for lf in leaves}
    check_ok = run_check(leaves, schema, layout).ok

    # model.decisions 同為空
    assert by["g/a"].decisions == [] == by["g/b"].decisions
    # status state 同
    assert section_state(by["g/a"], schema, check_ok) \
        == section_state(by["g/b"], schema, check_ok)
    # ready 結果同（ok 與 reasons）
    ok_a, reasons_a, *_ = _graduate(layout, schema, "g/a")
    ok_b, reasons_b, *_ = _graduate(layout, schema, "g/b")
    assert ok_a == ok_b and reasons_a == reasons_b


# ── Task 3.2：舊 live 樹 history.yaml 向後相容 ──────────────────────────────────


def test_legacy_live_tree_history_loads(make_project, write_leaf, monkeypatch, capsys):
    """含 live 樹 history.yaml 的舊專案照讀不炸；show 仍以 kind:history 定址（向後相容）。"""
    home = make_project()
    write_leaf(home, "g/x", concept={"id": "c1", "title": "X", "order": 1},
               history=[{"id": "h-old", "kind": "normative", "status": "superseded",
                         "statement": "old rule", "retired-in": "v2"}])
    monkeypatch.chdir(home.parent)
    (leaf,) = load_project(Layout(home))             # 不 raise
    assert leaf.history and leaf.history[0]["id"] == "h-old"
    assert show_cmd.run(["h-old", "--json"]) == 0
    p = json.loads(capsys.readouterr().out)
    assert p["kind"] == "history"


# ── Task 3.3：死決策留 decisions.yaml → 三套接線不斷 ───────────────────────────


def _dead_decision_project(make_project, write_leaf, monkeypatch):
    """單文章樹：spec/up 帶 A（superseded-by B）＋B（accepted、supersedes A）；spec/down realizes A。"""
    home = make_project()
    write_leaf(home, "spec",
               concept={"id": "root", "title": "規範", "order": 0,
                        "brief": {"audience": "a", "depth": "d", "breadth": "b"}})
    write_leaf(home, "spec/up", concept={"id": "cu", "title": "上游", "order": 1},
               decisions=[
                   {"id": "A", "statement": "採方案A", "status": "superseded",
                    "superseded-by": "B", "kind": "normative"},
                   {"id": "B", "statement": "採方案B", "status": "accepted",
                    "supersedes": "A", "kind": "normative"},
               ])
    write_leaf(home, "spec/down", concept={"id": "cd", "title": "下游", "order": 2,
                                           "realizes": ["A"]}, decisions=[])
    monkeypatch.chdir(home.parent)
    return home


def test_dead_decision_addressable_in_place(make_project, write_leaf, monkeypatch, capsys):
    """(a) 死決策留原 decisions.yaml：show / show --realized-by 就地可定址、supersede 鏈解析出活接替。"""
    home = _dead_decision_project(make_project, write_leaf, monkeypatch)
    assert show_cmd.run(["A", "--json"]) == 0
    p = json.loads(capsys.readouterr().out)
    assert p["kind"] == "decision" and p["status"] == "superseded" and p["supersededBy"] == "B"
    assert show_cmd.run(["A", "--realized-by", "--json"]) == 0
    q = json.loads(capsys.readouterr().out)
    assert q["definedAt"] == "spec/up" and "spec/down" in q["realizedBy"]
    # supersede 鏈解析：下游 realizes 撈到終端活接替 B
    leaves = load_project(Layout(home))
    consumer = next(lf for lf in leaves if lf.section == "spec/down")
    (item,) = realized_statements(consumer, decision_index(leaves))
    assert item["superseded_by"] == "B" and item["successor_statement"] == "採方案B"


def test_deps_two_hop_fires_for_downstream_realizes(make_project, write_leaf, monkeypatch):
    """(b) deps 指紋二跳信號照常：死決策就地被解析，換活接替時下游指紋變。"""
    home = _dead_decision_project(make_project, write_leaf, monkeypatch)
    leaves = load_project(Layout(home))
    consumer = next(lf for lf in leaves if lf.section == "spec/down")
    fp_with_successor = deps_fingerprint(consumer, decision_index(leaves))
    assert fp_with_successor != ""
    # 把 A 改回活決策（無接替）→ 二跳信號改變 → 指紋不同 ★store-only：改 store 記錄 decisions
    write_leaf.edit(home, "spec/up", decisions=[
        {"id": "A", "statement": "採方案A", "status": "accepted", "kind": "normative"}])
    leaves2 = load_project(Layout(home))
    consumer2 = next(lf for lf in leaves2 if lf.section == "spec/down")
    assert deps_fingerprint(consumer2, decision_index(leaves2)) != fp_with_successor


def test_check_supersede_consistency_green_with_dead_in_place(
        make_project, write_leaf, monkeypatch):
    """(c) check 的 supersede 一致性對「死決策留原檔」照樣綠（下游 realizes 過渡窗放行）。"""
    _dead_decision_project(make_project, write_leaf, monkeypatch)
    assert check_cmd.run([]) == 0
