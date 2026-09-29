"""考場排座位實測（2026/09/30）發現的缺口：登記 repo 的指令、未登記 repo 的簽收訊息、
test-command 開頭的環境變數與佔位符、design 清單欄位可刪除。"""

from __future__ import annotations

import sys

import pytest

from dspx.commands.code import code as code_cmd
from dspx.engine.layout import Layout
from dspx.engine.software import changes as chg
from dspx.engine.software import evidence as ev
from dspx.engine.software import specs as sp


def code(*argv) -> int:
    return code_cmd.run(list(argv))


def _spec() -> dict:
    return {"capability": "entry", "purpose": "入口", "requirements": [
        {"id": "R1", "title": "t", "statement": "It SHALL x.", "verification": ["test"],
         "scenarios": [{"id": "S1", "title": "s", "when": "w", "then": "t"}]}]}


@pytest.fixture
def proj(make_project, monkeypatch):
    home = make_project()
    monkeypatch.chdir(home.parent)
    monkeypatch.setenv("DOCSPEC_AGENT", "claude")
    layout = Layout(home)
    app = layout.project_root / "app"
    (app / "tests").mkdir(parents=True)
    (app / "src" / "pkg").mkdir(parents=True)
    (app / "src" / "pkg" / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
    (app / "tests" / "test_x.py").write_text(
        "from pkg import VALUE\n\ndef test_value():\n    assert VALUE == 1\n", encoding="utf-8")
    sp.write_spec(layout, _spec())
    return layout


def test_repo_add_writes_config_and_list_shows_command(proj, capsys):
    assert code("repo", "list") == 0
    assert "no repos registered" in capsys.readouterr().out
    assert code("repo", "add", "app", "app", "--test-command", "PYTHONPATH=src python -m pytest -q") == 0
    out = capsys.readouterr().out
    assert "registered" in out and "--junitxml" in out
    assert chg.repo_settings(proj)["app"] == {"path": "app",
                                              "test-command": "PYTHONPATH=src python -m pytest -q"}
    assert code("repo", "list") == 0
    assert "tests run as: PYTHONPATH=src python -m pytest -q '--rootdir=" in capsys.readouterr().out


def test_placeholder_in_test_command_is_refused(proj, capsys):
    assert code("repo", "add", "app", "app", "--test-command", "pytest {tests}") == 1
    assert "placeholder" in capsys.readouterr().err
    assert "app" not in chg.repo_settings(proj)


def test_sign_names_the_unregistered_repo(proj, capsys):
    code("change", "new", "fix", "--why", "x", "--modified", "entry")
    code("change", "delta", "fix", "--capability", "entry", "--op", "modify-scenario",
         "--ref", "R1/S1", "--then", "改")
    code("testplan", "add", "fix", "--location", "app:tests/test_x.py::test_value",
         "--covers", "entry/R1/S1")
    capsys.readouterr()
    assert code("testplan", "sign", "fix") == 1
    err = capsys.readouterr().err
    assert "not registered" in err and "docspec code repo add" in err
    assert "write it first" not in err


def test_env_prefix_reaches_the_test_run(proj, capsys, monkeypatch):
    monkeypatch.delenv("PYTHONPATH", raising=False)
    code("repo", "add", "app", "app", "--test-command",
         f"PYTHONPATH=src {sys.executable} -m pytest -q -p no:cacheprovider")
    code("change", "new", "fix", "--why", "x", "--modified", "entry")
    code("change", "delta", "fix", "--capability", "entry", "--op", "modify-scenario",
         "--ref", "R1/S1", "--then", "改")
    monkeypatch.setenv("DOCSPEC_AGENT", "gemini")
    code("testplan", "add", "fix", "--location", "app:tests/test_x.py::test_value",
         "--covers", "entry/R1/S1")
    assert code("testplan", "sign", "fix") == 0
    monkeypatch.setenv("DOCSPEC_AGENT", "claude")
    code("task", "add", "fix", "--title", "t", "--implements", "entry/R1",
         "--files", "app:src/pkg/__init__.py", "--verify", "test", "--tests", "T1")
    capsys.readouterr()
    assert code("evidence", "run", "fix", "1") == 0, capsys.readouterr()
    assert ev.command_env(proj, "app")["PYTHONPATH"] == "src"


def test_design_list_items_can_be_removed(proj, capsys):
    code("change", "new", "fix", "--why", "x", "--modified", "entry")
    code("change", "design", "fix", "--goal", "輸出 HTML 與 Excel", "--goal", "只輸出 HTML")
    assert code("change", "design", "fix", "--remove-goal", "輸出 HTML 與 Excel") == 0
    assert chg.load_change(proj, "fix")["design"]["goals"] == ["只輸出 HTML"]
    assert code("change", "design", "fix", "--remove-goal", "1") == 0
    assert "goals" not in chg.load_change(proj, "fix")["design"]
    assert code("change", "design", "fix", "--remove-risk", "沒有這條") == 1
    assert "no item" in capsys.readouterr().err


def test_change_can_reword_what_it_adds_keeping_ids(proj, capsys):
    """改自己新增的需求／情境：原地修改，編號不變（不必 undelta 再重加，測試的 covers 不斷）。"""
    code("change", "new", "fix", "--why", "x", "--new", "roster")
    assert code("change", "delta", "fix", "--capability", "roster", "--purpose", "名單",
                "--op", "add-requirement", "--title", "匯入", "--statement", "It SHALL reject the row.",
                "--verification", "test", "--scenario", "錯誤 | 有錯 | 拒絕該筆") == 0
    code("change", "delta", "fix", "--capability", "roster", "--op", "add-scenario", "--ref", "R1",
         "--title", "空白", "--when", "空檔", "--then", "提示")
    capsys.readouterr()
    assert code("change", "delta", "fix", "--capability", "roster", "--op", "modify-requirement",
                "--ref", "R1", "--statement", "It SHALL reject the whole roster.") == 0
    assert "edited its own new requirement R1" in capsys.readouterr().out
    assert code("change", "delta", "fix", "--capability", "roster", "--op", "modify-scenario",
                "--ref", "R1/S1", "--then", "整份不匯入") == 0
    assert code("change", "delta", "fix", "--capability", "roster", "--op", "modify-scenario",
                "--ref", "R1/S2", "--then", "列出原因") == 0
    deltas = chg.load_change(proj, "fix")["deltas"]["roster"]["deltas"]
    assert [d["op"] for d in deltas] == ["add-requirement", "add-scenario"]
    assert deltas[0]["id"] == "R1" and deltas[0]["statement"] == "It SHALL reject the whole roster."
    assert deltas[0]["scenarios"][0] == {"id": "S1", "title": "錯誤", "when": "有錯", "then": "整份不匯入"}
    assert deltas[1]["then"] == "列出原因"
    assert code("change", "delta", "fix", "--capability", "roster", "--op", "modify-requirement",
                "--ref", "R9", "--statement", "x") == 1          # 不是自己新增的：照舊規則擋下


def test_sign_and_evidence_catch_a_misnamed_planned_test(proj, capsys, monkeypatch):
    """實測：規劃的名稱和檔案裡的不一樣，簽收時就擋下；證據說清楚是哪個名稱，不只給 exit 4。"""
    code("repo", "add", "app", "app", "--test-command",
         f"PYTHONPATH=src {sys.executable} -m pytest -q -p no:cacheprovider")
    code("change", "new", "fix", "--why", "x", "--modified", "entry")
    code("change", "delta", "fix", "--capability", "entry", "--op", "modify-scenario",
         "--ref", "R1/S1", "--then", "改")
    monkeypatch.setenv("DOCSPEC_AGENT", "gemini")
    code("testplan", "add", "fix", "--location", "app:tests/test_x.py::test_valeu",
         "--covers", "entry/R1/S1")
    capsys.readouterr()
    assert code("testplan", "sign", "fix") == 1
    assert 'has no test named "test_valeu"' in capsys.readouterr().err
    from dspx.engine.software import tasks as tk
    assert tk.name_missing(proj, "app:tests/test_x.py::test_value") is None
    assert tk.name_missing(proj, "app:tests/test_x.py::test_value[1]") is None
