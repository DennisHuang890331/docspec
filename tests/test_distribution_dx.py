"""export-dx-batch 散布層：安裝來源（PEP 610）、version 輸出、init 非阻塞更新檢查、update。

網路相關一律 mock（urlopen／direct_url.json 讀取），不打真 GitHub。
"""

from __future__ import annotations

import json
import os

import pytest

from dspx.env import _install_source
from dspx import cli
from dspx.commands.maintenance import init as init_cmd
from dspx.commands.maintenance import update as su_cmd
from dspx.commands.maintenance import version as version_cmd


# ── 安裝來源解析（PEP 610 direct_url.json）─────────────────────────

def _fake_dist(payload: str | None):
    class _D:
        def read_text(self, name):   # noqa: ARG002
            return payload
    return lambda name: _D()


def test_read_install_source_git(monkeypatch):
    monkeypatch.setattr("importlib.metadata.distribution", _fake_dist(
        json.dumps({"url": "git+https://github.com/DennisHuang890331/docspec",
                    "vcs_info": {"vcs": "git", "commit_id": "deadbeefcafe1234"}})))
    src = _install_source.read_install_source()
    assert src == {"kind": "git", "commit": "deadbeefcafe1234",
                   "url": "git+https://github.com/DennisHuang890331/docspec"}


def test_read_install_source_dir(monkeypatch):
    monkeypatch.setattr("importlib.metadata.distribution", _fake_dist(
        json.dumps({"url": "file:///home/u/docspec", "dir_info": {"editable": False}})))
    src = _install_source.read_install_source()
    assert src["kind"] == "dir" and src["path"] == "/home/u/docspec"


def test_read_install_source_dir_windows_path(monkeypatch):
    monkeypatch.setattr("importlib.metadata.distribution", _fake_dist(
        json.dumps({"url": "file:///C:/proj/docspec", "dir_info": {}})))
    src = _install_source.read_install_source()
    assert src["kind"] == "dir" and src["path"] == "C:/proj/docspec"


def test_read_install_source_absent(monkeypatch):
    monkeypatch.setattr("importlib.metadata.distribution", _fake_dist(None))
    assert _install_source.read_install_source() is None


def test_read_install_source_unparsable(monkeypatch):
    monkeypatch.setattr("importlib.metadata.distribution", _fake_dist("{not json"))
    assert _install_source.read_install_source() is None


def test_read_install_source_dist_error(monkeypatch):
    def _boom(name):  # noqa: ARG001
        raise ValueError("no dist")
    monkeypatch.setattr("importlib.metadata.distribution", _boom)
    assert _install_source.read_install_source() is None


def test_update_command_and_argv():
    git = {"kind": "git", "commit": "x", "url": "u"}
    assert "uv tool install --from" in _install_source.update_command(git)
    assert "--reinstall" in _install_source.update_command(git)
    assert _install_source.update_argv(git)[0] == "uv" and "--reinstall" in _install_source.update_argv(git)
    assert _install_source.update_command({"kind": "dir", "path": "/x"}) == "uv tool upgrade docspec"
    assert _install_source.update_command(None) == "uv tool upgrade docspec"


# ── version 輸出（安裝來源 + typst 版本）──────────────────────────

def _stub_versions(monkeypatch):
    monkeypatch.setattr(version_cmd, "_typst_version", lambda: "0.13.1")
    monkeypatch.setattr(version_cmd, "_pandoc_version", lambda: "3.1.11")
    monkeypatch.setattr(version_cmd, "_tinytex_version", lambda: "(not installed; run `docspec setup`)")


def test_version_report_git_source(monkeypatch):
    _stub_versions(monkeypatch)
    monkeypatch.setattr(_install_source, "read_install_source", lambda *a, **k: {
        "kind": "git", "commit": "abc123def456789", "url": "git+https://github.com/DennisHuang890331/docspec"})
    out = version_cmd.report()
    assert "installed from git@abc123def456" in out    # commit[:12]
    assert "typst" in out and "0.13.1" in out and "default render engine" in out
    assert "pandoc" in out and "3.1.11" in out
    assert "optional LaTeX track" in out


def test_version_report_dir_source(monkeypatch):
    _stub_versions(monkeypatch)
    monkeypatch.setattr(_install_source, "read_install_source", lambda *a, **k: {
        "kind": "dir", "path": "/home/u/docspec"})
    out = version_cmd.report()
    assert "installed from directory /home/u/docspec" in out
    assert "build snapshot" in out and "uv tool upgrade docspec" in out


def test_version_report_no_source_omits_line(monkeypatch):
    _stub_versions(monkeypatch)
    monkeypatch.setattr(_install_source, "read_install_source", lambda *a, **k: None)
    out = version_cmd.report()
    assert "installed from" not in out
    assert "typst" in out       # 其餘輸出照常


def test_typst_version_reads_subprocess(monkeypatch):
    from dspx.engine import paths
    monkeypatch.setattr(paths, "resolve_typst", lambda: "typst")

    class _R:
        stdout = "typst 0.13.1 (abc123)\n"
    monkeypatch.setattr(version_cmd.subprocess, "run", lambda *a, **k: _R())
    assert version_cmd._typst_version() == "0.13.1"


def test_typst_version_missing_hints(monkeypatch):
    from dspx.engine import paths
    monkeypatch.setattr(paths, "resolve_typst", lambda: None)
    assert "docspec setup" in version_cmd._typst_version()


# ── init 非阻塞更新檢查（全 mock）─────────────────────────────────

def _init_dir(tmp_path, monkeypatch, name):
    proj = tmp_path / name
    proj.mkdir()
    monkeypatch.chdir(proj)
    return proj


