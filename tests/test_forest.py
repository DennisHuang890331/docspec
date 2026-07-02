"""森林地圖架構不變式：單向、derive（無第二份）、平行＝無邊、地圖只投 develop、
約束＝audit-only 非阻塞（無新引擎硬閘）。每條對應一個拍板的設計決策。"""

from __future__ import annotations

import yaml

from dspx.aperture import project
from dspx.check import run_check
from dspx.commands import impact as impact_cmd
from dspx.commands.impact import _analyze
from dspx.forest import forest_view
from dspx.layout import Layout
from dspx.model import load_project
from dspx.schema import load_schema


def _leaves(home):
    return load_project(Layout(home))


def _project(home, skill, section):
    layout = Layout(home)
    leaves = load_project(layout)
    return project(layout, load_schema(), skill, section, leaves)


def _two_tree_governed(make_project, write_leaf):
    """t2 governed-by t1（兩棵 root 樹、一條跨樹治理邊）。"""
    home = make_project()
    write_leaf(home, "t1", concept={"id": "c-t1", "title": "T1", "order": 1,
                                    "status": "draft", "concept": "T1 主旨",
                                    "brief": {"範圍": "一"}})
    write_leaf(home, "t2", concept={"id": "c-t2", "title": "T2", "order": 1,
                                    "status": "draft", "concept": "T2 主旨",
                                    "brief": {"範圍": "二"}, "governed-by": ["c-t1"]})
    return home


# ── 單向：父不存子，反向只由 impact 算 ──
def test_single_direction_parent_stores_no_child(make_project, write_leaf, monkeypatch, capsys):
    home = _two_tree_governed(make_project, write_leaf)
    # t1 自己的 concept 沒有任何指向 t2 的欄位（父不存子）
    t1_raw = yaml.safe_load(
        (home / "corpus" / "t1" / "concept.yaml").read_text(encoding="utf-8"))
    assert "governed-by" not in t1_raw
    assert all("c-t2" not in str(v) and "t2" != v for v in t1_raw.values())

    # 反向只由 impact 算出：impact c-t1 列出 governed-by ← t2
    monkeypatch.chdir(home.parent)
    assert impact_cmd.run(["c-t1"]) == 0
    out = capsys.readouterr().out
    assert "governed-by ← t2" in out


def test_impact_governed_by_json(make_project, write_leaf, monkeypatch, capsys):
    home = _two_tree_governed(make_project, write_leaf)
    monkeypatch.chdir(home.parent)
    import json
    assert impact_cmd.run(["c-t1", "--json"]) == 0
    info = json.loads(capsys.readouterr().out)
    assert info["governedBy"] == ["t2"]


def test_impact_governed_by_is_transitive(make_project, write_leaf, monkeypatch, capsys):
    """深森林 blast radius：改 t1（頂層）不只炸到直接 governed-by 它的 t2，還遞移炸到
    governed-by t2 的 t3（staleness 用同一 ancestor_leaves 算 stale-inherited）。Round 9 LOW-2。"""
    home = make_project()
    write_leaf(home, "t1", concept={"id": "c-t1", "title": "T1", "order": 1,
                                    "status": "draft", "concept": "T1 主旨", "brief": {"範圍": "一"}})
    write_leaf(home, "t2", concept={"id": "c-t2", "title": "T2", "order": 1,
                                    "status": "draft", "concept": "T2 主旨",
                                    "brief": {"範圍": "二"}, "governed-by": ["c-t1"]})
    write_leaf(home, "t3", concept={"id": "c-t3", "title": "T3", "order": 1,
                                    "status": "draft", "concept": "T3 主旨",
                                    "brief": {"範圍": "三"}, "governed-by": ["c-t2"]})
    info = _analyze(_leaves(home), "c-t1")
    assert info["governedBy"] == ["t2"]               # 直接
    assert info["governedTransitive"] == ["t3"]       # 遞移（過去被漏算 → blast radius 低估）

    # CLI blast radius 計入遞移 = 2（t2 直接 + t3 遞移），且 t3 標 inherited (transitive)
    monkeypatch.chdir(home.parent)
    assert impact_cmd.run(["c-t1"]) == 0
    out = capsys.readouterr().out
    assert "Blast radius: 2 section(s)" in out
    assert "governed-by ← t2" in out
    assert "inherited (transitive) ← t3" in out


