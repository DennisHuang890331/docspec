"""crossdoc-impact：把既有跨文件真相圖反向 surface（反向索引 + show 三視圖）。

反作弊紀律：核心斷言是**反向 ≡ 正向反轉**（同源不漂）與**--impact 的 stale-upstream 集 ≡ 真改
決策後 section_state 標 stale-upstream 的節**（用既有投影對照），不挑「只斷 exit code」的軟柿子。
"""

from __future__ import annotations

import json

from dspx.commands.deliverable import render as render_cmd
from dspx.commands.query import show as show_cmd
from dspx.commands.query.status import _docs_hashes, _leaf_row
from dspx.crossref import build_reverse_indices
from dspx.layout import Layout
from dspx.model import ancestor_leaves, decision_index, load_project
from dspx.schema import load_schema


def _impact_project(make_project, write_leaf):
    """A 篇（root a → a/rules[dec-x] → a/rules/sub 路徑階層）；B 篇 b/impl realizes A 的 dec-x。"""
    home = make_project()
    write_leaf(home, "a", concept={"id": "c-a", "title": "A", "order": 0, "concept": "A 主旨",
                                   "brief": {"audience": "x", "depth": "y", "breadth": "z"}})
    write_leaf(home, "a/rules", concept={"id": "c-arules", "title": "規則", "order": 1,
                                         "concept": "規則層"},
               decisions=[{"id": "dec-x", "kind": "normative", "status": "accepted",
                           "statement": "頂層四態。"}])
    write_leaf(home, "a/rules/sub", concept={"id": "c-asub", "title": "子", "order": 1,
                                             "concept": "子層"})
    write_leaf(home, "b/impl", concept={"id": "c-bimpl", "title": "實作", "order": 1,
                                        "concept": "實作 A", "realizes": ["dec-x"]})
    return home


def _leaves(home):
    return load_project(Layout(home))


# ── 同源斷言（3.1）：反向 ≡ 正向反轉，釘死不漂 ─────────────────────────────

def test_reverse_realizes_is_forward_inverse(make_project, write_leaf):
    home = _impact_project(make_project, write_leaf)
    leaves = _leaves(home)
    ri = build_reverse_indices(leaves)
    # ⟸：reverse_realizes[d] 的每個成員都真的 realizes d
    for d, lfs in ri.reverse_realizes.items():
        for lf in lfs:
            assert d in [str(x) for x in (lf.concept.get("realizes") or [])]
    # ⟹：每個 realizes d 的 leaf 都在 reverse_realizes[d]
    for lf in leaves:
        for rid in (lf.concept.get("realizes") or []):
            assert lf in ri.reverse_realizes[str(rid)]


def test_descendants_is_ancestor_leaves_inverse(make_project, write_leaf):
    home = _impact_project(make_project, write_leaf)
    leaves = _leaves(home)
    ri = build_reverse_indices(leaves)
    by_section = {lf.section: lf for lf in leaves}
    concept_by_id = {lf.concept["id"]: lf for lf in leaves
                     if lf.concept and lf.concept.get("id")}
    # ⟸：leaf∈descendants[X] ⟹ X∈ancestor_leaves(leaf).sections
    for X, lfs in ri.descendants.items():
        for lf in lfs:
            anc_secs = [a.section for a, _ in ancestor_leaves(lf.section, by_section, concept_by_id)]
            assert X in anc_secs
    # ⟹：X∈ancestor_leaves(leaf) ⟹ leaf∈descendants[X]
    for lf in leaves:
        for a, _ in ancestor_leaves(lf.section, by_section, concept_by_id):
            assert lf in ri.descendants[a.section]
    # 具體：a 的子孫＝路徑鏈 a/rules, a/rules/sub
    assert sorted(l.section for l in ri.descendants["a"]) == ["a/rules", "a/rules/sub"]


# ── 3.2：--impact stale-upstream 集 ≡ 真改決策後 section_state 標 stale-upstream 的節 ──

def _sync_of(home, section):
    layout = Layout(home)
    leaves = load_project(layout)
    by = {lf.section: lf for lf in leaves}
    leaf = by[section]
    return _leaf_row(layout, leaf, load_schema(), True, _docs_hashes(layout, leaf.article),
                     by, decision_index(leaves))["sync"]


def test_impact_stale_upstream_matches_real_restale(make_project, write_leaf, monkeypatch, capsys):
    home = _impact_project(make_project, write_leaf)
    monkeypatch.chdir(home.parent)
    # 給 b/impl 落散文並定基準（含 deps 指紋）
    render_cmd.run(["b"])
    latest = home.parent / "docs" / "b" / "_latest.md"
    latest.write_text(
        latest.read_text(encoding="utf-8").replace("## 1. 實作\n", "## 1. 實作\n\n實作四態。\n"),
        encoding="utf-8")
    render_cmd.run(["b"])
    assert _sync_of(home, "b/impl") == "synced"

    # --impact 的預測（改 a/rules 之前）：stale-upstream = realizer 們
    capsys.readouterr()           # 清掉 render 的 stdout，別汙染 --json
    assert show_cmd.run(["a/rules", "--impact", "--json"]) == 0
    imp = json.loads(capsys.readouterr().out)
    predicted = {r["section"] for r in imp["staleUpstream"]}
    assert predicted == {"b/impl"}

    # 真改 a/rules 的 active 決策 statement → 重算全節 sync，收集 stale-upstream
    dec = home / "corpus" / "a" / "rules" / "decisions.yaml"
    dec.write_text(dec.read_text(encoding="utf-8").replace("頂層四態。", "頂層五態。"),
                   encoding="utf-8")
    layout = Layout(home)
    leaves = load_project(layout)
    by = {lf.section: lf for lf in leaves}
    actual = set()
    for lf in leaves:
        sync = _leaf_row(layout, lf, load_schema(), True, _docs_hashes(layout, lf.article),
                         by, decision_index(leaves))["sync"]
        if sync == "stale-upstream":
            actual.add(lf.section)
    assert actual == predicted   # ★同源：反向預測 ≡ 正向 staleness 實測


