"""森林地圖架構不變式：單向、derive（無第二份）、平行＝無邊、地圖只投 develop、
約束＝audit-only 非阻塞（無新引擎硬閘）。每條對應一個拍板的設計決策。"""

from __future__ import annotations

import yaml

from dspx.aperture import project
from dspx.check import run_check
from dspx.commands import show as show_cmd
from dspx.crossref import build_reverse_indices
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


# ── 單向：父不存子，反向只由 show --impact（descendants）算 ──
def test_single_direction_parent_stores_no_child(make_project, write_leaf, monkeypatch, capsys):
    home = _two_tree_governed(make_project, write_leaf)
    # t1 自己的 concept 沒有任何指向 t2 的欄位（父不存子）
    t1_raw = yaml.safe_load(
        (home / "corpus" / "t1" / "concept.yaml").read_text(encoding="utf-8"))
    assert "governed-by" not in t1_raw
    assert all("c-t2" not in str(v) and "t2" != v for v in t1_raw.values())

    # 反向只由 show t1 --impact 算出：t2 是 t1 的子孫（stale-inherited）
    monkeypatch.chdir(home.parent)
    import json
    assert show_cmd.run(["t1", "--impact", "--json"]) == 0
    info = json.loads(capsys.readouterr().out)
    assert "t2" in info["staleInherited"]


def test_impact_descendants_json(make_project, write_leaf, monkeypatch, capsys):
    home = _two_tree_governed(make_project, write_leaf)
    monkeypatch.chdir(home.parent)
    import json
    assert show_cmd.run(["t1", "--impact", "--json"]) == 0
    info = json.loads(capsys.readouterr().out)
    assert info["staleInherited"] == ["t2"]


def test_impact_descendants_is_transitive(make_project, write_leaf, monkeypatch, capsys):
    """深森林 blast radius：改 t1（頂層）不只炸到直接 governed-by 它的 t2，還遞移炸到
    governed-by t2 的 t3（descendants 用同一 ancestor_leaves 反轉＝與 stale-inherited 同源）。"""
    home = make_project()
    write_leaf(home, "t1", concept={"id": "c-t1", "title": "T1", "order": 1,
                                    "status": "draft", "concept": "T1 主旨", "brief": {"範圍": "一"}})
    write_leaf(home, "t2", concept={"id": "c-t2", "title": "T2", "order": 1,
                                    "status": "draft", "concept": "T2 主旨",
                                    "brief": {"範圍": "二"}, "governed-by": ["c-t1"]})
    write_leaf(home, "t3", concept={"id": "c-t3", "title": "T3", "order": 1,
                                    "status": "draft", "concept": "T3 主旨",
                                    "brief": {"範圍": "三"}, "governed-by": ["c-t2"]})
    ri = build_reverse_indices(_leaves(home))
    assert sorted(lf.section for lf in ri.descendants["t1"]) == ["t2", "t3"]  # 直接 + 遞移

    # CLI stale-inherited 計入遞移（t2 直接 + t3 遞移）
    monkeypatch.chdir(home.parent)
    assert show_cmd.run(["t1", "--impact"]) == 0
    out = capsys.readouterr().out
    assert "stale-inherited" in out
    assert "t2" in out and "t3" in out


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
    for other in ("apply", "factcheck", "publish"):
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
    assert instr.run(["apply", "t2"]) == 0
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
    proj = _project(home, "apply", "t2")
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
    assert _project(home, "apply", "doc/sec").coverage_contract is None


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
    assert instr.run(["apply", "b"]) == 0
    out2 = capsys.readouterr().out
    assert "anchor:" not in out2 and "full concept catalogue" not in out2


# ── projection-order-and-map-fixes：parallel 遞移判準／concept-less root／環旗標 ──


def _grandparent_chain(make_project, write_leaf):
    """t3 治於 t2、t2 治於 t1（爺孫鏈，無 t3→t1 直接邊）＋ 真無關文件 t4。"""
    home = make_project()
    write_leaf(home, "t1", concept={"id": "c-t1", "title": "T1", "order": 1,
                                    "status": "draft", "concept": "T1 主旨", "brief": {}})
    write_leaf(home, "t2", concept={"id": "c-t2", "title": "T2", "order": 1,
                                    "status": "draft", "concept": "T2 主旨",
                                    "brief": {}, "governed-by": ["c-t1"]})
    write_leaf(home, "t3", concept={"id": "c-t3", "title": "T3", "order": 1,
                                    "status": "draft", "concept": "T3 主旨",
                                    "brief": {}, "governed-by": ["c-t2"]})
    write_leaf(home, "t4", concept={"id": "c-t4", "title": "T4", "order": 1,
                                    "status": "draft", "concept": "T4 主旨", "brief": {}})
    return home


