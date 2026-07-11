"""aperture 投影：draft 欄位裁切、develop 防漏、父鏈 brief。"""

from __future__ import annotations

import pytest

from dspx.aperture import ApertureError, project
from dspx.config import load_config
from dspx.layout import Layout
from dspx.model import load_project
from dspx.schema import load_schema


def _project(home, skill, section):
    layout = Layout(home)
    leaves = load_project(layout)
    return project(layout, load_schema(), skill, section, leaves, load_config(home))


def test_draft_crops_concept_to_four_fields(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "a/x", concept={
        "id": "c1", "title": "X", "order": 1, "status": "draft",
        "concept": "講 X", "brief": {"受眾": "人"}, "must_cover": ["a"],
        "sources": ["s"], "realizes": ["d1"],
    }, decisions=[{"id": "d1", "kind": "normative", "status": "accepted", "statement": "規"}])

    proj = _project(home, "draft", "a/x")
    concept_text = proj.reads["concept"]
    # 准投的四欄在
    assert "concept" in concept_text and "brief" in concept_text
    assert "must_cover" in concept_text and "sources" in concept_text
    # 治理欄不投
    assert "realizes" not in concept_text


def test_draft_decisions_statement_only(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1},
               decisions=[
                   {"id": "d1", "kind": "normative", "status": "accepted",
                    "statement": "活的規範", "rationale": "祕密理由",
                    "rejected": ["否決案"]},
                   {"id": "d2", "kind": "normative", "status": "deprecated",
                    "statement": "退場的"},
               ])
    proj = _project(home, "draft", "a/x")
    dtext = proj.reads["decisions"]
    assert "活的規範" in dtext
    assert "祕密理由" not in dtext      # rationale 剝除
    assert "否決案" not in dtext        # rejected 剝除
    assert "退場的" not in dtext        # 非 active 不投


def test_draft_never_sees_develop_or_history(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1},
               develop="# 機密草稿亂想",
               history=[{"id": "h1", "kind": "normative", "status": "superseded",
                         "statement": "墳場"}])
    proj = _project(home, "draft", "a/x")
    assert "develop" not in proj.reads
    assert "history" not in proj.reads


def test_develop_is_only_reader_of_develop(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1},
               develop="# 草稿內容")
    proj = _project(home, "develop", "a/x")
    assert "草稿內容" in proj.reads["develop"]


def test_purpose_projected_to_develop_and_draft(make_project, write_leaf):
    """config.purpose 投 develop 開工脈絡＋draft 寫定向 overview 的北極星（W2）；edit 不帶。"""
    home = make_project("language: zh-TW\ndocs_layout: per-article\npurpose: 把分散文件統一成一座森林\n")
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1})
    assert _project(home, "develop", "a/x").project_purpose == "把分散文件統一成一座森林"
    assert _project(home, "draft", "a/x").project_purpose == "把分散文件統一成一座森林"
    assert _project(home, "edit", "a/x").project_purpose is None


def test_purpose_empty_not_projected(make_project, write_leaf):
    """purpose 空（未填）→ develop 投影 None（不印空行）。"""
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1})
    assert _project(home, "develop", "a/x").project_purpose is None


def test_parent_brief_chain(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "art", concept={"id": "root", "title": "Art", "order": 1,
                                     "concept": "整篇主旨", "brief": {"受眾": "讀者"}})
    write_leaf(home, "art/sec", concept={"id": "c1", "title": "Sec", "order": 1})
    proj = _project(home, "draft", "art/sec")
    assert proj.parent_briefs
    assert proj.parent_briefs[0]["section"] == "art"
    assert proj.parent_briefs[0]["concept"] == "整篇主旨"