# ── derive（無第二份）：刪掉 governed-by → hierarchy 立刻消失 ──
def test_forest_hierarchy_derives_from_governed_by(make_project, write_leaf):
    home = _two_tree_governed(make_project, write_leaf)
    f = forest_view(_leaves(home))
    assert any(h["childDoc"] == "t2" and h["parentDoc"] == "t1" for h in f["hierarchy"])
    assert f["hierarchy"][0]["via"] == [["c-t2", "c-t1"]]

    # 拿掉 t2 的 governed-by → hierarchy 立刻空（證明 derive 自 concept.governed-by，無第二存）
    write_leaf(home, "t2", concept={"id": "c-t2", "title": "T2", "order": 1,
                                    "status": "draft", "concept": "T2 主旨",
                                    "brief": {"範圍": "二"}})
    f2 = forest_view(_leaves(home))
    assert f2["hierarchy"] == []


# ── 平行＝無邊 ──
def test_parallel_is_no_edge(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "t1", concept={"id": "c-t1", "title": "T1", "order": 1,
                                    "status": "draft", "concept": "T1 主旨", "brief": {}})
    write_leaf(home, "t2", concept={"id": "c-t2", "title": "T2", "order": 1,
                                    "status": "draft", "concept": "T2 主旨", "brief": {}})
    f = forest_view(_leaves(home))
    assert f["hierarchy"] == []
    assert ["t1", "t2"] in f["parallel"]


def test_governed_pair_not_parallel(make_project, write_leaf):
    home = _two_tree_governed(make_project, write_leaf)
    f = forest_view(_leaves(home))
    assert ["t1", "t2"] not in f["parallel"]
    assert f["parallel"] == []


# ── 文件清單一句話 derive 自 root.concept ──
def test_documents_one_liner(make_project, write_leaf):
    home = _two_tree_governed(make_project, write_leaf)
    f = forest_view(_leaves(home))
    docs = {d["article"]: d for d in f["documents"]}
    assert docs["t1"]["oneLiner"] == "T1 主旨"
    assert docs["t1"]["conceptId"] == "c-t1"
    assert docs["t2"]["status"] == "draft"


# ── 地圖只投 develop ──
def test_map_only_develop(make_project, write_leaf):
    home = _two_tree_governed(make_project, write_leaf)
    assert isinstance(_project(home, "develop", "t2").forest, dict)
    for other in ("draft", "edit", "factcheck", "publish"):
        assert _project(home, other, "t2").forest is None


def test_develop_prints_forest_map(make_project, write_leaf, monkeypatch, capsys):
    home = _two_tree_governed(make_project, write_leaf)
    monkeypatch.chdir(home.parent)
    from dspx.commands import instructions as instr
    assert instr.run(["develop", "t2"]) == 0
    out = capsys.readouterr().out
    assert "Forest map" in out
    assert "t2 → t1" in out

    # draft 投影沒有森林地圖段
    assert instr.run(["draft", "t2"]) == 0
    assert "森林地圖" not in capsys.readouterr().out