def test_parallel_is_transitive_grandparent_not_parallel(make_project, write_leaf):
    """4.1：遞移判準——爺孫（t1 遞移可達 t3 的反向）不標平行；真無關文件（t4）仍平行；
    hierarchy 仍只含直接 rollup 邊（rollup 定義不變）。"""
    home = _grandparent_chain(make_project, write_leaf)
    f = forest_view(_leaves(home))
    assert ["t1", "t3"] not in f["parallel"]                      # 爺孫不平行（原判準誤標）
    assert ["t1", "t4"] in f["parallel"] and ["t3", "t4"] in f["parallel"]
    assert sorted((h["childDoc"], h["parentDoc"]) for h in f["hierarchy"]) == [
        ("t2", "t1"), ("t3", "t2")]                               # 無 t3→t1 直接邊


def test_conceptless_root_listed_with_group_title(make_project, write_leaf):
    """4.2：root 未結晶但樹已有帶 concept 的 leaf → documents 條目不蒸發：conceptId=null、
    oneLiner 取 group.yaml title、rootCrystallized=false；已結晶條目標 true；anchors 照舊
    derive；該 article 參與 parallel——hierarchy 與 documents 不再自相矛盾。"""
    home = make_project()
    write_leaf(home, "t1", concept={"id": "c-t1", "title": "T1", "order": 1,
                                    "status": "draft", "concept": "T1 主旨", "brief": {}})
    # 施工中樹：只有深處 leaf 有 concept（其 cid 經 governed-by 進 hierarchy）、root 未結晶
    write_leaf(home, "wip/part", concept={"id": "c-wp", "title": "部件", "order": 1,
                                          "status": "draft", "concept": "部件主旨",
                                          "governed-by": ["c-t1"]})
    (home / "corpus" / "wip" / "group.yaml").write_text("title: 施工中文件\n", encoding="utf-8")
    f = forest_view(_leaves(home), Layout(home))
    docs = {d["article"]: d for d in f["documents"]}
    assert "wip" in docs                                          # 不蒸發
    wip = docs["wip"]
    assert wip["conceptId"] is None and wip["status"] is None
    assert wip["oneLiner"] == "施工中文件"                        # group.yaml title（render 同機制）
    assert wip["rootCrystallized"] is False
    assert docs["t1"]["rootCrystallized"] is True                 # 既有條目 additive 標 true
    # hierarchy 的 wip→t1 邊有 documents 條目對應（地圖不再自相矛盾）
    assert any(h["childDoc"] == "wip" and h["parentDoc"] == "t1" for h in f["hierarchy"])
    assert ["t1", "wip"] not in f["parallel"]                     # 有邊＝非平行（參與判準）


def test_conceptless_root_slug_fallback_without_layout(make_project, write_leaf):
    """4.2：無 group.yaml（或無 layout 可讀）→ oneLiner humanize slug fallback。"""
    home = make_project()
    write_leaf(home, "t1", concept={"id": "c-t1", "title": "T1", "order": 1,
                                    "status": "draft", "concept": "T1 主旨", "brief": {}})
    write_leaf(home, "wip-doc/part", concept={"id": "c-wp", "title": "部件", "order": 1,
                                              "status": "draft", "concept": "部件",
                                              "governed-by": ["c-t1"]})
    for f in (forest_view(_leaves(home), Layout(home)), forest_view(_leaves(home))):
        wip = next(d for d in f["documents"] if d["article"] == "wip-doc")
        assert wip["oneLiner"] == "Wip Doc" and wip["rootCrystallized"] is False


def _mutual_governance(make_project, write_leaf):
    """t1⇄t2 互治成環（check 會另外紅）＋ 無環邊 t3→t1。"""
    home = make_project()
    write_leaf(home, "t1", concept={"id": "c-t1", "title": "T1", "order": 1,
                                    "status": "draft", "concept": "T1 主旨",
                                    "brief": {}, "governed-by": ["c-t2"]})
    write_leaf(home, "t2", concept={"id": "c-t2", "title": "T2", "order": 1,
                                    "status": "draft", "concept": "T2 主旨",
                                    "brief": {}, "governed-by": ["c-t1"]})
    write_leaf(home, "t3", concept={"id": "c-t3", "title": "T3", "order": 1,
                                    "status": "draft", "concept": "T3 主旨",
                                    "brief": {}, "governed-by": ["c-t1"]})
    return home


