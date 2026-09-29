"""治理層（第一期）：紀錄儲存、編號、裁定確認前提、決策取代、文件章節 realizes 治理決策。"""

from __future__ import annotations

import json

import pytest

from dspx.check import run_check
from dspx.commands.deliverable import render as render_cmd
from dspx.commands.governance import decision as decision_cmd
from dspx.commands.governance import question as question_cmd
from dspx.commands.governance import ruling as ruling_cmd
from dspx.commands.query.status import _docs_hashes, _leaf_row
from dspx.engine import governance as gv
from dspx.engine.layout import Layout
from dspx.engine.model import decision_index, load_project, project_decision_index
from dspx.engine.schema import load_schema


@pytest.fixture
def gov_project(make_project, monkeypatch):
    home = make_project()
    monkeypatch.chdir(home.parent)
    monkeypatch.setenv("DOCSPEC_AGENT", "claude")
    return home


def _confirm(home, rid):
    """測試用：模擬使用者確認（真正路徑是 `docspec approve`，見 test_approve）。"""
    layout = Layout(home)
    rec = gv.load_record(gv.record_path(layout, "ruling", rid), "ruling")
    rec["status"] = "confirmed"
    gv.write_record(layout, "ruling", rec)


# ── 儲存與編號 ─────────────────────────────────────────────────────────────

def test_ids_are_prefixed_per_tool_and_one_file_per_record(gov_project, monkeypatch):
    assert question_cmd.run(["add", "--title", "首頁要不要合併"]) == 0
    assert question_cmd.run(["add", "--title", "影像格式"]) == 0
    monkeypatch.setenv("DOCSPEC_AGENT", "gpt")
    assert question_cmd.run(["add", "--title", "刪除的語意"]) == 0
    qdir = gov_project / "governance" / "questions"
    assert sorted(p.name for p in qdir.iterdir()) == [
        "Q-claude-1.yaml", "Q-claude-2.yaml", "Q-gpt-1.yaml"]


def test_hand_edit_breaks_the_seal(gov_project):
    question_cmd.run(["add", "--title", "原題"])
    path = gov_project / "governance" / "questions" / "Q-claude-1.yaml"
    path.write_text(path.read_text(encoding="utf-8").replace("原題", "被改"), encoding="utf-8")
    with pytest.raises(gv.GovernanceError, match="integrity seal mismatch"):
        gv.load_governance(Layout(gov_project))


def test_tool_prefix_required_when_undetectable(gov_project, monkeypatch, capsys):
    monkeypatch.delenv("DOCSPEC_AGENT")
    for k in list(__import__("os").environ):
        if k.startswith(("CLAUDE", "CODEX_", "GEMINI")):
            monkeypatch.delenv(k, raising=False)
    assert question_cmd.run(["add", "--title", "x"]) == 1
    assert "--by" in capsys.readouterr().err


def test_duplicate_id_across_branches_is_a_check_error(gov_project):
    question_cmd.run(["add", "--title", "a"])
    layout = Layout(gov_project)
    # 模擬另一分支合併進來的同號紀錄（檔名不同但 id 相同＝撞號）
    rec = gv.load_record(gv.record_path(layout, "question", "Q-claude-1"), "question")
    other = gv.kind_dir(layout, "question") / "Q-claude-1-merged.yaml"
    other.write_text(gv.dump_record("question", {**rec, "title": "b"}), encoding="utf-8")
    errs = gv.validate(layout)
    assert any("duplicate governance id" in e for e in errs)


# ── 裁定與決策 ─────────────────────────────────────────────────────────────

def test_question_answered_is_derived(gov_project):
    question_cmd.run(["add", "--title", "刪除要不要兩步"])
    ruling_cmd.run(["add", "--quote", "刪除就是刪除", "--tier", "major", "--answers", "Q-claude-1"])
    layout = Layout(gov_project)
    gov = gv.load_governance(layout)
    assert gv.question_effective_status(gov.questions[0], gov) == "answered"
    assert gov.rulings[0]["status"] == "pending"


def test_minor_ruling_is_recorded_only_and_cannot_activate_a_decision(gov_project, capsys):
    ruling_cmd.run(["add", "--quote", "名稱可以", "--tier", "minor"])
    decision_cmd.run(["add", "--title", "名稱", "--statement", "用這個名稱", "--based-on", "RL-claude-1"])
    assert decision_cmd.run(["activate", "D-claude-1"]) == 1
    assert "not confirmed by the owner" in capsys.readouterr().err


