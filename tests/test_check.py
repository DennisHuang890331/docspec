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


def test_realizes_to_retired_history_is_dead(make_project, write_leaf):
    # FG-1: realizing a decision that has been RETIRED into history is a dangling edge
    # (the consumer is anchored to a truth that no longer lives) — symmetric with the
    # governed-by → deprecated guard. check MUST fail-loud.
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1,
                                      "realizes": ["d-old"]},
               history=[{"id": "d-old", "kind": "normative", "status": "superseded",
                         "statement": "old"}])
    res = _check(home)
    assert not res.ok
    assert any("retired decision" in e and "d-old" in e for e in res.errors)


def test_realizes_to_superseded_but_present_passes(make_project, write_leaf):
    # A decision still living in decisions.yaml but marked superseded is a legitimate
    # transient migration window — check does NOT block (staleness + aperture handle it).
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1,
                                      "realizes": ["d-sup"]},
               decisions=[{"id": "d-sup", "kind": "normative", "status": "superseded",
                           "statement": "old but present", "superseded-by": "d-new"},
                          {"id": "d-new", "kind": "normative", "status": "accepted",
                           "statement": "new", "supersedes": "d-sup"}])
    assert _check(home).ok


def test_realizes_to_concept_is_wrong_edge(make_project, write_leaf):
    # realizes is for a shared decision; pointing it at a concept id is the wrong edge type
    # (governance is governed-by). check MUST fail-loud.
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1})
    write_leaf(home, "a/y", concept={"id": "c2", "title": "Y", "order": 2,
                                     "realizes": ["c1"]})
    res = _check(home)
    assert not res.ok
    assert any("concept id" in e and "c1" in e for e in res.errors)


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
    from dspx.commands.query.status import section_state
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1, "concept": ""},
               decisions=[{"id": "d1", "kind": "normative", "status": "accepted", "statement": "s"}])
    leaf = next(lf for lf in load_project(Layout(home)) if lf.section == "a/x")
    assert section_state(leaf, load_schema(), check_ok=True) == "developing"


def test_section_state_complete_is_ready(make_project, write_leaf):
    from dspx.commands.query.status import section_state
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


def test_deep_nesting_beyond_max_heading_level_fails(make_project, write_leaf):
    # 1.8(d)：章節樹過深 → 標題層級 > 四級（H5）→ render 會吐 #######＝字面文字、靜默破版 → check ERROR
    home = make_project()
    write_leaf(home, "g/a/b/c/d/e", concept={"id": "c1", "title": "葉", "order": 1})  # level 6 (五級)
    res = _check(home)
    assert not res.ok
    assert any("too deep" in e for e in res.errors)


def test_four_levels_deep_passes(make_project, write_leaf):
    # 四級（1.1.1.1）＝最深合法層級，不報深度錯（level 5）
    home = make_project()
    write_leaf(home, "g/a/b/c/d", concept={"id": "c1", "title": "葉", "order": 1})  # level 5 (四級)
    res = _check(home)
    assert not any("too deep" in e for e in res.errors)


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


def test_governs_cycle_path_has_no_leadin(make_project, write_leaf):
    """3-node 環，且有一個無辜下游節點當 DFS 引線：報出的環路徑必須從真正成環的節點起，
    不得把引線節點印在最前端（深森林誤導，Round 9 LOW-1）。t0 -> t1 -> t2 -> t3 -> t1。"""
    def gov(name, order, target):
        write_leaf(home, name,
                   concept={"id": f"c-{name}", "title": name.upper(), "order": order,
                            "concept": "x", "brief": {"audience": "a", "depth": "d", "breadth": "b"},
                            "governed-by": [target]})
    home = make_project()
    gov("t0", 1, "c-t1")   # 引線：t0 治於 t1，但 t0 不在環裡
    gov("t1", 2, "c-t2")
    gov("t2", 3, "c-t3")
    gov("t3", 4, "c-t1")   # 環：t1 -> t2 -> t3 -> t1
    res = _check(home)
    assert not res.ok
    cyc = next(e for e in res.errors if "governs cycle" in e)
    path = cyc.split("governs cycle:", 1)[1].strip()
    nodes = [p.strip() for p in path.split("→")]
    # 引線 c-t0 不得出現；路徑頭尾相同（閉環）且只含環上三節點
    assert "c-t0" not in nodes
    assert nodes[0] == nodes[-1]
    assert set(nodes) == {"c-t1", "c-t2", "c-t3"}


# ── 圖片引用完整性（Stage A：figure-embedding，需 layout）───────────────

def _check_with_layout(home):
    layout = Layout(home)
    leaves = load_project(layout)
    return run_check(leaves, load_schema(), layout)


def _write_latest(home, article, section, title, body):
    layout = Layout(home)
    latest = layout.docs_latest(article)
    latest.parent.mkdir(parents=True, exist_ok=True)
    latest.write_text(
        f"---\narticle: {article}\n---\n<!-- dspx:section {section} -->\n# {title}\n\n{body}\n",
        encoding="utf-8")