def test_cycle_edges_flagged_additively(make_project, write_leaf):
    """4.3：互治成環兩邊皆帶 cycle: true；無環邊不加欄；旗標不改 check 行為（成環的硬紅燈
    仍是 check 的、由它照舊報錯）。"""
    home = _mutual_governance(make_project, write_leaf)
    f = forest_view(_leaves(home))
    by_edge = {(h["childDoc"], h["parentDoc"]): h for h in f["hierarchy"]}
    assert by_edge[("t1", "t2")].get("cycle") is True
    assert by_edge[("t2", "t1")].get("cycle") is True
    assert "cycle" not in by_edge[("t3", "t1")]                   # 無環邊不加欄（省噪）
    # 地圖只標不擋：check 的 governs 成環紅燈不因旗標改變（照舊 fail）
    result = run_check(_leaves(home), load_schema(), Layout(home))
    assert not result.ok


def test_no_cycle_flag_on_acyclic_forest_and_check_green(make_project, write_leaf):
    """4.3 對照：無環森林——任何邊都無 cycle 欄、check 不因本旗標多紅。"""
    home = make_project()
    full_brief = {"audience": "人", "depth": "gate", "breadth": "全", "forbidden": ["無"]}
    write_leaf(home, "t1", concept={"id": "c-t1", "title": "T1", "order": 1,
                                    "status": "draft", "concept": "T1 主旨", "brief": full_brief})
    write_leaf(home, "t2", concept={"id": "c-t2", "title": "T2", "order": 2,
                                    "status": "draft", "concept": "T2 主旨",
                                    "brief": full_brief, "governed-by": ["c-t1"]})
    f = forest_view(_leaves(home))
    assert all("cycle" not in h for h in f["hierarchy"])
    assert run_check(_leaves(home), load_schema(), Layout(home)).ok


def test_develop_forest_map_prints_uncrystallized_note_and_cycle_warning(
        make_project, write_leaf, monkeypatch, capsys):
    """4.4：Forest map 人讀輸出——未結晶 root 行帶 (root not yet crystallized)；
    環上邊行帶成環警示（指出 check 會報錯）；正常條目不帶。"""
    home = _mutual_governance(make_project, write_leaf)
    # 加一棵施工中樹（root 未結晶）
    write_leaf(home, "wip/part", concept={"id": "c-wp", "title": "部件", "order": 1,
                                          "status": "draft", "concept": "部件主旨",
                                          "governed-by": ["c-t3"]})
    (home / "corpus" / "wip" / "group.yaml").write_text("title: 施工中文件\n", encoding="utf-8")
    monkeypatch.chdir(home.parent)
    from dspx.commands import instructions as instr
    assert instr.run(["develop", "t3"]) == 0
    out = capsys.readouterr().out
    assert "[wip] 施工中文件  (root not yet crystallized)" in out
    assert "  t1 → t2  ⚠ governs cycle — `docspec check` will fail" in out
    assert "  t2 → t1  ⚠ governs cycle — `docspec check` will fail" in out
    # 正常條目/無環邊不帶字樣
    t3_line = next(ln for ln in out.splitlines() if ln.startswith("  [t3]"))
    assert "not yet crystallized" not in t3_line
    t3_edge = next(ln for ln in out.splitlines() if ln.startswith("  t3 → t1"))
    assert "cycle" not in t3_edge


# ── show --impact 零命中訊息（誠實回報「無跨節影響」，非錯誤）─────────────────────


def test_impact_zero_blast_message(make_project, write_leaf, monkeypatch, capsys):
    """未被消費的活 concept（無子孫、無 realizer、無錨）→ 回「no cross-section impact」；
    有下游後非零分支列出子孫。"""
    home = make_project()
    write_leaf(home, "t1", concept={"id": "c-t1", "title": "T1", "order": 1, "status": "draft",
                                    "concept": "新 anchor", "brief": {"範圍": "一"}})
    monkeypatch.chdir(home.parent)
    assert show_cmd.run(["t1", "--impact"]) == 0
    out = capsys.readouterr().out
    assert "no cross-section impact" in out
    write_leaf(home, "t2", concept={"id": "c-t2", "title": "T2", "order": 1, "status": "draft",
                                    "concept": "子", "brief": {"範圍": "二"},
                                    "governed-by": ["c-t1"]})
    assert show_cmd.run(["t1", "--impact"]) == 0
    out2 = capsys.readouterr().out
    assert "no cross-section impact" not in out2
    assert "t2" in out2
