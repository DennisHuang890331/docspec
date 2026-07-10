"""凍結區（archive/）保護：freeze hash 抓包、hook guard、Claude hook 生成。"""

from __future__ import annotations

import io
import json

import pytest

from dspx import freeze
from dspx.commands import hook as hook_cmd


def test_is_frozen_path():
    assert freeze.is_frozen_path("docs/guide/archive/v1.md")
    assert freeze.is_frozen_path("docs/archive/guide_v1.md")
    assert not freeze.is_frozen_path("docs/guide/_latest.md")


def test_record_then_verify_detects_tamper(tmp_path):
    home = tmp_path / "docspec"
    home.mkdir()
    root = tmp_path
    docs = root / "docs" / "guide" / "archive"
    docs.mkdir(parents=True)
    snap = docs / "v1.md"
    snap.write_text("frozen content", encoding="utf-8")

    freeze.record(home, root, snap)
    assert (home / ".freeze.yaml").is_file()
    assert freeze.verify(home, root, root / "docs") == []          # 完好

    snap.write_text("TAMPERED", encoding="utf-8")                   # 竄改
    problems = freeze.verify(home, root, root / "docs")
    assert any("tampered" in p for _, p in problems)

    snap.unlink()                                                   # 刪除
    problems = freeze.verify(home, root, root / "docs")
    assert any("deleted" in p for _, p in problems)


def test_verify_flags_untracked_archive_file(tmp_path):
    home = tmp_path / "docspec"
    home.mkdir()
    root = tmp_path
    arch = root / "docs" / "guide" / "archive"
    arch.mkdir(parents=True)
    (arch / "v9.md").write_text("snuck in", encoding="utf-8")       # 沒經 publish 登記
    problems = freeze.verify(home, root, root / "docs")
    assert any("not registered" in p for _, p in problems)


def _run_guard(monkeypatch, payload: dict) -> int:
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    monkeypatch.setattr("sys.stdin.isatty", lambda: False, raising=False)
    return hook_cmd.run(["guard"])


def test_hook_guard_blocks_archive_write(monkeypatch):
    rc = _run_guard(monkeypatch, {"tool_input": {"file_path": "docs/guide/archive/v1.md"}})
    assert rc == 2                                                  # 擋下


def test_hook_guard_allows_latest_write(monkeypatch):
    rc = _run_guard(monkeypatch, {"tool_input": {"file_path": "docs/guide/_latest.md"}})
    assert rc == 0                                                  # 放行


@pytest.mark.parametrize("command", [
    "echo x > docs/g/archive/v1.md",            # 重導寫入
    "echo x >> archive/v1.md",                  # append
    "sed -i 's/a/b/' docs/g/archive/v1.md",     # in-place 改
    "rm docs/g/archive/v1.md",                  # 刪
    "cp _latest.md docs/g/archive/v2.md",       # cp 目的地是 archive
    "mv docs/g/archive/v1.md /tmp/",            # mv 把快照搬走
    "cat foo | tee docs/g/archive/v1.md",       # tee 寫入
    "Remove-Item docs/g/archive/v1.md",         # PowerShell 刪
    "Set-Content -Path docs/g/archive/v1.md -Value x",  # PowerShell 寫
])
def test_command_modifies_archive_blocks(command):
    from dspx.commands.hook import _command_modifies_archive
    assert _command_modifies_archive(command) is True, command


@pytest.mark.parametrize("command", [
    "cat docs/g/archive/v1.md",                 # 純讀
    "grep foo docs/g/archive/v1.md",            # 純讀
    "cp docs/g/archive/v1.md /tmp/x.md",        # 從 archive 複製出來（不影響快照）
    "ls docs/g/archive/",                        # 列目錄
    "echo x > docs/g/_latest.md",               # 寫 _latest（允許）
    "diff docs/g/archive/v1.md docs/g/_latest.md",  # 比對
])
def test_command_leaves_archive_alone_allows(command):
    from dspx.commands.hook import _command_modifies_archive
    assert _command_modifies_archive(command) is False, command


def test_hook_guard_blocks_bash_write_to_archive(monkeypatch):
    rc = _run_guard(monkeypatch, {"tool_input": {"command": "rm docs/g/archive/v1.md"}})
    assert rc == 2


def test_hook_guard_allows_bash_read_from_archive(monkeypatch):
    rc = _run_guard(monkeypatch, {"tool_input": {"command": "cp docs/g/archive/v1.md /tmp/x"}})
    assert rc == 0


def test_hook_guard_blocks_on_bad_json(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("not json"))
    monkeypatch.setattr("sys.stdin.isatty", lambda: False, raising=False)
    assert hook_cmd.run(["guard"]) == 2                            # 解析不了→擋下（fail-closed）


