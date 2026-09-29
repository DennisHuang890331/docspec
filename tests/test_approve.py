"""使用者批准流程（第一期第 3 步）：`docspec approve` 的三層防護、裁定確認／駁回、發布申請。"""

from __future__ import annotations

import io
import json

import pytest

from dspx.commands._internal import hook as hook_cmd
from dspx.commands.deliverable import publish as publish_cmd
from dspx.commands.deliverable import render as render_cmd
from dspx.commands.governance import approve as approve_cmd
from dspx.commands.governance import decision as decision_cmd
from dspx.commands.governance import ruling as ruling_cmd
from dspx.engine import governance as gv
from dspx.engine.layout import Layout


@pytest.fixture
def owner_terminal(monkeypatch):
    """模擬使用者本人在互動終端機：無 agent 記號、stdin/stdout 是 tty，逐題回答。"""
    answers: list[str] = []
    monkeypatch.setattr("sys.stdin.isatty", lambda: True, raising=False)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True, raising=False)
    monkeypatch.setattr("builtins.input", lambda prompt="": answers.pop(0))
    monkeypatch.setattr(gv, "git_user", lambda cwd: "owner-name")
    return answers


@pytest.fixture
def project(make_project, monkeypatch):
    home = make_project()
    (home / "governance").mkdir()                 # 啟用治理層
    monkeypatch.chdir(home.parent)
    return home


def _as_agent(monkeypatch, tool="claude"):
    monkeypatch.setenv("DOCSPEC_AGENT", tool)


def _as_owner(monkeypatch):
    monkeypatch.delenv("DOCSPEC_AGENT", raising=False)


# ── 防護 ──────────────────────────────────────────────────────────────────

def test_approve_refused_in_agent_environment(project, monkeypatch, owner_terminal, capsys):
    monkeypatch.setenv("CLAUDECODE", "1")                  # tty 也騙不過 agent 記號
    assert approve_cmd.run([]) == 2
    assert "agents cannot run it" in capsys.readouterr().err


def test_approve_refused_without_interactive_terminal(project, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False, raising=False)
    assert approve_cmd.run([]) == 2


def test_approve_list_is_open_to_agents(project, monkeypatch, capsys):
    _as_agent(monkeypatch)
    ruling_cmd.run(["add", "--quote", "刪除就是刪除", "--tier", "major"])
    capsys.readouterr()
    assert approve_cmd.run(["--list", "--json"]) == 0
    pending = json.loads(capsys.readouterr().out)["pending"]
    assert [p["id"] for p in pending] == ["RL-claude-1"]


@pytest.mark.parametrize("command,blocked", [
    ("docspec approve", True),
    ("cd proj && docspec approve", True),
    ("\"C:\\bin\\docspec.exe\" approve", True),
    ("python -m dspx approve", True),
    ("docspec approve --list", False),
    ("docspec ruling list", False),
])
def test_hook_blocks_agent_calling_approve(monkeypatch, command, blocked):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"tool_input": {"command": command}})))
    monkeypatch.setattr("sys.stdin.isatty", lambda: False, raising=False)
    assert hook_cmd.run(["guard"]) == (2 if blocked else 0)


# ── 裁定確認／駁回 ────────────────────────────────────────────────────────

def test_owner_confirms_ruling_then_decision_can_activate(project, monkeypatch, owner_terminal):
    """驗收情境 S3：使用者確認之前決策不能生效；確認後可以，並記下確認者。"""
    _as_agent(monkeypatch)
    ruling_cmd.run(["add", "--quote", "刪除就是刪除", "--tier", "major"])
    decision_cmd.run(["add", "--title", "刪除一步完成", "--statement", "一步完成。",
                      "--based-on", "RL-claude-1"])
    assert decision_cmd.run(["activate", "D-claude-1"]) == 1
    _as_owner(monkeypatch)
    owner_terminal.append("y")
    assert approve_cmd.run([]) == 0
    rec = gv.load_governance(Layout(project)).rulings[0]
    assert (rec["status"], rec["confirmed-by"]) == ("confirmed", "owner-name")
    _as_agent(monkeypatch)
    assert decision_cmd.run(["activate", "D-claude-1"]) == 0


def test_owner_rejects_ruling_and_dependent_decision_is_flagged(project, monkeypatch, owner_terminal):
    _as_agent(monkeypatch)
    ruling_cmd.run(["add", "--quote", "可以插隊", "--tier", "major"])
    decision_cmd.run(["add", "--title", "插隊", "--statement", "互動請求優先。",
                      "--based-on", "RL-claude-1"])
    _as_owner(monkeypatch)
    owner_terminal.extend(["n", "我說的是別的意思"])
    assert approve_cmd.run([]) == 0
    gov = gv.load_governance(Layout(project))
    assert gov.rulings[0]["status"] == "rejected"
    assert gov.rulings[0]["rejected-reason"] == "我說的是別的意思"
    assert [(s["trigger"], s["target"]) for s in gov.suspects] == [("RL-claude-1", "D-claude-1")]


def test_skip_leaves_item_pending(project, monkeypatch, owner_terminal):
    _as_agent(monkeypatch)
    ruling_cmd.run(["add", "--quote", "x", "--tier", "major"])
    _as_owner(monkeypatch)
    owner_terminal.append("s")
    approve_cmd.run([])
    assert gv.load_governance(Layout(project)).rulings[0]["status"] == "pending"


# ── 發布申請 ──────────────────────────────────────────────────────────────

def _written_article(home, write_leaf):
    write_leaf(home, "g/x", concept={"id": "c1", "title": "X", "order": 1},
               decisions=[{"id": "d1", "kind": "normative", "status": "accepted", "statement": "規"}])
    render_cmd.run(["g"])
    latest = home.parent / "docs" / "g" / "_latest.md"
    latest.write_text(latest.read_text(encoding="utf-8").replace("## 1. X\n", "## 1. X\n\n內文。\n"),
                      encoding="utf-8")
    return home.parent / "docs" / "g"


def test_agent_publish_becomes_request_and_owner_approval_publishes(
        project, write_leaf, monkeypatch, owner_terminal):
    docs = _written_article(project, write_leaf)
    _as_agent(monkeypatch)
    assert publish_cmd.run(["g", "--note", "首版"]) == 0
    assert not (docs / "archive").exists()                       # agent 沒有真的發布
    req = gv.load_governance(Layout(project)).requests[0]
    assert (req["action"], req["status"], req["payload"]["article"]) == ("publish", "pending", "g")
    assert publish_cmd.run(["g"]) == 0                           # 重送＝不重複開申請
    assert len(gv.load_governance(Layout(project)).requests) == 1

    _as_owner(monkeypatch)
    owner_terminal.append("y")
    assert approve_cmd.run([]) == 0
    assert (docs / "archive" / "v1.0.0.md").is_file()
    assert gv.load_governance(Layout(project)).requests[0]["status"] == "done"


def test_owner_can_publish_directly(project, write_leaf, monkeypatch):
    docs = _written_article(project, write_leaf)
    assert publish_cmd.run(["g"]) == 0
    assert (docs / "archive" / "v1.0.0.md").is_file()


def test_projects_without_governance_keep_old_publish(make_project, write_leaf, monkeypatch):
    home = make_project()
    monkeypatch.chdir(home.parent)
    docs = _written_article(home, write_leaf)
    _as_agent(monkeypatch)
    assert publish_cmd.run(["g"]) == 0
    assert (docs / "archive" / "v1.0.0.md").is_file()