def test_path_only_regression_governed_false(make_project, write_leaf):
    """path-only 單樹：parent_briefs 只含路徑父、全 governed:False；
    factcheck 的 ancestor_normative 與 path-only 預期相同。"""
    home = make_project()
    write_leaf(home, "art", concept={"id": "root", "title": "Art", "order": 1,
                                     "concept": "整篇主旨", "brief": {"受眾": "讀者"}},
               decisions=[{"id": "dn", "kind": "normative", "status": "accepted",
                           "statement": "根規範"}])
    write_leaf(home, "art/sec", concept={"id": "c1", "title": "Sec", "order": 1})
    # draft 投影：只一個路徑父，governed False
    proj = _project(home, "draft", "art/sec")
    assert proj.parent_briefs == [{
        "section": "art", "concept": "整篇主旨",
        "brief": {"受眾": "讀者"}, "governed": False,
    }]
    # factcheck 投影：ancestor_normative 含根的 normative（path-only 等價）
    fc = _project(home, "factcheck", "art/sec")
    assert fc.ancestor_normative == [
        {"section": "art", "decisions": [{"id": "dn", "statement": "根規範"}]}
    ]
    assert all(pb["governed"] is False for pb in fc.parent_briefs)


def test_cross_tree_governed_brief_and_normative(make_project, write_leaf):
    """跨樹：t2 的 concept governed-by [c-t1] → 繼承 t1 的 brief（governed:True）
    與 t1 的 normative 決策（factcheck）。"""
    home = make_project()
    write_leaf(home, "t1", concept={"id": "c-t1", "title": "T1", "order": 1,
                                    "concept": "T1 主旨", "brief": {"範圍": "一"}},
               decisions=[{"id": "d-t1", "kind": "normative", "status": "accepted",
                           "statement": "T1 規範"}])
    write_leaf(home, "t2", concept={"id": "c-t2", "title": "T2", "order": 1,
                                    "concept": "T2 主旨", "brief": {"範圍": "二"},
                                    "governed-by": ["c-t1"]})
    proj = _project(home, "draft", "t2")
    govs = [pb for pb in proj.parent_briefs if pb.get("governed")]
    assert any(pb["section"] == "t1" and pb["concept"] == "T1 主旨"
               and pb["brief"] == {"範圍": "一"} for pb in govs)
    # factcheck 撈跨樹 normative
    fc = _project(home, "factcheck", "t2")
    assert {"section": "t1",
            "decisions": [{"id": "d-t1", "statement": "T1 規範"}]} in fc.ancestor_normative


def test_transitive_governed_chain(make_project, write_leaf):
    """t3 governed-by t2、t2 governed-by t1 → t3 祖先含 t2 與 t1。"""
    home = make_project()
    write_leaf(home, "t1", concept={"id": "c-t1", "title": "T1", "order": 1,
                                    "concept": "T1 主旨", "brief": {}})
    write_leaf(home, "t2", concept={"id": "c-t2", "title": "T2", "order": 1,
                                    "concept": "T2 主旨", "brief": {},
                                    "governed-by": ["c-t1"]})
    write_leaf(home, "t3", concept={"id": "c-t3", "title": "T3", "order": 1,
                                    "concept": "T3 主旨", "brief": {},
                                    "governed-by": ["c-t2"]})
    proj = _project(home, "draft", "t3")
    secs = {pb["section"] for pb in proj.parent_briefs}
    assert "t2" in secs and "t1" in secs
    assert all(pb["governed"] is True for pb in proj.parent_briefs)


def test_cycle_safety_terminates(make_project, write_leaf):
    """互治環（t1 governed-by t2、t2 governed-by t1）：closure 終止不掛。"""
    home = make_project()
    write_leaf(home, "t1", concept={"id": "c-t1", "title": "T1", "order": 1,
                                    "concept": "T1", "brief": {},
                                    "governed-by": ["c-t2"]})
    write_leaf(home, "t2", concept={"id": "c-t2", "title": "T2", "order": 1,
                                    "concept": "T2", "brief": {},
                                    "governed-by": ["c-t1"]})
    # 不應無限迴圈；visited 自保
    proj = _project(home, "draft", "t1")
    secs = {pb["section"] for pb in proj.parent_briefs}
    assert secs == {"t2"}      # t1 自己不算祖先；t2 經 governed-by 進來一次