# ── 約束＝audit-only 非阻塞：語義牴觸但結構合法 → check 綠、可 ready ──
def test_governed_by_adds_no_semantic_gate(make_project, write_leaf, monkeypatch):
    """t2 的 concept 語義上「牴觸」其 governed-by 父 t1，但結構（死引用/環）合法
    → run_check 仍綠（引擎只做結構檢查、不判語義、不新增硬閘）。"""
    home = make_project()
    full_brief = {"audience": "人", "depth": "gate", "breadth": "全", "forbidden": ["無"]}
    write_leaf(home, "t1", concept={"id": "c-t1", "title": "T1", "order": 1,
                                    "status": "draft",
                                    "concept": "一律使用公制單位", "brief": full_brief})
    write_leaf(home, "t2", concept={"id": "c-t2", "title": "T2", "order": 2,
                                    "status": "draft",
                                    "concept": "一律使用英制單位（直接牴觸 c-t1）",
                                    "brief": full_brief, "governed-by": ["c-t1"]})
    res = run_check(_leaves(home), load_schema())
    assert res.ok is True      # 語義牴觸不擋＝引擎不判語義

    # 且能畢業（ready）：給可榨乾的 develop + 完整 yaml
    write_leaf(home, "t2", concept={"id": "c-t2", "title": "T2", "order": 2,
                                    "status": "draft",
                                    "concept": "一律使用英制單位（直接牴觸 c-t1）",
                                    "brief": full_brief, "governed-by": ["c-t1"]},
               decisions=[{"id": "d-t2", "kind": "normative", "status": "accepted",
                           "statement": "用英制"}],
               develop="<!-- drained -->")
    monkeypatch.chdir(home.parent)
    from dspx.commands import ready as ready_cmd
    assert ready_cmd.run(["t2"]) == 0
    assert not (home / "corpus" / "t2" / "develop.md").exists()


# ── change `multi-document-governance-robustness`：治理感知 staleness + 守門 + 投影 ──

def test_governed_by_deprecated_concept_rejected(make_project, write_leaf):
    """M3：governed-by 指向 deprecated concept → check ERROR（退場概念不可被繼承）。"""
    home = make_project()
    write_leaf(home, "t1", concept={"id": "c-t1", "title": "T1", "order": 1,
                                    "status": "deprecated", "concept": "退場", "brief": {"範圍": "一"}})
    write_leaf(home, "t2", concept={"id": "c-t2", "title": "T2", "order": 1,
                                    "status": "draft", "concept": "二", "brief": {"範圍": "二"},
                                    "governed-by": ["c-t1"]})
    result = run_check(_leaves(home), load_schema(), Layout(home))
    assert not result.ok
    assert any("deprecated" in e for e in result.errors)


def test_governed_by_live_concept_not_flagged_deprecated(make_project, write_leaf):
    """M3 反例：governed-by 指存活 concept → 無 deprecated 報錯。"""
    home = _two_tree_governed(make_project, write_leaf)   # t1 status=draft（存活）
    result = run_check(_leaves(home), load_schema(), Layout(home))
    assert not any("deprecated" in e for e in result.errors)


def test_governed_parent_brief_change_restales_child(make_project, write_leaf):
    """M1：跨樹治理父 brief 變 → 被 governed 子節 anc 指紋變（staleness 傳播）。"""
    from dspx.model import ancestor_brief_fingerprint
    home = _two_tree_governed(make_project, write_leaf)
    by1 = {lf.section: lf for lf in _leaves(home)}
    fp1 = ancestor_brief_fingerprint("t2", by1)
    write_leaf(home, "t1", concept={"id": "c-t1", "title": "T1", "order": 1,
                                    "status": "draft", "concept": "T1 主旨", "brief": {"範圍": "一改"}})
    by2 = {lf.section: lf for lf in _leaves(home)}
    assert ancestor_brief_fingerprint("t2", by2) != fp1


def test_single_tree_fingerprint_ignores_unrelated_tree(make_project, write_leaf):
    """M1 回歸：無 governed-by 的單樹節，anc 指紋不受他樹變動影響（單樹等價不變式）。"""
    from dspx.model import ancestor_brief_fingerprint
    home = make_project()
    write_leaf(home, "doc", concept={"id": "r", "title": "Doc", "order": 1, "status": "draft",
                                     "concept": "root", "brief": {"a": "1"}})
    write_leaf(home, "doc/sec", concept={"id": "s", "title": "Sec", "order": 1, "status": "draft",
                                         "concept": "sec", "brief": {"b": "2"}})
    write_leaf(home, "other", concept={"id": "o", "title": "Other", "order": 1, "status": "draft",
                                       "concept": "o", "brief": {"c": "3"}})
    by1 = {lf.section: lf for lf in _leaves(home)}
    fp1 = ancestor_brief_fingerprint("doc/sec", by1)
    write_leaf(home, "other", concept={"id": "o", "title": "Other", "order": 1, "status": "draft",
                                       "concept": "o改", "brief": {"c": "9"}})
    by2 = {lf.section: lf for lf in _leaves(home)}
    assert ancestor_brief_fingerprint("doc/sec", by2) == fp1