def test_decision_cannot_activate_before_owner_confirms_ruling(gov_project, capsys):
    """驗收情境 S3（引擎半）：未確認的裁定不能讓依據它的決策生效。"""
    ruling_cmd.run(["add", "--quote", "刪除就是刪除", "--tier", "major"])
    decision_cmd.run(["add", "--title", "刪除一步完成", "--statement", "刪除錄製資料一步完成。",
                      "--based-on", "RL-claude-1"])
    assert decision_cmd.run(["activate", "D-claude-1"]) == 1
    assert "docspec approve" in capsys.readouterr().err
    _confirm(gov_project, "RL-claude-1")
    assert decision_cmd.run(["activate", "D-claude-1"]) == 0
    assert gv.validate(Layout(gov_project)) == []


def test_active_decision_on_unconfirmed_ruling_is_a_check_error(gov_project):
    ruling_cmd.run(["add", "--quote", "x", "--tier", "major"])
    layout = Layout(gov_project)
    gv.write_record(layout, "decision", {
        "id": "D-claude-1", "title": "t", "statement": "s", "status": "active",
        "based-on": ["RL-claude-1"], "created-by": "claude", "created-at": "2026-09-29"})
    assert any("not confirmed by the owner" in e for e in gv.validate(layout))


def _supersede_d7(home):
    """仿台中港 D7 → D15：D15 取代 D7 時寫出合併後的完整新版（驗收情境 S1）。"""
    ruling_cmd.run(["add", "--quote", "首頁維持原樣", "--tier", "major"])
    _confirm(home, "RL-claude-1")
    decision_cmd.run(["add", "--title", "首頁與導覽", "--statement", "/tasks 頁面維持不變；首頁為總覽。",
                      "--based-on", "RL-claude-1"])
    decision_cmd.run(["activate", "D-claude-1"])
    ruling_cmd.run(["add", "--quote", "三頁合併成首頁", "--tier", "major"])
    _confirm(home, "RL-claude-2")
    decision_cmd.run(["add", "--title", "首頁與導覽", "--supersedes", "D-claude-1",
                      "--statement", "錄製資料、標註任務、資料集版本三頁合併到首頁；/tasks 只轉址。",
                      "--based-on", "RL-claude-2"])


def test_effective_design_shows_only_the_complete_new_version(gov_project, capsys):
    """驗收情境 S1：取代後，目前有效設計只有新版；歷史可查原文與依據。"""
    _supersede_d7(gov_project)
    assert decision_cmd.run(["activate", "D-claude-2"]) == 0
    capsys.readouterr()
    assert decision_cmd.run(["list", "--json"]) == 0
    active = json.loads(capsys.readouterr().out)["decisions"]
    assert [d["id"] for d in active] == ["D-claude-2"]
    assert "三頁合併" in active[0]["statement"]
    assert decision_cmd.run(["show", "D-claude-2", "--json"]) == 0
    hist = json.loads(capsys.readouterr().out)["history"]
    assert [(h["id"], h["effective-status"]) for h in hist] == [
        ("D-claude-2", "active"), ("D-claude-1", "superseded")]
    assert hist[1]["statement"] == "/tasks 頁面維持不變；首頁為總覽。"   # 舊版原文保留
    assert hist[1]["based-on"] == ["RL-claude-1"]


def test_supersede_cycle_is_detected(gov_project):
    layout = Layout(gov_project)
    base = {"title": "t", "statement": "s", "status": "draft", "created-by": "claude",
            "created-at": "2026-09-29"}
    gv.write_record(layout, "decision", {**base, "id": "D-claude-1", "supersedes": ["D-claude-2"]})
    gv.write_record(layout, "decision", {**base, "id": "D-claude-2", "supersedes": ["D-claude-1"]})
    assert any("supersede cycle" in e for e in gv.validate(layout))


# ── 文件章節 realizes 治理決策 ──────────────────────────────────────────────

def _doc_section(home, write_leaf, realizes):
    write_leaf(home, "guide", concept={"id": "c-guide", "title": "說明書", "order": 0,
                                       "concept": "說明", "brief": {"audience": "x", "depth": "y",
                                                                   "breadth": "z"}})
    write_leaf(home, "guide/home", concept={"id": "c-home", "title": "首頁", "order": 1,
                                            "concept": "首頁說明", "realizes": realizes})


