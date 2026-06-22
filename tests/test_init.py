"""dspx init — 專案骨架。"""

from __future__ import annotations

from dspx.commands import init as init_cmd
from dspx.config import load_config


def test_init_creates_project(tmp_path, monkeypatch):
    proj = tmp_path / "新文章專案"
    proj.mkdir()
    monkeypatch.chdir(proj)
    assert init_cmd.run([]) == 0
    home = proj / "docspec"
    assert (home / "config.yaml").is_file()
    assert (home / "corpus").is_dir()
    # 產出的 config 可被載入且預設正確
    cfg = load_config(home)
    assert cfg["schema"] == "section-driven"
    # config 清理（已拍）：有 purpose、無 tags、autonomy 只剩 publish
    assert "purpose" in cfg
    assert "tags" not in cfg
    assert set(cfg["autonomy"]) == {"publish"}
    raw = (home / "config.yaml").read_text(encoding="utf-8")
    assert "purpose:" in raw          # 模板帶 purpose 行
    assert "tags" not in raw          # 模板不再有 tags


def test_init_reinit_refreshes_keeps_custom(tmp_path, monkeypatch):
    proj = tmp_path / "p"
    proj.mkdir()
    monkeypatch.chdir(proj)
    assert init_cmd.run([]) == 0
    cfg = proj / "docspec" / "config.yaml"
    cfg.write_text("language: en\n", encoding="utf-8")     # 使用者客製
    assert init_cmd.run([]) == 0                            # 重 init＝重新設定（不再退 2）
    assert cfg.read_text(encoding="utf-8") == "language: en\n"  # 既有檔保留不覆寫


def test_init_tool_selection_claude_only(tmp_path, monkeypatch):
    proj = tmp_path / "p2"
    proj.mkdir()
    monkeypatch.chdir(proj)
    assert init_cmd.run(["--tool", "claude"]) == 0
    assert (proj / ".claude" / "skills" / "dspx-develop" / "SKILL.md").is_file()
    assert not (proj / ".agent").exists()      # 只裝 claude
    assert not (proj / ".codex").exists()


def test_init_tool_chatgpt_alias(tmp_path, monkeypatch):
    proj = tmp_path / "p3"
    proj.mkdir()
    monkeypatch.chdir(proj)
    assert init_cmd.run(["--tool", "chatgpt"]) == 0   # chatgpt → codex
    assert (proj / ".codex" / "skills" / "dspx-develop" / "SKILL.md").is_file()
    assert not (proj / ".claude").exists()


def test_init_bad_tool(tmp_path, monkeypatch):
    proj = tmp_path / "p4"
    proj.mkdir()
    monkeypatch.chdir(proj)
    assert init_cmd.run(["--tool", "bogus"]) == 2
    assert not (proj / "docspec").exists()     # 非法 → 不建