def test_init_update_check_git_behind(tmp_path, monkeypatch, capsys):
    _init_dir(tmp_path, monkeypatch, "p")
    monkeypatch.setattr(_install_source, "read_install_source",
                        lambda *a, **k: {"kind": "git", "commit": "aaaaaaa", "url": "u"})
    monkeypatch.setattr(init_cmd, "_github_head_sha", lambda *a, **k: "bbbbbbbbbbbb")
    assert init_cmd.run(["--tool", "claude"]) == 0
    out = capsys.readouterr().out
    assert "Update available" in out and "uv tool install --from" in out


def test_init_update_check_git_uptodate_silent(tmp_path, monkeypatch, capsys):
    _init_dir(tmp_path, monkeypatch, "p")
    monkeypatch.setattr(_install_source, "read_install_source",
                        lambda *a, **k: {"kind": "git", "commit": "abcdef1234", "url": "u"})
    monkeypatch.setattr(init_cmd, "_github_head_sha", lambda *a, **k: "abcdef1234567890")
    assert init_cmd.run(["--tool", "claude"]) == 0
    assert "Update available" not in capsys.readouterr().out


def test_init_update_check_network_error_silent_and_exit_unchanged(tmp_path, monkeypatch, capsys):
    _init_dir(tmp_path, monkeypatch, "p")
    monkeypatch.setattr(_install_source, "read_install_source",
                        lambda *a, **k: {"kind": "git", "commit": "aaaaaaa", "url": "u"})

    def _boom(*a, **k):
        raise OSError("no network")
    monkeypatch.setattr(init_cmd, "_github_head_sha", _boom)
    rc = init_cmd.run(["--tool", "claude"])
    assert rc == 0                                   # 例外不改離開碼
    out = capsys.readouterr().out
    assert "Update available" not in out and "Update:" not in out   # 完全靜默


def test_init_update_check_dir_offline_no_network(tmp_path, monkeypatch, capsys):
    _init_dir(tmp_path, monkeypatch, "p")
    monkeypatch.setattr(_install_source, "read_install_source",
                        lambda *a, **k: {"kind": "dir", "path": "/x/docspec"})
    called = []
    monkeypatch.setattr(init_cmd, "_github_head_sha",
                        lambda *a, **k: called.append(1) or "z")
    assert init_cmd.run(["--tool", "claude"]) == 0
    out = capsys.readouterr().out
    assert "snapshot" in out and "uv tool upgrade docspec" in out
    assert not called                                # 目錄裝＝零網路呼叫


def test_init_no_update_check_flag_skips_entirely(tmp_path, monkeypatch):
    _init_dir(tmp_path, monkeypatch, "p")
    called = []
    monkeypatch.setattr(init_cmd, "_print_update_check", lambda: called.append(1))
    assert init_cmd.run(["--tool", "claude", "--no-update-check"]) == 0
    assert not called


def test_init_update_check_no_source_silent(tmp_path, monkeypatch, capsys):
    _init_dir(tmp_path, monkeypatch, "p")
    monkeypatch.setattr(_install_source, "read_install_source", lambda *a, **k: None)
    assert init_cmd.run(["--tool", "claude"]) == 0
    out = capsys.readouterr().out
    assert "Update available" not in out and "Update:" not in out


# ── self-update（預設印指令、--run detached）──────────────────────

def test_self_update_prints_git_command(monkeypatch, capsys):
    monkeypatch.setattr(_install_source, "read_install_source",
                        lambda *a, **k: {"kind": "git", "commit": "x", "url": "u"})
    assert su_cmd.run([]) == 0
    out = capsys.readouterr().out
    assert "uv tool install --from" in out and "--reinstall" in out


def test_self_update_prints_dir_command(monkeypatch, capsys):
    monkeypatch.setattr(_install_source, "read_install_source",
                        lambda *a, **k: {"kind": "dir", "path": "/x"})
    assert su_cmd.run([]) == 0
    assert "uv tool upgrade docspec" in capsys.readouterr().out


def test_self_update_unknown_source_generic_hint(monkeypatch, capsys):
    monkeypatch.setattr(_install_source, "read_install_source", lambda *a, **k: None)
    assert su_cmd.run([]) == 0
    assert "uv tool upgrade docspec" in capsys.readouterr().out


def test_self_update_run_launches_detached_not_waited(monkeypatch, capsys):
    monkeypatch.setattr(_install_source, "read_install_source",
                        lambda *a, **k: {"kind": "git", "commit": "x", "url": "u"})
    calls = {}

    class _FakePopen:
        def __init__(self, argv, **kw):
            calls["argv"] = argv
            calls["kw"] = kw
        # 刻意無 wait/communicate：run() 不得等待

    monkeypatch.setattr(su_cmd.subprocess, "Popen", _FakePopen)
    assert su_cmd.run(["--run"]) == 0
    assert calls["argv"][0] == "uv" and "--reinstall" in calls["argv"]
    if os.name == "nt":
        assert "creationflags" in calls["kw"]        # DETACHED_PROCESS|新 process group
    else:
        assert calls["kw"].get("start_new_session") is True
    assert "docspec version" in capsys.readouterr().out


# ── 兩層 help：update 露、template 藏 ─────────────────────────

def test_default_help_lists_update(capsys):
    cli.main(["--help"])
    out = capsys.readouterr().out
    assert "\n  update" in out
    assert "\n  template" not in out           # agent-facing、預設 help 不列


def test_help_all_lists_template_and_update(capsys):
    cli.main(["--help-all"])
    out = capsys.readouterr().out
    assert "template" in out and "\n  update" in out


def test_update_runnable_by_direct_dispatch(monkeypatch, capsys):
    monkeypatch.setattr(_install_source, "read_install_source", lambda *a, **k: None)
    assert cli.main(["update"]) == 0
    assert "uv tool upgrade docspec" in capsys.readouterr().out