def _sync(home, section):
    layout = Layout(home)
    leaves = load_project(layout)
    by = {lf.section: lf for lf in leaves}
    return _leaf_row(layout, by[section], load_schema(), True, _docs_hashes(layout, "guide"),
                     by, project_decision_index(layout, leaves))["sync"]


def test_realizes_gov_decision_check_rules(gov_project, write_leaf):
    _supersede_d7(gov_project)                       # D-claude-1 active, D-claude-2 draft
    _doc_section(gov_project, write_leaf, ["gov:D-claude-2", "gov:D-claude-9"])
    layout = Layout(gov_project)
    errs = run_check(load_project(layout), load_schema(), layout).errors
    assert any("draft governance decision \"gov:D-claude-2\"" in e for e in errs)
    assert any("nonexistent governance decision \"gov:D-claude-9\"" in e for e in errs)


def test_superseding_gov_decision_makes_realizing_section_stale(gov_project, write_leaf):
    """驗收情境 S2（第一期範圍）：取代決策後，依賴它的文件章節轉 stale-upstream。"""
    _supersede_d7(gov_project)
    _doc_section(gov_project, write_leaf, ["gov:D-claude-1"])
    render_cmd.run(["guide"])
    latest = gov_project.parent / "docs" / "guide" / "_latest.md"
    latest.write_text(latest.read_text(encoding="utf-8").replace(
        "## 1. 首頁\n", "## 1. 首頁\n\n/tasks 維持不變。\n"), encoding="utf-8")
    render_cmd.run(["guide"])
    assert _sync(gov_project, "guide/home") == "synced"
    decision_cmd.run(["activate", "D-claude-2"])
    assert _sync(gov_project, "guide/home") == "stale-upstream"


def test_corpus_only_fingerprints_unchanged_by_governance(make_project, write_leaf):
    """只 realizes corpus 決策的章節：有無治理層，決策索引（指紋來源）完全相同。"""
    home = make_project()
    write_leaf(home, "a", concept={"id": "c-a", "title": "A", "order": 0, "concept": "A"},
               decisions=[{"id": "dec-x", "kind": "normative", "status": "accepted",
                           "statement": "四態。"}])
    layout = Layout(home)
    leaves = load_project(layout)
    assert project_decision_index(layout, leaves) == decision_index(leaves)


# ── 影響分析與追溯（第 5 步） ────────────────────────────────────────────────

from dspx.commands.governance import impact as impact_cmd  # noqa: E402
from dspx.commands.governance import trace as trace_cmd    # noqa: E402


def test_superseding_ruling_flags_decisions_based_on_it(gov_project, capsys):
    ruling_cmd.run(["add", "--quote", "JPG PNG 都可以", "--tier", "major"])
    _confirm(gov_project, "RL-claude-1")
    decision_cmd.run(["add", "--title", "影像格式", "--statement", "依需要解成 JPG 或 PNG。",
                      "--based-on", "RL-claude-1"])
    decision_cmd.run(["activate", "D-claude-1"])
    ruling_cmd.run(["add", "--quote", "一律 PNG", "--tier", "major", "--supersedes", "RL-claude-1"])
    _confirm(gov_project, "RL-claude-2")
    from dspx.engine.impact import flag_after_change
    created = flag_after_change(Layout(gov_project), "RL-claude-2")
    assert len(created) == 1
    capsys.readouterr()
    assert impact_cmd.run(["--json"]) == 0
    items = json.loads(capsys.readouterr().out)
    assert [(s["trigger"], s["target"]) for s in items["suspects"]] == [("RL-claude-1", "D-claude-1")]
    # 重跑不重複建標記
    assert flag_after_change(Layout(gov_project), "RL-claude-2") == []
    # 清除要理由
    sid = items["suspects"][0]["id"]
    assert impact_cmd.run(["clear", sid, "--reason", "已改寫決策為一律 PNG"]) == 0
    capsys.readouterr()
    impact_cmd.run(["--json"])
    assert json.loads(capsys.readouterr().out)["suspects"] == []


