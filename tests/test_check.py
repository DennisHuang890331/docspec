"""check：id 唯一 / 死引用 / 循環。"""

from __future__ import annotations

from dspx.check import run_check
from dspx.layout import Layout
from dspx.model import load_project
from dspx.schema import load_schema


def _check(home):
    layout = Layout(home)
    leaves = load_project(layout)
    return run_check(leaves, load_schema())


def test_clean_project_passes(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "a/intro", concept={"id": "c1", "title": "Intro", "order": 1},
               decisions=[{"id": "d1", "kind": "normative", "status": "accepted", "statement": "x"}])
    res = _check(home)
    assert res.ok
    assert "c1" in res.index.ids and "d1" in res.index.ids
    assert res.index.ids["d1"].kind == "decision"


def test_duplicate_id_fails(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "a/one", concept={"id": "dup", "title": "1", "order": 1})
    write_leaf(home, "a/two", concept={"id": "dup", "title": "2", "order": 2})
    res = _check(home)
    assert not res.ok
    assert any("duplicate id" in e for e in res.errors)


def test_dead_realizes_ref_fails(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1,
                                      "realizes": ["ghost"]})
    res = _check(home)
    assert not res.ok
    assert any("ghost" in e for e in res.errors)


def test_realizes_to_history_is_not_dead(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1,
                                      "realizes": ["d-old"]},
               history=[{"id": "d-old", "kind": "normative", "status": "superseded",
                         "statement": "old"}])
    assert _check(home).ok


def test_supersede_cycle_fails(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1},
               decisions=[
                   {"id": "d1", "kind": "normative", "status": "accepted", "statement": "1",
                    "supersedes": "d2"},
                   {"id": "d2", "kind": "normative", "status": "accepted", "statement": "2",
                    "supersedes": "d1"},
               ])
    res = _check(home)
    assert not res.ok
    assert any("supersedes cycle" in e for e in res.errors)


def test_empty_required_field_fails(make_project, write_leaf):
    # concept 一句話必填；空字串＝未填（舊 check 的 :162 bug 把 "" 當有填）
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1, "concept": ""})
    res = _check(home)
    assert not res.ok
    assert any("concept" in e and "empty" in e for e in res.errors)


def test_placeholder_required_field_fails(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "TODO", "order": 1})
    res = _check(home)
    assert not res.ok
    assert any("title" in e and "placeholder" in e for e in res.errors)


def test_wrong_type_order_fails(make_project, write_leaf):
    # order 必須是 number；字串 "1" 舊版靜默崩成 0.0
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": "1"})
    res = _check(home)
    assert not res.ok
    assert any("order" in e and "should be type" in e for e in res.errors)


def test_brief_layout_enum_recursion_fails(make_project, write_leaf):
    # brief 巢狀 sub-schema：layout enum 由遞迴驗（1.2）
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1,
                                     "brief": {"layout": "bogus"}})
    res = _check(home)
    assert not res.ok
    assert any("layout" in e for e in res.errors)


def test_brief_kind_enum_recursion_fails(make_project, write_leaf):
    # D2：brief.kind 是可選 enum；非法值由遞迴擋（但 present 才驗）。
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1,
                                     "brief": {"audience": "a", "depth": "d",
                                               "breadth": "b", "kind": "blog"}})
    res = _check(home)
    assert not res.ok
    assert any("kind" in e for e in res.errors)


def test_brief_kind_valid_passes(make_project, write_leaf):
    # D2：合法 kind 過；省略 kind 也過（可選、子繼承＝缺即合法）。
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1,
                                     "brief": {"audience": "a", "depth": "d",
                                               "breadth": "b", "kind": "reference"}})
    write_leaf(home, "a/y", concept={"id": "c2", "title": "Y", "order": 2,
                                     "brief": {"audience": "a", "depth": "d",
                                               "breadth": "b"}})   # no kind
    assert _check(home).ok


def test_brief_subfield_type_recursion_fails(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1,
                                     "brief": {"audience": ["should be string"]}})
    res = _check(home)
    assert not res.ok
    assert any("audience" in e and "should be type" in e for e in res.errors)


def test_brief_valid_passes(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1,
                                     "brief": {"audience": "devs", "depth": "deep",
                                               "breadth": "wide", "forbidden": [],
                                               "layout": "prose"}})
    assert _check(home).ok


def test_section_state_incomplete_is_developing(make_project, write_leaf):
    # 1.3：完整檔但必填欄空 → developing（不 ready、不擋寫）
    from dspx.commands.status import section_state
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1, "concept": ""},
               decisions=[{"id": "d1", "kind": "normative", "status": "accepted", "statement": "s"}])
    leaf = next(lf for lf in load_project(Layout(home)) if lf.section == "a/x")
    assert section_state(leaf, load_schema(), check_ok=True) == "developing"


