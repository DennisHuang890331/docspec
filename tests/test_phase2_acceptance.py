"""第二期驗收情境（docs/dev/phase2-design.md §7）：S2 完整鏈、S5 豁免、S7 匯入、S8 只改一個情境、S9 並行衝突。

資料是仿台中港專案結構的合成資料；台中港真實資料只在本機跑（見 phase2-detail.md §17），不進 repo。
"""

from __future__ import annotations

import json
import shlex
import sys

import pytest

from dspx.check import run_check
from dspx.commands.code import code as code_cmd
from dspx.commands.governance import decision as decision_cmd
from dspx.commands.governance import impact as impact_cmd
from dspx.commands.governance import roadmap as roadmap_cmd
from dspx.commands.governance import ruling as ruling_cmd
from dspx.engine.layout import Layout
from dspx.engine.model import load_project
from dspx.engine.schema import load_schema
from dspx.engine.software import io
from dspx.engine.software import specs as sp

RB = ["--read-back", "覆述", "--confirmed", "對"]
TESTS = "def test_first_row_visible():\n    assert True\n\ndef test_import_row():\n    assert True\n"


def code(*argv) -> int:
    return code_cmd.run(list(argv))


@pytest.fixture
def port(make_project, monkeypatch):
    """仿台中港：task-entry-page 規格、labelvault repo、決策 D-claude-1「/tasks 頁面維持不變」。"""
    home = make_project()
    monkeypatch.chdir(home.parent)
    monkeypatch.setenv("DOCSPEC_AGENT", "claude")
    layout = Layout(home)
    lv = layout.project_root / "tools" / "labelvault"
    (lv / "tests" / "browser").mkdir(parents=True)
    (lv / "src").mkdir()
    (lv / "src" / "portal.py").write_text("PAGE = '/tasks'\n", encoding="utf-8")
    (lv / "tests" / "browser" / "test_entry_page.py").write_text(TESTS, encoding="utf-8")
    cmd = shlex.join([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"])
    io.config_path(layout).parent.mkdir(parents=True, exist_ok=True)
    io.config_path(layout).write_text(
        f"repos:\n  labelvault: {{path: tools/labelvault, test-command: {json.dumps(cmd)}}}\n",
        encoding="utf-8")
    ruling_cmd.run(["add", "--quote", "/tasks 頁面維持不變", *RB])
    decision_cmd.run(["add", "--title", "/tasks 頁面維持不變", "--statement", "/tasks 頁面維持不變",
                      "--based-on", "RL-claude-1"])
    decision_cmd.run(["activate", "D-claude-1"])
    sp.write_spec(layout, {"capability": "task-entry-page", "purpose": "任務入口頁", "requirements": [
        {"id": "R1", "title": "第一列任務在第一畫面", "statement": "The first task row SHALL be visible.",
         "verification": ["test"], "based-on": ["gov:D-claude-1"],
         "scenarios": [
             {"id": "S1", "title": "開啟任務", "when": "開啟首頁", "then": "第一列在第一畫面"},
             {"id": "S2", "title": "大量 AI 工作", "when": "跑過數百個工作", "then": "首頁長度不變"}]},
        {"id": "R2", "title": "匯入列", "statement": "Imports SHALL appear as task rows.",
         "verification": ["test"],
         "scenarios": [{"id": "S1", "title": "匯入中", "when": "解碼中", "then": "顯示進度"}]}]})
    return layout


def _deliver(cid: str, *, ref: str = "R1/S1", then: str = "第一列完整可見",
             test: str = "test_first_row_visible", run: bool = True) -> None:
    """一個完整的小 change：差異 → 測試角色規劃 → 任務 → 引擎代跑。"""
    code("change", "new", cid, "--why", "修正首頁", "--modified", "task-entry-page")
    code("change", "delta", cid, "--capability", "task-entry-page", "--op", "modify-scenario",
         "--ref", ref, "--then", then)
    code("testplan", "add", cid, "--location", f"labelvault:tests/browser/test_entry_page.py::{test}",
         "--covers", f"task-entry-page/{ref}", "--level", "browser", "--by", "gemini")
    code("task", "add", cid, "--title", "6.6 調整首頁版面", "--implements",
         f"task-entry-page/{ref.split('/')[0]}", "--files", "labelvault:src/portal.py",
         "--verify", "test", "--tests", "T1")
    if run:
        assert code("evidence", "run", cid, "1") == 0


def _suspects(capsys) -> list[dict]:
    capsys.readouterr()
    impact_cmd.run(["--json"])
    return json.loads(capsys.readouterr().out)["suspects"]


def test_s2_full_chain(port, write_leaf, capsys):
    """取代「/tasks 頁面維持不變」→ 需求、已完成的任務 6.6（只標需重看）、瀏覽器測試、說明書章節全部被標記；
    每個標記附理由清除後才消失。"""
    _deliver("entry-fix")
    assert code("archive", "entry-fix") == 0
    home = port.planning_home
    write_leaf(home, "guide", concept={"id": "c-guide", "title": "說明書", "order": 0, "concept": "說明",
                                       "brief": {"audience": "x", "depth": "y", "breadth": "z"}})
    write_leaf(home, "guide/home", concept={"id": "c-home", "title": "首頁", "order": 1,
                                            "concept": "首頁說明", "realizes": ["req:task-entry-page/R1"]})

    ruling_cmd.run(["add", "--quote", "首頁改成資料集總覽", *RB, "--supersedes", "RL-claude-1"])
    decision_cmd.run(["add", "--title", "首頁是資料集總覽", "--statement", "首頁是資料集總覽，/tasks 轉址",
                      "--based-on", "RL-claude-2", "--supersedes", "D-claude-1"])
    decision_cmd.run(["activate", "D-claude-2"])

    flags = {s["target"]: s for s in _suspects(capsys)}
    assert "req:task-entry-page/R1" in flags
    assert "task:entry-fix#1" in flags                                # 已完成的任務：標記，不重開
    assert "test:labelvault:tests/browser/test_entry_page.py::test_first_row_visible" in flags
    assert "doc:guide/home" in flags
    assert "req:task-entry-page/R2" not in flags                      # 沒依據這條決策的不受影響
    assert flags["task:entry-fix#1"]["path"] == [
        "D-claude-1", "based-on", "req:task-entry-page/R1", "implements", "task:entry-fix#1"]

    from dspx.engine.software import changes as chg
    t = chg.load_archived(port, "entry-fix")["tasks"]["tasks"][0]
    assert t["status"] == "done"                                      # 歷史沒被改
    for target, s in flags.items():
        assert impact_cmd.run(["clear", s["id"], "--reason", f"看過 {target}，已依新決策處理"]) == 0
    assert _suspects(capsys) == []


def test_s5_waivers_show_on_the_roadmap(port, capsys):
    """封存時未驗證的三項（車輛 bag、NAS、資料碟）以豁免呈現；roadmap 顯示「完成（含豁免 3 項）」。"""
    roadmap_cmd.run(["add", "--title", "資料集管理", "--ref", "swc:dataset-library"])
    _deliver("dataset-library")
    ruling_cmd.run(["add", "--quote", "車輛 bag、NAS、資料碟還沒到，先豁免", *RB])
    for i, what in enumerate(("車輛 bag 相容性", "NAS 同步", "專用資料碟"), 2):
        code("task", "add", "dataset-library", "--title", f"驗證{what}", "--verify", "demonstration")
        assert code("evidence", "waive", "dataset-library", str(i), "--ruling", "RL-claude-2",
                    "--reopen-when", f"{what}可用時") == 0
    assert code("archive", "dataset-library") == 0
    capsys.readouterr()
    roadmap_cmd.run([])
    out = capsys.readouterr().out
    assert "完成（含豁免 3 項）" in out and "資料集管理" in out


def test_s7_import_counts_check_and_pending_merge(make_project, monkeypatch, capsys):
    """匯入：數量與原檔一致、check 通過、局部取代的設計決策（D7／D13／D15）列為待合併。"""
    home = make_project()
    monkeypatch.chdir(home.parent)
    monkeypatch.setenv("DOCSPEC_AGENT", "claude")
    root = home.parent / "openspec"
    reqs = "".join(f"### Requirement: Req {i}\nIt SHALL do {i}.\n\n#### Scenario: s{i}\n"
                   f"- **WHEN** a{i}\n- **THEN** b{i}\n\n" for i in range(1, 4))
    for cap in ("task-entry-page", "annotation/recording-folder-format"):
        p = root / "specs" / cap / "spec.md"
        p.parent.mkdir(parents=True)
        p.write_text(f"## Purpose\n{cap}\n\n## Requirements\n\n{reqs}", encoding="utf-8")
    ch = root / "changes" / "dataset-library"
    (ch / "specs" / "task-entry-page").mkdir(parents=True)
    (ch / "proposal.md").write_text("## Why\n\nT2.\n", encoding="utf-8")
    (ch / "tasks.md").write_text("- [x] 1.1 a\n- [ ] 1.2 b\n", encoding="utf-8")
    (ch / "design.md").write_text(
        "## Decisions\n\n### D1. Services\n\n### D7. Shared overview\n\n"
        "## D13. User rulings (supersede earlier text where they conflict)\n\n"
        "### D15. Home page (supersede D7's dashboard revision where they conflict)\n", encoding="utf-8")
    (ch / "specs" / "task-entry-page" / "spec.md").write_text(
        "## ADDED Requirements\n\n### Requirement: GPU status\nIt SHALL show GPU.\n\n"
        "#### Scenario: g\n- **WHEN** x\n- **THEN** y\n", encoding="utf-8")
    for i in range(3):
        a = root / "changes" / "archive" / f"2026-09-1{i}-old-{i}"
        a.mkdir(parents=True)
        (a / "proposal.md").write_text("## Why\n\nold\n", encoding="utf-8")

    assert code("import-openspec") == 0
    layout = Layout(home)
    counts = {c: (len(s["requirements"]), sum(len(r["scenarios"]) for r in s["requirements"]))
              for c, s in sp.load_all(layout).items()}
    assert counts == {"task-entry-page": (3, 3), "annotation/recording-folder-format": (3, 3)}
    from dspx.engine.software import changes as chg
    assert len(chg.list_archived(layout)) == 3 and chg.list_active(layout) == ["dataset-library"]
    assert run_check(load_project(layout), load_schema(), layout).ok
    report = (io.root(layout) / "import-openspec-report.md").read_text(encoding="utf-8")
    assert "待合併：D7、D13、D15" in report
    oq = chg.load_change(layout, "dataset-library")["design"]["open-questions"][0]
    assert "D7、D13、D15" in oq


def test_s8_changing_one_scenario_leaves_the_others_untouched(port):
    before = sp.load_spec(port, "task-entry-page")
    _deliver("one-scenario", ref="R1/S1", then="第一列完整可見，不被工具列遮住")
    delta = io.load(io.change_dir(port, "one-scenario") / "specs" / "task-entry-page.yaml", "delta")
    assert delta["deltas"] == [{"op": "modify-scenario", "ref": "R1/S1",
                                "then": "第一列完整可見，不被工具列遮住", "base": delta["deltas"][0]["base"]}]
    assert code("archive", "one-scenario") == 0
    after = sp.load_spec(port, "task-entry-page")
    assert after["requirements"][0]["scenarios"][1] == before["requirements"][0]["scenarios"][1]
    assert after["requirements"][1] == before["requirements"][1]
    assert {k: v for k, v in after["requirements"][0].items() if k != "scenarios"} == \
        {k: v for k, v in before["requirements"][0].items() if k != "scenarios"}


def test_s9_the_later_of_two_changes_to_the_same_place_stops(port, capsys):
    _deliver("first", then="A")
    _deliver("second", then="B")
    assert code("archive", "first") == 0
    capsys.readouterr()
    assert code("archive", "second") == 1
    assert "changed since this delta was written" in capsys.readouterr().out
    assert sp.load_spec(port, "task-entry-page")["requirements"][0]["scenarios"][0]["then"] == "A"
    assert io.change_dir(port, "second").exists()                   # 沒被搬走、沒被部分寫入