def test_glossary_injected_as_lean_index(make_project, write_leaf):
    """glossary 注入＝精瘦索引（canonical/bucket/code/aliases_forbidden）；definition/english 不注入（下鑽）。"""
    import yaml
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1})
    (home / "glossary.yaml").write_text(yaml.safe_dump({"terms": [
        {"id": "rmm", "canonical": "風險估測系統", "bucket": "module", "code": "RMM",
         "english": "Risk Monitoring Module", "definition": "監測異常的子系統。",
         "aliases_forbidden": ["安全監控系統"]},
    ]}, allow_unicode=True, sort_keys=False), encoding="utf-8")
    for skill in ("draft", "edit", "factcheck"):
        proj = _project(home, skill, "a/x")
        assert len(proj.glossary) == 1
        term = proj.glossary[0]
        assert set(term) == {"id", "canonical", "bucket", "code", "aliases_forbidden"}
        assert "definition" not in term and "english" not in term
        assert term["canonical"] == "風險估測系統"


def test_unknown_skill_raises(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1})
    with pytest.raises(ApertureError):
        _project(home, "nonskill", "a/x")


# ── roadmap 投影（Seam 3；只投 develop）──────────────────────────────

def _write_roadmap(path, entries):
    import yaml
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"entries": entries}, allow_unicode=True,
                                   sort_keys=False), encoding="utf-8")


def _roadmap_fixture(home, write_leaf):
    """art 文件＋forest roadmap：本文件 open/doing/done ＋ forest open。"""
    write_leaf(home, "art", concept={"id": "c-art", "title": "Art", "order": 1,
                                     "concept": "x", "brief": {"audience": "a"}})
    _write_roadmap(home / "roadmap.yaml", [
        {"id": "f1", "kind": "task", "status": "open", "title": "森林工作",
         "what": "w", "target": "forest"},
    ])
    _write_roadmap(home / "corpus" / "art" / "roadmap.yaml", [
        {"id": "r-open", "kind": "task", "status": "open", "title": "可開工",
         "what": "w", "target": "art"},
        {"id": "r-doing", "kind": "task", "status": "doing", "title": "進行中",
         "what": "w", "target": "c-art"},
        {"id": "r-done", "kind": "task", "status": "done", "title": "已完成",
         "what": "w", "target": "art", "done-to": "d1"},
    ])


def test_develop_roadmap_includes_doc_and_forest_open(make_project, write_leaf):
    home = make_project()
    _roadmap_fixture(home, write_leaf)
    proj = _project(home, "develop", "art")
    assert proj.roadmap is not None
    ids = {e["id"] for e in proj.roadmap}
    assert {"r-open", "r-doing", "f1"} <= ids   # 本文件 open/doing ＋ forest open
    assert "r-done" not in ids                   # done 掉出


def test_develop_roadmap_carries_derive_flags(make_project, write_leaf):
    home = make_project()
    _roadmap_fixture(home, write_leaf)
    proj = _project(home, "develop", "art")
    by_id = {e["id"]: e for e in proj.roadmap}
    assert by_id["r-open"]["unblocked"] is True
    assert by_id["r-doing"]["status"] == "doing"


def test_non_develop_skills_have_no_roadmap(make_project, write_leaf):
    home = make_project()
    _roadmap_fixture(home, write_leaf)
    for skill in ("draft", "edit", "factcheck"):
        proj = _project(home, skill, "art")
        assert proj.roadmap is None


# ── 圖片資產（Stage A：figure-embedding）────────────────────────────

def _add_asset(home, section, name, data=b"\x89PNG\r\n\x1a\n_fake"):
    # Model A：圖資產住交付側 docs/assets/（per-article layout：docs/<article>/assets/），非 corpus。
    adir = Layout(home).docs_assets_dir(section.split("/")[0])
    adir.mkdir(parents=True, exist_ok=True)
    (adir / name).write_bytes(data)
    return adir / name


def test_draft_sees_image_assets_as_refs(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1})
    _add_asset(home, "a/x", "diagram.svg")
    _add_asset(home, "a/x", "photo.png")
    proj = _project(home, "draft", "a/x")
    # 投的是 backend-neutral 引用路徑、依檔名排序
    assert proj.image_assets == ["assets/diagram.svg", "assets/photo.png"]


