"""dspx skills — list / install 到三工具。"""

from __future__ import annotations

from dspx.commands.maintenance import _skills as skills_cmd
from dspx.env.frontmatter import parse_frontmatter
from dspx.env.skills import available_skills

# 五個作者工作流 skill（裝成 skill＋command）——draft+edit 已併為單一 apply
_EXPECTED = {
    "dspx-develop",
    "dspx-apply",
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
    # skill-redesign: the mechanical craft (XML skeleton / shapes / export flags / troubleshooting)
    # moved out of the SKILL.md body into a sibling reference.md — it installs alongside as an aux file.
    assert (skill_dir / "reference.md").is_file()
    ref = (skill_dir / "reference.md").read_text(encoding="utf-8")
    assert "draw.io XML skeleton" in ref and "ELECTRON_RUN_AS_NODE" in ref
    # support skill 不產 slash command
    assert not (tmp_path / ".claude" / "commands" / "dspx" / "diagram.md").exists()


def test_diagram_reference_is_a_sibling_aux_file():
    """reference.md is a diagram-skill aux file (not the SKILL.md), so it ships with the support skill."""
    diagram = next(s for s in available_skills() if s.name == "dspx-diagram")
    aux_names = {p.name for p in diagram.aux_files}
    assert "reference.md" in aux_names
    # the skill body points at it and no longer inlines the actual XML skeleton / shape tables
    assert "reference.md" in diagram.body
    assert "<mxfile" not in diagram.body           # the raw skeleton lives in reference.md, not the body
    assert "rounded=1;whiteSpace=wrap" not in diagram.body   # the shape-style table moved out too


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
            (tmp_path / base / "skills" / "dspx-apply" / "SKILL.md").read_text(encoding="utf-8"),
            source=tmp_path)
        assert meta["name"] == "dspx-apply"
        assert meta["description"] and body.strip()
    # (2) command：各工具原生叫用位置
    assert (tmp_path / ".claude" / "commands" / "dspx" / "apply.md").is_file()        # /dspx:apply
    assert (tmp_path / ".agent" / "workflows" / "dspx-apply.md").is_file()            # antigravity
    assert (codex_home / "prompts" / "dspx-apply.md").is_file()                        # codex 全域
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
    """install 不需既有 docspec 專案（bootstrap-free，給 init 場景）。預設只裝單一 claude。"""
    assert skills_cmd.run(["install", "--path", str(tmp_path)]) == 0
    assert (tmp_path / ".claude" / "skills" / "dspx-develop" / "SKILL.md").is_file()


def test_install_default_is_single_agent_not_all(tmp_path):
    """預設只裝 claude 一家，不灑 .agent/.codex（三家不共享 memory，別污染專案）。"""
    assert skills_cmd.run(["install", "--path", str(tmp_path)]) == 0
    assert (tmp_path / ".claude").is_dir()
    assert not (tmp_path / ".agent").exists()
    assert not (tmp_path / ".codex").exists()


def test_install_tool_all_installs_every_agent(tmp_path):
    """明確 `--tool all` 才裝三家（共享 memory 的場景）。"""
    assert skills_cmd.run(["install", "--tool", "all", "--path", str(tmp_path)]) == 0
    for d in (".claude", ".agent", ".codex"):
        assert (tmp_path / d / "skills" / "dspx-develop" / "SKILL.md").is_file()


def test_skills_folded_into_init():
    """skills 退場：安裝併進 `docspec init`（含 reinit 冪等補裝、--tool 選家）；不再是頂層指令。"""
    from dspx.commands import REGISTRY
    assert "skills" not in REGISTRY


# skill-redesign: every workflow SKILL.md is a thin drive-through driver — the rules live in the
# schema/init projections and are pulled at runtime; the skill only anchors to them. Per-skill body
# budgets (D1/D5); mechanics beyond the budget go to `docspec guide` / instructions / reference.md.
_BODY_BUDGET = {
    "dspx-apply": 150, "dspx-develop": 120, "dspx-factcheck": 90,
    "dspx-publish": 80, "dspx-release": 90, "dspx-diagram": 90,
}


def test_skill_bodies_within_per_skill_budget():
    """Each redesigned skill respects its own line budget (drive-through format, no restated rules)."""
    for s in available_skills():
        budget = _BODY_BUDGET.get(s.name)
        assert budget is not None, f"{s.name} has no declared budget"
        n = len(s.body.splitlines())
        assert n < budget, f"{s.name} body is {n} lines (>= {budget}); push mechanics to the projections"


def test_every_skill_is_drive_through_format():
    """D1 contract: four-section structure (Input/Steps/Output/Guardrails), each anchored to docspec
    commands. Every workflow + support skill follows it."""
    for s in available_skills():
        for section in ("**Input**", "**Steps**", "**Output**", "**Guardrails**"):
            assert section in s.body, f"{s.name} body missing {section}"
        # the driver leans on the engine: every skill invokes docspec commands
        assert "docspec " in s.body, f"{s.name} does not anchor to any docspec command"


