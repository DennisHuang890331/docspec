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
    leaf = home / "corpus"
    for part in section.split("/"):
        leaf = leaf / part
    adir = leaf / "assets"
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


def test_document_map_only_for_draft(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "art", concept={"id": "r", "title": "R", "order": 0, "concept": "總覽",
                                      "brief": {"audience": "a", "depth": "d", "breadth": "b"}})
    assert _project(home, "draft", "art").document_map != []
    assert _project(home, "edit", "art").document_map == []
    assert _project(home, "factcheck", "art").document_map == []


def test_image_change_marks_section_stale(make_project, write_leaf):
    """改圖片內容 → 該節 source_hash 變（staleness）。"""
    from dspx.model import load_project as _lp
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1})
    asset = _add_asset(home, "a/x", "d.png", data=b"\x89PNG\r\n\x1a\nAAA")
    layout = Layout(home)
    before = {lf.section: lf.source_hash() for lf in _lp(layout)}["a/x"]
    asset.write_bytes(b"\x89PNG\r\n\x1a\nBBB")   # 改圖
    after = {lf.section: lf.source_hash() for lf in _lp(layout)}["a/x"]
    assert before != after
