"""軟體領域：證據（引擎代跑測試）與任務完成的自動推導。"""

from __future__ import annotations

import json
import shlex
import sys

import pytest

from dspx.commands.code import code as code_cmd
from dspx.commands.governance import ruling as ruling_cmd
from dspx.engine.layout import Layout
from dspx.engine.software import changes as chg
from dspx.engine.software import evidence as ev
from dspx.engine.software import io
from dspx.engine.software import specs as sp

TEST_SRC = """
import pytest

def test_first_row():
    assert True

def test_empty():
    assert {empty}

@pytest.mark.skip(reason="no GPU")
def test_gpu():
    pass

class TestLayout:
    def test_width(self):
        assert True
"""


def code(*argv) -> int:
    return code_cmd.run(list(argv))


def _spec() -> dict:
    return {"capability": "entry", "purpose": "入口頁", "requirements": [
        {"id": "R1", "title": "列出任務", "statement": "It SHALL list tasks.", "verification": ["test"],
         "scenarios": [{"id": "S1", "title": "第一列", "when": "開啟", "then": "看到"},
                       {"id": "S2", "title": "空", "when": "沒資料", "then": "提示"}]},
        {"id": "R2", "title": "版面", "statement": "It MUST fit.", "verification": ["inspection"],
         "scenarios": [{"id": "S1", "title": "寬", "when": "1280", "then": "不捲動"}]}]}


