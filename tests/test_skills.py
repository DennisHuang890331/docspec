"""dspx skills — list / install 到三工具。"""

from __future__ import annotations

from dspx.commands import skills_cmd as skills_cmd
from dspx.frontmatter import parse_frontmatter
from dspx.skills import available_skills

# 六個作者工作流 skill（裝成 skill＋command）
_EXPECTED = {
    "dspx-develop",
    "dspx-draft",
    "dspx-edit",
    "dspx-factcheck",
    "dspx-publish",
    "dspx-release",
}
# support skill（subagent 載入、隨帶 scripts/、不產 command）
_SUPPORT = {"dspx-diagram"}


def test_available_skills_finds_all():
    names = {s.name for s in available_skills()}
    assert names == _EXPECTED | _SUPPORT
    for s in available_skills():
        assert s.description  # 每個都有非空 description


def test_workflow_vs_support_kind():
    by_name = {s.name: s for s in available_skills()}
    for name in _EXPECTED:
        assert by_name[name].is_workflow, f"{name} should be a workflow skill"
    for name in _SUPPORT:
        assert not by_name[name].is_workflow, f"{name} should be a support skill"
        assert by_name[name].kind == "support"


def test_support_skill_ships_vendored_scripts():
    diagram = next(s for s in available_skills() if s.name == "dspx-diagram")
    aux_names = {p.name for p in diagram.aux_files}
    assert {"validate.py", "encode_drawio_url.py", "NOTICE.md"} <= aux_names


def test_install_support_skill_copies_scripts_no_command(tmp_path, monkeypatch):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / ".codexhome"))
    assert skills_cmd.run(["install", "--tool", "claude", "--path", str(tmp_path)]) == 0
    skill_dir = tmp_path / ".claude" / "skills" / "dspx-diagram"
    assert (skill_dir / "SKILL.md").is_file()
    assert (skill_dir / "scripts" / "validate.py").is_file()
    assert (skill_dir / "scripts" / "encode_drawio_url.py").is_file()
    # support skill 不產 slash command
    assert not (tmp_path / ".claude" / "commands" / "dspx" / "diagram.md").exists()


def test_skills_list_returns_zero_and_lists_all(capsys):
    assert skills_cmd.run(["list"]) == 0
    out = capsys.readouterr().out
    for name in _EXPECTED:
        assert name in out


def test_install_claude_writes_skill_with_frontmatter(tmp_path):
    assert skills_cmd.run(["install", "--tool", "claude", "--path", str(tmp_path)]) == 0
    md = tmp_path / ".claude" / "skills" / "dspx-develop" / "SKILL.md"
    assert md.is_file()
    meta, body = parse_frontmatter(md.read_text(encoding="utf-8"), source=md)
    assert meta["name"] == "dspx-develop"
    assert meta["description"]
    assert body.strip()  # 本文有內容
    # 五個都落地
    for name in _EXPECTED:
        assert (tmp_path / ".claude" / "skills" / name / "SKILL.md").is_file()


def test_install_all_writes_skill_and_command_per_tool(tmp_path, monkeypatch):
    codex_home = tmp_path / ".codexhome"
    monkeypatch.setenv("CODEX_HOME", str(codex_home))   # codex command 全域→導向 tmp
    assert skills_cmd.run(["install", "--tool", "all", "--path", str(tmp_path)]) == 0
    # (1) skill：三工具同一套結構 <tool 夾>/skills/<name>/SKILL.md（完整 SKILL.md）
    for base in (".claude", ".agent", ".codex"):
        for name in _EXPECTED:
            assert (tmp_path / base / "skills" / name / "SKILL.md").is_file()
        meta, body = parse_frontmatter(
            (tmp_path / base / "skills" / "dspx-draft" / "SKILL.md").read_text(encoding="utf-8"),
            source=tmp_path)
        assert meta["name"] == "dspx-draft"
        assert meta["description"] and body.strip()
    # (2) command：各工具原生叫用位置
    assert (tmp_path / ".claude" / "commands" / "dspx" / "draft.md").is_file()        # /dspx:draft
    assert (tmp_path / ".agent" / "workflows" / "dspx-draft.md").is_file()            # antigravity
    assert (codex_home / "prompts" / "dspx-draft.md").is_file()                        # codex 全域
    # 不再產單檔 AGENTS.md（OpenSpec 已棄用）
    assert not (tmp_path / "AGENTS.md").exists()


def test_install_claude_writes_freeze_hook(tmp_path):
    import json
    assert skills_cmd.run(["install", "--tool", "claude", "--path", str(tmp_path)]) == 0
    settings = json.loads((tmp_path / ".claude" / "settings.json").read_text(encoding="utf-8"))
    pre = settings["hooks"]["PreToolUse"]
    assert any("hook guard" in str(e) for e in pre)   # C4：docspec 可能是絕對路徑


def test_install_codex_writes_freeze_hook(tmp_path, monkeypatch):
    """C2：Codex hook schema 與 Claude 同構 → 寫 .codex/hooks.json（含 apply_patch matcher）。"""
    import json
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / ".codexhome"))
    assert skills_cmd.run(["install", "--tool", "codex", "--path", str(tmp_path)]) == 0
    hooks_file = tmp_path / ".codex" / "hooks.json"
    assert hooks_file.is_file()
    hooks = json.loads(hooks_file.read_text(encoding="utf-8"))["hooks"]
    guard = hooks["PreToolUse"][0]
    assert "hook guard" in str(guard)                 # C4：docspec 可能是絕對路徑
    assert "apply_patch" in guard["matcher"]