def test_skill_bodies_carry_no_environment_troubleshooting():
    """PATH troubleshooting block is GONE from the body — environment needs live in frontmatter
    compatibility only (skill-redesign); the body carries zero environment noise."""
    for s in available_skills():
        for noise in ("PATH", "not found", "reinstall"):
            assert noise not in s.body, f"{s.name} body still carries environment noise: {noise!r}"


def test_every_skill_frontmatter_has_compatibility_with_path_recovery():
    """Environment need (incl. the docspec-not-found recovery) is carried by the frontmatter
    `compatibility` field, one line, so the body stays clean. It survives install (skills.py .text)."""
    for s in available_skills():
        compat = s.frontmatter.get("compatibility")
        assert compat, f"{s.name} frontmatter lacks a compatibility field"
        assert "uv tool dir --bin" in compat, f"{s.name} compatibility lacks the PATH recovery hint"
        assert "never reinstall" in compat, f"{s.name} compatibility lacks the never-reinstall guard"


def test_every_skill_frontmatter_carries_uniform_license():
    """Human review: all 6 skills carry the repo's own license (was inconsistent — only 3 did),
    aligning with OpenSpec's skill license-field convention."""
    for s in available_skills():
        assert s.frontmatter.get("license") == "PolyForm-Noncommercial-1.0.0", (
            f"{s.name} frontmatter lacks the uniform license field")


def test_compatibility_survives_install(tmp_path):
    """skills.py .text preserves the full frontmatter — otherwise the compatibility field (the only
    home for the env recovery after the body block was removed) is dropped at install time."""
    from dspx.env.frontmatter import parse_frontmatter
    assert skills_cmd.run(["install", "--tool", "claude", "--path", str(tmp_path)]) == 0
    md = tmp_path / ".claude" / "skills" / "dspx-apply" / "SKILL.md"
    meta, _ = parse_frontmatter(md.read_text(encoding="utf-8"), source=md)
    assert "uv tool dir --bin" in (meta.get("compatibility") or "")


def test_no_skill_body_restates_the_projected_rules():
    """grep: the verdict-verb whitelist, the dispatch exclusion list, and the long-form writing
    principles now live ONLY in the `instructions apply` projection — no skill body re-copies them
    (iron law 2: rules live in the schema, get projected, never duplicated in drifting skill prose)."""
    for s in available_skills():
        body = s.body
        # the whole ack-own whitelist / the exclusion list header must not be pasted into a skill
        assert "── Verdict verbs ──" not in body, f"{s.name} restates the verdict-verb block"
        assert "── Dispatch exclusions ──" not in body, f"{s.name} restates the dispatch exclusion block"
        # the item-by-item whitelist detail (the exhaustive structural-metadata list) is not re-copied
        assert "This whitelist is EXHAUSTIVE" not in body, f"{s.name} pastes the ack-own whitelist detail"
        # the exclusion-list intro sentence is not re-copied into any body
        assert "copy this exclusion list" not in body.lower(), f"{s.name} pastes the exclusion-list brief"


def test_apply_zero_inference_important_sits_inside_the_rewrite_write_step():
    """D3 / task 3.2: zero-inference [TBD] is the ONE inline IMPORTANT, and it sits INSIDE apply's
    rewrite write step — not at the file end, not buried mid-list. (The projection dual-carries the
    authority; this is the attention half.)"""
    body = next(s for s in available_skills() if s.name == "dspx-apply").body
    imp = body.index("IMPORTANT — zero-inference")
    steps = body.index("**Steps**")
    rewrite = body.index("3. **rewrite**")
    align = body.index("4. **align**")
    output = body.index("**Output**")
    # the IMPORTANT is in the rewrite step, between the Steps header and Output (not the file tail)
    assert steps < rewrite < imp < align < output
    seg = body[rewrite:align]
    assert "[TBD]" in seg and "unforgivable" in seg      # the iron-law core is present in that step


def test_release_skill_has_no_dead_links():
    """Part B removed REFERENCE.md + scripts/; the release SKILL.md must not point at them."""
    release = next(s for s in available_skills() if s.name == "dspx-release")
    assert "REFERENCE.md" not in release.body
    assert "scripts/measure_fonts" not in release.body
    assert "<skill-dir>" not in release.body


# ── C4：agent-path-portability (now carried by frontmatter compatibility, not a body STEP-0) ──

def test_agent_path_recovery_now_lives_in_compatibility_not_body():
    """skill-redesign: the docspec-not-found recovery (the Codex-hang fix) moved out of a body STEP-0
    block into the one-line frontmatter `compatibility` field — so the body stays clean and the
    recovery still reaches the agent (it survives install via skills.py .text)."""
    for s in available_skills():
        compat = s.frontmatter.get("compatibility") or ""
        assert "uv tool dir --bin" in compat, f"{s.name} compatibility lacks the not-found recovery"
        # the old body STEP-0 recovery paragraph must be gone
        assert "If `docspec` is not found" not in s.body, f"{s.name} still carries a body STEP-0 block"


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