# ── 3.3：跨文件案例 ────────────────────────────────────────────────────────

def test_cross_file_realized_by_and_impact(make_project, write_leaf, monkeypatch, capsys):
    home = _impact_project(make_project, write_leaf)
    monkeypatch.chdir(home.parent)
    # A 的決策 dec-x --realized-by 含 B（跨全部文章）
    assert show_cmd.run(["dec-x", "--realized-by", "--json"]) == 0
    q = json.loads(capsys.readouterr().out)
    assert q["definedAt"] == "a/rules" and q["realizedBy"] == ["b/impl"]
    # 改 A 之前 show a/rules --impact：B 在 stale-upstream，來源＝A 的決策 dec-x
    assert show_cmd.run(["a/rules", "--impact", "--json"]) == 0
    imp = json.loads(capsys.readouterr().out)
    assert {"section": "b/impl", "viaDecision": "dec-x"} in imp["staleUpstream"]


def test_impact_norm_when_section_owns_active_normative(make_project, write_leaf, monkeypatch, capsys):
    """a/rules 有 active normative（dec-x）→ 其子孫（a/rules/sub）另標 stale-norm。"""
    home = _impact_project(make_project, write_leaf)
    monkeypatch.chdir(home.parent)
    assert show_cmd.run(["a/rules", "--impact", "--json"]) == 0
    imp = json.loads(capsys.readouterr().out)
    assert imp["staleInherited"] == ["a/rules/sub"]
    assert imp["staleNorm"] == ["a/rules/sub"]   # 有 active normative → 同集另標 norm


# ── 3.4：reverse_anchor 需 render 的邊角（誠實回報、非空集假裝無引用）─────────

def _anchor_project(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "g/a", concept={"id": "sec-a", "title": "甲", "order": 1, "concept": "甲節"})
    write_leaf(home, "g/b", concept={"id": "sec-b", "title": "乙", "order": 2, "concept": "乙節"})
    return home


def _inject_anchor(home, article, ref_section, anchor_id):
    """把指向 anchor_id 的散文錨塞進 ref_section 槽並重 render（注入號碼）。"""
    latest = home.parent / "docs" / article / "_latest.md"
    lines = latest.read_text(encoding="utf-8").split("\n")
    out, i = [], 0
    while i < len(lines):
        out.append(lines[i])
        if lines[i] == f"<!-- dspx:section {ref_section} -->" and i + 1 < len(lines):
            out.append(lines[i + 1])           # heading 行
            out.append("")
            out.append(f"見 <!--@{anchor_id}--><!--@--> 一節。")
            i += 2
            while i < len(lines) and lines[i].strip() == "":
                i += 1
            continue
        i += 1
    latest.write_text("\n".join(out), encoding="utf-8")
    assert render_cmd.run([article]) == 0


def test_referenced_by_unrendered_reports_need_render_not_empty(
        make_project, write_leaf, monkeypatch, capsys):
    home = _anchor_project(make_project, write_leaf)
    monkeypatch.chdir(home.parent)
    # 尚未 render：--referenced-by 必須明確回報「需先 render」，MUST NOT 空集假裝無引用
    assert show_cmd.run(["g/a", "--referenced-by"]) == 0
    out = capsys.readouterr().out
    assert "not yet rendered" in out and "g" in out
    assert "no prose cross-reference points at it" not in out


def test_referenced_by_lists_anchor_after_render(make_project, write_leaf, monkeypatch, capsys):
    home = _anchor_project(make_project, write_leaf)
    monkeypatch.chdir(home.parent)
    assert render_cmd.run(["g"]) == 0
    _inject_anchor(home, "g", "g/b", "sec-a")   # g/b 的散文指向 g/a（sec-a）

    # 反向索引：reverse_anchor[sec-a] 含 (g, g/b)
    layout = Layout(home)
    ri = build_reverse_indices(load_project(layout), layout)
    assert ("g", "g/b") in ri.reverse_anchor.get("sec-a", [])
    assert ri.unrendered_articles == []          # g 已 render

    # show g/a --referenced-by 列出 g/b
    capsys.readouterr()           # 清掉 render 的 stdout
    assert show_cmd.run(["g/a", "--referenced-by", "--json"]) == 0
    ref = json.loads(capsys.readouterr().out)
    assert any(r["article"] == "g" and r["section"] == "g/b" for r in ref["referencedBy"])


def test_impact_cross_reference_group(make_project, write_leaf, monkeypatch, capsys):
    """--impact 的跨參考類：改 g/a 前，指向它的散文錨（g/b）列在 crossReference。"""
    home = _anchor_project(make_project, write_leaf)
    monkeypatch.chdir(home.parent)
    assert render_cmd.run(["g"]) == 0
    _inject_anchor(home, "g", "g/b", "sec-a")
    capsys.readouterr()           # 清掉 render 的 stdout
    assert show_cmd.run(["g/a", "--impact", "--json"]) == 0
    imp = json.loads(capsys.readouterr().out)
    assert any(r["article"] == "g" and r["section"] == "g/b" and r["viaId"] == "sec-a"
               for r in imp["crossReference"])


def test_impact_not_a_leaf_errors(make_project, write_leaf, monkeypatch):
    home = _impact_project(make_project, write_leaf)
    monkeypatch.chdir(home.parent)
    assert show_cmd.run(["no/such/section", "--impact"]) == 1