def test_install_codex_only_writes_codex_skill_and_global_prompt(tmp_path, monkeypatch):
    codex_home = tmp_path / ".codexhome"
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    assert skills_cmd.run(["install", "--tool", "codex", "--path", str(tmp_path)]) == 0
    assert (tmp_path / ".codex" / "skills" / "dspx-develop" / "SKILL.md").is_file()
    assert (codex_home / "prompts" / "dspx-develop.md").is_file()
    # codex 單獨不產 claude/antigravity，也不產 AGENTS.md
    assert not (tmp_path / ".claude").exists()
    assert not (tmp_path / ".agent").exists()
    assert not (tmp_path / "AGENTS.md").exists()


def test_install_skips_existing_then_force_overwrites(tmp_path, capsys):
    md = tmp_path / ".claude" / "skills" / "dspx-develop" / "SKILL.md"
    md.parent.mkdir(parents=True)
    md.write_text("USER EDIT", encoding="utf-8")

    assert skills_cmd.run(["install", "--tool", "claude", "--path", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "skipped" in out
    assert md.read_text(encoding="utf-8") == "USER EDIT"  # 未覆寫

    assert skills_cmd.run(
        ["install", "--tool", "claude", "--path", str(tmp_path), "--force"]) == 0
    assert md.read_text(encoding="utf-8") != "USER EDIT"  # 已覆寫
    meta, _ = parse_frontmatter(md.read_text(encoding="utf-8"), source=md)
    assert meta["name"] == "dspx-develop"


def test_install_works_anywhere_no_project_required(tmp_path):
    """install 不需既有 docspec 專案（bootstrap-free，給 init 場景）。"""
    assert skills_cmd.run(["install", "--path", str(tmp_path)]) == 0
    assert (tmp_path / ".codex" / "skills" / "dspx-develop" / "SKILL.md").is_file()


def test_skills_registered_in_cli():
    from dspx.commands import REGISTRY

    assert "skills" in REGISTRY
    assert REGISTRY["skills"].NAME == "skills"


def test_skill_bodies_within_budget():
    """All skills are pure stance; mechanics are projected by `docspec guide`, and
    pack craft by `docspec reference`. No skill (including the slimmed dspx-release)
    exceeds the body budget."""
    budget = 500
    for s in available_skills():
        n = len(s.body.splitlines())
        assert n < budget, f"{s.name} body is {n} lines (>= {budget}); push mechanics to docspec guide"


def test_release_skill_has_no_dead_links():
    """Part B removed REFERENCE.md + scripts/; the release SKILL.md must not point at them."""
    release = next(s for s in available_skills() if s.name == "dspx-release")
    assert "REFERENCE.md" not in release.body
    assert "scripts/measure_fonts" not in release.body
    assert "<skill-dir>" not in release.body


# ── C4：agent-path-portability ──────────────────────────────────

def test_every_skill_step0_has_path_recovery():
    """每個 skill 的靜態 STEP-0 都要教「docspec 不在 PATH」時怎麼自救（Codex 卡死的修法）。"""
    for s in available_skills():
        assert "uv tool dir --bin" in s.body, f"{s.name} STEP-0 lacks docspec-not-found recovery"


# 正準共用 recovery 段落（逐字）。skill 可在其後附 skill-specific 句（如 diagram 的 draw.io），
# 但這段共用文字 MUST 跨 skill 逐字一致——重抄的散文一旦分歧就是鐵律2 漂移（P6）。
_CANONICAL_RECOVERY = (
    "**If `docspec` is not found** — it IS installed (via `uv tool`); your shell's PATH just "
    "predates the install (a freshly-launched or sandboxed agent shell). Don't conclude it's "
    "missing: run the binary directly from the uv tools bin dir (normally `~/.local/bin/docspec`, "
    "Windows `%USERPROFILE%\\.local\\bin\\docspec.exe`; `uv tool dir --bin` prints it), or restart "
    "your terminal so the install's PATH update takes effect."
)


def test_step0_recovery_paragraph_is_byte_identical_across_skills():
    """P6：共用 recovery 段落跨全 skill 逐字一致（防重抄分歧；diagram 的 draw.io 句另附不影響此段）。"""
    for s in available_skills():
        assert _CANONICAL_RECOVERY in s.body, (
            f"{s.name} STEP-0 recovery paragraph diverges from the canonical text")


def test_docspec_invocation_uses_absolute_path(monkeypatch):
    monkeypatch.setattr(skills_cmd.shutil, "which", lambda _: r"C:\Users\u\.local\bin\docspec.exe", raising=False)
    assert skills_cmd._docspec_invocation() == r"C:\Users\u\.local\bin\docspec.exe"


def test_docspec_invocation_quotes_spaces(monkeypatch):
    monkeypatch.setattr(skills_cmd.shutil, "which", lambda _: r"C:\Program Files\bin\docspec.exe", raising=False)
    assert skills_cmd._docspec_invocation() == r'"C:\Program Files\bin\docspec.exe"'


def test_docspec_invocation_falls_back_to_bare(monkeypatch):
    monkeypatch.setattr(skills_cmd.shutil, "which", lambda _: None, raising=False)
    assert skills_cmd._docspec_invocation() == "docspec"


def test_guard_detector_tolerates_absolute_path():
    entry = {"hooks": [{"command": r'"C:\x\docspec.exe" hook guard'}]}
    assert skills_cmd._is_docspec_guard(entry)


def test_dspx_python_m_entrypoint_importable():
    import dspx.__main__ as m
    assert callable(m.main)