def test_claude_install_writes_freeze_hook(tmp_path):
    from dspx.commands.skills_cmd import _install
    _install(tmp_path, ("claude",), force=True)
    settings = tmp_path / ".claude" / "settings.json"
    assert settings.is_file()
    data = json.loads(settings.read_text(encoding="utf-8"))
    pre = data["hooks"]["PreToolUse"]
    cmds = [h["command"] for e in pre for h in e["hooks"]]
    # C4 portability：docspec 可能被解析成絕對路徑（避免 hook 在 PATH 未更新的 shell 找不到）
    assert any(c.endswith("hook guard") for c in cmds)
    # 冪等：再裝一次不重複
    _install(tmp_path, ("claude",), force=True)
    data2 = json.loads(settings.read_text(encoding="utf-8"))
    guards = [h for e in data2["hooks"]["PreToolUse"] for h in e["hooks"]
              if str(h["command"]).endswith("hook guard")]
    assert len(guards) == 1


def test_claude_install_preserves_existing_settings(tmp_path):
    from dspx.commands.skills_cmd import _install
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps({"permissions": {"allow": ["Bash(ls)"]}}), encoding="utf-8")
    _install(tmp_path, ("claude",), force=True)
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert data["permissions"]["allow"] == ["Bash(ls)"]            # 既有設定保留
    assert data["hooks"]["PreToolUse"]                              # hook 加上


# ── fingerprint v2：凍結 hash 換行正規化＋舊 manifest 自動遷移（change fingerprint-v2 D6）──


def _freeze_home(tmp_path):
    home = tmp_path / "docspec"
    home.mkdir()
    arch = tmp_path / "docs" / "guide" / "archive"
    arch.mkdir(parents=True)
    return home, tmp_path, arch


def test_crlf_lf_checkout_is_not_tamper(tmp_path):
    """LF 檢出不再全報竄改：CRLF 登記 → LF 檢出（同內容）→ verify 零誤報。"""
    home, root, arch = _freeze_home(tmp_path)
    snap = arch / "v1.md"
    snap.write_bytes("frozen content\r\nline two\r\n".encode("utf-8"))
    freeze.record(home, root, snap)
    snap.write_bytes("frozen content\nline two\n".encode("utf-8"))   # 模擬 LF worktree 檢出
    assert freeze.verify(home, root, root / "docs") == []


def test_old_algorithm_manifest_auto_migrates_once(tmp_path, capsys):
    """舊算法 hash 條目：verify 舊算法命中 → 改寫 manifest＋stderr 提示；二次 verify 直接命中。"""
    import hashlib
    import yaml as _yaml
    home, root, arch = _freeze_home(tmp_path)
    snap = arch / "v1.md"
    snap.write_bytes("frozen content\r\nline two\r\n".encode("utf-8"))
    # 手植舊算法（raw bytes 不正規化）hash＝模擬 v2 前 publish 的 manifest
    old_hash = hashlib.sha256(snap.read_bytes()).hexdigest()
    (home / ".freeze.yaml").write_text(
        _yaml.safe_dump({"frozen": {"docs/guide/archive/v1.md": old_hash}}), encoding="utf-8")
    capsys.readouterr()
    assert freeze.verify(home, root, root / "docs") == []            # 命中舊算法、非竄改
    assert "migrated" in capsys.readouterr().err                     # 一行可見提示（非靜默）
    migrated = freeze.load_manifest(home)["docs/guide/archive/v1.md"]
    assert migrated != old_hash                                      # 條目已改寫成新算法
    capsys.readouterr()
    assert freeze.verify(home, root, root / "docs") == []            # 二次 verify 直接命中
    assert "migrated" not in capsys.readouterr().err                 # 遷移一次性


def test_real_tamper_not_laundered_by_fallback(tmp_path):
    """真竄改（內容變）：新舊算法皆不命中 → 照報 tampered、manifest 不被改寫。"""
    home, root, arch = _freeze_home(tmp_path)
    snap = arch / "v1.md"
    snap.write_bytes("frozen content\r\n".encode("utf-8"))
    freeze.record(home, root, snap)
    want = freeze.load_manifest(home)["docs/guide/archive/v1.md"]
    snap.write_bytes("TAMPERED\r\n".encode("utf-8"))
    problems = freeze.verify(home, root, root / "docs")
    assert any("tampered" in p for _, p in problems)
    assert freeze.load_manifest(home)["docs/guide/archive/v1.md"] == want   # 零洗白


def test_legacy_table_gets_same_fallback(tmp_path, capsys):
    """legacy 表（register-legacy 遷入歷版）與封存 hash 走同一 _hash → 同一 fallback 遷移。"""
    import hashlib
    import yaml as _yaml
    home, root, arch = _freeze_home(tmp_path)
    old = arch / "legacy-v0.md"
    old.write_bytes("pre-docspec version\r\n".encode("utf-8"))
    old_hash = hashlib.sha256(old.read_bytes()).hexdigest()
    (home / ".freeze.yaml").write_text(
        _yaml.safe_dump({"frozen": {}, "legacy": {"docs/guide/archive/legacy-v0.md": old_hash}}),
        encoding="utf-8")
    capsys.readouterr()
    assert freeze.verify(home, root, root / "docs") == []
    assert "migrated" in capsys.readouterr().err
    assert freeze.load_legacy(home)["docs/guide/archive/legacy-v0.md"] != old_hash