def test_realizes_superseded_changes_deps_fingerprint(make_project, write_leaf):
    """M2：被 realizes 的決策 supersede（只改 status）→ 消費節 deps 指紋變（觸發 stale-upstream）。"""
    from dspx.model import deps_fingerprint, decision_index
    home = make_project()
    write_leaf(home, "auth", concept={"id": "c-auth", "title": "Auth", "order": 1, "status": "draft",
                                      "concept": "權威", "brief": {"a": "1"}},
               decisions=[{"id": "d1", "kind": "normative", "status": "accepted",
                           "statement": "X 是唯一真相"}])
    write_leaf(home, "consumer", concept={"id": "c-con", "title": "Con", "order": 1, "status": "draft",
                                          "concept": "消費", "brief": {"a": "2"}, "realizes": ["d1"]})
    leaves1 = _leaves(home)
    con1 = next(lf for lf in leaves1 if lf.section == "consumer")
    fp1 = deps_fingerprint(con1, decision_index(leaves1))
    write_leaf(home, "auth", concept={"id": "c-auth", "title": "Auth", "order": 1, "status": "draft",
                                      "concept": "權威", "brief": {"a": "1"}},
               decisions=[{"id": "d1", "kind": "normative", "status": "superseded",
                           "statement": "X 是唯一真相"}])
    leaves2 = _leaves(home)
    con2 = next(lf for lf in leaves2 if lf.section == "consumer")
    fp2 = deps_fingerprint(con2, decision_index(leaves2))
    assert fp1 and fp2 and fp1 != fp2


def test_draft_gets_governed_parent_normative(make_project, write_leaf):
    """M4 跨樹：draft 投影含 governed-by 父的 active normative ruling（落筆遵守、供料非 gate）。"""
    home = make_project()
    write_leaf(home, "t1", concept={"id": "c-t1", "title": "T1", "order": 1, "status": "draft",
                                    "concept": "權威", "brief": {"a": "1"}},
               decisions=[{"id": "d-gov", "kind": "normative", "status": "accepted",
                           "statement": "父 ruling"}])
    write_leaf(home, "t2", concept={"id": "c-t2", "title": "T2", "order": 1, "status": "draft",
                                    "concept": "子", "brief": {"a": "2"}, "governed-by": ["c-t1"]})
    proj = _project(home, "draft", "t2")
    assert any(d["id"] == "d-gov" for a in proj.ancestor_normative for d in a["decisions"])


def test_factcheck_coverage_contract_projected(make_project, write_leaf):
    """W3：factcheck 投影前景化 must_cover + layout/kind；draft 不投。"""
    home = make_project()
    write_leaf(home, "doc/sec", concept={"id": "c1", "title": "Sec", "order": 1, "status": "draft",
        "concept": "x", "must_cover": ["項目甲", "項目乙"],
        "brief": {"audience": "a", "depth": "d", "breadth": "b", "layout": "prose", "kind": "reference"}})
    cc = _project(home, "factcheck", "doc/sec").coverage_contract
    assert cc and cc["must_cover"] == ["項目甲", "項目乙"]
    assert cc["layout"] == "prose" and cc["kind"] == "reference"
    assert _project(home, "draft", "doc/sec").coverage_contract is None


# ── anchors：root concept ∪ 已被 governed-by 指到的 concept（Decision 4）──────


