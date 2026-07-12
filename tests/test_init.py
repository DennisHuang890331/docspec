"""dspx init — 專案骨架。"""

from __future__ import annotations

from dspx.commands.maintenance import init as init_cmd
from dspx.engine.config import load_config


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


def test_backbone_rule8_crossref_by_anchor_not_handtyped_number():
    """skill-redesign: 規則 8 修錨矛盾——同文件/內部跨文件的節交叉引用一律用穩定錨
    `<!--@id--><!--@-->`（render 注入活 §N）；核准寫法是 anchor-injected §N、被禁的是**手寫**
    章號/字面 §N（會漂）。不再教「引章節人讀標題、禁用 §」的舊矛盾寫法。"""
    guide = init_cmd.build_writing_guide("zh-TW")
    assert "<!--@" in guide                                   # 錨形式（穩定綁 concept.id）
    assert "hand-typed" in guide                              # 手寫章號被禁
    assert "anchor-injected `§N` IS the sanctioned form" in guide   # 核准寫法＝錨注入 §N
    assert "（詳見<錨>）" in guide                              # 寫「（詳見<錨>）」
    # 舊矛盾文案（引人讀標題、禁 §）已移除
    assert "詳見「〈章節標題〉」一節" not in guide
    assert "over `§` notation" not in guide


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


def test_init_scaffolds_gitattributes_lf_pin(tmp_path, monkeypatch):
    """fingerprint-v2 D2 第三層防禦：init 附 .gitattributes（docspec 管的文字檔釘 eol=lf）；
    既有檔不覆寫（保留使用者客製）。"""
    proj = tmp_path / "換行專案"
    proj.mkdir()
    monkeypatch.chdir(proj)
    assert init_cmd.run([]) == 0
    ga = proj / ".gitattributes"
    assert ga.is_file()
    raw = ga.read_text(encoding="utf-8")
    for pattern in ("*.md", "*.yaml", "*.yml"):
        assert f"{pattern} text eol=lf" in raw
    assert b"\r\n" not in ga.read_bytes()          # 腳手架本身也是 LF
    # 重 init 不覆寫使用者客製
    ga.write_text("*.md text eol=lf\n# custom\n", encoding="utf-8")
    assert init_cmd.run([]) == 0
    assert "# custom" in ga.read_text(encoding="utf-8")