def test_image_assets_only_for_draft_and_edit(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1})
    _add_asset(home, "a/x", "d.png")
    assert _project(home, "draft", "a/x").image_assets == ["assets/d.png"]
    assert _project(home, "edit", "a/x").image_assets == ["assets/d.png"]
    # factcheck/develop 不需要放圖 → 不投
    assert _project(home, "factcheck", "a/x").image_assets == []
    assert _project(home, "develop", "a/x").image_assets == []


def test_no_assets_dir_means_empty(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1})
    assert _project(home, "draft", "a/x").image_assets == []


def test_non_image_files_in_assets_ignored(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1})
    _add_asset(home, "a/x", "keep.svg")
    _add_asset(home, "a/x", "notes.txt")   # 非圖片副檔名 → 忽略
    assert _project(home, "draft", "a/x").image_assets == ["assets/keep.svg"]


def test_draft_sees_document_map_in_order(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "art", concept={"id": "r", "title": "Root", "order": 0,
                                      "concept": "定位總覽",
                                      "brief": {"audience": "a", "depth": "d", "breadth": "b"}})
    write_leaf(home, "art/beta", concept={"id": "b", "title": "Beta", "order": 2, "concept": "界定 B"})
    write_leaf(home, "art/alpha", concept={"id": "a", "title": "Alpha", "order": 1, "concept": "界定 A"})
    proj = _project(home, "draft", "art/alpha")
    secs = [n["section"] for n in proj.document_map]
    assert secs == ["art", "art/alpha", "art/beta"]   # 依 outline order
    by_sec = {n["section"]: n for n in proj.document_map}
    assert by_sec["art/alpha"]["role"] == "界定 A" and by_sec["art/alpha"]["title"] == "Alpha"


def test_document_map_is_structure_only_no_sibling_prose(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "art", concept={"id": "r", "title": "Root", "order": 0, "concept": "總覽",
                                      "brief": {"audience": "a", "depth": "d", "breadth": "b"}})
    write_leaf(home, "art/x", concept={"id": "x", "title": "X", "order": 1, "concept": "X 角色"},
               material="SIBLING_SECRET_PROSE 不該外洩",
               decisions=[{"id": "dx", "kind": "normative", "status": "accepted",
                           "statement": "SIBLING_DECISION_STMT"}])
    proj = _project(home, "draft", "art")   # 從 root 看 map，含 sibling art/x
    blob = repr(proj.document_map)
    assert "art/x" in blob and "X 角色" in blob          # 結構（role）在
    assert "SIBLING_SECRET_PROSE" not in blob            # 鄰節 material 不洩
    assert "SIBLING_DECISION_STMT" not in blob           # 鄰節 decision 不洩


def _ordered_group_corpus(home, write_leaf):
    """projection-order-and-map-fixes 2.4 fixture：annex 群 order 殿後（group.yaml order=99）、
    末節 order 與字典序相反（annex-b 字典序最前、outline 殿後；foreword 0.5 最前）。"""
    write_leaf(home, "art/foreword", concept={"id": "c-fw", "title": "前言", "order": 0.5,
                                              "concept": "開場"})
    write_leaf(home, "art/intro", concept={"id": "c-in", "title": "簡介", "order": 1,
                                           "concept": "導入"})
    write_leaf(home, "art/annex-b/ground", concept={"id": "c-bg", "title": "地面", "order": 1,
                                                    "concept": "附錄內容"})
    (home / "corpus" / "art" / "annex-b").mkdir(parents=True, exist_ok=True)
    (home / "corpus" / "art" / "annex-b" / "group.yaml").write_text(
        "title: 附錄B\norder: 99\n", encoding="utf-8")


