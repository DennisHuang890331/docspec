"""軟體領域：封存（差異併回正式規格、資料夾收進 _archive、基線）與回歸測試。"""

from __future__ import annotations

import json
import shlex
import shutil
import sys

import pytest

from dspx.commands.code import code as code_cmd
from dspx.engine.layout import Layout
from dspx.engine.software import changes as chg
from dspx.engine.software import io
from dspx.engine.software import specs as sp
from dspx.engine.software import validate_all

TESTS = """
def test_first_row():
    assert {ok}

def test_width():
    assert True
"""


def code(*argv) -> int:
    return code_cmd.run(list(argv))


def _spec() -> dict:
    return {"capability": "entry", "purpose": "入口頁", "requirements": [
        {"id": "R1", "title": "列出任務", "statement": "It SHALL list tasks.", "verification": ["test"],
         "scenarios": [{"id": "S1", "title": "第一列", "when": "開啟", "then": "看到第一列"}]},
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
    (app / "tests" / "test_entry.py").write_text(TESTS.format(ok="True"), encoding="utf-8")
    cmd = shlex.join([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"])
    io.config_path(layout).parent.mkdir(parents=True, exist_ok=True)
    io.config_path(layout).write_text(
        f"repos:\n  app: {{path: app, test-command: {json.dumps(cmd)}}}\n", encoding="utf-8")
    sp.write_spec(layout, _spec())
    return layout


def _change(cid: str, then: str = "第一列完整可見", run: bool = True) -> None:
    code("change", "new", cid, "--why", "x", "--modified", "entry")
    code("change", "delta", cid, "--capability", "entry", "--op", "modify-scenario",
         "--ref", "R1/S1", "--then", then)
    code("testplan", "add", cid, "--location", "app:tests/test_entry.py::test_first_row",
         "--covers", "entry/R1/S1", "--by", "gemini")
    code("task", "add", cid, "--title", "修", "--implements", "entry/R1", "--files", "app:src/entry.py",
         "--verify", "test", "--tests", "T1")
    if run:
        code("evidence", "run", cid, "1")


def test_archive_merges_spec_moves_folder_and_writes_baseline(proj, capsys):
    _change("fix")
    capsys.readouterr()
    assert code("archive", "fix") == 0
    out = capsys.readouterr().out
    assert "spec entry updated" in out and "_archive" in out
    s1 = sp.load_spec(proj, "entry")["requirements"][0]["scenarios"][0]
    assert s1["then"] == "第一列完整可見"
    assert s1["verified-by"] == ["app:tests/test_entry.py::test_first_row"]
    assert not io.change_dir(proj, "fix").exists()
    assert chg.change_state(proj, "fix") == "archived"
    [baseline] = list(io.baselines_dir(proj).glob("*-fix.yaml"))
    body = io.load(baseline, "baseline")
    assert body["evidence"] == ["E-claude-1"] and body["tasks"] == {"done": 1}
    assert code("change", "show", "fix") == 0                   # 封存後仍查得到
    assert "第一列完整可見" in capsys.readouterr().out
    assert code("change", "new", "fix", "--why", "again") == 1  # id 不能重用
    errs, _w = validate_all(proj)
    assert errs == []


def test_archive_blocked_until_tasks_are_done(proj, capsys):
    _change("fix", run=False)
    capsys.readouterr()
    assert code("archive", "fix") == 1
    out = capsys.readouterr().out
    assert "task 1 (修) is 未開始" in out
    assert sp.load_spec(proj, "entry") == _spec()              # 沒動
    assert io.change_dir(proj, "fix").exists()


def test_dry_run_writes_nothing(proj, capsys):
    _change("fix")
    capsys.readouterr()
    assert code("archive", "fix", "--dry-run") == 0
    assert "would archive fix" in capsys.readouterr().out
    assert sp.load_spec(proj, "entry") == _spec()
    assert io.change_dir(proj, "fix").exists()


def test_human_verified_requirement_needs_acceptance(proj, capsys):
    code("change", "new", "lay", "--why", "x", "--modified", "entry")
    code("change", "delta", "lay", "--capability", "entry", "--op", "modify-requirement",
         "--ref", "R2", "--statement", "It MUST fit 1024px.")
    code("task", "add", "lay", "--title", "寬度", "--implements", "entry/R2", "--verify", "inspection")
    code("evidence", "add", "lay", "1", "--type", "inspection", "--subject", "截圖", "--conclusion", "ok")
    capsys.readouterr()
    assert code("archive", "lay") == 1
    assert "needs the owner's acceptance" in capsys.readouterr().out
    code("evidence", "accept", "lay", "1", "--read-back", "1024 寬已無捲動", "--confirmed", "對")
    assert code("archive", "lay") == 0
    assert sp.load_spec(proj, "entry")["requirements"][1]["statement"] == "It MUST fit 1024px."


def test_second_change_on_same_scenario_stops_instead_of_overwriting(proj, capsys):
    _change("a", then="A 版")
    _change("b", then="B 版")
    capsys.readouterr()
    assert code("archive", "a") == 0
    assert "active change b edits the same capability" in capsys.readouterr().out
    assert code("archive", "b") == 1
    assert "changed since this delta was written" in capsys.readouterr().out
    assert sp.load_spec(proj, "entry")["requirements"][0]["scenarios"][0]["then"] == "A 版"


def test_unarchived_prerequisite_blocks(proj, capsys):
    _change("base", run=False)
    code("change", "new", "next", "--why", "x", "--depends-on", "base")
    capsys.readouterr()
    assert code("archive", "next") == 1
    assert "must be archived first" in capsys.readouterr().out


def test_failure_midway_rolls_back(proj, monkeypatch):
    _change("fix")

    def boom(*_a, **_k):
        raise OSError("disk full")
    monkeypatch.setattr(shutil, "move", boom)
    assert code("archive", "fix") == 1
    assert sp.load_spec(proj, "entry") == _spec()
    assert not list(io.baselines_dir(proj).glob("*.yaml"))
    assert io.change_dir(proj, "fix").exists()


def test_regression_list_and_run_map_failures_to_scenarios(proj, capsys):
    _change("fix")
    code("archive", "fix")
    capsys.readouterr()
    assert code("test", "--list") == 0
    assert "app:tests/test_entry.py::test_first_row  ← entry/R1/S1" in capsys.readouterr().out
    assert code("test") == 0
    assert "passed 1, failed 0" in capsys.readouterr().out
    (proj.project_root / "app" / "tests" / "test_entry.py").write_text(
        TESTS.format(ok="False"), encoding="utf-8")
    assert code("test") == 1
    assert "failed → affects entry/R1/S1" in capsys.readouterr().out


def test_deleted_test_file_breaks_verified_by(proj):
    _change("fix")
    code("archive", "fix")
    (proj.project_root / "app" / "tests" / "test_entry.py").unlink()
    errs, _w = validate_all(proj)
    assert any("test file is missing" in e and "entry/R1/S1" in e for e in errs)


def test_archive_creates_a_new_capability(proj, tmp_path):
    code("change", "new", "lib", "--why", "資料庫", "--new", "library")
    code("change", "delta", "lib", "--capability", "library", "--purpose", "管理資料集",
         "--op", "add-requirement", "--title", "列出", "--statement", "It SHALL list datasets.",
         "--verification", "test", "--scenario", "有資料 | 開啟 | 列出")
    code("testplan", "add", "lib", "--location", "app:tests/test_entry.py::test_width",
         "--covers", "library/R1/S1", "--by", "gemini")
    code("task", "add", "lib", "--title", "做", "--implements", "library/R1", "--verify", "test",
         "--tests", "T1")
    code("evidence", "run", "lib", "1")
    assert code("archive", "lib") == 0
    spec = sp.load_spec(proj, "library")
    assert spec["purpose"] == "管理資料集"
    assert spec["requirements"][0]["scenarios"][0]["verified-by"] == ["app:tests/test_entry.py::test_width"]
    assert sp.validate_spec(spec) == []