def test_section_state_complete_is_ready(make_project, write_leaf):
    from dspx.commands.status import section_state
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1, "concept": "real",
                                     "brief": {"audience": "a", "depth": "d", "breadth": "b"}},
               decisions=[{"id": "d1", "kind": "normative", "status": "accepted", "statement": "s"}])
    leaf = next(lf for lf in load_project(Layout(home)) if lf.section == "a/x")
    assert section_state(leaf, load_schema(), check_ok=True) == "ready"


def test_root_brief_incomplete_fails(make_project, write_leaf):
    # 1.8(a)：root 節（無 '/'）必填 audience/depth/breadth；預設 brief {} → 紅
    home = make_project()
    write_leaf(home, "art", concept={"id": "c1", "title": "Art", "order": 1, "concept": "x"})
    res = _check(home)
    assert not res.ok
    assert any("brief" in e and "root" in e for e in res.errors)


def test_root_brief_complete_passes(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "art", concept={"id": "c1", "title": "Art", "order": 1, "concept": "x",
                                     "brief": {"audience": "a", "depth": "d", "breadth": "b"}},
               decisions=[{"id": "d1", "kind": "normative", "status": "accepted", "statement": "s"}])
    assert _check(home).ok


def test_sibling_order_collision_fails(make_project, write_leaf):
    # 1.8(b)
    home = make_project()
    write_leaf(home, "art/a", concept={"id": "c1", "title": "A", "order": 1, "concept": "x"})
    write_leaf(home, "art/b", concept={"id": "c2", "title": "B", "order": 1, "concept": "y"})
    res = _check(home)
    assert not res.ok
    assert any("collides" in e for e in res.errors)


def test_supersede_coherence_fails(make_project, write_leaf):
    # 1.8(c)：a supersedes b，但 b 仍 accepted、無 superseded-by → 紅
    home = make_project()
    write_leaf(home, "art/x", concept={"id": "c1", "title": "X", "order": 1, "concept": "x"},
               decisions=[
                   {"id": "a", "kind": "normative", "status": "accepted", "statement": "new",
                    "supersedes": "b"},
                   {"id": "b", "kind": "normative", "status": "accepted", "statement": "old"},
               ])
    res = _check(home)
    assert not res.ok
    assert any("superseded" in e for e in res.errors)


def test_supersede_coherence_passes(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "art/x", concept={"id": "c1", "title": "X", "order": 1, "concept": "x"},
               decisions=[
                   {"id": "a", "kind": "normative", "status": "accepted", "statement": "new",
                    "supersedes": "b"},
                   {"id": "b", "kind": "normative", "status": "superseded", "statement": "old",
                    "superseded-by": "a"},
               ])
    assert _check(home).ok


def test_governed_by_existing_concept_passes(make_project, write_leaf):
    # governed-by 指向存在的活 concept id → 綠
    home = make_project()
    write_leaf(home, "t1", concept={"id": "c-t1", "title": "T1", "order": 1, "concept": "x",
                                    "brief": {"audience": "a", "depth": "d", "breadth": "b"}})
    write_leaf(home, "t2", concept={"id": "c-t2", "title": "T2", "order": 2, "concept": "y",
                                    "brief": {"audience": "a", "depth": "d", "breadth": "b"},
                                    "governed-by": ["c-t1"]})
    assert _check(home).ok


def test_governed_by_nonexistent_fails(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "t2", concept={"id": "c-t2", "title": "T2", "order": 1, "concept": "y",
                                    "brief": {"audience": "a", "depth": "d", "breadth": "b"},
                                    "governed-by": ["c-nope"]})
    res = _check(home)
    assert not res.ok
    assert any("governed-by" in e and "c-nope" in e for e in res.errors)


def test_governed_by_decision_id_fails(make_project, write_leaf):
    # governed-by 指向 decision id（錯 kind）→ 報「非 concept」
    home = make_project()
    write_leaf(home, "t1", concept={"id": "c-t1", "title": "T1", "order": 1, "concept": "x",
                                    "brief": {"audience": "a", "depth": "d", "breadth": "b"}},
               decisions=[{"id": "dec-x", "kind": "normative", "status": "accepted",
                           "statement": "s"}])
    write_leaf(home, "t2", concept={"id": "c-t2", "title": "T2", "order": 2, "concept": "y",
                                    "brief": {"audience": "a", "depth": "d", "breadth": "b"},
                                    "governed-by": ["dec-x"]})
    res = _check(home)
    assert not res.ok
    assert any("governed-by" in e and "non-concept" in e for e in res.errors)


def test_governs_cycle_fails(make_project, write_leaf):
    # 兩個 concept 互相 governed-by → governs 成環
    home = make_project()
    write_leaf(home, "t1", concept={"id": "c-t1", "title": "T1", "order": 1, "concept": "x",
                                    "brief": {"audience": "a", "depth": "d", "breadth": "b"},
                                    "governed-by": ["c-t2"]})
    write_leaf(home, "t2", concept={"id": "c-t2", "title": "T2", "order": 2, "concept": "y",
                                    "brief": {"audience": "a", "depth": "d", "breadth": "b"},
                                    "governed-by": ["c-t1"]})
    res = _check(home)
    assert not res.ok
    assert any("governs cycle" in e for e in res.errors)