def test_document_map_follows_shared_outline_order_with_groups(make_project, write_leaf,
                                                               monkeypatch):
    """2.4：documentMap 列序＝render 交付物順序（group.yaml order 生效、非字典序）；
    group 列存在（kind=group、在地化 title、group order、無 role）；leaf 列 additive 補 kind。"""
    home = make_project()
    _ordered_group_corpus(home, write_leaf)
    proj = _project(home, "draft", "art/intro")
    secs = [n["section"] for n in proj.document_map]
    # 字典序會是 annex-b 最前；outline 順序＝foreword(0.5) < intro(1) < 附錄B群(99)
    assert secs == ["art/foreword", "art/intro", "art/annex-b", "art/annex-b/ground"]
    by_sec = {n["section"]: n for n in proj.document_map}
    g = by_sec["art/annex-b"]
    assert g["kind"] == "group" and g["title"] == "附錄B" and g["order"] == 99.0
    assert g["role"] is None
    assert set(g) == {"section", "title", "order", "number", "role", "kind"}   # structure-only、無散文欄
    assert by_sec["art/intro"]["kind"] == "leaf"

    # documentMap 列序＝render 交付物章節順序（同一共用排序器）
    from dspx.commands import render as render_cmd
    monkeypatch.chdir(home.parent)
    assert render_cmd.run(["art"]) == 0
    text = (home.parent / "docs" / "art" / "_latest.md").read_text(encoding="utf-8")
    assert (text.index("## 1. 前言") < text.index("## 2. 簡介")
            < text.index("## 3. 附錄B") < text.index("### 3.1 地面"))


def test_document_map_groupless_project_unchanged_except_kind(make_project, write_leaf):
    """2.4：無 group.yaml 專案的 documentMap 除 additive `kind` 外不變（列序、既有欄位）。"""
    home = make_project()
    write_leaf(home, "art", concept={"id": "r", "title": "Root", "order": 0, "concept": "總覽",
                                     "brief": {"audience": "a", "depth": "d", "breadth": "b"}})
    write_leaf(home, "art/beta", concept={"id": "b", "title": "Beta", "order": 2, "concept": "界定 B"})
    write_leaf(home, "art/alpha", concept={"id": "a", "title": "Alpha", "order": 1, "concept": "界定 A"})
    proj = _project(home, "draft", "art/alpha")
    assert [n["section"] for n in proj.document_map] == ["art", "art/alpha", "art/beta"]
    for n in proj.document_map:
        assert set(n) == {"section", "title", "order", "number", "role", "kind"}
        assert n["kind"] == "leaf"


def test_instructions_draft_prints_group_row_without_you_are_here(make_project, write_leaf,
                                                                  monkeypatch, capsys):
    """2.3：document map 人讀輸出把 group 列印成可辨分組行；group 行不印 "◀ you are here"。"""
    home = make_project()
    _ordered_group_corpus(home, write_leaf)
    monkeypatch.chdir(home.parent)
    from dspx.commands import instructions as instr
    assert instr.run(["draft", "art/annex-b/ground"]) == 0
    out = capsys.readouterr().out
    group_line = next(ln for ln in out.splitlines() if "[group]" in ln)
    assert "art/annex-b/" in group_line and "附錄B" in group_line
    assert "you are here" not in group_line
    here_line = next(ln for ln in out.splitlines() if "◀ you are here" in ln)
    assert "art/annex-b/ground" in here_line


def test_document_map_only_for_draft(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "art", concept={"id": "r", "title": "R", "order": 0, "concept": "總覽",
                                      "brief": {"audience": "a", "depth": "d", "breadth": "b"}})
    assert _project(home, "draft", "art").document_map != []
    assert _project(home, "edit", "art").document_map == []
    assert _project(home, "factcheck", "art").document_map == []


def test_image_change_does_not_stale_section(make_project, write_leaf):
    """Model A：圖移到交付側 docs/assets/、**不再折入 corpus source_hash** → 改圖不改 source_hash
    （圖是交付物、由 draft 流程刷新，非 corpus 源變動；corpus 源 hash 不得反向依賴交付物）。"""
    from dspx.model import load_project as _lp
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1})
    asset = _add_asset(home, "a/x", "d.png", data=b"\x89PNG\r\n\x1a\nAAA")
    layout = Layout(home)
    before = {lf.section: lf.source_hash() for lf in _lp(layout)}["a/x"]
    asset.write_bytes(b"\x89PNG\r\n\x1a\nBBB")   # 改圖（交付側）
    after = {lf.section: lf.source_hash() for lf in _lp(layout)}["a/x"]
    assert before == after


