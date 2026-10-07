"""Retiring the executable must preserve project data and foreign tool settings."""

from __future__ import annotations

import json
import re

import pytest

from dspx import cli
from dspx.commands.maintenance import _skills as skills_cmd
from dspx.commands.maintenance import init as init_cmd


@pytest.mark.parametrize("binary", [
    r"C:\工具 空間\Scripts\artispec.exe",
    "/home/user/工具 空間/bin/artispec",
])
def test_hooks_resolve_only_artispec_and_quote_space_paths(monkeypatch, binary):
    looked_up = []

    def resolve(command):
        looked_up.append(command)
        return binary if command == "artispec" else None

    monkeypatch.setattr(skills_cmd.shutil, "which", resolve)
    assert skills_cmd._docspec_invocation() == f'"{binary}"'
    assert looked_up == ["artispec"]


def test_missing_artispec_reports_path_without_using_old_binary(tmp_path, monkeypatch, capsys):
    looked_up = []

    def resolve(command):
        looked_up.append(command)
        return "C:/old/docspec.exe" if command == "docspec" else None

    monkeypatch.setattr(skills_cmd.shutil, "which", resolve)
    assert skills_cmd.run(["install", "--tool", "claude", "--path", str(tmp_path)]) == 0
    captured = capsys.readouterr()
    output = captured.out + captured.err
    assert "artispec" in output and "PATH" in output
    assert "docspec" not in looked_up
    data = json.loads((tmp_path / ".claude/settings.json").read_text(encoding="utf-8"))
    commands = [h["command"] for entries in data["hooks"].values() for e in entries for h in e["hooks"]]
    assert commands == ["artispec hook guard", "artispec hook check"]


@pytest.mark.parametrize("command", [
    "docspec hook guard",
    r'"C:\old tools\docspec.exe" hook guard',
    "/home/old/bin/docspec hook guard",
    "artispec hook guard",
    r'"C:\tools\artispec.exe" hook guard',
])
def test_own_hook_detector_recognizes_legacy_and_new_executables(command):
    assert skills_cmd._is_docspec_guard({"hooks": [{"command": command}]})


@pytest.mark.parametrize("command", [
    "other-tool hook guard",
    "other-tool hook check",
    "echo artispec hook guard",
    "echo docspec hook check",
    "/tools/not-artispec hook guard",
    "python /tools/custom.py hook guard",
])
def test_foreign_hook_commands_are_not_claimed(command):
    entry = {"hooks": [{"type": "command", "command": command}]}
    assert not skills_cmd._is_docspec_guard(entry)
    assert not skills_cmd._is_docspec_postcheck(entry)


@pytest.mark.parametrize("tool,relative,event,post_event", [
    ("claude", ".claude/settings.json", "PreToolUse", "PostToolUse"),
    ("codex", ".codex/hooks.json", "PreToolUse", "PostToolUse"),
    ("gemini", ".gemini/settings.json", "BeforeTool", None),
])
def test_refresh_preserves_foreign_and_mixed_hooks_without_duplicates(tmp_path, monkeypatch, tool, relative, event, post_event):
    monkeypatch.setattr(skills_cmd.shutil, "which", lambda cmd: "/tools/artispec" if cmd == "artispec" else None)
    path = tmp_path / relative
    path.parent.mkdir(parents=True)
    foreign = {"matcher": "custom", "hooks": [{"type": "command", "command": "other-tool hook guard"}]}
    foreign_prompt = {"matcher": "Edit", "hooks": [{"type": "prompt", "prompt": "Check the user's policy."}]}
    mixed_foreign = {"type": "command", "command": "custom-tool hook guard", "timeout": 27}
    mixed = {"matcher": "Write", "custom-field": "preserve", "hooks": [
        {"type": "command", "command": r'"C:\old tools\docspec.exe" hook guard'},
        mixed_foreign,
    ]}
    hooks = {event: [foreign, foreign_prompt, mixed], "UnrelatedEvent": [{"hooks": [{"command": "echo untouched"}]}]}
    foreign_check = {"matcher": "other", "hooks": [{"type": "command", "command": "other-tool hook check"}]}
    if post_event:
        hooks[post_event] = [foreign_check, {"hooks": [{"command": "/old/docspec hook check"}]}]
    original = {"theme": "dark", "permissions": {"allow": ["Bash(pwd)"]}, "hooks": hooks}
    path.write_text(json.dumps(original), encoding="utf-8")
    for _ in range(2):
        skills_cmd._install_hook(tmp_path, tool, [])
    actual = json.loads(path.read_text(encoding="utf-8"))
    assert actual["theme"] == "dark" and actual["permissions"] == original["permissions"]
    assert actual["hooks"]["UnrelatedEvent"] == hooks["UnrelatedEvent"]
    assert foreign in actual["hooks"][event]
    assert foreign_prompt in actual["hooks"][event]
    assert {**mixed, "hooks": [mixed_foreign]} in actual["hooks"][event]
    commands = [h["command"] for e in actual["hooks"][event] for h in e["hooks"] if "command" in h]
    assert commands.count("/tools/artispec hook guard") == 1
    assert all("docspec" not in command for command in commands)
    if post_event:
        assert foreign_check in actual["hooks"][post_event]
        commands = [h["command"] for e in actual["hooks"][post_event] for h in e["hooks"]]
        assert commands.count("/tools/artispec hook check") == 1