def _add_asset(home, section, name, data=b"\x89PNG\r\n\x1a\n_fake"):
    # Model A：圖資產住交付側 docs/assets/（per-article：docs/<article>/assets/），非 corpus。
    adir = Layout(home).docs_assets_dir(section.split("/")[0])
    adir.mkdir(parents=True, exist_ok=True)
    (adir / name).write_bytes(data)


def test_broken_image_ref_fails_check(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1})
    _write_latest(home, "a", "a/x", "X", "See ![diagram](assets/missing.svg) here.")
    res = _check_with_layout(home)
    assert not res.ok
    assert any("missing.svg" in e and "does not resolve" in e for e in res.errors)


def test_resolved_image_ref_passes_check(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1})
    _add_asset(home, "a/x", "diagram.svg")
    _write_latest(home, "a", "a/x", "X", "See ![diagram](assets/diagram.svg) here.")
    res = _check_with_layout(home)
    assert res.ok, res.errors


def test_external_image_ref_not_validated(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1})
    _write_latest(home, "a", "a/x", "X", "![remote](https://example.com/y.png)")
    res = _check_with_layout(home)
    assert res.ok, res.errors


def test_shared_asset_referenced_by_multiple_sections_passes(make_project, write_leaf):
    """Model A：圖集中在單一 `docs/assets/`。多節引用同一 `assets/diagram.svg`（同一實體檔）→
    無「扁平命名空間指向多節各自的檔」歧義（per-section 模型才有），check ⑨ 放行。
    撞名守門在 Model A 已消除（一個 basename 就是一個檔）。"""
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1})
    write_leaf(home, "a/y", concept={"id": "c2", "title": "Y", "order": 2})
    _add_asset(home, "a/x", "diagram.svg")   # Model A：寫進 docs/a/assets/diagram.svg（單一檔）
    layout = Layout(home)
    latest = layout.docs_latest("a")
    latest.parent.mkdir(parents=True, exist_ok=True)
    latest.write_text(
        "---\narticle: a\n---\n"
        "<!-- dspx:section a/x -->\n# X\n\n![d](assets/diagram.svg)\n\n"
        "<!-- dspx:section a/y -->\n# Y\n\n![d](assets/diagram.svg)\n",
        encoding="utf-8")
    res = _check_with_layout(home)
    assert res.ok, res.errors


def test_image_ref_check_skipped_without_latest(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1})
    res = _check_with_layout(home)   # no _latest.md rendered yet
    assert res.ok, res.errors


# ── diagram-intent 閘（C1：宣告 layout=diagram 卻零張圖＝機械落差）──────────

_DIAGRAM_BRIEF = {"audience": "devs", "depth": "deep", "breadth": "b", "layout": "diagram"}
_PROSE_BRIEF = {"audience": "devs", "depth": "deep", "breadth": "b", "layout": "prose"}


def test_declared_diagram_without_image_fails_check(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1,
                                     "brief": dict(_DIAGRAM_BRIEF)})
    _write_latest(home, "a", "a/x", "X", "Just prose, no figure embedded.")
    res = _check_with_layout(home)
    assert not res.ok
    assert any("layout=diagram" in e and "a/x" in e for e in res.errors)


def test_declared_diagram_with_image_passes_check(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1,
                                     "brief": dict(_DIAGRAM_BRIEF)})
    _add_asset(home, "a/x", "arch.png")
    _write_latest(home, "a", "a/x", "X", "![arch](assets/arch.png)")
    res = _check_with_layout(home)
    assert res.ok, res.errors


def test_declared_diagram_with_empty_body_not_flagged(make_project, write_leaf):
    """F-diagram-gate-blocks-incremental-build：宣告 layout=diagram 但散文尚未撰寫（body 空）
    → 閘不觸發，增量撰寫期間 check 保持綠（宣告 layout 先於作圖，不是機械落差）。"""
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1,
                                     "brief": dict(_DIAGRAM_BRIEF)})
    _write_latest(home, "a", "a/x", "X", "")   # 骨架已 render、散文未寫
    res = _check_with_layout(home)
    assert res.ok, res.errors


def test_diagram_gate_error_routes_to_drawio_track(make_project, write_leaf):
    """閘的錯誤訊息＝choke point：必須指路 drawio→PNG 正軌（dspx-diagram／--with-drawio），
    否則 naive 作者在這個失敗點會自己發明 mermaid。"""
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1,
                                     "brief": dict(_DIAGRAM_BRIEF)})
    _write_latest(home, "a", "a/x", "X", "Prose written, but no figure embedded.")
    res = _check_with_layout(home)
    assert not res.ok
    err = next(e for e in res.errors if "layout=diagram" in e)
    assert "dspx-diagram" in err
    assert "--with-drawio" in err