# ── revision-coherence-probes：factcheck 的語義一致性探針投影 ──

def test_factcheck_coherence_contract_lists_pairs(make_project, write_leaf):
    """factcheck 投影 coherence_contract，列出 title/framing/own_brief/decisions 該核對的對。"""
    home = make_project()
    write_leaf(home, "doc/sec", concept={"id": "p1", "title": "Sec", "order": 1,
                                         "concept": "父框架", "brief": {"audience": "專家"}})
    write_leaf(home, "doc/sec/a", concept={
        "id": "c1", "title": "A 標題", "order": 1, "concept": "A 的框架一句話",
        "brief": {"audience": "新手", "depth": "概覽"}},
        decisions=[{"id": "d1", "kind": "normative", "status": "accepted",
                    "statement": "規則", "rationale": "因為舊框架"}])
    proj = _project(home, "factcheck", "doc/sec/a")
    coh = proj.coherence_contract
    assert coh is not None
    assert coh["title"] == "A 標題"
    assert coh["framing"] == "A 的框架一句話"
    # own_brief 在（因為有祖先可對照）
    assert coh["own_brief"]["audience"] == "新手" and coh["own_brief"]["depth"] == "概覽"
    # decisions 列 statement + rationale（rationale 常承載舊框架）
    assert coh["decisions"][0]["id"] == "d1"
    assert coh["decisions"][0]["rationale"] == "因為舊框架"


def test_coherence_figure_pair_only_when_drawio_present(make_project, write_leaf):
    """Model A：圖資產為文件層（docs/<article>/assets/）。有 .drawio 的文件 → 其節列 figure 對；
    另一個無 .drawio 的文件 → 省略。"""
    home = make_project()
    write_leaf(home, "g/sec", concept={"id": "c1", "title": "T", "order": 1, "concept": "f"})
    write_leaf(home, "h/sec", concept={"id": "c2", "title": "T2", "order": 1, "concept": "f2"})
    adir = Layout(home).docs_assets_dir("g")
    adir.mkdir(parents=True, exist_ok=True)
    (adir / "arch.drawio").write_text("<mxfile/>", encoding="utf-8")
    assert _project(home, "factcheck", "g/sec").coherence_contract.get("figures") == ["assets/arch.drawio"]
    assert "figures" not in (_project(home, "factcheck", "h/sec").coherence_contract or {})


def test_coherence_contract_factcheck_only(make_project, write_leaf):
    """coherence_contract 只投 factcheck（draft/edit 不給）。"""
    home = make_project()
    write_leaf(home, "g/x", concept={"id": "c1", "title": "X", "order": 1, "concept": "f",
                                     "brief": {"audience": "a"}})
    assert _project(home, "draft", "g/x").coherence_contract is None
    assert _project(home, "factcheck", "g/x").coherence_contract is not None


def test_coherence_own_brief_omitted_without_ancestor(make_project, write_leaf):
    """無祖先（root 級單節）→ own_brief 對省略（沒得對照），但 title/framing 仍在。"""
    home = make_project()
    write_leaf(home, "solo", concept={"id": "c1", "title": "T", "order": 1, "concept": "f",
                                      "brief": {"audience": "a", "depth": "d"}})
    coh = _project(home, "factcheck", "solo").coherence_contract
    assert coh["title"] == "T" and coh["framing"] == "f"
    assert "own_brief" not in coh   # 無祖先 brief 可對照


def test_coherence_contract_includes_realized_pair(make_project, write_leaf):
    """#1：本節 realizes 別文件決策 → coherence_contract 列出 realized↔prose 對（多文件語義盲區）。"""
    home = make_project()
    write_leaf(home, "b/owner", concept={"id": "co", "title": "Owner", "order": 1},
               decisions=[{"id": "dec-shared", "kind": "normative", "status": "accepted",
                           "statement": "共享真相 X"}])
    write_leaf(home, "a/user", concept={"id": "cu", "title": "User", "order": 1,
                                        "concept": "用 X", "realizes": ["dec-shared"]})
    coh = _project(home, "factcheck", "a/user").coherence_contract
    assert coh is not None and "realized" in coh
    r = coh["realized"][0]
    assert r["id"] == "dec-shared" and r["statement"] == "共享真相 X"
    assert r["from_section"] == "b/owner"