def test_impact_lists_doc_sections_on_superseded_decision(gov_project, write_leaf, capsys):
    """驗收情境 S2（第一期）：取代「/tasks 維持不變」→ 依賴它的說明書章節列為需重看，附接替者。"""
    _supersede_d7(gov_project)
    _doc_section(gov_project, write_leaf, ["gov:D-claude-1"])
    decision_cmd.run(["activate", "D-claude-2"])
    capsys.readouterr()
    impact_cmd.run(["--json"])
    sections = json.loads(capsys.readouterr().out)["sections"]
    assert [(r["section"], r["decision"], r["successor"]) for r in sections] == [
        ("guide/home", "D-claude-1", "D-claude-2")]


def test_trace_shows_both_directions(gov_project, write_leaf, capsys):
    _supersede_d7(gov_project)
    _doc_section(gov_project, write_leaf, ["gov:D-claude-1"])
    capsys.readouterr()
    assert trace_cmd.run(["D-claude-1", "--json"]) == 0
    t = json.loads(capsys.readouterr().out)
    assert {"ref": "RL-claude-1", "type": "based-on"} in t["upstream"]
    assert {"ref": "D-claude-2", "type": "supersedes"} in t["downstream"]
    assert {"ref": "doc:guide/home", "type": "realizes"} in t["downstream"]


# ── 檢視（第 6 步） ─────────────────────────────────────────────────────────

from dspx.commands.governance import brief as brief_cmd  # noqa: E402
from dspx.engine import views  # noqa: E402


def test_brief_is_one_page_plain_and_points_to_next_steps(gov_project, write_leaf, capsys):
    """驗收情境 S4（機械半）：兩千字以內、編號只在括號裡、有下一步。"""
    _supersede_d7(gov_project)
    _doc_section(gov_project, write_leaf, ["gov:D-claude-1"])
    for i in range(40):                                    # 大量待決問題也不能撐爆一頁
        question_cmd.run(["add", "--title", f"第 {i} 個待決問題，描述很長很長很長很長很長很長很長"])
    ruling_cmd.run(["add", "--quote", "先這樣寫", "--tier", "minor"])
    ruling_cmd.run(["add", "--quote", "可以插隊", "--tier", "major"])      # 待確認
    capsys.readouterr()
    assert brief_cmd.run([]) == 0
    text = capsys.readouterr().out
    assert len(text) <= views.BRIEF_LIMIT
    assert "下一步" in text and "docspec approve" in text
    assert "還有" in text                                   # 長清單被截短並指路
    assert "未經本人確認" in text                           # minor 裁定標示
    assert "（Q-claude-1）" in text                          # 編號在括號


def test_design_view_lists_only_active_full_text(gov_project, capsys):
    _supersede_d7(gov_project)
    decision_cmd.run(["activate", "D-claude-2"])
    capsys.readouterr()
    assert brief_cmd.run(["--design"]) == 0
    text = capsys.readouterr().out
    assert "三頁合併" in text and "/tasks 頁面維持不變" not in text
    assert "D-claude-1" in text                             # 只以「取代了」出現


def test_brief_write_regenerates_view_files(gov_project):
    assert brief_cmd.run(["--write"]) == 0
    out = gov_project.parent / "docs" / "project"
    assert sorted(p.name for p in out.iterdir()) == ["design.md", "pending.md", "status.md"]


def test_activating_replacement_clears_flags_on_replaced_decision(gov_project):
    ruling_cmd.run(["add", "--quote", "維持原樣", "--tier", "major"])
    _confirm(gov_project, "RL-claude-1")
    decision_cmd.run(["add", "--title", "首頁", "--statement", "維持。", "--based-on", "RL-claude-1"])
    decision_cmd.run(["activate", "D-claude-1"])
    ruling_cmd.run(["add", "--quote", "合併", "--tier", "major", "--supersedes", "RL-claude-1"])
    _confirm(gov_project, "RL-claude-2")
    from dspx.engine.impact import flag_after_change
    layout = Layout(gov_project)
    assert len(flag_after_change(layout, "RL-claude-2")) == 1          # D-claude-1 被標可疑
    decision_cmd.run(["add", "--title", "首頁", "--statement", "合併。", "--based-on", "RL-claude-2",
                      "--supersedes", "D-claude-1"])
    decision_cmd.run(["activate", "D-claude-2"])
    s = gv.load_governance(layout).suspects[0]
    assert (s["status"], s["cleared-reason"]) == ("cleared", "superseded by D-claude-2")
