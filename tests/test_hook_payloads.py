"""hook guard（第一期第 8 步）：只擋寫入、凍結區只認 docs/…/archive、原生支援 Codex apply_patch
與 Antigravity 呼叫格式、治理紀錄與產生的檢視不可手改。案例取自台中港專案實際踩到的情況。"""

from __future__ import annotations

import io
import json

import pytest

from dspx.commands._internal import hook as hook_cmd
from dspx.reports import freeze


def _guard(monkeypatch, payload) -> int:
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    monkeypatch.setattr("sys.stdin.isatty", lambda: False, raising=False)
    return hook_cmd.run(["guard"])


def _cmd(command):
    return {"tool_input": {"command": command}}


@pytest.mark.parametrize("command", [
    "echo it's in openspec/changes/archive",                    # 單引號不對稱，不再整段擋下
    "find openspec/changes/archive -name tasks.md -exec cat {} \\;",
    "grep -rn foo docs/archive/",
    "cat docs/guide/archive/v1.0.0.md | head",
    "ls openspec/changes/archive/",
    "mv openspec/changes/x openspec/changes/archive/2026-09-29-x",   # OpenSpec 自己的封存目錄
    "cp docs/archive/g_v1.md /tmp/old.md",                      # 從凍結區複製出來＝讀
])
def test_read_only_and_foreign_archive_commands_pass(monkeypatch, command):
    assert _guard(monkeypatch, _cmd(command)) == 0


@pytest.mark.parametrize("command", [
    "rm docs/archive/g_v1.md",
    "find docs/archive -name '*.md' -delete",
    "find docs/guide/archive -exec rm {} \\;",
    "sed -i 's/a/b/' docs/archive/g_v1.md",
    "echo x > docs/archive/g_v1.md",
    "echo it's > docs/archive/g_v1.md",
])
def test_writes_to_docspec_archive_are_blocked(monkeypatch, command):
    assert _guard(monkeypatch, _cmd(command)) == 2


def test_frozen_path_scope():
    assert freeze.is_frozen_path("docs/archive/g_v1.md")
    assert freeze.is_frozen_path("/home/u/proj/docs/guide/archive/v1.md")
    assert not freeze.is_frozen_path("openspec/changes/archive/2026-09-15-x/tasks.md")
    assert not freeze.is_frozen_path("docspec/changes/_archive/x/change.yaml")


def test_codex_apply_patch_paths_are_checked(monkeypatch):
    patch = ("*** Begin Patch\n*** Update File: src/app.py\n@@\n-a\n+b\n"
             "*** Update File: docs/archive/g_v1.md\n@@\n-x\n+y\n*** End Patch\n")
    assert _guard(monkeypatch, {"tool_name": "apply_patch", "tool_input": {"input": patch}}) == 2
    ok = "*** Begin Patch\n*** Add File: src/new.py\n+print(1)\n*** End Patch\n"
    assert _guard(monkeypatch, {"tool_name": "apply_patch", "tool_input": {"input": ok}}) == 0
    # 透過 shell 呼叫的 apply_patch 也看得到
    assert _guard(monkeypatch, _cmd("apply_patch <<'EOF'\n" + patch + "EOF")) == 2


def test_unparseable_apply_patch_fails_closed(monkeypatch):
    assert _guard(monkeypatch, {"tool_name": "apply_patch", "tool_input": {"input": "garbage"}}) == 2


def test_antigravity_payloads_answer_with_json_decision(monkeypatch, capsys):
    deny = {"toolCall": {"name": "write_to_file", "args": {"TargetFile": "docs/archive/g_v1.md"}}}
    assert _guard(monkeypatch, deny) == 0                       # Antigravity：離開碼 0、看 stdout
    assert json.loads(capsys.readouterr().out)["decision"] == "deny"
    allow = {"toolCall": {"name": "run_command", "args": {"CommandLine": "ls docs/archive"}}}
    assert _guard(monkeypatch, allow) == 0
    assert json.loads(capsys.readouterr().out) == {"decision": "allow"}


@pytest.mark.parametrize("payload,blocked", [
    ({"tool_input": {"file_path": "/p/docspec/governance/decisions/D-claude-1.yaml"}}, True),
    (_cmd("sed -i 's/draft/active/' docspec/governance/decisions/D-claude-1.yaml"), True),
    (_cmd("cat docspec/governance/decisions/D-claude-1.yaml"), False),
    ({"tool_input": {"file_path": "docs/project/status.md"}}, True),
    (_cmd("echo hi > docs/project/status.md"), True),
    ({"tool_input": {"file_path": "docs/guide/_latest.md"}}, False),
])
def test_governance_records_and_views_are_engine_owned(monkeypatch, payload, blocked):
    assert _guard(monkeypatch, payload) == (2 if blocked else 0)