def test_realized_superseded_decision_foregrounds_status_and_successor(make_project, write_leaf):
    """FG-1 語義半：realizes 一個 superseded 決策 → aperture 帶 status＋接替決策（id＋statement），
    讓 draft/factcheck 不被死真相誤導。活決策不帶 marker（回歸）。"""
    home = make_project()
    write_leaf(home, "b/owner", concept={"id": "co", "title": "Owner", "order": 1},
               decisions=[{"id": "dec-old", "kind": "normative", "status": "superseded",
                           "statement": "舊真相", "superseded-by": "dec-new"},
                          {"id": "dec-new", "kind": "normative", "status": "accepted",
                           "statement": "新真相", "supersedes": "dec-old"}])
    write_leaf(home, "a/user", concept={"id": "cu", "title": "User", "order": 1,
                                        "concept": "用真相", "realizes": ["dec-old"]})
    # factcheck coherence realized pair carries status + successor
    coh = _project(home, "factcheck", "a/user").coherence_contract
    r = coh["realized"][0]
    assert r["status"] == "superseded"
    assert r["superseded_by"] == "dec-new"
    assert r["successor_statement"] == "新真相"
    # both draft and factcheck see the realized block with the successor data
    for skill in ("draft", "factcheck"):
        realized = _project(home, skill, "a/user").realized
        assert realized and realized[0]["superseded_by"] == "dec-new"

    # a LIVE realized decision carries no superseding marker (regression)
    write_leaf(home, "a/user2", concept={"id": "cu2", "title": "User2", "order": 2,
                                         "concept": "用新", "realizes": ["dec-new"]})
    r2 = _project(home, "factcheck", "a/user2").coherence_contract["realized"][0]
    assert r2["status"] == "accepted" and not r2.get("superseded_by")


def test_realized_successor_walks_chain_to_first_live(make_project, write_leaf):
    """Round-8 FINDING-1: the successor must be the FIRST LIVE decision in the supersede chain,
    not a one-hop hop that lands on another dead decision."""
    home = make_project()
    # chain d1 -> d2 (also superseded) -> d3 (live)
    write_leaf(home, "b/owner", concept={"id": "co", "title": "Owner", "order": 1},
               decisions=[{"id": "d1", "kind": "normative", "status": "superseded",
                           "statement": "v1 dead", "superseded-by": "d2"},
                          {"id": "d2", "kind": "normative", "status": "superseded",
                           "statement": "v2 dead", "superseded-by": "d3", "supersedes": "d1"},
                          {"id": "d3", "kind": "normative", "status": "accepted",
                           "statement": "v3 live", "supersedes": "d2"}])
    write_leaf(home, "a/user", concept={"id": "cu", "title": "User", "order": 1,
                                        "concept": "x", "realizes": ["d1"]})
    r = _project(home, "factcheck", "a/user").coherence_contract["realized"][0]
    assert r["status"] == "superseded"
    assert r["superseded_by"] == "d3"            # terminal LIVE, not the dead d2
    assert r["successor_statement"] == "v3 live"


def test_realized_successor_none_when_chain_ends_dead(make_project, write_leaf):
    """A superseded decision whose chain never reaches a live decision (here: no superseded-by)
    must report no live successor — never print a dead statement as if live."""
    home = make_project()
    write_leaf(home, "b/owner", concept={"id": "co", "title": "Owner", "order": 1},
               decisions=[{"id": "d1", "kind": "normative", "status": "superseded",
                           "statement": "killed without replacement"}])
    write_leaf(home, "a/user", concept={"id": "cu", "title": "User", "order": 1,
                                        "concept": "x", "realizes": ["d1"]})
    r = _project(home, "factcheck", "a/user").coherence_contract["realized"][0]
    assert r["status"] == "superseded"
    assert not r.get("superseded_by") and not r.get("successor_statement")