def test_non_diagram_without_image_not_flagged(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1,
                                     "brief": dict(_PROSE_BRIEF)})
    _write_latest(home, "a", "a/x", "X", "Just prose, no figure — and that's fine.")
    res = _check_with_layout(home)
    assert res.ok, res.errors


# ── F1：跨節決策依賴漏接結構邊。sources 填內部 id=ERROR、散文順帶提及=WARN ──────

def test_f1_sources_internal_id_is_error(make_project, write_leaf):
    """sources 契約只放外部出處；出現內部 decision id 卻無結構邊 → ERROR（無聲漂移陷阱、fail-loud）。"""
    home = make_project()
    write_leaf(home, "a/owner", concept={"id": "co", "title": "Owner", "order": 1},
               decisions=[{"id": "dec-split-plane", "kind": "normative",
                           "status": "accepted", "statement": "Split planes."}])
    write_leaf(home, "a/user", concept={"id": "cu", "title": "User", "order": 2,
                                        "sources": ["Builds on dec-split-plane."]})
    res = _check(home)
    assert not res.ok                                        # ERROR 擋下
    assert any("dec-split-plane" in e and "a/user" in e and "sources" in e for e in res.errors)


def test_f1_prose_ref_without_edge_warns(make_project, write_leaf):
    """A 的散文順帶明引 B 的決策 id，卻無結構邊 → 非阻塞 WARN（check 仍過）。"""
    home = make_project()
    write_leaf(home, "a/owner", concept={"id": "co", "title": "Owner", "order": 1},
               decisions=[{"id": "dec-shard-by-job", "kind": "normative",
                           "status": "accepted", "statement": "Shard by job id."}])
    write_leaf(home, "a/user", concept={"id": "cu", "title": "User", "order": 2,
                                        "concept": "We rely on dec-shard-by-job downstream."})
    res = _check(home)
    assert res.ok                                            # 非阻塞
    assert any("dec-shard-by-job" in w and "a/user" in w for w in res.warnings)


def test_f1_realizes_edge_suppresses_both(make_project, write_leaf):
    """已用 realizes 指向 → 依賴可見、staleness 生效 → 即使 id 也在 sources/散文，皆不 ERROR/WARN。"""
    home = make_project()
    write_leaf(home, "a/owner", concept={"id": "co", "title": "Owner", "order": 1},
               decisions=[{"id": "dec-shard-by-job", "kind": "normative",
                           "status": "accepted", "statement": "Shard by job id."}])
    write_leaf(home, "a/user", concept={"id": "cu", "title": "User", "order": 2,
                                        "realizes": ["dec-shard-by-job"],
                                        "sources": ["See dec-shard-by-job."],
                                        "concept": "We rely on dec-shard-by-job downstream."})
    res = _check(home)
    assert res.ok
    assert not any("dec-shard-by-job" in x for x in (*res.errors, *res.warnings))


def test_f1_governed_by_edge_suppresses(make_project, write_leaf):
    """引用的決策由 governed-by 的父節擁有 → 治理鏈已覆蓋 → 不報。"""
    home = make_project()
    write_leaf(home, "a/parent", concept={"id": "cp", "title": "Parent", "order": 1},
               decisions=[{"id": "dec-policy", "kind": "normative",
                           "status": "accepted", "statement": "Policy."}])
    write_leaf(home, "b/child", concept={"id": "cc", "title": "Child", "order": 1,
                                         "governed-by": ["cp"],
                                         "sources": ["Per dec-policy."]})
    res = _check(home)
    assert res.ok and not any("dec-policy" in x for x in (*res.errors, *res.warnings))


def test_f1_pure_semantic_prose_not_flagged(make_project, write_leaf):
    """純語義散文（無真實 id）→ 不誤報、不 ERROR（語義切片不由引擎 gate）。"""
    home = make_project()
    write_leaf(home, "a/owner", concept={"id": "co", "title": "Owner", "order": 1},
               decisions=[{"id": "dec-shard-by-job", "kind": "normative",
                           "status": "accepted", "statement": "Shard by job id."}])
    write_leaf(home, "a/user", concept={"id": "cu", "title": "User", "order": 2,
               "concept": "Consolidates the decisions recorded in the root and subsystem sections."})
    res = _check(home)
    assert res.ok
    assert res.warnings == []                                # 無真實 id → 不攔


def test_f1_own_decision_ref_not_flagged(make_project, write_leaf):
    """節引用自己擁有的決策 id → 非跨節 → 不報。"""
    home = make_project()
    write_leaf(home, "a/owner", concept={"id": "co", "title": "Owner", "order": 1,
                                         "concept": "Per dec-self we shard.",
                                         "sources": ["dec-self rationale."]},
               decisions=[{"id": "dec-self", "kind": "normative",
                           "status": "accepted", "statement": "Shard."}])
    res = _check(home)
    assert res.ok and res.warnings == []