@pytest.fixture
def proj(make_project, monkeypatch):
    home = make_project()
    monkeypatch.chdir(home.parent)
    monkeypatch.setenv("DOCSPEC_AGENT", "claude")
    layout = Layout(home)
    app = layout.project_root / "app"
    (app / "tests").mkdir(parents=True)
    (app / "src").mkdir()
    (app / "src" / "entry.py").write_text("X = 1\n", encoding="utf-8")
    (app / "tests" / "test_entry.py").write_text(TEST_SRC.format(empty="True"), encoding="utf-8")
    cmd = shlex.join([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"])
    io.config_path(layout).parent.mkdir(parents=True, exist_ok=True)
    io.config_path(layout).write_text(
        f"repos:\n  app: {{path: app, test-command: {json.dumps(cmd)}}}\n", encoding="utf-8")
    sp.write_spec(layout, _spec())
    code("change", "new", "fix", "--why", "x", "--modified", "entry")
    code("change", "delta", "fix", "--capability", "entry", "--op", "modify-scenario",
         "--ref", "R1/S1", "--then", "完整看到")
    monkeypatch.setenv("DOCSPEC_AGENT", "gemini")          # 測試角色
    code("testplan", "add", "fix", "--location", "app:tests/test_entry.py::test_first_row",
         "--covers", "entry/R1/S1")
    code("testplan", "add", "fix", "--location", "app:tests/test_entry.py::test_empty",
         "--covers", "entry/R1/S2")
    code("testplan", "add", "fix", "--location", "app:tests/test_entry.py::test_gpu",
         "--covers", "entry/R1/S2")
    code("testplan", "add", "fix", "--location", "app:tests/test_entry.py::TestLayout::test_width",
         "--covers", "entry/R2/S1")
    code("testplan", "sign", "fix")                           # 測試角色寫好測試後簽收
    monkeypatch.setenv("DOCSPEC_AGENT", "claude")          # 實作者
    code("task", "add", "fix", "--title", "修第一列", "--implements", "entry/R1",
         "--files", "app:src/entry.py", "--verify", "test", "--tests", "T1,T4")
    return layout


def _task(layout, tid="1") -> dict:
    return next(t for t in chg.load_change(layout, "fix")["tasks"]["tasks"] if t["id"] == tid)


def test_run_passes_and_engine_marks_done(proj, capsys):
    assert _task(proj)["status"] == "not-started"
    assert code("evidence", "run", "fix", "1") == 0
    out = capsys.readouterr().out
    assert "passed 2, failed 0, skipped 0" in out
    assert "未開始 → 完成" in out
    t = _task(proj)
    assert t["status"] == "done" and t["evidence"] == ["E-claude-1"] and t["completed-at"]
    e = ev.load_all(proj)[0]
    assert [p["outcome"] for p in e["per-test"]] == ["passed", "passed"]
    assert e["environment"]["python"] and e["files"]["app:src/entry.py"].startswith("sha256:")


def test_changing_a_declared_file_reverts_to_needs_rerun(proj, capsys):
    code("evidence", "run", "fix", "1")
    (proj.project_root / "app" / "src" / "entry.py").write_text("X = 2\n", encoding="utf-8")
    capsys.readouterr()
    code("change", "status", "fix")
    out = capsys.readouterr().out
    assert "完成 → 需重跑證據" in out and "app:src/entry.py" in out
    assert _task(proj)["status"] == "needs-rerun"
    assert "completed-at" not in _task(proj)
    code("evidence", "run", "fix", "1")
    assert _task(proj)["status"] == "done"


def test_failing_test_blocks_completion(proj, capsys):
    code("task", "add", "fix", "--title", "空清單", "--implements", "entry/R1", "--verify", "test",
         "--tests", "T2")
    (proj.project_root / "app" / "tests" / "test_entry.py").write_text(
        TEST_SRC.format(empty="False"), encoding="utf-8")
    assert code("evidence", "run", "fix", "2") == 1
    out = capsys.readouterr().out
    assert "T2" in out and "failed" in out
    assert _task(proj, "2")["status"] == "in-progress"


def test_skips_need_to_be_declared(proj, capsys):
    code("task", "add", "fix", "--title", "gpu", "--implements", "entry/R1", "--verify", "test",
         "--tests", "T3")
    assert code("evidence", "run", "fix", "2") == 1
    assert "not declared with --allow-skips" in capsys.readouterr().out
    code("task", "add", "fix", "--title", "gpu ok", "--implements", "entry/R1", "--verify", "test",
         "--tests", "T3", "--allow-skips")
    assert code("evidence", "run", "fix", "3") == 0
    assert _task(proj, "3")["status"] == "done"


def test_planned_test_missing_from_run_fails(proj, capsys):
    code("testplan", "add", "fix", "--location", "app:tests/test_entry.py::test_nope",
         "--covers", "entry/R1/S1")
    code("task", "add", "fix", "--title", "x", "--implements", "entry/R1", "--verify", "test",
         "--tests", "T5")
    assert code("evidence", "run", "fix", "2") == 1
    assert "not found in the run: T5" in capsys.readouterr().out


def test_custom_commands_are_refused(proj, capsys):
    """A1：不接受自訂指令（`-- true` 曾讓一定失敗的測試變成「完成」）。"""
    assert code("evidence", "run", "fix", "1", "--", "true") == 1
    assert "custom test commands are not accepted" in capsys.readouterr().err
    assert ev.load_all(proj) == []


def test_inspection_and_acceptance(proj):
    code("task", "add", "fix", "--title", "版面", "--implements", "entry/R2", "--verify", "inspection")
    assert code("evidence", "add", "fix", "2", "--type", "inspection", "--subject", "screenshot 1280",
                "--conclusion", "寬度不足", "--result", "fail") == 1
    assert _task(proj, "2")["status"] == "in-progress"
    assert code("evidence", "accept", "fix", "2", "--read-back", "1280 寬已無水平捲動",
                "--confirmed", "對") == 0
    assert _task(proj, "2")["status"] == "done"


def test_waiver_needs_an_effective_ruling(proj, capsys):
    assert code("evidence", "waive", "fix", "1", "--ruling", "RL-claude-1",
                "--reopen-when", "有 GPU 時") == 1
    assert "effective ruling" in capsys.readouterr().err
    ruling_cmd.run(["add", "--quote", "這項先豁免", "--read-back", "豁免任務 1", "--confirmed", "好"])
    assert code("evidence", "waive", "fix", "1", "--ruling", "RL-claude-1",
                "--reopen-when", "有 GPU 時") == 0
    assert _task(proj)["status"] == "done-waived"


def test_check_warns_when_recorded_status_is_behind(proj):
    from dspx.engine.software import validate_all
    code("evidence", "run", "fix", "1")
    (proj.project_root / "app" / "src" / "entry.py").write_text("X = 3\n", encoding="utf-8")
    _errs, warns = validate_all(proj)
    assert any("recorded \"done\" but evidence says \"needs-rerun\"" in w for w in warns)


def test_same_agent_writing_tests_and_task_is_flagged(proj, monkeypatch):
    """B4：比的是「測試撰寫者」和「任務建立者」，不是誰跑了測試。"""
    from dspx.engine.software import validate_all
    monkeypatch.setenv("DOCSPEC_AGENT", "gemini")          # 測試角色自己跑測試：正常
    code("evidence", "run", "fix", "1")
    assert not any("same agent" in w for w in validate_all(proj)[1])
    code("task", "add", "fix", "--title", "x", "--implements", "entry/R1", "--files", "app:src/entry.py",
         "--verify", "test", "--tests", "T1")                  # gemini 自己建任務又用自己寫的測試
    assert any("same agent that created task 2" in w for w in validate_all(proj)[1])


def test_junit_matching_is_exact():
    """A2：引擎固定 rootdir＝repo 根目錄，名稱必須完整相符；別處的同名檔不能冒充。"""
    case = {"classname": "tests.test_entry.TestLayout", "name": "test_width[1]"}
    assert ev._matches("app:tests/test_entry.py::TestLayout::test_width", case)
    assert ev._matches("app:tests/test_entry.py", case)
    assert not ev._matches("app:tests/test_entry.py::test_width", case)
    fake = {"classname": "test_entry.TestLayout", "name": "test_width"}    # 別的 rootdir 跑出來的
    assert not ev._matches("app:tests/test_entry.py::TestLayout::test_width", fake)
