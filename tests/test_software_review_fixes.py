"""第二期 review（docs/dev/phase2-review.md）每一項修正的回歸測試：A1–A3、A5、A6、B1–B4。"""

from __future__ import annotations

import json
import shlex
import sys

import pytest
import yaml

from dspx.commands.code import code as code_cmd
from dspx.commands.governance import ruling as ruling_cmd
from dspx.engine.layout import Layout
from dspx.engine.software import changes as chg
from dspx.engine.software import io
from dspx.engine.software import specs as sp
from dspx.engine.software import validate_all

FAILING = "def test_a():\n    assert False\n"


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
    (app / "src").mkdir()
    (app / "src" / "a.py").write_text("X = 1\n", encoding="utf-8")
    (app / "tests" / "test_a.py").write_text(FAILING, encoding="utf-8")
    cmd = shlex.join([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"])
    io.config_path(layout).parent.mkdir(parents=True, exist_ok=True)
    io.config_path(layout).write_text(
        f"repos:\n  app: {{path: app, test-command: {json.dumps(cmd)}}}\n", encoding="utf-8")
    sp.write_spec(layout, {"capability": "c", "purpose": "p", "requirements": [
        {"id": "R1", "title": "t", "statement": "It SHALL x.", "verification": ["test"],
         "scenarios": [{"id": "S1", "title": "s", "when": "w", "then": "t"},
                       {"id": "S2", "title": "s2", "when": "w2", "then": "t2"}]}]})
    code("change", "new", "f", "--why", "x", "--modified", "c")
    code("change", "delta", "f", "--capability", "c", "--op", "modify-scenario", "--ref", "R1/S1",
         "--then", "y")
    code("testplan", "add", "f", "--location", "app:tests/test_a.py::test_a", "--covers", "c/R1/S1",
         "--by", "gemini")
    code("task", "add", "f", "--title", "t", "--implements", "c/R1", "--files", "app:src/a.py",
         "--verify", "test", "--tests", "T1")
    return layout


def _status(layout, tid="1"):
    return next(t for t in chg.load_change(layout, "f")["tasks"]["tasks"] if t["id"] == tid)["status"]


def test_a1_custom_command_cannot_complete_a_task(proj, capsys):
    code("testplan", "sign", "f", "--by", "gemini")
    assert code("evidence", "run", "f", "1", "--", "true") == 1
    assert _status(proj) == "not-started"


def test_a3_unsigned_tests_do_not_count(proj, capsys):
    (proj.project_root / "app" / "tests" / "test_a.py").write_text(FAILING.replace("False", "True"),
                                                                    encoding="utf-8")
    assert code("evidence", "run", "f", "1") == 1
    assert "has not been signed off by the test role" in capsys.readouterr().out
    assert _status(proj) == "in-progress"


def test_a3_test_changed_after_sign_off_is_refused_until_the_test_role_re_signs(proj, capsys):
    code("testplan", "sign", "f", "--by", "gemini")
    test_file = proj.project_root / "app" / "tests" / "test_a.py"
    test_file.write_text(FAILING.replace("False", "True"), encoding="utf-8")     # 實作者改測試
    capsys.readouterr()
    assert code("evidence", "run", "f", "1") == 1
    assert "changed after the test role signed it off" in capsys.readouterr().out
    assert _status(proj) == "in-progress"
    # 測試角色看過之後同意修改、重新簽收 → 才算數
    assert code("testplan", "sign", "f", "--by", "gemini") == 0
    assert code("evidence", "run", "f", "1") == 0
    assert _status(proj) == "done"


def test_a3_only_the_test_author_signs(proj, capsys):
    assert code("testplan", "sign", "f", "--by", "claude") == 1          # 實作者（建任務的人）
    assert "only its author" in capsys.readouterr().err
    code("testplan", "add", "f", "--location", "app:tests/test_missing.py::test_x", "--covers",
         "c/R1/S1", "--by", "gemini")
    assert code("testplan", "sign", "f", "T2", "--by", "gemini") == 1   # 測試還沒寫
    assert "does not exist yet" in capsys.readouterr().err


def test_a3_implementation_task_cannot_declare_a_test_file(proj):
    code("task", "add", "f", "--title", "x", "--implements", "c/R1",
         "--files", "app:tests/test_a.py", "--verify", "inspection")
    errs, _w = validate_all(proj)
    assert any("tests belong to the test role" in e for e in errs)


def test_a5_task_without_files_gets_a_reminder(proj):
    code("task", "add", "f", "--title", "no files", "--implements", "c/R1", "--verify", "test",
         "--tests", "T1")
    _e, warns = validate_all(proj)
    assert any("task 2: declares no files" in w for w in warns)


def test_a6_waiver_shows_the_ruling_text(proj, capsys):
    ruling_cmd.run(["add", "--quote", "首頁字型用思源黑體", "--read-back", "字型", "--confirmed", "對"])
    capsys.readouterr()
    assert code("evidence", "waive", "f", "1", "--ruling", "RL-claude-1", "--reopen-when", "x") == 0
    out = capsys.readouterr().out
    assert "waived by 「首頁字型用思源黑體」(gov:RL-claude-1)" in out
    assert "check that this ruling is really about this task" in out


def test_b1_seal_message_points_to_the_right_fix(proj):
    p = io.change_dir(proj, "f") / "tasks.yaml"
    p.write_text(p.read_text(encoding="utf-8").replace("not-started", "done"), encoding="utf-8")
    with pytest.raises(io.SoftwareError) as exc:
        chg.load_change(proj, "f")
    assert "fsck" not in str(exc.value) and "docspec code" in str(exc.value)


def test_b2_gaps_template_round_trip(proj, capsys, tmp_path):
    code("change", "delta", "f", "--capability", "c", "--op", "modify-scenario", "--ref", "R1/S2",
         "--then", "z")
    code("task", "add", "f", "--title", "imported-like", "--verify", "inspection")
    capsys.readouterr()
    assert code("change", "gaps", "f") == 0
    out = capsys.readouterr().out
    assert "scenarios without a planned test: 1" in out and "c/R1/S2" in out
    assert code("change", "gaps", "f", "--template") == 0
    draft = yaml.safe_load(capsys.readouterr().out)
    assert [t["task"] for t in draft["tasks"]] == ["2"]
    assert draft["tests"] == [{"location": "", "covers": ["c/R1/S2"], "level": "unit"}]
    # 實作者填任務、測試角色填測試，各自載入
    draft["tasks"][0].update({"implements": ["c/R1"], "files": ["app:src/a.py"]})
    draft["tests"][0]["location"] = "app:tests/test_a.py::test_a"
    f = tmp_path / "links.yaml"
    f.write_text(yaml.safe_dump(draft, allow_unicode=True), encoding="utf-8")
    assert code("task", "set", "f", "--from", str(f)) == 0
    assert code("testplan", "add", "f", "--from", str(f), "--by", "gemini") == 0
    capsys.readouterr()
    code("change", "gaps", "f")
    out = capsys.readouterr().out
    assert "scenarios without a planned test: 0" in out
    assert "tasks missing verification or files: 0" in out


def test_b2_bad_entry_writes_nothing(proj, tmp_path):
    f = tmp_path / "links.yaml"
    f.write_text("tasks:\n  - task: '1'\n    files: [app:src/b.py]\n  - task: '99'\n", encoding="utf-8")
    assert code("task", "set", "f", "--from", str(f)) == 1
    t = chg.load_change(proj, "f")["tasks"]["tasks"][0]
    assert t["files"] == ["app:src/a.py"]                              # 全部成功才寫入


def test_b3_import_report_lists_screen_like_requirements(make_project, monkeypatch):
    from dspx.engine.software import openspec_import as osi
    spec = {"capability": "home", "requirements": [
        {"id": "R1", "title": "Home", "statement": "The first row SHALL be visible at 1366×768."},
        {"id": "R2", "title": "Delete", "statement": "Deleting SHALL be one step."}]}
    assert osi.screen_like(spec) == ["home/R1 Home"]


def test_b4_tasks_record_their_creator(proj):
    assert chg.load_change(proj, "f")["tasks"]["tasks"][0]["created-by"] == "claude"
