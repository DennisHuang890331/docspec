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


# ── writing-guide.md naturalness seed（依 --lang 種通用規則，非「10 檔 genre profile」機械種入）──

def test_build_writing_guide_seeds_zh_naturalness():
    guide = init_cmd.build_writing_guide("zh-TW")
    assert "docspec reference writing-zh" in guide
    assert "動詞當家" in guide and "被字句" in guide and "禁報幕" in guide
    assert "docspec reference writing-en" not in guide.split("## Project conventions")[1]


def test_build_writing_guide_seeds_en_naturalness():
    guide = init_cmd.build_writing_guide("en")
    assert "docspec reference writing-en" in guide
    assert "Verb-centric" in guide and "Active voice" in guide and "AI-ism" in guide
    assert "動詞當家" not in guide


def test_build_writing_guide_unknown_lang_keeps_placeholder():
    guide = init_cmd.build_writing_guide("fr")
    assert "docspec ships no bundled reference for this language yet" in guide
    assert "動詞當家" not in guide and "Verb-centric" not in guide


def test_init_default_lang_seeds_zh(tmp_path, monkeypatch):
    """No --lang → default is zh-TW → writing-guide.md is seeded, not left as an empty scaffold."""
    proj = tmp_path / "p5"
    proj.mkdir()
    monkeypatch.chdir(proj)
    assert init_cmd.run([]) == 0
    guide = (proj / "docspec" / "writing-guide.md").read_text(encoding="utf-8")
    assert "動詞當家" in guide
    assert "docspec reference writing-zh" in guide


def test_init_lang_en_seeds_en(tmp_path, monkeypatch):
    proj = tmp_path / "p6"
    proj.mkdir()
    monkeypatch.chdir(proj)
    assert init_cmd.run(["--lang", "en"]) == 0
    guide = (proj / "docspec" / "writing-guide.md").read_text(encoding="utf-8")
    assert "Verb-centric" in guide
    assert "docspec reference writing-en" in guide