def _anchor_forest(make_project, write_leaf, *, edge=True):
    """文件 a：root（c-a-root）＋深路徑 anchor（c-a-anchor）＋無人指的 c-a-other；
    文件 b：root（c-b），edge=True 時 governed-by c-a-anchor。"""
    home = make_project()
    write_leaf(home, "a", concept={"id": "c-a-root", "title": "A根", "order": 1,
                                   "status": "draft", "concept": "A 主旨",
                                   "brief": {"範圍": "一"}})
    write_leaf(home, "a/deep/anchor", concept={"id": "c-a-anchor", "title": "深錨",
                                               "order": 1, "status": "draft",
                                               "concept": "深層治理錨點"})
    write_leaf(home, "a/other", concept={"id": "c-a-other", "title": "其他", "order": 2,
                                         "status": "draft", "concept": "無人指"})
    b_concept = {"id": "c-b", "title": "B", "order": 1, "status": "draft",
                 "concept": "B 主旨", "brief": {"範圍": "二"}}
    if edge:
        b_concept["governed-by"] = ["c-a-anchor"]
    write_leaf(home, "b", concept=b_concept)
    return home


def test_forest_anchors_root_and_targeted_listed(make_project, write_leaf):
    """6.1a：root concept ＋ 已被 governed-by 指到的非 root concept 都在 anchors（依 section 排序）；
    6.1b：無人指的非 root concept 不在。"""
    home = _anchor_forest(make_project, write_leaf)
    docs = {d["article"]: d for d in forest_view(_leaves(home))["documents"]}
    anchors = docs["a"]["anchors"]
    assert [a["id"] for a in anchors] == ["c-a-root", "c-a-anchor"]   # section 排序：a < a/deep/…
    assert anchors[1] == {"id": "c-a-anchor", "title": "深錨", "section": "a/deep/anchor"}
    assert all(a["id"] != "c-a-other" for a in anchors)               # 未被指到 → 不列
    assert [a["id"] for a in docs["b"]["anchors"]] == ["c-b"]         # b 只有 root


def test_forest_anchor_disappears_with_only_edge(make_project, write_leaf):
    """6.1c：移除唯一指向非 root anchor 的 governed-by → anchor 從候選消失（derive 自單一來源）。"""
    home = _anchor_forest(make_project, write_leaf, edge=False)
    docs = {d["article"]: d for d in forest_view(_leaves(home))["documents"]}
    assert [a["id"] for a in docs["a"]["anchors"]] == ["c-a-root"]


def test_develop_forest_map_prints_anchors_and_catalogue_hint(make_project, write_leaf,
                                                              monkeypatch, capsys):
    """6.2：instructions develop 的 Forest map 印 anchor 行＋目錄指引；非 develop 不投。"""
    home = _anchor_forest(make_project, write_leaf)
    monkeypatch.chdir(home.parent)
    from dspx.commands import instructions as instr
    assert instr.run(["develop", "b"]) == 0
    out = capsys.readouterr().out
    assert "    anchor: c-a-root — A根  (a)" in out
    assert "    anchor: c-a-anchor — 深錨  (a/deep/anchor)" in out
    assert "  (full concept catalogue of a document: docspec list <article> --json)" in out
    # 非 develop skill：forest=None → 無 anchor 行、無目錄指引
    assert instr.run(["draft", "b"]) == 0
    out2 = capsys.readouterr().out
    assert "anchor:" not in out2 and "full concept catalogue" not in out2


# ── impact 零命中訊息（Decision 12 / 13d）─────────────────────────────────────


def test_impact_zero_blast_message_not_orphan(make_project, write_leaf, monkeypatch, capsys):
    """10.1：未被消費的活 concept → 訊息說 not-yet-consumed／no inbound，非裸孤兒句；
    有下游時非零分支不變。"""
    home = make_project()
    write_leaf(home, "t1", concept={"id": "c-t1", "title": "T1", "order": 1, "status": "draft",
                                    "concept": "新 anchor", "brief": {"範圍": "一"}})
    monkeypatch.chdir(home.parent)
    assert impact_cmd.run(["c-t1"]) == 0
    out = capsys.readouterr().out
    assert "not-yet-consumed" in out and "no inbound" in out
    assert "(nothing depends on it)" not in out
    write_leaf(home, "t2", concept={"id": "c-t2", "title": "T2", "order": 1, "status": "draft",
                                    "concept": "子", "brief": {"範圍": "二"},
                                    "governed-by": ["c-t1"]})
    assert impact_cmd.run(["c-t1"]) == 0
    assert "(changing it means redoing these)" in capsys.readouterr().out