@pytest.mark.parametrize("body", [
    "{ not JSON", "[]", "null", '{"hooks": []}',
    '{"hooks": {"PreToolUse": {}}}',
    '{"hooks": {"PreToolUse": [null]}}',
    '{"hooks": {"PreToolUse": [{"hooks": {}}]}}',
    '{"hooks": {"PreToolUse": [{"hooks": [null]}]}}',
    '{"hooks": {"PreToolUse": [{"hooks": [{"command": 12}]}]}}',
])
def test_corrupt_hook_settings_fail_without_replacing_original(tmp_path, monkeypatch, capsys, body):
    monkeypatch.setattr(skills_cmd.shutil, "which", lambda _: "/tools/artispec")
    path = tmp_path / ".claude/settings.json"
    path.parent.mkdir()
    original = body.encode("utf-8")
    path.write_bytes(original)
    assert skills_cmd.run(["install", "--tool", "claude", "--path", str(tmp_path)]) != 0
    assert path.read_bytes() == original
    captured = capsys.readouterr()
    assert "settings.json" in captured.err


@pytest.mark.parametrize("lang", ["en", "zh-TW"])
def test_generated_rules_use_new_commands_and_preserve_managed_markers(lang):
    text = init_cmd.agents_md_block(lang)
    assert "<!-- docspec:begin -->" in text and "<!-- docspec:end -->" in text
    assert "docspec/" in text
    assert not re.search(r"(?:`|\bUsage:\s*)docspec\s+[a-z]", text)
    assert "artispec roadmap show" in text


def test_generated_skill_commands_do_not_recommend_retired_executable(tmp_path, monkeypatch):
    monkeypatch.setattr(skills_cmd.shutil, "which", lambda _: "/tools/artispec")
    assert skills_cmd.run(["install", "--tool", "all", "--path", str(tmp_path)]) == 0
    for base in (".agents", ".claude", ".gemini"):
        for path in (tmp_path / base).rglob("*"):
            if path.is_file() and path.suffix in {".md", ".toml"}:
                text = path.read_text(encoding="utf-8")
                assert not re.search(r"(?:`|\n\s*|\$\s*)docspec\s+(?:init|code|roadmap|handover|show|check|export|freeze)\b", text), path


@pytest.mark.parametrize("command", ["init", "code", "change", "roadmap", "handover", "freeze", "export", "proof"])
def test_current_help_uses_only_artispec_executable(command, capsys):
    try:
        result = cli.main([command, "--help"])
    except SystemExit as exc:
        result = exc.code
    assert result == 0
    captured = capsys.readouterr()
    text = captured.out + captured.err
    assert "artispec" in text
    assert not re.search(r"\bdocspec\s+(?:init|code|change|roadmap|handover|freeze|export|proof)\b", text)


def test_reinit_preserves_owner_rules_and_user_content_containing_old_name(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(skills_cmd.shutil, "which", lambda _: "/tools/artispec")
    home = tmp_path / "docspec"
    home.mkdir()
    config = b"language: en\n# owner config\n"
    (home / "config.yaml").write_bytes(config)
    legacy = b"This archived manual records `docspec show guide` as originally used.\n"
    archive = tmp_path / "docs/archive/guide_v1.md"
    archive.parent.mkdir(parents=True)
    archive.write_bytes(legacy)
    owner_rule = "# User rule\nKeep historical `docspec show guide` examples verbatim.\n"
    agents = tmp_path / "AGENTS.md"
    agents.write_text(owner_rule + "\n<!-- docspec:begin -->\nold managed block\n<!-- docspec:end -->\n", encoding="utf-8")
    for _ in range(2):
        assert init_cmd.run(["--tool", "codex", "--agents-md", "--no-update-check", "--no-tex-hint"]) == 0
    assert agents.read_text(encoding="utf-8").startswith(owner_rule)
    assert agents.read_text(encoding="utf-8").count("<!-- docspec:begin -->") == 1
    assert (home / "config.yaml").read_bytes() == config
    assert archive.read_bytes() == legacy


def test_gemini_refresh_preserves_legacy_hook_controls_and_current_hooks_config(tmp_path, monkeypatch):
    """Gemini's legacy hooks.disabled lives beside event arrays, not inside one."""
    monkeypatch.setattr(skills_cmd.shutil, "which", lambda _: "/tools/artispec")
    path = tmp_path / ".gemini/settings.json"
    path.parent.mkdir()
    foreign = {"matcher": "read_file", "hooks": [{"type": "command", "command": "custom-tool read-check"}]}
    original = {
        "hooksConfig": {"enabled": True, "notifications": False},
        "hooks": {"enabled": False, "notifications": True, "disabled": ["custom-disabled"], "BeforeTool": [foreign]},
    }
    path.write_text(json.dumps(original), encoding="utf-8")
    for _ in range(2):
        skills_cmd._install_hook(tmp_path, "gemini", [])
    actual = json.loads(path.read_text(encoding="utf-8"))
    assert actual["hooksConfig"] == original["hooksConfig"]
    for key in ("enabled", "notifications", "disabled"):
        assert actual["hooks"][key] == original["hooks"][key]
    assert foreign in actual["hooks"]["BeforeTool"]
    assert len(actual["hooks"]["BeforeTool"]) == 2
