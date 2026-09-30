"""軟體領域與治理層、文件樹的連結（P2-5）：影響分析、roadmap swc:、文件章節 realizes req:、一頁現況。"""

from __future__ import annotations

import json
import shlex
import sys

import pytest

from dspx.check import run_check
from dspx.commands.code import code as code_cmd
from dspx.commands.deliverable import render as render_cmd
from dspx.commands.governance import decision as decision_cmd
from dspx.commands.governance import impact as impact_cmd
from dspx.commands.governance import roadmap as roadmap_cmd
from dspx.commands.governance import ruling as ruling_cmd
from dspx.commands.governance import trace as trace_cmd
from dspx.commands.query.status import _docs_hashes, _leaf_row
from dspx.engine.layout import Layout
from dspx.engine.model import load_project, project_decision_index
from dspx.engine.schema import load_schema
from dspx.engine.software import io
from dspx.engine.software import specs as sp

RB = ["--read-back", "覆述", "--confirmed", "對"]
TESTS = "def test_first_row():\n    assert True\n\ndef test_new():\n    assert True\n"


def code(*argv) -> int:
    return code_cmd.run(list(argv))


@pytest.fixture
def proj(make_project, monkeypatch):
    home = make_project()
    monkeypatch.chdir(home.parent)
    monkeypatch.setenv("DOCSPEC_AGENT", "claude")
    layout = Layout(home)
    app = layout.project_root / "app"
    (app / "tests").mkdir(parents=True)
    (app / "tests" / "test_entry.py").write_text(TESTS, encoding="utf-8")
    cmd = shlex.join([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"])
    io.config_path(layout).parent.mkdir(parents=True, exist_ok=True)
    io.config_path(layout).write_text(
        f"repos:\n  app: {{path: app, test-command: {json.dumps(cmd)}}}\n", encoding="utf-8")
    # 決策 D-claude-1：入口頁第一列要可見
    ruling_cmd.run(["add", "--quote", "第一列要看得到", *RB])
    decision_cmd.run(["add", "--title", "入口頁", "--statement", "第一列要可見", "--based-on", "RL-claude-1"])
    decision_cmd.run(["activate", "D-claude-1"])
    sp.write_spec(layout, {"capability": "entry", "purpose": "入口頁", "requirements": [
        {"id": "R1", "title": "列出任務", "statement": "It SHALL list tasks.", "verification": ["test"],
         "based-on": ["gov:D-claude-1"],
         "scenarios": [{"id": "S1", "title": "第一列", "when": "開啟", "then": "看到第一列",
                        "verified-by": ["app:tests/test_entry.py::test_first_row"]}]}]})
    return layout


def _supersede_d1() -> None:
    ruling_cmd.run(["add", "--quote", "第一列要完整可見，不被工具列遮住", *RB, "--supersedes", "RL-claude-1"])
    decision_cmd.run(["add", "--title", "入口頁 v2", "--statement", "第一列完整可見", "--based-on",
                      "RL-claude-2", "--supersedes", "D-claude-1"])
    decision_cmd.run(["activate", "D-claude-2"])


def _change(cid: str, then: str = "完整看到第一列", decision: str = "D-claude-1",
            location: str = "app:tests/test_entry.py::test_new") -> None:
    code("change", "new", cid, "--why", "x", "--modified", "entry")
    code("change", "design", cid, "--decision", decision)
    code("change", "delta", cid, "--capability", "entry", "--op", "modify-scenario",
         "--ref", "R1/S1", "--then", then)
    code("testplan", "add", cid, "--location", location, "--covers", "entry/R1/S1", "--by", "gemini")
    code("testplan", "sign", cid, "--by", "gemini")
    code("task", "add", cid, "--title", "修", "--implements", "entry/R1", "--verify", "test", "--tests", "T1")


def _impact(capsys) -> dict:
    capsys.readouterr()
    impact_cmd.run(["--json"])
    return json.loads(capsys.readouterr().out)


# ── 影響分析 ─────────────────────────────────────────────────────────────

def test_superseding_a_decision_flags_software_downstream(proj, capsys):
    """驗收情境 S2（跨領域）：取代決策 → 依據它的進行中 change 與需求都被標為需重看。"""
    _change("fix")
    _supersede_d1()
    targets = {s["target"] for s in _impact(capsys)["suspects"]}
    assert {"swc:fix", "req:entry/R1"} <= targets
    # 進行中的 change：狀態提醒；封存被擋，直到看過並清除
    capsys.readouterr()
    code("change", "status", "fix")
    assert "affected by a change to D-claude-1" in capsys.readouterr().out
    code("evidence", "run", "fix", "1")
    capsys.readouterr()
    assert code("archive", "fix") == 1
    assert "affected by a change to D-claude-1" in capsys.readouterr().out


def test_archive_clears_requirement_flag_when_it_rewrites_the_basis(proj, capsys):
    _supersede_d1()
    flags = {s["target"]: s["id"] for s in _impact(capsys)["suspects"]}
    assert "req:entry/R1" in flags
    code("change", "new", "rebase", "--why", "依新決策", "--modified", "entry")
    code("change", "delta", "rebase", "--capability", "entry", "--op", "modify-requirement",
         "--ref", "R1", "--based-on", "D-claude-2")
    code("task", "add", "rebase", "--title", "改依據", "--implements", "entry/R1", "--verify", "test",
         "--tests", "T1")
    code("testplan", "add", "rebase", "--location", "app:tests/test_entry.py::test_first_row",
         "--covers", "entry/R1/S1", "--by", "gemini")
    code("testplan", "sign", "rebase", "--by", "gemini")
    code("evidence", "run", "rebase", "1")
    capsys.readouterr()
    assert code("archive", "rebase") == 0
    assert "cleared (requirement rewritten by this change)" in capsys.readouterr().out
    assert "req:entry/R1" not in {s["target"] for s in _impact(capsys)["suspects"]}
    assert sp.load_spec(proj, "entry")["requirements"][0]["based-on"] == ["gov:D-claude-2"]


def test_trace_includes_software_nodes(proj, capsys):
    _change("fix")
    capsys.readouterr()
    assert trace_cmd.run(["D-claude-1", "--json"]) == 0
    down = json.loads(capsys.readouterr().out)["downstream"]
    assert {"ref": "swc:fix", "type": "based-on"} in down
    assert {"ref": "req:entry/R1", "type": "based-on"} in down


# ── 被修改的情境：舊測試不再算數 ───────────────────────────────────────

def test_modified_scenario_replaces_its_verified_by(proj, capsys):
    _change("fix")
    code("evidence", "run", "fix", "1")
    capsys.readouterr()
    assert code("archive", "fix") == 0
    out = capsys.readouterr().out
    assert "no longer verify it" in out and "test_first_row" in out
    s1 = sp.load_spec(proj, "entry")["requirements"][0]["scenarios"][0]
    assert s1["verified-by"] == ["app:tests/test_entry.py::test_new"]


# ── roadmap 連到軟體 change ──────────────────────────────────────────────

def _roadmap_status(capsys) -> dict:
    capsys.readouterr()
    roadmap_cmd.run(["--json"])
    v = json.loads(capsys.readouterr().out)
    return {r["id"]: r for r in v["unassigned"]}


def test_roadmap_progress_follows_the_software_change(proj, capsys):
    roadmap_cmd.run(["add", "--title", "入口頁修正", "--ref", "swc:fix"])
    layout = proj
    assert any("\"swc:fix\" points to nothing" in e
               for e in run_check(load_project(layout), load_schema(), layout).errors)
    _change("fix")
    assert _roadmap_status(capsys)["W-claude-1"]["status"] == "in-progress"
    _supersede_d1()
    row = _roadmap_status(capsys)["W-claude-1"]
    assert row["status"] == "blocked" and "swc:fix" in row["blocked-because"]
    sid = next(s["id"] for s in _impact(capsys)["suspects"] if s["target"] == "swc:fix")
    impact_cmd.run(["clear", sid, "--reason", "新決策只是措辭更嚴格，這個 change 已符合"])
    code("evidence", "run", "fix", "1")
    capsys.readouterr()
    assert code("archive", "fix") == 1                  # 設計仍引用被取代的決策
    assert "superseded decision" in capsys.readouterr().out
    code("change", "design", "fix", "--remove-decision", "D-claude-1", "--decision", "D-claude-2")
    assert code("archive", "fix") == 0
    assert _roadmap_status(capsys)["W-claude-1"]["status"] == "done"


def test_roadmap_shows_waived_software_change(proj, capsys):
    roadmap_cmd.run(["add", "--title", "入口頁修正", "--ref", "swc:fix"])
    _change("fix")
    ruling_cmd.run(["add", "--quote", "這項先豁免", *RB])
    code("evidence", "waive", "fix", "1", "--ruling", "RL-claude-2", "--reopen-when", "有 GPU")
    assert code("archive", "fix") == 0
    assert _roadmap_status(capsys)["W-claude-1"]["status"] == "done-waived"
    from dspx.engine.roadmap_v2 import status_label
    assert status_label("done-waived", {}) == "完成（含豁免）"


# ── 文件章節 realizes 軟體需求 ────────────────────────────────────────────

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


def test_doc_section_realizing_a_requirement_goes_stale_when_it_changes(proj, write_leaf, capsys):
    home = proj.planning_home
    _doc_section(home, write_leaf, ["req:entry/R1", "req:entry/R9"])
    errs = run_check(load_project(proj), load_schema(), proj).errors
    assert any("nonexistent software requirement \"req:entry/R9\"" in e for e in errs)
    _doc_section(home, write_leaf, ["req:entry/R1"])
    render_cmd.run(["guide"])
    latest = home.parent / "docs" / "guide" / "_latest.md"
    latest.write_text(latest.read_text(encoding="utf-8").replace(
        "## 1. 首頁\n", "## 1. 首頁\n\n打開就能看到第一列。\n").replace(
        "# 說明書\n", "# 說明書\n\n這份說明書介紹首頁。\n"), encoding="utf-8")
    render_cmd.run(["guide"])
    assert _sync(home, "guide/home") == "synced"
    _change("fix", decision="D-claude-1")
    code("evidence", "run", "fix", "1")
    assert code("archive", "fix") == 0
    # 2026/09/30 裁定：文件管文件、軟體管軟體。只因軟體需求變了而落後＝stale-software：
    # 記下差異、照樣提醒更新，但不擋文件定版；差異寫進該版的紀錄。
    assert _sync(home, "guide/home") == "stale-software"
    from dspx.commands.deliverable import freeze as freeze_cmd
    from dspx.engine import project_baseline as pb
    capsys.readouterr()
    assert freeze_cmd.run(["guide"]) == 0
    assert "guide/home" in capsys.readouterr().err
    assert pb.doc_version_record(proj, "guide", "1.0.0")["software-divergence"] == ["guide/home"]


def test_software_errors_do_not_hold_up_documents(proj, write_leaf, capsys):
    """軟體 change 有錯（缺測試、缺任務）時，文件的 check 仍是綠的；`docspec check` 另列軟體問題。"""
    home = proj.planning_home
    _doc_section(home, write_leaf, ["req:entry/R1"])
    code("change", "new", "half", "--why", "x", "--modified", "entry")
    code("change", "delta", "half", "--capability", "entry", "--op", "modify-scenario",
         "--ref", "R1/S1", "--then", "改")
    res = run_check(load_project(proj), load_schema(), proj)
    assert res.ok and res.software_errors
    from dspx.commands.query import check as check_cmd
    capsys.readouterr()
    assert check_cmd.run([]) == 1                                   # 整體健康檢查照樣反映軟體問題
    out = capsys.readouterr().out
    assert "check passed (documents)" in out and "do not hold up documents" in out


def test_undelta_takes_back_a_wrong_delta(proj, capsys):
    _change("fix")
    code("change", "delta", "fix", "--capability", "entry", "--op", "add-scenario", "--ref", "R1",
         "--title", "t", "--when", "w", "--then", "x")
    assert code("change", "undelta", "fix", "--capability", "entry", "--ref", "R1/S2") == 0
    assert code("change", "undelta", "fix", "--capability", "entry", "--ref", "R1") == 0
    from dspx.engine.software import changes as chg
    assert chg.load_change(proj, "fix")["deltas"] == {}
    assert code("change", "undelta", "fix", "--capability", "entry", "--ref", "R1") == 1
